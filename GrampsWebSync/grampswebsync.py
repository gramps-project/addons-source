# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2026       David Straub
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


"""Gramps addon to synchronize with a Gramps Web server.

Provides :class:`GrampsWebSyncTool`, a :class:`Gtk.Assistant` presenting a
:class:`session.SyncSession`. :data:`PAGE_FOR_STATE` maps each
:class:`session.State` to an assistant page and :func:`error_message`
localizes a :class:`session.ErrorKind`.

The synchronization itself lives in :mod:`session`.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse

from adapters import (
    ConfigCredentialStore,
    GLibTaskRunner,
    GrampsMediaStore,
    IoRunner,
    KeyringUnavailable,
    SystemClock,
)
from const import (
    C_ADD_LOC,
    C_ADD_REM,
    C_DEL_LOC,
    C_DEL_REM,
    C_UPD_BOTH,
    C_UPD_LOC,
    C_UPD_REM,
    DESTRUCTIVE_MODES,
    MODE_BIDIRECTIONAL,
    MODE_RESET_TO_LOCAL,
    MODE_RESET_TO_REMOTE,
    Actions,
)
from diffhandler import changes_to_actions, has_local_actions, has_remote_actions
from gi.repository import GLib, Gtk
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import Tag
from gramps.gui.dialog import QuestionDialog2
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug.tool import BatchTool, ToolOptions
from session import (
    STATUS_COMPARING,
    STATUS_FETCHING,
    STATUS_LOCAL_APPLIED,
    ErrorKind,
    State,
    SyncSession,
    next_state,
)
from webapihandler import WebApiHandler

assert glocale is not None  # for type checker
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = _trans.ngettext


LOG = logging.getLogger("grampswebsync")


#: Assistant page indices, in the order the pages are appended.
PAGE_INTRO = 0
PAGE_LOGIN = 1
PAGE_COMPARING = 2
PAGE_REVIEW_CHANGES = 3
PAGE_APPLYING = 4
PAGE_REVIEW_FILES = 5
PAGE_TRANSFERRING = 6
PAGE_CONCLUSION = 7

#: The one place that knows how flow states correspond to assistant pages.
#: Both terminal states share the conclusion page, which renders either the
#: summary or the error.
PAGE_FOR_STATE: dict[State, int] = {
    State.INTRO: PAGE_INTRO,
    State.LOGIN: PAGE_LOGIN,
    State.COMPARING: PAGE_COMPARING,
    State.REVIEW_CHANGES: PAGE_REVIEW_CHANGES,
    State.APPLYING: PAGE_APPLYING,
    State.REVIEW_FILES: PAGE_REVIEW_FILES,
    State.TRANSFERRING: PAGE_TRANSFERRING,
    State.DONE: PAGE_CONCLUSION,
    State.FAILED: PAGE_CONCLUSION,
}


def keyring_message(problem: KeyringUnavailable) -> str:
    """Return the localized notice for an unusable keyring.

    Under snap the failure is a confinement setting the user can change, so the
    message carries the command rather than only apologizing.

    :param problem: What the keyring reported.
    :returns: A message suitable for display.
    """
    if problem.snap_command:
        return _(
            "The password could not be saved to the system keyring. "
            "Snap confinement blocks access until you run: %s"
        ) % problem.snap_command
    return _(
        "The password could not be saved to the system keyring. "
        "You will need to enter it each time."
    )


def error_message(kind: ErrorKind, detail: str = "") -> str:
    """Return the localized message for an error kind.

    Translation lives here rather than in :mod:`session` so the flow logic can
    be asserted on stable enum values instead of translated prose.

    :param kind: The classification recorded by the session.
    :param detail: Optional extra context, e.g. an HTTP status.
    :returns: A message suitable for display.
    """
    messages = {
        ErrorKind.AUTH_FAILED: _(
            "Authentication failed. Please check your username and password."
        ),
        ErrorKind.FORBIDDEN: _(
            "Access forbidden. Please check username and password."
        ),
        ErrorKind.NOT_FOUND: _("GrampsWeb service not found. Please check the URL."),
        ErrorKind.RATE_LIMITED: _(
            "Too many requests, please try again in a few seconds."
        ),
        ErrorKind.TREE_DISABLED: _("GrampsWeb tree is disabled."),
        ErrorKind.CONNECTION_FAILED: _(
            "Connection failed. Please check the URL and your internet connection."
        ),
        ErrorKind.INVALID_RESPONSE: _(
            "Invalid server response. Please check the URL."
        ),
        ErrorKind.INSUFFICIENT_PERMISSIONS: _(
            "Your user does not have sufficient server permissions to use sync."
        ),
        ErrorKind.XML_IMPORT_FAILED: _("Failed importing downloaded XML file."),
        ErrorKind.CONFLICT: _(
            "Unable to synchronize changes to server: objects have been modified."
        ),
        ErrorKind.APPLY_FAILED: _("Unexpected error while applying changes."),
        ErrorKind.STALE_LOCAL_DATA: _(
            "The family tree was modified while the changes were being "
            "reviewed. Nothing has been applied. Please compare again."
        ),
    }
    if kind is ErrorKind.SERVER_TASK_FAILED:
        return _("The server could not apply the changes: %s") % detail
    if kind is ErrorKind.SERVER_ERROR:
        return _("Server error %s. Please check your connection.") % detail
    if kind is ErrorKind.UNEXPECTED:
        return _("Unexpected error: %s") % detail
    return messages.get(kind, _("Unexpected error: %s") % detail)


class GrampsWebSyncTool(BatchTool, ManagedWindow):
    """Assistant presenting a :class:`session.SyncSession` to the user."""

    def __init__(self, dbstate, user, options_class, name, *args, **kwargs) -> None:
        """Build the assistant and the session behind it."""
        LOG.debug("Initializing Gramps Web Sync addon.")
        BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            # The user declined the undo-history warning; honour that instead
            # of opening the assistant anyway.
            LOG.debug("Undo history warning declined; not opening the tool.")
            return
        ManagedWindow.__init__(self, user.uistate, [], self.__class__)

        self.dbstate = dbstate

        self.credentials = ConfigCredentialStore()
        self.session = SyncSession(
            db=dbstate.db,
            user=self._user,
            backend_factory=self._make_backend,
            credentials=self.credentials,
            media=GrampsMediaStore(dbstate.db),
            runner=GLibTaskRunner(),
            io_runner=IoRunner(),
            clock=SystemClock(),
            listener=self,
        )

        self.assistant = Gtk.Assistant()
        self.set_window(self.assistant, None, _("Gramps Web Sync"))
        self.setup_configs("interface.webapisync", 780, 600)

        self.assistant.connect("close", self.do_close, "close")
        self.assistant.connect("cancel", self.do_close, "cancel")
        self.assistant.connect("prepare", self.prepare)

        self.intro = IntroductionPage(self.assistant)
        self.add_page(self.intro, Gtk.AssistantPageType.INTRO, _("Introduction"))

        self.loginpage = LoginPage(
            self.assistant,
            url=self.credentials.get_url(),
            username=self.credentials.get_username(),
            password=self.credentials.get_password(),
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
            self.sync_progress_page, Gtk.AssistantPageType.PROGRESS, _("Summary")
        )

        self.file_confirmation = FileConfirmationPage(self.assistant)
        self.add_page(
            self.file_confirmation, Gtk.AssistantPageType.CONFIRM, _("Media Files")
        )

        self.file_progress_page = FileProgressPage(self.assistant)
        self.add_page(
            self.file_progress_page,
            Gtk.AssistantPageType.PROGRESS,
            _("Progress Information"),
        )

        self.conclusion = ConclusionPage(self.assistant, on_retry=self.on_retry)
        self.add_page(self.conclusion, Gtk.AssistantPageType.SUMMARY, _("Summary"))

        self.show()
        self.assistant.set_forward_page_func(self.forward_page, None)

    # --------------------------------------------------------
    # Window management
    # --------------------------------------------------------
    def build_menu_names(self, obj):  # type: ignore
        """Override :class:`.ManagedWindow` method."""
        return (_("Gramps Web Sync"), None)

    def add_page(self, page, page_type, title=""):
        """Append a page to the assistant."""
        page.show_all()
        self.assistant.append_page(page)
        self.assistant.set_page_title(page, title)
        self.assistant.set_page_type(page, page_type)

    def do_close(self, assistant, signal_name="?"):
        """Close the assistant and release the session's resources.

        :param assistant: The assistant emitting the signal.
        :param signal_name: Which signal fired, ``close`` or ``cancel``.
        """
        LOG.debug(
            "Closing Gramps Web Sync addon (signal=%s, page=%s, state=%s).",
            signal_name,
            assistant.get_current_page(),
            self.session.state.name,
        )
        self.session.cancel()
        position = self.window.get_position()  # crock
        self.assistant.hide()
        self.window.move(position[0], position[1])
        self.close()

    def _make_backend(self, url: str, username: str, password: str) -> WebApiHandler:
        """Build the real Web API handler. Injected into the session."""
        return WebApiHandler(url, username, password, None)

    def on_retry(self, _button) -> None:
        """Resume a failed run from the step that failed."""
        self.session.retry()

    # --------------------------------------------------------
    # SessionListener
    # --------------------------------------------------------
    def on_state_changed(self, state: State) -> None:
        """Follow the session to the page representing ``state``."""
        target = PAGE_FOR_STATE[state]
        if self.assistant.get_current_page() != target:
            self.assistant.set_current_page(target)

    def on_progress(self, kind: str, fraction: float) -> None:
        """Render a progress update from the session."""
        if kind == "api":
            self.sync_progress_page.update_api_progress(fraction)
        else:
            self.file_progress_page.update_progress(kind, fraction)
        self._pump()

    def on_status(self, stage: str) -> None:
        """Render a status update from the session."""
        self._render_status(stage)
        self._pump()

    @staticmethod
    def _pump() -> None:
        """Redraw now.

        The session's steps run on the main loop, so without this the label
        and bar would not repaint until the whole step finished.
        """
        while Gtk.events_pending():
            Gtk.main_iteration()

    def _render_status(self, stage: str) -> None:
        """Show the message for ``stage``."""
        if stage == STATUS_FETCHING:
            self.diff_progress_page.label.set_text(_("Fetching remote data..."))
        elif stage == STATUS_COMPARING:
            self.diff_progress_page.label.set_text(
                _("Comparing local and remote data...")
            )
        elif stage == STATUS_LOCAL_APPLIED:
            self.sync_progress_page.label.set_text(
                _("Successfully applied changes to local database.")
            )

    # --------------------------------------------------------
    # Navigation
    # --------------------------------------------------------
    def forward_page(self, page, data):
        """Return the page index the session's flow says comes next."""
        return PAGE_FOR_STATE[next_state(self.session.state, self.session)]

    def prepare(self, assistant, page):
        """Render a page as it is shown, and fire any intent it triggers.

        Every intent is guarded on the session's current state, so a page
        being prepared more than once -- which happens whenever the session
        navigates to the page it is already on -- cannot start the same work
        twice.
        """
        page.update_complete()

        if page is self.loginpage:
            if self.session.state is State.INTRO:
                self.session.begin()
            if self.session.login_error is not None:
                error = self.session.login_error
                self.loginpage.show_error(error_message(error.kind, error.detail))
            else:
                self.loginpage.clear_error()
            self._show_keyring_notice(self.loginpage)

        elif page is self.diff_progress_page:
            if self.session.state is State.LOGIN:
                self.loginpage.clear_error()
                url = self.sanitize_url(self.loginpage.url.get_text())
                self.session.submit_credentials(
                    url,
                    self.loginpage.username.get_text(),
                    self.loginpage.password.get_text(),
                )

        elif page is self.confirmation:
            self.confirmation.prepare(self.session.changes)

        elif page is self.sync_progress_page:
            if self.session.state is State.REVIEW_CHANGES:
                self.assistant.commit()  # erases the visited page history
                mode = self.confirmation.sync_mode
                self.sync_progress_page.prepare(self.session, mode)
                self.session.confirm_changes(mode)

        elif page is self.file_confirmation:
            self.file_confirmation.prepare(
                self.session.missing_local, self.session.missing_remote
            )

        elif page is self.file_progress_page:
            if self.session.state is State.REVIEW_FILES:
                self.file_progress_page.prepare(
                    self.session.missing_local, self.session.missing_remote
                )
                self.session.confirm_files()

        elif page is self.conclusion:
            self.conclusion.prepare(self.session)
            self._show_keyring_notice(self.conclusion)

    def _show_keyring_notice(self, page) -> None:
        """Tell the user if the keyring could not be used.

        Reported rather than swallowed: without this the password field is
        simply empty every run and nothing explains why.
        """
        problem = self.credentials.keyring_error()
        if problem is not None:
            page.show_notice(keyring_message(problem))

    def sanitize_url(self, url: str) -> str:
        """Prepend https if no scheme is given, and warn about plain http.

        :param url: The URL as typed by the user.
        :returns: The URL to actually use.
        """
        url = url.strip()
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
                return urlunparse(parsed_url._replace(scheme="https"))
        return url


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
        if current_page is not None:
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
        self.error_label.get_style_context().add_class("error")
        self.error_label.set_no_show_all(True)  # Don't show when show_all() is called
        self.error_label.hide()
        grid.attach(self.error_label, 0, 3, 2, 1)

        # Non-fatal notice, e.g. an unusable keyring. Distinct from the error
        # label because it does not stop the user from continuing.
        self.notice_label = Gtk.Label()
        self.notice_label.set_line_wrap(True)
        self.notice_label.set_max_width_chars(60)
        self.notice_label.set_no_show_all(True)
        self.notice_label.hide()
        grid.attach(self.notice_label, 0, 4, 2, 1)

        # Connect entry change events
        self.url.connect("changed", self.on_entry_changed)
        self.username.connect("changed", self.on_entry_changed)
        self.password.connect("changed", self.on_entry_changed)

    def show_error(self, message: str):
        """Display an error message on the login page.

        The message is escaped: it can carry server or exception text, and an
        unescaped ``&`` or ``<`` would break the markup or swallow the message.
        """
        label = GLib.markup_escape_text(_("Error:"))
        self.error_label.set_markup(
            f"<b>{label}</b> {GLib.markup_escape_text(message)}"
        )
        self.error_label.show()
        self.update_complete()

    def clear_error(self):
        """Clear any displayed error message."""
        self.error_label.hide()
        self.update_complete()

    def show_notice(self, message: str):
        """Display a non-fatal notice, such as an unusable keyring."""
        self.notice_label.set_markup(f"<i>{GLib.markup_escape_text(message)}</i>")
        self.notice_label.show()

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
        self.sync_label.set_text(_("Sync mode"))

        # Box for radio buttons
        self.radio_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        #: Mode -> the one-line explanation shown when it is selected. With
        #: per-object selection out of scope this is the user's only control,
        #: so each option has to say what it will do.
        self.mode_descriptions = {
            MODE_BIDIRECTIONAL: _(
                "Changes from both sides are combined. Objects edited in both "
                "places are merged."
            ),
            MODE_RESET_TO_LOCAL: _(
                "The server is made to match this computer. Anything changed "
                "only on the server is discarded."
            ),
            MODE_RESET_TO_REMOTE: _(
                "This computer is made to match the server. Anything changed "
                "only here is discarded."
            ),
        }

        first = None
        for mode, label in (
            (MODE_BIDIRECTIONAL, _("Bidirectional Synchronization")),
            (MODE_RESET_TO_LOCAL, _("Reset remote to local")),
            (MODE_RESET_TO_REMOTE, _("Reset local to remote")),
        ):
            if first is None:
                button = Gtk.RadioButton.new_with_label_from_widget(None, label)
                first = button
            else:
                button = Gtk.RadioButton.new_from_widget(first)
                button.set_label(label)
            button.connect("toggled", self.on_radio_button_toggled, mode)
            self.radio_box.pack_start(button, False, False, 0)

        self.description_label = Gtk.Label()
        self.description_label.set_line_wrap(True)
        self.description_label.set_max_width_chars(70)
        self.description_label.set_xalign(0)

        # Box to hold the label and radio buttons
        self.label_radio_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.label_radio_box.pack_start(self.sync_label, False, False, 0)
        self.label_radio_box.pack_start(self.radio_box, False, False, 0)
        self.label_radio_box.pack_start(self.description_label, False, False, 0)

        self.outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.outer_box.pack_start(scrolled_window, True, True, 0)
        self.outer_box.pack_start(self.label_radio_box, False, False, 10)

        self.pack_start(self.outer_box, True, True, 0)

    def on_radio_button_toggled(self, button, name):
        """Callback for radio buttons setting sync mode."""
        if button.get_active():
            self.sync_mode = int(name)
            self.update_description()

    def update_description(self):
        """Describe the selected mode, warning if it deletes."""
        text = self.mode_descriptions.get(self.sync_mode, "")
        if self.sync_mode in DESTRUCTIVE_MODES:
            self.description_label.set_markup(
                f"<b>{GLib.markup_escape_text(_('Warning:'))}</b> "
                f"{GLib.markup_escape_text(text)}"
            )
        else:
            self.description_label.set_text(text)

    def prepare(self, changes: Actions):
        """Convert the changes list to a tree store."""
        self.store.clear()  # this page may be prepared more than once
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

        self.update_description()
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

    def prepare(self, session: SyncSession, sync_mode: int):
        """Describe the work about to be done.

        Called before the session applies anything, so the actions are derived
        here from the mode the user just chose.

        :param session: The session holding the pending changes.
        :param sync_mode: The mode selected on the confirmation page.
        """
        actions = changes_to_actions(session.changes, sync_mode)
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
            self.label_progressbar_api.set_text(
                _("Applying changes to remote database ...")
            )
            self.progressbar_api.show()
        else:
            self.label_progressbar_api.set_text(
                _("No changes to apply to remote database.")
            )
            self.progressbar_api.hide()


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
        """List the files that would be transferred."""
        self.store.clear()  # this page may be prepared more than once
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
            self.label1.set_text(
                ngettext(
                    "Downloading %s media file",
                    "Downloading %s media files",
                    n_down,
                )
                % n_down
            )
        n_up = len(files_missing_remote)
        if not n_up:
            self.label2.hide()
            self.progressbar2.hide()
        else:
            self.label2.show()
            self.progressbar2.show()
            self.label2.set_text(
                ngettext(
                    "Uploading %s media file",
                    "Uploading %s media files",
                    n_up,
                )
                % n_up
            )

    def update_progress(self, kind: str, fraction: float):
        """Update the download or upload progress bar.

        :param kind: Either ``"download"`` or ``"upload"``.
        :param fraction: Completed share of that transfer, in ``[0, 1]``.
        """
        if kind == "download":
            self.progressbar1.set_fraction(fraction)
        elif kind == "upload":
            self.progressbar2.set_fraction(fraction)


