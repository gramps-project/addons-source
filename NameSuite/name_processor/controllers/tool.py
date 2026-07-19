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

import re
from typing import TYPE_CHECKING, Any, Generator

from name_processor.models.audit import AuditScope
from name_processor.models.person import Gender
from name_processor.models.renamer import AltAction, MatchMode
from name_processor.presentation.row_schemas import GivenRowData

if TYPE_CHECKING:
    from names_tool import NamesTool
    from name_processor.models.audit import AuditIssue
    from name_processor.models.renamer import MatchMode
    from name_processor.repositories.gramps_read import (
        GrampsPersonProxy,
        GrampsReadRepository,
    )
    from name_processor.repositories.gramps_write import GrampsWriteRepository
    from name_processor.services.alt_names import AltNamesService
    from name_processor.services.audit import AuditService
    from name_processor.services.chronology import ChronologyService
    from name_processor.services.patronymic import PatronymicInferenceService
    from name_processor.services.renamer import RenamerService, RenameConfig
    from name_processor.protocols.view import ToolViewPort, BackgroundTaskRunner


class ToolController:
    def __init__(
        self,
        tool_instance: NamesTool,
        view: ToolViewPort,
        read_repo: GrampsReadRepository,
        write_repo: GrampsWriteRepository,
        renamer_service: RenamerService,
        alt_names_service: AltNamesService,
        patronymic_service: PatronymicInferenceService,
        audit_service: AuditService,
        chronology_service: ChronologyService,
        task_runner: BackgroundTaskRunner,
    ) -> None:
        self.tool = tool_instance
        self.dbstate = tool_instance.dbstate
        self.user = getattr(tool_instance, "user", None)

        # Kept strictly for View compatibility (`if self.controller.db.is_open()`)
        self.db = self.dbstate.db

        # MVCS Layers
        self._view = view
        self._read_repo = read_repo
        self._write_repo = write_repo
        self._renamer_service = renamer_service
        self._alt_names_service = alt_names_service
        self._audit_service = audit_service
        self._chronology_service = chronology_service
        self._task_runner = task_runner

        # Guard to prevent overlapping async scan operations
        self._is_rename_scanning = False
        self._is_audit_scanning = False

        # State Caches
        self._given_names_cache: set[str] = set()
        self._rename_candidates: dict[str, GivenRowData] = {}
        self._audit_candidates: dict[tuple[str, str], AuditIssue] = {}

    def cleanup(self) -> None:
        pass

    def get_gramps_person(self, handle: str) -> Any:
        """Used by the view to open the native Gramps Person Editor."""
        return self._read_repo.get_raw_person(handle)

    # ==========================================
    # Initialization & Caching
    # ==========================================
    def initialize_median_year_async(self) -> None:
        self._task_runner.run_chunked(
            self._chronology_service.generate_years(),
            self._chronology_service.update_median_year,
        )

    def initialize_given_names_async(self) -> None:
        def generator(chunk_size: int = 500) -> Generator[None, None, set[str]]:
            names = set()
            count = 0
            for proxy in self._read_repo.iter_all_persons():
                if proxy.given_name:
                    names.add(proxy.given_name)
                count += 1
                if count % chunk_size == 0:
                    yield None
            return names

        def on_complete(final_names: set[str] | None) -> None:
            if final_names:
                self._given_names_cache.update(final_names)
                self._view.setup_given_name_autocompletion()

        self._task_runner.run_chunked(generator(), on_complete)

    def get_given_names(self) -> set[str]:
        return self._given_names_cache

    # ==========================================
    # Tab 1: Rename Names
    # ==========================================
    def _validate_rename_input(
        self, source: str, target: str, match_mode: MatchMode
    ) -> tuple[bool, str | None]:
        """
        Validates rename scan input parameters.

        Args:
            source: Source name pattern to search for
            target: Target name to replace with
            match_mode: Match mode (EXACT, SUBSTRING, or REGEX)

        Returns:
            tuple[bool, str | None]: (is_valid, error_message)
            - If valid: (True, None)
            - If invalid: (False, error_message)
        """
        # Validate source is not empty or whitespace-only
        if not source or not source.strip():
            return False, "Source name cannot be empty."

        # Validate regex pattern when Regular Expression match mode is selected
        if match_mode == MatchMode.REGEX:
            try:
                re.compile(source)
            except re.error:
                return False, "Invalid regular expression pattern in source name."

        # Validate target is not whitespace-only
        if target and not target.strip():
            return False, "Target name cannot contain only whitespace."

        return True, None

    def on_rename_scan_requested(
        self, source: str, target: str, match_mode: MatchMode
    ) -> None:
        """
        Handles rename scan request from the view after input validation.

        Validates the input parameters and shows an error dialog via the view
        if validation fails. Otherwise, initiates the scan.

        Args:
            source: Source name pattern to search for
            target: Target name to replace with
            match_mode: Match mode (EXACT, SUBSTRING, or REGEX)
        """
        is_valid, error_message = self._validate_rename_input(
            source, target, match_mode
        )

        if not is_valid:
            assert error_message is not None
            self._view.show_ok_dialog("Invalid Input", error_message)
            return

        self.run_rename_scan(source, target, match_mode)

    def _propose_rename(
        self, person: GrampsPersonProxy, cfg: RenameConfig, preserve_alt: bool
    ) -> GivenRowData | None:
        """Evaluates a single person and returns UI row data if a match occurs."""
        proposed_name = self._renamer_service.evaluate_person(
            person.given_name or "", cfg
        )
        if not proposed_name:
            return None

        return GivenRowData(
            checkbox=True,
            gramps_id=person.gramps_id,
            display_name=person.display_name,
            current=person.given_name or "",
            proposed=proposed_name,
            alt_action=(AltAction.PRESERVE if preserve_alt else AltAction.OVERWRITE),
            handle=person.handle,
        )

    def run_rename_scan(self, source: str, target: str, match_mode: MatchMode) -> bool:
        if self._is_rename_scanning:
            return False

        self._is_rename_scanning = True
        self._view.clear_rename_proposals()
        self._rename_candidates.clear()
        preserve_alt = self._view.is_preserve_alt_enabled()

        def scan_generator(
            chunk_size: int = 250,
        ) -> Generator[None, None, tuple[bool, str | None]]:
            try:
                cfg = self._renamer_service.create_config(match_mode, source, target)
            except re.error as e:
                return False, str(e.msg)

            found_any = False
            count = 0
            for person in self._read_repo.iter_all_persons():
                row_data = self._propose_rename(person, cfg, preserve_alt)
                if row_data:
                    self._rename_candidates[person.handle] = row_data
                    self._view.append_rename_proposal(row_data)
                    found_any = True
                count += 1
                if count % chunk_size == 0:
                    yield None
            return found_any, None

        def on_complete(result: tuple[bool, str | None] | None) -> None:
            self._is_rename_scanning = False
            if result is None:
                return
            found_any, error_msg = result
            if error_msg:
                self._view.show_ok_dialog("Invalid Regular Expression", error_msg)
                return

            self._view.update_given_apply_button()
            if not found_any:
                self._view.show_ok_dialog(
                    "No Results", "No matching given names found."
                )

        self._task_runner.run_chunked(scan_generator(), on_complete)
        return True

    def update_preserve_alt(self, action: AltAction) -> None:
        """Dynamically updates the proposed rename action on all stored objects
        and refreshes the view.
        """
        for row_data in self._rename_candidates.values():
            self._rename_candidates[row_data.handle] = row_data._replace(
                alt_action=action
            )

        self._view.update_given_store_actions(action)

    def apply_checked_renamings(self) -> bool:
        handles = self._view.get_checked_renaming_handles()
        if not handles:
            return False

        preserve_alt = self._view.is_preserve_alt_enabled()
        approved_changes = [
            self._rename_candidates[h] for h in handles if h in self._rename_candidates
        ]

        with self._write_repo.transaction("Batch Given Name Renaming") as t:
            for change in approved_changes:
                self._write_repo.apply_first_name_correction(
                    t, change.handle, change.proposed, preserve_alt
                )

        return True

    # ==========================================
    # Tab 2: Audit Patronymics
    # ==========================================
    def get_available_audit_rules(self) -> list[str]:
        return self._audit_service.get_available_audit_rules()

    def run_audit_scan(
        self, audit_scope: AuditScope, enabled_rules_set: set[str], use_pre_reform: bool
    ) -> bool:
        if self._is_audit_scanning:
            return False

        self._is_audit_scanning = True
        self._view.clear_audit_results()
        self._audit_candidates.clear()

        # Get total person count dynamically from the repo for the progress bar
        total_people = self._read_repo.get_person_count()

        def scan_generator(chunk_size: int = 50) -> Generator[None, None, int]:
            processed_count = 0
            for person in self._read_repo.iter_all_persons():
                processed_count += 1

                # Apply scope filter
                if audit_scope == AuditScope.MALES_ONLY:
                    if person.gender != Gender.MALE:
                        continue
                elif audit_scope == AuditScope.FEMALES_ONLY:
                    if person.gender != Gender.FEMALE:
                        continue

                issues = self._audit_service.audit_person(
                    person, enabled_rules_set, use_pre_reform
                )
                for issue in issues:
                    self._audit_candidates[(person.handle, issue.rule_id)] = issue
                    self._view.append_issue(issue)

                if processed_count % chunk_size == 0:
                    fraction = (
                        min(processed_count / total_people, 1.0)
                        if total_people > 0
                        else 1.0
                    )
                    self._view.update_audit_progress(
                        fraction,
                        f"{min(processed_count, total_people)} / {total_people}",
                    )
                    yield None

            return processed_count

        def on_complete(total_processed: int | None) -> None:
            self._is_audit_scanning = False
            self._view.on_audit_complete(len(self._audit_candidates))

        self._task_runner.run_chunked(scan_generator(), on_complete)
        return True

    def apply_checked_audit_fixes(self, use_pre_reform: bool) -> bool:
        keys = self._view.get_checked_audit_keys()
        if not keys:
            return False

        with self._write_repo.transaction("Batch Patronymic Audit Fixes") as t:
            for key in keys:
                issue = self._audit_candidates.get(key)
                if not issue:
                    continue

                self._write_repo.apply_patronymic_correction(
                    t, issue.person_handle, issue.suggested_fix
                )

        return True
