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

from collections import deque
from typing import Generator

from name_processor.protocols.chronology import ChronologySubject, ChronologyRepository


class ChronologyService:
    """Service for estimating historical reference years using graph traversal."""

    # Chronology graph traversal BFS depth limit
    BFS_MAX_DEPTH = 4

    def __init__(self, read_repo: ChronologyRepository):
        self._read_repo: ChronologyRepository = read_repo
        # Lazy load the database median year only if a fallback is required
        self._db_median_year: int | None = None

    def set_db_median_year(self, median_year: int) -> None:
        self._db_median_year = median_year

    def generate_years(self, chunk_size: int = 100) -> Generator[None, None, list[int]]:
        """Creates a generator that collects event years from the repository.

        Yields periodically to allow UI updates during iteration.

        Args:
            chunk_size: Number of years to collect before yielding.

        Returns:
            A generator that yields None periodically and returns the list of years.
        """
        years = []
        for year in self._read_repo.iter_all_events_years():
            years.append(year)
            if len(years) % chunk_size == 0:
                yield None
        return years

    def update_median_year(self, years: list[int] | None = None) -> None:
        self._db_median_year = None

        if not years:
            return

        years = sorted(years)
        self._db_median_year = years[len(years) // 2]

    def estimate_reference_year(self, person_handle: str) -> int | None:
        """
        Calculates the historical reference year (Y_ref) for a person.
        Falls back through three tiers:
        1. Direct birth/marriage/death events.
        2. Generational BFS graph traversal (up to depth BFS_MAX_DEPTH).
        3. Database-wide median fallback.
        """
        person = self._read_repo.get_person(person_handle)
        if not person:
            return None

        # Tier 1: Direct Person Events
        person_year = self._get_person_event_year(person_handle)
        if person_year is not None:
            return person_year

        # Tier 2: BFS Generational Distance Estimation
        estimated_year = self._bfs_estimate_year(person_handle)
        if estimated_year is not None:
            return estimated_year

        # Tier 3: Database Fallback (Lazy loaded)
        return self._db_median_year

    def _get_person_event_year(self, person_handle: str) -> int | None:
        """Returns the latest event year from the person's events."""
        years = self._read_repo.get_event_years(person_handle)
        if years:
            return max(years)
        return None

    def _bfs_estimate_year(self, start_handle: str) -> int | None:
        """
        Performs BFS graph search up to depth BFS_MAX_DEPTH to estimate birth year based on relatives.
        g = generational offset relative to the target person:
          - Sibling / Spouse: g = 0
          - Parent: g = 1 (Relative Birth + 25)
          - Child: g = -1 (Relative Birth - 25)
        """
        visited: set[str] = {start_handle}
        # Cache fetched persons to avoid redundant DB calls
        person_cache: dict[str, ChronologySubject | None] = {}
        # Using deque for O(1) pops in BFS
        queue: deque[tuple[str, int, int]] = deque(
            [(start_handle, 0, 0)]
        )  # (handle, gen_offset, depth)
        candidates: list[int] = []

        while queue:
            handle, gen_offset, depth = queue.popleft()
            if depth > self.BFS_MAX_DEPTH:
                continue

            # Fetch person from cache or DB
            if handle not in person_cache:
                person_cache[handle] = self._read_repo.get_person(handle)
            person = person_cache[handle]
            if not person:
                continue

            # Evaluate relatives (excluding the starting person itself)
            if handle != start_handle:
                rel_year = self._get_person_event_year(handle)
                if rel_year is not None:
                    estimated_year = rel_year + (gen_offset * 25)
                    candidates.append(estimated_year)

            # Queue Parents (gen_offset + 1)
            father_handle = self._read_repo.get_father_handle(handle)
            if father_handle and father_handle not in visited:
                visited.add(father_handle)
                queue.append((father_handle, gen_offset + 1, depth + 1))

            mother_handle = self._read_repo.get_mother_handle(handle)
            if mother_handle and mother_handle not in visited:
                visited.add(mother_handle)
                queue.append((mother_handle, gen_offset + 1, depth + 1))

            # Queue Children (gen_offset - 1)
            for child_handle in self._read_repo.get_children_handles(handle):
                if child_handle not in visited:
                    visited.add(child_handle)
                    queue.append((child_handle, gen_offset - 1, depth + 1))

            # Queue Siblings (gen_offset)
            for sibling_handle in self._read_repo.get_siblings_handles(handle):
                if sibling_handle not in visited:
                    visited.add(sibling_handle)
                    queue.append((sibling_handle, gen_offset, depth + 1))

        if candidates:
            candidates.sort()
            return candidates[len(candidates) // 2]  # Median value
        return None
