from descendants_timeline.model.child_ref import ChildRef, ChildRelation
from descendants_timeline.model.event import Event, EventSemantic
from descendants_timeline.model.family import Family
from descendants_timeline.model.family_event_ref import FamilyEventRef, FamilyRoleSemantic
from descendants_timeline.model.gramps_date_document import GrampsDateDocument
from descendants_timeline.model.person import Person, PersonGender
from descendants_timeline.model.person_event_ref import EventRoleSemantic, PersonEventRef


def convert_date_document(date_object):
    if date_object is None:
        return None

    raw_newyear = date_object.newyear
    newyear_was_list = isinstance(raw_newyear, list)

    return GrampsDateDocument(
        calendar_code=date_object.calendar,
        modifier_code=date_object.modifier,
        quality_code=date_object.quality,
        dateval=date_object.dateval,
        text=date_object.text,
        newyear=(
            tuple(raw_newyear)
            if newyear_was_list
            else raw_newyear
        ),
        newyear_was_list=newyear_was_list,
    )


def convert_date_raw_newyear(date_object):
    return date_object.newyear


def convert_date_raw_dateval(date_object):
    return date_object.dateval


def convert_date_stop_date(date_object):
    return date_object.get_stop_date()


def convert_date_start_date(date_object):
    return date_object.get_start_date()


def convert_date_new_year(date_object):
    return date_object.get_new_year()


def convert_date_slash2(date_object):
    return date_object.get_slash2()


def convert_date_slash(date_object):
    return date_object.get_slash()


def convert_date_day_valid(date_object):
    return date_object.get_day_valid()


def convert_date_month_valid(date_object):
    return date_object.get_month_valid()


def convert_date_year_valid(date_object):
    return date_object.get_year_valid()


def convert_date_is_full(date_object):
    return date_object.is_full()


def convert_date_is_empty(date_object):
    return date_object.is_empty()


def convert_date_text(date_object):
    return date_object.get_text()


def convert_date_stop_ymd(date_object):
    return date_object.get_stop_ymd()


def convert_date_start_ymd(date_object):
    return date_object.get_ymd()


def convert_date_modifier_code(date_object):
    return date_object.get_modifier()


def convert_date_quality_code(date_object):
    return date_object.get_quality()


def convert_date_calendar_code(date_object):
    return date_object.get_calendar()


def convert_event(event, temporal_value):
    return Event(
        event_id=convert_event_handle(event),
        source_type=convert_event_source_type(event.type),
        semantic=convert_event_semantic(event.type),
        date=temporal_value,
        date_document=convert_date_document(convert_event_date_object(event)),
    )


def convert_event_date_object(event):
    return event.date


def convert_event_semantic(event_type):
    code = int(event_type)
    if code == 12:
        return EventSemantic.BIRTH
    if code == 15:
        return EventSemantic.BAPTISM
    if code == 1:
        return EventSemantic.MARRIAGE
    if code == 7:
        return EventSemantic.DIVORCE
    if code == 21:
        return EventSemantic.CENSUS
    if code == 13:
        return EventSemantic.DEATH
    if code == 19:
        return EventSemantic.BURIAL
    return EventSemantic.UNKNOWN


def convert_event_source_type(event_type):
    return event_type.xml_str()


def convert_event_handle(event):
    return event.get_handle()


def convert_family(family):
    return Family(
        family_id=convert_family_handle(family),
        parent1_id=convert_family_parent1_id(family),
        parent2_id=convert_family_parent2_id(family),
        event_refs=convert_family_event_refs(family),
        child_refs=convert_family_child_refs(family),
    )


def convert_family_handle(family):
    return family.get_handle()


def convert_family_event_refs(family):
    return tuple(
        convert_family_event_ref(event_ref)
        for event_ref in family.get_event_ref_list()
    )


def convert_family_event_ref(event_ref):
    event_id = convert_family_event_ref_handle(event_ref)
    role = event_ref.get_role()
    return FamilyEventRef(
        event_id=event_id,
        semantic_role=convert_family_event_role_semantic(role),
        source_role=convert_family_event_source_role(role),
    )


def convert_family_event_source_role(role):
    return role.xml_str()


def convert_family_event_role_semantic(role):
    role_code = int(role)
    if role_code == 8:
        return FamilyRoleSemantic.FAMILY
    return FamilyRoleSemantic.UNKNOWN


