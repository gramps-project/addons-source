#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025      Doug Blank
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

"""
A Tab-triggered, live-filtering completion popover for a Gtk.TextView,
built on completion.get_completion_items().

Kept as a standalone controller (not part of GrampyScript.py's Gramplet
class) so it can be driven directly against a plain Gtk.TextView in
tests, independent of the full Gramps Gramplet machinery.

Wiring it into a host widget requires forwarding four things:
    textview "key-press-event"   -> controller.on_key_press(event)
                                     (if it returns True, treat the event
                                     as handled and stop further processing)
    buffer   "changed"           -> controller.on_buffer_changed()
    textview "button-press-event"/"focus-out-event" -> controller.close()
"""

import logging

from gi.repository import Gdk, Gtk

from completion import get_completion_items

_LOG = logging.getLogger(".GrampyScript.completion")

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
        `get_namespace`: zero-arg callable returning the current
        namespace dict for get_completion_items() (e.g.
        `lambda: build_namespace(self.dbstate.db)`); called fresh on
        every request so it always reflects the live database.
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
            # would leave GTK's own default handler to run instead (e.g.
            # inserting a literal tab character for Gdk.KEY_Tab), which
            # looks like "completion silently does nothing." Log and
            # fall back to "not handled" instead.
            _LOG.exception("completion on_key_press failed")
            self.close()
            return False

    def _on_key_press(self, event):
        keyval = event.keyval
        _LOG.debug("on_key_press keyval=%s open=%s", Gdk.keyval_name(keyval), self.is_open())
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
        it = self._cursor_iter()
        start = it.copy()
        if not start.backward_char():
            _LOG.debug("not completable: at start of buffer")
            return False
        ch = start.get_char()
        completable = ch.isalnum() or ch in "_.]"
        _LOG.debug("preceding char=%r completable=%s", ch, completable)
        return completable

    def _compute_items(self):
        source = self.buffer.get_text(
            self.buffer.get_start_iter(), self.buffer.get_end_iter(), True
        )
        line, column = self._cursor_line_column()
        prefix = self._word_prefix()
        _LOG.debug("computing completions at line=%s column=%s prefix=%r", line, column, prefix)
        try:
            namespace = self.get_namespace()
            items = get_completion_items(source, line, column, namespace)
        except Exception:
            _LOG.exception("building completion namespace/items failed")
            return []
        if not prefix.startswith("_"):
            items = [item for item in items if not item["name"].startswith("_")]
        _LOG.debug("found %d completion(s): %s", len(items), [i["name"] for i in items[:10]])
        if not items:
            _LOG.debug("zero completions, full source was:\n%s", source)
        return items

    def trigger(self):
        """Try to open the popover at the cursor. Returns True if it
        did (there was something completable to show)."""
        if not self._is_completable_context():
            return False
        items = self._compute_items()
        if not items:
            _LOG.debug("trigger: no completions, falling back to default Tab behavior")
            return False
        self.items = items
        self.selected_index = 0
        self._open_popover()
        return True

    def refresh(self):
        """Recompute matches for an already-open popover, following the
        cursor as the user keeps typing. Closes if nothing matches
        anymore."""
        if not self._is_completable_context():
            self.close()
            return
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
        self.selected_index = max(0, min(len(self.items) - 1, self.selected_index + delta))
        self._update_row_selection()

    def accept(self):
        if self.items:
            item = self.items[self.selected_index]
            self.buffer.insert(self._cursor_iter(), item["complete"])
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
