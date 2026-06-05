from typing import Protocol


class ConfidenceSubject(Protocol):
    """Protocol for subjects evaluated by the ConfidenceService."""

    @property
    def handle(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def siblings_handles(self) -> list[str]: ...

    @property
    def surnames(self) -> list[str]: ...

    @property
    def given_name(self) -> str | None: ...
