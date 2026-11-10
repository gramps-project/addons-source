from enum import Enum

from dataclasses import dataclass
from datetime import date

from .resolved_bound import ResolvedBound

from .constraint_resolution import ConstraintResolution
from ..model.temporal import TemporalValue
from ..model.temporal_target import TemporalTarget

class ReconciledBoundOrigin(str, Enum):
    GRAMPS = "GRAMPS"
    INFERENCE = "INFERENCE"


class ReconciliationConflictType(str, Enum):
    GRAMPS_INFERENCE = "GRAMPS_INFERENCE"

@dataclass(frozen=True, slots=True)
class ReconciledBound:
    value: date
    origin: ReconciledBoundOrigin
    inferred_bound: ResolvedBound | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.value, date):
            raise TypeError("value must be a date")

        if not isinstance(self.origin, ReconciledBoundOrigin):
            raise TypeError(
                "origin must be a ReconciledBoundOrigin"
            )

        if self.origin == ReconciledBoundOrigin.GRAMPS:
            if self.inferred_bound is not None:
                raise ValueError(
                    "a GRAMPS bound cannot have an inferred_bound"
                )

        if self.origin == ReconciledBoundOrigin.INFERENCE:
            if not isinstance(self.inferred_bound, ResolvedBound):
                raise ValueError(
                    "an INFERENCE bound requires an inferred_bound"
                )

            if self.value != self.inferred_bound.value:
                raise ValueError(
                    "value must match inferred_bound.value"
                )

@dataclass(frozen=True, slots=True)
class ReconciledTemporalDomain:
    target: TemporalTarget
    gramps_value: TemporalValue
    constraint_resolution: ConstraintResolution

    principal_minimum: ReconciledBound | None
    principal_maximum: ReconciledBound | None

    conflict_type: ReconciliationConflictType | None
    conflicting_bounds: tuple[ResolvedBound, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target, TemporalTarget):
            raise TypeError(
                "target must be a TemporalTarget"
            )

        if not isinstance(self.gramps_value, TemporalValue):
            raise TypeError(
                "gramps_value must be a TemporalValue"
            )

        if not isinstance(
            self.constraint_resolution,
            ConstraintResolution,
        ):
            raise TypeError(
                "constraint_resolution must be a ConstraintResolution"
            )

        if self.constraint_resolution.target != self.target:
            raise ValueError(
                "constraint_resolution target must match target"
            )

        if (
            self.principal_minimum is not None
            and not isinstance(
                self.principal_minimum,
                ReconciledBound,
            )
        ):
            raise TypeError(
                "principal_minimum must be a ReconciledBound or None"
            )

        if (
            self.principal_maximum is not None
            and not isinstance(
                self.principal_maximum,
                ReconciledBound,
            )
        ):
            raise TypeError(
                "principal_maximum must be a ReconciledBound or None"
            )

        if (
            self.principal_minimum is not None
            and self.principal_maximum is not None
            and self.principal_minimum.value
            > self.principal_maximum.value
        ):
            raise ValueError(
                "principal_minimum cannot be after principal_maximum"
            )

        if (
            self.conflict_type is not None
            and not isinstance(
                self.conflict_type,
                ReconciliationConflictType,
            )
        ):
            raise TypeError(
                "conflict_type must be a "
                "ReconciliationConflictType or None"
            )

        if not isinstance(self.conflicting_bounds, tuple):
            raise TypeError(
                "conflicting_bounds must be a tuple"
            )

        if not all(
            isinstance(bound, ResolvedBound)
            for bound in self.conflicting_bounds
        ):
            raise TypeError(
                "conflicting_bounds must contain only ResolvedBound"
            )

        if self.conflict_type is None:
            if self.conflicting_bounds:
                raise ValueError(
                    "conflicting_bounds requires a conflict_type"
                )
        else:
            if not self.conflicting_bounds:
                raise ValueError(
                    "conflict_type requires conflicting_bounds"
                )