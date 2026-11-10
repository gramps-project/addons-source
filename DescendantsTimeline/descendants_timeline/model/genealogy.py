"""Conteneur du modèle généalogique normalisé."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from descendants_timeline.gramps_date_normalization import DateNormalizationDiagnostic

from .event import Event
from .family import Family
from .person import Person


@dataclass(frozen=True, slots=True)
class RawGenealogyData:
    """Photographie immuable du sous-ensemble généalogique utile."""

    persons: Mapping[str, Person]
    families: Mapping[str, Family]
    events: Mapping[str, Event]
    root_person_id: str
    date_normalization_diagnostics: tuple[DateNormalizationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        persons = self._copy_persons(self.persons)
        families = self._copy_families(self.families)
        events = self._copy_events(self.events)

        if not isinstance(self.root_person_id, str) or not self.root_person_id.strip():
            raise ValueError("root_person_id must be a non-empty string")

        if self.root_person_id not in persons:
            raise ValueError("root_person_id must reference a person present in persons")

        self._validate_person_references(persons, families, events)
        self._validate_family_references(persons, families, events)

        object.__setattr__(self, "persons", MappingProxyType(persons))
        object.__setattr__(self, "families", MappingProxyType(families))
        object.__setattr__(self, "events", MappingProxyType(events))
        object.__setattr__(
            self, "date_normalization_diagnostics", tuple(self.date_normalization_diagnostics),
        )

    @staticmethod
    def _copy_persons(values: Mapping[str, Person]) -> dict[str, Person]:
        if not isinstance(values, Mapping):
            raise TypeError("persons must be a mapping")
        copied = dict(values)
        for key, person in copied.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("persons keys must be non-empty strings")
            if not isinstance(person, Person):
                raise TypeError("persons must contain only Person objects")
            if key != person.person_id:
                raise ValueError("persons key must match Person.person_id")
        return copied

    @staticmethod
    def _copy_families(values: Mapping[str, Family]) -> dict[str, Family]:
        if not isinstance(values, Mapping):
            raise TypeError("families must be a mapping")
        copied = dict(values)
        for key, family in copied.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("families keys must be non-empty strings")
            if not isinstance(family, Family):
                raise TypeError("families must contain only Family objects")
            if key != family.family_id:
                raise ValueError("families key must match Family.family_id")
        return copied

    @staticmethod
    def _copy_events(values: Mapping[str, Event]) -> dict[str, Event]:
        if not isinstance(values, Mapping):
            raise TypeError("events must be a mapping")
        copied = dict(values)
        for key, event in copied.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("events keys must be non-empty strings")
            if not isinstance(event, Event):
                raise TypeError("events must contain only Event objects")
            if key != event.event_id:
                raise ValueError("events key must match Event.event_id")
        return copied

    @staticmethod
    def _validate_person_references(
        persons: Mapping[str, Person],
        families: Mapping[str, Family],
        events: Mapping[str, Event],
    ) -> None:
        for person in persons.values():
            for ref in person.event_refs:
                if ref.event_id not in events:
                    raise ValueError(
                        f"Person {person.person_id} references missing event {ref.event_id}"
                    )
            for family_id in person.parent_family_ids:
                if family_id not in families:
                    raise ValueError(
                        f"Person {person.person_id} references missing parent family {family_id}"
                    )
            for family_id in person.family_ids:
                if family_id not in families:
                    raise ValueError(
                        f"Person {person.person_id} references missing family {family_id}"
                    )

    @staticmethod
    def _validate_family_references(
        persons: Mapping[str, Person],
        families: Mapping[str, Family],
        events: Mapping[str, Event],
    ) -> None:
        for family in families.values():
            if family.parent1_id is not None and family.parent1_id not in persons:
                raise ValueError(
                    f"Family {family.family_id} references missing parent1 {family.parent1_id}"
                )
            if family.parent2_id is not None and family.parent2_id not in persons:
                raise ValueError(
                    f"Family {family.family_id} references missing parent2 {family.parent2_id}"
                )
            for ref in family.event_refs:
                if ref.event_id not in events:
                    raise ValueError(
                        f"Family {family.family_id} references missing event {ref.event_id}"
                    )
            for child_ref in family.child_refs:
                if child_ref.person_id not in persons:
                    raise ValueError(
                        f"Family {family.family_id} references missing child {child_ref.person_id}"
                    )
