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
Functional tests for each gramplet's get_items() against a real in-memory
Gramps database, bypassing Gramplet.__init__ (and so all GTK/GUI setup)
since get_items() only touches self.dbstate and self.filter_missing.
"""

import os
import sys
import types
import unittest

try:
    import gi

    gi.require_version("Gtk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Event, EventType, Name, Place, PlaceName, Person, Surname

from cloudgramplet import _hex_to_rgb
from givennamewordcloudgramplet import GivenNameWordCloudGramplet
from placewordcloudgramplet import PlaceWordCloudGramplet
from surnamewordcloudgramplet import SurnameWordCloudGramplet


def _make_gramplet(cls, db, filter_missing):
    """Build a gramplet instance without running Gramplet.__init__/init(),
    which would require a live GUI. get_items() only needs dbstate/filter_missing.
    """
    gramplet = object.__new__(cls)
    gramplet.dbstate = types.SimpleNamespace(db=db)
    gramplet.filter_missing = filter_missing
    return gramplet


class CloudGrampletLogicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = make_database("sqlite")
        cls.db.load(":memory:")

        with DbTxn("Add test objects", cls.db) as trans:
            cls.smith1 = cls._add_person(cls.db, trans, "John", "Smith")
            cls.smith2 = cls._add_person(cls.db, trans, "Jane", "Smith")
            cls.doe = cls._add_person(cls.db, trans, "John", "Doe")
            cls.blank = cls._add_person(cls.db, trans, "", "")

            cls.place = cls._add_place(cls.db, trans, "Springfield")
            cls.unused_place = cls._add_place(cls.db, trans, "Shelbyville")

            event = Event()
            event.set_type(EventType(EventType.BIRTH))
            event.set_place_handle(cls.place.handle)
            cls.db.add_event(event, trans)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    @staticmethod
    def _add_person(db, trans, given, surname):
        person = Person()
        name = Name()
        name.set_first_name(given)
        gramps_surname = Surname()
        gramps_surname.set_surname(surname)
        name.set_surname_list([gramps_surname])
        person.set_primary_name(name)
        db.add_person(person, trans)
        return person

    @staticmethod
    def _add_place(db, trans, place_name):
        place = Place()
        place.set_name(PlaceName(value=place_name))
        db.add_place(place, trans)
        return place


class TestGivenNameWordCloudGramplet(CloudGrampletLogicTest):
    def test_counts_given_names(self):
        gramplet = _make_gramplet(
            GivenNameWordCloudGramplet, self.db, filter_missing=True
        )
        items = dict((value, count) for value, _linked, count in gramplet.get_items())
        self.assertEqual(items["John"], 2)
        self.assertEqual(items["Jane"], 1)
        self.assertNotIn("", items)

    def test_filter_missing_false_includes_blank(self):
        gramplet = _make_gramplet(
            GivenNameWordCloudGramplet, self.db, filter_missing=False
        )
        items = dict((value, count) for value, _linked, count in gramplet.get_items())
        self.assertIn("", items)


class TestSurnameWordCloudGramplet(CloudGrampletLogicTest):
    def test_counts_surnames_and_links_a_handle(self):
        gramplet = _make_gramplet(
            SurnameWordCloudGramplet, self.db, filter_missing=True
        )
        items = {
            value: (linked, count) for value, linked, count in gramplet.get_items()
        }
        self.assertEqual(items["Smith"][1], 2)
        self.assertEqual(items["Doe"][1], 1)
        self.assertIn(items["Smith"][0], (self.smith1.handle, self.smith2.handle))
        self.assertNotIn("", items)

    def test_filter_missing_false_includes_blank(self):
        gramplet = _make_gramplet(
            SurnameWordCloudGramplet, self.db, filter_missing=False
        )
        items = dict((value, count) for value, _linked, count in gramplet.get_items())
        self.assertIn("", items)


class TestPlaceWordCloudGramplet(CloudGrampletLogicTest):
    def test_only_referenced_places_are_included(self):
        gramplet = _make_gramplet(PlaceWordCloudGramplet, self.db, filter_missing=True)
        items = {
            value: (linked, count) for value, linked, count in gramplet.get_items()
        }
        self.assertIn("Springfield", items)
        self.assertEqual(items["Springfield"][0], self.place.handle)
        self.assertEqual(items["Springfield"][1], 1)
        # Shelbyville has no backlinks, so it must not appear.
        self.assertNotIn("Shelbyville", items)


class TestHexToRgb(unittest.TestCase):
    def test_black(self):
        self.assertEqual(_hex_to_rgb("#000000"), (0.0, 0.0, 0.0))

    def test_white(self):
        self.assertEqual(_hex_to_rgb("#ffffff"), (1.0, 1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
