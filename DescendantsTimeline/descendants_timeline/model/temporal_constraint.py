"""Contrainte temporelle produite par une règle d'inférence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from .temporal_evidence import TemporalEvidence
from .temporal_target import TemporalTarget


class ConstraintOperator(str, Enum):
    """Sens d'une borne temporelle absolue."""

    BEFORE_OR_EQUAL = "BEFORE_OR_EQUAL"
    AFTER_OR_EQUAL = "AFTER_OR_EQUAL"


class ConstraintStrength(str, Enum):
    """Force logique de la règle ayant produit la contrainte."""

    HARD = "HARD"
    SOFT = "SOFT"


@dataclass(frozen=True, slots=True)
class TemporalConstraint:
    """Borne temporelle concrète produite par une Rule.

    Une TemporalConstraint ne représente jamais directement une borne
    saisie dans Gramps. Les bornes Gramps restent portées par TemporalValue.
    """

    target: TemporalTarget
    operator: ConstraintOperator
    bound: date
    rule_id: str
    strength: ConstraintStrength
    evidences: tuple[TemporalEvidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target, TemporalTarget):
            raise TypeError("target must be a TemporalTarget")

        if not isinstance(self.operator, ConstraintOperator):
            raise TypeError("operator must be a ConstraintOperator")

        if not isinstance(self.bound, date):
            raise TypeError("bound must be a date")

        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("rule_id must be a non-empty string")

        if not isinstance(self.strength, ConstraintStrength):
            raise TypeError("strength must be a ConstraintStrength")

        if not isinstance(self.evidences, tuple):
            raise TypeError("evidences must be a tuple")

        if not self.evidences:
            raise ValueError(
                "TemporalConstraint must contain at least one evidence"
            )

        if not all(
            isinstance(evidence, TemporalEvidence)
            for evidence in self.evidences
        ):
            raise TypeError(
                "evidences must contain only TemporalEvidence objects"
            )