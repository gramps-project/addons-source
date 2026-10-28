#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  The Gramps Development Team
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
Tests for the in-memory search in ``deep_connections``: FamilyLinks,
shortest_connection and the labels, against a real Gramps database and
Gramps' own relationship calculator.

The tree::

    GF + GM                      WF + WM
       |-- A (m) + W (f) ----------|-- W
       |      |-- C (m)            `-- X (f) -- Y (f)
       |      |-- C2 (m) + D (f)  (C2 married his cousin D)
       |      `-- S (m)  W's son, A's stepson
       `-- B (f) + H (m)
              `-- D (f)

    G2 (f)
       |-- M (f)  + Q (m) -- P (m)  birth son of Q and M
       `-- M2 (f) + Q (m) -- P      P is M2's stepson (added first)
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import ChildRef, ChildRefType, Family, Name, Person
from gramps.gen.proxy import PrivateProxyDb
from gramps.gen.relationship import get_relationship_calculator

import deep_connections as dc

MALE, FEMALE = Person.MALE, Person.FEMALE


class _Tree:
    """A small tree in a temporary SQLite database."""

    def __init__(self):
        self.dirname = tempfile.mkdtemp(prefix="deepconnections_")
        self.db = make_database("sqlite")
        self.db.load(self.dirname)
        self.people = {}
        self.families = {}
        with DbTxn("build test tree", self.db) as txn:
            for name, gender in (
                ("GF", MALE),
                ("GM", FEMALE),
                ("A", MALE),
                ("B", FEMALE),
                ("W", FEMALE),
                ("H", MALE),
                ("C", MALE),
                ("C2", MALE),
                ("S", MALE),
                ("D", FEMALE),
                ("WF", MALE),
                ("WM", FEMALE),
                ("X", FEMALE),
                ("Y", FEMALE),
                ("G2", FEMALE),
                ("M", FEMALE),
                ("M2", FEMALE),
                ("Q", MALE),
                ("P", MALE),
            ):
                person = Person()
                person.set_gender(gender)
                primary_name = Name()
                primary_name.set_first_name(name)
                person.set_primary_name(primary_name)
                self.people[name] = self.db.add_person(person, txn)
            self._family(txn, "FG", "GF", "GM", ["A", "B"])
            self._family(
                txn, "FA", "A", "W", ["C", "C2", ("S", ChildRefType.STEPCHILD)]
            )
            self._family(txn, "FB", "H", "B", ["D"])
            self._family(txn, "FW", "WF", "WM", ["W", "X"])
            self._family(txn, "FX", None, "X", ["Y"])
            self._family(txn, "FC2", "C2", "D", [])
            self._family(txn, "FG2", None, "G2", ["M", "M2"])
            birth, step = ChildRefType.BIRTH, ChildRefType.STEPCHILD
            self._family(txn, "FQ2", "Q", "M2", [("P", birth, step)])
            self._family(txn, "FQ1", "Q", "M", ["P"])

    def _family(self, txn, key, father, mother, children):
        family = Family()
        if father:
            family.set_father_handle(self.people[father])
        if mother:
            family.set_mother_handle(self.people[mother])
        for child in children:
            # a name, or (name, relation to father[, relation to mother])
            if isinstance(child, str):
                child = (child,)
            name = child[0]
            ref = ChildRef()
            ref.set_reference_handle(self.people[name])
            if len(child) > 1:
                ref.set_father_relation(child[1])
            if len(child) > 2:
                ref.set_mother_relation(child[2])
            family.add_child_ref(ref)
        handle = self.db.add_family(family, txn)
        self.families[key] = handle
        for parent in (father, mother):
            if parent:
                person = self.db.get_person_from_handle(self.people[parent])
                person.add_family_handle(handle)
                self.db.commit_person(person, txn)
        for child in children:
            name = child if isinstance(child, str) else child[0]
            person = self.db.get_person_from_handle(self.people[name])
            person.add_parent_family_handle(handle)
            self.db.commit_person(person, txn)

    def close(self):
        self.db.close()
        shutil.rmtree(self.dirname, ignore_errors=True)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = _Tree()
        cls.db = cls.tree.db
        cls.p = cls.tree.people
        cls.links = dc.FamilyLinks.load(cls.db)
        cls.calc = get_relationship_calculator(reinit=True)
        cls.genders = {
            h: cls.db.get_person_from_handle(h).get_gender() for h in cls.p.values()
        }

    @classmethod
    def tearDownClass(cls):
        cls.tree.close()

    def names(self, path):
        by_handle = {h: n for n, h in self.p.items()}
        return [by_handle[link.handle] for link in path]

    def label(self, a, b):
        path = dc.shortest_connection(self.links, self.p[a], self.p[b])
        return dc.connection_label(self.links, path, self.genders, self.calc)

    def calculator(self, a, b):
        return self.calc.get_one_relationship(
            self.db,
            self.db.get_person_from_handle(self.p[a]),
            self.db.get_person_from_handle(self.p[b]),
        )

    def require_english(self):
        if (
            self.calc.get_sibling_relationship_string(self.calc.NORM_SIB, MALE, FEMALE)
            != "sister"
        ):
            self.skipTest("expected English wording")


class TestDescent(_Base):
    def test_labels_match_the_calculator(self):
        for a, b in (
            ("C", "D"),  # first cousins
            ("C", "B"),  # aunt
            ("D", "A"),  # uncle
            ("C", "GF"),  # grandfather
            ("GM", "D"),  # granddaughter
            ("C", "C2"),  # brother
            ("A", "S"),  # stepson
            ("S", "C"),  # half brother through W
            ("A", "C"),  # son
        ):
            with self.subTest(a=a, b=b):
                self.assertEqual(self.label(a, b), self.calculator(a, b))

    def test_chain_goes_through_the_common_ancestor(self):
        path = dc.shortest_connection(self.links, self.p["C"], self.p["D"])
        self.assertEqual(self.names(path), ["C", "A", self.names(path)[2], "B", "D"])
        self.assertIn(self.names(path)[2], ("GF", "GM"))
        self.assertEqual(
            [link.relation for link in path],
            [dc.SELF, dc.PARENT, dc.PARENT, dc.CHILD, dc.CHILD],
        )

    def test_cousin_wins_over_a_shorter_marriage_link(self):
        # C2's wife D is two steps from C (brother's wife) but also his
        # first cousin through their grandparents.
        self.assertEqual(self.label("C", "D"), self.calculator("C", "D"))
        path = dc.shortest_connection(self.links, self.p["C"], self.p["D"])
        self.assertNotIn(dc.SPOUSE, [link.relation for link in path])

    def test_birth_line_wins_over_an_equally_short_step_line(self):
        # G2 is P's grandmother by birth (through M) and his step-grandmother
        # (through his stepmother M2); both lines are two generations long.
        self.require_english()
        path = dc.shortest_connection(self.links, self.p["P"], self.p["G2"])
        self.assertEqual(self.names(path), ["P", "M", "G2"])
        self.assertEqual(self.label("P", "G2"), "grandmother")

    def test_path_labels(self):
        path = dc.shortest_connection(self.links, self.p["C"], self.p["D"])
        labels = dc.path_labels(self.links, path, self.genders, self.calc)
        names = self.names(path)
        for name, label in zip(names[1:], labels[1:]):
            with self.subTest(person=name):
                self.assertEqual(label, self.calculator("C", name))
        self.assertEqual(labels[0], "")


class TestInLaws(_Base):
    def test_in_law_labels(self):
        self.require_english()
        for a, b, expected in (
            ("A", "X", "sister-in-law"),  # spouse's sister
            ("A", "H", "brother-in-law"),  # sister's husband
            ("GF", "W", "daughter-in-law"),  # son's wife
            ("W", "GM", "mother-in-law"),  # husband's mother
            ("A", "Y", "niece-in-law"),  # spouse's niece
        ):
            with self.subTest(a=a, b=b):
                self.assertEqual(self.calculator(a, b), "")  # not by descent
                self.assertEqual(self.label(a, b), expected)

    def test_spouse_alone_has_no_label(self):
        path = dc.shortest_connection(self.links, self.p["A"], self.p["W"])
        self.assertEqual(self.names(path), ["A", "W"])
        self.assertEqual(
            dc.connection_label(self.links, path, self.genders, self.calc), ""
        )

    def test_longer_connection_has_path_but_no_label(self):
        # H is B's husband; X is W's sister: H -> B -> A -> W -> X
        path = dc.shortest_connection(self.links, self.p["H"], self.p["X"])
        self.assertEqual(self.names(path)[0], "H")
        self.assertEqual(self.names(path)[-1], "X")
        self.assertEqual(
            dc.connection_label(self.links, path, self.genders, self.calc), ""
        )


class TestSearch(_Base):
    def test_no_connection(self):
        lone = dc.FamilyLinks()
        lone.add_family("F1", "P", None, [("K", 1, 1)])  # BIRTH
        self.assertIsNone(dc.shortest_connection(lone, "P", "nobody"))

    def test_same_person(self):
        path = dc.shortest_connection(self.links, self.p["C"], self.p["C"])
        self.assertEqual(self.names(path), ["C"])

    def test_limit(self):
        with self.assertRaises(dc.SearchLimitReached):
            dc.any_path(self.links, self.p["H"], self.p["Y"], max_people=3)

    def test_restrictions_come_from_the_database(self):
        # Make W's parents' family private: through a privacy proxy, W and X
        # are no longer linked, so A and X are not connected at all.
        with DbTxn("make private", self.db) as txn:
            family = self.db.get_family_from_handle(self.tree.families["FW"])
            family.set_privacy(True)
            self.db.commit_family(family, txn)
        try:
            restricted = dc.FamilyLinks.load(PrivateProxyDb(self.db))
            self.assertIsNone(
                dc.shortest_connection(restricted, self.p["A"], self.p["X"])
            )
            self.assertIsNotNone(
                dc.shortest_connection(self.links, self.p["A"], self.p["X"])
            )
        finally:
            with DbTxn("make public", self.db) as txn:
                family = self.db.get_family_from_handle(self.tree.families["FW"])
                family.set_privacy(False)
                self.db.commit_family(family, txn)


if __name__ == "__main__":
    unittest.main()
