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

"""Mocked unit tests for the ``QueryFilter`` gramplet's click handlers.

No live Gramps window, no database on disk -- ``self.gui``/``self.dbstate``/
``self.uistate`` are replaced with mocks (``PersonQueryFilter.__new__``
bypasses ``Gramplet.__init__``, the same pattern
``Form/tests/test_editform_save_guards.py`` uses to avoid needing a running
main window). ``compile_expr``/``GenericFilterFactory`` run for real --
they're pure/fast and need no display.

Run with::

    python3 -m unittest GOQLFilter.tests.test_goql -v
"""

import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gi  # noqa: F401
    from gi.repository import Gdk
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)

try:
    import goql as goql_gramplet
except ImportError as exc:
    raise unittest.SkipTest(
        "goql import failed (likely missing gramps-object-query-language): %s" % exc
    )


def _make_gramplet(initial_text=""):
    """A ``PersonQueryFilter`` with only the attributes its click handlers
    touch -- bypasses ``Gramplet.__init__``, which wants a live
    ``GuiGramplet``/``dbstate``/``uistate`` and builds real widgets against
    a running Gramps window. ``_get_expr_text``/``_set_expr_text`` stand in
    for the real ``Gtk.TextBuffer``-backed versions -- what they read from
    and write to is exactly the seam ``find_clicked``/``reset_clicked``/
    ``define_clicked``/history navigation go through.
    """
    gramplet = goql_gramplet.PersonQueryFilter.__new__(goql_gramplet.PersonQueryFilter)
    text = {"value": initial_text}
    gramplet._get_expr_text = MagicMock(side_effect=lambda: text["value"].strip())
    gramplet._set_expr_text = MagicMock(
        side_effect=lambda t: text.__setitem__("value", t)
    )
    gramplet.msg_label = MagicMock()
    gramplet.dbstate = MagicMock()
    gramplet.uistate = MagicMock()
    gramplet.gui = MagicMock()
    gramplet.history = []
    gramplet.history_index = None
    gramplet.history_draft = ""
    gramplet.completion = MagicMock()
    gramplet.completion.on_key_press.return_value = False
    return gramplet


def _key_event(keyval, ctrl=False):
    return types.SimpleNamespace(
        keyval=keyval,
        state=(Gdk.ModifierType.CONTROL_MASK if ctrl else Gdk.ModifierType(0)),
    )


# ------------------------------------------------------------
#
# DefineFilterCallbackTest
#
# ------------------------------------------------------------
class DefineFilterCallbackTest(unittest.TestCase):
    """Regression test: interactively, "Define filter" -> OK raised
    ``TypeError: QueryFilter._filter_defined() missing 2 required
    positional arguments: 'filterdb' and '_filter_name'``.

    Cause: ``define_clicked`` passed ``_filter_defined`` to ``EditFilter``'s
    ``update`` parameter, which ``EditFilter.on_ok_clicked`` calls with zero
    arguments (``self.update()``). The two-argument call
    (``self.selection_callback(self.filterdb, self.filter.get_name())``)
    is a separate parameter, ``selection_callback`` -- see
    ``gramps/gui/editors/filtereditor.py``. Fixed by passing
    ``_filter_defined`` as ``selection_callback`` instead.
    """

    def test_define_clicked_uses_selection_callback_not_update(self):
        gramplet = _make_gramplet("gender == Person.MALE")

        with patch.object(goql_gramplet, "EditFilter") as mock_edit_filter:
            gramplet.define_clicked(None)

        mock_edit_filter.assert_called_once()
        _args, kwargs = mock_edit_filter.call_args
        # Bound methods aren't identical objects across separate attribute
        # accesses even for the same instance+function, so compare by
        # equality (bound methods implement __eq__), not identity.
        self.assertEqual(kwargs.get("selection_callback"), gramplet._filter_defined)
        self.assertIsNone(kwargs.get("update"))

    def test_filter_defined_matches_editfilter_call_signature(self):
        """``EditFilter.on_ok_clicked`` calls
        ``self.selection_callback(self.filterdb, self.filter.get_name())``
        -- ``_filter_defined`` must accept exactly that shape and use it to
        persist + reload the custom filter list.
        """
        gramplet = _make_gramplet()
        filterdb = MagicMock()

        with patch.object(goql_gramplet, "reload_custom_filters") as mock_reload:
            gramplet._filter_defined(filterdb, "My Filter")

        filterdb.save.assert_called_once()
        mock_reload.assert_called_once()
        gramplet.uistate.emit.assert_called_once_with("filters-changed", ("Person",))

    def test_define_clicked_reports_compile_error_without_opening_dialog(self):
        gramplet = _make_gramplet("this is not valid GOQL !!")

        with patch.object(goql_gramplet, "EditFilter") as mock_edit_filter:
            gramplet.define_clicked(None)

        mock_edit_filter.assert_not_called()
        gramplet.msg_label.set_text.assert_called()


