"""Nature d'une barre de vie dans la timeline."""

from __future__ import annotations

from enum import Enum


class LifeBarKind(str, Enum):
    """Nature de la barre de vie transmise au renderer."""

    NORMAL = "NORMAL"
    REVERSED = "REVERSED"
    ZERO_LENGTH = "ZERO_LENGTH"
    NO_GUARANTEED_INTERVAL = "NO_GUARANTEED_INTERVAL"
