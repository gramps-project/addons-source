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

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from name_processor.protocols.gramps import Person, Family, Event


_MISSING: object = object()  # Sentinel for cache miss


class EntityCache:
    """Thread-unsafe, in-memory cache for individual Gramps entities.

    Stores entities keyed by their Gramps handle. Uses a sentinel value
    to distinguish 'never queried' from 'queried, returned None'.

    This class has no knowledge of Gramps internals, database signals,
    or repository logic. It is a pure data structure.

    NOTE: This cache is not thread-safe. It is designed for single-threaded
    use in the GTK main loop context. Do not use from background threads.
    """

    def __init__(self) -> None:
        self._persons: dict[str, Any] = {}
        self._families: dict[str, Any] = {}
        self._events: dict[str, Any] = {}

    # --- Person ---

    def get_person(self, handle: str) -> Any:
        """Returns cached person or _MISSING sentinel."""
        return self._persons.get(handle, _MISSING)

    def put_person(self, handle: str, person: Person) -> None:
        """Stores a person (or None for negative lookups)."""
        self._persons[handle] = person

    def invalidate_person(self, handle: str) -> None:
        """Removes a single person from cache. No-op if not cached."""
        self._persons.pop(handle, None)

    def clear_persons(self) -> None:
        """Removes all cached persons. Used on person-rebuild."""
        self._persons.clear()

    # --- Family ---

    def get_family(self, handle: str) -> Any:
        """Returns cached family or _MISSING sentinel."""
        return self._families.get(handle, _MISSING)

    def put_family(self, handle: str, family: Family) -> None:
        """Stores a family (or None for negative lookups)."""
        self._families[handle] = family

    def invalidate_family(self, handle: str) -> None:
        """Removes a single family from cache. No-op if not cached."""
        self._families.pop(handle, None)

    def clear_families(self) -> None:
        """Removes all cached families. Used on family-rebuild."""
        self._families.clear()

    # --- Event ---

    def get_event(self, handle: str) -> Any:
        """Returns cached event or _MISSING sentinel."""
        return self._events.get(handle, _MISSING)

    def put_event(self, handle: str, event: Event) -> None:
        """Stores an event (or None for negative lookups)."""
        self._events[handle] = event

    def invalidate_event(self, handle: str) -> None:
        """Removes a single event from cache. No-op if not cached."""
        self._events.pop(handle, None)

    def clear_events(self) -> None:
        """Removes all cached events. Used on event-rebuild."""
        self._events.clear()

    # --- Global Operations ---

    def clear_all(self) -> None:
        """Removes all cached entities. Used on database change."""
        self._persons.clear()
        self._families.clear()
        self._events.clear()

    # --- Diagnostic Properties ---

    @property
    def person_count(self) -> int:
        """Number of cached person entries (for diagnostics)."""
        return len(self._persons)

    @property
    def family_count(self) -> int:
        """Number of cached family entries (for diagnostics)."""
        return len(self._families)

    @property
    def event_count(self) -> int:
        """Number of cached event entries (for diagnostics)."""
        return len(self._events)
