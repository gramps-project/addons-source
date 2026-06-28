"""
Tests for datadict2.py — DataDict2, DataList2, and NoneData.

Uses real Gramps gen-lib objects (no GTK required).
"""

import pytest
from unittest.mock import MagicMock

from gramps.gen.lib import Person, Name, Surname, Family, Event, EventRef, EventType
from gramps.gen.simple import SimpleAccess

from datadict2 import DataDict2, DataList2, NoneData, set_sa


# ---------------------------------------------------------------------------
# Fixture: minimal SimpleAccess so property methods don't crash
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_sa():
    db = MagicMock()
    db.get_event_from_handle.return_value = None   # no birth/death events
    db.get_place_from_handle.return_value = None
    db.get_source_from_handle.return_value = None
    sa = SimpleAccess(db)
    set_sa(sa)
    yield sa


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


# ---------------------------------------------------------------------------
# NoneData
# ---------------------------------------------------------------------------

class TestNoneData:
    def test_is_falsy(self):
        assert not NoneData()

    def test_str_is_empty(self):
        assert str(NoneData()) == ""

    def test_attribute_chain_returns_none_data(self):
        result = NoneData().foo.bar.baz
        assert isinstance(result, NoneData)

    def test_callable_returns_empty_string(self):
        assert NoneData()() == ""

    def test_iter_yields_nothing(self):
        assert list(NoneData()) == []


# ---------------------------------------------------------------------------
# DataDict2 — basic attribute access
# ---------------------------------------------------------------------------

class TestDataDict2BasicAccess:
    def test_gramps_id_via_attribute(self):
        dd = DataDict2(_make_person(gramps_id="I0042"))
        assert dd.gramps_id == "I0042"

    def test_class_key(self):
        dd = DataDict2(_make_person())
        assert dd["_class"] == "Person"

    def test_missing_key_returns_none_data(self):
        dd = DataDict2(_make_person())
        result = dd.nonexistent_field
        assert isinstance(result, NoneData)

    def test_nested_dict_wraps_as_datadict2(self):
        dd = DataDict2(_make_person())
        # primary_name is a dict in the serialised form
        assert isinstance(dd.primary_name, DataDict2)

    def test_nested_list_wraps_as_datalist2(self):
        dd = DataDict2(_make_person())
        assert isinstance(dd.primary_name.surname_list, DataList2)

    def test_scalar_returned_directly(self):
        dd = DataDict2(_make_person(gramps_id="I0001"))
        assert isinstance(dd.gramps_id, str)


# ---------------------------------------------------------------------------
# DataDict2 — genealogy properties
# ---------------------------------------------------------------------------

class TestDataDict2GenealogyProperties:
    def test_name_property_returns_primary_name_for_person(self):
        dd = DataDict2(_make_person())
        assert dd.name == dd.primary_name

    def test_name_first_name(self):
        dd = DataDict2(_make_person(first="Alice"))
        assert dd.name.first_name == "Alice"

    def test_surname_via_surname_list(self):
        dd = DataDict2(_make_person(surname="Jones"))
        assert dd.name.surname_list[0].surname == "Jones"

    def test_birth_returns_none_data_when_absent(self):
        dd = DataDict2(_make_person())
        assert not dd.birth

    def test_death_returns_none_data_when_absent(self):
        dd = DataDict2(_make_person())
        assert not dd.death

    def test_birth_chain_attribute_access_is_safe(self):
        # Attribute chaining on NoneData is safe — returns falsy NoneData each step.
        dd = DataDict2(_make_person())
        assert not dd.birth          # NoneData
        assert not dd.birth.date     # still NoneData

    def test_birth_guard_before_method_call(self):
        # NoneData().__call__ returns "", not NoneData, so calling methods on the
        # result of a method call is not safe. Always guard with `if birth:` first.
        dd = DataDict2(_make_person())
        birth = dd.birth
        year = birth.get_date_object().get_year() if birth else 0
        assert year == 0

    def test_notes_is_list(self):
        dd = DataDict2(_make_person())
        assert isinstance(dd.notes, (list, DataList2))

    def test_tags_is_list(self):
        dd = DataDict2(_make_person())
        assert isinstance(dd.tags, (list, DataList2))

    def test_citations_is_list(self):
        dd = DataDict2(_make_person())
        assert isinstance(dd.citations, (list, DataList2))

    def test_private_default_false(self):
        dd = DataDict2(_make_person())
        assert dd.private == False

    def test_family_gramps_id(self):
        dd = DataDict2(_make_family(gramps_id="F0007"))
        assert dd.gramps_id == "F0007"
        assert dd["_class"] == "Family"


# ---------------------------------------------------------------------------
# DataDict2 — null-safe chaining
# ---------------------------------------------------------------------------

class TestDataDict2NullSafeChaining:
    def test_missing_birth_place_title_is_safe(self):
        dd = DataDict2(_make_person())
        result = dd.birth.place.title
        # Must not raise; returns "" or NoneData
        assert not result or isinstance(result, (str, NoneData))

    def test_none_data_in_chain_stays_falsy(self):
        dd = DataDict2(_make_person())
        assert not dd.birth
        assert not dd.birth.date
        assert not dd.birth.date.dateval

    def test_non_existent_deeply_nested(self):
        dd = DataDict2(_make_person())
        result = dd.a.b.c.d.e
        assert not result


# ---------------------------------------------------------------------------
# DataList2
# ---------------------------------------------------------------------------

class TestDataList2:
    def _make_list(self):
        p1 = DataDict2(_make_person(gramps_id="I0001", first="Alice"))
        p2 = DataDict2(_make_person(gramps_id="I0002", first="Bob"))
        return DataList2([p1, p2])

    def test_len(self):
        dl = self._make_list()
        assert len(dl) == 2

    def test_getitem_wraps_dict(self):
        dl = self._make_list()
        assert isinstance(dl[0], DataDict2)

    def test_getitem_out_of_range_returns_none_data(self):
        dl = self._make_list()
        assert isinstance(dl[99], NoneData)

    def test_iter_yields_all_items(self):
        dl = self._make_list()
        items = list(dl)
        assert len(items) == 2

    def test_getattr_fans_out_across_items(self):
        dl = self._make_list()
        ids = dl.gramps_id
        assert "I0001" in ids
        assert "I0002" in ids

    def test_add_concatenates(self):
        dl1 = DataList2([DataDict2(_make_person(gramps_id="I0001"))])
        dl2 = DataList2([DataDict2(_make_person(gramps_id="I0002"))])
        combined = dl1 + dl2
        assert len(combined) == 2

    def test_empty_list(self):
        dl = DataList2([])
        assert len(dl) == 0
        assert list(dl) == []
