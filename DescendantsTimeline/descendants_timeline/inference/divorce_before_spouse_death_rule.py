from descendants_timeline.inference.rule import Rule
from descendants_timeline.inference.rule_context import RuleContext

from descendants_timeline.model.temporal_target import (
    TemporalOwnerType,
    TemporalTarget,
    TargetSemantic,
)

from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.person_event_ref import EventRoleSemantic
from descendants_timeline.model.temporal_constraint import (
    ConstraintOperator,
    ConstraintStrength,
    TemporalConstraint,
)
from descendants_timeline.model.temporal_evidence import (
    EvidenceOwnerType,
)


class DivorceBeforeSpouseDeathRule(Rule):
    rule_id = "DIVORCE_BEFORE_SPOUSE_DEATH"
    strength = ConstraintStrength.HARD

    def is_applicable(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> bool:
        return (
            target.owner_type is TemporalOwnerType.FAMILY
            and target.semantic is TargetSemantic.DIVORCE
        )

    def evaluate(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> tuple[TemporalConstraint, ...]:

        if not self.is_applicable(target, context):
            return ()

        family = context.data.families.get(target.owner_id)

        if family is None:
            return ()

        family_person_ids = {
            person_id
            for person_id in (
                family.parent1_id,
                family.parent2_id,
            )
            if person_id is not None
        }

        death_evidences = tuple(
            evidence
            for evidence in context.evidences
            if (
                evidence.semantic is EventSemantic.DEATH
                and evidence.owner_type is EvidenceOwnerType.PERSON
                and evidence.owner_id in family_person_ids
                and evidence.role is EventRoleSemantic.PRINCIPAL
                and evidence.principal_owner_type
                is TemporalOwnerType.PERSON
                and evidence.principal_owner_id == evidence.owner_id
            )
        )

        constraints = []

        for death_evidence in death_evidences:

            if death_evidence.date.normalized_maximum is None:
                continue

            constraints.append(
                TemporalConstraint(
                    target=target,
                    operator=ConstraintOperator.BEFORE_OR_EQUAL,
                    bound=death_evidence.date.normalized_maximum,
                    rule_id=self.rule_id,
                    strength=self.strength,
                    evidences=(death_evidence,),
                )
            )

        return tuple(constraints)