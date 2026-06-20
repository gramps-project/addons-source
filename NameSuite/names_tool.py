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

from gramps.gui.plug import tool

from name_processor.controllers.tool import ToolController
from name_processor.repositories.entity_cache import EntityCache
from name_processor.repositories.caching_read import CachingReadRepository
from name_processor.repositories.invalidation import InvalidationSignalManager
from name_processor.repositories.gramps_read import GrampsReadRepository
from name_processor.repositories.gramps_write import GrampsWriteRepository
from name_processor.views.gtk_runner import GtkBackgroundTaskRunner
from name_processor.views.tool import ToolWindow

# Domain Services
from name_processor.services.audit import AuditService
from name_processor.services.alt_names import AltNamesService
from name_processor.services.chronology import ChronologyService
from name_processor.services.confidence import ConfidenceService
from name_processor.services.patronymic import PatronymicInferenceService
from name_processor.services.renamer import RenamerService


class NamesTool(tool.Tool):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        # Declare placeholders BEFORE running the parent constructor
        self._view = ToolWindow(None)
        self._controller: ToolController | None = None
        self._read_repo: CachingReadRepository | GrampsReadRepository | None = None
        self._entity_cache: EntityCache | None = None
        self._signal_manager: InvalidationSignalManager | None = None
        self._write_repo: GrampsWriteRepository | None = None
        self._chronology_service: ChronologyService | None = None
        self._confidence_service: ConfidenceService | None = None
        self._patronymic_service: PatronymicInferenceService | None = None
        self._alt_names_service: AltNamesService | None = None
        self._renamer_service: RenamerService | None = None
        self._audit_service: AuditService | None = None
        self._task_runner: GtkBackgroundTaskRunner | None = None

        # Initialize early so _disconnect_db_signals doesn't throw an AttributeError
        self._db_signal_handles: list = []

        super().__init__(dbstate, options_class, name)
        self.dbstate = dbstate
        self.user = user

        # Subscribe to database-changed signal (Tool base class doesn't do this automatically)
        self.dbstate.connect("database-changed", self.db_changed)

        # Initialize dependencies
        self._initialize_dependencies()

    def run(self) -> None:
        if self._controller:
            self._view.window.show_all()

    def db_changed(self, db) -> None:
        """
        Overridden to recreate the database-dependent dependency graph
        whenever the database state changes (e.g., opened, switched, or closed).
        """
        self._disconnect_db_signals()

        if self.dbstate.is_open():
            # Clear view state
            if self._view:
                self._view.clear_rename_proposals()
                self._view.clear_audit_results()

            # Recreate dependencies with new database
            self._initialize_dependencies()

            # Connect to database modification signals
            self._db_signal_handles = [
                self.dbstate.db.connect("person-update", self._on_data_modified),
                self.dbstate.db.connect("person-rebuild", self._on_data_modified),
                self.dbstate.db.connect("family-update", self._on_data_modified),
                self.dbstate.db.connect("family-rebuild", self._on_data_modified),
            ]
        else:
            # DB has closed - cleanly tear down backend dependencies
            self._controller = None

    def _initialize_dependencies(self) -> None:
        """
        Initialize or reinitialize all database-dependent dependencies.
        Called from __init__ and db_changed().
        """
        # Repositories
        self._entity_cache = EntityCache()
        self._read_repo = CachingReadRepository(self.dbstate.db, self._entity_cache)
        self._signal_manager = InvalidationSignalManager(
            self.dbstate.db, self._entity_cache
        )
        self._write_repo = GrampsWriteRepository(self.dbstate.db)

        # Domain Services
        self._chronology_service = ChronologyService(self._read_repo)
        self._confidence_service = ConfidenceService(self._read_repo)
        self._patronymic_service = PatronymicInferenceService(
            self._read_repo, self._confidence_service, self._chronology_service
        )
        self._alt_names_service = AltNamesService(self._read_repo)
        self._renamer_service = RenamerService()
        self._audit_service = AuditService(
            read_repo=self._read_repo,
            chronology_service=self._chronology_service,
            confidence_service=self._confidence_service,
        )

        # Presentation Layer
        self._task_runner = GtkBackgroundTaskRunner()
        self._controller = ToolController(
            tool_instance=self,
            view=self._view,
            read_repo=self._read_repo,
            write_repo=self._write_repo,
            patronymic_service=self._patronymic_service,
            renamer_service=self._renamer_service,
            alt_names_service=self._alt_names_service,
            audit_service=self._audit_service,
            chronology_service=self._chronology_service,
            task_runner=self._task_runner,
        )

        self._view.set_controller(self._controller)

    def _disconnect_db_signals(self) -> None:
        """Safely unhooks database modification signals to prevent memory leaks."""
        # Disconnect database modification signals (person-update, family-update, etc.)
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
            # Clear cached data to force refresh
            self._controller._given_names_cache.clear()
            self._controller._rename_candidates.clear()
            self._controller._audit_candidates.clear()


class NamesToolOptions(tool.ToolOptions):
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
