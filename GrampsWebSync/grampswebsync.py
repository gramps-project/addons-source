# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2024       David Straub
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


"""Gramps addon to synchronize with a Gramps Web server."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from const import (
    C_ADD_LOC,
    C_ADD_REM,
    C_DEL_LOC,
    C_DEL_REM,
    C_UPD_BOTH,
    C_UPD_LOC,
    C_UPD_REM,
    MODE_BIDIRECTIONAL,
    MODE_MERGE,
    MODE_RESET_TO_LOCAL,
    MODE_RESET_TO_REMOTE,
    Actions,
)
from diffhandler import (
    WebApiSyncDiffHandler,
    changes_to_actions,
    has_local_actions,
    has_remote_actions,
)
from gi.repository import GLib, Gtk
from gramps.gen.config import config as configman
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import import_as_dict
from gramps.gen.errors import HandleError
from gramps.gen.lib import Tag
from gramps.gen.utils.file import media_path_full
from gramps.gui.dialog import QuestionDialog2
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug.tool import BatchTool, ToolOptions
from webapihandler import WebApiHandler, transaction_to_json

assert glocale is not None  # for type checker
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = _trans.ngettext


LOG = logging.getLogger("grampswebsync")


def get_password(service: str, username: str) -> str | None:
    """If keyring is installed, return the user's password or None."""
    LOG.debug("Retrieving password for user %s", username)
    try:
        import keyring
    except ImportError:
        LOG.warning("Keyring is not installed, cannot retrieve password.")
        return None
    return keyring.get_password(service, username)


def set_password(service: str, username: str, password: str) -> None:
    """If keyring is installed, store the user's password."""
    try:
        import keyring
    except ImportError:
        return None
    LOG.debug("Storing password for user %s", username)
    keyring.set_password(service, username, password)


