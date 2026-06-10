#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from typing import TYPE_CHECKING

from name_processor.models.infer import (
    PatronymicInferenceStatus,
    ProposedPatronymic,
)
from name_processor.models.person import Gender
from name_processor.protocols.patronymic import PatronymicSubject
from name_processor.services.morphology import MorphologyService

if TYPE_CHECKING:
    from name_processor.repositories.gramps_read import GrampsReadRepository
    from name_processor.services.confidence import ConfidenceService
    from name_processor.services.chronology import ChronologyService


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