def convert_family_event_ref_handle(event_ref):
    return event_ref.get_reference_handle()


def convert_family_child_refs(family):
    return tuple(
        convert_family_child_ref(child_ref)
        for child_ref in family.get_child_ref_list()
    )


def convert_family_child_ref(child_ref):
    parent1 = convert_family_child_relation_to_parent1(child_ref)
    parent2 = convert_family_child_relation_to_parent2(child_ref)
    return ChildRef(
        person_id=convert_family_child_ref_handle(child_ref),
        relation_to_parent1=parent1,
        relation_to_parent2=parent2,
        custom_relation_to_parent1=(
            child_ref.get_father_relation().xml_str() if parent1 is ChildRelation.CUSTOM else None
        ),
        custom_relation_to_parent2=(
            child_ref.get_mother_relation().xml_str() if parent2 is ChildRelation.CUSTOM else None
        ),
    )


def convert_family_child_relation_to_parent2(child_ref):
    return convert_family_child_relation(
        child_ref.get_mother_relation()
    )


def convert_family_child_relation_to_parent1(child_ref):
    return convert_family_child_relation(
        child_ref.get_father_relation()
    )


def convert_family_child_relation(relation):
    relation_code = int(relation)
    if relation_code == 7:
        return ChildRelation.CUSTOM
    if relation_code == 0:
        return ChildRelation.NONE
    if relation_code == 1:
        return ChildRelation.BIRTH
    if relation_code == 2:
        return ChildRelation.ADOPTED
    if relation_code == 3:
        return ChildRelation.STEPCHILD
    if relation_code == 4:
        return ChildRelation.SPONSORED
    if relation_code == 5:
        return ChildRelation.FOSTER
    if relation_code == 6:
        return ChildRelation.UNKNOWN
    raise ValueError(f"unsupported Gramps child relation code: {relation_code}")


def convert_family_child_ref_handle(child_ref):
    return child_ref.get_reference_handle()


def convert_family_parent2_id(family):
    return family.get_mother_handle()


def convert_family_parent1_id(family):
    return family.get_father_handle()


def convert_person(person, name_formatter):
    return Person(
        person_id=convert_person_handle(person),
        display_name=convert_person_display_name(
            person,
            name_formatter,
        ),
        gender=convert_person_gender(person),
        event_refs=convert_person_event_refs(person),
        parent_family_ids=convert_person_parent_family_ids(
            person
        ),
        family_ids=convert_person_family_ids(person),
    )


def convert_person_event_refs(person):
    return tuple(
        convert_person_event_ref(event_ref)
        for event_ref in person.get_event_ref_list()
    )


def convert_person_event_ref(event_ref):
    role = event_ref.get_role()
    return PersonEventRef(
        event_id=convert_person_event_ref_handle(event_ref),
        semantic_role=convert_person_event_role_semantic(role),
        source_role=convert_person_event_source_role(role),
    )


def convert_person_event_source_role(role):
    return role.xml_str()


def convert_person_event_role_semantic(role):
    role_code = int(role)
    if role_code == 1:
        return EventRoleSemantic.PRINCIPAL
    if role_code == 7:
        return EventRoleSemantic.WITNESS
    if role_code == 9:
        return EventRoleSemantic.INFORMANT
    return EventRoleSemantic.UNKNOWN


def convert_person_event_ref_handle(event_ref):
    return event_ref.get_reference_handle()


def convert_person_parent_family_ids(person):
    return tuple(person.get_parent_family_handle_list())


def convert_person_family_ids(person):
    return tuple(person.get_family_handle_list())


def convert_person_display_name(person, name_formatter):
    display_name = name_formatter(person)
    if not display_name.strip():
        get_gramps_id = getattr(person, "get_gramps_id", None)
        gramps_id = get_gramps_id() if get_gramps_id is not None else None
        if gramps_id and gramps_id.strip():
            return f"[{gramps_id}]"
        raise ValueError("empty Gramps display name")
    return display_name


def convert_person_handle(person):
    return person.get_handle()


def convert_person_gender(person):
    gender_code = person.get_gender()
    if gender_code == 1:
        return PersonGender.MALE
    if gender_code == 0:
        return PersonGender.FEMALE
    if gender_code == 2:
        return PersonGender.UNKNOWN
    if gender_code == 3:
        return PersonGender.OTHER
    raise ValueError("unsupported Gramps gender code")
