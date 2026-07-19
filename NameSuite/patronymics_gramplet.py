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

from gramps.gen.plug import Gramplet

from name_processor.controllers.gramplet import GrampletController
from name_processor.models.infer import PatronymicInferenceStatus
from name_processor.repositories.entity_cache import EntityCache
from name_processor.repositories.caching_read import CachingReadRepository
from name_processor.repositories.invalidation import InvalidationSignalManager
from name_processor.repositories.gramps_read import GrampsReadRepository
from name_processor.repositories.gramps_write import GrampsWriteRepository
from name_processor.services.patronymic import PatronymicInferenceService
from name_processor.services.confidence import ConfidenceService
from name_processor.services.chronology import ChronologyService
from name_processor.views.gtk_runner import GtkBackgroundTaskRunner
from name_processor.views.gramplet import GrampletView

if TYPE_CHECKING:
    from gramps.gen.types import PersonHandle


class PatronymicSuggestionGramplet(Gramplet):
    def __init__(self, gui, nav_group: int = 0) -> None:
        # Declare placeholders BEFORE running the parent constructor
        self._view = GrampletView(self)
        self._controller: GrampletController | None = None
        self._read_repo: CachingReadRepository | GrampsReadRepository | None = None
        self._entity_cache: EntityCache | None = None
        self._signal_manager: InvalidationSignalManager | None = None
        self._write_repo: GrampsWriteRepository | None = None
        self._confidence_service: ConfidenceService | None = None
        self._chronology_service: ChronologyService | None = None
        self._patronymic_service: PatronymicInferenceService | None = None

        # Initialize early so _disconnect_db_signals doesn't throw an AttributeError
        self._db_signal_handles: list = []

        # Run super constructor (which invokes init() and db_changed())
        super().__init__(gui, nav_group)

    def init(self) -> None:
        """
        Runs once when the Gramplet is registered.
        Sets up the static visual interface.
        """
        self._view.init()

        # Embed the view's widget into the Gramplet container
        self._view.embed(self.gui)

    def db_changed(self) -> None:
        """
        Overridden to recreate the database-dependent dependency graph
        whenever the database state changes (e.g., opened, switched, or closed).
        """
        self._disconnect_db_signals()

        if self.dbstate.is_open():
            # Recreate repositories tied to the new database session
            self._entity_cache = EntityCache()
            self._read_repo = CachingReadRepository(self.dbstate.db, self._entity_cache)
            self._signal_manager = InvalidationSignalManager(
                self.dbstate.db, self._entity_cache
            )
            self._write_repo = GrampsWriteRepository(self.dbstate.db)

            # Recreate domain services
            self._confidence_service = ConfidenceService(self._read_repo)
            self._chronology_service = ChronologyService(self._read_repo)
            self._patronymic_service = PatronymicInferenceService(
                self._read_repo, self._confidence_service, self._chronology_service
            )

            # Recreate the controller and link it to the existing view
            self._task_runner = GtkBackgroundTaskRunner()
            self._controller = GrampletController(
                self._view,
                self._patronymic_service,
                self._chronology_service,
                self._read_repo,
                self._write_repo,
                self._task_runner,
            )
            if self._view:
                self._view.set_controller(self._controller)

            # Connect to database modification signals
            self._db_signal_handles = [
                self.dbstate.db.connect("person-update", self._on_data_modified),
                self.dbstate.db.connect("person-rebuild", self._on_data_modified),
                self.dbstate.db.connect("family-update", self._on_data_modified),
                self.dbstate.db.connect("family-rebuild", self._on_data_modified),
            ]

            # Hand off the non-blocking database scan orchestration to the controller
            self._controller.initialize_background_tasks()
        else:
            # DB has closed - cleanly tear down backend dependencies
            self._controller = None
            if self._view:
                self._view.set_controller(None)
                self._view.show_status_message(
                    PatronymicInferenceStatus.NO_ACTIVE_PERSON, apply_sensitive=False
                )

    def active_changed(self, handle: PersonHandle) -> None:
        """Called automatically by Gramps when the active person changes."""
        if self.dbstate.is_open() and self._controller:
            self._controller.on_active_changed(handle)

    def _disconnect_db_signals(self) -> None:
        """Safely unhooks database signals to prevent memory leaks."""
        if (
            self._db_signal_handles
            and self.dbstate
            and getattr(self.dbstate, "db", None)
        ):
            for handle in self._db_signal_handles:
                self.dbstate.db.disconnect(handle)
        self._db_signal_handles = []

        if self._signal_manager:
            self._signal_manager.disconnect_all()
            self._signal_manager = None
        self._entity_cache = None

    def _on_data_modified(self, *args, **kwargs) -> None:
        """Triggered by Gramps on Edit, Undo, or Redo."""
        if self._controller:
            self._controller.refresh()
