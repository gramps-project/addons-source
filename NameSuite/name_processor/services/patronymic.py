from typing import TYPE_CHECKING

from NameSuite.name_processor.models.infer import (
    PatronymicInferenceStatus,
    ProposedPatronymic,
)
from NameSuite.name_processor.models.person import Gender
from NameSuite.name_processor.protocols.patronymic import PatronymicSubject
from NameSuite.name_processor.services.morphology import MorphologyService

if TYPE_CHECKING:
    from NameSuite.name_processor.repositories.gramps_read import GrampsReadRepository
    from NameSuite.name_processor.services.confidence import ConfidenceService
    from NameSuite.name_processor.services.chronology import ChronologyService


class PatronymicInferenceService:
    def __init__(
        self,
        read_repo: "GrampsReadRepository",
        confidence: "ConfidenceService",
        chronology_service: "ChronologyService",
    ):
        self._read_repo = read_repo
        self._confidence_service = confidence
        self._chronology_service = chronology_service

    def infer_patronymic(
        self, person: PatronymicSubject, father: PatronymicSubject | None
    ) -> ProposedPatronymic:
        """
        Generate a patronymic candidate for a single person.
        Handles DB lookups, validation, and morphology generation.
        """
        if not person:
            return ProposedPatronymic(status=PatronymicInferenceStatus.NO_ACTIVE_PERSON)

        if person.gender not in (Gender.MALE, Gender.FEMALE):
            return ProposedPatronymic(status=PatronymicInferenceStatus.NON_BINARY)

        if person.has_patronymic:
            return ProposedPatronymic(
                status=PatronymicInferenceStatus.ALREADY_HAS_PATRONYMIC
            )

        if not father:
            return ProposedPatronymic(status=PatronymicInferenceStatus.NO_FATHER)

        if not father.given_name:
            return ProposedPatronymic(status=PatronymicInferenceStatus.FATHER_NO_NAME)

        ref_year = self._chronology_service.estimate_reference_year(person.handle)

        patronymic = MorphologyService.generate_east_slavic_patronymic(
            father_name=father.given_name,
            is_male=(person.gender == Gender.MALE),
            year=ref_year,
            pre_reform_script=False,
        )

        if patronymic:
            confidence = self._confidence_service.calculate(person, father, ref_year)

            return ProposedPatronymic(
                status=PatronymicInferenceStatus.SUCCESS,
                patronymic=patronymic,
                father_name=father.given_name,
                confidence=confidence,
            )
        else:
            return ProposedPatronymic(status=PatronymicInferenceStatus.MORPHOLOGY_FAIL)