# ------------------------------------------------------------
#
# FindResetTest
#
# ------------------------------------------------------------
class FindResetTest(unittest.TestCase):
    """Happy-path coverage for the Find/Reset mechanism itself: setting
    ``view.generic_filter`` and calling ``view.build_tree()`` -- the same
    two calls core's own ``plugins/gramplet/filter.py`` uses.
    """

    def test_find_clicked_sets_generic_filter_and_rebuilds(self):
        gramplet = _make_gramplet("gender == Person.MALE")
        gramplet.gui.view.search_bar.is_visible.return_value = False

        gramplet.find_clicked(None)

        self.assertIsNotNone(gramplet.gui.view.generic_filter)
        gramplet.gui.view.build_tree.assert_called_once()

    def test_find_clicked_reports_compile_error_without_touching_view(self):
        gramplet = _make_gramplet("this is not valid GOQL !!")

        gramplet.find_clicked(None)

        gramplet.gui.view.build_tree.assert_not_called()
        gramplet.msg_label.set_text.assert_called()

    def test_find_clicked_with_empty_expression_resets_instead(self):
        gramplet = _make_gramplet("   ")
        gramplet.gui.view.search_bar.is_visible.return_value = False

        gramplet.find_clicked(None)

        gramplet._set_expr_text.assert_called_once_with("")
        self.assertIsNone(gramplet.gui.view.generic_filter)
        gramplet.gui.view.build_tree.assert_called_once()

    def test_reset_clicked_clears_filter_and_rebuilds(self):
        gramplet = _make_gramplet()
        gramplet.gui.view.search_bar.is_visible.return_value = False

        gramplet.reset_clicked(None)

        gramplet._set_expr_text.assert_called_once_with("")
        self.assertIsNone(gramplet.gui.view.generic_filter)
        gramplet.gui.view.build_tree.assert_called_once()

    def test_hide_quick_search_bar_hides_when_visible(self):
        gramplet = _make_gramplet()
        gramplet.gui.view.search_bar.is_visible.return_value = True

        gramplet._hide_quick_search_bar()

        gramplet.gui.view.search_bar.hide.assert_called_once()

    def test_hide_quick_search_bar_leaves_hidden_bar_alone(self):
        gramplet = _make_gramplet()
        gramplet.gui.view.search_bar.is_visible.return_value = False

        gramplet._hide_quick_search_bar()

        gramplet.gui.view.search_bar.hide.assert_not_called()

    def test_hide_quick_search_bar_tolerates_a_view_without_one(self):
        gramplet = _make_gramplet()
        del gramplet.gui.view.search_bar  # e.g. a non-ListView pageview

        gramplet._hide_quick_search_bar()  # must not raise


def _make_gramplet_for_keypress(cursor_line=0, line_count=1):
    """A gramplet with a mocked ``text_buffer`` reporting a fixed cursor
    line / line count, and mocked ``find_clicked``/``_history_back``/
    ``_history_forward`` -- enough to test ``_on_key_press``'s dispatch in
    isolation, without constructing a real ``Gtk.TextView`` (needs a real
    display connection to construct at all, which the documented test
    invocation's ``GDK_BACKEND=-`` deliberately does without -- see
    ``HistoryNavigationTest`` for the text-content-level coverage this
    dispatch-only test doesn't duplicate).
    """
    gramplet = goql_gramplet.PersonQueryFilter.__new__(goql_gramplet.PersonQueryFilter)
    cursor_iter = MagicMock()
    cursor_iter.get_line.return_value = cursor_line
    gramplet.text_buffer = MagicMock()
    gramplet.text_buffer.get_iter_at_mark.return_value = cursor_iter
    gramplet.text_buffer.get_line_count.return_value = line_count
    gramplet.find_clicked = MagicMock()
    gramplet._history_back = MagicMock()
    gramplet._history_forward = MagicMock()
    gramplet.completion = MagicMock()
    gramplet.completion.on_key_press.return_value = False
    return gramplet


