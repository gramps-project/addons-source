"""Placement logique d'une personne dans la timeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from descendants_timeline.layout.life_bar_kind import LifeBarKind
from descendants_timeline.layout.position_kind import PositionKind
from descendants_timeline.layout.temporal_display_value import TemporalPositionQualification
from descendants_timeline.temporal_bound_qualification import TemporalDomainQualification
from descendants_timeline.traversal.descendance_traversal import (
    TraversalRole,
)


@dataclass(frozen=True, slots=True)
class PersonPlacement:
    """Position logique d'une occurrence de personne dans la timeline.

    x_start/x_end retain independent birth/death references, never a missing
    event's replacement. visual_x locates the occurrence without asserting a
    lifespan. A NO_GUARANTEED_INTERVAL exposes that single point through the
    legacy bar properties; its temporal domains remain available separately.
    """

    person_id: str
    row_index: int
    generation: int
    role: TraversalRole
    family_id: str | None
    spouse_of_person_id: str | None
    x_start: float | None
    x_end: float | None
    y: float
    visual_rank: int | None = None
    x_start_kind: PositionKind = PositionKind.REPRESENTATIVE
    x_end_kind: PositionKind = PositionKind.REPRESENTATIVE
    life_bar_kind: LifeBarKind = LifeBarKind.NORMAL
    # Retained for old callers; never used to manufacture a temporal endpoint.
    short_bar_length: float | None = None
    birth_position_qualification: TemporalPositionQualification | None = field(default=None, compare=False)
    birth_qualification: TemporalDomainQualification | None = field(default=None, compare=False)
    death_qualification: TemporalDomainQualification | None = field(default=None, compare=False)
    visual_x: float | None = None
    visual_position_kind: PositionKind = PositionKind.VISUAL_FALLBACK

    @property
    def bar_x_start(self) -> float | None:
        if self.life_bar_kind is LifeBarKind.NO_GUARANTEED_INTERVAL:
            return self.visual_x
        return self.x_start

    @property
    def bar_x_end(self) -> float | None:
        if self.life_bar_kind is LifeBarKind.NO_GUARANTEED_INTERVAL:
            return self.visual_x
        return self.x_end

    def __post_init__(self) -> None:
        if self.visual_rank is None:
            object.__setattr__(self, "visual_rank", self.row_index)

        if not isinstance(self.person_id, str) or not self.person_id:
            raise ValueError(
                "person_id must be a non-empty string"
            )

        if not isinstance(self.row_index, int) or self.row_index < 0:
            raise ValueError(
                "row_index must be a non-negative integer"
            )

        if not isinstance(self.generation, int) or self.generation < 1:
            raise ValueError(
                "generation must be a positive integer"
            )

        if not isinstance(self.role, TraversalRole):
            raise TypeError(
                "role must be a TraversalRole"
            )

        if self.family_id is not None and (
            not isinstance(self.family_id, str) or not self.family_id
        ):
            raise ValueError(
                "family_id must be None or a non-empty string"
            )

        if self.spouse_of_person_id is not None and (
            not isinstance(self.spouse_of_person_id, str)
            or not self.spouse_of_person_id
        ):
            raise ValueError(
                "spouse_of_person_id must be None or a non-empty string"
            )

        if self.x_start is not None and not isinstance(
            self.x_start, (int, float)
        ):
            raise TypeError(
                "x_start must be None or a number"
            )

        if not isinstance(self.x_start_kind, PositionKind):
            raise TypeError(
                "x_start_kind must be a PositionKind"
            )

        if self.x_end is not None and not isinstance(
            self.x_end, (int, float)
        ):
            raise TypeError(
                "x_end must be None or a number"
            )

        if not isinstance(self.x_end_kind, PositionKind):
            raise TypeError(
                "x_end_kind must be a PositionKind"
            )

        if not isinstance(self.y, (int, float)):
            raise TypeError(
                "y must be a number"
            )
        if not isinstance(self.life_bar_kind, LifeBarKind):
            raise TypeError(
                "life_bar_kind must be a LifeBarKind"
            )
