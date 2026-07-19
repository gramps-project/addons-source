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
Tests for SliderOption / GuiSliderOption: the vendored NumberOption
subclass and its GTK widget, registered with the plugin manager as an
external option so WordClouds needs no Gramps core changes.
"""

import os
import sys
import unittest

try:
    import gi

    gi.require_version("Gtk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

from gi.repository import Gtk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from slideroption import GuiSliderOption, SliderOption


class TestSliderOption(unittest.TestCase):
    """SliderOption inherits all min/max/step/value logic from NumberOption."""

    def test_initial_value(self):
        option = SliderOption("Quality", 0.5, 0.0, 1.0, 0.1)
        self.assertEqual(option.get_value(), 0.5)
        self.assertEqual(option.get_min(), 0.0)
        self.assertEqual(option.get_max(), 1.0)
        self.assertEqual(option.get_step(), 0.1)

    def test_set_value(self):
        option = SliderOption("Count", 10, 1, 150)
        option.set_value(75)
        self.assertEqual(option.get_value(), 75)


class TestGuiSliderOption(unittest.TestCase):
    """Smoke tests for the GTK widget wrapping a SliderOption."""

    def _make_widget(self, option):
        return GuiSliderOption(option, None, None, [], False)

    def test_widget_reflects_initial_value(self):
        option = SliderOption("Count", 10, 1, 150)
        widget = self._make_widget(option)
        self.assertIsInstance(widget, Gtk.Box)

    def test_option_value_change_updates_widget_without_error(self):
        option = SliderOption("Count", 10, 1, 150)
        self._make_widget(option)
        # Should not raise: exercises __value_changed via the signal.
        option.set_value(42)
        self.assertEqual(option.get_value(), 42)

    def test_clean_up_disconnects_without_error(self):
        option = SliderOption("Count", 10, 1, 150)
        widget = self._make_widget(option)
        widget.clean_up()


if __name__ == "__main__":
    unittest.main()
