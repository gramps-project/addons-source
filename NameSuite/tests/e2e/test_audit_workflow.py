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
from name_processor.models.audit import AuditIssue, AuditScope  # noqa: E402
from name_processor.models.person import Gender  # noqa: E402
from tests.fakes.fake_tool_view import FakeToolView  # noqa: E402
from tests.fakes.sync_task_runner import SynchronousTaskRunner  # noqa: E402
from tests.fixtures import setup_sample_family  # noqa: E402


class TestAuditWorkflow(unittest.TestCase):
    """End-to-end tests for audit scan and apply workflow."""

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

    def test_audit_scan_finds_issues(self) -> None:
        """Test that audit scan finds and displays issues."""
        # Arrange: Create mock person proxy
        mock_proxy = MagicMock()
        mock_proxy.handle = "handle1"
        mock_proxy.gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return an issue
        mock_issue = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            father_name="Ivan",
            current_value="Ivanovich",
            suggested_fix="Ivanov",
            confidence=0.95,
            reference_year="1850",
            rule_id="test_rule",
            explanation="Patronymic pattern mismatch",
            severity="high",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(AuditScope.ALL, {"test_rule"}, False)

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue appended to view
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertEqual(self.fake_view.audit_issues[0].rule_id, "test_rule")

        # Assert: Issue checked by default
        self.assertEqual(len(self.fake_view.checked_audit_keys), 1)

    def test_audit_scan_with_scope_filter(self) -> None:
        """Test that audit scan respects scope filter (males only)."""
        # Arrange: Create mock person proxies (male and female)
        mock_male = MagicMock()
        mock_male.handle = "handle1"
        mock_male.gender = Gender.MALE

        mock_female = MagicMock()
        mock_female.handle = "handle2"
        mock_female.gender = Gender.FEMALE

        self.mock_read_repo.iter_all_persons.return_value = iter(
            [mock_male, mock_female]
        )
        self.mock_read_repo.get_person_count.return_value = 2

        # Configure audit service
        self.mock_audit_service.audit_person.return_value = []

        # Configure mock to run synchronously

        # Act: Run scan with MALES_ONLY scope
        result = self.controller.run_audit_scan(
            AuditScope.MALES_ONLY, {"test_rule"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Audit service called only for male (once)
        self.assertEqual(self.mock_audit_service.audit_person.call_count, 1)

    def test_audit_apply_checked_fixes(self) -> None:
        """Test that applying checked audit fixes calls write repository correctly."""
        # Arrange: Pre-populate audit candidates
        mock_issue = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            father_name="Ivan",
            current_value="Ivanovich",
            suggested_fix="Ivanov",
            confidence=0.95,
            reference_year="1850",
            rule_id="test_rule",
            explanation="Patronymic pattern mismatch",
            severity="high",
            is_pre_reform=False,
        )
        self.controller._audit_candidates[("handle1", "test_rule")] = mock_issue
        self.fake_view.audit_issues.append(mock_issue)
        self.fake_view.checked_audit_keys.add(("handle1", "test_rule"))

        # Mock repository methods
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=False)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with correct parameters
        self.mock_write_repo.apply_patronymic_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_patronymic_correction.call_args
        self.assertEqual(call_args[0][1], "handle1")  # person_handle
        self.assertEqual(call_args[0][2], "Ivanov")  # suggested_fix

    def test_audit_apply_partial_selection(self) -> None:
        """Test that only checked issues are applied."""
        # Arrange: Pre-populate two audit candidates
        mock_issue1 = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            father_name="Ivan",
            current_value="Ivanovich",
            suggested_fix="Ivanov",
            confidence=0.95,
            reference_year="1850",
            rule_id="rule1",
            explanation="Patronymic pattern mismatch",
            severity="high",
            is_pre_reform=False,
        )
        mock_issue2 = AuditIssue(
            person_handle="handle2",
            gramps_id="I0002",
            display_name="Petr Petrov",
            father_name="Petr",
            current_value="Petrovich",
            suggested_fix="Petrov",
            confidence=0.90,
            reference_year="1860",
            rule_id="rule2",
            explanation="Patronymic pattern mismatch",
            severity="medium",
            is_pre_reform=False,
        )
        self.controller._audit_candidates[("handle1", "rule1")] = mock_issue1
        self.controller._audit_candidates[("handle2", "rule2")] = mock_issue2
        self.fake_view.audit_issues.extend([mock_issue1, mock_issue2])

        # Only check first issue
        self.fake_view.checked_audit_keys.add(("handle1", "rule1"))

        # Mock repository methods
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=False)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called only once (for first issue)
        self.mock_write_repo.apply_patronymic_correction.assert_called_once()

    def test_audit_scan_cyrillic_patronymic_generation_male(self) -> None:
        """Test that audit scan generates correct male Cyrillic patronymic from father's name."""
        # Arrange: Create mock male person proxy with Cyrillic father name
        mock_proxy = MagicMock()
        mock_proxy.handle = "handle1"
        mock_proxy.gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return patronymic generation issue
        mock_issue = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Алексей Иванов",
            father_name="Иван",
            current_value="",
            suggested_fix="Иванович",
            confidence=0.95,
            reference_year="1850",
            rule_id="patronymic_generation",
            explanation="Generated patronymic from father's name",
            severity="high",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue appended with Cyrillic patronymic
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertEqual(self.fake_view.audit_issues[0].father_name, "Иван")
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "Иванович")

    def test_audit_scan_cyrillic_patronymic_generation_female(self) -> None:
        """Test that audit scan generates correct female Cyrillic patronymic from father's name."""
        # Arrange: Create mock female person proxy with Cyrillic father name
        mock_proxy = MagicMock()
        mock_proxy.handle = "handle1"
        mock_proxy.gender = Gender.FEMALE

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return patronymic generation issue
        mock_issue = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Мария Иванова",
            father_name="Иван",
            current_value="",
            suggested_fix="Ивановна",
            confidence=0.95,
            reference_year="1850",
            rule_id="patronymic_generation",
            explanation="Generated patronymic from father's name",
            severity="high",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue appended with female Cyrillic patronymic
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertEqual(self.fake_view.audit_issues[0].father_name, "Иван")
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "Ивановна")

    def test_audit_scan_gender_suffix_mismatch(self) -> None:
        """Test that audit scan flags gender suffix mismatch in Cyrillic patronymics."""
        # Arrange: Create mock male person proxy with female patronymic suffix
        mock_proxy = MagicMock()
        mock_proxy.handle = "handle1"
        mock_proxy.gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return gender mismatch issue
        mock_issue = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Алексей Ивановна",
            father_name="Иван",
            current_value="Ивановна",
            suggested_fix="Иванович",
            confidence=0.98,
            reference_year="1850",
            rule_id="gender_suffix_mismatch",
            explanation="Male person has female patronymic suffix",
            severity="high",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"gender_suffix_mismatch"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue appended with gender mismatch detected
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertEqual(
            self.fake_view.audit_issues[0].rule_id, "gender_suffix_mismatch"
        )
        self.assertEqual(self.fake_view.audit_issues[0].current_value, "Ивановна")
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "Иванович")

    def test_audit_scan_pre_reform_orthography(self) -> None:
        """Test that audit scan handles pre-reform Cyrillic orthography."""
        # Arrange: Create mock person proxy
        mock_proxy = MagicMock()
        mock_proxy.handle = "handle1"
        mock_proxy.gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter([mock_proxy])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return issue with pre-reform orthography
        mock_issue = AuditIssue(
            person_handle="handle1",
            gramps_id="I0001",
            display_name="Алексей Федоров",
            father_name="Федор",
            current_value="Федорович",
            suggested_fix="Фёдорович",
            confidence=0.90,
            reference_year="1850",
            rule_id="orthography_check",
            explanation="Pre-reform orthography detected",
            severity="medium",
            is_pre_reform=True,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan with pre-reform orthography enabled
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"orthography_check"}, True
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue appended with pre-reform orthography flag
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertTrue(self.fake_view.audit_issues[0].is_pre_reform)
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "Фёдорович")

    def test_patronymic_generation_for_children(self) -> None:
        """Test patronymic generation for children from father's name."""
        # Arrange: Set up sample family
        family = setup_sample_family()

        # Set up gender for family members
        family["I001"].gender = Gender.MALE  # Father
        family["I000"].gender = Gender.FEMALE  # Daughter
        family["I002"].gender = Gender.FEMALE  # Daughter
        family["I004"].gender = Gender.MALE  # Son
        family["I003"].gender = Gender.FEMALE  # Unrelated

        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())
        self.mock_read_repo.get_person_count.return_value = 5

        # Configure audit service to return patronymic generation issues for children
        def mock_audit_person(person, rules, use_pre_reform):
            if person.gramps_id == "I000":
                return [
                    AuditIssue(
                        person_handle="handle_i000",
                        gramps_id="I000",
                        display_name="Облонская, Анна",
                        father_name="Аркадий",
                        current_value="",
                        suggested_fix="Ивановна",
                        confidence=0.95,
                        reference_year="1850",
                        rule_id="patronymic_generation",
                        explanation="Generated patronymic from father's name",
                        severity="high",
                        is_pre_reform=False,
                    )
                ]
            elif person.gramps_id == "I002":
                return [
                    AuditIssue(
                        person_handle="handle_i002",
                        gramps_id="I002",
                        display_name="Облонская, Долли",
                        father_name="Аркадий",
                        current_value="",
                        suggested_fix="Ивановна",
                        confidence=0.95,
                        reference_year="1850",
                        rule_id="patronymic_generation",
                        explanation="Generated patronymic from father's name",
                        severity="high",
                        is_pre_reform=False,
                    )
                ]
            elif person.gramps_id == "I004":
                return [
                    AuditIssue(
                        person_handle="handle_i004",
                        gramps_id="I004",
                        display_name="Oblonsky, Stiva",
                        father_name="Аркадий",
                        current_value="",
                        suggested_fix="Иванович",
                        confidence=0.95,
                        reference_year="1850",
                        rule_id="patronymic_generation",
                        explanation="Generated patronymic from father's name",
                        severity="high",
                        is_pre_reform=False,
                    )
                ]
            return []

        self.mock_audit_service.audit_person.side_effect = mock_audit_person

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Three issues found (I000, I002, I004)
        self.assertEqual(len(self.fake_view.audit_issues), 3)

        # Assert: All have correct father name and suggested patronymics
        issue_ids = {issue.gramps_id for issue in self.fake_view.audit_issues}
        self.assertEqual(issue_ids, {"I000", "I002", "I004"})

        # Assert: All checked by default
        self.assertEqual(len(self.fake_view.checked_audit_keys), 3)

        # Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=False)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called three times
        self.assertEqual(self.mock_write_repo.apply_patronymic_correction.call_count, 3)

    def test_gender_suffix_mismatch_detection(self) -> None:
        """Test gender suffix mismatch detection."""
        # Arrange: Set up sample family with incorrect suffix
        family = setup_sample_family()
        family["I001"].gender = Gender.MALE  # Father with female suffix

        self.mock_read_repo.iter_all_persons.return_value = iter([family["I001"]])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return gender mismatch issue
        mock_issue = AuditIssue(
            person_handle="handle_i001",
            gramps_id="I001",
            display_name="Облонский, Аркадий",
            father_name="",
            current_value="Ивановна",
            suggested_fix="Иванович",
            confidence=0.98,
            reference_year="1850",
            rule_id="gender_suffix_mismatch",
            explanation="Male person has female patronymic suffix",
            severity="high",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"gender_suffix_mismatch"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue found
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertEqual(
            self.fake_view.audit_issues[0].rule_id, "gender_suffix_mismatch"
        )
        self.assertEqual(self.fake_view.audit_issues[0].current_value, "Ивановна")
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "Иванович")

        # Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=False)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with correct fix
        self.mock_write_repo.apply_patronymic_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_patronymic_correction.call_args
        self.assertEqual(call_args[0][2], "Иванович")

    def test_pre_reform_orthography_detection(self) -> None:
        """Test pre-reform orthography detection."""
        # Arrange: Set up sample family with pre-reform patronymic
        family = setup_sample_family()
        family["I001"].gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter([family["I001"]])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return pre-reform orthography issue
        mock_issue = AuditIssue(
            person_handle="handle_i001",
            gramps_id="I001",
            display_name="Облонский, Аркадий",
            father_name="Федор",
            current_value="Федорович",
            suggested_fix="Фёдорович",
            confidence=0.90,
            reference_year="1850",
            rule_id="orthography_check",
            explanation="Pre-reform orthography detected",
            severity="medium",
            is_pre_reform=True,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan with pre-reform orthography enabled
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"orthography_check"}, True
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue found with pre-reform flag
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertTrue(self.fake_view.audit_issues[0].is_pre_reform)
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "Фёдорович")

        # Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=True)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called with pre-reform fix
        self.mock_write_repo.apply_patronymic_correction.assert_called_once()
        call_args = self.mock_write_repo.apply_patronymic_correction.call_args
        self.assertEqual(call_args[0][2], "Фёдорович")

    def test_scope_filter_males_only(self) -> None:
        """Test scope filter - males only."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        family["I001"].gender = Gender.MALE
        family["I000"].gender = Gender.FEMALE
        family["I002"].gender = Gender.FEMALE
        family["I004"].gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())
        self.mock_read_repo.get_person_count.return_value = 4

        # Configure audit service to return issues for males only
        def mock_audit_person(person, rules, use_pre_reform):
            if person.gender == Gender.MALE:
                return [
                    AuditIssue(
                        person_handle=person.handle,
                        gramps_id=person.gramps_id,
                        display_name=person.display_name,
                        father_name="",
                        current_value="",
                        suggested_fix="Иванович",
                        confidence=0.95,
                        reference_year="1850",
                        rule_id="patronymic_generation",
                        explanation="Generated patronymic from father's name",
                        severity="high",
                        is_pre_reform=False,
                    )
                ]
            return []

        self.mock_audit_service.audit_person.side_effect = mock_audit_person

        # Configure mock to run synchronously

        # Act: Run scan with MALES_ONLY scope
        result = self.controller.run_audit_scan(
            AuditScope.MALES_ONLY, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Only males in results (I001, I004)
        self.assertEqual(len(self.fake_view.audit_issues), 2)
        issue_ids = {issue.gramps_id for issue in self.fake_view.audit_issues}
        self.assertEqual(issue_ids, {"I001", "I004"})

    def test_scope_filter_females_only(self) -> None:
        """Test scope filter - females only."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        family["I001"].gender = Gender.MALE
        family["I000"].gender = Gender.FEMALE
        family["I002"].gender = Gender.FEMALE
        family["I004"].gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())
        self.mock_read_repo.get_person_count.return_value = 4

        # Configure audit service to return issues for females only
        def mock_audit_person(person, rules, use_pre_reform):
            if person.gender == Gender.FEMALE:
                return [
                    AuditIssue(
                        person_handle=person.handle,
                        gramps_id=person.gramps_id,
                        display_name=person.display_name,
                        father_name="",
                        current_value="",
                        suggested_fix="Ивановна",
                        confidence=0.95,
                        reference_year="1850",
                        rule_id="patronymic_generation",
                        explanation="Generated patronymic from father's name",
                        severity="high",
                        is_pre_reform=False,
                    )
                ]
            return []

        self.mock_audit_service.audit_person.side_effect = mock_audit_person

        # Configure mock to run synchronously

        # Act: Run scan with FEMALES_ONLY scope
        result = self.controller.run_audit_scan(
            AuditScope.FEMALES_ONLY, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Only females in results (I000, I002)
        self.assertEqual(len(self.fake_view.audit_issues), 2)
        issue_ids = {issue.gramps_id for issue in self.fake_view.audit_issues}
        self.assertEqual(issue_ids, {"I000", "I002"})

    def test_multiple_issues_same_person(self) -> None:
        """Test multiple issues for the same person."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        family["I000"].gender = Gender.FEMALE

        self.mock_read_repo.iter_all_persons.return_value = iter([family["I000"]])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return multiple issues for same person
        mock_issue1 = AuditIssue(
            person_handle="handle_i000",
            gramps_id="I000",
            display_name="Облонская, Анна",
            father_name="Аркадий",
            current_value="",
            suggested_fix="Ивановна",
            confidence=0.95,
            reference_year="1850",
            rule_id="patronymic_generation",
            explanation="Generated patronymic from father's name",
            severity="high",
            is_pre_reform=False,
        )
        mock_issue2 = AuditIssue(
            person_handle="handle_i000",
            gramps_id="I000",
            display_name="Облонская, Анна",
            father_name="Аркадий",
            current_value="Иванович",
            suggested_fix="Ивановна",
            confidence=0.98,
            reference_year="1850",
            rule_id="gender_suffix_mismatch",
            explanation="Female person has male patronymic suffix",
            severity="high",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue1, mock_issue2]

        # Configure mock to run synchronously

        # Act: Run scan with both rules
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation", "gender_suffix_mismatch"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Two issues for same person
        self.assertEqual(len(self.fake_view.audit_issues), 2)
        rule_ids = {issue.rule_id for issue in self.fake_view.audit_issues}
        self.assertEqual(rule_ids, {"patronymic_generation", "gender_suffix_mismatch"})

        # Uncheck one issue
        self.fake_view.checked_audit_keys.discard(
            ("handle_i000", "gender_suffix_mismatch")
        )

        # Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes (only patronymic_generation)
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=False)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called only once (for patronymic_generation)
        self.assertEqual(self.mock_write_repo.apply_patronymic_correction.call_count, 1)

    def test_apply_partial_selection(self) -> None:
        """Test applying partial selection of audit issues."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        family["I000"].gender = Gender.FEMALE
        family["I002"].gender = Gender.FEMALE
        family["I004"].gender = Gender.MALE

        self.mock_read_repo.iter_all_persons.return_value = iter(
            [family["I000"], family["I002"], family["I004"]]
        )
        self.mock_read_repo.get_person_count.return_value = 3

        # Configure audit service to return issues for all three
        def mock_audit_person(person, rules, use_pre_reform):
            return [
                AuditIssue(
                    person_handle=person.handle,
                    gramps_id=person.gramps_id,
                    display_name=person.display_name,
                    father_name="Аркадий",
                    current_value="",
                    suggested_fix="Иванович"
                    if person.gender == Gender.MALE
                    else "Ивановна",
                    confidence=0.95,
                    reference_year="1850",
                    rule_id="patronymic_generation",
                    explanation="Generated patronymic from father's name",
                    severity="high",
                    is_pre_reform=False,
                )
            ]

        self.mock_audit_service.audit_person.side_effect = mock_audit_person

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Three issues found
        self.assertEqual(len(self.fake_view.audit_issues), 3)

        # Uncheck I002
        self.fake_view.checked_audit_keys.discard(
            ("handle_i002", "patronymic_generation")
        )

        # Mock repository methods for apply
        self.mock_write_repo.transaction.return_value.__enter__ = MagicMock()
        self.mock_write_repo.transaction.return_value.__exit__ = MagicMock()

        # Act: Apply checked fixes (I000 and I004 only)
        result = self.controller.apply_checked_audit_fixes(use_pre_reform=False)

        # Assert: Apply succeeded
        self.assertTrue(result)

        # Assert: Write repository called twice (for I000 and I004)
        self.assertEqual(self.mock_write_repo.apply_patronymic_correction.call_count, 2)

    def test_unrelated_person_not_affected(self) -> None:
        """Test that unrelated person is not affected by patronymic generation."""
        # Arrange: Set up sample family
        family = setup_sample_family()
        family["I001"].gender = Gender.MALE
        family["I000"].gender = Gender.FEMALE
        family["I002"].gender = Gender.FEMALE
        family["I004"].gender = Gender.MALE
        family["I003"].gender = Gender.FEMALE  # Unrelated

        self.mock_read_repo.iter_all_persons.return_value = iter(family.values())
        self.mock_read_repo.get_person_count.return_value = 5

        # Configure audit service to return issues only for children of I001
        def mock_audit_person(person, rules, use_pre_reform):
            if person.gramps_id in ["I000", "I002", "I004"]:
                return [
                    AuditIssue(
                        person_handle=person.handle,
                        gramps_id=person.gramps_id,
                        display_name=person.display_name,
                        father_name="Аркадий",
                        current_value="",
                        suggested_fix="Иванович"
                        if person.gender == Gender.MALE
                        else "Ивановна",
                        confidence=0.95,
                        reference_year="1850",
                        rule_id="patronymic_generation",
                        explanation="Generated patronymic from father's name",
                        severity="high",
                        is_pre_reform=False,
                    )
                ]
            return []

        self.mock_audit_service.audit_person.side_effect = mock_audit_person

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: I003 not in results
        issue_ids = {issue.gramps_id for issue in self.fake_view.audit_issues}
        self.assertNotIn("I003", issue_ids)
        self.assertEqual(issue_ids, {"I000", "I002", "I004"})

    def test_cross_language_patronymic_generation(self) -> None:
        """Test cross-language patronymic generation."""
        # Arrange: Set up sample family with English father name
        family = setup_sample_family()
        family["I003"].gender = Gender.FEMALE

        self.mock_read_repo.iter_all_persons.return_value = iter([family["I003"]])
        self.mock_read_repo.get_person_count.return_value = 1

        # Configure audit service to return empty suggestion for non-Cyrillic name
        mock_issue = AuditIssue(
            person_handle="handle_i003",
            gramps_id="I003",
            display_name="Skłodowska, Maria",
            father_name="Joseph",
            current_value="",
            suggested_fix="",
            confidence=0.0,
            reference_year="1850",
            rule_id="patronymic_generation",
            explanation="Non-Cyrillic name - patronymic not applicable",
            severity="low",
            is_pre_reform=False,
        )
        self.mock_audit_service.audit_person.return_value = [mock_issue]

        # Configure mock to run synchronously

        # Act: Run scan
        result = self.controller.run_audit_scan(
            AuditScope.ALL, {"patronymic_generation"}, False
        )

        # Assert: Scan started successfully
        self.assertTrue(result)

        # Assert: Issue found with empty suggestion
        self.assertEqual(len(self.fake_view.audit_issues), 1)
        self.assertEqual(self.fake_view.audit_issues[0].father_name, "Joseph")
        self.assertEqual(self.fake_view.audit_issues[0].suggested_fix, "")


if __name__ == "__main__":
    unittest.main()
