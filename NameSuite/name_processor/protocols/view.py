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

# name_processor/protocols/view.py
from collections.abc import Callable, Generator
from typing import Protocol, TypeVar

from name_processor.models.audit import AuditIssue
from name_processor.models.infer import PatronymicInferenceStatus
from name_processor.models.renamer import AltAction
from name_processor.presentation.row_schemas import GivenRowData

T = TypeVar("T")


class ToolViewPort(Protocol):
    """Protocol for ToolWindow UI."""

    # Read path (controller → view)
    def clear_rename_proposals(self) -> None: ...

    def append_rename_proposal(self, row: GivenRowData) -> None: ...

    def update_given_store_actions(self, action: AltAction) -> None: ...

    def update_given_apply_button(self) -> None: ...

    def clear_audit_results(self) -> None: ...

    def append_issue(self, issue: AuditIssue) -> None: ...

    def update_audit_progress(self, fraction: float, text: str) -> None: ...

    def on_audit_complete(self, total_found: int) -> None: ...

    def setup_given_name_autocompletion(self) -> None: ...

    def show_ok_dialog(self, title: str, message: str) -> None: ...

    # Write path (view → controller queries)
    def get_checked_renaming_handles(self) -> set[str]: ...

    def get_checked_audit_keys(self) -> set[tuple[str, str]]: ...

    def is_preserve_alt_enabled(self) -> bool: ...


class GrampletViewPort(Protocol):
    """Protocol for GrampletView UI."""

    def show_status_message(
        self, message_key: PatronymicInferenceStatus, apply_sensitive: bool = False
    ) -> None: ...

    def show_suggestion(self, patronymic: str, father_name: str) -> None: ...

    def display_error(self, title_key: str, message: str) -> None: ...


class BackgroundTaskRunner(Protocol):
    """Protocol for running chunked background tasks without freezing UI."""

    def run_chunked(
        self,
        generator: Generator[None, None, T],
        on_complete: Callable[[T | None], None] | None = None,
    ) -> None:
        """
        Execute a generator in chunks, yielding control periodically.

        Args:
            generator: A generator yielding control periodically.
            on_complete: Callback executed with the generator's final return value.
        """
        ...
