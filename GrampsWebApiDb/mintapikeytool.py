#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Douglas S. Blank <doug.blank@gmail.com>
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""Tools/Utilities/Generate Gramps Web API key

Dialog front end for WebApiHandler.mint_api_key() (webapi_client.py):
username/password in, a GRAMPS_WEB_API_KEY value out. Exists because
generating a key otherwise requires either a shell with the standalone
gramps-api-client package installed, or hand-writing the three lines of
Python from GrampsWebApiDb's own README -- this tool is that same call
behind a form, for anyone who just wants the key string.

A TOOL rather than a gramplet: generating a key is a one-off setup action,
not something worth keeping permanently docked in a gramplet bar. It
doesn't read or write anything in dbstate's Family Tree -- see
build_dialog() below -- but Gramps only populates the Tools menu once
some Family Tree is open, so in practice the user still needs one open
(any backend, even an empty local tree) to reach this tool at all.

On success, it also sets GRAMPS_WEB_API_KEY in this running Gramps
process's environment, so a WebApiDB-backed Family Tree can be opened in
the same session without restarting Gramps -- but that lasts only for
this process; it is not written to a shell profile, settings.ini, or any
open Family Tree, matching the README's "Credentials" section on why
persistence otherwise stays a manual step.

"Create Synced Family Tree for this key" goes one step further: it
creates (but does not open) a new, empty Family Tree using the
"grampswebapidb" DATABASE plugin, named "<username>@<host>" for whoever
the key authenticates as -- the exact name grampswebapidb.py's
_check_identity_async() requires, via the same CLIDbManager.create_new_db_cli()
Gramps' own Family Tree Manager uses for its "New" button, just with an
explicit dbid instead of the configured default backend. See README.md's
"Family Tree naming" section for why that name is required.
"""

# ------------------------------------------------------------------------
#
# Standard Python modules
#
# ------------------------------------------------------------------------
import os
import re
import threading
from urllib.error import HTTPError, URLError

# ------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# ------------------------------------------------------------------------
from gi.repository import GLib, Gtk

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gramps.cli.clidbman import CLIDbManager
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug import tool
from gramps.gui.utils import text_to_clipboard

from webapi_client import API_KEY_ENV_VAR, WebApiHandler

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#: Same failure modes WebApiHandler.from_env()/push_transaction() can
#: raise elsewhere in this addon -- see grampswebapidb.py's
#: _CONNECTION_ERRORS -- but here they mean "bad URL/credentials or an
#: unreachable server" rather than "lost sync", so they're just reported
#: in the status label rather than acted on.
_MINT_ERRORS = (ValueError, HTTPError, URLError, OSError)

#: Same substitution grampswebapidb.py's _check_identity_async() applies to a
#: Family Tree's own name before comparing it against the server identity
#: -- keep in sync if that changes. Applied here too so a tree created by
#: this button already has the name _check_identity_async() will accept.
_FAMILY_TREE_NAME_UNSAFE_CHARS = re.compile(r"[':<>|,;=\"\[\]\.\+\*\/\?\\]")

#: The DATABASE plugin id grampswebapidb.gpr.py registers WebApiDB under.
_WEBAPIDB_ID = "grampswebapidb"


class MintApiKeyTool(tool.Tool, ManagedWindow):
    """
    Dialog that turns a server URL + username + password into a
    GRAMPS_WEB_API_KEY value, via WebApiHandler.mint_api_key().
    """

    def __init__(self, dbstate, user, options_class, name, callback=None):
        self.dbstate = dbstate
        self.uistate = user.uistate
        self.mint_thread = None
        self.tree_thread = None
        ManagedWindow.__init__(self, self.uistate, [], self.__class__)
        self.set_window(Gtk.Window(), Gtk.Label(), "")
        tool.Tool.__init__(self, dbstate, options_class, name)

        dialog = self.build_dialog()
        dialog.run()
        dialog.destroy()
        self.close()

    def build_dialog(self):
        dialog = Gtk.Dialog(
            _("Generate Gramps Web API key"),
            self.uistate.window if self.uistate else None,
            Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
            (Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE),
        )
        dialog.set_default_size(420, -1)

        vbox = dialog.get_content_area()
        vbox.set_border_width(6)
        vbox.set_spacing(6)

        self.url_entry = self.__add_entry(
            vbox, _("Server URL"), _("e.g. https://your-server/api")
        )
        self.username_entry = self.__add_entry(vbox, _("Username"))
        self.password_entry = self.__add_entry(vbox, _("Password"))
        self.password_entry.set_visibility(False)
        self.password_entry.connect("activate", self.mint_clicked)

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.START)
        button_box.set_spacing(6)
        button_box.set_border_width(6)

        self.mint_button = Gtk.Button(label=_("Generate API Key"))
        self.mint_button.connect("clicked", self.mint_clicked)
        button_box.add(self.mint_button)
        vbox.pack_start(button_box, False, False, 0)

        self.status_label = Gtk.Label(halign=Gtk.Align.START)
        self.status_label.set_line_wrap(True)
        self.status_label.set_text(
            _(
                "Enter your server URL, username, and password, then "
                "click Generate API Key."
            )
        )
        vbox.pack_start(self.status_label, False, False, 0)

        self.key_entry = self.__add_entry(vbox, _("GRAMPS_WEB_API_KEY"))
        self.key_entry.set_editable(False)

        copy_box = Gtk.ButtonBox()
        copy_box.set_layout(Gtk.ButtonBoxStyle.START)
        copy_box.set_spacing(6)
        copy_box.set_border_width(6)

        copy_button = Gtk.Button(label=_("Copy"))
        copy_button.connect("clicked", self.copy_clicked)
        copy_box.add(copy_button)
        vbox.pack_start(copy_box, False, False, 0)

        self.create_tree_button = Gtk.Button(
            label=_("Create Synced Family Tree for this key")
        )
        self.create_tree_button.set_sensitive(False)
        self.create_tree_button.connect("clicked", self.create_tree_clicked)
        vbox.pack_start(self.create_tree_button, False, False, 0)

        self.tree_name_entry = self.__add_entry(vbox, _("Family Tree"))
        self.tree_name_entry.set_editable(False)

        existing_key = os.environ.get(API_KEY_ENV_VAR)
        if existing_key:
            self.key_entry.set_text(existing_key)
            self.create_tree_button.set_sensitive(True)
            self.status_label.set_text(
                _(
                    "Found an existing %s for this session. Click Create "
                    "Synced Family Tree to use it directly, or fill in the "
                    "form above to generate a different key."
                )
                % API_KEY_ENV_VAR
            )

        dialog.show_all()
        return dialog

    def __add_entry(self, vbox, name, tooltip=""):
        label = Gtk.Label(halign=Gtk.Align.START)
        label.set_markup("<b>%s</b>" % name)
        vbox.pack_start(label, False, False, 0)
        entry = Gtk.Entry()
        entry.set_tooltip_text(tooltip)
        vbox.pack_start(entry, False, False, 0)
        return entry

    def mint_clicked(self, obj):
        url = self.url_entry.get_text().strip()
        username = self.username_entry.get_text().strip()
        password = self.password_entry.get_text()
        if not url or not username or not password:
            self.status_label.set_text(
                _("Please fill in the server URL, username, and password.")
            )
            return

        self.key_entry.set_text("")
        self.tree_name_entry.set_text("")
        self.password_entry.set_text("")
        self.status_label.set_text(_("Generating API key…"))
        self.mint_button.set_sensitive(False)
        self.create_tree_button.set_sensitive(False)

        if self.mint_thread and self.mint_thread.is_alive():
            return
        self.mint_thread = threading.Thread(
            target=self._mint_api_key, args=(url, username, password)
        )
        self.mint_thread.daemon = True
        self.mint_thread.start()

    def _mint_api_key(self, url, username, password):
        """Run off the GTK main thread; hands the result back via idle_add."""
        try:
            key = WebApiHandler.mint_api_key(url, username, password)
        except _MINT_ERRORS as exc:
            GLib.idle_add(self._mint_failed, self._describe_mint_error(exc))
        else:
            GLib.idle_add(self._mint_succeeded, key)

    @staticmethod
    def _describe_mint_error(exc):
        """
        Turn a mint_api_key() exception into a message that says which of
        URL/username/password is the likely problem, instead of a raw
        urllib exception the user has to decode themselves.
        """
        if isinstance(exc, HTTPError):
            if exc.code in (401, 403):
                return (
                    _("Login failed (HTTP %d): check your username and password.")
                    % exc.code
                )
            return _("Server returned an error (HTTP %d %s): check the Server URL.") % (
                exc.code,
                exc.reason,
            )
        if isinstance(exc, OSError):
            # Covers URLError (DNS failure, connection refused, ...) and
            # socket.timeout, both OSError subclasses -- the server at
            # that URL could not be reached at all.
            reason = getattr(exc, "reason", exc)
            return _("Could not reach the server: check the Server URL. (%s)") % reason
        return _("Unexpected response from the server: %s") % exc

    def _mint_failed(self, message):
        self.status_label.set_text(_("Error: %s") % message)
        self.mint_button.set_sensitive(True)
        return False

    def _mint_succeeded(self, key):
        os.environ[API_KEY_ENV_VAR] = key
        self.key_entry.set_text(key)
        self.status_label.set_text(
            _(
                "Success. %s is now set for this Gramps session -- no "
                "restart needed. Copy the key below to also set it in your "
                "shell environment for next time."
            )
            % API_KEY_ENV_VAR
        )
        self.mint_button.set_sensitive(True)
        self.create_tree_button.set_sensitive(True)
        self.key_entry.grab_focus()
        self.key_entry.select_region(0, -1)
        return False

    def copy_clicked(self, obj):
        text_to_clipboard(self.key_entry.get_text())

    def create_tree_clicked(self, obj):
        key = self.key_entry.get_text().strip()
        if not key:
            return

        self.tree_name_entry.set_text("")
        self.status_label.set_text(_("Looking up account identity…"))
        self.create_tree_button.set_sensitive(False)

        if self.tree_thread and self.tree_thread.is_alive():
            return
        self.tree_thread = threading.Thread(target=self._lookup_identity, args=(key,))
        self.tree_thread.daemon = True
        self.tree_thread.start()

    def _lookup_identity(self, key):
        """Run off the GTK main thread; hands the result back via idle_add."""
        try:
            identity = WebApiHandler.from_api_key(key).get_identity()
        except _MINT_ERRORS as exc:
            GLib.idle_add(self._create_tree_failed, self._describe_mint_error(exc))
        else:
            GLib.idle_add(self._create_tree, identity)

    def _create_tree(self, identity):
        """
        Create the local Family Tree entry (mkdir + name.txt +
        database.txt) for `identity`, via the same CLIDbManager Gramps'
        own Family Tree Manager uses -- see clidbman.py's
        create_new_db_cli(). Runs on the GTK main thread (via idle_add):
        it's local filesystem work, not network, and touches self.dbstate.
        """
        tree_name = _FAMILY_TREE_NAME_UNSAFE_CHARS.sub("_", identity)
        dbman = CLIDbManager(self.dbstate)
        if tree_name in [existing[0] for existing in dbman.current_names]:
            self.tree_name_entry.set_text(tree_name)
            self.status_label.set_text(
                _(
                    'A Family Tree named "%s" already exists. Open it from '
                    "Family Trees -> Manage Family Trees instead of "
                    "creating another one."
                )
                % tree_name
            )
            self.create_tree_button.set_sensitive(True)
            return False
        try:
            new_path, title = dbman.create_new_db_cli(
                title=tree_name, dbid=_WEBAPIDB_ID
            )
        except Exception as exc:
            self.status_label.set_text(_("Error creating Family Tree: %s") % exc)
            self.create_tree_button.set_sensitive(True)
            return False
        self.tree_name_entry.set_text(title)
        self.status_label.set_text(
            _(
                'Created Family Tree "%s". Open it from Family Trees -> '
                "Manage Family Trees to start syncing."
            )
            % title
        )
        self.create_tree_button.set_sensitive(True)
        self.tree_name_entry.grab_focus()
        self.tree_name_entry.select_region(0, -1)
        return False

    def _create_tree_failed(self, message):
        self.status_label.set_text(_("Error: %s") % message)
        self.create_tree_button.set_sensitive(True)
        return False


class MintApiKeyToolOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
