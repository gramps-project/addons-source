from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.event_date_evidence import (
    is_event_date_modifier_admissible_as_evidence,
)
from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.person_event_ref import EventRoleSemantic
from descendants_timeline.model.temporal_evidence import (
    EvidenceOwnerType,
    TemporalEvidence,
)
from descendants_timeline.model.temporal_target import TemporalOwnerType
from descendants_timeline.model.family_event_ref import FamilyRoleSemantic

from descendants_timeline.inference.event_reference_index import (
    EventReferenceIndex,
)


class TemporalEvidenceBuilder:
    """
    Construit les TemporalEvidence à partir des données généalogiques brutes.

    Le Builder qualifie les références d'événements utilisables comme preuves
    temporelles.

    Il ne produit aucune TemporalConstraint et n'effectue aucune inférence
    temporelle.
    """

    @classmethod
    def build(
        cls,
        data: RawGenealogyData,
    ) -> tuple[TemporalEvidence, ...]:

        if not isinstance(data, RawGenealogyData):
            raise TypeError("data must be a RawGenealogyData")

        reference_index = EventReferenceIndex.from_data(data)

        evidences: list[TemporalEvidence] = []

        for event in data.events.values():

            individual_event_semantics = (
                EventSemantic.BIRTH,
                EventSemantic.BAPTISM,
                EventSemantic.DEATH,
                EventSemantic.BURIAL,
            )

            family_event_semantics = (
                EventSemantic.MARRIAGE,
                EventSemantic.DIVORCE,
            )

            individual_existence_event_semantics = (
                EventSemantic.CENSUS,
            )

            if event.semantic not in (
                *individual_event_semantics,
                *family_event_semantics,
                *individual_existence_event_semantics,
            ):
                continue

            if event.date_document is not None and not (
                is_event_date_modifier_admissible_as_evidence(
                    event.semantic,
                    event.date_document.modifier_code,
                )
            ):
                continue

            if not event.date.is_usable_as_evidence:
                continue

            references = reference_index.get(event.event_id)

            if event.semantic in individual_event_semantics:
                principal_references = tuple(
                    reference
                    for reference in references
                    if (
                        reference.owner_type is EvidenceOwnerType.PERSON
                        and reference.role is EventRoleSemantic.PRINCIPAL
                    )
                )

                principal_owner_type = TemporalOwnerType.PERSON

            elif event.semantic in family_event_semantics:
                principal_references = tuple(
                    reference
                    for reference in references
                    if (
                        reference.owner_type is EvidenceOwnerType.FAMILY
                        and reference.role is FamilyRoleSemantic.FAMILY
                    )
                )

                principal_owner_type = TemporalOwnerType.FAMILY

            elif event.semantic in individual_existence_event_semantics:
                principal_references = tuple(
                    reference
                    for reference in references
                    if (
                        reference.owner_type is EvidenceOwnerType.PERSON
                        and reference.role is EventRoleSemantic.PRINCIPAL
                    )
                )

                principal_owner_type = TemporalOwnerType.PERSON

            else:
                continue

            if len(principal_references) != 1:
                continue

            principal_reference = principal_references[0]

            for reference in references:

                if event.semantic in individual_event_semantics:

                    if reference.owner_type is not EvidenceOwnerType.PERSON:
                        continue

                    if reference.role not in (
                        EventRoleSemantic.PRINCIPAL,
                        EventRoleSemantic.WITNESS,
                        EventRoleSemantic.INFORMANT,
                    ):
                        continue

                elif event.semantic in family_event_semantics:

                    if reference.owner_type is EvidenceOwnerType.FAMILY:
                        if reference.role is not FamilyRoleSemantic.FAMILY:
                            continue

                    elif reference.owner_type is EvidenceOwnerType.PERSON:
                        if reference.role not in (
                            EventRoleSemantic.WITNESS,
                            EventRoleSemantic.INFORMANT,
                        ):
                            continue

                    else:
                        continue

                elif event.semantic in individual_existence_event_semantics:

                    if reference.owner_type is not EvidenceOwnerType.PERSON:
                        continue

                    if reference.role is not EventRoleSemantic.PRINCIPAL:
                        continue

                else:
                    continue

                evidence = TemporalEvidence(
                    owner_type=reference.owner_type,
                    owner_id=reference.owner_id,
                    event_id=event.event_id,
                    semantic=event.semantic,
                    role=reference.role,
                    date=event.date,
                    principal_owner_type=principal_owner_type,
                    principal_owner_id=principal_reference.owner_id,
                )

                evidences.append(evidence)

        return tuple(evidences)
