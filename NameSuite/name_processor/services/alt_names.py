from typing import TYPE_CHECKING
from gramps.gen.lib import Name, NameType

if TYPE_CHECKING:
    from gramps.gen.lib import Person


class AltNamesService:
    def preserve_primary_name(self, gramps_person: "Person") -> None:
        """
        Creates a deep copy of the person's current primary name and appends it
        to their Alternative Names list. Retains all attached citations and dates.
        """
        primary_name = gramps_person.get_primary_name()
        if not primary_name:
            return

        # Gramps domain objects support deep copy via the 'source' kwarg
        preserved_name = Name(source=primary_name)

        # Reclassify the preserved name to distinguish it from the new primary
        preserved_name.set_type(NameType(NameType.AKA))

        gramps_person.add_alternate_name(preserved_name)

    def is_protected_by_alias(self, gramps_person: "Person", search_str: str) -> bool:
        """
        Checks if a specific string exists within the alternative names.
        Used to skip renaming if the string is a known historical alias or maiden name.
        """
        for alt_name in gramps_person.get_alternate_names():
            if search_str in alt_name.get_first_name():
                return True
        return False
