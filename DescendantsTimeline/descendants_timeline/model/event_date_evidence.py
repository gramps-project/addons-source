from .event import EventSemantic
from .event_date_compatibility import is_event_date_modifier_compatible


def is_event_date_modifier_admissible_as_evidence(
    semantic: EventSemantic,
    modifier_code: int,
) -> bool:
    """Évalue uniquement l'absence d'exclusion liée au modificateur documentaire."""
    return is_event_date_modifier_compatible(semantic, modifier_code)
