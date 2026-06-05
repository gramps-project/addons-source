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
