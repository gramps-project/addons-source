from dataclasses import dataclass

from descendants_timeline.model.temporal_target import TemporalTarget


@dataclass(frozen=True)
class DiagnosticPlacement:
    target: TemporalTarget
    x: float
    y: float
