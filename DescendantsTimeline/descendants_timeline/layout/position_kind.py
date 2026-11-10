"""Nature d'une coordonnée logique dans la timeline."""

from __future__ import annotations

from enum import Enum


class PositionKind(str, Enum):
    """Nature de la position transmise au renderer."""

    REPRESENTATIVE = "REPRESENTATIVE"
    DOMAIN_DISPLAY = "DOMAIN_DISPLAY"
    VISUAL_FALLBACK = "VISUAL_FALLBACK"
