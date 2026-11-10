from descendants_timeline.inference.rule import Rule
from descendants_timeline.inference.rule_context import RuleContext

from descendants_timeline.model.temporal_target import (
    TemporalOwnerType,
    TemporalTarget,
    TargetSemantic,
)

from descendants_timeline.model.temporal_constraint import (
    ConstraintOperator,
    ConstraintStrength,
    TemporalConstraint,
)

from .date_arithmetic import add_years
from .inference_parameters import MIN_MARRIAGE_AGE_YEARS


class BirthMinimumAgeAtMarriageRule(Rule):
    rule_id = "BIRTH_MINIMUM_AGE_AT_MARRIAGE"
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

        marriage_evidences = context.marriage_evidences_for_parent(target.owner_id)

        constraints = []

        for marriage_evidence in marriage_evidences:
            marriage_maximum = (
                marriage_evidence.date.normalized_maximum
            )

            if marriage_maximum is None:
                continue

            constraints.append(
                TemporalConstraint(
                    target=target,
                    operator=ConstraintOperator.BEFORE_OR_EQUAL,
                    bound=add_years(
                        marriage_maximum,
                        -MIN_MARRIAGE_AGE_YEARS,
                    ),
                    rule_id=self.rule_id,
                    strength=self.strength,
                    evidences=(marriage_evidence,),
                )
            )

        return tuple(constraints)
