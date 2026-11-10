"""Pure, isolated graphical qualification for DEATH; no renderer integration."""

from dataclasses import dataclass
from descendants_timeline.inference.reconciled_temporal_domain import (
    ReconciledBoundOrigin,
)
from descendants_timeline.model.temporal_constraint import ConstraintStrength
from descendants_timeline.temporal_bound_qualification import (
    TemporalBoundQualification, TemporalDomainQualification, TemporalShape,
    qualify_graphical_domain,
)


@dataclass(frozen=True, slots=True)
class DeathGraphicalQualification:
    temporal_qualification: TemporalDomainQualification
    minimum: TemporalBoundQualification | None
    maximum: TemporalBoundQualification | None
    # None means no admissible geometry; it never requests a visual fallback.
    shape: TemporalShape | None

def _is_graphically_admissible(
    qualification: TemporalBoundQualification | None,
) -> bool:
    """Accept documentary bounds and principal HARD inferred bounds only."""
    if qualification is None:
        return False

    bound = qualification.bound
    return (
        bound.origin is ReconciledBoundOrigin.GRAMPS
        or (
            bound.origin is ReconciledBoundOrigin.INFERENCE
            and bound.inferred_bound is not None
            and bound.inferred_bound.strength is ConstraintStrength.HARD
        )
    )


def qualify_death_graphically(
    qualification: TemporalDomainQualification,
) -> DeathGraphicalQualification:
    """Filter contributions before determining the graphical shape."""
    if qualification.source_domain is not None:
        admissible = qualify_graphical_domain(qualification.source_domain)

        def retain_original(selected, original):
            if selected is not None and original is not None and selected.bound is original.bound:
                return original
            return selected

        return DeathGraphicalQualification(
            qualification,
            retain_original(admissible.minimum, qualification.minimum),
            retain_original(admissible.maximum, qualification.maximum),
            admissible.shape,
        )

    minimum = (
        qualification.minimum
        if _is_graphically_admissible(qualification.minimum)
        else None
    )
    maximum = (
        qualification.maximum
        if _is_graphically_admissible(qualification.maximum)
        else None
    )

    shape = TemporalDomainQualification(minimum, maximum).shape

    return DeathGraphicalQualification(
        qualification,
        minimum,
        maximum,
        shape,
    )
