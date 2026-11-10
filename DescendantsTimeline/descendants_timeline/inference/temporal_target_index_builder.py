"""Construction de l'index des cibles temporelles."""

from __future__ import annotations

from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.temporal import TemporalValue
from descendants_timeline.model.temporal_target import (
    TargetSemantic,
    TemporalOwnerType,
    TemporalTarget,
)
from descendants_timeline.model.temporal_target_entry import TemporalTargetEntry
from descendants_timeline.model.temporal_target_index import TemporalTargetIndex

from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.event_date_evidence import (
    is_event_date_modifier_admissible_as_evidence,
)
from descendants_timeline.model.person_event_ref import EventRoleSemantic

from descendants_timeline.model.temporal_target_anomaly import (
    TemporalTargetAnomaly,
    TemporalTargetAnomalyType,
)
from descendants_timeline.model.family_event_ref import FamilyRoleSemantic


def _person_principal_event_ids(
    person,
    semantic: EventSemantic,
    data: RawGenealogyData,
) -> tuple[str, ...]:
    return tuple(
        ref.event_id
        for ref in person.event_refs
        if ref.semantic_role is EventRoleSemantic.PRINCIPAL
        and data.events[ref.event_id].semantic is semantic
    )
def _family_event_ids(
    family,
    semantic: EventSemantic,
    data: RawGenealogyData,
) -> tuple[str, ...]:
    return tuple(
        ref.event_id
        for ref in family.event_refs
        if ref.semantic_role is FamilyRoleSemantic.FAMILY
        and data.events[ref.event_id].semantic is semantic
    )


def selected_gramps_event_id(
    data: RawGenealogyData,
    target: TemporalTarget,
) -> str | None:
    """Retourne la source unique sélectionnée pour la cible, sans comparer les dates."""
    semantic = {
        TargetSemantic.BIRTH: EventSemantic.BIRTH,
        TargetSemantic.DEATH: EventSemantic.DEATH,
        TargetSemantic.MARRIAGE: EventSemantic.MARRIAGE,
        TargetSemantic.DIVORCE: EventSemantic.DIVORCE,
    }[target.semantic]
    if target.owner_type is TemporalOwnerType.PERSON:
        event_ids = _person_principal_event_ids(
            data.persons[target.owner_id], semantic, data,
        )
    else:
        event_ids = _family_event_ids(
            data.families[target.owner_id], semantic, data,
        )
    return event_ids[0] if len(event_ids) == 1 else None


class TemporalTargetIndexBuilder:
    """Construit les cibles temporelles reconnues dans une généalogie."""

    def build(self, data: RawGenealogyData) -> TemporalTargetIndex:
        if not isinstance(data, RawGenealogyData):
            raise TypeError("data doit être un RawGenealogyData.")

        entries: dict[TemporalTarget, TemporalTargetEntry] = {}

        for person in data.persons.values():
            birth_entry = self._build_person_target_entry(
                person,
                EventSemantic.BIRTH,
                TargetSemantic.BIRTH,
                data,
            )
            entries[birth_entry.target] = birth_entry

            death_entry = self._build_person_target_entry(
                person,
                EventSemantic.DEATH,
                TargetSemantic.DEATH,
                data,
            )
            entries[death_entry.target] = death_entry

        for family in data.families.values():
            marriage_entry = self._build_family_target_entry(
                family,
                EventSemantic.MARRIAGE,
                TargetSemantic.MARRIAGE,
                data,
            )

            if marriage_entry is not None:
                entries[marriage_entry.target] = marriage_entry
            divorce_entry = self._build_family_target_entry(
                family,
                EventSemantic.DIVORCE,
                TargetSemantic.DIVORCE,
                data,
            )

            if divorce_entry is not None:
                entries[divorce_entry.target] = divorce_entry

        return TemporalTargetIndex(entries=entries)

    def _build_person_target_entry(
        self,
        person,
        semantic: EventSemantic,
        target_semantic: TargetSemantic,
        data: RawGenealogyData,
    ) -> TemporalTargetEntry:
        event_ids = _person_principal_event_ids(
            person,
            semantic,
            data,
        )

        target = TemporalTarget(
            owner_type=TemporalOwnerType.PERSON,
            owner_id=person.person_id,
            semantic=target_semantic,
        )

        if len(event_ids) == 1:
            event = data.events[event_ids[0]]
            gramps_value = event.date
            if event.date_document is not None and not (
                is_event_date_modifier_admissible_as_evidence(
                    event.semantic,
                    event.date_document.modifier_code,
                )
            ):
                gramps_value = TemporalValue.unknown()
            anomalies = ()

        elif len(event_ids) > 1:
            gramps_value = TemporalValue.unknown()
            anomalies = (
                TemporalTargetAnomaly(
                    anomaly_type=(
                        TemporalTargetAnomalyType.MULTIPLE_PRINCIPAL_EVENTS
                    ),
                    event_ids=event_ids,
                ),
            )

        else:
            gramps_value = TemporalValue.unknown()
            anomalies = ()

        return TemporalTargetEntry(
            target=target,
            gramps_value=gramps_value,
            anomalies=anomalies,
        )
    def _build_family_target_entry(
        self,
        family,
        semantic: EventSemantic,
        target_semantic: TargetSemantic,
        data: RawGenealogyData,
    ) -> TemporalTargetEntry | None:
        event_ids = _family_event_ids(
            family,
            semantic,
            data,
        )

        if not event_ids:
            return None

        target = TemporalTarget(
            owner_type=TemporalOwnerType.FAMILY,
            owner_id=family.family_id,
            semantic=target_semantic,
        )

        if len(event_ids) == 1:
            event = data.events[event_ids[0]]
            gramps_value = event.date
            if event.date_document is not None and not (
                is_event_date_modifier_admissible_as_evidence(
                    event.semantic,
                    event.date_document.modifier_code,
                )
            ):
                gramps_value = TemporalValue.unknown()
            anomalies = ()

        else:
            gramps_value = TemporalValue.unknown()
            anomalies = (
                TemporalTargetAnomaly(
                    anomaly_type=(
                        TemporalTargetAnomalyType.MULTIPLE_PRINCIPAL_EVENTS
                    ),
                    event_ids=event_ids,
                ),
            )

        return TemporalTargetEntry(
            target=target,
            gramps_value=gramps_value,
            anomalies=anomalies,
        )
