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

"""Regression tests for fast_relationship_engine.py's copy of the
gramps-project/gramps#2526 search, on small hand-built trees.

These mirror the regression tests added to that PR alongside its later
fixes (loop pruning, nearest-first result cap), run here against
`fast_relationship_calculator()` instead of core's own calculator.

Run with::

    python3 -m unittest FastRelationshipGraph.tests.test_engine -v
"""

import unittest

try:
    import gi  # noqa: F401
    import gramps  # noqa: F401
except ImportError as exc:
    raise unittest.SkipTest("FastRelationshipGraph tests require 'gi' and 'gramps': %s" % exc)

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import ChildRefType, Family, Person

from fast_relationship_engine import fast_relationship_calculator


def _make_db():
    db = make_database("sqlite")
    db.load(":memory:")
    return db


def _add_person(db, gender=Person.MALE):
    person = Person()
    person.set_gender(gender)
    with DbTxn("add person", db) as trans:
        db.add_person(person, trans)
    return person


def _add_family(db, father=None, mother=None):
    family = Family()
    if father is not None:
        family.set_father_handle(father.handle)
    if mother is not None:
        family.set_mother_handle(mother.handle)
    with DbTxn("add family", db) as trans:
        db.add_family(family, trans)
    return family


def _add_child(db, family, child):
    with DbTxn("add child", db) as trans:
        db.add_child_to_family(
            family,
            child,
            mrel=ChildRefType(ChildRefType.BIRTH),
            frel=ChildRefType(ChildRefType.BIRTH),
            trans=trans,
        )


class LoopPruningTest(unittest.TestCase):
    def test_loop_through_start_person_is_not_reported(self):
        """A path that climbs back to the starting person through a loop
        and then on to a real ancestor must be pruned, as the original
        does. The start person's own path is stored without going
        through the loop index, so it has to be picked up from `pmap`."""
        db = _make_db()
        try:
            person = _add_person(db, Person.MALE)
            father = _add_person(db, Person.MALE)
            grandfather = _add_person(db, Person.MALE)
            mother = _add_person(db, Person.FEMALE)
            son = _add_person(db, Person.MALE)
            wife = _add_person(db, Person.FEMALE)
            _add_child(db, _add_family(db, grandfather, None), father)
            _add_child(db, _add_family(db, father, mother), person)
            _add_child(db, _add_family(db, son, None), mother)
            # closes the loop: son is also person's maternal grandfather
            _add_child(db, _add_family(db, person, wife), son)

            calc = fast_relationship_calculator()
            p1 = db.get_person_from_handle(person.handle)
            p2 = db.get_person_from_handle(grandfather.handle)
            rels, _handles = calc.get_all_relationships(db, p1, p2)
            self.assertEqual(rels, ["grandfather"])
            dist, _msg = calc.get_relationship_distance_new(
                db, p1, p2, all_families=True, all_dist=True, only_birth=False
            )
            self.assertEqual([(d[2], d[4]) for d in dist], [("ff", "")])
            self.assertTrue(calc._FastRelationshipMixin__loop_detected)
        finally:
            db.close()


class MaxCommonResultsTest(unittest.TestCase):
    def test_cap_keeps_nearest_path_across_visit_order(self):
        """The cap must keep the nearest paths even when a farther path
        to the same ancestor is found first. Here the ancestor is
        reached through the father's line (`fff`) before the mother's
        (`mf`), and with a cap of 1 only the nearer `mf` may survive."""
        db = _make_db()
        try:
            ancestor = _add_person(db, Person.MALE)
            ancestor_family = _add_family(db, ancestor, None)
            son = _add_person(db, Person.MALE)
            daughter = _add_person(db, Person.FEMALE)
            other = _add_person(db, Person.MALE)
            _add_child(db, ancestor_family, son)
            _add_child(db, ancestor_family, daughter)
            _add_child(db, ancestor_family, other)
            grandson = _add_person(db, Person.MALE)
            _add_child(db, _add_family(db, son, None), grandson)
            person = _add_person(db, Person.MALE)
            _add_child(db, _add_family(db, grandson, daughter), person)

            p1 = db.get_person_from_handle(person.handle)
            p2 = db.get_person_from_handle(other.handle)
            for all_dist in (True, False):
                calc = fast_relationship_calculator()
                calc.set_max_common_results(1)
                data, _msg = calc.get_relationship_distance_new(
                    db, p1, p2, all_dist=all_dist, all_families=True
                )
                if all_dist:
                    self.assertEqual([(d[0], d[2], d[4]) for d in data], [(3, "mf", "f")])
                else:
                    self.assertEqual((data[0], data[2], data[4]), (3, "mf", "f"))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