# ------------------------------------------------------------
#
# HistoryNavigationTest
#
# ------------------------------------------------------------
class HistoryNavigationTest(unittest.TestCase):
    """``_remember_history``/``_history_back``/``_history_forward`` in
    isolation, through the ``_get_expr_text``/``_set_expr_text`` seam.
    """

    def test_remember_history_appends_and_resets_index(self):
        gramplet = _make_gramplet()
        gramplet.history_index = 0  # pretend we were mid-browse

        gramplet._remember_history("gender == Person.MALE")

        self.assertEqual(gramplet.history, ["gender == Person.MALE"])
        self.assertIsNone(gramplet.history_index)

    def test_remember_history_skips_immediate_repeat(self):
        gramplet = _make_gramplet()
        gramplet._remember_history("gender == Person.MALE")
        gramplet._remember_history("gender == Person.MALE")

        self.assertEqual(gramplet.history, ["gender == Person.MALE"])

    def test_remember_history_ignores_empty_expression(self):
        gramplet = _make_gramplet()
        gramplet._remember_history("")

        self.assertEqual(gramplet.history, [])

    def test_history_back_recalls_most_recent_first_and_saves_draft(self):
        gramplet = _make_gramplet("draft in progress")
        gramplet.history = ["first", "second"]

        gramplet._history_back()

        self.assertEqual(gramplet._get_expr_text(), "second")
        self.assertEqual(gramplet.history_draft, "draft in progress")

    def test_history_back_twice_walks_further_back(self):
        gramplet = _make_gramplet()
        gramplet.history = ["first", "second"]

        gramplet._history_back()
        gramplet._history_back()

        self.assertEqual(gramplet._get_expr_text(), "first")

    def test_history_back_stops_at_oldest_entry(self):
        gramplet = _make_gramplet()
        gramplet.history = ["only"]

        gramplet._history_back()
        gramplet._history_back()

        self.assertEqual(gramplet._get_expr_text(), "only")

    def test_history_back_with_empty_history_is_a_no_op(self):
        gramplet = _make_gramplet("still typing")

        gramplet._history_back()

        self.assertEqual(gramplet._get_expr_text(), "still typing")

    def test_history_forward_returns_to_draft_past_newest(self):
        gramplet = _make_gramplet("draft in progress")
        gramplet.history = ["first", "second"]
        gramplet._history_back()  # -> "second", saves the draft

        gramplet._history_forward()

        self.assertEqual(gramplet._get_expr_text(), "draft in progress")
        self.assertIsNone(gramplet.history_index)

    def test_history_forward_without_browsing_is_a_no_op(self):
        gramplet = _make_gramplet("still typing")

        gramplet._history_forward()

        self.assertEqual(gramplet._get_expr_text(), "still typing")


