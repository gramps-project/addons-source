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


class BirthMaximumLifespanFromBurialRule(Rule):
    rule_id = "BIRTH_MAXIMUM_LIFESPAN_FROM_BURIAL"
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

        burial_evidences = context.personal_principal_evidences(
            target.owner_id, EventSemantic.BURIAL,
        )

        constraints = []

        for burial_evidence in burial_evidences:
            burial_minimum = (
                burial_evidence.date.normalized_minimum
            )

            if burial_minimum is None:
                continue

            constraints.append(
                TemporalConstraint(
                    target=target,
                    operator=ConstraintOperator.AFTER_OR_EQUAL,
                    bound=add_years(
                        burial_minimum,
                        -MAX_PLAUSIBLE_LIFESPAN_YEARS,
                    ),
                    rule_id=self.rule_id,
                    strength=self.strength,
                    evidences=(burial_evidence,),
                )
            )

        return tuple(constraints)
