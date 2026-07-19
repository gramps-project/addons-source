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
Regression test: every WordClouds module must import cleanly and expose
the class named in WordClouds.gpr.py, and each gramplet class must be a
Gramplet subclass.
"""

import os
import sys
import unittest

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# Make sure addon modules are importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWordCloudsImports(unittest.TestCase):
    """Every module registered in WordClouds.gpr.py must import cleanly."""

    def test_wordcloudwidget_imports(self):
        import wordcloudwidget

        self.assertTrue(hasattr(wordcloudwidget, "WordCloudWidget"))

    def test_slideroption_imports(self):
        import slideroption

        self.assertTrue(hasattr(slideroption, "SliderOption"))
        self.assertTrue(hasattr(slideroption, "GuiSliderOption"))

    def test_cloudgramplet_imports(self):
        import cloudgramplet

        self.assertTrue(hasattr(cloudgramplet, "CloudGramplet"))

    def test_gramplet_classes_are_gramplet_subclasses(self):
        from gramps.gen.plug import Gramplet

        from givennamewordcloudgramplet import GivenNameWordCloudGramplet
        from surnamewordcloudgramplet import SurnameWordCloudGramplet
        from placewordcloudgramplet import PlaceWordCloudGramplet

        for cls in (
            GivenNameWordCloudGramplet,
            SurnameWordCloudGramplet,
            PlaceWordCloudGramplet,
        ):
            self.assertTrue(
                issubclass(cls, Gramplet), "%s must be a Gramplet subclass" % cls
            )


if __name__ == "__main__":
    unittest.main()
