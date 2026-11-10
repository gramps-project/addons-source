"""Modèle temporel central.

Ce module ne dépend ni de Gramps, ni du rendu, ni de l'interface graphique.
Les dates normalisées utilisent ``datetime.date`` dans le référentiel
proleptique grégorien commun retenu pour les calculs et la timeline.
La valeur documentaire d'origine reste conservée séparément.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class ValueOrigin(str, Enum):
    """Origine de la valeur temporelle elle-même."""

    GRAMPS = "GRAMPS"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(str, Enum):
    """Admissibilité de la valeur comme preuve directe."""

    EVIDENCE_USABLE = "EVIDENCE_USABLE"
    EVIDENCE_UNPROVEN = "EVIDENCE_UNPROVEN"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"


class CertaintyLevel(str, Enum):
    """Niveau qualitatif de certitude, et non probabilité statistique."""

    CERTAIN = "CERTAIN"
    VERY_PROBABLE = "VERY_PROBABLE"
    PROBABLE = "PROBABLE"
    POSSIBLE = "POSSIBLE"
    UNDETERMINED = "UNDETERMINED"

class SourceQuality(str, Enum):
    """Niveau qualitatif de la source (liste fermée GRAMPS)."""
    NORMAL = "NORMAL"
    CALCULATED = "CALCULATED"
    ESTIMATED = "ESTIMATED"


@dataclass(frozen=True, slots=True)
class TemporalValue:
    """Information temporelle documentée, inférée ou inconnue.

    ``source_value`` conserve la formulation documentaire issue de Gramps.
    ``normalized_minimum`` et ``normalized_maximum`` sont les bornes
    converties dans le référentiel grégorien commun.

    ``representative_value`` est temporellement justifiée. Elle ne doit pas
    être confondue avec une future ``display_value`` produite uniquement par
    le ``LayoutEngine``.

    Purpose
    -------
    Représente une valeur temporelle utilisée par le moteur d'inférence.

    Responsibilities
    ----------------
    - conserver la valeur documentaire ;
    - conserver la valeur normalisée ;
    - garantir les invariants.

    Does NOT
    --------
    - effectuer des inférences ;
    - calculer une display_value ;
    - dessiner quoi que ce soit.

    See also
    --------
    Specifications : E006,E007,C008,C009
    Architecture   : A005,§14.2
    Algorithms     : §24
    """

    source_value: str | None
    source_calendar: str | None
    normalized_minimum: date | None
    normalized_maximum: date | None
    representative_value: date | None
    value_origin: ValueOrigin
    source_quality: SourceQuality
    evidence_status: EvidenceStatus
    certainty: CertaintyLevel
    # Frontière désignée par une date documentaire stricte BEFORE/AFTER.
    # Les bornes normalisées excluent cette date ; elle n'est pas un représentant.
    documentary_boundary: date | None = None

    def __post_init__(self) -> None:
        minimum = self.normalized_minimum
        maximum = self.normalized_maximum
        representative = self.representative_value

        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(
                "normalized_minimum ne peut pas être postérieur "
                "à normalized_maximum."
            )

        if representative is not None:
            if minimum is not None and representative < minimum:
                raise ValueError(
                    "representative_value ne peut pas précéder "
                    "normalized_minimum."
                )
            if maximum is not None and representative > maximum:
                raise ValueError(
                    "representative_value ne peut pas suivre "
                    "normalized_maximum."
                )

        if self.value_origin is ValueOrigin.GRAMPS and self.source_value is None:
            raise ValueError(
                "Une valeur d'origine GRAMPS doit conserver source_value."
            )

        if self.value_origin is ValueOrigin.INFERRED and self.source_value is not None:
            raise ValueError(
                "Une valeur INFERRED ne doit pas prétendre provenir "
                "directement d'une source Gramps."
            )

        if (
            self.source_quality is SourceQuality.CALCULATED
            and self.evidence_status is EvidenceStatus.EVIDENCE_USABLE
            ):
                raise ValueError(
                    "Une date CALCULATED ne peut pas être utilisée comme preuve directe."
                )

        if self.value_origin is ValueOrigin.UNKNOWN:
            if any(
                value is not None
                for value in (
                    self.source_value,
                    self.source_calendar,
                    self.normalized_minimum,
                    self.normalized_maximum,
                    self.representative_value,
                    self.documentary_boundary,
                )
            ):
                raise ValueError(
                    "Une valeur UNKNOWN ne doit contenir aucune valeur temporelle."
                )
            if self.evidence_status is not EvidenceStatus.EVIDENCE_UNAVAILABLE:
                raise ValueError(
                    "Une valeur UNKNOWN doit avoir "
                    "evidence_status=EVIDENCE_UNAVAILABLE."
                )

        if self.evidence_status is EvidenceStatus.EVIDENCE_UNAVAILABLE:
            if any(
                value is not None
                for value in (
                    self.normalized_minimum,
                    self.normalized_maximum,
                    self.representative_value,
                    self.documentary_boundary,
                )
            ):
                raise ValueError(
                    "EVIDENCE_UNAVAILABLE est incompatible avec des bornes "
                    "ou une valeur représentative."
                )

        if self.evidence_status is EvidenceStatus.EVIDENCE_USABLE:
            if (
                self.normalized_minimum is None
                and self.normalized_maximum is None
                and self.representative_value is None
            ):
                raise ValueError(
                    "Une preuve utilisable doit fournir au moins une information "
                    "temporelle normalisée."
                )

    @property
    def has_closed_interval(self) -> bool:
        return (
            self.normalized_minimum is not None
            and self.normalized_maximum is not None
        )

    @property
    def is_exact(self) -> bool:
        return (
            self.has_closed_interval
            and self.normalized_minimum == self.normalized_maximum
        )

    @property
    def is_usable_as_evidence(self) -> bool:
        return self.evidence_status is EvidenceStatus.EVIDENCE_USABLE

    @classmethod
    def unknown(cls) -> "TemporalValue":
        return cls(
            source_value=None,
            source_calendar=None,
            normalized_minimum=None,
            normalized_maximum=None,
            representative_value=None,
            value_origin=ValueOrigin.UNKNOWN,
            source_quality=SourceQuality.NORMAL,
            evidence_status=EvidenceStatus.EVIDENCE_UNAVAILABLE,
            certainty=CertaintyLevel.UNDETERMINED,
        )
