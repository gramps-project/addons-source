from name_processor.models.person import Person, Gender


def test_gender_enum():
    assert Gender.MALE.value == "MALE"
    assert Gender.FEMALE.value == "FEMALE"
    assert Gender.UNKNOWN.value == "UNKNOWN"


def test_person_dataclass_initialization():
    person = Person(
        handle="h123",
        gramps_id="I0001",
        given_name="Ivan",
        gender=Gender.MALE,
        has_patronymic=False,
        display_name="Ivan Petrovich",
    )

    assert person.handle == "h123"
    assert person.gramps_id == "I0001"
    assert person.given_name == "Ivan"
    assert person.gender == Gender.MALE
    assert person.has_patronymic is False
    assert person.display_name == "Ivan Petrovich"

    # Check default factory fields
    assert person.father_handle is None
    assert person.alternate_first_names == []


def test_person_dataclass_with_optional_fields():
    person = Person(
        handle="h123",
        gramps_id="I0001",
        given_name="Maria",
        gender=Gender.FEMALE,
        has_patronymic=True,
        display_name="Maria Ivanovna",
        father_handle="f456",
        alternate_first_names=["Masha", "Marya"],
    )

    assert person.father_handle == "f456"
    assert person.alternate_first_names == ["Masha", "Marya"]
