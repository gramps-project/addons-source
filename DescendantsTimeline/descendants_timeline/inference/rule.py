from abc import ABC, abstractmethod

from descendants_timeline.inference.rule_context import RuleContext
from descendants_timeline.model.temporal_constraint import (
    ConstraintStrength,
    TemporalConstraint,
)
from descendants_timeline.model.temporal_target import TemporalTarget


class Rule(ABC):
    rule_id: str
    strength: ConstraintStrength

    @abstractmethod
    def is_applicable(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> bool:
        ...

    @abstractmethod
    def evaluate(
        self,
        target: TemporalTarget,
        context: RuleContext,
    ) -> tuple[TemporalConstraint, ...]:
        ...