class GrampsWebSyncTool(BatchTool, ManagedWindow):
    """Main class for the Gramps Web Sync tool."""

    def __init__(self, dbstate, user, options_class, name, *args, **kwargs) -> None:
        """Initialize GUI."""
        LOG.debug("Initializing Gramps Web Sync addon.")
        BatchTool.__init__(self, dbstate, user, options_class, name)
        ManagedWindow.__init__(self, user.uistate, [], self.__class__)

        self.dbstate = dbstate
        self.callback = self.uistate.pulse_progressbar

        self.config = configman.register_manager("webapisync")
        self.config.register("credentials.url", "")
        self.config.register("credentials.username", "")
        self.config.register("credentials.timestamp", 0)
        self.config.load()

        self.assistant = Gtk.Assistant()
        self.set_window(self.assistant, None, _("Gramps Web Sync"))
        self.setup_configs("interface.webapisync", 780, 600)

        self.assistant.connect("close", self.do_close)
        self.assistant.connect("cancel", self.do_close)
        self.assistant.connect("apply", self.apply)
        self.assistant.connect("prepare", self.prepare)

        self.intro = IntroductionPage(self.assistant)
        self.add_page(self.intro, Gtk.AssistantPageType.INTRO, _("Introduction"))

        self.url = self.config.get("credentials.url")
        self.username = self.config.get("credentials.username")
        self.password = self.get_password()
        self.loginpage = LoginPage(
            self.assistant,
            url=self.url,
            username=self.username,
            password=self.password,
        )
        self.add_page(self.loginpage, Gtk.AssistantPageType.CONTENT, _("Login"))

        self.diff_progress_page = DiffProgressPage(self.assistant)
        self.add_page(
            self.diff_progress_page,
            Gtk.AssistantPageType.PROGRESS,
            _("Progress Information"),
        )

        self.confirmation = ConfirmationPage(self.assistant)
        self.add_page(
            self.confirmation, Gtk.AssistantPageType.CONFIRM, _("Final confirmation")
        )

        self.sync_progress_page = SyncProgressPage(self.assistant)
        self.add_page(
            self.sync_progress_page,
            Gtk.AssistantPageType.PROGRESS,
            _("Summary"),
        )

        self.file_confirmation = FileConfirmationPage(self.assistant)
        self.add_page(
            self.file_confirmation,
            Gtk.AssistantPageType.CONFIRM,
            _("Media Files"),
        )

        self.file_progress_page = FileProgressPage(self.assistant)
        self.add_page(
            self.file_progress_page,
            Gtk.AssistantPageType.PROGRESS,
            _("Progress Information"),
        )

        self.conclusion = ConclusionPage(self.assistant)
        self.add_page(self.conclusion, Gtk.AssistantPageType.SUMMARY, _("Summary"))

        self.show()
        self.assistant.set_forward_page_func(self.forward_page, None)

        self._api: WebApiHandler | None = None

        self.db1 = dbstate.db
        self.db2 = None
        self._download_timestamp = 0
        self._changes: Actions | None = None
        self._sync: WebApiSyncDiffHandler | None = None
        self.files_missing_local: list[tuple[str, str]] = []
        self.files_missing_remote: list[tuple[str, str]] = []
        self.uploaded: dict[str, bool] = {}
        self.downloaded: dict[str, bool] = {}

    @property
    def api(self) -> WebApiHandler:
        if self._api is None:
            raise ValueError("No WebApiHandler found")  # shouldn't happen!
        return self._api

    @property
    def sync(self) -> WebApiSyncDiffHandler:
        if self._sync is None:
            raise ValueError("No WebApiSyncDiffHandler found")  # shouldn't happen!
        return self._sync

    @property
    def changes(self) -> Actions:
        if self._changes is None:
            raise ValueError("No change actions found")  # shouldn't happen!
        return self._changes

    def build_menu_names(self, obj):  # type: ignore
        """Override :class:`.ManagedWindow` method."""
        return (_("Gramps Web Sync"), None)

    def do_close(self, assistant):
        """Close the assistant."""
        LOG.debug("Closing Gramps Web Sync addon.")
        position = self.window.get_position()  # crock
        self.assistant.hide()
        self.window.move(position[0], position[1])
        self.close()

    def forward_page(self, page, data):
        """Specify the next page to be displayed."""
        LOG.debug(f"Moving to next page from page {page}.")
        if self.conclusion.error:
            LOG.debug("Skipping to last page due to error.")
            return 7
        if page == 2 and self._changes is not None and len(self.changes) == 0:
            LOG.debug("Skipping to media sync as databases are in sync.")
            return 4
        if page == 5 and self.conclusion.unchanged:
            LOG.debug("Skipping to last page as media files are in sync.")
            return 7
        return page + 1

    def add_page(self, page, page_type, title=""):
        """Add a page to the assistant."""
        page.show_all()
        self.assistant.append_page(page)
        self.assistant.set_page_title(page, title)
        self.assistant.set_page_type(page, page_type)


    def handle_done_syncing_dbs(self):
        """Handle the completion of syncing the databases."""
        self.save_timestamp()
        self.sync_progress_page.handle_done_syncing_dbs()
        self.files_missing_local = self.get_missing_files_local()
        self.assistant.next_page()


    def prepare(self, assistant, page):
        """Run page preparation code."""
        page.update_complete()
        if page == self.diff_progress_page:
            # Clear any previous login error when starting fresh
            self.loginpage.clear_error()

            # Try to connect and authenticate
            self.save_credentials()
            url, username, password = self.get_credentials()
            if not self.test_connection(url, username, password):
                # Connection failed, go back to login page
                self.assistant.set_current_page(1)  # Login page index
                return None

            if "ViewPrivate" not in self.api.get_permissions():
                self.loginpage.show_error(
                    _("Your user does not have sufficient server permissions to use sync.")
                )
                self.assistant.set_current_page(1)  # Go back to login page
                return None

            self.diff_progress_page.label.set_text(_("Fetching remote data..."))
            t = threading.Thread(target=self.async_compare_dbs)
            t.start()
        elif page == self.confirmation:
            self.confirmation.prepare(self.changes)
        elif page == self.sync_progress_page:
            self.assistant.commit()  # just erases the visited page history
            actions = changes_to_actions(self.changes, self.confirmation.sync_mode)
            self.sync_progress_page.prepare(actions)
            if len(actions) == 0:
                self.handle_done_syncing_dbs()
            else:
                try:
                    self.commit_all_actions(actions)
                except Exception as e:
                    self.handle_error(
                        _("Unexpected error while applying changes.") + f" {e}"
                    )
                
            # now, get missing media files
        elif page == self.file_confirmation:
            if self.files_missing_local:
                LOG.debug(
                    "The following media files are missing on the local side: %s",
                    ", ".join([gramps_id for gramps_id, _ in self.files_missing_local]),
                )
            else:
                LOG.debug("No files missing locally.")
            self.files_missing_remote = self.get_missing_files_remote()
            if self.files_missing_remote:
                LOG.debug(
                    "The following media files are missing on the remote side: %s",
                    ", ".join(
                        [gramps_id for gramps_id, _ in self.files_missing_remote]
                    ),
                )
            else:
                LOG.debug("No files missing remotely.")
            if not self.files_missing_local and not self.files_missing_remote:
                self.handle_files_unchanged()
            else:
                self.file_confirmation.prepare(
                    self.files_missing_local, self.files_missing_remote
                )
        elif page == self.file_progress_page:
            self.file_progress_page.prepare(
                self.files_missing_local, self.files_missing_remote
            )
            t = threading.Thread(target=self.async_transfer_media)
            t.start()
        elif page == self.conclusion:
            if self.conclusion.error:
                pass
            elif self.conclusion.unchanged:
                text = _("Media files are in sync.")
                self.conclusion.label.set_text(text)
                LOG.info("Media files are in sync.")
            else:
                text = ""
                if self.downloaded:
                    ok = sum([b for gid, b in self.downloaded.items()])
                    nok = sum([not b for gid, b in self.downloaded.items()])
                    if ok:
                        text += _("Successfully downloaded %s media files.") % ok
                        text += " "
                    if nok:
                        text += _("Encountered %s errors during download.") % nok
                        text += " "
                if self.uploaded:
                    ok = sum([b for gid, b in self.uploaded.items()])
                    nok = sum([not b for gid, b in self.uploaded.items()])
                    if ok:
                        text += _("Successfully uploaded %s media files.") % ok
                        text += " "
                    if nok:
                        text += _("Encountered %s errors during upload.") % nok
                self.conclusion.label.set_text(text)

            self.conclusion.set_complete()

    def test_connection(self, url: str, username: str, password: str) -> bool:
        """Test the connection and authentication. Return True if successful."""
        try:
            # Try to create API handler
            self._api = WebApiHandler(url, username, password, None)

            # Test the connection by making a simple API call
            self.api.get_permissions()
            return True

        except HTTPError as exc:
            if exc.code == 401:
                self.loginpage.show_error(_("Authentication failed. Please check your username and password."))
            elif exc.code == 403:
                self.loginpage.show_error(_("Access forbidden. Please check username and password."))
            elif exc.code == 404:
                self.loginpage.show_error(_("GrampsWeb service not found. Please check the URL."))
            else:
                self.loginpage.show_error(_("Server error %s. Please check your connection.") % exc.code)
            return False
        except URLError:
            self.loginpage.show_error(_("Connection failed. Please check the URL and your internet connection."))
            return False
        except ValueError as e:
            self.loginpage.show_error(_("Invalid server response. Please check the URL."))
            return False
        except Exception as e:
            self.loginpage.show_error(_("Unexpected error: %s") % str(e))
            return False

    def handle_files_unchanged(self):
        self.conclusion.unchanged = True
        self.assistant.next_page()

    def apply(self, assistant):
        """Apply the changes."""
        page_number = assistant.get_current_page()
        page = assistant.get_nth_page(page_number)
        if page == self.confirmation:
            pass
        elif page == self.file_confirmation:
            pass

    def download_files(self):
        """Download media files missing locally."""
        if not self.files_missing_local:
            return
        res = {}
        for gramps_id, handle in self.files_missing_local:
            LOG.debug("Downloading file %s", gramps_id)
            self.downloaded[gramps_id] = self._download_file(handle)
            self._update_file_progress()
        return res

    def _update_file_progress(self):
        """Update the file progress bars."""
        self.file_progress_page.update_progress(
            self.files_missing_local,
            self.files_missing_remote,
            self.downloaded,
            self.uploaded,
        )
        # force updating progress bar
        while Gtk.events_pending():
            Gtk.main_iteration()

    def _download_file(self, handle):
        """Download a single media file."""
        try:
            obj = self.db1.get_media_from_handle(handle)
        except HandleError:
            self.handle_error(_("Error accessing media object."))
            return
        path = media_path_full(self.db1, obj.get_path())
        return self.api.download_media_file(handle=handle, path=path)

    def upload_files(self):
        """Upload media files missing remotely."""
        if not self.files_missing_remote:
            return
        res = {}
        for gramps_id, handle in self.files_missing_remote:
            LOG.debug("Uploading file %s", gramps_id)
            self.uploaded[gramps_id] = self._upload_file(handle)
            self._update_file_progress()
        return res

    def _upload_file(self, handle):
        """Upload a single media file."""
        try:
            obj = self.db1.get_media_from_handle(handle)
        except HandleError:
            self.handle_error(_("Error accessing media object."))
            return
        path = media_path_full(self.db1, obj.get_path())
        return self.api.upload_media_file(handle=handle, path=path)

    def get_password(self):
        """Get a stored password."""
        url = self.config.get("credentials.url")
        username = self.config.get("credentials.username")
        if not url or not username:
            return None
        return get_password(url, username)

    def handle_error(self, message):
        """Handle an error message during sync."""
        LOG.error(message)
        self.conclusion.error = True
        self.assistant.next_page()
        self.conclusion.label.set_text(message)  #
        self.conclusion.set_complete()

    def handle_unchanged(self):
        """Return a message if nothing has changed."""
        self.save_timestamp()
        self.assistant.next_page()

    def async_compare_dbs(self):
        """Download the remote data and import it to an in-memory database."""
        # store timestamp just before downloading the XML
        self._download_timestamp = datetime.now().timestamp()
        GLib.idle_add(self.get_diff_actions)

    def get_diff_actions(self) -> None:
        """Download the remote data, import it and compare it to local."""
        LOG.info("Downloading Gramps XML file.")
        path = self.handle_server_errors(self.api.download_xml)
        if path is None:
            return
        LOG.debug("Importing Gramps XML file.")
        db2 = import_as_dict(str(path), self._user)
        if db2 is None:
            self.handle_error(_("Failed importing downloaded XML file."))
            return
        else:
            LOG.debug("Successfully imported Gramps XML file.")
        path.unlink()  # delete temporary file
        self.db2 = db2
        self.diff_progress_page.label.set_text(_("Comparing local and remote data..."))
        LOG.info("Comparing local and remote data...")
        timestamp = self.config.get("credentials.timestamp") or None
        self._sync = WebApiSyncDiffHandler(
            self.db1, self.db2, user=self._user, last_synced=timestamp
        )
        self._changes = self.sync.get_changes()
        self.diff_progress_page.label.set_text("")
        self.diff_progress_page.set_complete()
        if len(self.changes) == 0:
            LOG.info("Databases are in sync.")
            self.handle_unchanged()
        else:
            self.assistant.next_page()

    def async_transfer_media(self):
        """Upload/download media files."""
        GLib.idle_add(self._async_transfer_media)

    def _async_transfer_media(self):
        """Upload/download media files."""
        self.handle_server_errors(self.download_files)
        self.handle_server_errors(self.upload_files)
        self.file_progress_page.set_complete()
        self.assistant.next_page()

    def handle_server_errors(self, callback: Callable, *args) -> None:
        """Handle server errors while executing a function."""
        try:
            return callback(*args)
        except HTTPError as exc:
            if exc.code == 401:
                self.handle_error(_("Server authorization error."))
            elif exc.code == 403:
                self.handle_error(
                    _("Server authorization error: insufficient permissions.")
                )
            elif exc.code == 404:
                self.handle_error(_("Error: URL not found."))
            elif exc.code == 409:
                self.handle_error(
                    _(
                        "Unable to synchronize changes to server: objects have been modified."
                    )
                )
            else:
                self.handle_error(_("Error %s while connecting to server.") % exc.code)
            return None
        except URLError:
            self.handle_error(_("URL error while connecting to server."))
            return None
        except ValueError:
            self.handle_error(_("Error while parsing response from server."))
            return None

    def save_credentials(self) -> None:
        """Save the login credentials."""
        url = self.loginpage.url.get_text()
        url = self.sanitize_url(url)
        if url is None:
            self.handle_error("No URL provided")
            return
        username = self.loginpage.username.get_text()
        password = self.loginpage.password.get_text()
        if url != self.config.get("credentials.url"):
            # if URL changed, clear last sync timestamp
            self.config.set("credentials.timestamp", 0)
        self.config.set("credentials.url", url)
        self.config.set("credentials.username", username)
        set_password(url, username, password)
        self.config.save()

    def sanitize_url(self, url: str) -> str | None:
        """Warn if http and prepend https if missing."""
        parsed_url = urlparse(url)
        if parsed_url.scheme == "":
            # if no httpX given, prepend https!
            url = f"https://{url}"
        elif parsed_url.scheme == "http":
            question = QuestionDialog2(
                _("Continue without transport encryption?"),
                _(
                    "You have specified a URL with http scheme. "
                    "If you continue, your password will be sent "
                    "in clear text over the network. "
                    "Use only for local testing!"
                ),
                _("Continue with HTTP"),
                _("Use HTTPS"),
                parent=self.window,
            )
            if not question.run():
                return url.replace("http", "https")
        return url

    def get_credentials(self):
        """Get a tuple of URL, username, and password."""
        return (
            self.config.get("credentials.url"),
            self.config.get("credentials.username"),
            self.loginpage.password.get_text(),
        )

    def commit_all_actions(self, actions: Actions) -> None:
        """Commit all changes to the databases."""
        LOG.info("Committing all changes to the databases.")
        msg = "Apply Gramps Web Sync changes"
        with DbTxn(msg, self.sync.db1) as trans1:
            with DbTxn(msg, self.sync.db2) as trans2:
                if has_local_actions(actions):
                    LOG.debug("Committing changes to local database.")
                else:
                    LOG.debug("No changes to apply to local database.")
                self.sync.commit_actions(actions, trans1, trans2)
                self.sync_progress_page.handle_local_sync_complete(actions)
                # force the sync if mode is reset
                force = self.confirmation.sync_mode in {
                    MODE_RESET_TO_LOCAL,
                    MODE_RESET_TO_REMOTE,
                }
                lang = self.api.get_lang()
                payload = transaction_to_json(trans2, lang)
        GLib.idle_add(
            self.async_commit_actions_to_remote, payload, force
        )

    def async_commit_actions_to_remote(self, payload: dict[str, "Any"], force: bool) -> None:
        """Commit all changes to the remote database."""
        GLib.idle_add(self._async_commit_actions_to_remote, payload, force)

    def _async_commit_actions_to_remote(self, payload: dict[str, "Any"], force: bool) -> None:
        """Upload/download media files."""
        LOG.debug("Committing changes to remote database.")
        self.handle_server_errors(
            self.api.commit,
            payload,
            force,
            self.sync_progress_page.update_api_progress,
        )
        self.handle_done_syncing_dbs()

    def save_timestamp(self):
        """Save last sync timestamp."""
        # self.config.set("credentials.timestamp", self._download_timestamp)
        timestamp = datetime.now().timestamp()
        LOG.debug(
            "Saving current time stamp (%s) as last successful sync time.", timestamp
        )
        self.config.set("credentials.timestamp", timestamp)
        self.config.save()

    def get_missing_files_local(self) -> list[tuple[str, str]]:
        """Get a list of media files missing locally."""
        return [
            (media.gramps_id, media.handle)
            for media in self.db1.iter_media()
            if not os.path.exists(media_path_full(self.db1, media.get_path()))
        ]

    def get_missing_files_remote(self):
        """Get a list of media files missing remotely."""
        missing_files = self.handle_server_errors(self.api.get_missing_files) or []
        return [(media["gramps_id"], media["handle"]) for media in missing_files]


