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

from gramps.gen.display.name import displayer
from gramps.gen.lib import Person as GrampsPerson
from gramps.gen.lib.nameorigintype import NameOriginType

from name_processor.models.person import Gender


class GrampsPersonProxy:
    """
    A proxy for Gramps Person that implements various subject interfaces.
    """

    def __init__(self, gramps_person: GrampsPerson) -> None:
        self._person = gramps_person

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