# ------------------------------------------------------------
#
# KeyPressTest
#
# ------------------------------------------------------------
class KeyPressTest(unittest.TestCase):
    """``_on_key_press``'s dispatch: completion gets first look at every key
    (so its popover's Up/Down/Enter/Escape work); Ctrl+Enter runs Find;
    Tab is always consumed -- it never inserts a tab character, even when
    there was nothing to complete; Up/Down (when completion didn't
    consume them) only recall history at the first/last line of the
    buffer, so normal cursor movement inside a multi-line expression
    still works.
    """

    def test_ctrl_enter_runs_find_and_is_consumed(self):
        gramplet = _make_gramplet_for_keypress()

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Return, ctrl=True))

        self.assertTrue(handled)
        gramplet.find_clicked.assert_called_once()

    def test_plain_enter_is_not_consumed(self):
        gramplet = _make_gramplet_for_keypress()

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Return, ctrl=False))

        self.assertFalse(handled)
        gramplet.find_clicked.assert_not_called()

    def test_up_at_first_line_of_single_line_buffer_recalls_history(self):
        gramplet = _make_gramplet_for_keypress(cursor_line=0, line_count=1)

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Up))

        self.assertTrue(handled)
        gramplet._history_back.assert_called_once()

    def test_up_on_a_later_line_of_a_multiline_buffer_is_not_consumed(self):
        gramplet = _make_gramplet_for_keypress(cursor_line=1, line_count=2)

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Up))

        self.assertFalse(handled)
        gramplet._history_back.assert_not_called()

    def test_down_on_an_earlier_line_of_a_multiline_buffer_is_not_consumed(self):
        gramplet = _make_gramplet_for_keypress(cursor_line=0, line_count=2)

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Down))

        self.assertFalse(handled)
        gramplet._history_forward.assert_not_called()

    def test_down_at_last_line_recalls_history(self):
        gramplet = _make_gramplet_for_keypress(cursor_line=1, line_count=2)

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Down))

        self.assertTrue(handled)
        gramplet._history_forward.assert_called_once()

    def test_tab_is_consumed_even_with_nothing_to_complete(self):
        gramplet = _make_gramplet_for_keypress()
        gramplet.completion.on_key_press.return_value = False  # nothing completable

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Tab))

        self.assertTrue(handled)  # never falls back to inserting a tab

    def test_tab_delegates_to_completion_first(self):
        gramplet = _make_gramplet_for_keypress()
        gramplet.completion.on_key_press.return_value = True  # triggered/accepted

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Tab))

        self.assertTrue(handled)
        gramplet.completion.on_key_press.assert_called_once()

    def test_completion_open_intercepts_up_before_history_navigation(self):
        """When the completion popover is open, Up/Down navigate it, not
        history -- CompletionController.on_key_press itself decides this
        (returns True while open); this just checks _on_key_press honors
        that decision instead of also running its own Up/Down handling.
        """
        gramplet = _make_gramplet_for_keypress(cursor_line=0, line_count=1)
        gramplet.completion.on_key_press.return_value = True

        handled = gramplet._on_key_press(None, _key_event(Gdk.KEY_Up))

        self.assertTrue(handled)
        gramplet._history_back.assert_not_called()


# ------------------------------------------------------------
#
# HistoryPersistenceTest
#
# ------------------------------------------------------------
class HistoryPersistenceTest(unittest.TestCase):
    """``on_load``/``on_save`` round-trip history through ``self.gui.data``
    -- the same per-instance saved-placement mechanism core gramplets like
    ``plugins/gramplet/pedigreegramplet.py`` use for their own persisted
    options (``Gramplet.__init__`` calls ``init()`` then ``on_load()``;
    ``GrampletBar.on_delete`` calls ``on_save()`` before writing
    ``self.gui.data`` to the gramplet's saved-placement .ini file).
    """

    def test_on_load_restores_history_from_gui_data(self):
        gramplet = goql_gramplet.PersonQueryFilter.__new__(
            goql_gramplet.PersonQueryFilter
        )
        gramplet.gui = MagicMock()
        gramplet.gui.data = ["first", "second"]

        gramplet.on_load()

        self.assertEqual(gramplet.history, ["first", "second"])

    def test_on_save_writes_history_to_gui_data(self):
        gramplet = _make_gramplet()
        gramplet.history = ["first", "second"]

        gramplet.on_save()

        self.assertEqual(gramplet.gui.data, ["first", "second"])

    def test_remember_history_caps_at_max_entries(self):
        gramplet = _make_gramplet()
        total = goql_gramplet.HISTORY_MAX_ENTRIES + 5
        for i in range(total):
            gramplet._remember_history("expr %d" % i)

        self.assertEqual(len(gramplet.history), goql_gramplet.HISTORY_MAX_ENTRIES)
        self.assertEqual(gramplet.history[0], "expr 5")
        self.assertEqual(gramplet.history[-1], "expr %d" % (total - 1))


