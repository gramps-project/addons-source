from unittest.mock import Mock, MagicMock
import pytest

from NameSuite.name_processor.controllers.gramplet import GrampletController
from NameSuite.name_processor.models.infer import PatronymicInferenceStatus


@pytest.fixture
def mocks():
    """Fixture to provide fresh mocks for every test."""
    return {
        "view": Mock(),
        "patronymic_service": Mock(),
        "read_repo": Mock(),
        "write_repo": Mock(),
    }


@pytest.fixture
def controller(mocks):
    return GrampletController(
        view=mocks["view"],
        patronymic_service=mocks["patronymic_service"],
        read_repo=mocks["read_repo"],
        write_repo=mocks["write_repo"],
    )


def test_on_active_changed_with_none_handle(controller, mocks):
    # Act
    controller.on_active_changed(None)

    # Assert
    assert controller.current_handle is None
    mocks["view"].show_status_message.assert_called_once_with(
        PatronymicInferenceStatus.NO_ACTIVE_PERSON, apply_sensitive=False
    )
    mocks["read_repo"].get_person_proxy.assert_not_called()


def test_on_active_changed_person_not_found(controller, mocks):
    # Arrange
    mocks["read_repo"].get_person_proxy.return_value = None

    # Act
    controller.on_active_changed("h123")

    # Assert
    assert controller.current_handle == "h123"
    mocks["read_repo"].get_person_proxy.assert_called_once_with("h123")
    mocks["view"].show_status_message.assert_called_once_with(
        PatronymicInferenceStatus.NO_ACTIVE_PERSON, apply_sensitive=False
    )


def test_on_active_changed_success(controller, mocks):
    # Arrange
    mock_person = Mock()
    mock_person.father_handle = "f456"
    mock_father = Mock()

    mock_result = MagicMock()
    mock_result.status = PatronymicInferenceStatus.SUCCESS
    mock_result.patronymic = "Ivanovich"
    mock_result.father_name = "Ivan"

    # Setup read_repo to return the person, then the father
    mocks["read_repo"].get_person_proxy.side_effect = [mock_person, mock_father]
    mocks["patronymic_service"].infer_patronymic.return_value = mock_result

    # Act
    controller.on_active_changed("h123")

    # Assert
    mocks["patronymic_service"].infer_patronymic.assert_called_once_with(
        mock_person, mock_father
    )
    assert controller._suggested_patronymic == "Ivanovich"
    mocks["view"].show_suggestion.assert_called_once_with("Ivanovich", "Ivan")


def test_on_apply_clicked_does_nothing_if_no_suggestion(controller, mocks):
    # Arrange
    controller.current_handle = "h123"
    controller._suggested_patronymic = None

    # Act
    controller.on_apply_clicked()

    # Assert
    mocks["write_repo"].update_patronymic_names.assert_not_called()


def test_on_apply_clicked_success(controller, mocks):
    # Arrange
    controller.current_handle = "h123"
    controller._suggested_patronymic = "Ivanovich"

    # Act
    controller.on_apply_clicked()

    # Assert
    mocks["write_repo"].update_patronymic_names.assert_called_once_with(
        {"h123": "Ivanovich"}
    )
    mocks["view"].show_status_message.assert_called_once_with(
        PatronymicInferenceStatus.SUCCESS, apply_sensitive=False
    )
