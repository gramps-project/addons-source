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

from typing import Protocol


class ChronologySubject(Protocol):
    """The shape of the subject data required by ChronologyService."""

    @property
    def handle(self) -> str: ...

    @property
    def event_years(self) -> list[int]:
        """A list of years extracted from the subject's birth, death, or marriage events."""
        ...

    @property
    def father_handle(self) -> str | None: ...

    @property
    def mother_handle(self) -> str | None: ...

    @property
    def children_handles(self) -> list[str]: ...

    @property
    def siblings_handles(self) -> list[str]: ...


class ChronologyRepository(Protocol):
    """The repository interface required by ChronologyService."""

    def get_chronology_subject(self, handle: str) -> ChronologySubject | None: ...
