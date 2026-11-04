#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       David Straub
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

"""Integration tests for ``degreesofseparation.py``.

Run with::

    python3 -m unittest FilterRules.tests.test_integration_degreesofseparation -v
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

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gi
except ImportError as err:
    raise unittest.SkipTest("PyGObject not available: %s" % err)

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import ChildRef, Family, Person

from degreesofseparation import DegreesOfSeparation

# Families as (father, mother, children). Distances from "me", following the
# rule's links (parent, child, partner, sibling or half-sibling):
#   1: dad, mom, sister, half_brother, wife, kid
#   2: grandpa, grandma, aunt, stepmom, kid_wife, grandkid
#   3: uncle, cousin
# "stranger" is not connected to anyone.
FAMILIES = [
    ("grandpa", "grandma", ["dad", "aunt"]),
    ("dad", "mom", ["me", "sister"]),
    ("dad", "stepmom", ["half_brother"]),
    ("me", "wife", ["kid"]),
    ("kid", "kid_wife", ["grandkid"]),
    ("uncle", "aunt", ["cousin"]),
]
PEOPLE = sorted({name for fam in FAMILIES for name in (fam[0], fam[1], *fam[2])})
PEOPLE.append("stranger")

DEGREE_1 = {"me", "dad", "mom", "sister", "half_brother", "wife", "kid"}
DEGREE_2 = DEGREE_1 | {"grandpa", "grandma", "aunt", "stepmom", "kid_wife", "grandkid"}
DEGREE_3 = DEGREE_2 | {"uncle", "cousin"}


class DegreesOfSeparationTest(unittest.TestCase):
    """Check which people the rule matches at each depth."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp(prefix="degreesofseparation_")
        cls.db = make_database("sqlite")
        cls.db.load(cls.tmp_dir)
        cls.handles = {}
        with DbTxn("build test db", cls.db) as trans:
            for name in PEOPLE:
                person = Person()
                person.set_gramps_id(name)
                cls.handles[name] = cls.db.add_person(person, trans)
            for father, mother, children in FAMILIES:
                family = Family()
                family.set_father_handle(cls.handles[father])
                family.set_mother_handle(cls.handles[mother])
                for child in children:
                    child_ref = ChildRef()
                    child_ref.set_reference_handle(cls.handles[child])
                    family.add_child_ref(child_ref)
                fam_handle = cls.db.add_family(family, trans)
                for parent in (father, mother):
                    person = cls.db.get_person_from_handle(cls.handles[parent])
                    person.add_family_handle(fam_handle)
                    cls.db.commit_person(person, trans)
                for child in children:
                    person = cls.db.get_person_from_handle(cls.handles[child])
                    person.add_parent_family_handle(fam_handle)
                    cls.db.commit_person(person, trans)
        cls.names = {handle: name for name, handle in cls.handles.items()}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def matched(self, gramps_id, degrees):
        """Return the names of the people the rule matches."""
        rule = DegreesOfSeparation([gramps_id, str(degrees)])
        rule.prepare(self.db, None)
        matched = {
            self.names[handle]
            for handle in self.handles.values()
            if rule.apply_to_one(self.db, self.db.get_person_from_handle(handle))
        }
        self.assertEqual(matched, {self.names[h] for h in rule.selected_handles})
        return matched

    def test_zero_degrees_matches_only_the_person(self):
        self.assertEqual(self.matched("me", 0), {"me"})

    def test_one_degree(self):
        self.assertEqual(self.matched("me", 1), DEGREE_1)

    def test_two_degrees(self):
        self.assertEqual(self.matched("me", 2), DEGREE_2)

    def test_three_degrees(self):
        self.assertEqual(self.matched("me", 3), DEGREE_3)

    def test_more_degrees_than_needed_stops_at_unconnected_people(self):
        self.assertEqual(self.matched("me", 10), set(PEOPLE) - {"stranger"})

    def test_from_another_start_person(self):
        self.assertEqual(
            self.matched("cousin", 1), {"cousin", "uncle", "aunt"}
        )
        self.assertEqual(
            self.matched("cousin", 2),
            {"cousin", "uncle", "aunt", "grandpa", "grandma", "dad"},
        )

    def test_unknown_id_matches_nobody(self):
        self.assertEqual(self.matched("nobody", 3), set())


if __name__ == "__main__":
    unittest.main()
