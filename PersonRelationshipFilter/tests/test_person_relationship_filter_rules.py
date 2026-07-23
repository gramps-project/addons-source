#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Doug Blank <doug.blank@gmail.com>
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
Unit tests for the relationship-matching filter rules defined in
``PersonRelationshipFilter.py``.

The tests build a small family tree directly in an in-memory database
(no dependency on the shared ``example.gramps`` fixture) so each
rule's relationship traversal and name-field matching can be checked
precisely. Two regressions are covered explicitly:

* ``IsSiblingofNamedSibling`` used to raise ``HandleError`` when
  applied to a person with no recorded parents, because
  ``get_family_from_handle(None)`` raises rather than returning
  ``None``.
* ``RegExpPersonal``/``RegExpFamily`` searched mismatched ``Name``
  fields (``title`` was listed twice in the personal field list, and
  ``call`` name was searched by the family/surname rule instead), so
  personal search never matched a person's call name and surname
  search could false-positive on an unrelated title or call name.
"""

# ------------------------
# Python modules
# ------------------------
import os
import sys
import unittest

# ------------------------
# Gramps modules
# ------------------------
# The addon directory goes on sys.path so ``import PersonRelationshipFilter``
# resolves the flat ``PersonRelationshipFilter.py`` module directly (there is
# no wrapping package — the file lives right in the addon directory).
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps
except ImportError as err:
    raise unittest.SkipTest("gramps package not available: %s" % err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

try:
    from gramps.gen.db import DbTxn
    from gramps.gen.db.utils import make_database
    from gramps.gen.lib import ChildRef, Family, Name, Person, Surname

    from PersonRelationshipFilter import (
        HasName,
        HasNamedChild,
        HasNamedFather,
        HasNamedMother,
        HasNamedSpouse,
        IsSiblingofNamedSibling,
        RegExpFamily,
        RegExpPersonal,
    )
except Exception as err:  # noqa: BLE001 — environment guard
    raise unittest.SkipTest("PersonRelationshipFilter module unavailable: %s" % err)


def _make_name(first, surname, call="", nick="", title="", famnick=""):
    """Build a Name with the given given/surname plus the secondary fields
    under test (call name, nickname, title, family nickname)."""
    name = Name()
    name.set_first_name(first)
    name.set_call_name(call)
    name.set_nick_name(nick)
    name.set_title(title)
    name.famnick = famnick
    surname_obj = Surname()
    surname_obj.set_surname(surname)
    name.set_surname_list([surname_obj])
    return name


def _make_database():
    db = make_database("sqlite")
    db.load(":memory:")
    return db


class PersonRelationshipFilterRulesTest(unittest.TestCase):
    """
    Exercises the rules against a small, precisely-built family tree::

        Frank Farnsworth (father) + Martha Miller (mother)
            -> Carol Farnsworth (call "Caz", nick "Care", title "Dr.",
                                  family nickname "Farns")
            -> Dan Farnsworth
        Carol Farnsworth + Sam Smith (spouse)
        Owen Orphanage -- no recorded parents
    """

    @classmethod
    def setUpClass(cls):
        cls.db = _make_database()
        with DbTxn("build test tree", cls.db) as trans:
            father = Person()
            father.set_gender(Person.MALE)
            father.set_primary_name(_make_name("Frank", "Farnsworth"))
            father_handle = cls.db.add_person(father, trans)

            mother = Person()
            mother.set_gender(Person.FEMALE)
            mother.set_primary_name(_make_name("Martha", "Miller"))
            mother_handle = cls.db.add_person(mother, trans)

            carol = Person()
            carol.set_gender(Person.FEMALE)
            carol.set_primary_name(
                _make_name(
                    "Carol",
                    "Farnsworth",
                    call="Caz",
                    nick="Care",
                    title="Dr.",
                    famnick="Farns",
                )
            )
            carol_handle = cls.db.add_person(carol, trans)

            dan = Person()
            dan.set_gender(Person.MALE)
            dan.set_primary_name(_make_name("Dan", "Farnsworth"))
            dan_handle = cls.db.add_person(dan, trans)

            orphan = Person()
            orphan.set_gender(Person.MALE)
            orphan.set_primary_name(_make_name("Owen", "Orphanage"))
            orphan_handle = cls.db.add_person(orphan, trans)

            spouse = Person()
            spouse.set_gender(Person.MALE)
            spouse.set_primary_name(_make_name("Sam", "Smith"))
            spouse_handle = cls.db.add_person(spouse, trans)

            parent_family = Family()
            parent_family.set_father_handle(father_handle)
            parent_family.set_mother_handle(mother_handle)
            for child_handle in (carol_handle, dan_handle):
                child_ref = ChildRef()
                child_ref.set_reference_handle(child_handle)
                parent_family.add_child_ref(child_ref)
            parent_family_handle = cls.db.add_family(parent_family, trans)

            father.add_family_handle(parent_family_handle)
            mother.add_family_handle(parent_family_handle)
            carol.add_parent_family_handle(parent_family_handle)
            dan.add_parent_family_handle(parent_family_handle)

            marriage = Family()
            marriage.set_father_handle(spouse_handle)
            marriage.set_mother_handle(carol_handle)
            marriage_handle = cls.db.add_family(marriage, trans)
            spouse.add_family_handle(marriage_handle)
            carol.add_family_handle(marriage_handle)

            for person in (father, mother, carol, dan, orphan, spouse):
                cls.db.commit_person(person, trans)

        cls.father = cls.db.get_person_from_handle(father_handle)
        cls.mother = cls.db.get_person_from_handle(mother_handle)
        cls.carol = cls.db.get_person_from_handle(carol_handle)
        cls.dan = cls.db.get_person_from_handle(dan_handle)
        cls.orphan = cls.db.get_person_from_handle(orphan_handle)
        cls.spouse = cls.db.get_person_from_handle(spouse_handle)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.db = None

    def _match_name(self, matcher_class, value, person, use_regex=False):
        """Apply a bare RegExpPersonal/RegExpFamily rule to one person."""
        rule = matcher_class([value], use_regex=use_regex)
        rule.requestprepare(self.db, None)
        try:
            return rule.apply_to_one(self.db, person)
        finally:
            rule.requestreset()

    def _match_relation(self, rule_class, value, person, matcher_class=RegExpPersonal):
        """Apply a _HasNamedRelation rule (Father/Mother/Sibling/Child/Spouse)
        to one person."""
        rule = rule_class([value], matcher_class, use_regex=False)
        rule.requestprepare(self.db, None)
        try:
            return rule.apply_to_one(self.db, person)
        finally:
            rule.requestreset()

    # -- name field matching --------------------------------------------

    def test_personal_matches_first_name(self):
        self.assertTrue(self._match_name(RegExpPersonal, "Carol", self.carol))

    def test_personal_matches_call_name(self):
        """Regression: the personal field list used to list 'title' twice
        instead of including the call name."""
        self.assertTrue(self._match_name(RegExpPersonal, "Caz", self.carol))

    def test_personal_matches_nick_name(self):
        self.assertTrue(self._match_name(RegExpPersonal, "Care", self.carol))

    def test_personal_matches_title(self):
        self.assertTrue(self._match_name(RegExpPersonal, "Dr", self.carol))

    def test_personal_does_not_match_surname(self):
        self.assertFalse(self._match_name(RegExpPersonal, "Farnsworth", self.carol))

    def test_family_matches_surname(self):
        self.assertTrue(self._match_name(RegExpFamily, "Farnsworth", self.carol))

    def test_family_matches_famnick(self):
        self.assertTrue(self._match_name(RegExpFamily, "Farns", self.carol))

    def test_family_does_not_match_title(self):
        """Regression: the family/surname field list used to include the
        personal title field, causing false-positive surname matches."""
        self.assertFalse(self._match_name(RegExpFamily, "Dr", self.carol))

    def test_family_does_not_match_call_name(self):
        """Regression: the family/surname field list used to include the
        personal call name field, causing false-positive surname matches."""
        self.assertFalse(self._match_name(RegExpFamily, "Caz", self.carol))

    def test_regex_mode_matches_pattern(self):
        self.assertTrue(
            self._match_name(RegExpPersonal, "^Car", self.carol, use_regex=True)
        )
        self.assertFalse(
            self._match_name(RegExpPersonal, "^ar", self.carol, use_regex=True)
        )

    # -- relationship traversal ------------------------------------------

    def test_has_named_father(self):
        self.assertTrue(self._match_relation(HasNamedFather, "Frank", self.carol))
        self.assertFalse(self._match_relation(HasNamedFather, "Nobody", self.carol))

    def test_has_named_mother(self):
        self.assertTrue(self._match_relation(HasNamedMother, "Martha", self.carol))

    def test_has_named_child(self):
        self.assertTrue(self._match_relation(HasNamedChild, "Carol", self.father))
        self.assertTrue(self._match_relation(HasNamedChild, "Dan", self.mother))

    def test_has_named_spouse(self):
        self.assertTrue(self._match_relation(HasNamedSpouse, "Sam", self.carol))
        self.assertFalse(self._match_relation(HasNamedSpouse, "Frank", self.carol))

    def test_is_sibling_of_named_sibling(self):
        self.assertTrue(
            self._match_relation(IsSiblingofNamedSibling, "Dan", self.carol)
        )
        self.assertTrue(
            self._match_relation(IsSiblingofNamedSibling, "Carol", self.dan)
        )

    def test_is_sibling_of_named_sibling_excludes_self(self):
        self.assertFalse(
            self._match_relation(IsSiblingofNamedSibling, "Carol", self.carol)
        )

    def test_is_sibling_of_named_sibling_with_no_parents_does_not_crash(self):
        """Regression: applying this rule to a person with no recorded
        parents used to raise HandleError from
        get_family_from_handle(None)."""
        self.assertFalse(
            self._match_relation(IsSiblingofNamedSibling, "Anyone", self.orphan)
        )

    def test_has_name_matches_own_name(self):
        self.assertTrue(self._match_relation(HasName, "Carol", self.carol))

    def test_has_name_female_family_search_trawls_spouse_surname(self):
        """A female's own family/surname search also matches her spouse's
        surname (so 'Person' search finds her under her married name)."""
        self.assertTrue(
            self._match_relation(
                HasName, "Smith", self.carol, matcher_class=RegExpFamily
            )
        )
        self.assertFalse(
            self._match_relation(
                HasName, "Smith", self.father, matcher_class=RegExpFamily
            )
        )


if __name__ == "__main__":
    unittest.main()