# ------------------------------------------------------------
#
# FilterProgressTest
#
# ------------------------------------------------------------
class FilterProgressTest(unittest.TestCase):
    """``_run_with_filter_progress``/``_filter_method_label`` -- the
    Prepare-time/Apply-time + SQL-vs-eval diagnostics mirrored from
    ``gui/filters/sidebar/_sidebarfilter.py``'s ``clicked()``.
    ``GenericFilter.apply()`` already reports those phase timings via
    ``user.notify(...)``; without ``uistate.filter_print_func`` wired up,
    ``gui/user.py``'s ``User._gui_print`` sends them to stdout instead of
    any widget -- which is exactly why they only ever showed up in a
    terminal before this.
    """

    def test_run_with_filter_progress_wires_and_clears_the_hooks(self):
        gramplet = _make_gramplet()
        seen = {}

        def action():
            seen["print_func_during"] = gramplet.uistate.filter_print_func
            seen["step_func_during"] = gramplet.uistate.filter_step_func

        gramplet._run_with_filter_progress(action)

        self.assertIsNotNone(seen["print_func_during"])
        self.assertIsNotNone(seen["step_func_during"])
        self.assertIsNone(gramplet.uistate.filter_print_func)
        self.assertIsNone(gramplet.uistate.filter_step_func)

    def test_run_with_filter_progress_clears_hooks_even_on_exception(self):
        gramplet = _make_gramplet()

        def action():
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            gramplet._run_with_filter_progress(action)

        self.assertIsNone(gramplet.uistate.filter_print_func)
        self.assertIsNone(gramplet.uistate.filter_step_func)

    def test_run_with_filter_progress_collects_messages(self):
        gramplet = _make_gramplet()

        def action():
            gramplet.uistate.filter_print_func("Prepare time: 0.01s")
            gramplet.uistate.filter_print_func("Apply time: 0.02s")

        phase_msgs = gramplet._run_with_filter_progress(action)

        self.assertEqual(phase_msgs, ["Prepare time: 0.01s", "Apply time: 0.02s"])

    def test_filter_method_label_reports_sql_when_a_rule_has_selected_handles(self):
        gramplet = _make_gramplet()
        rule = MagicMock()
        rule.selected_handles = {"h1"}
        gfilter = MagicMock()
        gfilter.get_rules.return_value = [rule]

        self.assertEqual(gramplet._filter_method_label(gfilter), "SQL")

    def test_filter_method_label_reports_eval_when_no_rule_has_selected_handles(self):
        gramplet = _make_gramplet()
        rule = MagicMock()
        rule.selected_handles = None
        gfilter = MagicMock()
        gfilter.get_rules.return_value = [rule]

        self.assertEqual(gramplet._filter_method_label(gfilter), "Python evaluation")


# ------------------------------------------------------------
#
# HelpButtonTest
#
# ------------------------------------------------------------
class HelpButtonTest(unittest.TestCase):
    """``self.gui.help_url`` is set from the ``.gpr.py`` registration's
    ``help_url=`` -- the same attribute/dispatch the built-in per-gramplet
    "Help" menu item already uses (``gui/widgets/grampletpane.py``/
    ``grampletbar.py``).
    """

    def test_help_clicked_opens_wiki_page_for_a_non_url_help_url(self):
        gramplet = _make_gramplet()
        gramplet.gui.help_url = "Addon:GrampsObjectQueryLanguage"

        with patch.object(goql_gramplet, "display_help") as mock_help, patch.object(
            goql_gramplet, "display_url"
        ) as mock_url:
            gramplet.help_clicked(None)

        mock_help.assert_called_once_with("Addon:GrampsObjectQueryLanguage")
        mock_url.assert_not_called()

    def test_help_clicked_opens_a_raw_url_directly(self):
        gramplet = _make_gramplet()
        gramplet.gui.help_url = "https://example.org/help"

        with patch.object(goql_gramplet, "display_help") as mock_help, patch.object(
            goql_gramplet, "display_url"
        ) as mock_url:
            gramplet.help_clicked(None)

        mock_url.assert_called_once_with("https://example.org/help")
        mock_help.assert_not_called()

    def test_help_clicked_with_no_help_url_does_nothing(self):
        gramplet = _make_gramplet()
        gramplet.gui.help_url = None

        with patch.object(goql_gramplet, "display_help") as mock_help, patch.object(
            goql_gramplet, "display_url"
        ) as mock_url:
            gramplet.help_clicked(None)

        mock_help.assert_not_called()
        mock_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
