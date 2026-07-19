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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from name_processor.protocols.gramps import Person
    from name_processor.protocols.repository import ReadRepository


class AltNamesService:
    """Thin wrapper for alternate name operations delegated to read repository."""

    def __init__(self, read_repo: ReadRepository | None = None) -> None:
        """
        Initialize with optional read repository for delegation.
        If not provided, methods will need to be called with repository explicitly.
        """
        self._read_repo = read_repo

    def is_protected_by_alias(self, gramps_person: Person, search_str: str) -> bool:
        """
        Delegates to ReadRepository.is_protected_by_alias.
        Checks if a specific string exists within the alternative names.
        Used to skip renaming if the string is a known historical alias or maiden name.
        """
        if self._read_repo:
            return self._read_repo.is_protected_by_alias(gramps_person, search_str)
        else:
            raise RuntimeError(
                "AltNamesService not initialized with read_repo. "
                "Use ReadRepository.is_protected_by_alias directly."
            )
