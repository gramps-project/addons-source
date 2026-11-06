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
Tests for how the Deep Connections Gramplet words a found path.

* The root ("self") step must never be printed, whatever the UI language.
  It used to be recognized by comparing its *translated* text with the
  English "self", so in a translated UI (e.g. German "selbst") every path
  ended with an extra "selbst of <Home person>" line.
* "father"/"mother" and "husband"/"wife" come from the person's recorded
  gender, not from which slot of the family they are in, and fall back to
  "parent"/"spouse" when the gender is unknown.

These drive the gramplet's real ``pretty_print`` with the GUI output
(``append_text``/``link``) captured, as in test_deep_connections.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The addon directory and its implementation module share a name; use the
# explicit submodule path (same trap noted in libaccess / gramps bug 0012691).
from DeepConnectionsGramplet import DeepConnectionsGramplet as dcg_mod
from gramps.gen.lib import Person

import deep_connections as dc


class _Person:
    def __init__(self, handle, gender):
        self.handle = handle
        self._gender = gender

    def get_primary_name(self):
        return self.handle

    def get_gender(self):
        return self._gender


class _DB:
    def __init__(self, people):
        self._people = {p.handle: p for p in people}

    def get_person_from_handle(self, handle):
        return self._people.get(handle)


class _DBState:
    def __init__(self, db):
        self.db = db


class _StubRelCalc:
    def get_one_relationship(self, db, person1, person2):
        return ""


class _StubNameDisplayer:
    def display_name(self, name):
        return str(name)


class _Harness(dcg_mod.DeepConnectionsGramplet):
    """The real ``pretty_print``, with its text output captured."""

    def __init__(self, db):
        # Deliberately do NOT call Gramplet.__init__ (no GUI / GTK).
        self.dbstate = _DBState(db)
        self.default_person = None
        self.selected_handles = set()
        self.relationship_calc = _StubRelCalc()
        self.text = ""

    def append_text(self, text):
        self.text += text

    def link(self, text, _kind, _handle):
        self.text += text

    def relationship_text(self, handle):
        return ""


def _path(*steps):
    """Build a path from steps listed root first."""
    node = None
    for step in steps:
        node = (node, step)
    return node


class TestPathWording(unittest.TestCase):
    def setUp(self):
        self._displayer = dcg_mod.name_displayer
        dcg_mod.name_displayer = _StubNameDisplayer()

    def tearDown(self):
        dcg_mod.name_displayer = self._displayer

    def _print(self, people, path, gender):
        harness = _Harness(_DB(people))
        harness.pretty_print(path, gender)
        return harness.text

    def test_root_is_not_printed_in_a_translated_ui(self):
        # Home "H" is the parent of "C"; the active person is C's child.
        people = [_Person("H", Person.MALE), _Person("C", Person.FEMALE)]
        path = _path(dc.Step(dc.SELF, "H"), dc.Step(dc.CHILD, "C"))
        original = dcg_mod._
        dcg_mod._ = lambda text: "<" + text + ">"  # every string "translated"
        try:
            text = self._print(people, path, Person.MALE)
        finally:
            dcg_mod._ = original
        # Only the one real step is printed; the root adds nothing.
        self.assertEqual(text.count("\n"), 1, text)
        self.assertNotIn("self", text)
        self.assertNotIn("H", text)

    def test_parent_and_spouse_follow_recorded_gender(self):
        # The step's relation describes the person printed before it, whose
        # gender is passed in; a woman in a family's father slot is a mother.
        people = [_Person("A", Person.MALE)]
        for relation, gender, expected in (
            (dc.PARENT, Person.MALE, "father of A"),
            (dc.PARENT, Person.FEMALE, "mother of A"),
            (dc.PARENT, Person.UNKNOWN, "parent of A"),
            (dc.SPOUSE, Person.MALE, "husband of A"),
            (dc.SPOUSE, Person.FEMALE, "wife of A"),
            (dc.SPOUSE, Person.UNKNOWN, "spouse of A"),
            (dc.CHILD, Person.FEMALE, "child of A"),
            (dc.SIBLING, Person.MALE, "sibling of A"),
        ):
            with self.subTest(relation=relation, gender=gender):
                text = self._print(people, _path(dc.Step(relation, "A")), gender)
                self.assertEqual(text.strip(), expected)

    def test_gender_of_each_step_comes_from_the_person_before_it(self):
        # Active person (female) is the mother of M (male), M is the
        # husband of W, W is attached to the root.
        people = [_Person("M", Person.MALE), _Person("W", Person.FEMALE)]
        path = _path(
            dc.Step(dc.SELF, "R"),
            dc.Step(dc.SPOUSE, "W"),
            dc.Step(dc.PARENT, "M"),
        )
        text = self._print(people, path, Person.FEMALE)
        self.assertEqual(
            [line.strip() for line in text.strip().split("\n")],
            ["mother of M", "husband of W"],
        )


if __name__ == "__main__":
    unittest.main()
