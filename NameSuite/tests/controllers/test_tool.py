from unittest.mock import MagicMock
from name_processor.controllers.tool import ToolController


def test_controller_initialization():
    mock_dbstate = MagicMock()
    mock_tool = MagicMock(dbstate=mock_dbstate)

    # Instantiate without real DB
    controller = ToolController(
        tool_instance=mock_tool,
        view=MagicMock(),
        read_repo=MagicMock(),
        write_repo=MagicMock(),
        patronymic_service=MagicMock(),
        renamer_service=MagicMock(),
        alt_names_service=MagicMock(),
        audit_service=MagicMock(),
        chronology_service=MagicMock(),
    )
    assert controller.dbstate == mock_dbstate


def test_update_preserve_alt() -> None:
    mock_dbstate = MagicMock()
    mock_tool = MagicMock(dbstate=mock_dbstate)
    mock_view = MagicMock()

    controller = ToolController(
        tool_instance=mock_tool,
        view=mock_view,
        read_repo=MagicMock(),
        write_repo=MagicMock(),
        patronymic_service=MagicMock(),
        renamer_service=MagicMock(),
        alt_names_service=MagicMock(),
        audit_service=MagicMock(),
        chronology_service=MagicMock(),
    )

    from name_processor.models.renamer import ProposedRename

    proposal1 = ProposedRename(
        handle="handle1",
        gramps_id="I0001",
        display_name="Ivan Ivanov",
        original_given_name="Ivan",
        proposed_given_name="Ioann",
        alt_action="Overwrite",
    )
    controller._rename_candidates["handle1"] = proposal1

    # Toggle preserve on (active=True)
    controller.update_preserve_alt(True)

    assert proposal1.alt_action == "Preserve"
    mock_view.update_given_store_actions.assert_called_once_with("Preserve")

    # Toggle preserve off (active=False)
    mock_view.reset_mock()
    controller.update_preserve_alt(False)

    assert proposal1.alt_action == "Overwrite"
    mock_view.update_given_store_actions.assert_called_once_with("Overwrite")
