"""Opérations calendaires utilisées par le moteur d'inférence."""

from __future__ import annotations

from datetime import date


def add_years(value: date, years: int) -> date:
    """
    Décale une date d'un nombre entier d'années.

    Si la date est un 29 février et que l'année résultante
    n'est pas bissextile, le résultat est fixé au 1er mars.
    """

    if not isinstance(value, date):
        raise TypeError("value must be a date")

    if not isinstance(years, int):
        raise TypeError("years must be an integer")

    target_year = value.year + years

    try:
        return value.replace(year=target_year)
    except ValueError:
        # Le seul cas attendu ici est le 29 février
        # déplacé vers une année non bissextile.
        if value.month == 2 and value.day == 29:
            return date(target_year, 3, 1)

        raise