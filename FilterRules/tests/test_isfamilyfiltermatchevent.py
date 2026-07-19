#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Doug Blank
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
Regression tests for the ``IsFamilyFilterMatchEvent`` filter rule.

``prepare()`` used to update ``self.events``, an attribute never
defined anywhere on the class, instead of ``self.selected_handles``
(the attribute it initializes and that ``apply_to_one()`` actually
checks). That raised ``AttributeError: 'IsFamilyFilterMatchEvent'
object has no attribute 'events'`` whenever the "Events of families
matching a <family filter>" rule was applied, crashing the filter
entirely. See:
https://gramps.discourse.group/t/crash-of-an-event-filter-using-a-functional-family-filter/9733
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import os
import shutil
import sys
import tempfile
import unittest

# The addon imports Gtk at module load (via
# gramps.gui.editors.filtereditor). GTK/GDK are already pinned to 3.0
# repo-wide by tests/__init__.py (PR #950); skip cleanly here if
# PyGObject isn't available at all.
try:
    import gi
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)

# Addon root goes on sys.path so ``FilterRules.isfamilyfiltermatchevent``
# resolves. The ``FilterRules`` directory lacks an __init__.py, so this
# relies on Python 3 namespace packages.
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps
except ImportError as err:
    raise unittest.SkipTest("gramps package not available: %s" % err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Event, EventRef, EventType, Family, FamilyRelType

# CustomFilters starts out as None; it must be initialized before any
# module imports the name by value, since reload_custom_filters()
# rebinds the module-level global rather than mutating it in place.
from gramps.gen.filters import reload_custom_filters

reload_custom_filters()
from gramps.gen.filters import CustomFilters, GenericFilterFactory
from gramps.gen.filters.rules.family import HasIdOf as FamilyHasIdOf
from gramps.cli.user import User

from FilterRules.isfamilyfiltermatchevent import IsFamilyFilterMatchEvent

FAMILY_FILTER_NAME = "_test_isfamilyfiltermatchevent_family_filter"


class IsFamilyFilterMatchEventTest(unittest.TestCase):
    """Regression tests for IsFamilyFilterMatchEvent.prepare()."""

    def setUp(self):
        """Build a database with two families, each with one event, and
        register a custom Family filter matching only the first."""
        self.db_dir = tempfile.mkdtemp(prefix="isfamilyfiltermatchevent_")
        self.db = make_database("sqlite")
        self.db.load(self.db_dir)

        with DbTxn("build test db", self.db) as txn:
            matched_event = Event()
            matched_event.set_type(EventType(EventType.MARRIAGE))
            self.db.add_event(matched_event, txn)
            self.matched_event_handle = matched_event.handle

            unmatched_event = Event()
            unmatched_event.set_type(EventType(EventType.MARRIAGE))
            self.db.add_event(unmatched_event, txn)
            self.unmatched_event_handle = unmatched_event.handle

            matched_family = Family()
            matched_family.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
            matched_ref = EventRef()
            matched_ref.set_reference_handle(self.matched_event_handle)
            matched_family.add_event_ref(matched_ref)
            self.db.add_family(matched_family, txn)
            self.matched_family_gramps_id = matched_family.gramps_id

            unmatched_family = Family()
            unmatched_family.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
            unmatched_ref = EventRef()
            unmatched_ref.set_reference_handle(self.unmatched_event_handle)
            unmatched_family.add_event_ref(unmatched_ref)
            self.db.add_family(unmatched_family, txn)

        family_filter = GenericFilterFactory("Family")()
        family_filter.set_name(FAMILY_FILTER_NAME)
        family_filter.add_rule(FamilyHasIdOf([self.matched_family_gramps_id]))
        CustomFilters.get_filters_dict("Family")[FAMILY_FILTER_NAME] = family_filter

    def tearDown(self):
        del CustomFilters.get_filters_dict("Family")[FAMILY_FILTER_NAME]
        self.db.close()
        shutil.rmtree(self.db_dir, ignore_errors=True)

    def test_prepare_does_not_raise_attributeerror(self):
        """prepare() must populate selected_handles, not crash on the
        undefined self.events."""
        rule = IsFamilyFilterMatchEvent([FAMILY_FILTER_NAME])
        rule.requestprepare(self.db, User())
        self.assertEqual(rule.selected_handles, {self.matched_event_handle})

    def test_apply_to_one_matches_only_expected_event(self):
        """apply_to_one() must accept the matched family's event and
        reject the unmatched family's event."""
        rule = IsFamilyFilterMatchEvent([FAMILY_FILTER_NAME])
        rule.requestprepare(self.db, User())
        matched_event = self.db.get_event_from_handle(self.matched_event_handle)
        unmatched_event = self.db.get_event_from_handle(self.unmatched_event_handle)
        self.assertTrue(rule.apply_to_one(self.db, matched_event))
        self.assertFalse(rule.apply_to_one(self.db, unmatched_event))

    def test_full_filter_apply(self):
        """Running the rule through a GenericFilter must return exactly
        the matched family's event."""
        event_filter = GenericFilterFactory("Event")()
        event_filter.add_rule(IsFamilyFilterMatchEvent([FAMILY_FILTER_NAME]))
        results = set(event_filter.apply(self.db))
        self.assertEqual(results, {self.matched_event_handle})

    def test_missing_family_filter(self):
        """A rule referencing a nonexistent family filter must not
        crash and must match nothing."""
        rule = IsFamilyFilterMatchEvent(["_no_such_filter_"])
        rule.requestprepare(self.db, User())
        self.assertEqual(rule.selected_handles, set())


if __name__ == "__main__":
    unittest.main()
