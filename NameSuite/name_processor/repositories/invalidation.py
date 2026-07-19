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

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from name_processor.protocols.gramps import GrampsDatabase
    from name_processor.repositories.entity_cache import EntityCache


class InvalidationSignalManager:
    """Bridges Gramps DB signals to EntityCache invalidation.

    Registers signal handlers on the Gramps database and translates
    signal callbacks into cache invalidation operations.

    This is the only component that knows about Gramps signal names.
    It must be explicitly disconnected before the database reference
    becomes invalid.
    """

    def __init__(self, db: GrampsDatabase, cache: EntityCache) -> None:
        self._db = db
        self._cache = cache
        self._signal_keys: list[int] = []
        self._connect_signals()

    def _connect_signals(self) -> None:
        """Registers handlers for all 12 relevant Gramps DB signals."""
        self._connect("person-add", self._on_person_changed)
        self._connect("person-update", self._on_person_changed)
        self._connect("person-delete", self._on_person_changed)
        self._connect("person-rebuild", self._on_person_rebuild)

        self._connect("family-add", self._on_family_changed)
        self._connect("family-update", self._on_family_changed)
        self._connect("family-delete", self._on_family_changed)
        self._connect("family-rebuild", self._on_family_rebuild)

        self._connect("event-add", self._on_event_changed)
        self._connect("event-update", self._on_event_changed)
        self._connect("event-delete", self._on_event_changed)
        self._connect("event-rebuild", self._on_event_rebuild)

    def _connect(self, signal: str, handler: Callable[..., None]) -> None:
        key = self._db.connect(signal, handler)
        self._signal_keys.append(key)

    def disconnect_all(self) -> None:
        """Unhooks all signal handlers. Must be called before db changes."""
        for key in self._signal_keys:
            self._db.disconnect(key)
        self._signal_keys.clear()

    # --- Person Signal Handlers ---
    def _on_person_changed(self, *args: Any, **kwargs: Any) -> None:
        """Invoked when person objects are added, updated, or deleted."""
        if args and isinstance(args[0], list):
            for handle in args[0]:
                if isinstance(handle, str):
                    self._cache.invalidate_person(handle)
        elif args and isinstance(args[0], str):
            self._cache.invalidate_person(args[0])

    def _on_person_rebuild(self, *args: Any, **kwargs: Any) -> None:
        """Invoked when the person database is rebuilt."""
        self._cache.clear_persons()

    # --- Family Signal Handlers ---
    def _on_family_changed(self, *args: Any, **kwargs: Any) -> None:
        """Invoked when family objects are added, updated, or deleted."""
        if args and isinstance(args[0], list):
            for handle in args[0]:
                if isinstance(handle, str):
                    self._cache.invalidate_family(handle)
        elif args and isinstance(args[0], str):
            self._cache.invalidate_family(args[0])

    def _on_family_rebuild(self, *args: Any, **kwargs: Any) -> None:
        """Invoked when the family database is rebuilt."""
        self._cache.clear_families()

    # --- Event Signal Handlers ---
    def _on_event_changed(self, *args: Any, **kwargs: Any) -> None:
        """Invoked when event objects are added, updated, or deleted."""
        if args and isinstance(args[0], list):
            for handle in args[0]:
                if isinstance(handle, str):
                    self._cache.invalidate_event(handle)
        elif args and isinstance(args[0], str):
            self._cache.invalidate_event(args[0])

    def _on_event_rebuild(self, *args: Any, **kwargs: Any) -> None:
        """Invoked when the event database is rebuilt."""
        self._cache.clear_events()
