from dataclasses import dataclass
from enum import Enum

from descendants_timeline.inference.resolved_bound import ResolvedBound
from descendants_timeline.model.temporal_constraint import (
    ConstraintOperator,
    ConstraintStrength,
    TemporalConstraint,
)
from descendants_timeline.model.temporal_target import TemporalTarget


class ConstraintConflictType(str, Enum):
    HARD_HARD = "HARD_HARD"
    HARD_SOFT = "HARD_SOFT"
    SOFT_SOFT = "SOFT_SOFT"


@dataclass(frozen=True, slots=True)
class ConstraintResolution:
    target: TemporalTarget

    hard_minimum: ResolvedBound | None
    hard_maximum: ResolvedBound | None

    refined_minimum: ResolvedBound | None
    refined_maximum: ResolvedBound | None

    conflict_type: ConstraintConflictType | None
    conflicting_constraints: tuple[TemporalConstraint, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target, TemporalTarget):
            raise TypeError("target must be a TemporalTarget")

        for bound_name, bound in (
            ("hard_minimum", self.hard_minimum),
            ("hard_maximum", self.hard_maximum),
            ("refined_minimum", self.refined_minimum),
            ("refined_maximum", self.refined_maximum),
        ):
            if bound is not None and not isinstance(bound, ResolvedBound):
                raise TypeError(
                    f"{bound_name} must be a ResolvedBound or None"
                )

            if bound is not None and bound.target != self.target:
                raise ValueError(
                    f"{bound_name} must have the ConstraintResolution target"
                )

        if (
            self.hard_minimum is not None
            and self.hard_minimum.operator
            is not ConstraintOperator.AFTER_OR_EQUAL
        ):
            raise ValueError(
                "hard_minimum must use AFTER_OR_EQUAL"
            )

        if (
            self.hard_maximum is not None
            and self.hard_maximum.operator
            is not ConstraintOperator.BEFORE_OR_EQUAL
        ):
            raise ValueError(
                "hard_maximum must use BEFORE_OR_EQUAL"
            )

        if (
            self.refined_minimum is not None
            and self.refined_minimum.operator
            is not ConstraintOperator.AFTER_OR_EQUAL
        ):
            raise ValueError(
                "refined_minimum must use AFTER_OR_EQUAL"
            )

        if (
            self.refined_maximum is not None
            and self.refined_maximum.operator
            is not ConstraintOperator.BEFORE_OR_EQUAL
        ):
            raise ValueError(
                "refined_maximum must use BEFORE_OR_EQUAL"
            )

        if (
            self.hard_minimum is not None
            and self.hard_minimum.strength
            is not ConstraintStrength.HARD
        ):
            raise ValueError(
                "hard_minimum must have HARD strength"
            )

        if (
            self.hard_maximum is not None
            and self.hard_maximum.strength
            is not ConstraintStrength.HARD
        ):
            raise ValueError(
                "hard_maximum must have HARD strength"
            )

        if (
            self.conflict_type is not None
            and not isinstance(
                self.conflict_type,
                ConstraintConflictType,
            )
        ):
            raise TypeError(
                "conflict_type must be a ConstraintConflictType or None"
            )

        if not isinstance(self.conflicting_constraints, tuple):
            raise TypeError(
                "conflicting_constraints must be a tuple"
            )

        if not all(
            isinstance(constraint, TemporalConstraint)
            for constraint in self.conflicting_constraints
        ):
            raise TypeError(
                "conflicting_constraints must contain only "
                "TemporalConstraint objects"
            )

        if (
            self.conflict_type is None
            and self.conflicting_constraints
        ):
            raise ValueError(
                "conflicting_constraints must be empty when "
                "conflict_type is None"
            )

        if (
            self.conflict_type is not None
            and not self.conflicting_constraints
        ):
            raise ValueError(
                "conflicting_constraints must not be empty when "
                "conflict_type is set"
            )
        if any(
            constraint.target != self.target
            for constraint in self.conflicting_constraints
        ):
            raise ValueError(
                "conflicting_constraints must have "
                "the ConstraintResolution target"
            )
        if (
            self.conflict_type is not None
            and len(self.conflicting_constraints) < 2
        ):
            raise ValueError(
                "a conflict must contain at least two constraints"
            )
        if (
            self.conflict_type is ConstraintConflictType.HARD_HARD
            and any(
                constraint.strength is not ConstraintStrength.HARD
                for constraint in self.conflicting_constraints
            )
        ):
            raise ValueError(
                "HARD_HARD conflict must contain only HARD constraints"
            )
        if (
            self.conflict_type is ConstraintConflictType.SOFT_SOFT
            and any(
                constraint.strength is not ConstraintStrength.SOFT
                for constraint in self.conflicting_constraints
            )
        ):
            raise ValueError(
                "SOFT_SOFT conflict must contain only SOFT constraints"
            )
        if self.conflict_type is ConstraintConflictType.HARD_SOFT:
            has_hard = any(
                constraint.strength is ConstraintStrength.HARD
                for constraint in self.conflicting_constraints
            )

            has_soft = any(
                constraint.strength is ConstraintStrength.SOFT
                for constraint in self.conflicting_constraints
            )

            if not has_hard or not has_soft:
                raise ValueError(
                    "HARD_SOFT conflict must contain "
                    "at least one HARD and one SOFT constraint"
                )
