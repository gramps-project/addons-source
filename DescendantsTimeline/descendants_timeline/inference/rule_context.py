from collections.abc import Mapping
from dataclasses import dataclass, field
from heapq import merge
from types import MappingProxyType

from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.family_event_ref import FamilyRoleSemantic
from descendants_timeline.model.person_event_ref import EventRoleSemantic
from descendants_timeline.model.temporal_evidence import EvidenceOwnerType, TemporalEvidence
from descendants_timeline.model.temporal_target import TemporalOwnerType


def _build_marriage_evidences_by_parent(data, evidences):
    """Index existing marriage evidence in its original order, once per context."""
    by_parent = {}
    for evidence in evidences:
        if not (
            evidence.semantic is EventSemantic.MARRIAGE
            and evidence.owner_type is EvidenceOwnerType.FAMILY
            and evidence.role is FamilyRoleSemantic.FAMILY
            and evidence.principal_owner_type is TemporalOwnerType.FAMILY
            and evidence.principal_owner_id == evidence.owner_id
        ):
            continue
        family = data.families.get(evidence.owner_id)
        if family is None:
            continue
        if family.parent1_id is not None:
            by_parent.setdefault(family.parent1_id, []).append(evidence)
        if family.parent2_id is not None and family.parent2_id != family.parent1_id:
            by_parent.setdefault(family.parent2_id, []).append(evidence)
    return MappingProxyType({parent: tuple(values) for parent, values in by_parent.items()})


def _build_personal_principal_evidences(evidences):
    """Keep every qualifying birth/death/burial/census/baptism occurrence without deduplication."""
    by_person_and_semantic = {}
    for evidence in evidences:
        if (
            evidence.semantic in (EventSemantic.BIRTH, EventSemantic.DEATH, EventSemantic.BURIAL, EventSemantic.CENSUS, EventSemantic.BAPTISM)
            and evidence.owner_type is EvidenceOwnerType.PERSON
            and evidence.role is EventRoleSemantic.PRINCIPAL
            and evidence.principal_owner_type is TemporalOwnerType.PERSON
            and evidence.principal_owner_id == evidence.owner_id
        ):
            key = (evidence.owner_id, evidence.semantic)
            by_person_and_semantic.setdefault(key, []).append(evidence)
    return MappingProxyType({key: tuple(values) for key, values in by_person_and_semantic.items()})


def _build_divorce_evidences_by_parent(data, evidences):
    """Keep parent and family divorce occurrences in one pass, without deduplication."""
    by_parent = {}
    by_family = {}
    for evidence in evidences:
        if not (
            evidence.semantic is EventSemantic.DIVORCE
            and evidence.owner_type is EvidenceOwnerType.FAMILY
            and evidence.role is FamilyRoleSemantic.FAMILY
            and evidence.principal_owner_type is TemporalOwnerType.FAMILY
            and evidence.principal_owner_id == evidence.owner_id
        ):
            continue
        by_family.setdefault(evidence.owner_id, []).append(evidence)
        family = data.families.get(evidence.owner_id)
        if family is None:
            continue
        if family.parent1_id is not None:
            by_parent.setdefault(family.parent1_id, []).append(evidence)
        if family.parent2_id is not None and family.parent2_id != family.parent1_id:
            by_parent.setdefault(family.parent2_id, []).append(evidence)
    return (
        MappingProxyType({parent: tuple(values) for parent, values in by_parent.items()}),
        MappingProxyType({family: tuple(values) for family, values in by_family.items()}),
    )


def _build_birth_occurrence_positions(evidences):
    """Record birth, death and burial occurrence ordinals in one pass, never object identities."""
    by_person = {}
    deaths_by_person = {}
    burials_by_person = {}
    for position, evidence in enumerate(evidences):
        if (
            evidence.semantic is EventSemantic.BIRTH
            and evidence.owner_type is EvidenceOwnerType.PERSON
            and evidence.role is EventRoleSemantic.PRINCIPAL
            and evidence.principal_owner_type is TemporalOwnerType.PERSON
            and evidence.principal_owner_id == evidence.owner_id
        ):
            by_person.setdefault(evidence.owner_id, []).append(position)
        elif (
            evidence.semantic is EventSemantic.DEATH
            and evidence.owner_type is EvidenceOwnerType.PERSON
            and evidence.role is EventRoleSemantic.PRINCIPAL
            and evidence.principal_owner_type is TemporalOwnerType.PERSON
            and evidence.principal_owner_id == evidence.owner_id
        ):
            deaths_by_person.setdefault(evidence.owner_id, []).append(position)
        elif (
            evidence.semantic is EventSemantic.BURIAL
            and evidence.owner_type is EvidenceOwnerType.PERSON
            and evidence.role is EventRoleSemantic.PRINCIPAL
            and evidence.principal_owner_type is TemporalOwnerType.PERSON
            and evidence.principal_owner_id == evidence.owner_id
        ):
            burials_by_person.setdefault(evidence.owner_id, []).append(position)
    return (
        MappingProxyType({person: tuple(values) for person, values in by_person.items()}),
        MappingProxyType({person: tuple(values) for person, values in deaths_by_person.items()}),
        MappingProxyType({person: tuple(values) for person, values in burials_by_person.items()}),
    )


