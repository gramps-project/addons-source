from datetime import date
from dataclasses import dataclass
from enum import Enum

from descendants_timeline.inference.reconciled_temporal_domain import (
    ReconciledBound, ReconciledBoundOrigin,
)

from descendants_timeline.inference.bound_provenance import has_independent_bound_justification
from descendants_timeline.inference.temporal_inference_result import (
    TemporalInferenceResult,
)
from descendants_timeline.model.temporal_target import TargetSemantic
from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.temporal_target_anomaly import TemporalTargetAnomalyType


class PositionProvenance(str, Enum):
    MIXED = "MIXED"
    GRAMPS = "GRAMPS"
    INFERENCE = "INFERENCE"


@dataclass(frozen=True, slots=True)
class TemporalPositionQualification:
    value: date
    provenance: PositionProvenance
    contributing_bounds: tuple[ReconciledBound, ...]


def should_show_inference_indicator(qualification: TemporalPositionQualification) -> bool:
    """Request an indicator only for demonstrated inferred contributions."""
    if qualification.provenance is PositionProvenance.INFERENCE:
        return True
    if qualification.provenance is PositionProvenance.GRAMPS:
        return False
    if qualification.provenance is PositionProvenance.MIXED:
        return True
    raise NotImplementedError("this position provenance decision is not supported yet")


def qualify_display_position(result: TemporalInferenceResult) -> TemporalPositionQualification:
    """Qualify supported exact representatives and BIRTH maxima.

    The estimator's exact-domain rule requires both principal bounds. Preserve
    those contributions rather than using the domain-wide indicator request.
    Other selection rules are deliberately not supported yet.
    """
    minimum = result.reconciled_domain.principal_minimum
    maximum = result.reconciled_domain.principal_maximum
    representative = result.estimate.representative_value
    if (
        result.target_entry.target.semantic == TargetSemantic.BIRTH
        and representative is not None
        and minimum is not None
        and maximum is not None
        and minimum.value == maximum.value == representative
        and minimum.origin is ReconciledBoundOrigin.INFERENCE
        and maximum.origin is ReconciledBoundOrigin.INFERENCE
    ):
        return TemporalPositionQualification(
            value=determine_display_value(result),
            provenance=PositionProvenance.INFERENCE,
            contributing_bounds=(minimum, maximum),
        )
    if (
        result.target_entry.target.semantic == TargetSemantic.BIRTH
        and representative is not None
        and minimum is not None
        and maximum is not None
        and minimum.value == maximum.value == representative
        and minimum.origin is ReconciledBoundOrigin.GRAMPS
        and maximum.origin is ReconciledBoundOrigin.GRAMPS
    ):
        return TemporalPositionQualification(
            value=determine_display_value(result),
            provenance=PositionProvenance.GRAMPS,
            contributing_bounds=(minimum, maximum),
        )
    if (
        representative is not None
        and minimum is not None
        and maximum is not None
        and minimum.value == maximum.value == representative
        and {minimum.origin, maximum.origin} == {
            ReconciledBoundOrigin.GRAMPS, ReconciledBoundOrigin.INFERENCE,
        }
    ):
        return TemporalPositionQualification(
            value=determine_display_value(result),
            provenance=PositionProvenance.MIXED,
            contributing_bounds=(minimum, maximum),
        )
    # Without a representative, the BIRTH selection rule uses only the maximum.
    # A minimum present in the domain is not a contribution to this choice.
    if (
        representative is None
        and result.target_entry.target.semantic == TargetSemantic.BIRTH
        and maximum is not None
        and maximum.origin is ReconciledBoundOrigin.GRAMPS
    ):
        return TemporalPositionQualification(
            value=determine_display_value(result),
            provenance=PositionProvenance.GRAMPS,
            contributing_bounds=(maximum,),
        )
    if (
        representative is None
        and result.target_entry.target.semantic == TargetSemantic.BIRTH
        and maximum is not None
        and maximum.origin is ReconciledBoundOrigin.INFERENCE
    ):
        return TemporalPositionQualification(
            value=determine_display_value(result),
            provenance=PositionProvenance.INFERENCE,
            contributing_bounds=(maximum,),
        )
    raise NotImplementedError("this display position selection is not supported yet")


