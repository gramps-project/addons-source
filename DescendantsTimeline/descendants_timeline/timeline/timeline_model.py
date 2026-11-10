"""Modèle consolidé destiné à la construction de la timeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.event_date_diagnostic import EventDateDiagnostic
from descendants_timeline.model.temporal_target import TemporalTarget
from descendants_timeline.inference.temporal_inference_result import (
    TemporalInferenceResult,
)
from descendants_timeline.traversal.descendance_traversal import (
    TraversalResult,
)
from descendants_timeline.model.temporal_target import (
    TemporalOwnerType,
    TemporalTarget,
)

from types import MappingProxyType
from descendants_timeline.inference.temporal_target_index_builder import selected_gramps_event_id
from descendants_timeline.temporal_bound_qualification import (
    TemporalDomainQualification,
    qualify_graphical_domain,
)

@dataclass(frozen=True, slots=True)
class TimelineModel:
    """Données consolidées nécessaires à la future mise en page."""

    data: RawGenealogyData
    traversal: TraversalResult
    temporal_results: Mapping[
        TemporalTarget,
        TemporalInferenceResult,
    ]
    event_date_diagnostics: Mapping[str, EventDateDiagnostic] = field(default_factory=dict)
    graphical_qualifications: Mapping[TemporalTarget, TemporalDomainQualification] = field(
        init=False, repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.data, RawGenealogyData):
            raise TypeError(
                "data must be a RawGenealogyData"
            )

        if not isinstance(self.traversal, TraversalResult):
            raise TypeError(
                "traversal must be a TraversalResult"
            )

        if not isinstance(self.temporal_results, Mapping):
            raise TypeError(
                "temporal_results must be a Mapping"
            )

        if not all(
            isinstance(target, TemporalTarget)
            for target in self.temporal_results
        ):
            raise TypeError(
                "temporal_results keys must be TemporalTarget objects"
            )
        if not all(
            isinstance(result, TemporalInferenceResult)
            for result in self.temporal_results.values()
        ):
            raise TypeError(
                "temporal_results values must be "
                "TemporalInferenceResult objects"
            )
        for target, result in self.temporal_results.items():
            if target != result.target_entry.target:
                raise ValueError(
                    "temporal_results key must match result target"
                )

            if (
                target.owner_type is TemporalOwnerType.PERSON
                and target.owner_id not in self.data.persons
            ):
                raise ValueError(
                    "temporal target person owner must exist in data"
                )
            if (
                target.owner_type is TemporalOwnerType.FAMILY
                and target.owner_id not in self.data.families
            ):
                raise ValueError(
                    "temporal target family owner must exist in data"
                )
        object.__setattr__(
            self,
            "temporal_results",
            MappingProxyType(dict(self.temporal_results)),
        )
        object.__setattr__(
            self,
            "event_date_diagnostics",
            MappingProxyType(dict(self.event_date_diagnostics)),
        )
        qualifications = {}
        for target, result in self.temporal_results.items():
            event_id = selected_gramps_event_id(self.data, target)
            document = self.data.events[event_id].date_document if event_id is not None else None
            qualifications[target] = qualify_graphical_domain(
                result.reconciled_domain, date_document=document,
            )
        object.__setattr__(
            self,
            "graphical_qualifications",
            MappingProxyType(qualifications),
        )