@dataclass(frozen=True, slots=True)
class RuleContext:
    data: RawGenealogyData
    evidences: tuple[TemporalEvidence, ...]
    _marriage_evidences_by_parent: Mapping[str, tuple[TemporalEvidence, ...]] = field(
        init=False, repr=False, compare=False,
    )
    _personal_principal_evidences: Mapping[tuple[str, EventSemantic], tuple[TemporalEvidence, ...]] = field(
        init=False, repr=False, compare=False,
    )
    _divorce_evidences_by_parent: Mapping[str, tuple[TemporalEvidence, ...]] = field(
        init=False, repr=False, compare=False,
    )
    _birth_occurrence_positions: Mapping[str, tuple[int, ...]] = field(
        init=False, repr=False, compare=False,
    )

    _death_occurrence_positions: Mapping[str, tuple[int, ...]] = field(
        init=False, repr=False, compare=False,
    )

    _burial_occurrence_positions: Mapping[str, tuple[int, ...]] = field(
        init=False, repr=False, compare=False,
    )

    _divorce_evidences_by_family: Mapping[str, tuple[TemporalEvidence, ...]] = field(
        init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.data, RawGenealogyData):
            raise TypeError("data must be a RawGenealogyData")

        if not isinstance(self.evidences, tuple):
            raise TypeError("evidences must be a tuple")

        if not all(
            isinstance(evidence, TemporalEvidence)
            for evidence in self.evidences
        ):
            raise TypeError(
                "evidences must contain only TemporalEvidence objects"
            )
        object.__setattr__(
            self, "_marriage_evidences_by_parent",
            _build_marriage_evidences_by_parent(self.data, self.evidences),
        )
        object.__setattr__(
            self, "_personal_principal_evidences",
            _build_personal_principal_evidences(self.evidences),
        )
        divorce_parents, divorce_families = _build_divorce_evidences_by_parent(self.data, self.evidences)
        object.__setattr__(self, "_divorce_evidences_by_parent", divorce_parents)
        object.__setattr__(self, "_divorce_evidences_by_family", divorce_families)
        birth_positions, death_positions, burial_positions = _build_birth_occurrence_positions(self.evidences)
        object.__setattr__(self, "_birth_occurrence_positions", birth_positions)
        object.__setattr__(self, "_death_occurrence_positions", death_positions)
        object.__setattr__(self, "_burial_occurrence_positions", burial_positions)

    def marriage_evidences_for_parent(self, person_id):
        return self._marriage_evidences_by_parent.get(person_id, ())

    def personal_principal_evidences(self, person_id, semantic):
        return self._personal_principal_evidences.get((person_id, semantic), ())

    def divorce_evidences_for_parent(self, person_id):
        return self._divorce_evidences_by_parent.get(person_id, ())

    def ordered_birth_evidences_for_parents(self, person_ids):
        streams = (
            zip(
                self._birth_occurrence_positions.get(person_id, ()),
                self.personal_principal_evidences(person_id, EventSemantic.BIRTH),
            )
            for person_id in person_ids
        )
        return tuple(
            evidence
            for _, evidence in merge(*streams, key=lambda item: item[0])
        )

    def ordered_death_evidences_for_parents(self, person_ids):
        streams = (
            zip(
                self._death_occurrence_positions.get(person_id, ()),
                self.personal_principal_evidences(person_id, EventSemantic.DEATH),
            )
            for person_id in person_ids
        )
        return tuple(
            evidence
            for _, evidence in merge(*streams, key=lambda item: item[0])
        )

    def ordered_burial_evidences_for_parents(self, person_ids):
        streams = (
            zip(
                self._burial_occurrence_positions.get(person_id, ()),
                self.personal_principal_evidences(person_id, EventSemantic.BURIAL),
            )
            for person_id in person_ids
        )
        return tuple(
            evidence
            for _, evidence in merge(*streams, key=lambda item: item[0])
        )

    def divorce_evidences_for_family(self, family_id):
        return self._divorce_evidences_by_family.get(family_id, ())