class Page(Gtk.Box):
    """Page base class."""

    def __init__(self, assistant: Gtk.Assistant):
        """Initialize self."""
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.assistant = assistant
        self._complete = False

    def set_complete(self):
        """Set as complete."""
        self._complete = True
        self.update_complete()

    @property
    def complete(self):
        return self._complete

    def update_complete(self):
        """Set the current page's complete status."""
        page_number = self.assistant.get_current_page()
        current_page = self.assistant.get_nth_page(page_number)
        self.assistant.set_page_complete(current_page, self.complete)


class IntroductionPage(Page):
    """A page containing introductory text."""

    def __init__(self, assistant):
        super().__init__(assistant)
        label = Gtk.Label(label=self.__get_intro_text())
        label.set_line_wrap(True)
        label.set_use_markup(True)
        label.set_max_width_chars(60)

        self.pack_start(label, False, False, 0)
        self._complete = True

    def __get_intro_text(self):
        """Return the introductory text."""
        return _(
            "This tool allows to synchronize the currently opened "
            "family tree with a remote family tree served by Gramps Web.\n\n"
            "The tool assumes that the two trees are derivatives of each other, "
            "i.e. one of the two was created from a Gramps XML (not GEDCOM!) "
            "export of the other.\n\n"
            "After successful synchronization, the two trees will be identical. "
            "Modifications will be propagated based on timestamps. "
            "You will be prompted for confirmation before any changes are made "
            "to the local or remote trees.\n\n"
            "If you instead want to merge two significantly different trees "
            "with the option to make manual modifications, use the Import Merge "
            "Tool instead."
        )


