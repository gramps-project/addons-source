"""Pure bound qualification for future graphical command construction."""

from dataclasses import dataclass, field
from enum import Enum
from datetime import date

from descendants_timeline.model.gramps_date_document import GrampsDateDocument
from descendants_timeline.model.temporal import TemporalValue, SourceQuality, ValueOrigin

from descendants_timeline.layout.position_kind import PositionKind
from descendants_timeline.model.temporal_constraint import ConstraintStrength
from descendants_timeline.inference.constraint_resolution import ConstraintConflictType
from descendants_timeline.inference.resolved_bound import ResolvedBound

from descendants_timeline.inference.reconciled_temporal_domain import (
    ReconciledBound,
    ReconciledBoundOrigin,
    ReconciledTemporalDomain,
)


@dataclass(frozen=True, slots=True)
class TemporalBoundQualification:
    bound: ReconciledBound
    show_inference_indicator: bool
    documentary_value: TemporalValue | None = None

    @property
    def documentary_boundary(self) -> date | None:
        return self.documentary_value.documentary_boundary if self.documentary_value else None


def qualify_temporal_bound(bound: ReconciledBound) -> TemporalBoundQualification:
    """Qualify a present reconciled bound, preserving its source unchanged."""
    return TemporalBoundQualification(
        bound=bound,
        show_inference_indicator=bound.origin is ReconciledBoundOrigin.INFERENCE,
    )


class TemporalShape(str, Enum):
    EXACT = "EXACT"
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    SPAN = "SPAN"


@dataclass(frozen=True, slots=True)
class TemporalDomainQualification:
    minimum: TemporalBoundQualification | None
    maximum: TemporalBoundQualification | None
    source_domain: ReconciledTemporalDomain | None = field(default=None, compare=False, repr=False)

    @property
    def shape(self) -> TemporalShape | None:
        """Classify reconciled dates independently of their provenance."""
        if self.minimum is None and self.maximum is None:
            return None
        if self.minimum is None:
            return TemporalShape.BEFORE
        if self.maximum is None:
            return TemporalShape.AFTER
        if self.minimum.bound.value == self.maximum.bound.value:
            return TemporalShape.EXACT
        return TemporalShape.SPAN

    @property
    def use_lightened_color(self) -> bool:
        """Color of the represented event domain, never of the central life bar."""
        return self.shape is not None and (
            self.shape is not TemporalShape.EXACT or self.show_inference_indicator
        )

    @property
    def show_inference_indicator(self) -> bool:
        """Request at most one indicator for the whole domain."""
        return (
            (self.minimum is not None and self.minimum.show_inference_indicator)
            or (self.maximum is not None and self.maximum.show_inference_indicator)
        )


def qualify_temporal_domain(
    domain: ReconciledTemporalDomain,
) -> TemporalDomainQualification:
    """Preserve the raw domain for existing consumers, including SOFT bounds.

    Use qualify_graphical_domain for the admissible projection. Keeping this
    raw view separate avoids changing layout/Cairo consumption in lot 1.
    """
    if domain.principal_minimum is None and domain.principal_maximum is None:
        raise NotImplementedError("only domains with at least one bound are supported yet")
    return TemporalDomainQualification(
        source_domain=domain,
        minimum=(
            qualify_temporal_bound(domain.principal_minimum)
            if domain.principal_minimum is not None else None
        ),
        maximum=(
            qualify_temporal_bound(domain.principal_maximum)
            if domain.principal_maximum is not None else None
        ),
    )


