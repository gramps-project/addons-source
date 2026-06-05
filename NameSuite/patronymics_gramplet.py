from gramps.gen.plug import Gramplet
from gramps.gen.types import PersonHandle

from name_processor.controllers.gramplet import GrampletController
from name_processor.models.infer import PatronymicInferenceStatus
from name_processor.repositories.gramps_read import GrampsReadRepository
from name_processor.repositories.gramps_write import GrampsWriteRepository
from name_processor.services.patronymic import PatronymicInferenceService
from name_processor.services.confidence import ConfidenceService
from name_processor.services.chronology import ChronologyService
from name_processor.utils.gtk_runner import run_in_idle_loop
from name_processor.views.gramplet import GrampletView


class PatronymicSuggestionGramplet(Gramplet):
    def __init__(self, gui, nav_group: int = 0) -> None:
        # 1. Declare placeholders BEFORE running the parent constructor
        self._view = GrampletView(self)
        self._controller: GrampletController | None = None
        self._read_repo: GrampsReadRepository | None = None
        self._write_repo: GrampsWriteRepository | None = None
        self._confidence_service: ConfidenceService | None = None
        self._chronology_service: ChronologyService | None = None
        self._patronymic_service: PatronymicInferenceService | None = None

        # 2. Run super constructor (which invokes init() and db_changed())
        super().__init__(gui, nav_group)

    def init(self) -> None:
        """
        Runs once when the Gramplet is registered.
        Sets up the static visual interface.
        """
        self._view.init()

        # Swap default textview with custom layout (runs once)
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.WIDGET = self._view.get_root_widget()
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def db_changed(self) -> None:
        """
        Overridden to recreate the database-dependent dependency graph
        whenever the database state changes (e.g., opened, switched, or closed).
        """
        if self.dbstate.is_open():
            # Recreate repositories tied to the new database session
            self._read_repo = GrampsReadRepository(self.dbstate.db)
            self._write_repo = GrampsWriteRepository(self.dbstate.db)

            # Recreate domain services
            self._confidence_service = ConfidenceService(self._read_repo)
            self._chronology_service = ChronologyService(self._read_repo)
            self._patronymic_service = PatronymicInferenceService(
                self._read_repo, self._confidence_service, self._chronology_service
            )

            # Recreate the controller and link it to the existing view
            self._controller = GrampletController(
                self._view,
                self._patronymic_service,
                self._read_repo,
                self._write_repo,
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

            # Start the non-blocking database scan
            self._start_background_median_calc()
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

    def _on_data_modified(self, *args, **kwargs) -> None:
        """
        Triggered by Gramps on Edit, Undo, or Redo.
        Accepts *args because Gramps passes lists of modified handles.
        """
        if self._controller and self._controller.current_handle:
            # We don't bother checking if the specific handle is in the args.
            # If the father's name changed, the father's handle is in the args,
            # but we still need to update the current person's patronymic.
            # Simply re-triggering the controller is the safest approach.
            self._controller.on_active_changed(self._controller.current_handle)

    def _start_background_median_calc(self) -> None:
        if not self._read_repo:
            return

        # 1. Get the generator from the repository
        median_generator = self._read_repo.get_database_median_year_chunked()

        # 2. Define what happens when it finishes
        def on_median_calculated(median_year: int | None) -> None:
            if median_year is not None and self._chronology_service:
                self._chronology_service.set_db_median_year(median_year)

                # Update UI if needed
                if self._controller and self._controller.current_handle:
                    self._controller.on_active_changed(self._controller.current_handle)

        # 3. Hand it to the generic runner
        run_in_idle_loop(median_generator, on_complete=on_median_calculated)
