from dataclasses import dataclass
from enum import Enum
import re


class MatchMode(Enum):
    EXACT = "exact"
    SUBSTRING = "substring"
    REGEX = "regex"


class AltAction(Enum):
    PRESERVE = "Preserve"
    OVERWRITE = "Overwrite"


@dataclass
class RenameConfig:
    """Stores and validates user-defined replacement rules."""

    mode: MatchMode
    source: str
    target: str
    pattern: re.Pattern | None = None
    is_valid: bool = True
    error_msg: str = ""


@dataclass
class ProposedRename:
    """DTO representing a single proposed name change for the UI grid."""

    handle: str
    gramps_id: str
    display_name: str
    original_given_name: str
    proposed_given_name: str
    alt_action: str = AltAction.OVERWRITE.value
    matched_text: str = ""  # Text that was matched and replaced (for highlighting)
