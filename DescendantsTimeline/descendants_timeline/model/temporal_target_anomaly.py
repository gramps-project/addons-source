"""Anomalies structurelles associées aux cibles temporelles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TemporalTargetAnomalyType(str, Enum):
    """Type d'anomalie structurelle affectant une cible temporelle."""

    MULTIPLE_PRINCIPAL_EVENTS = "MULTIPLE_PRINCIPAL_EVENTS"
    FUTURE_EVENT = "FUTURE_EVENT"


@dataclass(frozen=True, slots=True)
class TemporalTargetAnomaly:
    """Anomalie structurelle affectant une cible temporelle.

    L'objet décrit uniquement l'anomalie et les événements Gramps
    qui en sont à l'origine. Il ne vérifie pas leur existence dans
    RawGenealogyData et ne produit aucun diagnostic destiné à l'interface.
    """

    anomaly_type: TemporalTargetAnomalyType
    event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.anomaly_type, TemporalTargetAnomalyType):
            raise TypeError(
                "anomaly_type doit être un TemporalTargetAnomalyType."
            )

        if not isinstance(self.event_ids, tuple):
            raise TypeError("event_ids doit être un tuple.")

        if not self.event_ids:
            raise ValueError("Une anomalie doit référencer au moins un événement.")

        if any(
            not isinstance(event_id, str) or not event_id.strip()
            for event_id in self.event_ids
        ):
            raise ValueError(
                "Chaque event_id doit être une chaîne non vide."
            )

        if len(set(self.event_ids)) != len(self.event_ids):
            raise ValueError(
                "event_ids ne doit pas contenir de doublons."
            )

        if (
            self.anomaly_type
            is TemporalTargetAnomalyType.MULTIPLE_PRINCIPAL_EVENTS
            and len(self.event_ids) < 2
        ):
            raise ValueError(
                "MULTIPLE_PRINCIPAL_EVENTS nécessite au moins deux événements."
            )
