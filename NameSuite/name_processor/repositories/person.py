from gramps.gen.display.name import displayer
from gramps.gen.lib import Person as GrampsPerson
from gramps.gen.lib.nameorigintype import NameOriginType

from name_processor.models.person import Gender


class GrampsPersonProxy:
    """
    A lazy adapter that makes a Gramps Person look like both
    a PatronymicSubject and a ChronologySubject.
    Data is ONLY extracted if the Service actually asks for it.
    """

    def __init__(self, gramps_person: GrampsPerson, db: object) -> None:
        self._person = gramps_person
        self._db = db

    @property
    def handle(self) -> str:
        return self._person.get_handle()

    @property
    def gramps_id(self) -> str:
        return self._person.get_gramps_id()

    @property
    def gender(self) -> Gender:
        # Translate Gramps int to Domain Enum
        return (
            Gender.MALE
            if self._person.get_gender() == GrampsPerson.MALE
            else Gender.FEMALE
        )

    @property
    def has_patronymic(self) -> bool:
        # Gramps specific check - only primary name, check surname origin types
        primary_name = self._person.get_primary_name()
        return any(
            surname.get_origintype() == NameOriginType.PATRONYMIC
            for surname in primary_name.get_surname_list()
        )

    @property
    def patronymic(self) -> str | None:
        # Return the surname with PATRONYMIC origin type
        primary_name = self._person.get_primary_name()
        for surname in primary_name.get_surname_list():
            if surname.get_origintype() == NameOriginType.PATRONYMIC:
                return surname.get_surname()
        return None

    @property
    def father_handle(self) -> str | None:
        # Traverses parent families where the subject is a child
        families = self._person.get_parent_family_handle_list()
        if not families:
            return None
        family = self._db.get_family_from_handle(families[0])
        return family.get_father_handle() if family else None

    @property
    def mother_handle(self) -> str | None:
        # Traverses parent families where the subject is a child
        families = self._person.get_parent_family_handle_list()
        if not families:
            return None
        family = self._db.get_family_from_handle(families[0])
        return family.get_mother_handle() if family else None

    @property
    def children_handles(self) -> list[str]:
        # Traverses spouse/parent families to find children
        children = []
        for family_handle in self._person.get_family_handle_list():
            family = self._db.get_family_from_handle(family_handle)
            if family:
                for child_ref in family.get_child_ref_list():
                    if child_ref.ref:
                        children.append(child_ref.ref)
        return children

    @property
    def siblings_handles(self) -> list[str]:
        # Traverses parent families to find other children
        siblings = []
        for family_handle in self._person.get_parent_family_handle_list():
            family = self._db.get_family_from_handle(family_handle)
            if family:
                for child_ref in family.get_child_ref_list():
                    child_handle = child_ref.ref
                    if child_handle and child_handle != self.handle:
                        siblings.append(child_handle)
        return siblings

    @property
    def event_years(self) -> list[int]:
        # Moved date extraction logic from service to adapter layer
        years = []
        for ref in self._person.get_event_ref_list():
            event = self._db.get_event_from_handle(ref.ref)
            if event:
                date_obj = event.get_date_object()
                if date_obj and not date_obj.is_empty():
                    year = date_obj.get_year()
                    if year and year > 0:
                        years.append(year)
        return years

    @property
    def given_name(self) -> str | None:
        primary_name = self._person.get_primary_name()
        return primary_name.get_first_name() if primary_name else None

    @property
    def surnames(self) -> list[str]:
        primary_name = self._person.get_primary_name()
        if not primary_name:
            return []
        return [
            surname.get_surname()
            for surname in primary_name.get_surname_list()
            if surname.get_surname()
        ]

    @property
    def display_name(self) -> str:
        primary_name = self._person.get_primary_name()
        return displayer.display_name(primary_name) if primary_name else ""
