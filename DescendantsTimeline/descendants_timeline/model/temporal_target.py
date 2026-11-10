"""Cible d'un calcul d'inférence temporelle."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TemporalOwnerType(str, Enum):
    """Type d'objet propriétaire d'une cible temporelle."""

    PERSON = "PERSON"
    FAMILY = "FAMILY"


class TargetSemantic(str, Enum):
    """Sémantiques temporelles pouvant être recherchées par le moteur."""

    BIRTH = "BIRTH"
    MARRIAGE = "MARRIAGE"
    DIVORCE = "DIVORCE"
    DEATH = "DEATH"


@dataclass(frozen=True, slots=True)
class TemporalTarget:
    """Identifie précisément la valeur temporelle recherchée.

    Une naissance et un décès appartiennent à une personne.
    Un mariage et un divorce appartiennent à une famille.
    """

    owner_type: TemporalOwnerType
    owner_id: str
    semantic: TargetSemantic

    def __post_init__(self) -> None:
        if not isinstance(self.owner_type, TemporalOwnerType):
            raise TypeError("owner_type must be a TemporalOwnerType")

        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be a non-empty string")

        if not isinstance(self.semantic, TargetSemantic):
            raise TypeError("semantic must be a TargetSemantic")

        if self.semantic in (TargetSemantic.BIRTH, TargetSemantic.DEATH):
            if self.owner_type is not TemporalOwnerType.PERSON:
                raise ValueError(
                    "BIRTH and DEATH targets must belong to a PERSON"
                )
        if self.semantic in (TargetSemantic.MARRIAGE, TargetSemantic.DIVORCE):
            if self.owner_type is not TemporalOwnerType.FAMILY:
                raise ValueError(
                    "MARRIAGE and DIVORCE targets must belong to a FAMILY"
                )
