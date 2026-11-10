"""Index inversé des références d'événements."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from descendants_timeline.model.temporal_evidence import EvidenceOwnerType
from descendants_timeline.model.person_event_ref import EventRoleSemantic
from descendants_timeline.model.family_event_ref import FamilyRoleSemantic
from descendants_timeline.model.genealogy import RawGenealogyData


@dataclass(frozen=True, slots=True)
class _EventReferenceEntry:
    """Référence interne vers un événement."""

    owner_type: EvidenceOwnerType
    owner_id: str
    role: EventRoleSemantic | FamilyRoleSemantic

    def __post_init__(self) -> None:
        if not isinstance(self.owner_type, EvidenceOwnerType):
            raise TypeError("owner_type must be an EvidenceOwnerType")

        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be a non-empty string")

        if self.owner_type is EvidenceOwnerType.PERSON:
            if not isinstance(self.role, EventRoleSemantic):
                raise TypeError(
                    "a PERSON event reference must use EventRoleSemantic"
                )

        if self.owner_type is EvidenceOwnerType.FAMILY:
            if not isinstance(self.role, FamilyRoleSemantic):
                raise TypeError(
                    "a FAMILY event reference must use FamilyRoleSemantic"
                )
@dataclass(frozen=True, slots=True)
class EventReferenceIndex:
    """Vue inversée des références d'événements."""

    _references: Mapping[str, tuple[_EventReferenceEntry, ...]]

    def __post_init__(self) -> None:
        """Protège l'index contre toute modification externe."""

        protected_references = MappingProxyType(
            {
                event_id: tuple(entries)
                for event_id, entries in self._references.items()
            }
        )

        object.__setattr__(
            self,
            "_references",
            protected_references,
        )

    def get(self, event_id: str) -> tuple[_EventReferenceEntry, ...]:
        """Retourne toutes les références associées à un événement."""

        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id must be a non-empty string")

        return self._references.get(event_id, ())

    @classmethod
    def from_data(cls, data: RawGenealogyData) -> "EventReferenceIndex":
        """Construit l'index à partir de RawGenealogyData."""

        if not isinstance(data, RawGenealogyData):
            raise TypeError("data must be a RawGenealogyData")

        temporary: dict[str, list[_EventReferenceEntry]] = {}

        for person in data.persons.values():
            for event_ref in person.event_refs:
                temporary.setdefault(event_ref.event_id, []).append(
                    _EventReferenceEntry(
                        owner_type=EvidenceOwnerType.PERSON,
                        owner_id=person.person_id,
                        role=event_ref.semantic_role,
                    )
                )

        for family in data.families.values():
            for event_ref in family.event_refs:
                temporary.setdefault(event_ref.event_id, []).append(
                    _EventReferenceEntry(
                        owner_type=EvidenceOwnerType.FAMILY,
                        owner_id=family.family_id,
                        role=event_ref.semantic_role,
                    )
                )

        references = {
            event_id: tuple(entries)
            for event_id, entries in temporary.items()
        }

        return cls(
            _references=references
        )