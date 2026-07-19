#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Douglas S. Blank <doug.blank@gmail.com>
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
Tests for the pure layout-math helpers in wordcloudwidget.py: font-size and
color interpolation, and axis-aligned bounding-box overlap detection.
"""

import os
import sys
import unittest

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wordcloudwidget import _aabbs_overlap, _count_to_color, _count_to_fontsize


class TestCountToFontsize(unittest.TestCase):
    def test_min_and_max_count_map_to_min_and_max_font(self):
        self.assertAlmostEqual(_count_to_fontsize(1, 1, 100, 8, 20), 8)
        self.assertAlmostEqual(_count_to_fontsize(100, 1, 100, 8, 20), 20)

    def test_equal_min_and_max_count_returns_midpoint(self):
        self.assertAlmostEqual(_count_to_fontsize(5, 5, 5, 8, 20), 14)

    def test_higher_count_never_yields_smaller_font(self):
        low = _count_to_fontsize(2, 1, 100, 8, 20)
        high = _count_to_fontsize(50, 1, 100, 8, 20)
        self.assertLessEqual(low, high)


class TestCountToColor(unittest.TestCase):
    def test_min_count_is_low_color(self):
        color = _count_to_color(1, 1, 100, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        self.assertEqual(color, (0.0, 0.0, 0.0))

    def test_max_count_is_high_color(self):
        color = _count_to_color(100, 1, 100, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        self.assertEqual(color, (1.0, 1.0, 1.0))

    def test_equal_min_and_max_count_returns_midpoint_color(self):
        color = _count_to_color(5, 5, 5, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        self.assertEqual(color, (0.5, 0.5, 0.5))


class TestAabbsOverlap(unittest.TestCase):
    def test_identical_boxes_overlap(self):
        self.assertTrue(_aabbs_overlap(0, 0, 10, 10, 0, 0, 10, 10))

    def test_disjoint_boxes_do_not_overlap(self):
        self.assertFalse(_aabbs_overlap(0, 0, 10, 10, 20, 20, 10, 10))

    def test_edge_touching_boxes_do_not_overlap(self):
        # Box B starts exactly where box A ends: touching, not overlapping.
        self.assertFalse(_aabbs_overlap(0, 0, 10, 10, 10, 0, 10, 10))

    def test_partial_overlap_is_detected(self):
        self.assertTrue(_aabbs_overlap(0, 0, 10, 10, 5, 5, 10, 10))


if __name__ == "__main__":
    unittest.main()
