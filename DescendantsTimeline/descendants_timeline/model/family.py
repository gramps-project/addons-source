"""Modèle d'une famille généalogique."""

from __future__ import annotations

from dataclasses import dataclass

from .child_ref import ChildRef
from .family_event_ref import FamilyEventRef


@dataclass(frozen=True, slots=True)
class Family:
    """Représente une famille minimale, immuable et indépendante de Gramps."""

    family_id: str
    parent1_id: str | None
    parent2_id: str | None
    event_refs: tuple[FamilyEventRef, ...]
    child_refs: tuple[ChildRef, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")

        self._validate_optional_person_id(self.parent1_id, "parent1_id")
        self._validate_optional_person_id(self.parent2_id, "parent2_id")

        if not isinstance(self.event_refs, tuple):
            raise TypeError("event_refs must be a tuple")

        if not all(isinstance(ref, FamilyEventRef) for ref in self.event_refs):
            raise TypeError("event_refs must contain only FamilyEventRef objects")

        if not isinstance(self.child_refs, tuple):
            raise TypeError("child_refs must be a tuple")

        if not all(isinstance(ref, ChildRef) for ref in self.child_refs):
            raise TypeError("child_refs must contain only ChildRef objects")

    @staticmethod
    def _validate_optional_person_id(value: str | None, field_name: str) -> None:
        """Valide un identifiant de personne éventuellement absent.

        None représente l'absence légitime d'un parent.
        Une chaîne vide représente une référence invalide.
        """

        if value is None:
            return

        if not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string or None")

        if not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string or None")
