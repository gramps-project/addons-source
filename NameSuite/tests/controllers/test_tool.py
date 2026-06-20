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
from unittest.mock import MagicMock, patch

# Mock GTK and Gramps modules before importing
from tests.compat_mocks import mock_gramps

mock_gramps()

from name_processor.controllers.tool import ToolController  # noqa: E402
from name_processor.models.audit import AuditScope  # noqa: E402
from name_processor.models.renamer import AltAction, MatchMode  # noqa: E402
from name_processor.presentation.row_schemas import GivenRowData  # noqa: E402
from name_processor.protocols.view import ToolViewPort  # noqa: E402
from tests.fakes.fake_tool_view import FakeToolView  # noqa: E402
from tests.fakes.sync_task_runner import SynchronousTaskRunner  # noqa: E402


class TestToolController(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures with sync task runner."""
        self.sync_runner = SynchronousTaskRunner()

    def test_controller_initialization(self):
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
            task_runner=self.sync_runner,
        )
        self.assertEqual(controller.dbstate, mock_dbstate)
        self.assertFalse(controller._is_rename_scanning)
        self.assertFalse(controller._is_audit_scanning)

    def test_update_preserve_alt(self) -> None:
        mock_dbstate = MagicMock()
        mock_tool = MagicMock(dbstate=mock_dbstate)
        fake_view = FakeToolView()

        controller = ToolController(
            tool_instance=mock_tool,
            view=fake_view,
            read_repo=MagicMock(),
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=MagicMock(),
            task_runner=self.sync_runner,
        )

        row_data1 = GivenRowData(
            checkbox=True,
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            current="Ivan",
            proposed="Ioann",
            alt_action=AltAction.OVERWRITE,
            handle="handle1",
        )
        controller._rename_candidates["handle1"] = row_data1

        # Toggle preserve on (active=True)
        controller.update_preserve_alt(AltAction.PRESERVE)

        self.assertEqual(
            controller._rename_candidates["handle1"].alt_action,
            AltAction.PRESERVE,
        )
        # Verify FakeToolView recorded the action update
        self.assertEqual(len(fake_view.store_action_updates), 1)
        self.assertEqual(fake_view.store_action_updates[0], AltAction.PRESERVE)

        # Toggle preserve off (active=False)
        controller.update_preserve_alt(AltAction.OVERWRITE)

        self.assertEqual(
            controller._rename_candidates["handle1"].alt_action,
            AltAction.OVERWRITE,
        )
        self.assertEqual(len(fake_view.store_action_updates), 2)
        self.assertEqual(fake_view.store_action_updates[1], AltAction.OVERWRITE)

    def test_run_rename_scan_exact_mode_filtering(self):
        mock_tool = MagicMock()
        fake_view = FakeToolView()
        mock_read_repo = MagicMock()
        from name_processor.services.renamer import RenamerService

        renamer_service = RenamerService()

        # Mock two proxies: one matches the given_name, one doesn't
        mock_proxy_match = MagicMock()
        mock_proxy_match.given_name = "Ivan"
        mock_proxy_match.gramps_id = "I0001"
        mock_proxy_match.display_name = "Ivan Ivanov"
        mock_proxy_match.handle = "handle1"
        mock_primary_name_match = MagicMock()
        mock_primary_name_match.get_first_name.return_value = "Ivan"
        mock_proxy_match.get_primary_name.return_value = mock_primary_name_match

        mock_proxy_no_match = MagicMock()
        mock_proxy_no_match.given_name = "Petr"
        mock_proxy_no_match.gramps_id = "I0002"
        mock_proxy_no_match.display_name = "Petr Petrov"
        mock_proxy_no_match.handle = "handle2"
        mock_primary_name_no_match = MagicMock()
        mock_primary_name_no_match.get_first_name.return_value = "Petr"
        mock_proxy_no_match.get_primary_name.return_value = mock_primary_name_no_match

        # Configure repository to return both proxies
        mock_read_repo.iter_all_persons.return_value = iter(
            [mock_proxy_match, mock_proxy_no_match]
        )

        controller = ToolController(
            tool_instance=mock_tool,
            view=fake_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=renamer_service,
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=MagicMock(),
            task_runner=self.sync_runner,
        )

        # Run scan: Source is 'Ivan', Target is 'Ioann'
        # With buggy RenamerService, both 'Ivan' and 'Petr' will get proposed names
        controller.run_rename_scan("Ivan", "Ioann", MatchMode.EXACT)

        # Verify that append_rename_proposal was called ONLY for 'Ivan'
        # With the bug, it will be called twice (for Ivan AND Petr)
        self.assertEqual(
            len(fake_view.rename_proposals),
            1,
            f"Expected 1 proposal, but got {len(fake_view.rename_proposals)}",
        )

    def test_run_rename_scan_no_results(self):
        mock_tool = MagicMock()
        fake_view = FakeToolView()
        mock_read_repo = MagicMock()
        mock_renamer_service = MagicMock()

        # No results
        mock_read_repo.iter_all_persons.return_value = iter([])

        mock_renamer_service.create_config.return_value = {}

        controller = ToolController(
            tool_instance=mock_tool,
            view=fake_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=mock_renamer_service,
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=MagicMock(),
            task_runner=self.sync_runner,
        )

        # Run scan
        controller.run_rename_scan("Ivan", "Ioann", MatchMode.EXACT)

        # Verify that "No Results" dialog WAS shown
        self.assertEqual(len(fake_view.dialog_calls), 1)
        title, message = fake_view.dialog_calls[0]
        self.assertEqual(title, "No Results")
        self.assertEqual(message, "No matching given names found.")

    def test_initialize_median_year_async(self):
        mock_tool = MagicMock()
        mock_view = MagicMock()
        mock_read_repo = MagicMock()
        mock_chronology_service = MagicMock()

        # Mock generate_years to return a generator that yields years
        def year_generator():
            yield None
            return [1800, 1850, 1900, 1950, 2000]

        mock_chronology_service.generate_years.return_value = year_generator()

        controller = ToolController(
            tool_instance=mock_tool,
            view=mock_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=mock_chronology_service,
            task_runner=self.sync_runner,
        )

        # Initialize median year
        controller.initialize_median_year_async()

        # Verify generate_years was called
        mock_chronology_service.generate_years.assert_called_once()

        # Verify update_median_year was called with collected years
        mock_chronology_service.update_median_year.assert_called_once()
        call_args = mock_chronology_service.update_median_year.call_args[0][0]
        self.assertEqual(call_args, [1800, 1850, 1900, 1950, 2000])

    def test_initialize_median_year_async_with_empty_years(self):
        mock_tool = MagicMock()
        mock_view = MagicMock()
        mock_read_repo = MagicMock()
        mock_chronology_service = MagicMock()

        # Mock generate_years to return a generator that yields empty list
        def empty_generator():
            return []
            yield  # Make it a generator

        mock_chronology_service.generate_years.return_value = empty_generator()

        controller = ToolController(
            tool_instance=mock_tool,
            view=mock_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=mock_chronology_service,
            task_runner=self.sync_runner,
        )

        # Initialize median year
        controller.initialize_median_year_async()

        # Verify generate_years was called
        mock_chronology_service.generate_years.assert_called_once()

        # Verify update_median_year was called with empty list
        mock_chronology_service.update_median_year.assert_called_once_with([])

    def test_run_audit_scan_guard_prevents_overlap(self) -> None:
        mock_tool = MagicMock()
        mock_view = MagicMock()
        mock_read_repo = MagicMock()
        mock_audit_service = MagicMock()

        controller = ToolController(
            tool_instance=mock_tool,
            view=mock_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=mock_audit_service,
            chronology_service=MagicMock(),
            task_runner=self.sync_runner,
        )

        # Set scanning flag to True
        controller._is_audit_scanning = True

        # Try to run scan while already scanning
        result = controller.run_audit_scan(AuditScope.ALL, set(["test_rule"]), False)

        # Should return False indicating scan was not started
        self.assertFalse(result)

    def test_run_audit_scan_with_results(self):
        mock_tool = MagicMock()
        fake_view = FakeToolView()
        mock_read_repo = MagicMock()
        mock_audit_service = MagicMock()

        # Mock person proxy
        mock_proxy = MagicMock()
        mock_proxy.handle = "handle1"
        mock_proxy.gender = 1  # Male

        # Configure repository to return proxy
        mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])
        mock_read_repo.get_person_count.return_value = 1

        # Mock audit service to return an issue
        mock_issue = MagicMock()
        mock_issue.rule_id = "test_rule"
        mock_issue.person_handle = "handle1"
        mock_audit_service.audit_person.return_value = [mock_issue]

        controller = ToolController(
            tool_instance=mock_tool,
            view=fake_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=mock_audit_service,
            chronology_service=MagicMock(),
            task_runner=self.sync_runner,
        )

        # Run scan
        result = controller.run_audit_scan(AuditScope.ALL, set(["test_rule"]), False)

        # Should return True indicating scan was started
        self.assertTrue(result)

        # Verify audit_person was called
        mock_audit_service.audit_person.assert_called_once()

        # Verify scanning flag was reset
        self.assertFalse(controller._is_audit_scanning)

        # Verify issue was appended to view
        self.assertEqual(len(fake_view.audit_issues), 1)

    def test_run_audit_scan_no_results(self):
        mock_tool = MagicMock()
        fake_view = FakeToolView()
        mock_read_repo = MagicMock()
        mock_audit_service = MagicMock()

        # No results
        mock_read_repo.iter_all_persons.return_value = iter([])
        mock_read_repo.get_person_count.return_value = 0
        mock_audit_service.audit_person.return_value = []

        controller = ToolController(
            tool_instance=mock_tool,
            view=fake_view,
            read_repo=mock_read_repo,
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=mock_audit_service,
            chronology_service=MagicMock(),
            task_runner=self.sync_runner,
        )

        # Run scan
        result = controller.run_audit_scan(AuditScope.ALL, set(["test_rule"]), False)

        # Should return True indicating scan was started
        self.assertTrue(result)

        # Verify scanning flag was reset
        self.assertFalse(controller._is_audit_scanning)

        # Verify no issues were appended to view
        self.assertEqual(len(fake_view.audit_issues), 0)


class TestToolControllerRenameValidation(unittest.TestCase):
    """Test cases for ToolController rename scan validation."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.mock_view = MagicMock(spec=ToolViewPort)
        self.mock_read_repo = MagicMock()
        self.mock_write_repo = MagicMock()
        self.mock_renamer_service = MagicMock()
        self.mock_alt_names_service = MagicMock()
        self.mock_patronymic_service = MagicMock()
        self.mock_audit_service = MagicMock()
        self.mock_chronology_service = MagicMock()
        self.mock_tool_instance = MagicMock()
        self.mock_tool_instance.dbstate = MagicMock()
        self.mock_tool_instance.dbstate.db = MagicMock()

        self.sync_runner = SynchronousTaskRunner()
        self.controller = ToolController(
            tool_instance=self.mock_tool_instance,
            view=self.mock_view,
            read_repo=self.mock_read_repo,
            write_repo=self.mock_write_repo,
            renamer_service=self.mock_renamer_service,
            alt_names_service=self.mock_alt_names_service,
            patronymic_service=self.mock_patronymic_service,
            audit_service=self.mock_audit_service,
            chronology_service=self.mock_chronology_service,
            task_runner=self.sync_runner,
        )

    def test_validate_rename_input_empty_source(self):
        """Validation should fail when source is empty."""
        is_valid, error = self.controller._validate_rename_input(
            "", "Ivan", MatchMode.EXACT
        )
        self.assertFalse(is_valid)
        self.assertEqual(error, "Source name cannot be empty.")

    def test_validate_rename_input_whitespace_source(self):
        """Validation should fail when source is only whitespace."""
        is_valid, error = self.controller._validate_rename_input(
            "   ", "Ivan", MatchMode.EXACT
        )
        self.assertFalse(is_valid)
        self.assertEqual(error, "Source name cannot be empty.")

    def test_validate_rename_input_invalid_regex(self):
        """Validation should fail for invalid regex pattern."""
        is_valid, error = self.controller._validate_rename_input(
            "[invalid(", "Ivan", MatchMode.REGEX
        )
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid regular expression pattern in source name.")

    def test_validate_rename_input_valid_regex(self):
        """Validation should pass for valid regex pattern."""
        is_valid, error = self.controller._validate_rename_input(
            "Иоанн", "Ivan", MatchMode.REGEX
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_rename_input_whitespace_target(self):
        """Validation should fail when target is only whitespace."""
        is_valid, error = self.controller._validate_rename_input(
            "Иоанн", "   ", MatchMode.EXACT
        )
        self.assertFalse(is_valid)
        self.assertEqual(error, "Target name cannot contain only whitespace.")

    def test_validate_rename_input_empty_target_allowed(self):
        """Validation should pass when target is empty (optional field)."""
        is_valid, error = self.controller._validate_rename_input(
            "Иоанн", "", MatchMode.EXACT
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_rename_input_valid_exact_mode(self):
        """Validation should pass for valid exact mode input."""
        is_valid, error = self.controller._validate_rename_input(
            "Иоанн", "Ivan", MatchMode.EXACT
        )
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_on_rename_scan_requested_empty_source_shows_dialog(self):
        """Empty source should show error dialog and not start scan."""
        self.controller.on_rename_scan_requested("", "Ivan", MatchMode.EXACT)

        self.mock_view.show_ok_dialog.assert_called_once()
        args = self.mock_view.show_ok_dialog.call_args[0]
        self.assertEqual(args[0], "Invalid Input")
        self.assertEqual(args[1], "Source name cannot be empty.")

    def test_on_rename_scan_requested_invalid_regex_shows_dialog(self):
        """Invalid regex should show error dialog and not start scan."""
        self.controller.on_rename_scan_requested("[invalid(", "Ivan", MatchMode.REGEX)

        self.mock_view.show_ok_dialog.assert_called_once()
        args = self.mock_view.show_ok_dialog.call_args[0]
        self.assertEqual(args[0], "Invalid Input")
        self.assertIn("Invalid regular expression", args[1])

    def test_on_rename_scan_requested_whitespace_target_shows_dialog(self):
        """Whitespace-only target should show error dialog and not start scan."""
        self.controller.on_rename_scan_requested("Иоанн", "   ", MatchMode.EXACT)

        self.mock_view.show_ok_dialog.assert_called_once()
        args = self.mock_view.show_ok_dialog.call_args[0]
        self.assertEqual(args[0], "Invalid Input")
        self.assertEqual(args[1], "Target name cannot contain only whitespace.")

    def test_on_rename_scan_requested_valid_calls_run_rename_scan(self):
        """Valid input should call run_rename_scan without showing dialog."""
        with patch.object(self.controller, "run_rename_scan") as mock_scan:
            self.controller.on_rename_scan_requested("Иоанн", "Ivan", MatchMode.EXACT)

            mock_scan.assert_called_once_with("Иоанн", "Ivan", MatchMode.EXACT)
            self.mock_view.show_ok_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
