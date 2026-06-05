from enum import Enum
from dataclasses import dataclass


class PatronymicInferenceStatus(Enum):
    """Status codes for patronymic inference."""

    SUCCESS = "SUCCESS"
    NO_ACTIVE_PERSON = "NO_ACTIVE_PERSON"
    NO_FATHER = "NO_FATHER"
    FATHER_NO_NAME = "FATHER_NO_NAME"
    NON_BINARY = "NON_BINARY"
    ALREADY_HAS_PATRONYMIC = "ALREADY_HAS_PATRONYMIC"
    MORPHOLOGY_FAIL = "MORPHOLOGY_FAIL"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class ProposedPatronymic:
    """Result of inferring a patronymic for a single person."""

    status: PatronymicInferenceStatus = PatronymicInferenceStatus.UNKNOWN_ERROR
    patronymic: str | None = None
    father_name: str | None = None
    confidence: float | None = None
