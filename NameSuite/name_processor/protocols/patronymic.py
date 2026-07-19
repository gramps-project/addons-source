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

from name_processor.models.person import Gender


class PatronymicSubject(Protocol):
    """The Service dictates the shape of the data it needs."""

    @property
    def handle(self) -> str: ...

    @property
    def gender(self) -> Gender: ...

    @property
    def has_patronymic(self) -> bool: ...

    @property
    def given_name(self) -> str | None: ...


class PatronymicRepository(Protocol):
    """The repository interface required by PatronymicInferenceService."""

    def get_person(self, handle: str) -> PatronymicSubject | None: ...

    def get_father_handle(self, person_handle: str) -> str | None: ...
