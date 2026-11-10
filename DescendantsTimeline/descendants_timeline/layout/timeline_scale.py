"""Échelle temporelle logique de la timeline."""

from __future__ import annotations

from datetime import date


class TimelineScale:
    """Convertit entre dates normalisées et coordonnées temporelles logiques."""

    def date_to_x(self, value: date) -> float:
        return float(value.toordinal())

    def x_to_date(self, x: float) -> date:
        return date.fromordinal(int(x))