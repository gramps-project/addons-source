"""Modèle des évènements généalogiques.

Ce module définit :
- ``EventSemantic`` : la sémantique d'évènement reconnue par le greffon ;
- ``Event`` : un évènement généalogique minimal et immuable.

Les types documentaires Gramps restent ouverts et sont conservés dans
``source_type``. Le greffon ne cherche à interpréter que les sémantiques
énumérées dans ``EventSemantic``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .gramps_date_document import GrampsDateDocument
from .temporal import TemporalValue


class EventSemantic(str, Enum):
    """Signification d'un évènement reconnue par le greffon.

    ``UNKNOWN`` ne signifie pas que l'évènement est inconnu ou invalide.
    Il signifie seulement que le greffon ne lui attribue actuellement
    aucune interprétation algorithmique particulière.
    """

    UNKNOWN = "UNKNOWN"
    BIRTH = "BIRTH"
    BAPTISM = "BAPTISM"
    MARRIAGE = "MARRIAGE"
    DIVORCE = "DIVORCE"
    CENSUS = "CENSUS"
    DEATH = "DEATH"
    BURIAL = "BURIAL"



@dataclass(frozen=True, slots=True)
class Event:
    """Représente un évènement généalogique extrait des données sources.

    Purpose
    -------
    Représente un évènement généalogique minimal utilisé par le modèle.

    Responsibilities
    ----------------
    - identifier l'évènement ;
    - conserver son type documentaire ;
    - exposer la sémantique reconnue par le greffon ;
    - conserver sa valeur temporelle ;
    - garantir ses invariants.

    Does NOT
    --------
    - connaître les personnes ou familles associées ;
    - conserver le rôle d'une personne dans l'évènement ;
    - accéder à Gramps ;
    - effectuer une inférence temporelle ;
    - convertir les calendriers ;
    - conserver ou interpréter un lieu ;
    - déterminer une position sur la timeline.
    """

    event_id: str
    source_type: str
    semantic: EventSemantic
    date: TemporalValue
    date_document: GrampsDateDocument | None = None

    def __post_init__(self) -> None:
        """Vérifie les invariants de l'évènement."""

        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("event_id must be a non-empty string")

        if not isinstance(self.source_type, str) or not self.source_type.strip():
            raise ValueError("source_type must be a non-empty string")

        if not isinstance(self.semantic, EventSemantic):
            raise TypeError("semantic must be an EventSemantic")

        if not isinstance(self.date, TemporalValue):
            raise TypeError("date must be a TemporalValue")
