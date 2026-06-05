from gramps.gui.plug import tool
from name_processor.controllers.tool import ToolController
from name_processor.repositories.gramps_read import GrampsReadRepository
from name_processor.repositories.gramps_write import GrampsWriteRepository
from name_processor.views.tool import ToolWindow

# Domain Services
from name_processor.services.chronology import ChronologyService
from name_processor.services.confidence import ConfidenceService
from name_processor.services.patronymic import PatronymicInferenceService
from name_processor.services.renamer import RenamerService
from name_processor.services.alt_names import AltNamesService

# Ensure you have an AuditService stub or class created
from name_processor.services.audit import AuditService


class NamesTool(tool.Tool):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        super().__init__(dbstate, options_class, name)
        self.dbstate = dbstate
        self.user = user

        # 1. Repositories
        self._read_repo = GrampsReadRepository(dbstate.db)
        self._write_repo = GrampsWriteRepository(dbstate.db)

        # 2. Domain Services
        self._chronology_service = ChronologyService(self._read_repo)
        self._confidence_service = ConfidenceService(self._read_repo)

        self._patronymic_service = PatronymicInferenceService(
            self._read_repo, self._confidence_service, self._chronology_service
        )

        self._alt_names_service = AltNamesService()
        self._renamer_service = RenamerService()
        self._audit_service = AuditService(
            read_repo=self._read_repo,
            chronology_service=self._chronology_service,
            confidence_service=self._confidence_service,
        )

        # 3. Presentation Layer
        self._view = ToolWindow(None)
        self._controller = ToolController(
            tool_instance=self,  # <--- Pass the tool itself
            view=self._view,
            read_repo=self._read_repo,
            write_repo=self._write_repo,
            patronymic_service=self._patronymic_service,
            renamer_service=self._renamer_service,
            alt_names_service=self._alt_names_service,
            audit_service=self._audit_service,
            chronology_service=self._chronology_service,
        )

        self._view.set_controller(self._controller)

    def run(self):
        self._view.window.show_all()


class NamesToolOptions(tool.ToolOptions):
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
