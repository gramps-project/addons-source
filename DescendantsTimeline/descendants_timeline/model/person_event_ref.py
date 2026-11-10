"""Référence d'un évènement depuis une personne."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventRoleSemantic(str, Enum):
    """Signification d'un rôle de personne reconnue par le greffon.

    UNKNOWN ne signifie pas que le rôle est invalide. Il signifie seulement
    que le greffon ne lui attribue actuellement aucune interprétation
    algorithmique particulière.
    """

    UNKNOWN = "UNKNOWN"
    PRINCIPAL = "PRINCIPAL"
    WITNESS = "WITNESS"
    INFORMANT = "INFORMANT"


@dataclass(frozen=True, slots=True)
class PersonEventRef:
    """Décrit la participation d'une personne à un évènement.

    Responsibilities
    ----------------
    - référencer un évènement existant ;
    - conserver le rôle documentaire provenant de Gramps ;
    - exposer la sémantique de rôle reconnue par le greffon ;
    - garantir ses invariants.

    Does NOT
    --------
    - contenir l'évènement lui-même ;
    - accéder à Gramps ;
    - effectuer une inférence temporelle ;
    - modifier l'évènement référencé.
    """

    event_id: str
    semantic_role: EventRoleSemantic
    source_role: str

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")

        if not isinstance(self.semantic_role, EventRoleSemantic):
            raise TypeError("semantic_role must be an EventRoleSemantic")

        if not isinstance(self.source_role, str) or not self.source_role.strip():
            raise ValueError("source_role must be a non-empty string")
