from unittest.mock import Mock, patch, MagicMock
import pytest

from name_processor.repositories.gramps_write import (
    is_patronymic_origin,
    update_or_add_patronymic,
    GrampsWriteRepository,
)


# Mock Gramps Constants
class MockNameOriginType:
    PATRONYMIC = 2
    GIVEN = 0


@pytest.fixture(autouse=True)
def patch_gramps_constants():
    with patch(
        "name_processor.repositories.gramps_write.NameOriginType", MockNameOriginType
    ):
        yield


def test_is_patronymic_origin():
    assert is_patronymic_origin(MockNameOriginType.PATRONYMIC) is True
    assert is_patronymic_origin(str(MockNameOriginType.PATRONYMIC)) is True
    assert is_patronymic_origin(MockNameOriginType.GIVEN) is False
    assert is_patronymic_origin(None) is False
    assert is_patronymic_origin("invalid_int") is False


def test_update_or_add_patronymic_updates_existing():
    mock_primary = Mock()
    mock_surname1 = Mock()
    mock_surname1.get_origintype.return_value = MockNameOriginType.GIVEN
    mock_surname1.get_surname.return_value = "Smith"

    mock_surname2 = Mock()
    mock_surname2.get_origintype.return_value = MockNameOriginType.PATRONYMIC
    mock_surname2.get_surname.return_value = "OldPatronymic"

    mock_primary.get_surname_list.return_value = [mock_surname1, mock_surname2]

    result = update_or_add_patronymic(mock_primary, "NewPatronymic")

    assert result == "OldPatronymic"
    mock_surname2.set_surname.assert_called_once_with("NewPatronymic")
    mock_primary.add_surname.assert_not_called()


@patch("name_processor.repositories.gramps_write.Surname")
def test_update_or_add_patronymic_adds_new(mock_surname_class):
    mock_primary = Mock()
    mock_surname_existing = Mock()
    mock_surname_existing.get_origintype.return_value = MockNameOriginType.GIVEN
    mock_primary.get_surname_list.return_value = [mock_surname_existing]

    mock_new_surname = Mock()
    mock_surname_class.return_value = mock_new_surname

    result = update_or_add_patronymic(mock_primary, "NewPatronymic")

    assert result == ""
    mock_new_surname.set_surname.assert_called_once_with("NewPatronymic")
    mock_new_surname.set_origintype.assert_called_once_with(
        MockNameOriginType.PATRONYMIC
    )
    mock_new_surname.set_primary.assert_called_once_with(False)
    mock_primary.add_surname.assert_called_once_with(mock_new_surname)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def write_repo(mock_db):
    return GrampsWriteRepository(mock_db)


@patch("name_processor.repositories.gramps_write.update_or_add_patronymic")
@patch("name_processor.repositories.gramps_write.DbTxn")
def test_update_patronymic_names(mock_dbtxn, mock_update_func, write_repo, mock_db):
    mock_txn_instance = MagicMock()
    mock_dbtxn.return_value.__enter__.return_value = mock_txn_instance

    mock_person = Mock()
    mock_primary = Mock()
    mock_person.get_primary_name.return_value = mock_primary
    mock_db.get_person_from_handle.return_value = mock_person

    # Act
    write_repo.update_patronymic_names({"h1": "Ivanovich"})

    # Assert
    mock_update_func.assert_called_once_with(mock_primary, "Ivanovich")
    mock_db.commit_person.assert_called_once_with(mock_person, mock_txn_instance)
