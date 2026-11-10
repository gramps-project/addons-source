from .event import EventSemantic


def is_event_date_modifier_compatible(
    semantic: EventSemantic,
    modifier_code: int,
) -> bool:
    if semantic in (
        EventSemantic.BIRTH,
        EventSemantic.DEATH,
        EventSemantic.MARRIAGE,
        EventSemantic.BURIAL,
        EventSemantic.DIVORCE,
        EventSemantic.BAPTISM,
        EventSemantic.CENSUS,
    ):
        if modifier_code in (0, 1, 2, 3, 4, 6):
            return True
        if modifier_code in (5, 7, 8):
            return False
    raise NotImplementedError