class LoginPage(Page):
    """A page to provide server credentials."""

    def __init__(self, assistant, url, username, password):
        super().__init__(assistant)
        self.set_spacing(12)

        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        self.add(grid)

        label = Gtk.Label(label=_("Server URL: "))
        grid.attach(label, 0, 0, 1, 1)
        self.url = Gtk.Entry()
        if url:
            self.url.set_text(url)
        self.url.set_hexpand(True)
        self.url.set_input_purpose(Gtk.InputPurpose.URL)
        grid.attach(self.url, 1, 0, 1, 1)

        label = Gtk.Label(label=_("Username: "))
        grid.attach(label, 0, 1, 1, 1)
        self.username = Gtk.Entry()
        if username:
            self.username.set_text(username)
        self.username.set_hexpand(True)
        grid.attach(self.username, 1, 1, 1, 1)

        label = Gtk.Label(label=_("Password: "))
        grid.attach(label, 0, 2, 1, 1)
        self.password = Gtk.Entry()
        if password:
            self.password.set_text(password)
        self.password.set_hexpand(True)
        self.password.set_visibility(False)
        self.password.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        grid.attach(self.password, 1, 2, 1, 1)

        # Error message label - initially hidden
        self.error_label = Gtk.Label()
        self.error_label.set_line_wrap(True)
        self.error_label.set_max_width_chars(60)
        self.error_label.set_markup('<span color="red"><b>Error:</b> </span>')
        self.error_label.set_no_show_all(True)  # Don't show when show_all() is called
        self.error_label.hide()
        grid.attach(self.error_label, 0, 3, 2, 1)

        # Connect entry change events
        self.url.connect("changed", self.on_entry_changed)
        self.username.connect("changed", self.on_entry_changed)
        self.password.connect("changed", self.on_entry_changed)

    def show_error(self, message: str):
        """Display an error message on the login page."""
        self.error_label.set_markup(f'<span color="red"><b>Error:</b> {message}</span>')
        self.error_label.show()
        self.update_complete()

    def clear_error(self):
        """Clear any displayed error message."""
        self.error_label.hide()
        self.update_complete()

    @property
    def complete(self):
        url = self.url.get_text()
        username = self.username.get_text()
        password = self.password.get_text()
        if url and username and password:
            return True
        return False

    def on_entry_changed(self, widget):
        """Handle changes to entry fields."""
        # Clear error when user starts typing
        if self.error_label.get_visible():
            self.clear_error()
        self.update_complete()


