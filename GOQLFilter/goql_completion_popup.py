#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025      Doug Blank
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

"""A Tab-triggered, live-filtering completion popover for a ``Gtk.TextView``.

Vendored from the ``GrampyScript`` addon's ``completion_popup.py``
(``CompletionController``), which is deliberately GTK-only and
completion-source-agnostic already -- its own docstring says it's "kept as
a standalone controller... so it can be driven directly against a plain
Gtk.TextView", touching its jedi-based backend through exactly one import
(``from completion import get_completion_items``). That's the only line
changed here: swapped for ``goql_completion``'s namespace-aware, non-jedi
source (see that module's docstring for why a where-expression can't reuse
GrampyScript's actual completion engine, only its popup).

Named differently from GrampyScript's own ``completion_popup.py``/
``completion.py`` on purpose -- if both addons are ever installed at once,
Gramps' plugin loader puts each addon's own directory on ``sys.path``, and
a bare ``import completion_popup`` here could resolve to whichever one
happened to be imported first instead of this file (the same
namespace-collision hazard as Mantis 12691, just at the addon-to-addon
level instead of within one addon).

Two further deltas from the vendored original, both because this editor's
Tab key has no fallback behavior to protect (GrampyScript's Tab inserts 4
spaces when nothing is completable; this one never inserts anything):

- ``_is_completable_context`` always returns True here -- GrampyScript
  gates completion on the preceding character (alnum/``_``/``.``/``]``) so
  Tab's whitespace-insert fallback doesn't fire in a confusing spot; this
  editor has no such fallback to protect, and "Tab on an empty buffer
  shows every top-level name for the current namespace" is exactly the
  wanted behavior, not an edge case to guard against.
- Callers are expected to unconditionally consume ``Gdk.KEY_Tab``
  themselves (return ``True``) regardless of what ``on_key_press`` reports,
  rather than falling back to inserting a tab character the way
  GrampyScript's own key handler does.

Wiring it into a host widget requires forwarding four things:
    textview "key-press-event"   -> controller.on_key_press(event)
                                     (if it returns True, treat the event
                                     as handled and stop further processing)
    buffer   "changed"           -> controller.on_buffer_changed()
    textview "button-press-event"/"focus-out-event" -> controller.close()
"""

import logging

from gi.repository import Gdk, Gtk

from goql_completion import get_completion_items

_LOG = logging.getLogger(".GOQLFilter.completion")

_NAVIGATION_KEYS = (
    Gdk.KEY_Left,
    Gdk.KEY_Right,
    Gdk.KEY_Home,
    Gdk.KEY_End,
    Gdk.KEY_Page_Up,
    Gdk.KEY_Page_Down,
)


