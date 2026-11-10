"""Résultat logique complet du moteur de layout."""

from __future__ import annotations

from dataclasses import dataclass

from descendants_timeline.layout.branch_reference_placement import (
    BranchReferencePlacement,
)
from descendants_timeline.layout.diagnostic_placement import DiagnosticPlacement
from descendants_timeline.layout.divorce_node_placement import (
    DivorceNodePlacement,
)
from descendants_timeline.layout.marriage_node_placement import (
    MarriageNodePlacement,
)
from descendants_timeline.layout.person_placement import PersonPlacement
from descendants_timeline.layout.remarriage_segment_placement import (
    RemarriageSegmentPlacement,
)


@dataclass(frozen=True, slots=True)
class TimelineLayout:
    """Ensemble des placements logiques produits pour une timeline."""

    person_placements: tuple[PersonPlacement, ...]
    marriage_node_placements: tuple[MarriageNodePlacement, ...]
    remarriage_segment_placements: tuple[RemarriageSegmentPlacement, ...]
    diagnostic_placements: tuple[DiagnosticPlacement, ...] = ()
    divorce_node_placements: tuple[DivorceNodePlacement, ...] = ()
    branch_reference_placements: tuple[BranchReferencePlacement, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.person_placements, tuple):
            raise TypeError(
                "person_placements must be a tuple"
            )

        if not all(
            isinstance(placement, PersonPlacement)
            for placement in self.person_placements
        ):
            raise TypeError(
                "person_placements must contain only PersonPlacement objects"
            )

        if not isinstance(self.marriage_node_placements, tuple):
            raise TypeError(
                "marriage_node_placements must be a tuple"
            )

        if not all(
            isinstance(placement, MarriageNodePlacement)
            for placement in self.marriage_node_placements
        ):
            raise TypeError(
                "marriage_node_placements must contain only "
                "MarriageNodePlacement objects"
            )

        if not isinstance(self.remarriage_segment_placements, tuple):
            raise TypeError(
                "remarriage_segment_placements must be a tuple"
            )

        if not all(
            isinstance(placement, RemarriageSegmentPlacement)
            for placement in self.remarriage_segment_placements
        ):
            raise TypeError(
                "remarriage_segment_placements must contain only "
                "RemarriageSegmentPlacement objects"
            )