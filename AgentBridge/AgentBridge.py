#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Brian Caudill
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Agent Bridge gramplet.

Embeds a control bridge inside the running Gramps process so an external agent
(typically an AI via the bundled MCP server) can drive the live application.
The agent communicates through a watched control directory: it drops request
files, the bridge executes them on the GTK main thread and writes response
files.

SECURITY: this executes arbitrary Python inside Gramps with the privileges of
the user running it.  It listens on no network port -- control is purely via
files under ``~/.gramps_agent`` -- so anyone able to write to that directory
(i.e. this user account) can run code in Gramps.  Only enable it on a machine
you trust, and remove the gramplet when you are done.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import os
import io
import hmac
import json
import time
import stat
import secrets
import logging
import traceback
import contextlib

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import GLib

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

LOG = logging.getLogger("AgentBridge")

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------
CONTROL_DIR = os.path.join(os.path.expanduser("~"), ".gramps_agent")
REQ_DIR = os.path.join(CONTROL_DIR, "requests")
RESP_DIR = os.path.join(CONTROL_DIR, "responses")
TOKEN_FILE = os.path.join(CONTROL_DIR, "token")
POLL_MS = 300
MAX_REPR = 20000


# -------------------------------------------------------------------------
#
# Helper functions
#
# -------------------------------------------------------------------------
def _ensure_token():
    """
    Return the shared secret, creating it on first run.

    An explicit ``GRAMPS_AGENT_TOKEN`` environment variable wins; otherwise the
    token is read from (or generated into) ``TOKEN_FILE`` with owner-only
    permissions. Every request must carry this token or it is refused.
    """
    env_token = os.environ.get("GRAMPS_AGENT_TOKEN")
    if env_token:
        return env_token
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
            existing = handle.read().strip()
        if existing:
            return existing
    except OSError:
        pass
    token = secrets.token_hex(32)
    with open(TOKEN_FILE, "w", encoding="utf-8") as handle:
        handle.write(token)
    try:
        os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return token



def _safe_repr(value):
    """
    Return a length-bounded repr of a value, never raising.
    """
    try:
        text = repr(value)
    except Exception:
        try:
            text = "<unreprable %s>" % type(value).__name__
        except Exception:
            text = "<unreprable>"
    if len(text) > MAX_REPR:
        text = text[:MAX_REPR] + "... [truncated]"
    return text