class DiffProgressPage(Page):
    """A progress page."""

    def __init__(self, assistant):
        super().__init__(assistant)
        label = Gtk.Label(label="")
        label.set_line_wrap(True)
        label.set_use_markup(True)
        label.set_max_width_chars(60)
        self.label = label
        self.pack_start(self.label, False, False, 0)


class ConfirmationPage(Page):
    """Page showing the differences before applying them."""

    def __init__(self, assistant):
        super().__init__(assistant)
        self.sync_mode = MODE_BIDIRECTIONAL
        self.store = Gtk.TreeStore(str, str)

        # tree view
        self.tree_view = Gtk.TreeView(model=self.store)

        for i, col in enumerate(["ID", "Content"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(col, renderer, text=i)
            self.tree_view.append_column(column)

        # scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.tree_view)

        self.sync_label = Gtk.Label()
        self.sync_label.set_text("Sync mode")

        # Box for radio buttons
        self.radio_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        # Radio buttons
        option_name = _("Bidirectional Synchronization")
        self.radio_button1 = Gtk.RadioButton.new_with_label_from_widget(
            None, option_name
        )
        self.radio_button1.connect(
            "toggled", self.on_radio_button_toggled, MODE_BIDIRECTIONAL
        )
        self.radio_box.pack_start(self.radio_button1, False, False, 0)

        option_name = _("Reset remote to local")
        self.radio_button2 = Gtk.RadioButton.new_from_widget(self.radio_button1)
        self.radio_button2.set_label(option_name)
        self.radio_button2.connect(
            "toggled", self.on_radio_button_toggled, MODE_RESET_TO_LOCAL
        )
        self.radio_box.pack_start(self.radio_button2, False, False, 0)

        option_name = _("Reset local to remote")
        self.radio_button3 = Gtk.RadioButton.new_from_widget(self.radio_button1)
        self.radio_button3.set_label(option_name)
        self.radio_button3.connect(
            "toggled", self.on_radio_button_toggled, MODE_RESET_TO_REMOTE
        )
        self.radio_box.pack_start(self.radio_button3, False, False, 0)

        option_name = _("Merge")
        self.radio_button4 = Gtk.RadioButton.new_from_widget(self.radio_button1)
        self.radio_button4.set_label(option_name)
        self.radio_button4.connect("toggled", self.on_radio_button_toggled, MODE_MERGE)
        self.radio_box.pack_start(self.radio_button4, False, False, 0)

        # Box to hold the label and radio buttons
        self.label_radio_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.label_radio_box.pack_start(self.sync_label, False, False, 0)
        self.label_radio_box.pack_start(self.radio_box, False, False, 0)

        self.outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.outer_box.pack_start(scrolled_window, True, True, 0)
        self.outer_box.pack_start(self.label_radio_box, False, False, 10)

        self.pack_start(self.outer_box, True, True, 0)

    def on_radio_button_toggled(self, button, name):
        """Callback for radio buttons setting sync mode."""
        if button.get_active():
            self.sync_mode = int(name)

    def prepare(self, changes: Actions):
        """Convert the changes list to a tree store."""
        change_labels = {
            _("Local changes"): {
                _("Added"): C_ADD_LOC,
                _("Deleted"): C_DEL_LOC,
                _("Modified"): C_UPD_LOC,
            },
            _("Remote changes"): {
                _("Added"): C_ADD_REM,
                _("Deleted"): C_DEL_REM,
                _("Modified"): C_UPD_REM,
            },
            _("Simultaneous changes"): {_("Modified"): C_UPD_BOTH},
        }

        for label1, v1 in change_labels.items():
            iter1 = self.store.append(None, [label1, ""])
            for label2, change_type in v1.items():
                rows = []
                for change in changes:
                    _type, handle, class_name, obj1, obj2 = change
                    if _type == change_type:
                        if obj1 is not None:
                            if class_name == "Tag":
                                assert isinstance(obj1, Tag)  # for type checker
                                gid = obj1.name
                            else:
                                gid = obj1.gramps_id
                        else:
                            assert obj2  # for type checker
                            if class_name == "Tag":
                                assert isinstance(obj2, Tag)  # for type checker
                                gid = obj2.name
                            else:
                                gid = obj2.gramps_id
                        obj_details = [class_name, gid]
                        rows.append(obj_details)
                if rows:
                    label2 = f"{label2} ({len(rows)})"
                    iter2 = self.store.append(iter1, [label2, ""])
                    for row in rows:
                        self.store.append(iter2, row)

        # expand first level
        for i, row in enumerate(self.store):
            self.tree_view.expand_row(Gtk.TreePath(i), False)

        self.set_complete()


class SyncProgressPage(Page):
    """Page showing database sync progress."""

    def __init__(self, assistant):
        super().__init__(assistant)
        label = Gtk.Label(label="")
        label.set_line_wrap(True)
        label.set_use_markup(True)
        label.set_max_width_chars(60)
        self.label = label
        self.pack_start(self.label, False, False, 0)

        self.label_progressbar_api = Gtk.Label(label="")
        self.label_progressbar_api.set_margin_top(50)
        self.pack_start(self.label_progressbar_api, False, False, 20)

        self.progressbar_api = Gtk.ProgressBar()
        self.pack_start(self.progressbar_api, False, False, 20)

        media_label = Gtk.Label(label=_("Fetching information about media files..."))
        media_label.set_line_wrap(True)
        media_label.set_use_markup(True)
        media_label.set_max_width_chars(60)
        self.media_label = media_label
        self.media_label.set_margin_top(50)
        self.pack_start(self.media_label, False, False, 0)

    def update_api_progress(self, progress: float) -> None:
        """Update the progress bar for the API transaction endpoint."""
        if progress >= 0:
            self.progressbar_api.set_fraction(progress)
        else:
            self.progressbar_api.pulse()
        # force updating progress bar
        while Gtk.events_pending():
            Gtk.main_iteration()


    def prepare(self, actions: Actions):
        if len(actions) == 0:
            self.label.set_text(_("Both trees are the same."))
            self.label_progressbar_api.hide()
            self.progressbar_api.hide()
        else:
            self.media_label.hide()
        if has_local_actions(actions):
            self.label.set_text(_("Applying changes to local database ..."))
        else:
            self.label.set_text(_("No changes to apply to local database."))
        if has_remote_actions(actions):
            self.label_progressbar_api.show()
            self.label_progressbar_api.set_text(_("Applying changes to remote database ..."))
            self.progressbar_api.show()
        else:
            self.label_progressbar_api.set_text(_("No changes to apply to remote database."))
            self.progressbar_api.hide()

    def handle_local_sync_complete(self, actions: Actions) -> None:
        """Handle completion of local sync."""
        if not has_local_actions(actions):
            return
        self.label.set_text(_("Successfully applied changes to local database."))

    def handle_done_syncing_dbs(self) -> None:
        """Handle completion of syncing the databases."""
        self.media_label.show()


class FileConfirmationPage(Page):
    """File sync confirmation page."""

    def __init__(self, assistant):
        super().__init__(assistant)
        self.store = Gtk.TreeStore(str)

        # tree view
        self.tree_view = Gtk.TreeView(model=self.store)

        for i, col in enumerate(["ID"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(col, renderer, text=i)
            self.tree_view.append_column(column)

        # scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.tree_view)

        self.pack_start(scrolled_window, True, True, 0)

    def prepare(self, missing_local, missing_remote):
        iter_local = self.store.append(None, [_("Missing locally")])
        for gramps_id, handle in missing_local:
            self.store.append(iter_local, [gramps_id])
        iter_remote = self.store.append(None, [_("Missing remotely")])
        for gramps_id, handle in missing_remote:
            self.store.append(iter_remote, [gramps_id])

        # expand first level
        for i, row in enumerate(self.store):
            self.tree_view.expand_row(Gtk.TreePath(i), False)

        self.set_complete()


class FileProgressPage(Page):
    """A file progress page."""

    def __init__(self, assistant):
        """Initialize page."""
        super().__init__(assistant)
        self.label1 = Gtk.Label(label="Media file download")
        self.pack_start(self.label1, False, False, 20)

        self.progressbar1 = Gtk.ProgressBar()
        self.pack_start(self.progressbar1, False, False, 20)

        self.label2 = Gtk.Label(label="Media file upload")
        self.pack_start(self.label2, False, False, 20)

        self.progressbar2 = Gtk.ProgressBar()
        self.pack_start(self.progressbar2, False, False, 20)

    def prepare(self, files_missing_local, files_missing_remote):
        """Prepare."""
        n_down = len(files_missing_local)
        if not n_down:
            self.label1.hide()
            self.progressbar1.hide()
        else:
            self.label1.show()
            self.progressbar1.show()
            self.label1.set_text(_("Downloading %s media file(s)") % n_down)
        n_up = len(files_missing_remote)
        if not n_up:
            self.label2.hide()
            self.progressbar2.hide()
        else:
            self.label2.show()
            self.progressbar2.show()
            self.label2.set_text(_("Uploading %s media file(s)") % n_up)

    def update_progress(
        self, files_missing_local, files_missing_remote, downloaded, uploaded
    ):
        """Update the progress bar."""
        n_down = len(files_missing_local)
        n_up = len(files_missing_remote)
        i_down = len(downloaded)
        i_up = len(uploaded)
        if n_down:
            self.progressbar1.set_fraction(i_down / n_down)
        if n_up:
            self.progressbar2.set_fraction(i_up / n_up)


class ConclusionPage(Page):
    """The conclusion page."""

    def __init__(self, assistant):
        super().__init__(assistant)
        self.error = False
        self.unchanged = False
        label = Gtk.Label(label="")
        label.set_line_wrap(True)
        label.set_use_markup(True)
        label.set_max_width_chars(60)
        self.label = label
        self.pack_start(self.label, False, False, 0)


class GrampsWebSyncOptions(ToolOptions):
    """Options for Gramps Web Sync."""