def qualify_graphical_domain(
    domain: ReconciledTemporalDomain,
    *, date_document: GrampsDateDocument | None = None,
) -> TemporalDomainQualification:
    """Project documentary and resolved HARD contributions without inference.

    Documentary principal bounds remain sovereign, including on a side where
    a stricter HARD constraint exists. A masked HARD bound may fill a missing
    side only if resolution/reconciliation did not invalidate it and it agrees
    with the opposite documentary bound. A rejected SOFT bound does not reject
    a distinct, compatible HARD contribution. Source objects remain untouched.
    """
    resolution = domain.constraint_resolution

    def select(
        principal: ReconciledBound | None,
        hard: ResolvedBound | None,
        opposite: ReconciledBound | None,
        *, minimum: bool,
    ) -> TemporalBoundQualification | None:
        if principal is not None and principal.origin is ReconciledBoundOrigin.GRAMPS:
            value = domain.gramps_value
            # Complete, year-only and month-only AFTER/BEFORE dates carry a documentary
            # reference on their own side. The reconciled bound stays unchanged.
            if (
                date_document is not None
                and date_document.calendar_code == 0
                and date_document.modifier_code == (2 if minimum else 1)
                and date_document.quality_code == 0
                and len(date_document.dateval) == 4
                and (
                    all(date_document.dateval[:3])
                    or (
                        minimum
                        and date_document.modifier_code == 2
                        and date_document.dateval[0] == 0
                        and date_document.dateval[1] == 0
                        and type(date_document.dateval[2]) is int
                        and date.min.year <= date_document.dateval[2] < date.max.year
                        and not date_document.dateval[3]
                        and date_document.newyear == 0
                    )
                    or (
                        not minimum
                        and date_document.modifier_code == 1
                        and date_document.dateval[0] == 0
                        and date_document.dateval[1] == 0
                        and type(date_document.dateval[2]) is int
                        and date.min.year < date_document.dateval[2] <= date.max.year
                        and not date_document.dateval[3]
                        and date_document.newyear == 0
                    )
                    or (
                        minimum
                        and date_document.modifier_code == 2
                        and date_document.dateval[0] == 0
                        and type(date_document.dateval[1]) is int
                        and 1 <= date_document.dateval[1] <= 12
                        and type(date_document.dateval[2]) is int
                        and date.min.year <= date_document.dateval[2] <= date.max.year
                        and not (
                            date_document.dateval[2] == date.max.year
                            and date_document.dateval[1] == date.max.month
                        )
                        and not date_document.dateval[3]
                        and date_document.newyear == 0
                    )
                    or (
                        not minimum
                        and date_document.modifier_code == 1
                        and date_document.dateval[0] == 0
                        and type(date_document.dateval[1]) is int
                        and 1 <= date_document.dateval[1] <= 12
                        and type(date_document.dateval[2]) is int
                        and date.min.year <= date_document.dateval[2] <= date.max.year
                        and not (
                            date_document.dateval[2] == date.min.year
                            and date_document.dateval[1] == date.min.month
                        )
                        and not date_document.dateval[3]
                        and date_document.newyear == 0
                    )
                )
                and value.value_origin is ValueOrigin.GRAMPS
                and value.source_quality is SourceQuality.NORMAL
                and value.is_usable_as_evidence
                and value.documentary_boundary is not None
                and (
                    (minimum and value.normalized_minimum == principal.value
                     and value.normalized_maximum is None)
                    or (not minimum and value.normalized_maximum == principal.value
                        and value.normalized_minimum is None)
                )
            ):
                return TemporalBoundQualification(principal, False, value)
            return qualify_temporal_bound(principal)
        if resolution.conflict_type is ConstraintConflictType.HARD_HARD:
            return None
        if hard is None and principal is not None:
            # Preserve an already reconciled HARD contribution even when a
            # caller supplies no separate hard_* entry (legacy raw fixtures).
            hard = principal.inferred_bound
        if hard is None or hard.strength is not ConstraintStrength.HARD:
            return None
        if any(hard == rejected for rejected in domain.conflicting_bounds):
            return None
        if opposite is not None and opposite.origin is ReconciledBoundOrigin.GRAMPS:
            if (minimum and hard.value > opposite.value) or (
                not minimum and hard.value < opposite.value
            ):
                return None
        bound = (
            principal if principal is not None and principal.inferred_bound is hard
            else ReconciledBound(hard.value, ReconciledBoundOrigin.INFERENCE, hard)
        )
        return qualify_temporal_bound(bound)

    return TemporalDomainQualification(
        minimum=select(domain.principal_minimum, resolution.hard_minimum,
                       domain.principal_maximum, minimum=True),
        maximum=select(domain.principal_maximum, resolution.hard_maximum,
                       domain.principal_minimum, minimum=False),
        source_domain=domain,
    )


@dataclass(frozen=True, slots=True)
class VisualPositionQualification:
    position_kind: PositionKind
    show_unknown_indicator: bool
    show_inference_indicator: bool


def should_show_visual_fallback_indicator(qualification: VisualPositionQualification) -> bool:
    """Request an indicator for an explicitly qualified visual fallback."""
    if qualification.position_kind is PositionKind.VISUAL_FALLBACK:
        return True
    if qualification.position_kind is PositionKind.REPRESENTATIVE:
        return False
    if qualification.position_kind is PositionKind.DOMAIN_DISPLAY:
        return False
    raise NotImplementedError("this visual position indicator decision is not supported yet")


def qualify_visual_position(position_kind: PositionKind) -> VisualPositionQualification:
    """Qualify a placement kind without assigning temporal provenance."""
    if position_kind in (PositionKind.REPRESENTATIVE, PositionKind.DOMAIN_DISPLAY):
        return VisualPositionQualification(
            position_kind=position_kind,
            show_unknown_indicator=False,
            show_inference_indicator=False,
        )
    if position_kind is not PositionKind.VISUAL_FALLBACK:
        raise NotImplementedError("this visual position kind is not supported yet")
    return VisualPositionQualification(
        position_kind=position_kind,
        show_unknown_indicator=True,
        show_inference_indicator=False,
    )
