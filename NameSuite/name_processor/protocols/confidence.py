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

from typing import Protocol


class ConfidenceSubject(Protocol):
    """Protocol for subjects evaluated by the ConfidenceService."""

    @property
    def display_name(self) -> str: ...

    @property
    def surnames(self) -> list[str]: ...

    @property
    def given_name(self) -> str | None: ...

    @property
    def has_patronymic(self) -> bool: ...


class ConfidenceRepository(Protocol):
    """The repository interface required by ConfidenceService."""

    def get_person(self, handle: str) -> ConfidenceSubject | None: ...

    def get_siblings_handles(self, person_handle: str) -> list[str]: ...
