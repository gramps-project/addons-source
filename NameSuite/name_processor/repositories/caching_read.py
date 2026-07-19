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

from name_processor.protocols.gramps import Person, Family, Event
from name_processor.repositories.gramps_read import GrampsReadRepository
from name_processor.repositories.entity_cache import EntityCache, _MISSING

if TYPE_CHECKING:
    from name_processor.protocols.gramps import GrampsDatabase


class CachingReadRepository(GrampsReadRepository):
    """Subclass of GrampsReadRepository that adds transparent caching.

    Overrides the private entity retrieval methods to check a cache before
    fetching from the database. All public and relationship traversal methods
    automatically benefit from this caching layer.
    """

    def __init__(self, db: GrampsDatabase, cache: EntityCache) -> None:
        super().__init__(db)
        self._cache = cache

    def _get_person_from_handle(self, handle: str) -> Person | None:
        cached = self._cache.get_person(handle)
        if cached is not _MISSING:
            return cached
        person = super()._get_person_from_handle(handle)
        if person is not None:
            self._cache.put_person(handle, person)
        return person

    def _get_family_from_handle(self, handle: str) -> Family | None:
        cached = self._cache.get_family(handle)
        if cached is not _MISSING:
            return cached
        family = super()._get_family_from_handle(handle)
        if family is not None:
            self._cache.put_family(handle, family)
        return family

    def _get_event_from_handle(self, handle: str) -> Event | None:
        cached = self._cache.get_event(handle)
        if cached is not _MISSING:
            return cached
        event = super()._get_event_from_handle(handle)
        if event is not None:
            self._cache.put_event(handle, event)
        return event
