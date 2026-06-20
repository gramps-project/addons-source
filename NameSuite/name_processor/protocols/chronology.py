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

from typing import Generator, Protocol


class ChronologySubject(Protocol):
    """The shape of the subject data required by ChronologyService."""

    @property
    def handle(self) -> str: ...


class ChronologyRepository(Protocol):
    """The repository interface required by ChronologyService."""

    def get_person(self, handle: str) -> ChronologySubject | None: ...

    def get_event_years(self, person_handle: str) -> list[int]: ...

    def iter_all_events_years(self) -> Generator[int, None, None]: ...

    def get_father_handle(self, person_handle: str) -> str | None: ...

    def get_mother_handle(self, person_handle: str) -> str | None: ...

    def get_children_handles(self, person_handle: str) -> list[str]: ...

    def get_siblings_handles(self, person_handle: str) -> list[str]: ...
