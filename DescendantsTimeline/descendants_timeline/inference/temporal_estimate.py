from dataclasses import dataclass
from datetime import date

from descendants_timeline.model.temporal import CertaintyLevel


@dataclass(frozen=True, slots=True)
class TemporalEstimate:
    representative_value: date | None
    certainty: CertaintyLevel

    def __post_init__(self) -> None:
        if (
            self.representative_value is not None
            and not isinstance(self.representative_value, date)
        ):
            raise TypeError(
                "representative_value must be a date or None"
            )

        if not isinstance(self.certainty, CertaintyLevel):
            raise TypeError(
                "certainty must be a CertaintyLevel"
            )

        if self.representative_value is None:
            if self.certainty != CertaintyLevel.UNDETERMINED:
                raise ValueError(
                    "certainty must be UNDETERMINED "
                    "when representative_value is None"
                )