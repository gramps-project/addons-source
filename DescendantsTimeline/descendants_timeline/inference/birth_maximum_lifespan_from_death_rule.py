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


class BirthMaximumLifespanFromDeathRule(Rule):
    rule_id = "BIRTH_MAXIMUM_LIFESPAN_FROM_DEATH"
    strength = ConstraintStrength.SOFT

    def is_applicable(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> bool:
        return (
            target.owner_type is TemporalOwnerType.PERSON
            and target.semantic is TargetSemantic.BIRTH
        )

    def evaluate(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> tuple[TemporalConstraint, ...]:

        if not self.is_applicable(target, context):
            return ()

        death_evidences = context.personal_principal_evidences(
            target.owner_id, EventSemantic.DEATH,
        )

        if len(death_evidences) != 1:
            return ()

        death_evidence = death_evidences[0]

        death_minimum = death_evidence.date.normalized_minimum

        if death_minimum is None:
            return ()

        return (
            TemporalConstraint(
                target=target,
                operator=ConstraintOperator.AFTER_OR_EQUAL,
                bound=add_years(
                    death_minimum,
                    -MAX_PLAUSIBLE_LIFESPAN_YEARS,
                ),
                rule_id=self.rule_id,
                strength=self.strength,
                evidences=(death_evidence,),
            ),
        )
