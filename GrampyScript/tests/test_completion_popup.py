"""
Tests for completion_popup.py — the Tab-triggered completion popover.

Needs a real (possibly virtual, e.g. Xvfb) display since it builds real
Gtk widgets (Gtk.Popover, Gtk.ListBox) and asks for their allocation.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from completion_popup import CompletionController


class _FakeEvent:
    def __init__(self, keyval):
        self.keyval = keyval


def _make_controller(text, cursor_offset=None, namespace=None):
    textview = Gtk.TextView()
    buffer = textview.get_buffer()
    buffer.set_text(text)
    if cursor_offset is None:
        cursor_offset = len(text)
    buffer.place_cursor(buffer.get_iter_at_offset(cursor_offset))

    # A real (offscreen) top-level window so widgets can be allocated --
    # Gtk.Popover needs a realized relative_to widget to compute a
    # position against.
    window = Gtk.Window()
    window.add(textview)
    window.set_default_size(400, 300)
    window.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()

    controller = CompletionController(textview, get_namespace=lambda: namespace or {})
    return controller, buffer, window


class TestTriggerAndClose(unittest.TestCase):
    def test_trigger_opens_for_completable_context(self):
        controller, buffer, window = _make_controller("active_person.")
        opened = controller.trigger()
        self.assertTrue(opened)
        self.assertTrue(controller.is_open())
        names = [item["name"] for item in controller.items]
        self.assertIn("primary_name", names)
        window.destroy()

    def test_trigger_does_not_open_after_whitespace(self):
        controller, buffer, window = _make_controller("x = 1 ")
        opened = controller.trigger()
        self.assertFalse(opened)
        self.assertFalse(controller.is_open())
        window.destroy()

    def test_trigger_does_not_open_on_empty_buffer(self):
        controller, buffer, window = _make_controller("")
        opened = controller.trigger()
        self.assertFalse(opened)
        window.destroy()

    def test_close_resets_state(self):
        controller, buffer, window = _make_controller("active_person.")
        controller.trigger()
        controller.close()
        self.assertFalse(controller.is_open())
        self.assertEqual(controller.items, [])
        self.assertEqual(controller.selected_index, 0)
        window.destroy()


class TestAccept(unittest.TestCase):
    def test_accept_inserts_missing_suffix_only(self):
        controller, buffer, window = _make_controller("active_person.primary_")
        controller.trigger()
        # first match should be primary_name (only dynamic key matching)
        names = [item["name"] for item in controller.items]
        self.assertEqual(names, ["primary_name"])
        controller.accept()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.assertEqual(text, "active_person.primary_name")
        self.assertFalse(controller.is_open())
        window.destroy()

    def test_accept_with_no_items_just_closes(self):
        controller, buffer, window = _make_controller("active_person.")
        controller.trigger()
        controller.items = []
        controller.accept()
        self.assertFalse(controller.is_open())
        window.destroy()


class TestNavigation(unittest.TestCase):
    def test_move_selection_clamped(self):
        controller, buffer, window = _make_controller("active_person.")
        controller.trigger()
        n = len(controller.items)
        self.assertGreater(n, 1)
        controller.move_selection(-1)
        self.assertEqual(controller.selected_index, 0)
        controller.move_selection(10**6)
        self.assertEqual(controller.selected_index, n - 1)
        controller.move_selection(-(10**6))
        self.assertEqual(controller.selected_index, 0)
        window.destroy()


class TestOnKeyPress(unittest.TestCase):
    def test_tab_opens_then_accepts(self):
        controller, buffer, window = _make_controller("active_person.primary_")
        consumed = controller.on_key_press(_FakeEvent(Gdk.KEY_Tab))
        self.assertTrue(consumed)
        self.assertTrue(controller.is_open())

        consumed = controller.on_key_press(_FakeEvent(Gdk.KEY_Tab))
        self.assertTrue(consumed)
        self.assertFalse(controller.is_open())
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.assertEqual(text, "active_person.primary_name")
        window.destroy()

    def test_tab_falls_through_when_nothing_completable(self):
        controller, buffer, window = _make_controller("x = 1 ")
        consumed = controller.on_key_press(_FakeEvent(Gdk.KEY_Tab))
        self.assertFalse(consumed)  # caller should fall back to inserting spaces
        window.destroy()

    def test_arrow_keys_only_consumed_while_open(self):
        controller, buffer, window = _make_controller("active_person.")
        self.assertFalse(controller.on_key_press(_FakeEvent(Gdk.KEY_Down)))
        controller.trigger()
        self.assertTrue(controller.on_key_press(_FakeEvent(Gdk.KEY_Down)))
        self.assertEqual(controller.selected_index, 1)
        window.destroy()

    def test_escape_closes_and_is_consumed(self):
        controller, buffer, window = _make_controller("active_person.")
        controller.trigger()
        consumed = controller.on_key_press(_FakeEvent(Gdk.KEY_Escape))
        self.assertTrue(consumed)
        self.assertFalse(controller.is_open())
        window.destroy()

    def test_left_right_close_but_are_not_consumed(self):
        controller, buffer, window = _make_controller("active_person.")
        controller.trigger()
        consumed = controller.on_key_press(_FakeEvent(Gdk.KEY_Left))
        self.assertFalse(consumed)  # cursor movement must still happen
        self.assertFalse(controller.is_open())
        window.destroy()

    def test_return_accepts_only_while_open(self):
        controller, buffer, window = _make_controller("active_person.primary_")
        # popover not open: Return must not be swallowed (newline/apply-script bindings)
        self.assertFalse(controller.on_key_press(_FakeEvent(Gdk.KEY_Return)))
        controller.trigger()
        self.assertTrue(controller.on_key_press(_FakeEvent(Gdk.KEY_Return)))
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.assertEqual(text, "active_person.primary_name")
        window.destroy()


class TestLiveRefresh(unittest.TestCase):
    def test_refresh_narrows_as_more_is_typed(self):
        controller, buffer, window = _make_controller("active_person.")
        controller.trigger()
        self.assertGreater(len(controller.items), 1)

        it = buffer.get_iter_at_mark(buffer.get_insert())
        buffer.insert(it, "primary_")
        controller.on_buffer_changed()
        names = [item["name"] for item in controller.items]
        self.assertEqual(names, ["primary_name"])
        window.destroy()

    def test_refresh_closes_when_context_no_longer_completable(self):
        controller, buffer, window = _make_controller("active_person.primary_")
        controller.trigger()
        self.assertTrue(controller.is_open())

        it = buffer.get_iter_at_mark(buffer.get_insert())
        buffer.insert(it, " ")
        controller.on_buffer_changed()
        self.assertFalse(controller.is_open())
        window.destroy()


if __name__ == "__main__":
    unittest.main()