# -------------------------------------------------------------------------
#
# AgentBridge
#
# -------------------------------------------------------------------------
class AgentBridge(Gramplet):
    """
    Poll a control directory and execute agent requests on the main loop.
    """

    def init(self):
        """
        Set up the control directory and start the polling timer.
        """
        self._ns = None
        self._timer_id = None
        self._served = 0
        self._token = None
        self.gui.set_text(_("Agent Bridge starting..."))
        try:
            os.makedirs(REQ_DIR, exist_ok=True)
            os.makedirs(RESP_DIR, exist_ok=True)
            self._token = _ensure_token()
        except OSError as err:
            self.gui.set_text(_("Agent Bridge error: %s") % err)
            LOG.error("Could not initialize control dir: %s", err)
            return
        self._start()
        self._set_status()

    def _start(self):
        """
        Start the GLib poll timer if it is not already running.
        """
        if self._timer_id is None:
            self._timer_id = GLib.timeout_add(POLL_MS, self._poll)

    def _set_status(self):
        """
        Update the gramplet status text.
        """
        db_name = _("(no tree)")
        try:
            if self.dbstate.is_open():
                db_name = self.dbstate.db.get_dbname()
        except Exception:
            pass
        self.gui.set_text(
            _("Agent Bridge active.\n")
            + _("Watching: %s\n") % REQ_DIR
            + _("Tree: %s\n") % db_name
            + _("Requests served: %d") % self._served
        )

    def main(self):
        """
        Refresh status on update events. No periodic work is done here.
        """
        self._set_status()

    def _namespace(self):
        """
        Return the persistent exec namespace, refreshing live references.
        """
        if self._ns is None:
            import gramps.gen.lib as gramps_lib

            self._ns = {
                "__name__": "agent_bridge",
                "gramps_lib": gramps_lib,
                "bridge": self,
            }
        # Keep live handles fresh on every call -- the tree can change.
        self._ns["dbstate"] = self.dbstate
        self._ns["uistate"] = self.uistate
        self._ns["gui"] = self.gui
        self._ns["db"] = self.dbstate.db if self.dbstate.is_open() else None
        return self._ns

    def _poll(self):
        """
        Process any pending request files. Always returns True to keep polling.
        """
        try:
            names = sorted(
                name for name in os.listdir(REQ_DIR) if name.endswith(".req.json")
            )
        except FileNotFoundError:
            return True
        for name in names:
            path = os.path.join(REQ_DIR, name)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    req = json.load(handle)
            except (ValueError, OSError):
                # File may still be partly written; leave it for the next tick.
                continue
            try:
                os.remove(path)
            except OSError:
                pass
            rid = req.get("id") or name[: -len(".req.json")]
            resp = self._handle(req)
            self._served += 1
            self._write_response(rid, resp)
            self._set_status()
        return True

    def _handle(self, req):
        """
        Dispatch a single request to the matching action handler.

        Requests must carry the shared secret token or they are refused without
        executing anything.
        """
        if not self._token or not hmac.compare_digest(
            str(req.get("token") or ""), self._token
        ):
            return {"ok": False, "error": "unauthorized: missing or invalid token"}
        action = req.get("action", "eval")
        try:
            if action == "ping":
                return {"ok": True, "pong": True, "served": self._served}
            if action == "eval":
                return self._do_eval(req.get("code", ""))
            if action == "install_plugin":
                return self._do_install(req)
            return {"ok": False, "error": "unknown action: %r" % action}
        except Exception:
            return {"ok": False, "error": traceback.format_exc()}

    def _do_eval(self, code):
        """
        Execute submitted code in the persistent namespace.

        Captures stdout/stderr. If the code assigns a variable named ``result``
        its repr is returned.
        """
        namespace = self._namespace()
        namespace["result"] = None
        stream = io.StringIO()
        try:
            compiled = compile(code, "<agent>", "exec")
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(
                stream
            ):
                exec(compiled, namespace)
            return {
                "ok": True,
                "stdout": stream.getvalue(),
                "result": _safe_repr(namespace.get("result")),
            }
        except Exception:
            return {
                "ok": False,
                "stdout": stream.getvalue(),
                "error": traceback.format_exc(),
            }

    def _do_install(self, req):
        """
        Write one or more plugin files to the user plugin directory and reload.

        Expects ``req['files']`` as a mapping of relative path -> file contents,
        and an optional ``req['name']`` used as the containing directory.
        """
        from gramps.gen.const import USER_PLUGINS
        from gramps.gen.plug import BasePluginManager

        files = req.get("files") or {}
        if not isinstance(files, dict) or not files:
            return {"ok": False, "error": "install_plugin needs a 'files' mapping"}
        subdir = req.get("name", "agent_plugin")
        target = os.path.join(USER_PLUGINS, subdir)
        os.makedirs(target, exist_ok=True)
        written = []
        for relpath, content in files.items():
            dest = os.path.join(target, relpath)
            os.makedirs(os.path.dirname(dest) or target, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as handle:
                handle.write(content)
            written.append(dest)
        pmgr = BasePluginManager.get_instance()
        # Scan the freshly written directory so a brand-new plugin registers.
        pmgr.reg_plugins(target, self.dbstate, self.uistate, rescan=True)
        return {"ok": True, "written": written, "dir": target}

    def _write_response(self, rid, resp):
        """
        Write a response file atomically (temp file then rename).
        """
        resp.setdefault("ok", True)
        resp["id"] = rid
        resp["ts"] = time.time()
        tmp = os.path.join(RESP_DIR, "%s.part" % rid)
        final = os.path.join(RESP_DIR, "%s.resp.json" % rid)
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(resp, handle)
            os.replace(tmp, final)
        except OSError as err:
            LOG.error("Could not write response %s: %s", rid, err)

    def on_save(self):
        """
        Stop the poll timer when the gramplet is disposed.
        """
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
