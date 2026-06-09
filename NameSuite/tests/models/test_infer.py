from NameSuite.name_processor.models.infer import PatronymicInferenceStatus, ProposedPatronymic


def test_patronymic_inference_status_enum():
    assert PatronymicInferenceStatus.SUCCESS.value == "SUCCESS"
    assert PatronymicInferenceStatus.NO_ACTIVE_PERSON.value == "NO_ACTIVE_PERSON"
    assert PatronymicInferenceStatus.MORPHOLOGY_FAIL.value == "MORPHOLOGY_FAIL"


def test_proposed_patronymic_dataclass_defaults():
    res = ProposedPatronymic()
    assert res.patronymic is None
    assert res.father_name is None
    assert res.status == PatronymicInferenceStatus.UNKNOWN_ERROR


def test_proposed_patronymic_dataclass_assignment():
    res = ProposedPatronymic(
        patronymic="Petrovich",
        father_name="Petr",
        status=PatronymicInferenceStatus.SUCCESS,
    )
    assert res.patronymic == "Petrovich"
    assert res.father_name == "Petr"
    assert res.status == PatronymicInferenceStatus.SUCCESS
