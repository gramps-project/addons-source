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


class MarriageBeforeSpouseBurialRule(Rule):
    rule_id = "MARRIAGE_BEFORE_SPOUSE_BURIAL"
    strength = ConstraintStrength.HARD

    def is_applicable(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> bool:
        return (
            target.owner_type is TemporalOwnerType.FAMILY
            and target.semantic is TargetSemantic.MARRIAGE
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

        burial_evidences = context.ordered_burial_evidences_for_parents(
            family_person_ids
        )

        constraints = []

        for burial_evidence in burial_evidences:
            if burial_evidence.date.normalized_maximum is None:
                continue

            constraints.append(
                TemporalConstraint(
                    target=target,
                    operator=ConstraintOperator.BEFORE_OR_EQUAL,
                    bound=burial_evidence.date.normalized_maximum,
                    rule_id=self.rule_id,
                    strength=self.strength,
                    evidences=(burial_evidence,),
                )
            )

        return tuple(constraints)