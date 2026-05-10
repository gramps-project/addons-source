#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Gramps Development Team
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

"""
Regression test for the tooltip-cache gate in
``LifeLineChartView.on_mouse_move``.

Historically the outer ``if`` test was a tuple expression::

    if (self._tooltip_individual_cache is None or \\
        self._tooltip_individual_cache != gr_individual, gr_family):

— ``(A or B, gr_family)`` is a non-empty tuple, which is always
truthy, so the body always ran on every mouse-move event. The
intended check is ``cache != (gr_individual, gr_family)`` (with a
proper inner tuple). After the fix, the body should run **only**
when the hovered individual/family changes.

This test exercises ``on_mouse_move`` directly with a stub
``LifeLineChartView`` instance and verifies that two consecutive
calls hovering the *same* individual update the tooltip exactly once
(i.e. on the cache-miss). Before the fix, ``info_label.set_text`` was
called on every move; after the fix, only on cache-miss transitions.
"""

import os
import sys
import unittest
from unittest import mock

# Pin GTK to 3.0 *before* any gramps.gui import — Gramps's gui
# layer references Gtk.IconSize.MENU which only exists in GTK 3.
# Skip the test cleanly if PyGObject / GTK 3 is unavailable, so the
# CI matrix does not have to choose between hard-failing and
# silently passing.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest(
        "GTK 3.0 / PyGObject not available: %s" % err)

# Make sure addon modules are importable from the parent directory.
# Required when this test is loaded via its dotted path
# (``LifeLineChartView.tests.test_lifelinechart_tooltip_cache``)
# rather than via ``unittest discover`` from inside ``tests/``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import lifelinechart
except ImportError as err:
    # ``life_line_chart`` and ``svgwrite`` are declared in the addon's
    # requires_mod and pip-installed by the addon-unit CI step. If
    # they are missing locally, skip the test rather than fail.
    raise unittest.SkipTest(
        "LifeLineChartView dependencies not available: %s" % err)


class TestOnMouseMoveTooltipCacheGate(unittest.TestCase):
    """Cover the outer-if gate around the tooltip update."""

    @staticmethod
    def _make_stub_view():
        """Build a stub ``LifeLineChartView`` with only the attributes
        ``on_mouse_move`` reads. We don't instantiate the real class
        because its ``__init__`` chains into NavigationView setup and
        full GTK widget construction. Instead we call the unbound
        method with a stub ``self``.
        """
        v = mock.MagicMock()
        v._tooltip_individual_cache = None
        v.last_x = None       # routes execution into the buggy if-block
        v.last_y = None
        v._mouse_click = False
        v.upper_left_view_position = (0, 0)
        v.zoom_level = 1.0
        v.mouse_x = 0
        v.mouse_y = 0
        # life_line_chart_instance returns (gr_individual, gr_family)
        # from get_individual_from_position; fixed in each test below.
        return v

    def test_unchanged_individual_does_not_re_set_tooltip(self):
        """Two consecutive moves over the same individual must call
        ``info_label.set_text`` exactly once (on the cache-miss
        transition), not twice.

        Before the fix this assertion fails because the buggy
        ``if (... , gr_family):`` test was always truthy and the body
        ran on every call.
        """
        v = self._make_stub_view()
        gr_individual = mock.MagicMock()
        gr_individual.individual.short_info_text = "Some Person"
        gr_individual.individual._gramps_person.get_gramps_id.return_value = "I0001"
        gr_family = mock.MagicMock()
        v.life_line_chart_instance.get_individual_from_position.return_value = (
            gr_individual,
            gr_family,
        )
        v.life_line_chart_instance._inverse_y_position.return_value = 1
        event = mock.MagicMock(x=10, y=20)
        widget = mock.MagicMock()

        # First call: cache is None — outer-if must fire, body runs.
        lifelinechart.LifeLineChartBaseWidget.on_mouse_move(v, widget, event)
        self.assertEqual(v.info_label.set_text.call_count, 1)
        self.assertEqual(v.queue_draw_wrapper.call_count, 1)
        # Cache assignment from the body (line ~1172):
        # ``self._tooltip_individual_cache = gr_individual, gr_family``
        self.assertEqual(
            v._tooltip_individual_cache, (gr_individual, gr_family))

        # Reset last_x/last_y to None — the outer condition gating
        # this whole branch — so the next call routes into the same
        # block again.
        v.last_x = None
        v.last_y = None

        # Second call with the SAME individual/family: outer-if must
        # now be False (cache equals the new tuple), so body must
        # NOT run again.
        lifelinechart.LifeLineChartBaseWidget.on_mouse_move(v, widget, event)
        self.assertEqual(
            v.info_label.set_text.call_count,
            1,
            "set_text must NOT be re-called when the hovered individual is unchanged "
            "(F634 outer-if was always-True before the fix)",
        )
        self.assertEqual(
            v.queue_draw_wrapper.call_count,
            1,
            "queue_draw_wrapper must NOT be re-called when the hovered individual "
            "is unchanged",
        )

    def test_changed_individual_re_runs_body(self):
        """When the hovered individual changes, the body must run
        again — both before and after the fix this should hold; the
        test pins down that the fix didn't *over*-suppress."""
        v = self._make_stub_view()
        gr_a = mock.MagicMock()
        gr_a.individual.short_info_text = "Person A"
        gr_a.individual._gramps_person.get_gramps_id.return_value = "I0001"
        gr_fam = mock.MagicMock()
        v.life_line_chart_instance.get_individual_from_position.return_value = (
            gr_a,
            gr_fam,
        )
        v.life_line_chart_instance._inverse_y_position.return_value = 1
        event = mock.MagicMock(x=10, y=20)
        widget = mock.MagicMock()

        lifelinechart.LifeLineChartBaseWidget.on_mouse_move(v, widget, event)
        v.last_x = None
        v.last_y = None

        # Second call: different individual. Body must run again.
        gr_b = mock.MagicMock()
        gr_b.individual.short_info_text = "Person B"
        gr_b.individual._gramps_person.get_gramps_id.return_value = "I0002"
        v.life_line_chart_instance.get_individual_from_position.return_value = (
            gr_b,
            gr_fam,
        )
        lifelinechart.LifeLineChartBaseWidget.on_mouse_move(v, widget, event)

        self.assertEqual(v.info_label.set_text.call_count, 2)
        self.assertEqual(v.queue_draw_wrapper.call_count, 2)
        self.assertEqual(v._tooltip_individual_cache, (gr_b, gr_fam))


if __name__ == "__main__":
    unittest.main()
