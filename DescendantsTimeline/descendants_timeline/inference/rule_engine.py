from dataclasses import dataclass

from descendants_timeline.inference.rule import Rule
from descendants_timeline.inference.rule_context import RuleContext
from descendants_timeline.model.temporal_constraint import TemporalConstraint
from descendants_timeline.model.temporal_target import TemporalTarget


@dataclass(frozen=True, slots=True)
class RuleEngine:
    rules: tuple[Rule, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rules, tuple):
            raise TypeError("rules must be a tuple")

        if not all(
            isinstance(rule, Rule)
            for rule in self.rules
        ):
            raise TypeError(
                "rules must contain only Rule objects"
            )

    def evaluate(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> tuple[TemporalConstraint, ...]:
        constraints: list[TemporalConstraint] = []

        for rule in self.rules:
            if not rule.is_applicable(target, context):
                continue

            rule_constraints = rule.evaluate(
                target,
                context,
            )

            constraints.extend(rule_constraints)

        return tuple(constraints)