class ConclusionPage(Page):
    """The conclusion page, reporting either the outcome or the error.

    :param assistant: The assistant owning this page.
    :param on_retry: Called when the user asks to resume a failed run.
    """

    def __init__(self, assistant, on_retry=None):
        super().__init__(assistant)
        label = Gtk.Label(label="")
        label.set_line_wrap(True)
        label.set_use_markup(True)
        label.set_max_width_chars(60)
        self.label = label
        self.pack_start(self.label, False, False, 0)

        self.notice_label = Gtk.Label()
        self.notice_label.set_line_wrap(True)
        self.notice_label.set_max_width_chars(60)
        self.notice_label.set_no_show_all(True)
        self.notice_label.hide()
        self.pack_start(self.notice_label, False, False, 10)

        # A failed run would otherwise be a dead end: the only button on a
        # summary page is Close, and reopening the tool re-downloads and
        # re-diffs the whole tree for what is usually a transient problem.
        self.retry_button = Gtk.Button(label=_("Try again"))
        self.retry_button.set_halign(Gtk.Align.CENTER)
        self.retry_button.set_no_show_all(True)
        self.retry_button.hide()
        if on_retry is not None:
            self.retry_button.connect("clicked", on_retry)
        self.pack_start(self.retry_button, False, False, 10)

    def prepare(self, session: SyncSession) -> None:
        """Render the final message for ``session``."""
        if session.error is not None:
            self.label.set_text(
                error_message(session.error.kind, session.error.detail)
            )
        else:
            self.label.set_text(self._outcome_summary(session))
        self.retry_button.set_visible(session.can_retry)
        self.set_complete()

    def show_notice(self, message: str) -> None:
        """Show a non-fatal notice alongside the outcome."""
        self.notice_label.set_markup(f"<i>{GLib.markup_escape_text(message)}</i>")
        self.notice_label.show()

    def _outcome_summary(self, session: SyncSession) -> str:
        """Describe what the run actually did, to both trees and to media.

        The old summary reported media only, so a run that applied hundreds of
        object changes and moved no files said "Media files are in sync."
        """
        parts = []
        applied = len(session.actions)
        if applied:
            parts.append(
                ngettext("Applied %s change.", "Applied %s changes.", applied)
                % applied
            )
        transfer = self._transfer_summary(session)
        if transfer:
            parts.append(transfer)
        elif not session.missing_both:
            parts.append(_("Media files are in sync."))
        if session.missing_both:
            count = len(session.missing_both)
            parts.append(
                ngettext(
                    "%s media file is missing on both sides and could not be "
                    "transferred.",
                    "%s media files are missing on both sides and could not be "
                    "transferred.",
                    count,
                )
                % count
            )
        if not parts:
            parts.append(_("Both trees are already in sync."))
        return " ".join(parts)

    @staticmethod
    def _transfer_summary(session: SyncSession) -> str:
        """Summarize how many media files moved, and how many failed."""
        text = ""
        if session.downloaded:
            ok = sum(session.downloaded.values())
            nok = sum(not v for v in session.downloaded.values())
            if ok:
                text += (
                    ngettext(
                        "Successfully downloaded %s media file.",
                        "Successfully downloaded %s media files.",
                        ok,
                    )
                    % ok
                    + " "
                )
            if nok:
                text += (
                    ngettext(
                        "Encountered %s error during download.",
                        "Encountered %s errors during download.",
                        nok,
                    )
                    % nok
                    + " "
                )
        if session.uploaded:
            ok = sum(session.uploaded.values())
            nok = sum(not v for v in session.uploaded.values())
            if ok:
                text += (
                    ngettext(
                        "Successfully uploaded %s media file.",
                        "Successfully uploaded %s media files.",
                        ok,
                    )
                    % ok
                    + " "
                )
            if nok:
                text += ngettext(
                    "Encountered %s error during upload.",
                    "Encountered %s errors during upload.",
                    nok,
                ) % nok
        return text


class GrampsWebSyncOptions(ToolOptions):
    """Options for Gramps Web Sync."""
