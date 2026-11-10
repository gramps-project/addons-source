"""Index des cibles temporelles reconnues dans la généalogie."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from descendants_timeline.model.temporal_target import TemporalTarget
from descendants_timeline.model.temporal_target_entry import TemporalTargetEntry


@dataclass(frozen=True, slots=True)
class TemporalTargetIndex:
    """Index immuable des états initiaux des cibles temporelles.

    Chaque TemporalTarget est associé à son TemporalTargetEntry.

    L'index ne construit pas les cibles, ne détecte pas les anomalies
    et n'effectue aucune inférence. Il garantit uniquement la cohérence
    et l'immutabilité de l'association target -> entry.
    """

    entries: Mapping[TemporalTarget, TemporalTargetEntry]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Mapping):
            raise TypeError("entries doit être un Mapping.")

        copied_entries = dict(self.entries)

        for target, entry in copied_entries.items():
            if not isinstance(target, TemporalTarget):
                raise TypeError(
                    "Chaque clé de entries doit être un TemporalTarget."
                )

            if not isinstance(entry, TemporalTargetEntry):
                raise TypeError(
                    "Chaque valeur de entries doit être un TemporalTargetEntry."
                )

            if target != entry.target:
                raise ValueError(
                    "Chaque clé de entries doit correspondre à entry.target."
                )

        object.__setattr__(
            self,
            "entries",
            MappingProxyType(copied_entries),
        )

    def get(
        self,
        target: TemporalTarget,
    ) -> TemporalTargetEntry | None:
        """Retourne l'entrée associée à target, ou None si la cible n'existe pas."""

        if not isinstance(target, TemporalTarget):
            raise TypeError("target doit être un TemporalTarget.")

        return self.entries.get(target)