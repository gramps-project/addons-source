"""Construction du modèle consolidé de timeline."""

from __future__ import annotations

from descendants_timeline.inference.temporal_inference_result import (
    TemporalInferenceResult,
)
from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.event import EventSemantic
from descendants_timeline.model.event_date_diagnostic import evaluate_event_date_modifier
from descendants_timeline.timeline.timeline_model import TimelineModel
from descendants_timeline.traversal.descendance_traversal import (
    TraversalResult,
)


class TimelineModelBuilder:
    """Construit un TimelineModel à partir des résultats déjà calculés."""

    def build(
        self,
        data: RawGenealogyData,
        traversal: TraversalResult,
        temporal_results: tuple[TemporalInferenceResult, ...],
    ) -> TimelineModel:
        if not isinstance(temporal_results, tuple):
            raise TypeError(
                "temporal_results must be a tuple"
            )

        results_by_target = {}

        for result in temporal_results:
            target = result.target_entry.target

            if target in results_by_target:
                raise ValueError(
                    "duplicate temporal target"
                )

            results_by_target[target] = result

        event_date_diagnostics = {}
        for event in data.events.values():
            if event.date_document is None or event.semantic is EventSemantic.UNKNOWN:
                continue
            diagnostic = evaluate_event_date_modifier(
                event.semantic,
                event.date_document.modifier_code,
            )
            if diagnostic is not None:
                event_date_diagnostics[event.event_id] = diagnostic

        return TimelineModel(
            data=data,
            traversal=traversal,
            temporal_results=results_by_target,
            event_date_diagnostics=event_date_diagnostics,
        )
