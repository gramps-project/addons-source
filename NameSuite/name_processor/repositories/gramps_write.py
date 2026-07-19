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

from collections.abc import Generator
import contextlib

from gramps.gen.db import DbTxn
from gramps.gen.lib import Name, NameOriginType, NameType, Surname

from name_processor.protocols.gramps import (
    GrampsDatabase,
    Person,
    PrimaryName,
)


# NOTE: In a future refactor, is_patronymic_origin and update_or_add_patronymic
# should be moved to a Domain Service (e.g., name_processor.services.mutator)
def is_patronymic_origin(orig: NameOriginType) -> bool:
    try:
        return bool(int(orig) == NameOriginType.PATRONYMIC)
    except (ValueError, TypeError):
        return False


def update_or_add_patronymic(
    primary_name: PrimaryName, new_patronymic_value: str
) -> str:
    surnames = primary_name.get_surname_list()
    orig_pat = ""
    found = False

    for s in surnames:
        if is_patronymic_origin(s.get_origintype()):
            orig_pat = s.get_surname()
            s.set_surname(new_patronymic_value)
            found = True
            break

    if not found:
        surn_obj = Surname()
        surn_obj.set_surname(new_patronymic_value)
        surn_obj.set_origintype(NameOriginType.PATRONYMIC)
        surn_obj.set_primary(False)
        primary_name.add_surname(surn_obj)

    return orig_pat


class GrampsWriteRepository:
    def __init__(self, db: GrampsDatabase) -> None:
        self._db = db

    # ==========================================
    # New MVCS Pure Persistence Methods
    # ==========================================
    @contextlib.contextmanager
    def transaction(self, description: str) -> Generator[DbTxn, None, None]:
        """
        Exposes the Gramps DbTxn context manager to higher layers.
        Ensures a batch of modifications is treated as a single Undo step.
        """
        with DbTxn(description, self._db) as trans:
            yield trans

    def commit_person(self, trans: DbTxn, person: Person) -> None:
        """
        Commits a fully prepared/mutated Person object to the database.
        """
        self._db.commit_person(person, trans)

    def preserve_primary_name(self, person: Person) -> None:
        """
        Creates a deep copy of the person's current primary name and appends it
        to their Alternative Names list. Retains all attached citations and dates.
        This is a mutation operation that prepares a Person object for write operations.
        """
        primary_name = person.get_primary_name()
        if not primary_name:
            return

        # Gramps domain objects support deep copy via the 'source' kwarg
        preserved_name = Name(source=primary_name)

        # Reclassify the preserved name to distinguish it from the new primary
        preserved_name.set_type(NameType(NameType.AKA))

        person.add_alternate_name(preserved_name)

    # --- ATOMIC COMMANDS ---
    def apply_first_name_correction(
        self, trans: DbTxn, handle: str, new_first_name: str, preserve_alt: bool = False
    ) -> None:
        """
        Renaming command for updating primary given names.

        Fetches the person internally, validates existence, and applies mutation.
        Optionally preserves the primary name as an alternate name before updating.
        """
        person = self._db.get_person_from_handle(handle)
        if not person:
            raise ValueError(f"Person with handle {handle} not found")

        if preserve_alt:
            self.preserve_primary_name(person)

        primary_name = person.get_primary_name()
        if primary_name:
            primary_name.set_first_name(new_first_name)
        self.commit_person(trans, person)

    def apply_patronymic_correction(
        self, trans: DbTxn, handle: str, new_patronymic: str
    ) -> None:
        """
        Fetches the person internally, validates existence, and applies mutation.
        """
        person = self._db.get_person_from_handle(handle)
        if not person:
            raise ValueError(f"Person with handle {handle} not found")

        primary_name = person.get_primary_name()
        if primary_name:
            update_or_add_patronymic(primary_name, new_patronymic)
            self.commit_person(trans, person)

    # ==========================================
    # Convenience Method (Used by Gramplet)
    # ==========================================
    def update_patronymic_names(self, patronymics: dict[str, str]) -> None:
        with self.transaction("Update Patronymic Names") as t:
            for handle, patronymic in patronymics.items():
                self.apply_patronymic_correction(t, handle, patronymic)
