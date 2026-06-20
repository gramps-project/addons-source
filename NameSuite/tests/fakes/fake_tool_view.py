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

from name_processor.models.audit import AuditIssue
from name_processor.models.renamer import AltAction
from name_processor.presentation.row_schemas import GivenRowData
from name_processor.protocols.view import ToolViewPort


class FakeToolView(ToolViewPort):
    """Headless implementation of ToolViewPort for E2E testing.

    Records all method calls and maintains in-memory state for assertions.
    No GTK dependencies.
    """

    def __init__(self) -> None:
        # In-memory stores for rename proposals
        self.rename_proposals: list[GivenRowData] = []
        self.checked_rename_handles: set[str] = set()

        # In-memory stores for audit results
        self.audit_issues: list[AuditIssue] = []
        self.checked_audit_keys: set[tuple[str, str]] = set()

        # State tracking
        self.preserve_alt_enabled: bool = False
        self.enabled_audit_rules: set[str] = set()

        # Dialog call tracking
        self.dialog_calls: list[tuple[str, str]] = []

        # Progress tracking
        self.audit_progress_updates: list[tuple[float, str]] = []
        self.audit_complete_total: int | None = None

        # Button state tracking
        self.given_apply_button_updated_count: int = 0
        self.audit_apply_button_updated_count: int = 0

        # Store action updates
        self.store_action_updates: list[AltAction] = []

        # Clear calls tracking
        self.clear_rename_proposals_called: int = 0
        self.clear_audit_results_called: int = 0

        # Autocompletion tracking
        self.autocompletion_names: set[str] = set()
        self.autocompletion_setup_called: int = 0

    # Read path (controller → view)
    def clear_rename_proposals(self) -> None:
        self.clear_rename_proposals_called += 1
        self.rename_proposals.clear()
        self.checked_rename_handles.clear()

    def append_rename_proposal(self, row: GivenRowData) -> None:
        self.rename_proposals.append(row)
        # Default to checked when appended
        self.checked_rename_handles.add(row.handle)

    def update_given_store_actions(self, action: AltAction) -> None:
        self.store_action_updates.append(action)
        # Update all proposals with new action
        self.rename_proposals = [
            row._replace(alt_action=action) for row in self.rename_proposals
        ]

    def update_given_apply_button(self) -> None:
        self.given_apply_button_updated_count += 1

    def clear_audit_results(self) -> None:
        self.clear_audit_results_called += 1
        self.audit_issues.clear()
        self.checked_audit_keys.clear()
        self.audit_progress_updates.clear()
        self.audit_complete_total = None

    def append_issue(self, issue: AuditIssue) -> None:
        self.audit_issues.append(issue)
        # Default to checked when appended
        self.checked_audit_keys.add((issue.person_handle, issue.rule_id))

    def update_audit_progress(self, fraction: float, text: str) -> None:
        self.audit_progress_updates.append((fraction, text))

    def on_audit_complete(self, total_found: int) -> None:
        self.audit_complete_total = total_found

    def update_audit_apply_button(self) -> None:
        self.audit_apply_button_updated_count += 1

    def setup_given_name_autocompletion(self) -> None:
        # Track that autocompletion was set up
        self.autocompletion_setup_called += 1

    def show_ok_dialog(self, title: str, message: str) -> None:
        self.dialog_calls.append((title, message))

    # Write path (view → controller queries)
    def get_checked_renaming_handles(self) -> set[str]:
        return self.checked_rename_handles.copy()

    def get_checked_audit_keys(self) -> set[tuple[str, str]]:
        return self.checked_audit_keys.copy()

    def is_preserve_alt_enabled(self) -> bool:
        return self.preserve_alt_enabled

    def get_audit_result_count(self) -> int:
        return len(self.audit_issues)

    def get_enabled_audit_rules(self) -> set[str]:
        return self.enabled_audit_rules.copy()

    # Helper methods for test control
    def set_preserve_alt_enabled(self, enabled: bool) -> None:
        """Test helper to set preserve alt state."""
        self.preserve_alt_enabled = enabled

    def set_enabled_audit_rules(self, rules: set[str]) -> None:
        """Test helper to set enabled audit rules."""
        self.enabled_audit_rules = rules

    def uncheck_rename_handle(self, handle: str) -> None:
        """Test helper to uncheck a specific rename proposal."""
        self.checked_rename_handles.discard(handle)

    def uncheck_audit_key(self, key: tuple[str, str]) -> None:
        """Test helper to uncheck a specific audit issue."""
        self.checked_audit_keys.discard(key)

    def set_autocompletion_names(self, names: set[str]) -> None:
        """Test helper to set the names available for autocompletion."""
        self.autocompletion_names = names

    def get_autocompletion_suggestions(self, prefix: str) -> list[str]:
        """
        Test helper to get autocompletion suggestions for a given prefix.
        Simulates GTK EntryCompletion behavior.
        """
        return sorted(
            [name for name in self.autocompletion_names if name.startswith(prefix)]
        )
