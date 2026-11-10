from descendants_timeline.inference.reconciled_temporal_domain import (
    ReconciledBoundOrigin,
    ReconciledTemporalDomain,
)
from descendants_timeline.inference.temporal_estimate import (
    TemporalEstimate,
)
from descendants_timeline.model.temporal import (
    CertaintyLevel,
    EvidenceStatus,
)


class TemporalEstimator:
    def estimate(
        self,
        domain: ReconciledTemporalDomain,
    ) -> TemporalEstimate:
        if not isinstance(domain, ReconciledTemporalDomain):
            raise TypeError(
                "domain must be a ReconciledTemporalDomain"
            )

        minimum = domain.principal_minimum
        maximum = domain.principal_maximum

        # Exact Gramps date supported by usable evidence.
        if (
            minimum is not None
            and maximum is not None
            and minimum.value == maximum.value
            and minimum.origin == ReconciledBoundOrigin.GRAMPS
            and maximum.origin == ReconciledBoundOrigin.GRAMPS
            and domain.gramps_value.evidence_status
            == EvidenceStatus.EVIDENCE_USABLE
        ):
            return TemporalEstimate(
                representative_value=minimum.value,
                certainty=CertaintyLevel.CERTAIN,
            )
        # Any other exact principal domain has a representative value.
        # Its certainty will be refined by a future estimation policy.
        if (
            minimum is not None
            and maximum is not None
            and minimum.value == maximum.value
        ):
            return TemporalEstimate(
                representative_value=minimum.value,
                certainty=CertaintyLevel.UNDETERMINED,
            )

        # No other estimation policy is defined yet.
        return TemporalEstimate(
            representative_value=None,
            certainty=CertaintyLevel.UNDETERMINED,
        )