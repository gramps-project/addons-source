"""Placement logique d'un nœud de divorce dans la timeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DivorceNodePlacement:
    """Position logique d'un divorce dans la timeline."""

    family_id: str
    descendant_person_id: str
    spouse_person_id: str
    x: float
    y: float
    descendant_row_index: int
    spouse_row_index: int
