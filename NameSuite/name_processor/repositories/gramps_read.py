from collections.abc import Generator
import itertools

from name_processor.repositories.person import GrampsPersonProxy
from name_processor.protocols.chronology import ChronologySubject


class GrampsReadRepository:
    def __init__(self, db: object) -> None:
        self._db = db

    # ==========================================
    # System Operations
    # ==========================================
    def get_person_count(self) -> int:
        """Returns the total number of individuals to power UI progress bars."""
        return self._db.get_number_of_people()

    def get_raw_person(self, handle: str) -> object:
        """
        Returns the raw, mutable Gramps Person object.
        Used only for write operations and native Gramps Editor dialogs.
        """
        return self._db.get_person_from_handle(handle)

    # ==========================================
    # Proxy Access & Iterators
    # ==========================================
    def get_person_proxy(self, handle: str) -> GrampsPersonProxy | None:
        gramps_person = self._db.get_person_from_handle(handle)
        if not gramps_person:
            return None
        return GrampsPersonProxy(gramps_person, self._db)

    def get_chronology_subject(self, handle: str) -> ChronologySubject | None:
        return self.get_person_proxy(handle)

    def get_person_proxies_chunked(
        self, chunk_size: int = 250
    ) -> Generator[list[GrampsPersonProxy], None, None]:
        """
        Yields batches of person proxies to hide handle iteration
        and support GTK idle loop chunking.
        """
        handles = self._db.get_person_handles()
        for i in range(0, len(handles), chunk_size):
            chunk = []
            for handle in handles[i : i + chunk_size]:
                proxy = self.get_person_proxy(handle)
                if proxy:
                    chunk.append(proxy)
            yield chunk

    def iter_all_person_proxies(self) -> Generator[GrampsPersonProxy, None, None]:
        """Yields person proxies one by one for direct iteration."""
        for handle in self._db.get_person_handles():
            proxy = self.get_person_proxy(handle)
            if proxy:
                yield proxy

    # ==========================================
    # Aggregations
    # ==========================================
    def get_database_median_year_chunked(
        self, chunk_size: int = 500
    ) -> Generator[None, None, int | None]:
        """Calculates the median year asynchronously."""
        years = []
        handles = self._db.get_event_handles()
        handle_iter = iter(handles)

        while True:
            chunk = list(itertools.islice(handle_iter, chunk_size))
            if not chunk:
                break

            for handle in chunk:
                event = self._db.get_event_from_handle(handle)
                if event:
                    date_obj = event.get_date_object()
                    if date_obj and not date_obj.is_empty():
                        year = date_obj.get_year()
                        if year and year > 0:
                            years.append(year)
            yield None

        if years:
            years.sort()
            return years[len(years) // 2]
        return None
