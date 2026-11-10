from descendants_timeline.inference.constraint_resolution import (
    ConstraintConflictType,
    ConstraintResolution,
)

from descendants_timeline.model.temporal_target import (
    TemporalTarget,
)
from descendants_timeline.inference.resolved_bound import ResolvedBound
from descendants_timeline.model.temporal_constraint import (
    ConstraintOperator,
    ConstraintStrength,
    TemporalConstraint,
)

class ConstraintResolver:
    def resolve(
        self,
        target: TemporalTarget,
        constraints: tuple[TemporalConstraint, ...],
    ) -> ConstraintResolution:
        if not isinstance(target, TemporalTarget):
            raise TypeError("target must be a TemporalTarget")

        if not isinstance(constraints, tuple):
            raise TypeError("constraints must be a tuple")

        if not all(
            isinstance(constraint, TemporalConstraint)
            for constraint in constraints
        ):
            raise TypeError(
                "constraints must contain only TemporalConstraint objects"
            )

        if not all(
            constraint.target == target
            for constraint in constraints
        ):
            raise ValueError(
                "all constraints must have the requested target"
            )

        hard_minimum = self._resolve_bound(
            target=target,
            constraints=constraints,
            operator=ConstraintOperator.AFTER_OR_EQUAL,
            strength=ConstraintStrength.HARD,
        )

        hard_maximum = self._resolve_bound(
            target=target,
            constraints=constraints,
            operator=ConstraintOperator.BEFORE_OR_EQUAL,
            strength=ConstraintStrength.HARD,
        )

        compatible_soft_constraints = tuple(
            constraint
            for constraint in constraints
            if (
                constraint.strength == ConstraintStrength.SOFT
                and not (
                    constraint.operator == ConstraintOperator.BEFORE_OR_EQUAL
                    and hard_minimum is not None
                    and constraint.bound < hard_minimum.value
                )
                and not (
                    constraint.operator == ConstraintOperator.AFTER_OR_EQUAL
                    and hard_maximum is not None
                    and constraint.bound > hard_maximum.value
                )
            )
        )

        conflicting_soft_constraints = tuple(
            constraint
            for constraint in constraints
            if (
                constraint.strength == ConstraintStrength.SOFT
                and (
                    (
                        constraint.operator == ConstraintOperator.BEFORE_OR_EQUAL
                        and hard_minimum is not None
                        and constraint.bound < hard_minimum.value
                    )
                    or
                    (
                        constraint.operator == ConstraintOperator.AFTER_OR_EQUAL
                        and hard_maximum is not None
                        and constraint.bound > hard_maximum.value
                    )
                )
            )
        )

        soft_minimum = self._resolve_bound(
            target=target,
            constraints=compatible_soft_constraints,
            operator=ConstraintOperator.AFTER_OR_EQUAL,
            strength=ConstraintStrength.SOFT,
        )

        soft_maximum = self._resolve_bound(
            target=target,
            constraints=compatible_soft_constraints,
            operator=ConstraintOperator.BEFORE_OR_EQUAL,
            strength=ConstraintStrength.SOFT,
        )

        if (
            hard_minimum is not None
            and hard_maximum is not None
            and hard_minimum.value > hard_maximum.value
        ):
            refined_minimum = None
            refined_maximum = None
            conflict_type = ConstraintConflictType.HARD_HARD
            conflicting_constraints = (
                hard_minimum.constraints
                + hard_maximum.constraints
            )
        else:
            if (
                hard_minimum is not None
                and soft_maximum is not None
                and soft_maximum.value < hard_minimum.value
            ):
                refined_minimum = hard_minimum
                refined_maximum = hard_maximum

                conflict_type = ConstraintConflictType.HARD_SOFT
                conflicting_constraints = (
                    hard_minimum.constraints
                    + soft_maximum.constraints
                )

            elif (
                hard_maximum is not None
                and soft_minimum is not None
                and soft_minimum.value > hard_maximum.value
            ):
                refined_minimum = hard_minimum
                refined_maximum = hard_maximum

                conflict_type = ConstraintConflictType.HARD_SOFT
                conflicting_constraints = (
                    hard_maximum.constraints
                    + soft_minimum.constraints
                )
            else:
                if hard_minimum is None:
                    refined_minimum = soft_minimum

                elif (
                    soft_minimum is not None
                    and soft_minimum.value > hard_minimum.value
                ):
                    refined_minimum = soft_minimum

                else:
                    refined_minimum = hard_minimum

                if hard_maximum is None:
                    refined_maximum = soft_maximum

                elif (
                    soft_maximum is not None
                    and soft_maximum.value < hard_maximum.value
                ):
                    refined_maximum = soft_maximum

                else:
                    refined_maximum = hard_maximum

                if (
                    refined_minimum is not None
                    and refined_maximum is not None
                    and refined_minimum.value > refined_maximum.value
                ):
                    refined_minimum = hard_minimum
                    refined_maximum = hard_maximum
                    conflict_type = ConstraintConflictType.SOFT_SOFT
                    conflicting_constraints = (
                        soft_minimum.constraints
                        + soft_maximum.constraints
                    )
                else:
                    if conflicting_soft_constraints:
                        conflict_type = ConstraintConflictType.HARD_SOFT

                        conflicting_constraints = tuple(
                            constraint
                            for constraint in constraints
                            if (
                                (
                                    constraint.strength == ConstraintStrength.HARD
                                    and (
                                        (
                                            constraint.operator
                                            == ConstraintOperator.AFTER_OR_EQUAL
                                            and any(
                                                soft.operator
                                                == ConstraintOperator.BEFORE_OR_EQUAL
                                                and soft.bound < constraint.bound
                                                for soft in conflicting_soft_constraints
                                            )
                                        )
                                        or
                                        (
                                            constraint.operator
                                            == ConstraintOperator.BEFORE_OR_EQUAL
                                            and any(
                                                soft.operator
                                                == ConstraintOperator.AFTER_OR_EQUAL
                                                and soft.bound > constraint.bound
                                                for soft in conflicting_soft_constraints
                                            )
                                        )
                                    )
                                )
                                or constraint in conflicting_soft_constraints
                            )
                        )

                    else:
                        conflict_type = None
                        conflicting_constraints = ()

        return ConstraintResolution(
            target=target,
            hard_minimum=hard_minimum,
            hard_maximum=hard_maximum,
            refined_minimum=refined_minimum,
            refined_maximum=refined_maximum,
            conflict_type=conflict_type,
            conflicting_constraints=conflicting_constraints,
        )
    def _resolve_bound(
        self,
        target: TemporalTarget,
        constraints: tuple[TemporalConstraint, ...],
        operator: ConstraintOperator,
        strength: ConstraintStrength,
    ) -> ResolvedBound | None:
        matching_constraints = tuple(
            constraint
            for constraint in constraints
            if (
                constraint.operator == operator
                and constraint.strength == strength
            )
        )

        if not matching_constraints:
            return None

        if operator == ConstraintOperator.AFTER_OR_EQUAL:
            winning_value = max(
                constraint.bound
                for constraint in matching_constraints
            )
        else:
            winning_value = min(
                constraint.bound
                for constraint in matching_constraints
            )

        winning_constraints = tuple(
            constraint
            for constraint in matching_constraints
            if constraint.bound == winning_value
        )

        return ResolvedBound(
            target=target,
            value=winning_value,
            operator=operator,
            strength=strength,
            constraints=winning_constraints,
        )

