"""Placement logique d'un nœud de mariage dans la timeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarriageNodePlacement:
    """Position logique d'un mariage dans la timeline."""

    family_id: str
    descendant_person_id: str
    spouse_person_id: str
    x: float
    y: float
    descendant_row_index: int
    spouse_row_index: int
    descendant_y: float | None = None
    spouse_y: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.family_id, str) or not self.family_id:
            raise ValueError(
                "family_id must be a non-empty string"
            )

        if (
            not isinstance(self.descendant_person_id, str)
            or not self.descendant_person_id
        ):
            raise ValueError(
                "descendant_person_id must be a non-empty string"
            )

        if (
            not isinstance(self.spouse_person_id, str)
            or not self.spouse_person_id
        ):
            raise ValueError(
                "spouse_person_id must be a non-empty string"
            )

        if not isinstance(self.x, (int, float)):
            raise TypeError(
                "x must be a number"
            )

        if not isinstance(self.y, (int, float)):
            raise TypeError(
                "y must be a number"
            )

        if (
            not isinstance(self.descendant_row_index, int)
            or self.descendant_row_index < 0
        ):
            raise ValueError(
                "descendant_row_index must be a non-negative integer"
            )

        if (
            not isinstance(self.spouse_row_index, int)
            or self.spouse_row_index < 0
        ):
            raise ValueError(
                "spouse_row_index must be a non-negative integer"
            )
