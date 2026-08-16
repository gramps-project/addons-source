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

Provides :class:`GrampsWebSyncTool`, a dialog presenting a
:class:`session.SyncSession` as four panes in a :class:`Gtk.Stack`.
:data:`PANE_FOR_STATE` maps each :class:`session.State` to the pane that
represents it and :func:`error_message` localizes a :class:`session.ErrorKind`.

The synchronization itself lives in :mod:`session`, and everything the panes
render is prepared in :mod:`presentation`.
"""

from __future__ import annotations

import logging
import time

from adapters import (
    ConfigCredentialStore,
    GLibTaskRunner,
    GrampsMediaStore,
    IoRunner,
    SystemClock,
)
from const import MODE_BIDIRECTIONAL, SYNC_MODES
from diffhandler import changes_to_actions
from gi.repository import GLib, Gtk, Pango
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.dialog import QuestionDialog2
from gramps.gui.display import display_url
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.plug.tool import BatchTool, ToolOptions
from presentation import (
    ReviewModel,
    build_review,
    deletion_warning,
    destination_label,
    error_message,
    context_lines,
    format_last_synced,
    insecure_warning,
    is_insecure,
    keyring_message,
    media_label,
    missing_both_notice,
    mode_description,
    mode_label,
    outcome_summary,
    sanitize_url,
    state_label,
    status_message,
    transfer_message,
    verb_label,
    version_line,
)
from session import WORKING_STATES, State, SyncSession
from webapihandler import WebApiHandler

assert glocale is not None  # for type checker
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


LOG = logging.getLogger("grampswebsync")

#: Where the manual lives. Deliberately the English page rather than a
#: localized one: the site declares its translations as ``hreflang`` alternates
#: and renders a language switcher from them, so it always offers every
#: language it currently has. Anything this addon hardcoded would be a guess
#: that goes stale, and a wrong guess is a 404.
#:
#: ``gramps.gui.display.display_help`` must not be used to open it -- it
#: appends the UI locale to whatever it is given, full URLs included.
DOCUMENTATION_URL = "https://www.grampsweb.org/administration/sync/"

#: Names of the stack's children.
PANE_CONNECT = "connect"
PANE_WORKING = "working"
PANE_REVIEW = "review"
PANE_RESULT = "result"

#: The one place that knows how flow states correspond to panes. Four panes
#: replace the eight assistant pages this tool used to have; the states that
#: differ only in what work is running share the working pane, and both
#: terminal states share the result pane.
PANE_FOR_STATE: dict[State, str] = {
    State.CONNECT: PANE_CONNECT,
    State.CONNECTING: PANE_WORKING,
    State.COMPARING: PANE_WORKING,
    State.REVIEW: PANE_REVIEW,
    State.APPLYING: PANE_WORKING,
    State.TRANSFERRING: PANE_WORKING,
    State.DONE: PANE_RESULT,
    State.FAILED: PANE_RESULT,
}

#: States in which the tool has begun writing. The server may not be swapped
#: underneath a run that has already committed something, and abandoning one
#: would leave no record of how far it got.
WRITING_STATES = (State.APPLYING, State.TRANSFERRING)

#: Response ids for the buttons the dialog adds itself.
RESPONSE_CONNECT = 1
RESPONSE_APPLY = 2
RESPONSE_RETRY = 3

#: Names of the phase markers, as children of each row's marker stack.
MARK_DONE = "done"
MARK_ACTIVE = "active"
MARK_PENDING = "pending"

#: Themed icon standing for a finished phase. A symbolic icon follows the
#: theme's foreground colour and its dark variant, which neither a text glyph
#: nor a bundled SVG would; the theme is also already a Gramps dependency.
DONE_ICON = "emblem-ok-symbolic"

#: How often the working pane is refreshed. A progress bar in pulse mode only
#: moves when it is told to, so this is the pulse rate as well as the rate the
#: elapsed clock is checked at.
TICK_INTERVAL_MS = 120

#: Column of the review tree holding the object name: free text of unbounded
#: length, and the only one that gives way when the window is too narrow.
NAME_COLUMN = 1

#: How narrow the name column may get before the tree scrolls instead.
NAME_MIN_WIDTH = 180

#: How wide the progress bar is allowed to get. Left to fill the pane it
#: stretches the width of the window and reads as a divider rather than a bar.
PROGRESS_WIDTH = 380


def _dim(text: str) -> str:
    """Return markup rendering ``text`` as secondary."""
    return f"<small>{GLib.markup_escape_text(text)}</small>"


def _hide_until_needed(widget: Gtk.Widget) -> None:
    """Show a widget's contents, then leave the widget itself hidden.

    Order matters. ``show_all`` skips a widget that has no-show-all set and so
    never reaches its children, which leaves a container that is later made
    visible looking empty.

    :param widget: The widget to prepare. Call after adding its children.
    """
    widget.show_all()
    widget.set_no_show_all(True)
    widget.hide()


def _label(text: str = "", *, xalign: float = 0.0, wrap: bool = True) -> Gtk.Label:
    """Return a left-aligned label with sensible wrapping defaults."""
    label = Gtk.Label(label=text)
    label.set_xalign(xalign)
    if wrap:
        label.set_line_wrap(True)
        label.set_max_width_chars(60)
    return label


# ------------------------------------------------------------
#
# The tool
#
# ------------------------------------------------------------
class GrampsWebSyncTool(BatchTool, ManagedWindow):
    """Dialog presenting a :class:`session.SyncSession` to the user."""

    def __init__(self, dbstate, user, options_class, name, *args, **kwargs) -> None:
        """Build the dialog and the session behind it."""
        LOG.debug("Initializing Gramps Web Sync addon.")
        BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            # The user declined the undo-history warning; honour that instead
            # of opening the dialog anyway.
            LOG.debug("Undo history warning declined; not opening the tool.")
            return
        ManagedWindow.__init__(self, user.uistate, [], self.__class__)

        self.dbstate = dbstate
        self._timer_id: int | None = None
        self._phase_started = time.monotonic()

        self.credentials = ConfigCredentialStore(tree_id=dbstate.db.get_dbid())
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

        self._build_window()
        self.show()
        self._start()

    # --------------------------------------------------------
    # Window construction
    # --------------------------------------------------------
    def _build_window(self) -> None:
        """Assemble the dialog: context strip, pane stack, footer, buttons."""
        self.dialog = Gtk.Dialog()
        self.set_window(self.dialog, None, _("Gramps Web Sync"))
        # A new key deliberately. The old one holds whatever size suited the
        # eight-page assistant, and a window that shares almost nothing with it
        # should not inherit a geometry chosen for the other one.
        self.setup_configs("interface.grampswebsync", 820, 640)

        content = self.dialog.get_content_area()
        content.set_spacing(0)

        self.context = ContextStrip(on_change_server=self._on_change_server)
        content.pack_start(self.context, False, False, 0)
        content.pack_start(
            Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0
        )

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_border_width(12)
        self.connect_pane = ConnectPane(
            on_changed=self._on_connect_fields_changed, on_forget=self._on_forget
        )
        self.working_pane = WorkingPane()
        self.review_pane = ReviewPane()
        self.result_pane = ResultPane()
        self.stack.add_named(self.connect_pane, PANE_CONNECT)
        self.stack.add_named(self.working_pane, PANE_WORKING)
        self.stack.add_named(self.review_pane, PANE_REVIEW)
        self.stack.add_named(self.result_pane, PANE_RESULT)
        content.pack_start(self.stack, True, True, 0)

        self.version_label = _label(wrap=False)
        self.version_label.set_margin_start(12)
        self.version_label.set_margin_bottom(6)
        self.version_label.set_markup(_dim(version_line(None)))
        content.pack_start(self.version_label, False, False, 0)

        self._build_buttons()
        self.dialog.connect("response", self._on_response)

    def _build_buttons(self) -> None:
        """Add every button once; visibility follows the state."""
        self.button_cancel = self.dialog.add_button(
            _("_Cancel"), Gtk.ResponseType.CANCEL
        )
        self.button_close = self.dialog.add_button(_("_Close"), Gtk.ResponseType.CLOSE)
        self.button_retry = self.dialog.add_button(_("_Try again"), RESPONSE_RETRY)
        self.button_connect = self.dialog.add_button(_("C_onnect"), RESPONSE_CONNECT)
        self.button_apply = self.dialog.add_button(_("_Apply"), RESPONSE_APPLY)
        for button in self._buttons():
            button.set_can_default(True)
            button.set_no_show_all(True)
            button.hide()

    def _buttons(self) -> tuple[Gtk.Button, ...]:
        """Return every button in the action area."""
        return (
            self.button_cancel,
            self.button_close,
            self.button_retry,
            self.button_connect,
            self.button_apply,
        )

    def build_menu_names(self, obj):  # type: ignore
        """Override :class:`.ManagedWindow` method."""
        return (_("Gramps Web Sync"), None)

    def _make_backend(self, url: str, username: str, password: str) -> WebApiHandler:
        """Build the real Web API handler. Injected into the session."""
        return WebApiHandler(url, username, password, None)

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    def _start(self) -> None:
        """Show the stored server, and connect if it belongs to the open tree.

        Where the tree cannot be established the credentials are still offered,
        but the user presses Connect.
        """
        # Connecting unprompted is only safe for the tree the entry was synced
        # from: against another one the two share nothing, every object falls
        # the wrong side of the baseline, and a bidirectional run proposes
        # deleting both trees.
        url = self.credentials.get_url()
        username = self.credentials.get_username()
        password = self.credentials.get_password() or ""
        self.connect_pane.set_credentials(url, username, password)
        self.connect_pane.set_notices(self._connect_notices())
        self.connect_pane.set_can_forget(bool(url))
        self.connect_pane.set_remember_password(
            self.credentials.get_remember_password()
        )
        self._refresh_password_storage()
        if url and username and password and self.credentials.is_for_open_tree():
            self._submit()
        else:
            self._render(self.session.state)

    def clean_up(self) -> None:
        """Release the session and stop the clock when the window goes away."""
        self._stop_timer()
        self.session.cancel()
        super().clean_up()

    def _on_response(self, _dialog, response: int) -> None:
        """Act on a button in the action area."""
        if response == Gtk.ResponseType.DELETE_EVENT:
            # ManagedWindow already closed us from its own delete-event
            # handler; acting again would only warn about a double close.
            return
        if response == RESPONSE_CONNECT:
            self._submit()
        elif response == RESPONSE_APPLY:
            self.session.confirm(
                self.review_pane.sync_mode, self.review_pane.transfer_media
            )
        elif response == RESPONSE_RETRY:
            self.session.retry()
        else:
            LOG.debug("Closing Gramps Web Sync addon (response=%s).", response)
            self.close()

    def _on_change_server(self, _button) -> None:
        """Stop whatever is running and return to the connect pane.

        Reachable while connecting and comparing, so that switching servers
        does not first cost a whole download of the one being left.
        """
        self.session.abandon()

    def _on_forget(self, _button) -> None:
        """Remove the stored server, after asking.

        The password can be retyped; the baseline cannot be recovered, and
        losing it turns the next run into a full comparison. That is worth a
        confirmation.
        """
        url = self.connect_pane.url.get_text()
        username = self.connect_pane.username.get_text()
        question = QuestionDialog2(
            _("Forget this server?"),
            _(
                "The address, user name and password stored for this server "
                "will be removed, along with the record of when this family "
                "tree last synchronized with it. The next synchronization "
                "will compare the two trees from scratch."
            ),
            _("Forget"),
            _("Cancel"),
            parent=self.window,
        )
        if not question.run():
            return
        LOG.info("Forgetting the stored server.")
        self.credentials.forget(url, username)
        self.connect_pane.set_credentials("", "", "")
        # Also drops the session's copy of the connection, which the context
        # strip and the version footer are rendered from.
        self.session.abandon()

    def _submit(self) -> None:
        """Hand what the connect pane holds to the session."""
        url = sanitize_url(self.connect_pane.url.get_text())
        self.connect_pane.set_url(url)
        self.session.submit_credentials(
            url,
            self.connect_pane.username.get_text(),
            self.connect_pane.password.get_text(),
            self.connect_pane.remember_password,
        )

    # --------------------------------------------------------
    # SessionListener
    # --------------------------------------------------------
    def on_state_changed(self, state: State) -> None:
        """Follow the session to the pane representing ``state``."""
        self._render(state)

    def on_progress(self, kind: str, fraction: float) -> None:
        """Render a progress update from the session."""
        detail = transfer_message(kind)
        if detail:
            self.working_pane.set_detail(detail)
        self.working_pane.set_fraction(fraction)
        self._pump()

    def on_status(self, stage: str) -> None:
        """Render a status update from the session."""
        self.working_pane.set_detail(status_message(stage))
        self._pump()

    @staticmethod
    def _pump() -> None:
        """Redraw now.

        The steps that touch a database run on the main loop, so without this
        the pane would not repaint until the whole step finished.
        """
        while Gtk.events_pending():
            Gtk.main_iteration()

    # --------------------------------------------------------
    # Rendering
    # --------------------------------------------------------
    def _render(self, state: State) -> None:
        """Show the pane for ``state`` and bring the rest of the shell in line."""
        self._prepare_pane(state)
        self.stack.set_visible_child_name(PANE_FOR_STATE[state])
        self._update_buttons(state)
        self._update_context(state)
        self._update_timer(state)
        self.version_label.set_markup(_dim(version_line(self.session.api_version)))

    def _prepare_pane(self, state: State) -> None:
        """Fill the pane for ``state`` with what the session now holds."""
        if state is State.CONNECT:
            error = self.session.login_error
            if error is None:
                self.connect_pane.clear_error()
            else:
                self.connect_pane.show_error(
                    error_message(error.kind, error.detail)
                )
            self.connect_pane.set_notices(self._connect_notices())
            self.connect_pane.set_can_forget(bool(self.credentials.get_url()))
            self._refresh_password_storage()
        elif state in WORKING_STATES:
            self.working_pane.set_state(state)
        elif state is State.REVIEW:
            self.review_pane.prepare(self.session)
        else:
            self.result_pane.prepare(self.session)
            # A keyring write happens after a successful connect, so its
            # failure can land once the user has left the connect pane.
            problem = self.credentials.keyring_error()
            if problem is not None:
                self.result_pane.show_notice(keyring_message(problem))

    def _update_buttons(self, state: State) -> None:
        """Show the buttons that make sense in ``state``, and pick the default."""
        terminal = state in (State.DONE, State.FAILED)
        self.button_cancel.set_visible(not terminal)
        self.button_close.set_visible(terminal)
        self.button_retry.set_visible(
            state is State.FAILED and self.session.can_retry
        )
        self.button_connect.set_visible(state is State.CONNECT)
        self.button_apply.set_visible(state is State.REVIEW)
        if state is State.CONNECT:
            self._on_connect_fields_changed()
            self.button_connect.grab_default()
        elif state is State.REVIEW:
            self.button_apply.grab_default()

    def _update_context(self, state: State) -> None:
        """Say which tree is being synced, and when it last was."""
        url = self.session.url or self.credentials.get_url()
        username = self.session.username or self.credentials.get_username()
        title, subtitle = context_lines(
            url,
            username,
            self.session.tree_name,
            format_last_synced(self.credentials.get_timestamp(url, username)),
        )
        self.context.update(title, subtitle)
        self.context.set_busy(state in WRITING_STATES)

    def _connect_notices(self) -> list[str]:
        """Return everything worth saying on the connect pane, in order.

        An unusable keyring is reported rather than swallowed: without it the
        password field is simply empty every run and nothing explains why.
        """
        notices = []
        if self.credentials.is_from_another_tree():
            notices.append(
                _(
                    "These credentials were last used with a different family "
                    "tree. Check the server before continuing."
                )
            )
        problem = self.credentials.keyring_error()
        if problem is not None:
            notices.append(keyring_message(problem))
        return notices

    def _refresh_password_storage(self) -> None:
        """Offer to remember the password only where that can be honoured."""
        problem = self.credentials.keyring_error()
        self.connect_pane.set_keyring_available(
            problem is None, "" if problem is None else keyring_message(problem)
        )

    def _on_connect_fields_changed(self) -> None:
        """Keep the Connect button in step with the entries."""
        self.button_connect.set_sensitive(self.connect_pane.complete)

    # --------------------------------------------------------
    # Elapsed time
    # --------------------------------------------------------
    def _update_timer(self, state: State) -> None:
        """Run a one-second clock for as long as a phase is running.

        A progress bar that can only pulse -- which is what the server's task
        endpoint gives us for most of an apply -- reads as a hang without one.
        """
        if state in WORKING_STATES:
            self._phase_started = time.monotonic()
            self.working_pane.set_elapsed(0)
            if self._timer_id is None:
                self._timer_id = GLib.timeout_add(TICK_INTERVAL_MS, self._tick)
        else:
            self._stop_timer()

    def _stop_timer(self) -> None:
        """Stop the elapsed-time clock, if it is running."""
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None

    def _tick(self) -> bool:
        """Animate the progress bar and update the elapsed-time readout."""
        self.working_pane.pulse()
        self.working_pane.set_elapsed(int(time.monotonic() - self._phase_started))
        return True


# ------------------------------------------------------------
#
# Shell widgets
#
# ------------------------------------------------------------
class ContextStrip(Gtk.Box):
    """Names the tree being synced, where from, and when it last was.

    The sync baseline governs the entire conflict classification, and until now
    nothing in the interface revealed it, or even which server was about to be
    written to -- let alone which tree on it.

    :param on_change_server: Called when the user wants a different server.
    """

    def __init__(self, on_change_server) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_border_width(12)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.server_label = _label(wrap=False)
        self.server_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.synced_label = _label(wrap=False)
        text.pack_start(self.server_label, False, False, 0)
        text.pack_start(self.synced_label, False, False, 0)
        self.pack_start(text, True, True, 0)

        self.change_button = Gtk.Button(label=_("Change server…"))
        self.change_button.set_valign(Gtk.Align.CENTER)
        self.change_button.connect("clicked", on_change_server)
        self.pack_start(self.change_button, False, False, 0)

    def update(self, title: str, subtitle: str) -> None:
        """Show what is being synced, and where from.

        :param title: The remote tree's name once known, else the account.
        :param subtitle: The line below it.
        """
        self.server_label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        self.synced_label.set_markup(_dim(subtitle))

    def set_busy(self, busy: bool) -> None:
        """Block a server switch while a sync is running."""
        self.change_button.set_sensitive(not busy)


class ConnectPane(Gtk.Box):
    """Server URL, user name and password, plus what used to be the intro page.

    :param on_changed: Called whenever an entry changes.
    :param on_forget: Called when the user asks to remove the stored server.
    """

    def __init__(self, on_changed, on_forget) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._on_changed = on_changed

        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(12)
        self.pack_start(grid, False, False, 0)

        self.url = self._entry(grid, _("Server URL:"), 0)
        self.url.set_input_purpose(Gtk.InputPurpose.URL)
        self.username = self._entry(grid, _("Username:"), 1)
        self.password = self._entry(grid, _("Password:"), 2)
        self.password.set_visibility(False)
        self.password.set_input_purpose(Gtk.InputPurpose.PASSWORD)

        self.remember_check = Gtk.CheckButton(label=_("Remember password"))
        self.remember_check.set_active(True)
        self.pack_start(self.remember_check, False, False, 0)

        self.scheme_label = self._hidden_label()
        self.pack_start(self.scheme_label, False, False, 0)
        self.error_label = self._hidden_label()
        self.error_label.get_style_context().add_class("error")
        self.pack_start(self.error_label, False, False, 0)
        self.notice_label = self._hidden_label()
        self.pack_start(self.notice_label, False, False, 0)

        self.forget_button = Gtk.Button(label=_("Forget this server"))
        self.forget_button.set_halign(Gtk.Align.START)
        self.forget_button.connect("clicked", on_forget)
        self.pack_start(self.forget_button, False, False, 0)

        self.pack_start(self._about(), False, False, 0)

    def _entry(self, grid: Gtk.Grid, text: str, row: int) -> Gtk.Entry:
        """Add one labelled entry to ``grid`` and return it."""
        grid.attach(_label(text, wrap=False), 0, row, 1, 1)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_activates_default(True)
        entry.connect("changed", self._on_entry_changed)
        grid.attach(entry, 1, row, 1, 1)
        return entry

    @staticmethod
    def _hidden_label() -> Gtk.Label:
        """Return a label that stays hidden until it has something to say."""
        label = _label()
        label.set_no_show_all(True)
        label.hide()
        return label

    def _about(self) -> Gtk.Expander:
        """Return the collapsed introduction, with a link to the wiki page.

        Four paragraphs of preconditions matter on first use and are friction
        on run fifty, so they fold away instead of occupying a page of their own.
        """
        expander = Gtk.Expander(label=_("About this tool"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(6)
        box.pack_start(_label(self._intro_text()), False, False, 0)
        help_button = Gtk.Button(label=_("Open the online manual"))
        help_button.set_halign(Gtk.Align.START)
        help_button.connect(
            "clicked", lambda *_a: display_url(DOCUMENTATION_URL)
        )
        box.pack_start(help_button, False, False, 0)
        expander.add(box)
        return expander

    @staticmethod
    def _intro_text() -> str:
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

    # --------------------------------------------------------
    # Contents
    # --------------------------------------------------------
    def set_credentials(self, url: str, username: str, password: str) -> None:
        """Pre-fill the entries from the credential store."""
        self.url.set_text(url or "")
        self.username.set_text(username or "")
        self.password.set_text(password or "")

    @property
    def remember_password(self) -> bool:
        """Whether the user is willing to have the password stored."""
        return self.remember_check.get_active()

    def set_remember_password(self, remember: bool) -> None:
        """Reflect the choice stored for this server."""
        self.remember_check.set_active(remember)

    def set_keyring_available(self, available: bool, reason: str = "") -> None:
        """Withdraw the offer when there is nowhere to store a password.

        Left checked but inert, the box would promise something that cannot
        happen; the reason goes on the tooltip so the state is explicable.
        """
        self.remember_check.set_sensitive(available)
        if not available:
            self.remember_check.set_active(False)
        self.remember_check.set_tooltip_text(reason or None)

    def set_can_forget(self, can_forget: bool) -> None:
        """Offer removal only when there is something stored to remove."""
        self.forget_button.set_sensitive(can_forget)

    def set_url(self, url: str) -> None:
        """Show the URL that will actually be used.

        The scheme is completed before connecting, and leaving the entry
        showing something else would misreport what the tool just did.
        """
        if self.url.get_text() != url:
            self.url.set_text(url)

    @property
    def complete(self) -> bool:
        """Whether all three fields have something in them."""
        return bool(
            self.url.get_text()
            and self.username.get_text()
            and self.password.get_text()
        )

    def show_error(self, message: str) -> None:
        """Display an error.

        The message is escaped: it can carry server or exception text, and an
        unescaped ``&`` or ``<`` would break the markup or swallow the message.
        """
        label = GLib.markup_escape_text(_("Error:"))
        self.error_label.set_markup(
            f"<b>{label}</b> {GLib.markup_escape_text(message)}"
        )
        self.error_label.show()

    def clear_error(self) -> None:
        """Clear any displayed error message."""
        self.error_label.hide()

    def set_notices(self, messages: list[str]) -> None:
        """Display non-fatal notices, or hide the label when there are none."""
        if not messages:
            self.notice_label.hide()
            return
        self.notice_label.set_markup(
            "\n".join(
                f"<i>{GLib.markup_escape_text(message)}</i>" for message in messages
            )
        )
        self.notice_label.show()

    def _on_entry_changed(self, _widget) -> None:
        """Clear a stale error, warn about http, and report the change on."""
        self.clear_error()
        if is_insecure(self.url.get_text()):
            self.scheme_label.set_markup(
                f"<b>{GLib.markup_escape_text(_('Warning:'))}</b> "
                f"{GLib.markup_escape_text(insecure_warning())}"
            )
            self.scheme_label.show()
        else:
            self.scheme_label.hide()
        self._on_changed()


class PhaseRow:
    """One line of the working pane's phase list: a marker and a name.

    The marker is a themed symbolic icon or a spinner rather than a character,
    so it neither depends on the interface font carrying the glyph nor stays
    the wrong colour in a dark theme.

    :param state: The phase this row stands for.
    """

    def __init__(self, state: State) -> None:
        self.marker = Gtk.Stack()
        self.marker.set_valign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.marker.add_named(Gtk.Box(), MARK_PENDING)
        self.marker.add_named(self.spinner, MARK_ACTIVE)
        self.marker.add_named(self._done_icon(), MARK_DONE)
        self.label = _label(state_label(state), wrap=False)
        # A stack has no visible child until its children are shown, and would
        # then ignore being told which one to display.
        self.marker.show_all()
        self.set_marker(MARK_PENDING)

    @staticmethod
    def _done_icon() -> Gtk.Widget:
        """Return the finished marker, falling back if the theme lacks it."""
        if Gtk.IconTheme.get_default().has_icon(DONE_ICON):
            return Gtk.Image.new_from_icon_name(DONE_ICON, Gtk.IconSize.MENU)
        return Gtk.Label(label="\u2713")

    def set_marker(self, marker: str) -> None:
        """Show this row as pending, running or finished.

        :param marker: One of the ``MARK_*`` names.
        """
        self.marker.set_visible_child_name(marker)
        if marker == MARK_ACTIVE:
            self.spinner.start()
        else:
            self.spinner.stop()
        name = GLib.markup_escape_text(self.label.get_text())
        self.label.set_markup(
            f"<b>{name}</b>" if marker == MARK_ACTIVE else name
        )


class WorkingPane(Gtk.Box):
    """A phase list, a detail line, a progress bar and an elapsed-time clock.

    One pane covers every long-running stage. The phase list is what tells the
    user where in the run they are; the clock is what distinguishes slow from
    stuck while the progress bar can only pulse.
    """

    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=24)
        self.set_valign(Gtk.Align.CENTER)
        # Filling the width would space the phase list and the bar far apart.
        self.set_halign(Gtk.Align.CENTER)

        #: Whether the running phase has reported a real fraction. Until it
        #: does the bar is pulsed; afterwards pulsing would fight the value.
        self._measurable = False
        self._elapsed_text = ""

        self._rows: dict[State, PhaseRow] = {}
        phases = Gtk.Grid()
        phases.set_row_spacing(8)
        phases.set_column_spacing(12)
        for index, state in enumerate(WORKING_STATES):
            row = PhaseRow(state)
            phases.attach(row.marker, 0, index, 1, 1)
            phases.attach(row.label, 1, index, 1, 1)
            self._rows[state] = row
        self.pack_start(phases, False, False, 0)

        # Grouped, so the detail line reads as belonging to the bar below it
        # rather than to the phase list above.
        progress = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.detail_label = _label(xalign=0.5)
        progress.pack_start(self.detail_label, False, False, 0)
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_size_request(PROGRESS_WIDTH, -1)
        progress.pack_start(self.progressbar, False, False, 0)
        self.elapsed_label = _label(xalign=0.5, wrap=False)
        progress.pack_start(self.elapsed_label, False, False, 0)
        self.pack_start(progress, False, False, 0)

    def set_state(self, state: State) -> None:
        """Mark ``state`` as the phase now running.

        Phases the run skipped are marked done rather than left pending: they
        are behind the user either way, and a list that never fills in reads as
        something having gone wrong.
        """
        current = WORKING_STATES.index(state)
        for index, phase in enumerate(WORKING_STATES):
            if index < current:
                mark = MARK_DONE
            elif index == current:
                mark = MARK_ACTIVE
            else:
                mark = MARK_PENDING
            self._rows[phase].set_marker(mark)
        self._measurable = False
        self.progressbar.set_fraction(0)

    def set_detail(self, text: str) -> None:
        """Show what the running phase is doing right now."""
        self.detail_label.set_text(text)

    def set_fraction(self, fraction: float) -> None:
        """Advance the progress bar, or pulse it when nothing is measurable."""
        if fraction >= 0:
            self._measurable = True
            self.progressbar.set_fraction(min(fraction, 1.0))
        else:
            self.progressbar.pulse()

    def pulse(self) -> None:
        """Advance the bar while the running phase reports no fraction.

        Downloading the remote tree reports none at all, so without a caller
        on a timer the bar moved one step and then stood still for the longest
        phase of the run.
        """
        if not self._measurable:
            self.progressbar.pulse()

    def set_elapsed(self, seconds: int) -> None:
        """Show how long the current phase has been running."""
        text = "" if seconds < 3 else f"{seconds // 60}:{seconds % 60:02d}"
        if text != self._elapsed_text:
            self._elapsed_text = text
            self.elapsed_label.set_markup(_dim(text))


class ReviewPane(Gtk.Box):
    """The one screen that matters: what will happen, and to which tree.

    The list is regenerated from the selected mode, so it shows the *actions*
    that mode produces rather than the raw differences. Media transfers are a
    checkbox here rather than a second confirmation page of their own.

    """

    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._session: SyncSession | None = None
        self.sync_mode = MODE_BIDIRECTIONAL

        self.mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.mode_box.pack_start(
            _label(_("Sync mode:"), wrap=False), False, False, 0
        )
        first = None
        for mode in SYNC_MODES:
            if first is None:
                button = Gtk.RadioButton.new_with_label_from_widget(
                    None, mode_label(mode)
                )
                first = button
            else:
                button = Gtk.RadioButton.new_with_label_from_widget(
                    first, mode_label(mode)
                )
            button.connect("toggled", self._on_mode_toggled, mode)
            self.mode_box.pack_start(button, False, False, 0)
        self.description_label = _label()
        self.description_label.set_margin_start(24)
        self.mode_box.pack_start(self.description_label, False, False, 0)
        _hide_until_needed(self.mode_box)
        self.pack_start(self.mode_box, False, False, 0)

        self.warning_label = _label()
        self.warning_label.set_no_show_all(True)
        self.warning_label.hide()
        self.pack_start(self.warning_label, False, False, 0)

        self.store = Gtk.TreeStore(str, str, str)
        self.tree_view = Gtk.TreeView(model=self.store)
        for index, title in enumerate(
            (_("Change"), _("Name"), _("ID"))
        ):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=index)
            column.set_resizable(True)
            if index == NAME_COLUMN:
                # An ellipsizing renderer reports a minimum width of almost
                # nothing, so only the column that should absorb the shortfall
                # gets one. Setting it on all three let every column collapse
                # to its minimum, and cut off the group headings, which sit in
                # column 0 and are longer than any leaf value in it.
                renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
                column.set_expand(True)
                column.set_min_width(NAME_MIN_WIDTH)
            self.tree_view.append_column(column)
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_shadow_type(Gtk.ShadowType.IN)
        self.scrolled.add(self.tree_view)
        _hide_until_needed(self.scrolled)
        self.pack_start(self.scrolled, True, True, 0)

        self.media_check = Gtk.CheckButton(label="")
        self.media_check.set_active(True)
        self.media_check.set_no_show_all(True)
        self.pack_start(self.media_check, False, False, 0)

        self.media_notice = _label()
        self.media_notice.set_margin_start(24)
        self.media_notice.set_no_show_all(True)
        self.media_notice.hide()
        self.pack_start(self.media_notice, False, False, 0)

    @property
    def transfer_media(self) -> bool:
        """Whether the user wants the missing media files moved."""
        return self.media_check.get_active()

    def prepare(self, session: SyncSession) -> None:
        """Render what ``session`` found, for the mode now selected."""
        self._session = session
        # A run with nothing but media to move has no mode to choose and no
        # object list to show, so neither is offered.
        self.mode_box.set_visible(bool(session.changes))
        self.scrolled.set_visible(bool(session.changes))
        self._render_media(session)
        self._render_changes()

    def _on_mode_toggled(self, button: Gtk.RadioButton, mode: int) -> None:
        """Re-render the list, because the mode reinterprets every row."""
        if not button.get_active():
            return
        self.sync_mode = mode
        self._render_changes()

    def _render_changes(self) -> None:
        """Rebuild the tree from the actions the selected mode produces."""
        self.store.clear()
        self.description_label.set_text(mode_description(self.sync_mode))
        session = self._session
        if session is None or not session.changes:
            self.warning_label.hide()
            return
        actions = changes_to_actions(session.changes, self.sync_mode)
        model = build_review(actions, session.db1, session.db2)
        self._fill(model)
        self._render_warning(model)

    def _fill(self, model: ReviewModel) -> None:
        """Write ``model`` into the tree store and expand the headings."""
        for destination in model.destinations:
            parent = self.store.append(
                None, [destination_label(destination.where, destination.count), "", ""]
            )
            for group in destination.groups:
                node = self.store.append(
                    parent, [verb_label(group.verb, group.count), "", ""]
                )
                for row in group.rows:
                    self.store.append(node, [row.type_label, row.name, row.gramps_id])
        self.tree_view.expand_all()

    def _render_warning(self, model: ReviewModel) -> None:
        """Show what will be deleted, if anything will be."""
        text = deletion_warning(model)
        if not text:
            self.warning_label.hide()
            return
        self.warning_label.set_markup(
            f"<b>{GLib.markup_escape_text(_('Warning:'))}</b> "
            f"{GLib.markup_escape_text(text)}"
        )
        self.warning_label.show()

    def _render_media(self, session: SyncSession) -> None:
        """Offer the media transfer, and name the files nothing can be done for."""
        if session.has_missing_files:
            self.media_check.set_label(
                media_label(len(session.missing_local), len(session.missing_remote))
            )
            self.media_check.show()
        else:
            self.media_check.hide()
        if session.missing_both:
            self.media_notice.set_markup(
                _dim(missing_both_notice(len(session.missing_both)))
            )
            self.media_notice.show()
        else:
            self.media_notice.hide()


class ResultPane(Gtk.Box):
    """Reports the outcome: a title, the error if there was one, and a summary."""

    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_valign(Gtk.Align.CENTER)

        self.title_label = _label(xalign=0.5)
        self.pack_start(self.title_label, False, False, 0)

        self.message_label = _label(xalign=0.5)
        self.pack_start(self.message_label, False, False, 0)

        self.summary_label = _label(xalign=0.5)
        self.pack_start(self.summary_label, False, False, 0)

        self.notice_label = _label(xalign=0.5)
        self.notice_label.set_no_show_all(True)
        self.notice_label.hide()
        self.pack_start(self.notice_label, False, False, 0)

        self.details = Gtk.Expander(label=_("Details"))
        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.details_label = _label()
        self.details_label.set_selectable(True)
        details_box.pack_start(self.details_label, False, False, 0)
        copy_button = Gtk.Button(label=_("Copy"))
        copy_button.set_halign(Gtk.Align.START)
        copy_button.connect("clicked", self._on_copy)
        details_box.pack_start(copy_button, False, False, 0)
        self.details.add(details_box)
        _hide_until_needed(self.details)
        self.pack_start(self.details, False, False, 0)

        self._details_text = ""

    def prepare(self, session: SyncSession) -> None:
        """Render the outcome of ``session``."""
        error = session.error
        if error is None:
            self.title_label.set_markup(
                f"<big><b>{GLib.markup_escape_text(_('Synchronization complete'))}"
                "</b></big>"
            )
            self.message_label.set_text("")
            self._set_details("")
        else:
            self.title_label.set_markup(
                f"<big><b>{GLib.markup_escape_text(_('Synchronization failed'))}"
                "</b></big>"
            )
            self.message_label.set_text(error_message(error.kind, error.detail))
            self._set_details(
                f"{error.kind.name}: {error.detail}"
                if error.detail
                else error.kind.name
            )
        self.summary_label.set_text(outcome_summary(session))

    def show_notice(self, message: str) -> None:
        """Show a non-fatal notice alongside the outcome."""
        self.notice_label.set_markup(f"<i>{GLib.markup_escape_text(message)}</i>")
        self.notice_label.show()

    def _set_details(self, text: str) -> None:
        """Offer the raw failure text, for pasting into a bug report."""
        self._details_text = text
        if text:
            self.details_label.set_text(text)
            self.details.show()
        else:
            self.details.hide()

    def _on_copy(self, _button) -> None:
        """Put the details on the clipboard."""
        from gi.repository import Gdk

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self._details_text, -1)


class GrampsWebSyncOptions(ToolOptions):
    """Options for Gramps Web Sync."""
