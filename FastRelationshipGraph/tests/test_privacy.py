#
# FastRelationshipGraph -- a standalone addon, independent of gramps-core
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
#

"""Tests for privacy behavior: a private person, a private family, or a
private ChildRef must each be individually invisible to a
FastRelationshipGraph constructed on a `PrivateProxyDb`-wrapped db, and
nothing else should be.

Unlike gramps-sql-extensions (a `restricted=` kwarg per call), this
package takes `db` at construction time -- restricted vs. unrestricted
is "construct on a PrivateProxyDb-wrapped db, or don't" (see
fast_relationship_graph.py's module docstring). setUpClass below builds
one small hand-crafted database exercising all three of PrivateProxyDb's
rules, plus one ordinary (non-private) link as a control, and two
FastRelationshipGraph instances over it -- one plain, one restricted.

Run with::

    python3 -m unittest FastRelationshipGraph.tests.test_privacy -v
"""

import unittest

try:
    import gi  # noqa: F401
    import gramps
except ImportError as exc:
    raise unittest.SkipTest("FastRelationshipGraph tests require 'gi' and 'gramps': %s" % exc)

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import ChildRefType, Family, Person
from gramps.gen.proxy import PrivateProxyDb

from fast_relationship_graph import FastRelationshipGraph


def _new_person(db, trans, gender, private=False):
    person = Person()
    person.set_gender(gender)
    person.set_privacy(private)
    handle = db.add_person(person, trans)
    return handle


def _new_family(db, trans, father_handle, mother_handle, children, family_private=False):
    """`children`: list of (Person, childref_private) pairs. Uses
    `db.add_child_to_family()` rather than hand-building a `ChildRef`
    and adding it to the family directly -- the latter only sets the
    *family's* side of the link (`Family.child_ref_list`); the object
    API's own traversal (`Person.get_main_parents_family_handle()`,
    which `RelationshipCalculator`/this package's ancestor-map BFS both
    depend on) reads the *person's* side (`Person.parent_family_list`),
    which only `add_child_to_family()` (or a hand-rolled
    `child.add_parent_family_handle()`) actually populates."""
    family = Family()
    family.set_privacy(family_private)
    family.set_father_handle(father_handle)
    family.set_mother_handle(mother_handle)
    family_handle = db.add_family(family, trans)
    for child, childref_private in children:
        db.add_child_to_family(
            family, child, mrel=ChildRefType.BIRTH, frel=ChildRefType.BIRTH, trans=trans
        )
        if childref_private:
            family.get_child_ref_list()[-1].set_privacy(True)
            db.commit_family(family, trans)
    return family_handle


