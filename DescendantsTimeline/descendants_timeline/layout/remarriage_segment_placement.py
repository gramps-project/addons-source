"""Placement logique d'un segment de remariage dans la timeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RemarriageSegmentPlacement:
    """Segment logique reliant des nœuds de remariage."""

    person_id: str
    x: float
    y_start: float
    y_end: float

    def __post_init__(self) -> None:
        if not isinstance(self.person_id, str) or not self.person_id:
            raise ValueError(
                "person_id must be a non-empty string"
            )

        if not isinstance(self.x, (int, float)):
            raise TypeError(
                "x must be a number"
            )

        if not isinstance(self.y_start, (int, float)):
            raise TypeError(
                "y_start must be a number"
            )

        if not isinstance(self.y_end, (int, float)):
            raise TypeError(
                "y_end must be a number"
            )

        if self.y_start > self.y_end:
            raise ValueError(
                "y_start must not be greater than y_end"
            )