"""Placement logique d'un renvoi de branche dans la timeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BranchReferencePlacement:
    """Position logique d'un renvoi de branche dans la timeline."""

    family_id: str
    descendant_row_index: int
    spouse_row_index: int
    referenced_row_index: int
    visual_rank: int
    y: float
    x: float | None = None
