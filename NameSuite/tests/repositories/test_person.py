from unittest.mock import Mock
import pytest

from name_processor.repositories.person import GrampsPersonProxy
from name_processor.models.person import Gender


# Mocking Gramps constants used in the proxy
class MockGrampsPerson:
    MALE = 0
    FEMALE = 1


class MockNameOriginType:
    PATRONYMIC = 2
    GIVEN = 0


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def mock_gramps_person():
    person = Mock()
    person.get_handle.return_value = "p123"
    return person


@pytest.fixture
def proxy(mock_gramps_person, mock_db):
    # Patch the GrampsPerson reference in the module to use our mock constants
    import name_processor.repositories.person as repo_module

    repo_module.GrampsPerson = MockGrampsPerson
    repo_module.NameOriginType = MockNameOriginType

    return GrampsPersonProxy(mock_gramps_person, mock_db)


def test_handle(proxy):
    assert proxy.handle == "p123"


def test_gender_male(proxy, mock_gramps_person):
    mock_gramps_person.get_gender.return_value = MockGrampsPerson.MALE
    assert proxy.gender == Gender.MALE


def test_gender_female_or_other(proxy, mock_gramps_person):
    mock_gramps_person.get_gender.return_value = MockGrampsPerson.FEMALE
    assert proxy.gender == Gender.FEMALE


def test_has_patronymic_true(proxy, mock_gramps_person):
    mock_primary_name = Mock()
    mock_surname1 = Mock()
    mock_surname1.get_origintype.return_value = MockNameOriginType.GIVEN
    mock_surname2 = Mock()
    mock_surname2.get_origintype.return_value = MockNameOriginType.PATRONYMIC

    mock_primary_name.get_surname_list.return_value = [mock_surname1, mock_surname2]
    mock_gramps_person.get_primary_name.return_value = mock_primary_name

    assert proxy.has_patronymic is True


def test_has_patronymic_false(proxy, mock_gramps_person):
    mock_primary_name = Mock()
    mock_surname = Mock()
    mock_surname.get_origintype.return_value = MockNameOriginType.GIVEN

    mock_primary_name.get_surname_list.return_value = [mock_surname]
    mock_gramps_person.get_primary_name.return_value = mock_primary_name

    assert proxy.has_patronymic is False


def test_father_handle_found(proxy, mock_gramps_person, mock_db):
    mock_gramps_person.get_parent_family_handle_list.return_value = ["fam1"]
    mock_family = Mock()
    mock_family.get_father_handle.return_value = "father123"
    mock_db.get_family_from_handle.return_value = mock_family

    assert proxy.father_handle == "father123"


def test_mother_handle_not_found(proxy, mock_gramps_person, mock_db):
    mock_gramps_person.get_parent_family_handle_list.return_value = []
    assert proxy.mother_handle is None


def test_children_handles(proxy, mock_gramps_person, mock_db):
    mock_gramps_person.get_family_handle_list.return_value = ["fam1", "fam2"]

    mock_fam1 = Mock()
    mock_child1 = Mock(ref="child1")
    mock_child2 = Mock(ref="child2")
    mock_fam1.get_child_ref_list.return_value = [mock_child1, mock_child2]

    mock_fam2 = Mock()
    mock_child3 = Mock(ref="child3")
    mock_fam2.get_child_ref_list.return_value = [mock_child3]

    mock_db.get_family_from_handle.side_effect = [mock_fam1, mock_fam2]

    assert proxy.children_handles == ["child1", "child2", "child3"]


def test_siblings_handles_excludes_self(proxy, mock_gramps_person, mock_db):
    # Proxy's own handle is "p123"
    mock_gramps_person.get_parent_family_handle_list.return_value = ["parent_fam"]

    mock_fam = Mock()
    mock_self = Mock(ref="p123")
    mock_sibling = Mock(ref="sib456")
    mock_fam.get_child_ref_list.return_value = [mock_self, mock_sibling]

    mock_db.get_family_from_handle.return_value = mock_fam

    assert proxy.siblings_handles == ["sib456"]


def test_event_years(proxy, mock_gramps_person, mock_db):
    mock_ref1 = Mock(ref="e1")
    mock_ref2 = Mock(ref="e2")
    mock_gramps_person.get_event_ref_list.return_value = [mock_ref1, mock_ref2]

    mock_event1 = Mock()
    mock_date1 = Mock()
    mock_date1.is_empty.return_value = False
    mock_date1.get_year.return_value = 1850
    mock_event1.get_date_object.return_value = mock_date1

    mock_event2 = Mock()
    mock_date2 = Mock()
    mock_date2.is_empty.return_value = True  # Empty date should be skipped
    mock_event2.get_date_object.return_value = mock_date2

    mock_db.get_event_from_handle.side_effect = [mock_event1, mock_event2]

    assert proxy.event_years == [1850]


def test_given_name(proxy, mock_gramps_person):
    mock_primary_name = Mock()
    mock_primary_name.get_first_name.return_value = "Ivan"
    mock_gramps_person.get_primary_name.return_value = mock_primary_name

    assert proxy.given_name == "Ivan"