class CompletionController:
    def __init__(self, textview, get_namespace):
        """
        `textview`: the Gtk.TextView to attach completion to.
        `get_namespace`: zero-arg callable returning the current GOQL
        namespace string ("Person", "Family", ...) for
        `get_completion_items()`; called fresh on every request so it
        always reflects whichever gramplet/rule this controller is
        attached to.
        """
        self.textview = textview
        self.buffer = textview.get_buffer()
        self.get_namespace = get_namespace
        self.popover = None
        self.listbox = None
        self.scrolled = None
        self.items = []
        self.selected_index = 0

    # ---- public event entry points -----------------------------------

    def on_key_press(self, event):
        """Return True if the event was consumed and should not be
        processed any further by the caller."""
        try:
            return self._on_key_press(event)
        except Exception:
            # Never let a bug here swallow the keypress entirely -- that
            # would leave GTK's own default handler to run instead, which
            # looks like "completion silently does nothing." Log and fall
            # back to "not handled" instead.
            _LOG.exception("completion on_key_press failed")
            self.close()
            return False

    def _on_key_press(self, event):
        keyval = event.keyval
        _LOG.debug(
            "on_key_press keyval=%s open=%s", Gdk.keyval_name(keyval), self.is_open()
        )
        if keyval == Gdk.KEY_Tab:
            if self.is_open():
                self.accept()
                return True
            return self.trigger()
        if self.is_open():
            if keyval == Gdk.KEY_Up:
                self.move_selection(-1)
                return True
            if keyval == Gdk.KEY_Down:
                self.move_selection(1)
                return True
            if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
                self.accept()
                return True
            if keyval == Gdk.KEY_Escape:
                self.close()
                return True
            if keyval in _NAVIGATION_KEYS:
                # The cursor is about to move out from under the popover;
                # let it move normally, just stop completing at this spot.
                self.close()
                return False
        return False

    def on_buffer_changed(self):
        if not self.is_open():
            return
        try:
            self.refresh()
        except Exception:
            _LOG.exception("completion refresh failed")
            self.close()

    def is_open(self):
        return self.popover is not None

    # ---- core -----------------------------------------------------------

    def _cursor_iter(self):
        return self.buffer.get_iter_at_mark(self.buffer.get_insert())

    def _cursor_line_column(self):
        it = self._cursor_iter()
        return it.get_line() + 1, it.get_line_offset()

    def _word_prefix(self):
        it = self._cursor_iter()
        start = it.copy()
        while start.backward_char():
            ch = start.get_char()
            if ch.isalnum() or ch == "_":
                continue
            start.forward_char()
            break
        return self.buffer.get_text(start, it, True)

    def _is_completable_context(self):
        # Always True here -- see this module's docstring for why, unlike
        # GrampyScript's version, this editor has no whitespace-insert
        # fallback to protect Tab from firing into.
        return True

    def _compute_items(self):
        source = self.buffer.get_text(
            self.buffer.get_start_iter(), self.buffer.get_end_iter(), True
        )
        line, column = self._cursor_line_column()
        prefix = self._word_prefix()
        _LOG.debug(
            "computing completions at line=%s column=%s prefix=%r", line, column, prefix
        )
        try:
            namespace = self.get_namespace()
            items = get_completion_items(source, line, column, namespace)
        except Exception:
            _LOG.exception("building completion items failed")
            return []
        if not prefix.startswith("_"):
            items = [item for item in items if not item["name"].startswith("_")]
        _LOG.debug(
            "found %d completion(s): %s", len(items), [i["name"] for i in items[:10]]
        )
        return items

    def trigger(self):
        """Try to complete at the cursor. Returns True if there was
        something completable to show. A single match is inserted
        directly instead of opening a popover with one row in it;
        multiple matches open the popover as usual."""
        if not self._is_completable_context():
            return False
        items = self._compute_items()
        if not items:
            _LOG.debug("trigger: no completions")
            return False
        self.items = items
        self.selected_index = 0
        if len(items) == 1:
            _LOG.debug(
                "trigger: single match, inserting directly: %s", items[0]["name"]
            )
            self.accept()
            return True
        self._open_popover()
        return True

    def refresh(self):
        """Recompute matches for an already-open popover, following the
        cursor as the user keeps typing. Closes if nothing matches
        anymore."""
        items = self._compute_items()
        if not items:
            self.close()
            return
        self.items = items
        self.selected_index = min(self.selected_index, len(items) - 1)
        self._rebuild_listbox()
        self._reposition()

    def move_selection(self, delta):
        if not self.items:
            return
        self.selected_index = max(
            0, min(len(self.items) - 1, self.selected_index + delta)
        )
        self._update_row_selection()

    def accept(self):
        if self.items:
            item = self.items[self.selected_index]
            self.buffer.insert(self._cursor_iter(), item["complete"])
            offset = item.get("cursor_offset", 0)
            if offset:
                it = self._cursor_iter()
                it.backward_chars(offset)
                self.buffer.place_cursor(it)
        self.close()

    def close(self):
        if self.popover is not None:
            self.popover.destroy()
        self.popover = None
        self.listbox = None
        self.scrolled = None
        self.items = []
        self.selected_index = 0

    # ---- widget building --------------------------------------------------

    def _open_popover(self):
        self.popover = Gtk.Popover()
        self.popover.set_relative_to(self.textview)
        self.popover.set_modal(False)
        self.popover.set_position(Gtk.PositionType.BOTTOM)

        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_max_content_height(200)
        self.scrolled.set_propagate_natural_height(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_activate_on_single_click(True)
        self.listbox.connect("row-activated", self._on_row_activated)
        self.scrolled.add(self.listbox)
        self.popover.add(self.scrolled)

        self._rebuild_listbox()
        self.popover.show_all()
        self._reposition()
        self.popover.popup()

    def _rebuild_listbox(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        for item in self.items:
            label = Gtk.Label(label=item["name"], xalign=0)
            label.set_margin_start(6)
            label.set_margin_end(6)
            row = Gtk.ListBoxRow()
            row.add(label)
            self.listbox.add(row)
        self.listbox.show_all()
        self._update_row_selection()

    def _update_row_selection(self):
        row = self.listbox.get_row_at_index(self.selected_index)
        if row is not None:
            self.listbox.select_row(row)
            self._scroll_to_row(row)

    def _scroll_to_row(self, row):
        alloc = row.get_allocation()
        adj = self.scrolled.get_vadjustment()
        if alloc.y < adj.get_value():
            adj.set_value(alloc.y)
        elif alloc.y + alloc.height > adj.get_value() + adj.get_page_size():
            adj.set_value(alloc.y + alloc.height - adj.get_page_size())

    def _reposition(self):
        rect = self.textview.get_iter_location(self._cursor_iter())
        x, y = self.textview.buffer_to_window_coords(
            Gtk.TextWindowType.WIDGET, rect.x, rect.y
        )
        pointing = Gdk.Rectangle()
        pointing.x = x
        pointing.y = y
        pointing.width = 1
        pointing.height = rect.height
        self.popover.set_pointing_to(pointing)

    def _on_row_activated(self, listbox, row):
        self.selected_index = row.get_index()
        self.accept()
