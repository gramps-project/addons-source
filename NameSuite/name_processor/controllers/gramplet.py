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

from typing import TYPE_CHECKING

from name_processor.models.infer import PatronymicInferenceStatus

if TYPE_CHECKING:
    from name_processor.repositories.gramps_read import GrampsReadRepository
    from name_processor.repositories.gramps_write import GrampsWriteRepository
    from name_processor.services.patronymic import PatronymicInferenceService
    from name_processor.services.chronology import ChronologyService
    from name_processor.protocols.view import GrampletViewPort, BackgroundTaskRunner


class GrampletController:
    def __init__(
        self,
        view: GrampletViewPort,
        patronymic_service: PatronymicInferenceService,
        chronology_service: ChronologyService,
        read_repo: GrampsReadRepository,
        write_repo: GrampsWriteRepository,
        task_runner: BackgroundTaskRunner,
    ) -> None:
        self._view = view
        self._patronymic_service = patronymic_service
        self._chronology_service = chronology_service
        self._read_repo = read_repo
        self._write_repo = write_repo
        self._task_runner = task_runner

        self._suggested_patronymic: str | None = None
        self._current_handle: str | None = None

    def initialize_background_tasks(self) -> None:
        """Starts the non-blocking database scan and refreshes on completion."""

        def on_median_calculated(years: list[int] | None) -> None:
            # Update the service with the calculated median year before refreshing
            self._chronology_service.update_median_year(years)
            self.refresh()

        self._task_runner.run_chunked(
            self._chronology_service.generate_years(chunk_size=500),
            on_complete=on_median_calculated,
        )

    def refresh(self) -> None:
        """Re-evaluates the active person without requiring external state."""
        if self._current_handle:
            self.on_active_changed(self._current_handle)

    def on_active_changed(self, handle: str) -> None:
        self._current_handle = handle
        self._suggested_patronymic = None

        if not handle:
            self._view.show_status_message(
                PatronymicInferenceStatus.NO_ACTIVE_PERSON, apply_sensitive=False
            )
            return

        res = self._patronymic_service.infer_patronymic(handle)

        if res.status == PatronymicInferenceStatus.SUCCESS:
            if res.patronymic is None or res.father_name is None:
                self._view.show_status_message(
                    PatronymicInferenceStatus.UNKNOWN_ERROR, apply_sensitive=False
                )
                return
            self._suggested_patronymic = res.patronymic
            self._view.show_suggestion(res.patronymic, res.father_name)
        else:
            self._view.show_status_message(res.status, apply_sensitive=False)

    def on_apply_clicked(self) -> None:
        if not self._current_handle or not self._suggested_patronymic:
            return

        try:
            self._write_repo.update_patronymic_names(
                {self._current_handle: self._suggested_patronymic}
            )

            self._view.show_status_message(
                PatronymicInferenceStatus.SUCCESS, apply_sensitive=False
            )
        except Exception as e:
            self._view.display_error("Update Failed", str(e))
