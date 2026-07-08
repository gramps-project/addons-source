"""
Tests for datadict2.py — DataDict2, DataList2, and NoneData.

Uses real Gramps gen-lib objects (no GTK required).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gramps.gen.lib import Person, Name, Surname, Family, NameOriginType
from gramps.gen.simple import SimpleAccess

from datadict2 import DataDict2, DataList2, NoneData, set_sa


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_person(gramps_id="I0001", first="John", surname="Smith"):
    p = Person()
    p.set_gramps_id(gramps_id)
    n = Name()
    sn = Surname()
    sn.set_surname(surname)
    n.add_surname(sn)
    n.set_first_name(first)
    p.set_primary_name(n)
    return p


def _make_family(gramps_id="F0001"):
    f = Family()
    f.set_gramps_id(gramps_id)
    return f


class _MockSaBase(unittest.TestCase):
    """Base class that sets up a minimal SimpleAccess mock before each test."""

    def setUp(self):
        db = MagicMock()
        db.get_event_from_handle.return_value = None
        db.get_place_from_handle.return_value = None
        db.get_source_from_handle.return_value = None
        # Mirror DbGeneric.method()'s real dispatch (getattr on a formatted,
        # lowercased method name), since a bare MagicMock doesn't do this.
        db.method.side_effect = lambda fmt, *args: getattr(
            db, fmt % tuple(a.lower() for a in args), None
        )
        self.db = db
        sa = SimpleAccess(db)
        set_sa(sa)


# ---------------------------------------------------------------------------
# NoneData
# ---------------------------------------------------------------------------

class TestNoneData(unittest.TestCase):
    def test_is_falsy(self):
        self.assertFalse(NoneData())

    def test_str_is_empty(self):
        self.assertEqual(str(NoneData()), "")

    def test_attribute_chain_returns_none_data(self):
        result = NoneData().foo.bar.baz
        self.assertIsInstance(result, NoneData)

    def test_callable_returns_empty_string(self):
        self.assertEqual(NoneData()(), "")

    def test_iter_yields_nothing(self):
        self.assertEqual(list(NoneData()), [])


# ---------------------------------------------------------------------------
# DataDict2 — basic attribute access
# ---------------------------------------------------------------------------

class TestDataDict2BasicAccess(_MockSaBase):
    def test_gramps_id_via_attribute(self):
        dd = DataDict2(_make_person(gramps_id="I0042"))
        self.assertEqual(dd.gramps_id, "I0042")

    def test_class_key(self):
        dd = DataDict2(_make_person())
        self.assertEqual(dd["_class"], "Person")

    def test_missing_key_returns_none_data(self):
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.nonexistent_field, NoneData)

    def test_nested_dict_wraps_as_datadict2(self):
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.primary_name, DataDict2)

    def test_nested_list_wraps_as_datalist2(self):
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.primary_name.surname_list, DataList2)

    def test_scalar_returned_directly(self):
        dd = DataDict2(_make_person(gramps_id="I0001"))
        self.assertIsInstance(dd.gramps_id, str)


# ---------------------------------------------------------------------------
# DataDict2 — genealogy properties
# ---------------------------------------------------------------------------

class TestDataDict2GenealogyProperties(_MockSaBase):
    def test_name_property_returns_primary_name_for_person(self):
        dd = DataDict2(_make_person())
        self.assertEqual(dd.name, dd.primary_name)

    def test_name_first_name(self):
        dd = DataDict2(_make_person(first="Alice"))
        self.assertEqual(dd.name.first_name, "Alice")

    def test_surname_via_surname_list(self):
        dd = DataDict2(_make_person(surname="Jones"))
        self.assertEqual(dd.name.surname_list[0].surname, "Jones")

    def test_birth_returns_none_data_when_absent(self):
        dd = DataDict2(_make_person())
        self.assertFalse(dd.birth)

    def test_death_returns_none_data_when_absent(self):
        dd = DataDict2(_make_person())
        self.assertFalse(dd.death)

    def test_birth_chain_attribute_access_is_safe(self):
        # Attribute chaining on NoneData is safe — returns falsy NoneData each step.
        dd = DataDict2(_make_person())
        self.assertFalse(dd.birth)
        self.assertFalse(dd.birth.date)

    def test_birth_guard_before_method_call(self):
        # Always guard with `if birth:` before calling methods on it.
        dd = DataDict2(_make_person())
        birth = dd.birth
        year = birth.get_date_object().get_year() if birth else 0
        self.assertEqual(year, 0)

    def test_notes_is_list(self):
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.notes, (list, DataList2))

    def test_tags_is_list(self):
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.tags, (list, DataList2))

    def test_citations_is_list(self):
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.citations, (list, DataList2))

    def test_private_default_false(self):
        dd = DataDict2(_make_person())
        self.assertEqual(dd.private, False)

    def test_family_gramps_id(self):
        dd = DataDict2(_make_family(gramps_id="F0007"))
        self.assertEqual(dd.gramps_id, "F0007")
        self.assertEqual(dd["_class"], "Family")

    def test_names_includes_alternate_names_in_order(self):
        # Regression: `names` was `[self.primary_name] + [self.alternate_names]`
        # -- the extra brackets nested the whole alternate_names list as one
        # element instead of spreading it in, and __radd__ used to reverse
        # the order on top of that.
        p = _make_person(first="John")
        alt = Name()
        alt_sn = Surname()
        alt_sn.set_surname("Doe")
        alt.add_surname(alt_sn)
        alt.set_first_name("Jack")
        p.add_alternate_name(alt)
        dd = DataDict2(p)
        self.assertEqual(len(dd.names), 2)
        self.assertEqual([n.first_name for n in dd.names], ["John", "Jack"])


# ---------------------------------------------------------------------------
# DataDict2 — surname/name/reference on non-Person and *Ref wrappers
# ---------------------------------------------------------------------------


class TestDataDict2NonPersonProperties(_MockSaBase):
    def test_surname_is_none_data_for_non_person(self):
        # Regression: used to raise KeyError via self["surname"], since no
        # schema has a top-level "surname" field.
        dd = DataDict2(_make_family())
        self.assertIsInstance(dd.surname, NoneData)

    def test_name_is_none_data_when_field_absent(self):
        # Regression: used to raise KeyError via self["name"] for classes
        # (like Family) with no "name" schema field.
        dd = DataDict2(_make_family())
        self.assertIsInstance(dd.name, NoneData)

    def test_reference_dispatches_by_class(self):
        # Regression: used to always call get_raw_person_data regardless of
        # which *Ref type was wrapped.
        from gramps.gen.lib import PersonRef
        from gramps.gen.lib.json_utils import object_to_dict

        ref = PersonRef()
        ref.set_reference_handle("HANDLE1")
        self.db.get_raw_person_data.return_value = object_to_dict(
            _make_person(gramps_id="I9999")
        )
        dd = DataDict2(ref)
        self.assertEqual(dd.reference.gramps_id, "I9999")
        self.db.get_raw_person_data.assert_called_with("HANDLE1")

    def test_reference_none_data_for_unmapped_class(self):
        dd = DataDict2(_make_family())
        self.assertIsInstance(dd.reference, NoneData)


# ---------------------------------------------------------------------------
# DataDict2 — null-safe chaining
# ---------------------------------------------------------------------------

class TestDataDict2NullSafeChaining(_MockSaBase):
    def test_missing_birth_place_title_is_safe(self):
        dd = DataDict2(_make_person())
        result = dd.birth.place.title
        self.assertTrue(not result or isinstance(result, (str, NoneData)))

    def test_none_data_in_chain_stays_falsy(self):
        dd = DataDict2(_make_person())
        self.assertFalse(dd.birth)
        self.assertFalse(dd.birth.date)
        self.assertFalse(dd.birth.date.dateval)

    def test_non_existent_deeply_nested(self):
        dd = DataDict2(_make_person())
        self.assertFalse(dd.a.b.c.d.e)


# ---------------------------------------------------------------------------
# DataList2
# ---------------------------------------------------------------------------

class TestDataList2(_MockSaBase):
    def _make_list(self):
        p1 = DataDict2(_make_person(gramps_id="I0001", first="Alice"))
        p2 = DataDict2(_make_person(gramps_id="I0002", first="Bob"))
        return DataList2([p1, p2])

    def test_len(self):
        self.assertEqual(len(self._make_list()), 2)

    def test_getitem_wraps_dict(self):
        self.assertIsInstance(self._make_list()[0], DataDict2)

    def test_getitem_out_of_range_returns_none_data(self):
        self.assertIsInstance(self._make_list()[99], NoneData)

    def test_iter_yields_all_items(self):
        self.assertEqual(len(list(self._make_list())), 2)

    def test_getattr_fans_out_across_items(self):
        ids = self._make_list().gramps_id
        self.assertIn("I0001", ids)
        self.assertIn("I0002", ids)

    def test_add_concatenates(self):
        dl1 = DataList2([DataDict2(_make_person(gramps_id="I0001"))])
        dl2 = DataList2([DataDict2(_make_person(gramps_id="I0002"))])
        self.assertEqual(len(dl1 + dl2), 2)

    def test_radd_preserves_order(self):
        # Regression: __radd__ used to return `self + value` instead of
        # `value + self`, so `plain_list + data_list2` (the pattern used to
        # loop over primary + alternate names) came out reversed.
        dl = DataList2([DataDict2(_make_person(gramps_id="I0002"))])
        combined = [DataDict2(_make_person(gramps_id="I0001"))] + dl
        self.assertEqual([p.gramps_id for p in combined], ["I0001", "I0002"])

    def test_empty_list(self):
        dl = DataList2([])
        self.assertEqual(len(dl), 0)
        self.assertEqual(list(dl), [])


# ---------------------------------------------------------------------------
# DataDict2 — mutation (attribute assignment and set_*() methods)
# ---------------------------------------------------------------------------

class TestDataDict2Mutation(_MockSaBase):
    def test_top_level_attribute_assignment(self):
        dd = DataDict2(_make_person(gramps_id="I0001"))
        dd.gramps_id = "I9999"
        self.assertEqual(dd._object.get_gramps_id(), "I9999")
        self.assertEqual(dd.gramps_id, "I9999")

    def test_nested_attribute_assignment_updates_real_object(self):
        # Regression: assigning through a nested wrapper (primary_name is
        # not the root) must mutate the real Person's Name object, not a
        # disconnected copy.
        dd = DataDict2(_make_person(first="John"))
        dd.primary_name.first_name = "Zoe"
        self.assertEqual(dd._object.get_primary_name().get_first_name(), "Zoe")
        self.assertEqual(dd.primary_name.first_name, "Zoe")

    def test_nested_set_method_updates_real_object(self):
        # Regression: calling a set_*() method on a nested wrapper (e.g. a
        # Surname inside primary_name.surname_list) used to run against a
        # standalone object rebuilt from that wrapper's own dict slice, so
        # the mutation never reached the real Person and was lost on commit.
        dd = DataDict2(_make_person(surname="Smith"))
        surname = dd.primary_name.surname_list[0]
        surname.set_surname("Jones")
        real_surname = dd._object.get_primary_name().get_surname_list()[0]
        self.assertEqual(real_surname.get_surname(), "Jones")
        self.assertEqual(dd.primary_name.surname_list[0].surname, "Jones")

    def test_nested_set_method_calls_callback_with_root(self):
        callback = MagicMock()
        dd = DataDict2(_make_person(surname="Smith"), callback=callback)
        surname = dd.primary_name.surname_list[0]
        surname.set_surname("Jones")
        callback.assert_called_once_with("set", dd)

    def test_concatenated_name_list_assignment_updates_real_object(self):
        # Regression: `[dd.primary_name] + dd.alternate_names` (the pattern
        # used to loop over all of a person's names) goes through
        # DataList2.__radd__, which builds a plain list of already-wrapped
        # DataDict2 items and re-wraps it in a new DataList2. Iterating that
        # outer DataList2 used to re-wrap each *already-wrapped* item via
        # __getitem__, discarding its real root/path and replacing it with
        # root=self (since the outer list has root=None), producing a
        # DataDict2 whose root is itself but whose path is non-empty --
        # an inconsistent state that made attribute assignment recurse
        # into itself trying to resolve `self.root._object`.
        dd = DataDict2(_make_person(surname="Smith"))
        for name in [dd.primary_name] + dd.alternate_names:
            self.assertIs(name.root, dd)
            for surname in name.surname_list:
                surname.set_surname("Jones")
        real = dd._object.get_primary_name().get_surname_list()[0]
        self.assertEqual(real.get_surname(), "Jones")


# ---------------------------------------------------------------------------
# DataDict2 — .string for GrampsType-based fields (NameOriginType, ...)
# ---------------------------------------------------------------------------

class TestDataDict2TypeString(_MockSaBase):
    def test_origintype_string_reflects_predefined_value(self):
        # Regression: the raw "string" field only holds the *custom*-type
        # override text, which is always "" for predefined values like
        # PATRILINEAL. `.string` must return the real, computed label
        # instead of that raw (and misleadingly empty) field.
        dd = DataDict2(_make_person(surname="Smith"))
        surname = dd.primary_name.surname_list[0]
        surname.set_origintype(NameOriginType.PATRILINEAL)
        self.assertEqual(dd.primary_name.surname_list[0].origintype.string, "Patrilineal")

    def test_origintype_string_empty_for_none(self):
        dd = DataDict2(_make_person())
        self.assertEqual(dd.primary_name.surname_list[0].origintype.string, "")

    def test_string_missing_field_falls_back_normally(self):
        # A DataDict2 with no "string" key at all (e.g. a Name) must not be
        # affected by the .string property -- it should fall through to
        # ordinary attribute lookup rather than raising or returning "".
        dd = DataDict2(_make_person())
        self.assertIsInstance(dd.primary_name.string, NoneData)


if __name__ == "__main__":
    unittest.main()
