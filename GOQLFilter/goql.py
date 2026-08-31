#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       Douglas Blank
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

"""Gramplets providing a gramps-object-query-language (GOQL) filter for each
primary object view: a multi-line text area for a where-expression plus
Find / Reset / Define filter buttons, the same shape as core's sidebar
filters.

"Find" compiles the expression, wraps it in a real ``GenericFilter`` (a
one-rule filter whose rule evaluates the compiled GOQL ``where`` AST via
``evaluate_where``), and drops it straight into ``view.generic_filter`` --
the exact mechanism ``plugins/gramplet/filter.py`` uses for the built-in
rule-based sidebar filters, just fed from a compiled expression instead of a
rule-picker widget. "Define filter" hands the same expression to Gramps'
own ``EditFilter`` dialog as a single ``MatchesExpression`` rule (see
``whereexprrule.py``), so it can be named and saved as an ordinary Custom
Filter -- reusable anywhere a Custom Filter is, not just in this gramplet.

The text area is a plain ``Enter``-inserts-a-newline ``Gtk.TextView`` (not a
``Gtk.Entry``) since where-expressions with ``and``/``or`` read better over
several lines; ``Ctrl+Return`` runs Find instead. Up/Down at the first/last
line of the buffer recall previous expressions from an in-memory,
per-gramplet-instance history (session-scoped -- not persisted to disk),
the same first/last-line-aware convention multiline REPL inputs use so
plain cursor movement inside a multi-line expression still works.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import logging
import time
from typing import Any

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
import warnings

with warnings.catch_warnings():
    # PyGObject warns on *import* of GLib -- not on use -- when the
    # underlying GLib build has moved unix_signal_add_full() to GLibUnix
    # (GLib >= 2.88). This addon never calls that function; the warning is
    # just noise from gi's override machinery. See
    # https://gitlab.gnome.org/GNOME/pygobject/-/work_items/757
    warnings.filterwarnings(
        "ignore", message=".*unix_signal_add_full.*", category=DeprecationWarning
    )
    from gi.repository import Gdk, GLib, Gtk

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.filters import (
    CustomFilters,
    GenericFilterFactory,
    reload_custom_filters,
)
from gramps.gui.display import display_help, display_url
from gramps.gui.editors import EditFilter

# -------------------------------------------------------------------------
#
# gramps-object-query-language modules (vendored -- see
# gramps_object_query_language_copy/, a bundled copy of the
# gramps-object-query-language PyPI package. This gramps60 branch of the
# addon vendors it rather than relying on `pip install
# gramps-object-query-language` -- see gramps_object_query_language_copy/
# for why (pip installs of pure-Python addon dependencies are unreliable
# across the various AIO installers on Gramps 6.0).
#
# -------------------------------------------------------------------------
from gramps_object_query_language_copy.query_lang import QueryLangError, compile_expr

from whereexprrule import (
    CitationMatchesExpression,
    EventMatchesExpression,
    FamilyMatchesExpression,
    MediaMatchesExpression,
    NoteMatchesExpression,
    PersonMatchesExpression,
    PlaceMatchesExpression,
    RepositoryMatchesExpression,
    SourceMatchesExpression,
)
from goql_completion_popup import CompletionController
from goql_highlight import classify_tokens

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

LOG = logging.getLogger(".GOQLFilter")

# Minimum pixel height for the text area's scrolled window -- a floor, not
# the actual displayed size (the Paned in init() splits editor/buttons ~50%
# of whatever space is actually available; this just keeps the editor from
# collapsing to something unreadable if the user drags the divider all the
# way down). Not computed from font metrics (needs a realized widget), just
# a reasonable fixed default.
TEXT_AREA_HEIGHT = 90

# Cap on saved history entries -- self.gui.data round-trips through the
# gramplet's saved placement config (an .ini file) on every save, so an
# unbounded history would keep growing that file forever.
HISTORY_MAX_ENTRIES = 50

# Foreground colors for goql_highlight.classify_tokens' categories -- muted,
# mid-tone hex values chosen to stay legible on both light and dark GTK
# themes, since a plain Gtk.TextView has no adaptive-theme color mechanism
# to hook into (no runtime dark/light detection here).
HIGHLIGHT_COLORS = {
    "keyword": "#7C3AED",
    "string": "#15803D",
    "number": "#B45309",
    "constant-class": "#BE185D",
    "operator": "#6B7280",
}


def _icon_button(icon_name, label_text):
    """A ``Gtk.Button`` with an icon beside its label.

    Same construction ``_sidebarfilter.py``'s ``_init_interface`` uses for
    its own "Reset" button (``edit-undo`` + label in an ``Gtk.Box``) --
    matched here for a consistent look, and reused for "Help".
    """
    button = Gtk.Button()
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    image = Gtk.Image()
    image.set_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
    box.pack_start(image, False, False, 0)
    box.pack_start(Gtk.Label(label=label_text), False, True, 0)
    button.add(box)
    return button


# -------------------------------------------------------------------------
#
# QueryFilter
#
# -------------------------------------------------------------------------
class QueryFilter(Gramplet):
    """Base class for all GOQL filter gramplets."""

    NAMESPACE: str = ""  # e.g. "Person"; set by subclass
    RULE_CLASS: Any = None  # e.g. PersonMatchesExpression; set by subclass

    def init(self):
        self.history = []
        self.history_index = None  # None == live/current input, not browsing
        self.history_draft = ""  # the not-yet-submitted text, saved on history-back

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_monospace(True)
        self.text_buffer = self.text_view.get_buffer()
        self.text_view.set_tooltip_text(
            _("A gramps-object-query-language where-expression, e.g.\n")
            + "gender == Person.MALE and 'Anderson' in primary_name.surname\n\n"
            + _("Enter inserts a newline; Ctrl+Enter runs Find.\n")
            + _("Up/Down at the first/last line recalls previous expressions.\n")
            + _("Tab always completes -- it never inserts a tab character.")
        )
        for tag_name, color in HIGHLIGHT_COLORS.items():
            self.text_buffer.create_tag(tag_name, foreground=color)

        self.completion = CompletionController(
            self.text_view, get_namespace=lambda: self.NAMESPACE
        )
        self.text_view.connect("key-press-event", self._on_key_press)
        self.text_buffer.connect("changed", self._on_text_changed)
        self.text_view.connect("button-press-event", self._on_textview_defocus)
        self.text_view.connect("focus-out-event", self._on_textview_defocus)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.set_min_content_height(TEXT_AREA_HEIGHT)
        scroller.add(self.text_view)

        # Reminds the user this expression's fields are specific to this
        # view -- e.g. "gender" compiles here but not in the Family filter.
        namespace_label = Gtk.Label()
        namespace_label.set_markup(
            "<b>%s</b>" % GLib.markup_escape_text(_("%s filter") % _(self.NAMESPACE))
        )
        namespace_label.set_xalign(0)

        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        editor_box.pack_start(namespace_label, False, False, 0)
        editor_box.pack_start(scroller, True, True, 0)

        # Same button shapes/icons as the built-in rule-based sidebar filter
        # (`gui/filters/sidebar/_sidebarfilter.py`'s `_init_interface`): a
        # plain mnemonic "Find" button, an icon+label "Reset", plain-text
        # "Define filter", grouped into two ButtonBox rows the same way.
        find_button = Gtk.Button.new_with_mnemonic(_("_Find"))
        find_button.set_tooltip_text(
            _("This updates the view with the current filter parameters.")
        )
        find_button.connect("clicked", self.find_clicked)

        reset_button = _icon_button("edit-undo", _("Reset"))
        reset_button.set_tooltip_text(
            _("This resets the filter parameters to empty state.")
        )
        reset_button.connect("clicked", self.reset_clicked)

        define_button = Gtk.Button(label=_("Define filter"))
        define_button.set_tooltip_text(
            _("This opens a dialog to save the current expression as a named filter.")
        )
        define_button.connect("clicked", self.define_clicked)

        help_button = _icon_button("help-browser", _("Help"))
        help_button.set_tooltip_text(_("Open this gramplet's help page in a browser."))
        help_button.connect("clicked", self.help_clicked)

        self.msg_label = Gtk.Label(label="")
        self.msg_label.set_line_wrap(True)
        self.msg_label.set_xalign(0)

        action_row = Gtk.ButtonBox()
        action_row.set_layout(Gtk.ButtonBoxStyle.START)
        action_row.set_spacing(6)
        action_row.add(find_button)
        action_row.add(reset_button)

        secondary_row = Gtk.ButtonBox()
        secondary_row.set_layout(Gtk.ButtonBoxStyle.START)
        secondary_row.set_spacing(6)
        secondary_row.add(define_button)
        secondary_row.add(help_button)

        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        bottom_box.pack_start(action_row, False, False, 0)
        bottom_box.pack_start(secondary_row, False, False, 0)
        bottom_box.pack_start(self.msg_label, False, False, 0)

        # A Paned (same widget core's own gui/views/pageview.py uses for its
        # sidebar/main-content split) rather than a plain Box with
        # expand=True on the scroller: a Box has no notion of "50% of
        # whatever's available," only "give the expanding child all
        # leftover space" -- the text area would end up taller than half
        # the gramplet on any reasonably tall placement. A Paned's handle
        # is also user-draggable afterward, which a fixed split wouldn't be.
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.paned.set_border_width(6)
        self.paned.pack1(editor_box, True, True)
        self.paned.pack2(bottom_box, False, True)
        self._paned_position_set = False
        self.paned.connect("size-allocate", self._init_paned_position)

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.paned)
        self.paned.show_all()

    def _init_paned_position(self, widget, allocation):
        """Split the editor/buttons area ~50/50 the first time this pane is
        actually sized.

        ``Gtk.Paned`` has no percentage-based position, only pixels, and
        the real allocated height isn't known until the widget is
        realized -- so this can't just be set once up front in ``init()``.
        Runs exactly once (``self._paned_position_set``): after that, the
        divider is the user's own drag to keep, not something to keep
        resetting back to 50% on every later resize.
        """
        if self._paned_position_set or allocation.height <= 1:
            return
        widget.set_position(allocation.height // 2)
        self._paned_position_set = True

    def on_load(self):
        """Restore history saved by a previous session.

        Called once, right after ``init()``, with ``self.gui.data`` already
        populated from this gramplet's saved placement config (an .ini
        file) -- the same mechanism core gramplets like
        ``pedigreegramplet.py`` use for their own persisted options. Each
        gramplet *instance* (Person filter, Family filter, ...) has its own
        ``self.gui.data``, so histories stay independent automatically.
        """
        self.history = [str(item) for item in self.gui.data]

    def on_save(self):
        """Called on app/view shutdown, before ``self.gui.data`` is written
        to disk -- see ``GrampletBar.on_delete``.
        """
        self.gui.data = list(self.history)

    def _on_text_changed(self, _buffer):
        self._apply_highlighting()
        self.completion.on_buffer_changed()

    def _on_textview_defocus(self, _widget, _event):
        """Close the completion popover on a click or focus-out -- shared
        handler for both signals (``button-press-event``,
        ``focus-out-event``), matching ``GrampyScript.py``'s
        ``on_textview_click``/``on_editor_focus_out``. Never consumes the
        event: a click still needs to move the cursor normally.
        """
        self.completion.close()
        return False

    def _apply_highlighting(self):
        start, end = self.text_buffer.get_bounds()
        for tag_name in HIGHLIGHT_COLORS:
            self.text_buffer.remove_tag_by_name(tag_name, start, end)
        source = self.text_buffer.get_text(start, end, False)
        for start_line, start_col, end_line, end_col, category in classify_tokens(
            source
        ):
            start_iter = self.text_buffer.get_iter_at_line_offset(start_line, start_col)
            end_iter = self.text_buffer.get_iter_at_line_offset(end_line, end_col)
            self.text_buffer.apply_tag_by_name(category, start_iter, end_iter)

    def _get_expr_text(self):
        start, end = self.text_buffer.get_bounds()
        return self.text_buffer.get_text(start, end, False).strip()

    def _set_expr_text(self, text):
        self.text_buffer.set_text(text)
        self.text_buffer.place_cursor(self.text_buffer.get_end_iter())

    def _set_message(self, text):
        self.msg_label.set_text(text)

    def _run_with_filter_progress(self, action):
        """Run ``action()`` with Gramps' own filter-application phase
        timings routed into this gramplet's message area, mirroring
        ``gui/filters/sidebar/_sidebarfilter.py``'s ``clicked()``.

        ``GenericFilter.apply()`` (``gen/filters/_genericfilter.py``)
        already reports "Prepare time: Xs" / "Apply time: Ys" via
        ``user.notify(...)`` on every call -- but ``User._gui_print``
        (``gui/user.py``) only routes that to a widget if
        ``uistate.filter_print_func`` is set; otherwise it falls through to
        stdout, which is exactly why those lines showed up in a terminal
        instead of this gramplet. Returns the collected phase messages.
        """
        phase_msgs = []

        def pump_events():
            while Gtk.events_pending():
                Gtk.main_iteration()

        def live_print(msg):
            phase_msgs.append(msg)
            self._set_message("\n".join(phase_msgs))
            pump_events()

        def live_step():
            pump_events()

        self.uistate.filter_print_func = live_print
        self.uistate.filter_step_func = live_step
        self.uistate.set_busy_cursor(True)
        try:
            action()
        finally:
            self.uistate.filter_print_func = None
            self.uistate.filter_step_func = None
            self.uistate.set_busy_cursor(False)
        return phase_msgs

    def _filter_method_label(self, gfilter):
        """ "SQL" if any rule in ``gfilter`` resolved a precomputed match set
        (``MatchesExpression.prepare`` sets ``selected_handles`` only when
        it pushed the expression down to SQL), else "Python evaluation".
        """
        for rule in gfilter.get_rules():
            if getattr(rule, "selected_handles", None) is not None:
                return _("SQL")
        return _("Python evaluation")

    def _remember_history(self, expr):
        """Append ``expr`` to history, skipping an immediate repeat."""
        if expr and (not self.history or self.history[-1] != expr):
            self.history.append(expr)
            del self.history[:-HISTORY_MAX_ENTRIES]
        self.history_index = None

    def _history_back(self):
        if not self.history:
            return
        if self.history_index is None:
            self.history_draft = self._get_expr_text()
            self.history_index = len(self.history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        else:
            return  # already at the oldest entry
        self._set_expr_text(self.history[self.history_index])

    def _history_forward(self):
        if self.history_index is None:
            return  # not browsing
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._set_expr_text(self.history[self.history_index])
        else:
            self.history_index = None
            self._set_expr_text(self.history_draft)

    def _on_key_press(self, _widget, event):
        # Completion first: when its popover is open, Up/Down/Enter/Escape
        # navigate/accept/dismiss it rather than falling through to history
        # navigation or a newline below -- see CompletionController's own
        # key-press dispatch.
        if self.completion.on_key_press(event):
            return True

        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)

        if event.keyval == Gdk.KEY_Tab:
            # Tab is always completion, never a literal tab/space insert:
            # self.completion.on_key_press already tried above and
            # returned False here only because there was nothing
            # completable -- still consume the key rather than falling
            # back to GTK's default (inserting a tab character).
            return True

        if ctrl and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.find_clicked(_widget)
            return True  # don't also insert a newline

        if not ctrl and event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down):
            cursor = self.text_buffer.get_iter_at_mark(self.text_buffer.get_insert())
            at_first_line = cursor.get_line() == 0
            at_last_line = cursor.get_line() == self.text_buffer.get_line_count() - 1
            if event.keyval == Gdk.KEY_Up and at_first_line:
                self._history_back()
                return True
            if event.keyval == Gdk.KEY_Down and at_last_line:
                self._history_forward()
                return True

        return False  # let GTK handle it normally

    def _hide_quick_search_bar(self):
        """Close the view's own quick-search bar, if open.

        ``ListView.build_tree()`` only reads ``generic_filter`` when its
        quick-search bar (the small text-search box built into every list
        view, independent of this gramplet) is hidden -- otherwise it uses
        *that* bar's own filter instead and ``generic_filter`` is silently
        ignored. The bar auto-hides when the view's Sidebar pane is toggled
        on, but this gramplet may just as well be docked in the bottombar,
        so hide it explicitly rather than depending on where the user put
        the gramplet.
        """
        search_bar = getattr(self.gui.view, "search_bar", None)
        if search_bar is not None and search_bar.is_visible():
            search_bar.hide()

    def _build_generic_filter(self, expr):
        """A ``GenericFilter`` for ``expr``, or ``None`` if it fails to compile.

        Validates ``expr`` up front so a bad expression reports a clear error
        here rather than silently matching nothing -- ``RULE_CLASS.prepare()``
        recompiles it a second time when the filter is applied, since a
        ``Rule`` only ever receives its arguments as plain strings.
        """
        try:
            compile_expr(self.NAMESPACE, expr)
        except QueryLangError as err:
            self._set_message(str(err))
            return None
        gfilter = GenericFilterFactory(self.NAMESPACE)()
        gfilter.add_rule(self.RULE_CLASS([expr]))
        return gfilter

    def find_clicked(self, _obj):
        expr = self._get_expr_text()
        self._set_message("")
        if not expr:
            self.reset_clicked(_obj)
            return
        gfilter = self._build_generic_filter(expr)
        if gfilter is None:
            return
        self._remember_history(expr)
        phase_msgs = []
        try:
            self._hide_quick_search_bar()
            self.gui.view.generic_filter = gfilter

            def do_build_tree():
                self.gui.view.build_tree()

            phase_msgs = self._run_with_filter_progress(do_build_tree)
        except Exception as err:  # never let a click silently fail
            LOG.exception("GOQL Filter gramplet: Find failed")
            self._set_message(_("Error applying filter: %s") % err)
            return
        model = self.gui.view.model
        summary = _("Showing %(shown)d of %(total)d (%(method)s)") % {
            "shown": model.displayed(),
            "total": model.total(),
            "method": self._filter_method_label(gfilter),
        }
        self._set_message("\n".join(phase_msgs + [summary]))

    def reset_clicked(self, _obj):
        self._set_expr_text("")
        try:
            self._hide_quick_search_bar()
            self.gui.view.generic_filter = None
            self.gui.view.build_tree()
        except Exception as err:
            LOG.exception("GOQL Filter gramplet: Reset failed")
            self._set_message(_("Error resetting filter: %s") % err)
            return
        self._set_message("")

    def define_clicked(self, _obj):
        expr = self._get_expr_text()
        if not expr:
            self._set_message(_("Enter an expression first"))
            return
        try:
            compile_expr(self.NAMESPACE, expr)
        except QueryLangError as err:
            self._set_message(str(err))
            return
        self._set_message("")
        self._remember_history(expr)

        gfilter = GenericFilterFactory(self.NAMESPACE)()
        gfilter.add_rule(self.RULE_CLASS([expr]))
        comment = _("Created by the GOQL Filter gramplet on {today}").format(
            today=time.strftime("%Y-%m-%d", time.localtime())
        )
        gfilter.set_comment(comment)

        EditFilter(
            self.NAMESPACE,
            self.dbstate,
            self.uistate,
            [],
            gfilter,
            CustomFilters,
            selection_callback=self._filter_defined,
        )

    def _filter_defined(self, filterdb, _filter_name):
        filterdb.save()
        reload_custom_filters()
        self.uistate.emit("filters-changed", (self.NAMESPACE,))

    def help_clicked(self, _obj):
        """Open this gramplet's registered ``help_url`` in a browser.

        ``self.gui.help_url`` is set from the ``.gpr.py`` registration's
        ``help_url=`` (``GuiGramplet.__init__``, ``gui/widgets/
        grampletpane.py``) -- the same attribute the built-in "Help" menu
        item on every gramplet tab already reads, via the same
        ``http(s)://`` vs. wiki-page-name dispatch used there
        (``grampletpane.py``/``grampletbar.py``'s own right-click "Help").
        """
        help_url = getattr(self.gui, "help_url", None)
        if not help_url:
            return
        if help_url.startswith(("http://", "https://")):
            display_url(help_url)
        else:
            display_help(help_url)


# -------------------------------------------------------------------------
#
# Per-type gramplets
#
# -------------------------------------------------------------------------
class PersonQueryFilter(QueryFilter):
    NAMESPACE = "Person"
    RULE_CLASS = PersonMatchesExpression


class FamilyQueryFilter(QueryFilter):
    NAMESPACE = "Family"
    RULE_CLASS = FamilyMatchesExpression


class EventQueryFilter(QueryFilter):
    NAMESPACE = "Event"
    RULE_CLASS = EventMatchesExpression


class PlaceQueryFilter(QueryFilter):
    NAMESPACE = "Place"
    RULE_CLASS = PlaceMatchesExpression


class RepositoryQueryFilter(QueryFilter):
    NAMESPACE = "Repository"
    RULE_CLASS = RepositoryMatchesExpression


class SourceQueryFilter(QueryFilter):
    NAMESPACE = "Source"
    RULE_CLASS = SourceMatchesExpression


class CitationQueryFilter(QueryFilter):
    NAMESPACE = "Citation"
    RULE_CLASS = CitationMatchesExpression


class MediaQueryFilter(QueryFilter):
    NAMESPACE = "Media"
    RULE_CLASS = MediaMatchesExpression


class NoteQueryFilter(QueryFilter):
    NAMESPACE = "Note"
    RULE_CLASS = NoteMatchesExpression
