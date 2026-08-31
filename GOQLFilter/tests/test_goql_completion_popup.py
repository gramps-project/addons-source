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

"""Tests for ``goql_completion_popup.CompletionController``'s decision
logic, driven with a mocked ``Gtk.TextView``/``Gtk.TextBuffer`` rather than
real ones -- ``Gtk.TextView()`` needs an actual display connection just to
construct (see ``test_goql.py``'s ``KeyPressTest`` fixtures for the same
constraint under this repo's documented ``GDK_BACKEND=-`` test invocation).
Real-popover paths (multi-match) aren't covered here for the same reason;
``_compute_items`` is patched directly to isolate ``trigger()``'s own
single/zero-match branching from how items get computed.

Run with::

    python3 -m unittest GOQLFilter.tests.test_goql_completion_popup -v
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gi  # noqa: F401
    from gi.repository import Gdk
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)

try:
    from goql_completion_popup import CompletionController
except ImportError as exc:
    raise unittest.SkipTest(
        "goql_completion_popup import failed (likely missing "
        "gramps-object-query-language): %s" % exc
    )


def _make_controller():
    textview = MagicMock()
    buffer = MagicMock()
    textview.get_buffer.return_value = buffer
    controller = CompletionController(textview, get_namespace=lambda: "Person")
    return controller, buffer


def _key_event(keyval):
    return types.SimpleNamespace(keyval=keyval, state=Gdk.ModifierType(0))


# ------------------------------------------------------------
#
# TriggerTest
#
# ------------------------------------------------------------
class TriggerTest(unittest.TestCase):
    def test_single_match_inserts_directly_without_opening_a_popover(self):
        controller, buffer = _make_controller()
        controller._compute_items = MagicMock(
            return_value=[{"name": "MALE", "complete": "LE", "cursor_offset": 0}]
        )

        handled = controller.trigger()

        self.assertTrue(handled)
        self.assertFalse(controller.is_open())
        buffer.insert.assert_called_once()
        self.assertEqual(buffer.insert.call_args.args[1], "LE")

    def test_no_matches_is_a_no_op(self):
        controller, buffer = _make_controller()
        controller._compute_items = MagicMock(return_value=[])

        handled = controller.trigger()

        self.assertFalse(handled)
        self.assertFalse(controller.is_open())
        buffer.insert.assert_not_called()


# ------------------------------------------------------------
#
# AcceptCloseTest
#
# ------------------------------------------------------------
class AcceptCloseTest(unittest.TestCase):
    def test_accept_inserts_the_selected_items_complete_text(self):
        controller, buffer = _make_controller()
        controller.items = [
            {"name": "count(...)", "complete": "count()", "cursor_offset": 0}
        ]
        controller.selected_index = 0

        controller.accept()

        buffer.insert.assert_called_once()
        self.assertEqual(buffer.insert.call_args.args[1], "count()")

    def test_accept_moves_cursor_back_by_cursor_offset(self):
        controller, buffer = _make_controller()
        controller.items = [
            {"name": "count(...)", "complete": "count()", "cursor_offset": 1}
        ]
        controller.selected_index = 0
        cursor_iter = MagicMock()
        buffer.get_iter_at_mark.return_value = cursor_iter

        controller.accept()

        cursor_iter.backward_chars.assert_called_once_with(1)
        buffer.place_cursor.assert_called_once_with(cursor_iter)

    def test_close_resets_state(self):
        controller, _buffer = _make_controller()
        controller.items = [{"name": "x", "complete": "", "cursor_offset": 0}]
        controller.selected_index = 2
        controller.popover = MagicMock()

        controller.close()

        self.assertIsNone(controller.popover)
        self.assertEqual(controller.items, [])
        self.assertEqual(controller.selected_index, 0)


# ------------------------------------------------------------
#
# OnKeyPressTest
#
# ------------------------------------------------------------
class OnKeyPressTest(unittest.TestCase):
    """Mirrors GOQLFilter/goql.py's own reliance on this dispatch: Tab
    triggers when closed and accepts when open; Up/Down/Enter/Escape only
    do anything while the popover is open, so a closed controller leaves
    them for the host widget (goql.py's own history navigation) to handle.
    """

    def test_tab_triggers_when_closed(self):
        controller, _buffer = _make_controller()
        controller.trigger = MagicMock(return_value=True)

        handled = controller.on_key_press(_key_event(Gdk.KEY_Tab))

        self.assertTrue(handled)
        controller.trigger.assert_called_once()

    def test_tab_accepts_when_open(self):
        controller, _buffer = _make_controller()
        controller.popover = MagicMock()  # is_open() -> True
        controller.accept = MagicMock()

        handled = controller.on_key_press(_key_event(Gdk.KEY_Tab))

        self.assertTrue(handled)
        controller.accept.assert_called_once()

    def test_escape_closes_when_open(self):
        controller, _buffer = _make_controller()
        controller.popover = MagicMock()
        controller.close = MagicMock()

        handled = controller.on_key_press(_key_event(Gdk.KEY_Escape))

        self.assertTrue(handled)
        controller.close.assert_called_once()

    def test_up_is_not_consumed_when_closed(self):
        controller, _buffer = _make_controller()

        handled = controller.on_key_press(_key_event(Gdk.KEY_Up))

        self.assertFalse(handled)

    def test_up_moves_selection_when_open(self):
        controller, _buffer = _make_controller()
        controller.popover = MagicMock()
        controller.move_selection = MagicMock()

        handled = controller.on_key_press(_key_event(Gdk.KEY_Up))

        self.assertTrue(handled)
        controller.move_selection.assert_called_once_with(-1)

    def test_never_propagates_an_exception(self):
        controller, _buffer = _make_controller()
        controller.trigger = MagicMock(side_effect=RuntimeError("boom"))

        handled = controller.on_key_press(_key_event(Gdk.KEY_Tab))

        self.assertFalse(handled)


if __name__ == "__main__":
    unittest.main()