class PrivacyTest(unittest.TestCase):
    """Three small families, one exercising each of PrivateProxyDb's
    three privacy rules, plus one ordinary (non-private) link in the
    first family as a control -- restricted filtering shouldn't hide
    anything it isn't supposed to, not just hide what it is."""

    @classmethod
    def setUpClass(cls):
        cls.db = make_database("sqlite")
        cls.db.load(":memory:")
        MALE, FEMALE = Person.MALE, Person.FEMALE

        with DbTxn("build privacy test tree", cls.db) as trans:
            # rule 1: a private person as a parent
            father1 = _new_person(cls.db, trans, MALE)
            mother1 = _new_person(cls.db, trans, FEMALE, private=True)
            child1 = _new_person(cls.db, trans, MALE)
            _new_family(
                cls.db, trans, father1, mother1,
                [(cls.db.get_person_from_handle(child1), False)],
            )

            # rule 2: a private family (both parents public, family itself private)
            father2 = _new_person(cls.db, trans, MALE)
            mother2 = _new_person(cls.db, trans, FEMALE)
            child2 = _new_person(cls.db, trans, MALE)
            _new_family(
                cls.db, trans, father2, mother2,
                [(cls.db.get_person_from_handle(child2), False)],
                family_private=True,
            )

            # rule 3: a private ChildRef (person/family public, just this link private)
            father3 = _new_person(cls.db, trans, MALE)
            mother3 = _new_person(cls.db, trans, FEMALE)
            child3 = _new_person(cls.db, trans, MALE)
            _new_family(
                cls.db, trans, father3, mother3,
                [(cls.db.get_person_from_handle(child3), True)],
            )

        cls.h = {
            "father1": father1, "mother1": mother1, "child1": child1,
            "father2": father2, "mother2": mother2, "child2": child2,
            "father3": father3, "mother3": mother3, "child3": child3,
        }
        cls.unrestricted = FastRelationshipGraph(cls.db)
        cls.restricted = FastRelationshipGraph(PrivateProxyDb(cls.db))

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_private_person_hidden_when_restricted(self):
        h = self.h
        rel_str, _, _ = self.unrestricted.relationship(h["child1"], h["mother1"])
        self.assertEqual(rel_str, "mother")
        rel_str, _, _ = self.restricted.relationship(h["child1"], h["mother1"])
        self.assertEqual(rel_str, "")

    def test_private_person_does_not_hide_other_parent(self):
        h = self.h
        rel_str_u, _, _ = self.unrestricted.relationship(h["child1"], h["father1"])
        rel_str_r, _, _ = self.restricted.relationship(h["child1"], h["father1"])
        self.assertEqual(rel_str_u, "father")
        self.assertEqual(rel_str_r, "father")

    def test_private_family_hidden_when_restricted(self):
        h = self.h
        rel_str, _, _ = self.unrestricted.relationship(h["child2"], h["father2"])
        self.assertEqual(rel_str, "father")
        rel_str, _, _ = self.restricted.relationship(h["child2"], h["father2"])
        self.assertEqual(rel_str, "")

    def test_private_childref_hidden_when_restricted(self):
        h = self.h
        rel_str, _, _ = self.unrestricted.relationship(h["child3"], h["father3"])
        self.assertEqual(rel_str, "father")
        rel_str, _, _ = self.restricted.relationship(h["child3"], h["father3"])
        self.assertEqual(rel_str, "")

    def test_all_relationships_respects_privacy(self):
        h = self.h
        self.assertEqual(self.restricted.all_relationships(h["child1"], h["mother1"]), [{}])
        self.assertEqual(
            self.unrestricted.all_relationships(h["child1"], h["mother1"])[0][
                "relationship_string"
            ],
            "mother",
        )

    def test_relationship_path_respects_privacy(self):
        h = self.h
        self.assertEqual(self.restricted.relationship_path(h["child1"], h["mother1"]), [])
        path = self.unrestricted.relationship_path(h["child1"], h["mother1"])
        self.assertEqual([node["handle"] for node in path], [h["child1"], h["mother1"]])
        self.assertEqual(path[-1]["relationship_string"], "mother")

    def test_all_relationship_paths_respects_privacy(self):
        h = self.h
        self.assertEqual(
            self.restricted.all_relationship_paths(h["child1"], h["mother1"]), []
        )
        paths = self.unrestricted.all_relationship_paths(h["child1"], h["mother1"])
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0][-1]["relationship_string"], "mother")

    def test_relationships_to_hides_private_target_person(self):
        """mother1 is herself a private Person (not just a private
        link), so a restricted caller shouldn't see her as a target at
        all -- silently dropped from an explicit `handles` list, and
        absent from the `handles=None` "everyone" listing, same as
        PrivateProxyDb hiding a private Person object entirely from a
        listing endpoint."""
        h = self.h

        explicit_restricted = self.restricted.relationships_to(
            h["child1"], handles=[h["father1"], h["mother1"]]
        )
        self.assertEqual(
            [item["handle"] for item in explicit_restricted["items"]], [h["father1"]]
        )
        self.assertEqual(explicit_restricted["total"], 1)

        explicit_unrestricted = self.unrestricted.relationships_to(
            h["child1"], handles=[h["father1"], h["mother1"]]
        )
        self.assertEqual(
            {item["handle"] for item in explicit_unrestricted["items"]},
            {h["father1"], h["mother1"]},
        )

        everyone_restricted = self.restricted.relationships_to(h["child1"])
        everyone_unrestricted = self.unrestricted.relationships_to(h["child1"])
        self.assertNotIn(
            h["mother1"], {item["handle"] for item in everyone_restricted["items"]}
        )
        self.assertIn(
            h["mother1"], {item["handle"] for item in everyone_unrestricted["items"]}
        )
        self.assertLess(everyone_restricted["total"], everyone_unrestricted["total"])

    def test_relationships_to_bulk_strategy_respects_privacy(self):
        """Same as test_relationships_to_hides_private_target_person,
        but forcing the full-tree-index (`_relationships_to_bulk`)
        strategy -- see fast_relationship_graph.py's own docstring on
        why that strategy must use `db.get_family_from_handle()` per
        family rather than `db.iter_families()`, which does not
        sanitize the families it returns."""
        h = self.h
        result = self.restricted.relationships_to(
            h["child1"], handles=[h["father1"], h["mother1"]], bulk_threshold=0
        )
        self.assertEqual([item["handle"] for item in result["items"]], [h["father1"]])


if __name__ == "__main__":
    unittest.main()
