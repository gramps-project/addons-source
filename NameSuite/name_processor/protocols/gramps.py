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

from typing import Protocol, Callable


class NameType(Protocol):
    """Protocol for Gramps NameType objects."""


class Surname(Protocol):
    """Protocol for Gramps Surname objects."""

    def get_origintype(self) -> int: ...

    def get_surname(self) -> str: ...

    def set_surname(self, value: str) -> None: ...

    def set_origintype(self, value: int) -> None: ...

    def set_primary(self, value: bool) -> None: ...


class PrimaryName(Protocol):
    """Protocol for Gramps Name objects used as primary names."""

    def get_surname_list(self) -> list[Surname]: ...

    def add_surname(self, surname: Surname) -> None: ...

    def get_first_name(self) -> str: ...

    def set_first_name(self, value: str) -> None: ...


class Name(Protocol):
    """Protocol for Gramps Name objects."""

    def get_first_name(self) -> str: ...

    def set_type(self, value: NameType) -> None: ...


class Person(Protocol):
    """Protocol for Gramps Person objects."""

    def get_primary_name(self) -> PrimaryName | None: ...

    def get_parent_family_handle_list(self) -> list[str]: ...

    def get_family_handle_list(self) -> list[str]: ...

    def get_event_ref_list(self) -> list[EventRef]: ...

    def add_alternate_name(self, name: Name) -> None: ...

    def get_alternate_names(self) -> list[Name]: ...


class Family(Protocol):
    """Protocol for Gramps Family objects."""

    def get_father_handle(self) -> str | None: ...

    def get_mother_handle(self) -> str | None: ...

    def get_child_ref_list(self) -> list[ChildRef]: ...


class Event(Protocol):
    """Protocol for Gramps Event objects."""

    def get_date_object(self) -> DateObject | None: ...


class DateObject(Protocol):
    """Protocol for Gramps date objects."""

    def is_empty(self) -> bool: ...

    def get_year(self) -> int | None: ...


class ChildRef(Protocol):
    """Protocol for Gramps child reference objects."""

    @property
    def ref(self) -> str | None: ...


class EventRef(Protocol):
    """Protocol for Gramps event reference objects."""

    @property
    def ref(self) -> str | None: ...


class GrampsDatabase(Protocol):
    """Protocol for Gramps database objects."""

    def get_number_of_people(self) -> int: ...

    def get_person_from_handle(self, handle: str) -> Person | None: ...

    def get_person_handles(self) -> list[str]: ...

    def get_event_handles(self) -> list[str]: ...

    def get_event_from_handle(self, handle: str) -> Event | None: ...

    def get_family_from_handle(self, handle: str) -> Family | None: ...

    def commit_person(self, person: Person, trans: object) -> None: ...

    def connect(self, signal: str, handler: Callable[..., None]) -> int: ...

    def disconnect(self, key: int) -> None: ...
