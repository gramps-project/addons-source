"""Orchestration du moteur d'inférence temporelle."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date

from descendants_timeline.cooperative_steps import complete
from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.family_event_ref import FamilyRoleSemantic
from descendants_timeline.model.person_event_ref import EventRoleSemantic
from descendants_timeline.model.temporal import ValueOrigin
from descendants_timeline.model.temporal_target import TargetSemantic
from descendants_timeline.model.temporal_target_anomaly import (
    TemporalTargetAnomaly,
    TemporalTargetAnomalyType,
)
from descendants_timeline.model.genealogy import RawGenealogyData


from descendants_timeline.inference.temporal_inference_result import (
    TemporalInferenceResult,
)
from descendants_timeline.inference.temporal_target_index_builder import (
    TemporalTargetIndexBuilder,
)
from descendants_timeline.inference.constraint_resolver import (
    ConstraintResolver,
)
from descendants_timeline.inference.temporal_reconciler import (
    TemporalReconciler,
)
from descendants_timeline.inference.temporal_estimator import (
    TemporalEstimator,
)
from descendants_timeline.inference.temporal_evidence_builder import (
    TemporalEvidenceBuilder,
)
from descendants_timeline.inference.rule_context import (
    RuleContext,
)
from descendants_timeline.inference.rule_engine import (
    RuleEngine,
)
from descendants_timeline.inference.default_rules import (
    default_rules,
)
from dataclasses import dataclass, field, replace

@dataclass(frozen=True, slots=True)
class TemporalInferenceEngine:
    """Orchestre le pipeline complet d'inférence temporelle."""

    rule_engine: RuleEngine = field(
        default_factory=lambda: RuleEngine(
            rules=default_rules()
        )
    )

    def __post_init__(self) -> None:
        if not isinstance(self.rule_engine, RuleEngine):
            raise TypeError(
                "rule_engine must be a RuleEngine"
            )


    def run(
        self,
        data: RawGenealogyData,
        reference_date: date | None = None,
        *, diagnostics=None,
    ) -> tuple[TemporalInferenceResult, ...]:
        return complete(self._iter_run(data, reference_date, diagnostics=diagnostics))

    def _iter_run(self, data, reference_date=None, *, diagnostics=None):
        with (
            diagnostics.phase("inference")
            if diagnostics is not None
            else nullcontext()
        ):
            if not isinstance(data, RawGenealogyData):
                raise TypeError(
                    "data must be a RawGenealogyData"
                )

            target_index = TemporalTargetIndexBuilder().build(data)
            evidences = TemporalEvidenceBuilder().build(data)
            if diagnostics is not None:
                diagnostics.increment("temporal_targets", len(target_index.entries))
                diagnostics.increment("temporal_evidences", len(evidences))

            context = RuleContext(
                data=data,
                evidences=evidences,
            )

            resolver = ConstraintResolver()
            reconciler = TemporalReconciler()
            estimator = TemporalEstimator()

            results: list[TemporalInferenceResult] = []

            yield None
            for target_entry in target_index.entries.values():
                constraints = self.rule_engine.evaluate(
                    target_entry.target,
                    context,
                )

                constraint_resolution = resolver.resolve(
                    target_entry.target,
                    constraints,
                )

                reconciled_domain = reconciler.reconcile(
                    target_entry.target,
                    target_entry.gramps_value,
                    constraint_resolution,
                )

                estimate = estimator.estimate(
                    reconciled_domain
                )

                if (
                    reference_date is not None
                    and target_entry.target.semantic in (
                        TargetSemantic.BIRTH, TargetSemantic.DEATH, TargetSemantic.MARRIAGE,
                        TargetSemantic.DIVORCE,
                    )
                    and target_entry.gramps_value.value_origin is ValueOrigin.GRAMPS
                    and target_entry.gramps_value.is_exact
                    and target_entry.gramps_value.normalized_minimum > reference_date
                ):
                    if target_entry.target.semantic in (TargetSemantic.MARRIAGE, TargetSemantic.DIVORCE):
                        event_semantic = (
                            EventSemantic.MARRIAGE
                            if target_entry.target.semantic is TargetSemantic.MARRIAGE
                            else EventSemantic.DIVORCE
                        )
                        event_ids = tuple(
                            ref.event_id
                            for ref in data.families[target_entry.target.owner_id].event_refs
                            if ref.semantic_role is FamilyRoleSemantic.FAMILY
                            and data.events[ref.event_id].semantic is event_semantic
                        )
                    else:
                        event_semantic = (
                            EventSemantic.BIRTH
                            if target_entry.target.semantic is TargetSemantic.BIRTH
                            else EventSemantic.DEATH
                        )
                        event_ids = tuple(
                            ref.event_id
                            for ref in data.persons[target_entry.target.owner_id].event_refs
                            if ref.semantic_role is EventRoleSemantic.PRINCIPAL
                            and data.events[ref.event_id].semantic is event_semantic
                        )
                    target_entry = replace(
                        target_entry,
                        anomalies=target_entry.anomalies + (
                            TemporalTargetAnomaly(
                                anomaly_type=TemporalTargetAnomalyType.FUTURE_EVENT,
                                event_ids=event_ids,
                            ),
                        ),
                    )

                results.append(
                    TemporalInferenceResult(
                        target_entry=target_entry,
                        constraints=constraints,
                        constraint_resolution=constraint_resolution,
                        reconciled_domain=reconciled_domain,
                        estimate=estimate,
                    )
                )

                yield None

            return tuple(results)
