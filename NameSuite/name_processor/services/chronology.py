from collections import deque
from NameSuite.name_processor.protocols.chronology import ChronologySubject, ChronologyRepository


class ChronologyService:
    def __init__(self, read_repo: ChronologyRepository):
        self._repo: ChronologyRepository = read_repo
        # Lazy load the database median year only if a fallback is required
        self._db_median_year: int | None = None

    def set_db_median_year(self, median_year: int) -> None:
        self._db_median_year = median_year

    def estimate_reference_year(self, person_handle: str) -> int | None:
        """
        Calculates the historical reference year (Y_ref) for a person.
        Falls back through three tiers:
        1. Direct birth/marriage/death events.
        2. Generational BFS graph traversal (up to depth 4).
        3. Database-wide median fallback.
        """
        person = self._repo.get_chronology_subject(person_handle)
        if not person:
            return None

        # Tier 1: Direct Person Events
        person_year = self._get_person_event_year(person)
        if person_year is not None:
            return person_year

        # Tier 2: BFS Generational Distance Estimation
        estimated_year = self._bfs_estimate_year(person_handle)
        if estimated_year is not None:
            return estimated_year

        # Tier 3: Database Fallback (Lazy loaded)
        return self._db_median_year

    def _get_person_event_year(self, person: ChronologySubject) -> int | None:
        """Returns the latest event year from the person's events."""
        years = person.event_years
        if years:
            return max(years)
        return None

    def _bfs_estimate_year(self, start_handle: str) -> int | None:
        """
        Performs BFS graph search up to depth 4 to estimate birth year based on relatives.
        g = generational offset relative to the target person:
          - Sibling / Spouse: g = 0
          - Parent: g = 1 (Relative Birth + 25)
          - Child: g = -1 (Relative Birth - 25)
        """
        visited: set[str] = {start_handle}
        # Cache fetched subjects to avoid redundant DB calls
        subject_cache: dict[str, ChronologySubject | None] = {}
        # Using deque for O(1) pops in BFS
        queue: deque[tuple[str, int, int]] = deque(
            [(start_handle, 0, 0)]
        )  # (handle, gen_offset, depth)
        candidates: list[int] = []

        while queue:
            handle, gen_offset, depth = queue.popleft()
            if depth > 4:
                continue

            # Fetch subject from cache or DB
            if handle not in subject_cache:
                subject_cache[handle] = self._repo.get_chronology_subject(handle)
            subject = subject_cache[handle]
            if not subject:
                continue

            # Evaluate relatives (excluding the starting subject itself)
            if handle != start_handle:
                rel_year = self._get_person_event_year(subject)
                if rel_year is not None:
                    estimated_year = rel_year + (gen_offset * 25)
                    candidates.append(estimated_year)

            # Queue Parents (gen_offset + 1)
            father_handle = subject.father_handle
            if father_handle and father_handle not in visited:
                visited.add(father_handle)
                queue.append((father_handle, gen_offset + 1, depth + 1))

            mother_handle = subject.mother_handle
            if mother_handle and mother_handle not in visited:
                visited.add(mother_handle)
                queue.append((mother_handle, gen_offset + 1, depth + 1))

            # Queue Children (gen_offset - 1)
            for child_handle in subject.children_handles:
                if child_handle not in visited:
                    visited.add(child_handle)
                    queue.append((child_handle, gen_offset - 1, depth + 1))

            # Queue Siblings (gen_offset)
            for sibling_handle in subject.siblings_handles:
                if sibling_handle not in visited:
                    visited.add(sibling_handle)
                    queue.append((sibling_handle, gen_offset, depth + 1))

        if candidates:
            candidates.sort()
            return candidates[len(candidates) // 2]  # Median value
        return None
