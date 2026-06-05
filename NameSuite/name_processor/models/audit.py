from dataclasses import dataclass
from enum import Enum

from name_processor.models.person import Gender


class AuditScope(Enum):
    """Filter options for database-wide auditing."""

    ALL = 0
    MALES_ONLY = 1
    FEMALES_ONLY = 2


@dataclass
class RuleContext:
    """A flattened, read-only snapshot of a person for rule evaluation."""

    person_handle: str
    gramps_id: str
    display_name: str
    gender: Gender
    current_patronymic: str
    father_given_name: str | None
    reference_year: int | None
    locale: str


@dataclass(frozen=True)
class ProposedChange:
    """Internal result from an individual rule."""

    explanation: str
    suggested_string: str


@dataclass(frozen=True)
class AuditIssue:
    """The DTO sent to the Controller and displayed in the View."""

    person_handle: str
    gramps_id: str
    display_name: str
    father_name: str | None
    current_value: str
    suggested_fix: str
    confidence: float
    reference_year: str
    rule_id: str
    explanation: str

    # TODO: decide if this is needed
    # Metadata for UI-level filtering and sorting
    severity: str
    is_pre_reform: bool
