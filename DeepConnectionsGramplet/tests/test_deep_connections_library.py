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
Tests for ``deep_connections``, the GUI-independent search used by the Deep
Connections Gramplet.  The module must import and run without GTK, so these
tests use only small in-memory stand-ins for the database.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import deep_connections as dc


class _ChildRef:
    def __init__(self, ref):
        self.ref = ref


class _PersonRef:
    def __init__(self, ref, rel):
        self.ref = ref
        self.rel = rel

    def get_reference_handle(self):
        return self.ref

    def get_relation(self):
        return self.rel


class _Note:
    def __init__(self, person_handles):
        self._links = [("gramps", "Person", "handle", h) for h in person_handles]

    def get_links(self):
        return self._links


class _Person:
    def __init__(self, handle, families=(), parent_families=(), assocs=(), notes=()):
        self.handle = handle
        self._families = list(families)
        self._parent_families = list(parent_families)
        self._assocs = list(assocs)
        self._notes = list(notes)

    def get_family_handle_list(self):
        return self._families

    def get_parent_family_handle_list(self):
        return self._parent_families

    def get_person_ref_list(self):
        return self._assocs

    def get_note_list(self):
        return self._notes


class _Family:
    def __init__(self, handle, father=None, mother=None, children=()):
        self.handle = handle
        self._father = father
        self._mother = mother
        self._children = list(children)

    def get_child_ref_list(self):
        return [_ChildRef(c) for c in self._children]

    def get_father_handle(self):
        return self._father

    def get_mother_handle(self):
        return self._mother

    def get_note_list(self):
        return []


class _DB:
    def __init__(self, people, families, notes=None):
        self._people = people
        self._families = families
        self._notes = notes or {}

    def get_person_from_handle(self, handle):
        return self._people.get(handle)

    def get_family_from_handle(self, handle):
        return self._families.get(handle)

    def get_note_from_handle(self, handle):
        return self._notes.get(handle)


def _in_law_db():
    """
    ``D`` (start) married ``W``.  ``W``'s sibling ``S`` married ``T``, and
    ``T`` is the child of ``P``.  ``D`` and ``P`` share no ancestor.

        D -- W   (family FDW)
        W, S     children of FWS
        S -- T   (family FST)
        T        child of P (family FP)
    """
    families = {
        "FDW": _Family("FDW", father="D", mother="W"),
        "FWS": _Family("FWS", children=["W", "S"]),
        "FST": _Family("FST", father="S", mother="T"),
        "FP": _Family("FP", father="P", children=["T"]),
    }
    people = {
        "D": _Person("D", families=["FDW"]),
        "W": _Person("W", families=["FDW"], parent_families=["FWS"]),
        "S": _Person("S", families=["FST"], parent_families=["FWS"]),
        "T": _Person("T", families=["FST"], parent_families=["FP"]),
        "P": _Person("P", families=["FP"]),
    }
    return _DB(people, families)


def _relations(path):
    """``[(relation, anchor), ...]`` from the found person back to the root."""
    return [(step.relation, step.handle) for step in dc.path_steps(path)]