def qualify_accepted_display_position(
    result: TemporalInferenceResult, selected_value: date | None,
) -> TemporalPositionQualification | None:
    """Associate an already accepted BIRTH maximum with its contribution.

    The caller supplies the object returned by the renderable selection. This
    function neither selects again nor rechecks the rendering authorization.
    A missing BIRTH selection has no temporal qualification; None carries no
    reason for the absence. Documentary and inferred maxima are supported.
    """
    if selected_value is None and result.target_entry.target.semantic == TargetSemantic.BIRTH:
        return None
    maximum = result.reconciled_domain.principal_maximum
    if (
        result.target_entry.target.semantic == TargetSemantic.BIRTH
        and result.estimate.representative_value is None
        and maximum is not None
        and maximum.origin in (ReconciledBoundOrigin.GRAMPS, ReconciledBoundOrigin.INFERENCE)
    ):
        # The BIRTH selection rule returns this bound's value object directly.
        # Identity checks coherence; provenance comes from the selected bound.
        if selected_value is not maximum.value:
            raise ValueError("selected_value must be the accepted BIRTH maximum value object")
        return TemporalPositionQualification(
            value=selected_value,
            provenance=(
                PositionProvenance.GRAMPS
                if maximum.origin is ReconciledBoundOrigin.GRAMPS
                else PositionProvenance.INFERENCE
            ),
            contributing_bounds=(maximum,),
        )
    raise NotImplementedError("only accepted BIRTH maxima without a representative are supported yet")


def determine_renderable_display_value(
    result: TemporalInferenceResult,
    *,
    future_event_ids: frozenset[str] = frozenset(),
    data: RawGenealogyData | None = None,
) -> date | None:
    if any(
        anomaly.anomaly_type is TemporalTargetAnomalyType.FUTURE_EVENT
        for anomaly in result.target_entry.anomalies
    ):
        return None
    if (
        future_event_ids
        and result.estimate.representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.DEATH
    ):
        minimum = result.reconciled_domain.principal_minimum
        if minimum is not None and not has_independent_bound_justification(
            minimum, future_event_ids, data=data, result=result,
        ):
            return None
    if (
        future_event_ids
        and result.estimate.representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.BIRTH
    ):
        maximum = result.reconciled_domain.principal_maximum
        if maximum is not None and not has_independent_bound_justification(
            maximum, future_event_ids, data=data, result=result,
        ):
            return None
    if (
        future_event_ids
        and result.estimate.representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.MARRIAGE
        and result.reconciled_domain.principal_maximum is None
    ):
        minimum = result.reconciled_domain.principal_minimum
        if minimum is not None and not has_independent_bound_justification(
            minimum, future_event_ids, data=data, result=result,
        ):
            return None
    if (
        future_event_ids
        and result.estimate.representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.MARRIAGE
        and result.reconciled_domain.principal_minimum is None
    ):
        maximum = result.reconciled_domain.principal_maximum
        if maximum is not None and not has_independent_bound_justification(
            maximum, future_event_ids, data=data, result=result,
        ):
            return None
    if (
        future_event_ids
        and result.estimate.representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.MARRIAGE
        and result.reconciled_domain.principal_minimum is not None
        and result.reconciled_domain.principal_maximum is not None
    ):
        minimum = result.reconciled_domain.principal_minimum
        maximum = result.reconciled_domain.principal_maximum
        if not has_independent_bound_justification(
            minimum, future_event_ids, data=data, result=result,
        ):
            return None
        if not has_independent_bound_justification(
            maximum, future_event_ids, data=data, result=result,
        ):
            return None
    if future_event_ids and result.estimate.representative_value is not None:
        minimum = result.reconciled_domain.principal_minimum
        maximum = result.reconciled_domain.principal_maximum
        if (
            minimum is not None
            and maximum is not None
            and minimum.value == maximum.value == result.estimate.representative_value
        ):
            if not has_independent_bound_justification(
                minimum, future_event_ids, data=data, result=result,
            ):
                return None
            if not has_independent_bound_justification(
                maximum, future_event_ids, data=data, result=result,
            ):
                return None
        # Les estimations hors d'un domaine exact correspondant restent non résolues.
    return determine_display_value(result)


def determine_display_value(result: TemporalInferenceResult) -> date | None:
    representative_value = result.estimate.representative_value
    if isinstance(representative_value, date):
        return representative_value

    if (
        representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.BIRTH
    ):
        maximum = result.reconciled_domain.principal_maximum
        if maximum is not None:
            return maximum.value

    if (
        representative_value is None
        and result.target_entry.target.semantic == TargetSemantic.DEATH
    ):
        minimum = result.reconciled_domain.principal_minimum
        if minimum is not None:
            return minimum.value

    if (
        representative_value is None
        and result.target_entry.target.semantic in (
            TargetSemantic.MARRIAGE,
            TargetSemantic.DIVORCE,
        )
    ):
        minimum = result.reconciled_domain.principal_minimum
        maximum = result.reconciled_domain.principal_maximum
        if minimum is not None and maximum is not None:
            return minimum.value + (maximum.value - minimum.value) // 2
        if minimum is not None and maximum is None:
            return minimum.value
        if minimum is None and maximum is not None:
            return maximum.value
