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
MCP server for the Gramps Agent Bridge.

Exposes the live Gramps application to any MCP-capable AI as a set of tools.
This process speaks the Model Context Protocol over stdio to the AI client and
forwards each call to the Agent Bridge gramplet running inside Gramps, using a
shared control directory (default ``~/.gramps_agent``).

Requirements (in the Python that launches this server, NOT Gramps' bundled
interpreter):

    pip install "mcp[cli]"

Register with an MCP client, e.g. Claude Code:

    claude mcp add gramps -- python /path/to/gramps_mcp_server.py

or add to a project ``.mcp.json``:

    {
      "mcpServers": {
        "gramps": { "command": "python",
                    "args": ["/path/to/gramps_mcp_server.py"] }
      }
    }

The Agent Bridge gramplet must be added to the Gramps Dashboard for these tools
to do anything; otherwise calls time out with a helpful message.
"""
import os
import json
import time
import uuid

from mcp.server.fastmcp import FastMCP

CONTROL_DIR = os.environ.get(
    "GRAMPS_AGENT_DIR", os.path.join(os.path.expanduser("~"), ".gramps_agent")
)
REQ_DIR = os.path.join(CONTROL_DIR, "requests")
RESP_DIR = os.path.join(CONTROL_DIR, "responses")
TOKEN_FILE = os.path.join(CONTROL_DIR, "token")
DEFAULT_TIMEOUT = float(os.environ.get("GRAMPS_AGENT_TIMEOUT", "60"))

mcp = FastMCP("gramps")


def _read_token():
    """Return the shared secret expected by the bridge, or '' if not found.

    Read fresh each call so a token the gramplet generates after this server
    starts is still picked up."""
    env_token = os.environ.get("GRAMPS_AGENT_TOKEN")
    if env_token:
        return env_token
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


# -------------------------------------------------------------------------
#
# Transport: write a request file, wait for the response file
#
# -------------------------------------------------------------------------
def _call(action, timeout=DEFAULT_TIMEOUT, **payload):
    """Send one request to the bridge and block for its response."""
    os.makedirs(REQ_DIR, exist_ok=True)
    os.makedirs(RESP_DIR, exist_ok=True)
    rid = uuid.uuid4().hex[:12]
    request = {"id": rid, "action": action, "token": _read_token()}
    request.update(payload)

    tmp = os.path.join(REQ_DIR, rid + ".req.json.part")
    final = os.path.join(REQ_DIR, rid + ".req.json")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(request, handle)
    os.replace(tmp, final)

    respfile = os.path.join(RESP_DIR, rid + ".resp.json")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(respfile):
            try:
                with open(respfile, "r", encoding="utf-8") as handle:
                    resp = json.load(handle)
            except (ValueError, OSError):
                time.sleep(0.1)
                continue
            try:
                os.remove(respfile)
            except OSError:
                pass
            return resp
        time.sleep(0.1)
    return {
        "ok": False,
        "error": (
            "Timed out after %ss. Is Gramps running with the 'Agent Bridge' "
            "gramplet added to the Dashboard? Control dir: %s" % (timeout, CONTROL_DIR)
        ),
    }


# -------------------------------------------------------------------------
#
# Core tools
#
# -------------------------------------------------------------------------
@mcp.tool()
def gramps_status() -> dict:
    """Check whether the Gramps Agent Bridge is reachable and report how many
    requests it has served. Use this first to confirm the connection."""
    return _call("ping", timeout=10)


@mcp.tool()
def gramps_eval(code: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Run Python code inside the live Gramps process and return its output.

    The code runs on the GTK main thread in a persistent namespace, so it can
    safely read or modify the family tree and drive the user interface, and
    names defined in one call remain available to later calls. These names are
    pre-bound: ``dbstate`` (the DbState), ``db`` (the open database or None),
    ``uistate`` (the UIState), ``gui`` (the gramplet view), ``gramps_lib``
    (gramps.gen.lib), and ``bridge`` (the gramplet itself).

    Assign to a variable named ``result`` to return a value; anything printed
    is captured as ``stdout``. Example:
        result = db.get_number_of_people()
    Returns a dict with ``ok`` and either ``stdout``/``result`` or ``error``."""
    return _call("eval", code=code, timeout=timeout)


@mcp.tool()
def gramps_install_plugin(name: str, files: dict, timeout: float = 30) -> dict:
    """Write a Gramps plugin into the user plugin directory and hot-reload it.

    ``name`` is the plugin subdirectory; ``files`` maps relative file paths to
    their text contents (include a ``*.gpr.py`` registration file plus the
    module). After this the plugin is registered and can be run via gramps_eval.
    Returns the list of written paths."""
    return _call("install_plugin", name=name, files=files, timeout=timeout)


# -------------------------------------------------------------------------
#
# Convenience tools (thin wrappers over gramps_eval)
#
# -------------------------------------------------------------------------
@mcp.tool()
def gramps_people_count() -> dict:
    """Return the number of people in the currently open family tree."""
    return _call(
        "eval",
        code="result = db.get_number_of_people() if db else 'no tree open'",
        timeout=20,
    )


@mcp.tool()
def gramps_search_people(text: str, limit: int = 25) -> dict:
    """Search people by surname or given name (case-insensitive substring).

    Returns up to ``limit`` matches as a list of {gramps_id, name} dicts."""
    code = (
        "matches = []\n"
        "needle = %r.lower()\n"
        "if db:\n"
        "    for person in db.iter_people():\n"
        "        name = person.get_primary_name().get_name()\n"
        "        if needle in name.lower():\n"
        "            matches.append({'gramps_id': person.get_gramps_id(),\n"
        "                            'name': name})\n"
        "            if len(matches) >= %d:\n"
        "                break\n"
        "result = matches\n" % (text, int(limit))
    )
    return _call("eval", code=code, timeout=60)


@mcp.tool()
def gramps_active_person() -> dict:
    """Return the gramps_id and name of the currently active (selected) person,
    or a note if none is active."""
    code = (
        "handle = uistate.get_active('Person') if uistate else None\n"
        "if handle and db:\n"
        "    p = db.get_person_from_handle(handle)\n"
        "    result = {'gramps_id': p.get_gramps_id(),\n"
        "              'name': p.get_primary_name().get_name()}\n"
        "else:\n"
        "    result = 'no active person'\n"
    )
    return _call("eval", code=code, timeout=20)


@mcp.tool()
def gramps_set_active_person(gramps_id: str) -> dict:
    """Make the person with the given Gramps ID the active person, which drives
    navigation across all Gramps views. Returns the activated person's name."""
    code = (
        "p = db.get_person_from_gramps_id(%r) if db else None\n"
        "if p is None:\n"
        "    result = 'no such person: %s'\n"
        "else:\n"
        "    uistate.set_active(p.get_handle(), 'Person')\n"
        "    result = p.get_primary_name().get_name()\n" % (gramps_id, gramps_id)
    )
    return _call("eval", code=code, timeout=20)


if __name__ == "__main__":
    mcp.run()