class TestFindConnections(unittest.TestCase):
    def test_finds_connection_through_marriages(self):
        paths = list(dc.find_connections(_in_law_db(), "D", "P", max_paths=1))
        self.assertEqual(len(paths), 1)
        # P is the father of T, T is the wife of S, S is the sibling of W,
        # and W is attached straight to the root D (issue 8653).
        self.assertEqual(
            _relations(paths[0]),
            [
                (dc.PARENT, "T"),
                (dc.SPOUSE, "S"),
                (dc.SIBLING, "W"),
                (dc.SELF, "D"),
            ],
        )

    def test_parents_of_the_family_are_recorded(self):
        path = next(dc.find_connections(_in_law_db(), "D", "P"))
        step = dc.path_steps(path)[0]
        self.assertEqual(step.parents, (None,))  # FP has no mother

    def test_start_equals_target(self):
        paths = list(dc.find_connections(_in_law_db(), "D", "D"))
        self.assertEqual([_relations(p) for p in paths], [[(dc.SELF, "D")]])

    def test_no_connection(self):
        db = _in_law_db()
        db._people["X"] = _Person("X")
        self.assertEqual(list(dc.find_connections(db, "D", "X")), [])

    def test_hidden_person_is_not_passed_through(self):
        # A privacy proxy returns None for a hidden person; the only
        # connection to P goes through S, so hiding S must hide it.
        db = _in_law_db()
        del db._people["S"]
        self.assertEqual(list(dc.find_connections(db, "D", "P")), [])

    def test_people_are_queued_once(self):
        # Parents P1/P2 with four children; X is unreachable, so the search
        # processes everyone it can reach.  Each child is reached from both
        # parents and from three siblings; every person must still be
        # processed only once.
        families = {
            "F": _Family(
                "F", father="P1", mother="P2", children=["C1", "C2", "C3", "C4"]
            )
        }
        people = {h: _Person(h, families=["F"]) for h in ("P1", "P2")}
        people.update(
            {h: _Person(h, parent_families=["F"]) for h in ("C1", "C2", "C3", "C4")}
        )
        people["X"] = _Person("X")
        search = dc.ConnectionSearch(_DB(people, families), "C1", "X")
        for _path in search.steps():
            pass
        self.assertEqual(search.people_processed, 6)
        self.assertEqual(search.visited, {"P1", "P2", "C1", "C2", "C3", "C4"})

    def test_max_people_stops_the_search(self):
        paths = list(dc.find_connections(_in_law_db(), "D", "P", max_people=2))
        self.assertEqual(paths, [])

    def test_max_paths(self):
        families = {
            "FDX": _Family("FDX", father="D", children=["X"]),
            "FDY": _Family("FDY", father="D", children=["Y"]),
            "FX": _Family("FX", father="X", children=["A"]),
            "FY": _Family("FY", father="Y", children=["A"]),
        }
        people = {
            "D": _Person("D", families=["FDX", "FDY"]),
            "X": _Person("X", families=["FX"], parent_families=["FDX"]),
            "Y": _Person("Y", families=["FY"], parent_families=["FDY"]),
            "A": _Person("A", parent_families=["FX", "FY"]),
        }
        db = _DB(people, families)
        self.assertEqual(len(list(dc.find_connections(db, "D", "A"))), 2)
        self.assertEqual(len(list(dc.find_connections(db, "D", "A", max_paths=1))), 1)


class TestOptionalLinks(unittest.TestCase):
    def _db(self):
        people = {
            "D": _Person("D", assocs=[_PersonRef("G", "Godfather")], notes=["N1"]),
            "G": _Person("G"),
            "M": _Person("M"),
        }
        return _DB(people, {}, notes={"N1": _Note(["M"])})

    def test_association(self):
        path = next(dc.find_connections(self._db(), "D", "G"))
        self.assertEqual(path[1].relation, dc.SELF)  # attached to the root
        relatives = dc.get_relatives(self._db(), "D", "root")
        assoc = [path for handle, path in relatives if handle == "G"][0]
        self.assertEqual(assoc[1].relation, dc.ASSOCIATION)
        self.assertEqual(assoc[1].detail, "Godfather")

    def test_note_link(self):
        relatives = dc.get_relatives(self._db(), "D", "root")
        note = [path for handle, path in relatives if handle == "M"][0]
        self.assertEqual(note[1].relation, dc.NOTE)

    def test_associations_and_notes_can_be_turned_off(self):
        db = self._db()
        self.assertEqual(
            list(dc.find_connections(db, "D", "G", follow_associations=False)), []
        )
        self.assertEqual(
            list(dc.find_connections(db, "D", "M", follow_notes=False)), []
        )


if __name__ == "__main__":
    unittest.main()
