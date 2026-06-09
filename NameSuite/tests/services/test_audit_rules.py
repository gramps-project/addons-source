from NameSuite.name_processor.services.audit_rules.gender_mismatch import ErrGenderMismatch
from NameSuite.name_processor.services.audit_rules.missing_patronymic import InfoMissingPatronymic
from NameSuite.name_processor.models.audit import RuleContext
from NameSuite.name_processor.models.person import Gender


def test_gender_mismatch_rule():
    rule = ErrGenderMismatch()
    ctx = RuleContext(
        person_handle="h1",
        gramps_id="I0001",
        display_name="Test",
        gender=Gender.MALE,
        current_patronymic="Ивановна",  # Incorrect suffix
        father_given_name="Иван",
        reference_year=2000,
        locale="ru",
    )

    change = rule.evaluate(ctx, use_pre_reform=False)
    assert change is not None
    assert "Иванович" in change.suggested_string


def test_missing_patronymic_rule_has_patronymic():
    rule = InfoMissingPatronymic()
    ctx = RuleContext(
        person_handle="h1",
        gramps_id="I0001",
        display_name="Test",
        gender=Gender.MALE,
        current_patronymic="Иванович",
        father_given_name="Иван",
        reference_year=2000,
        locale="ru",
    )
    change = rule.evaluate(ctx, use_pre_reform=False)
    assert change is None


def test_missing_patronymic_rule_no_father():
    rule = InfoMissingPatronymic()
    ctx = RuleContext(
        person_handle="h1",
        gramps_id="I0001",
        display_name="Test",
        gender=Gender.MALE,
        current_patronymic="",
        father_given_name="",
        reference_year=2000,
        locale="ru",
    )
    change = rule.evaluate(ctx, use_pre_reform=False)
    assert change is None


def test_missing_patronymic_rule_unknown_gender():
    rule = InfoMissingPatronymic()
    ctx = RuleContext(
        person_handle="h1",
        gramps_id="I0001",
        display_name="Test",
        gender=Gender.UNKNOWN,
        current_patronymic="",
        father_given_name="Иван",
        reference_year=2000,
        locale="ru",
    )
    change = rule.evaluate(ctx, use_pre_reform=False)
    assert change is None


def test_missing_patronymic_rule_suggests_male():
    rule = InfoMissingPatronymic()
    ctx = RuleContext(
        person_handle="h1",
        gramps_id="I0001",
        display_name="Test",
        gender=Gender.MALE,
        current_patronymic="",
        father_given_name="Иван",
        reference_year=2000,
        locale="ru",
    )
    change = rule.evaluate(ctx, use_pre_reform=False)
    assert change is not None
    assert change.suggested_string == "Иванович"


def test_missing_patronymic_rule_suggests_female():
    rule = InfoMissingPatronymic()
    ctx = RuleContext(
        person_handle="h1",
        gramps_id="I0001",
        display_name="Test",
        gender=Gender.FEMALE,
        current_patronymic="",
        father_given_name="Иван",
        reference_year=2000,
        locale="ru",
    )
    change = rule.evaluate(ctx, use_pre_reform=False)
    assert change is not None
    assert change.suggested_string == "Ивановна"
