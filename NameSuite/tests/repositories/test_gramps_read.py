from unittest.mock import Mock, patch
import pytest

from name_processor.repositories.gramps_read import GrampsReadRepository


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def read_repo(mock_db):
    return GrampsReadRepository(mock_db)


def test_get_person_proxy_returns_none(read_repo, mock_db):
    mock_db.get_person_from_handle.return_value = None
    assert read_repo.get_person_proxy("bad_handle") is None


@patch("name_processor.repositories.gramps_read.GrampsPersonProxy")
def test_get_person_proxy_success(mock_proxy_class, read_repo, mock_db):
    mock_person = Mock()
    mock_db.get_person_from_handle.return_value = mock_person

    result = read_repo.get_person_proxy("h123")

    mock_proxy_class.assert_called_once_with(mock_person, mock_db)
    assert result == mock_proxy_class.return_value


@patch("name_processor.repositories.gramps_read.GrampsPersonProxy")
def test_get_chronology_subject_success(mock_proxy_class, read_repo, mock_db):
    mock_person = Mock()
    mock_db.get_person_from_handle.return_value = mock_person

    result = read_repo.get_chronology_subject("h123")
    assert result == mock_proxy_class.return_value


def test_get_database_median_year_chunked_empty(read_repo, mock_db):
    mock_db.get_event_handles.return_value = []

    generator = read_repo.get_database_median_year_chunked()

    # A generator completing immediately raises StopIteration
    # with the final return value stored in excinfo.value.value
    with pytest.raises(StopIteration) as excinfo:
        next(generator)

    assert excinfo.value.value is None


def test_get_database_median_year_chunked(read_repo, mock_db):
    # Create 5 mock events
    mock_db.get_event_handles.return_value = ["e1", "e2", "e3", "e4", "e5"]

    def create_mock_event(year):
        event = Mock()
        date_obj = Mock()
        date_obj.is_empty.return_value = False
        date_obj.get_year.return_value = year
        event.get_date_object.return_value = date_obj
        return event

    # Unsorted years: 1910, 1950, 1890, 1900, 1920
    # Sorted: 1890, 1900, 1910, 1920, 1950 -> Median: 1910
    mock_db.get_event_from_handle.side_effect = [
        create_mock_event(1910),
        create_mock_event(1950),
        create_mock_event(1890),
        create_mock_event(1900),
        create_mock_event(1920),
    ]

    generator = read_repo.get_database_median_year_chunked(chunk_size=2)

    # Chunk 1 (e1, e2)
    assert next(generator) is None
    # Chunk 2 (e3, e4)
    assert next(generator) is None
    # Chunk 3 (e5)
    assert next(generator) is None

    # Completion
    with pytest.raises(StopIteration) as excinfo:
        next(generator)

    assert excinfo.value.value == 1910
