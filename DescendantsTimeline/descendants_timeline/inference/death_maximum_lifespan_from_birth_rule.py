from descendants_timeline.inference.rule import Rule
from descendants_timeline.inference.rule_context import RuleContext

from descendants_timeline.model.temporal_target import (
    TemporalOwnerType,
    TemporalTarget,
    TargetSemantic,
)

from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.temporal_constraint import (
    ConstraintOperator,
    ConstraintStrength,
    TemporalConstraint,
)

from .date_arithmetic import add_years
from .inference_parameters import MAX_PLAUSIBLE_LIFESPAN_YEARS


class DeathMaximumLifespanFromBirthRule(Rule):
    rule_id = "DEATH_MAXIMUM_LIFESPAN_FROM_BIRTH"
    strength = ConstraintStrength.SOFT

    def is_applicable(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> bool:
        return (
            target.owner_type is TemporalOwnerType.PERSON
            and target.semantic is TargetSemantic.DEATH
        )

    def evaluate(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> tuple[TemporalConstraint, ...]:

        if not self.is_applicable(target, context):
            return ()

        birth_evidences = context.personal_principal_evidences(
            target.owner_id, EventSemantic.BIRTH,
        )

        if len(birth_evidences) != 1:
            return ()

        birth_evidence = birth_evidences[0]

        birth_maximum = birth_evidence.date.normalized_maximum

        if birth_maximum is None:
            return ()

        return (
            TemporalConstraint(
                target=target,
                operator=ConstraintOperator.BEFORE_OR_EQUAL,
                bound=add_years(
                    birth_maximum,
                    MAX_PLAUSIBLE_LIFESPAN_YEARS,
                ),
                rule_id=self.rule_id,
                strength=self.strength,
                evidences=(birth_evidence,),
            ),
        )
