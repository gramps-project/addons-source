#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tests.compat_mocks import mock_gramps

mock_gramps()

from name_processor.controllers.tool import ToolController  # noqa: E402
from name_processor.models.renamer import AltAction, MatchMode  # noqa: E402
from name_processor.presentation.row_schemas import GivenRowData  # noqa: E402
from tests.fakes.fake_tool_view import FakeToolView  # noqa: E402
from tests.fakes.sync_task_runner import SynchronousTaskRunner  # noqa: E402
from tests.fixtures import setup_sample_family  # noqa: E402


class TestRenameWorkflow(unittest.TestCase):
    """End-to-end tests for rename scan and apply workflow."""

    def setUp(self) -> None:
        """Set up test fixtures with fake view and sync runner."""
        self.fake_view = FakeToolView()
        self.sync_runner = SynchronousTaskRunner()

        # Mock dependencies
        self.mock_tool = MagicMock()
        self.mock_tool.dbstate = MagicMock()
        self.mock_tool.dbstate.db = MagicMock()

        self.mock_read_repo = MagicMock()
        self.mock_write_repo = MagicMock()
        self.mock_renamer_service = MagicMock()
        self.mock_alt_names_service = MagicMock()
        self.mock_patronymic_service = MagicMock()
        self.mock_audit_service = MagicMock()
        self.mock_chronology_service = MagicMock()

        # Create controller
        self.controller = ToolController(
            tool_instance=self.mock_tool,
            view=self.fake_view,
            read_repo=self.mock_read_repo,
            write_repo=self.mock_write_repo,
            renamer_service=self.mock_renamer_service,
            alt_names_service=self.mock_alt_names_service,
            patronymic_service=self.mock_patronymic_service,
            audit_service=self.mock_audit_service,
            chronology_service=self.mock_chronology_service,
            task_runner=self.sync_runner,
        )

    def _run_scan_synchronously(self, generator, on_complete=None):
        """Helper to run a scan generator synchronously using SynchronousTaskRunner."""
        self.sync_runner.run_chunked(generator, on_complete)

    def test_rename_scan_finds_proposals(self) -> None:
        """Test that rename scan finds and displays proposals."""
        # Arrange: Create mock person proxies
        mock_proxy1 = MagicMock()
        mock_proxy1.given_name = "Ivan"
        mock_proxy1.gramps_id = "I0001"
        mock_proxy1.display_name = "Ivan Ivanov"
        mock_proxy1.handle = "handle1"

        mock_proxy2 = MagicMock()
        mock_proxy2.given_name = "Ivan"
        mock_proxy2.gramps_id = "I0002"
        mock_proxy2.display_name = "Ivan Petrov"
        mock_proxy2.handle = "handle2"

        self.mock_read_repo.iter_all_persons.return_value = iter(
            [mock_proxy1, mock_proxy2]
        )

        # Configure renamer service to return proposed name
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.return_value = "Ioann"

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_rename_scan("Ivan", "Ioann", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Two proposals appended to view
        self.assertEqual(len(self.fake_view.rename_proposals), 2)

        # Assert: Proposals have correct data
        proposal1 = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal1.current, "Ivan")
        self.assertEqual(proposal1.proposed, "Ioann")
        self.assertEqual(proposal1.handle, "handle1")

        # Assert: Both proposals checked by default
        self.assertEqual(len(self.fake_view.checked_rename_handles), 2)

    def test_rename_apply_checked_proposals(self) -> None:
        """Test that applying checked renamings calls write repository correctly."""
        # Arrange: Pre-populate rename candidates
        row_data = GivenRowData(
            checkbox=True,
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            current="Ivan",
            proposed="Ioann",
            alt_action=AltAction.OVERWRITE,
            handle="handle1",
        )
        self.controller._rename_candidates["handle1"] = row_data
        self.fake_view.rename_proposals.append(row_data)
        self.fake_view.checked_rename_handles.add("handle1")

        # Mock repository methods
        mock_person = MagicMock()
        self.mock_read_repo.get_raw_person.return_value = mock_person
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with correct parameters
        self.mock_write_repo.apply_first_name_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_first_name_correction.call_args
        self.assertEqual(call_args[0][2], "Ioann")  # proposed name

    def test_rename_apply_with_preserve_alt(self) -> None:
        """Test that preserve alt-names is respected during apply."""
        # Arrange: Pre-populate rename candidates
        row_data = GivenRowData(
            checkbox=True,
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            current="Ivan",
            proposed="Ioann",
            alt_action=AltAction.PRESERVE,
            handle="handle1",
        )
        self.controller._rename_candidates["handle1"] = row_data
        self.fake_view.rename_proposals.append(row_data)
        self.fake_view.checked_rename_handles.add("handle1")
        self.fake_view.set_preserve_alt_enabled(True)

        # Mock repository methods
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with new signature (handle, new_first_name, preserve_alt)
        self.mock_write_repo.apply_first_name_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_first_name_correction.call_args
        self.assertEqual(call_args[0][1], "handle1")  # handle
        self.assertEqual(call_args[0][2], "Ioann")  # new_first_name
        self.assertTrue(call_args[0][3])  # preserve_alt

    def test_rename_apply_partial_selection(self) -> None:
        """Test that only checked proposals are applied."""
        # Arrange: Pre-populate two rename candidates
        row_data1 = GivenRowData(
            checkbox=True,
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            current="Ivan",
            proposed="Ioann",
            alt_action=AltAction.OVERWRITE,
            handle="handle1",
        )
        row_data2 = GivenRowData(
            checkbox=True,
            gramps_id="I0002",
            display_name="Petr Petrov",
            current="Petr",
            proposed="Pyotr",
            alt_action=AltAction.OVERWRITE,
            handle="handle2",
        )
        self.controller._rename_candidates["handle1"] = row_data1
        self.controller._rename_candidates["handle2"] = row_data2
        self.fake_view.rename_proposals.extend([row_data1, row_data2])

        # Only check first proposal
        self.fake_view.checked_rename_handles.add("handle1")

        # Mock repository methods
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called only once (for handle1)
        self.mock_write_repo.apply_first_name_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_first_name_correction.call_args
        self.assertEqual(call_args[0][1], "handle1")  # handle
        self.assertEqual(call_args[0][2], "Ioann")  # new_first_name
        self.assertFalse(call_args[0][3])  # preserve_alt

    def test_preserve_alt_toggle_updates_all_proposals(self) -> None:
        """Test that toggling preserve alt updates all rename proposals."""
        # Arrange: Pre-populate rename candidates
        row_data1 = GivenRowData(
            checkbox=True,
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            current="Ivan",
            proposed="Ioann",
            alt_action=AltAction.OVERWRITE,
            handle="handle1",
        )
        row_data2 = GivenRowData(
            checkbox=True,
            gramps_id="I0002",
            display_name="Petr Petrov",
            current="Petr",
            proposed="Pyotr",
            alt_action=AltAction.OVERWRITE,
            handle="handle2",
        )
        self.controller._rename_candidates["handle1"] = row_data1
        self.controller._rename_candidates["handle2"] = row_data2
        self.fake_view.rename_proposals.extend([row_data1, row_data2])

        # Act: Toggle preserve alt to PRESERVE
        self.controller.update_preserve_alt(AltAction.PRESERVE)

        # Assert: All proposals updated to PRESERVE action
        for proposal in self.fake_view.rename_proposals:
            self.assertEqual(proposal.alt_action, AltAction.PRESERVE)

        # Assert: View notified of action update
        self.assertEqual(len(self.fake_view.store_action_updates), 1)
        self.assertEqual(self.fake_view.store_action_updates[0], AltAction.PRESERVE)

        # Act: Toggle preserve alt back to OVERWRITE
        self.controller.update_preserve_alt(AltAction.OVERWRITE)

        # Assert: All proposals updated to OVERWRITE action
        for proposal in self.fake_view.rename_proposals:
            self.assertEqual(proposal.alt_action, AltAction.OVERWRITE)

    def test_rename_scan_no_results_shows_dialog(self) -> None:
        """Test that scan with no results shows appropriate dialog."""
        # Arrange: Configure repository to return no persons
        self.mock_read_repo.iter_all_persons.return_value = iter([])

        self.mock_renamer_service.create_config.return_value = MagicMock()

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_rename_scan("Ivan", "Ioann", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: No proposals appended
        self.assertEqual(len(self.fake_view.rename_proposals), 0)

        # Assert: "No Results" dialog shown
        self.assertEqual(len(self.fake_view.dialog_calls), 1)
        title, message = self.fake_view.dialog_calls[0]
        self.assertEqual(title, "No Results")
        self.assertEqual(message, "No matching given names found.")

    def test_rename_scan_cyrillic_church_to_modern(self) -> None:
        """Test that rename scan handles Cyrillic church names to modern forms."""
        # Arrange: Create mock person proxy with Cyrillic church name
        mock_proxy = MagicMock()
        mock_proxy.given_name = "Иоанн"
        mock_proxy.gramps_id = "I0001"
        mock_proxy.display_name = "Иоанн Иванов"
        mock_proxy.handle = "handle1"

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])

        # Configure renamer service to return modern form
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.return_value = "Иван"

        # Configure mock to run synchronously

        # Act: Run scan with Cyrillic strings
        result = self.controller.run_rename_scan("Иоанн", "Иван", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Proposal appended with Cyrillic data
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.current, "Иоанн")
        self.assertEqual(proposal.proposed, "Иван")

    def test_rename_scan_cyrillic_typo_correction(self) -> None:
        """Test that rename scan handles Cyrillic typo correction."""
        # Arrange: Create mock person proxy with typo
        mock_proxy = MagicMock()
        mock_proxy.given_name = "Иоаннн"
        mock_proxy.gramps_id = "I0001"
        mock_proxy.display_name = "Иоаннн Иванов"
        mock_proxy.handle = "handle1"

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])

        # Configure renamer service to return corrected form
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.return_value = "Иван"

        # Configure mock to run synchronously

        # Act: Run scan to correct typo
        result = self.controller.run_rename_scan("Иоаннн", "Иван", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Proposal appended with corrected name
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.current, "Иоаннн")
        self.assertEqual(proposal.proposed, "Иван")

    def test_rename_scan_cyrillic_substring_hyphenated(self) -> None:
        """Test that rename scan handles substring matching in Cyrillic hyphenated names."""
        # Arrange: Create mock person proxy with hyphenated name
        mock_proxy = MagicMock()
        mock_proxy.given_name = "Анна-Иоанновна"
        mock_proxy.gramps_id = "I0001"
        mock_proxy.display_name = "Анна-Иоанновна Петрова"
        mock_proxy.handle = "handle1"

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])

        # Configure renamer service to return corrected form
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.return_value = "Анна-Ивановна"

        # Configure mock to run synchronously

        # Act: Run scan with substring match
        result = self.controller.run_rename_scan("Иоан", "Иван", MatchMode.SUBSTRING)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Proposal appended with corrected hyphenated name
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.current, "Анна-Иоанновна")
        self.assertEqual(proposal.proposed, "Анна-Ивановна")

    def test_rename_scan_cross_language(self) -> None:
        """Test that rename scan handles cross-language name standardization."""
        # Arrange: Create mock person proxy with Italian name
        mock_proxy = MagicMock()
        mock_proxy.given_name = "Giuseppe"
        mock_proxy.gramps_id = "I0001"
        mock_proxy.display_name = "Giuseppe Rossi"
        mock_proxy.handle = "handle1"

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])

        # Configure renamer service to return anglicized form
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.return_value = "Joseph"

        # Configure mock to run synchronously

        # Act: Run scan for cross-language standardization
        result = self.controller.run_rename_scan("Giuseppe", "Joseph", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Proposal appended with anglicized name
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.current, "Giuseppe")
        self.assertEqual(proposal.proposed, "Joseph")

    def test_controller_initialization_sets_tab_controller(self) -> None:
        """Test that set_controller updates tab controller references before setup_autocompletion."""
        # This test prevents regression of the bug where tabs had None controller
        # when setup_autocompletion was called during set_controller

        # Arrange: Create a real ToolWindow (not FakeToolView)
        # We need to test the actual initialization flow
        from name_processor.views.tool import ToolWindow

        # Arrange: Mock controller with required methods
        mock_controller = MagicMock()
        mock_controller.get_available_audit_rules.return_value = {"rule1", "rule2"}
        mock_controller.get_given_names.return_value = {"Ivan", "Maria"}
        mock_controller.initialize_median_year_async = MagicMock()
        mock_controller.initialize_given_names_async = MagicMock()

        # Create window with mock controller
        window = ToolWindow(None)
        window.set_controller(mock_controller)

        # Assert: Tab controller is set
        assert window.rename_tab is not None
        assert window.audit_tab is not None
        self.assertEqual(window.rename_tab.controller, mock_controller)
        self.assertEqual(window.audit_tab.controller, mock_controller)

    def test_tool_window_implements_protocol_methods(self) -> None:
        """Test that ToolWindow implements all methods defined in ToolViewPort protocol."""
        from name_processor.protocols.view import ToolViewPort
        from name_processor.views.tool import ToolWindow

        # Create window with mock controller
        mock_controller = MagicMock()
        mock_controller.get_available_audit_rules.return_value = {"rule1", "rule2"}
        mock_controller.initialize_median_year_async = MagicMock()
        mock_controller.initialize_given_names_async = MagicMock()

        window = ToolWindow(None)
        window.set_controller(mock_controller)

        # Get all methods defined in the protocol
        protocol_methods = {
            name for name in dir(ToolViewPort) if not name.startswith("_")
        }

        # Get all methods implemented by ToolWindow
        window_methods = {
            name
            for name in dir(window)
            if not name.startswith("_") and callable(getattr(window, name))
        }

        # Assert that ToolWindow implements all protocol methods
        missing_methods = protocol_methods - window_methods
        self.assertEqual(
            len(missing_methods),
            0,
            f"ToolWindow is missing protocol methods: {missing_methods}",
        )

    def test_exact_match_preserve_original_as_alternative(self) -> None:
        """Test exact match with preserve original name as alternative."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())

        # Set up autocompletion with available names (simulating UI state)
        self.fake_view.set_autocompletion_names(
            {"Анна", "Аркадий", "Долли", "Stiva", "Maria"}
        )

        # Verify autocompletion would suggest "Анна" for prefix "Ан"
        suggestions = self.fake_view.get_autocompletion_suggestions("Ан")
        self.assertIn("Анна", suggestions)

        # Configure mock to run synchronously

        # Configure renamer service for exact match
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.side_effect = lambda name, cfg: (
            "Ганна" if name == "Анна" else None
        )

        # Enable preserve alt
        self.fake_view.set_preserve_alt_enabled(True)

        # Act: Run scan for exact match "Анна" -> "Ганна"
        result = self.controller.run_rename_scan("Анна", "Ганна", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: One proposal for I000 (Анна)
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.gramps_id, "I000")
        self.assertEqual(proposal.current, "Анна")
        self.assertEqual(proposal.proposed, "Ганна")
        self.assertEqual(proposal.alt_action, AltAction.PRESERVE)

        # Arrange: Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with new signature (handle, new_first_name, preserve_alt)
        self.mock_write_repo.apply_first_name_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_first_name_correction.call_args
        self.assertEqual(call_args[0][1], family["I000"].handle)  # handle
        self.assertEqual(call_args[0][2], "Ганна")  # new_first_name
        self.assertTrue(call_args[0][3])  # preserve_alt

    def test_substring_match_preserve_original_as_alternative(self) -> None:
        """Test substring match with preserve original name as alternative."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())

        # Configure mock to run synchronously

        # Configure renamer service for substring match "А" -> "О"
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.side_effect = lambda name, cfg: (
            name.replace("А", "О") if "А" in name else None
        )

        # Enable preserve alt
        self.fake_view.set_preserve_alt_enabled(True)

        # Act: Run scan for substring match "А" -> "О"
        result = self.controller.run_rename_scan("А", "О", MatchMode.SUBSTRING)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Two proposals for I000 (Анна -> Онна) and I001 (Аркадий -> Оркадий)
        self.assertEqual(len(self.fake_view.rename_proposals), 2)

        # Check I000 proposal
        proposal_i000 = next(
            p for p in self.fake_view.rename_proposals if p.gramps_id == "I000"
        )
        self.assertEqual(proposal_i000.current, "Анна")
        self.assertEqual(proposal_i000.proposed, "Онна")
        self.assertEqual(proposal_i000.alt_action, AltAction.PRESERVE)

        # Check I001 proposal
        proposal_i001 = next(
            p for p in self.fake_view.rename_proposals if p.gramps_id == "I001"
        )
        self.assertEqual(proposal_i001.current, "Аркадий")
        self.assertEqual(proposal_i001.proposed, "Оркадий")
        self.assertEqual(proposal_i001.alt_action, AltAction.PRESERVE)

        # Arrange: Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called twice with new signature
        self.assertEqual(self.mock_write_repo.apply_first_name_correction.call_count, 2)
        # Check that preserve_alt was True for both calls
        for call in self.mock_write_repo.apply_first_name_correction.call_args_list:
            self.assertTrue(call[0][3])  # preserve_alt

    def test_regex_match_preserve_original_as_alternative(self) -> None:
        """Test regex match with preserve original name as alternative."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())

        # Configure mock to run synchronously

        # Configure renamer service for regex match "А(рк)ад(.*)" -> "О\2рай\1ий"
        # This should transform "Аркадий" to "Оийрайркий"
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.side_effect = lambda name, cfg: (
            "Оийрайркий" if name == "Аркадий" else None
        )

        # Enable preserve alt
        self.fake_view.set_preserve_alt_enabled(True)

        # Act: Run scan for regex match
        result = self.controller.run_rename_scan(
            "А(рк)ад(.*)", "О\\2рай\\1ий", MatchMode.REGEX
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: One proposal for I001 (Аркадий -> Оийрайркий)
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.gramps_id, "I001")
        self.assertEqual(proposal.current, "Аркадий")
        self.assertEqual(proposal.proposed, "Оийрайркий")
        self.assertEqual(proposal.alt_action, AltAction.PRESERVE)

        # Arrange: Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with new signature (handle, new_first_name, preserve_alt)
        self.mock_write_repo.apply_first_name_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_first_name_correction.call_args
        self.assertEqual(call_args[0][1], family["I001"].handle)  # handle
        self.assertEqual(call_args[0][2], "Оийрайркий")  # new_first_name
        self.assertTrue(call_args[0][3])  # preserve_alt

    def test_exact_match_without_preserve_original_as_alternative(self) -> None:
        """Test exact match without preserve original name as alternative."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())

        # Configure mock to run synchronously

        # Configure renamer service for exact match
        self.mock_renamer_service.create_config.return_value = MagicMock()
        self.mock_renamer_service.evaluate_person.side_effect = lambda name, cfg: (
            "Ганна" if name == "Анна" else None
        )

        # Disable preserve alt
        self.fake_view.set_preserve_alt_enabled(False)

        # Act: Run scan for exact match "Анна" -> "Ганна"
        result = self.controller.run_rename_scan("Анна", "Ганна", MatchMode.EXACT)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: One proposal for I000 (Анна)
        self.assertEqual(len(self.fake_view.rename_proposals), 1)
        proposal = self.fake_view.rename_proposals[0]
        self.assertEqual(proposal.gramps_id, "I000")
        self.assertEqual(proposal.current, "Анна")
        self.assertEqual(proposal.proposed, "Ганна")
        self.assertEqual(proposal.alt_action, AltAction.OVERWRITE)

        # Arrange: Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked renamings
        result = self.controller.apply_checked_renamings()

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with new signature (handle, new_first_name, preserve_alt=False)
        self.mock_write_repo.apply_first_name_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_first_name_correction.call_args
        self.assertEqual(call_args[0][1], family["I000"].handle)  # handle
        self.assertEqual(call_args[0][2], "Ганна")  # new_first_name
        self.assertFalse(call_args[0][3])  # preserve_alt


if __name__ == "__main__":
    unittest.main()
