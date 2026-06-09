# -*- coding: utf-8 -*-
"""
Confidence scoring engine for patronymic candidates.
Encapsulates heuristics used to determine reliability of inference results.
"""

import re
from typing import TYPE_CHECKING

from NameSuite.name_processor.services.morphology import SLAVIC_SURNAME_PATTERN

if TYPE_CHECKING:
    from NameSuite.name_processor.repositories.gramps_read import GrampsReadRepository
    from NameSuite.name_processor.protocols.confidence import ConfidenceSubject

# Confidence score thresholds
CONFIDENCE_BASE_SCORE = 0.40

CONFIDENCE_SCORE_SIBLING = 0.40
CONFIDENCE_SCORE_SLAVIC_SURNAME = 0.20

PENALTY_MULTI_WORD_FATHER = -0.40
PENALTY_MEDIEVAL_YEAR = -0.30
PENALTY_NON_CYRILLIC = -0.20
PENALTY_UNCERTAIN_FATHER = -0.50


def has_cyrillic(text: str) -> bool:
    """Returns True if the text contains Cyrillic characters."""
    return bool(re.search(r"[\u0400-\u04FF]", text))


class ConfidenceService:
    """Calculates confidence scores (0.0 to 1.0) for patronymic inferences."""

    def __init__(self, repository: "GrampsReadRepository") -> None:
        self._repository = repository

    def calculate(
        self,
        person: "ConfidenceSubject",
        father: "ConfidenceSubject | None",
        ref_year: int | None,
    ) -> float:
        """
        Multi-Signal Applicability Engine.
        Calculates a score between 0.0 and 1.0 based on available heuristics.
        """
        # Starting from a non-zero baseline because a successful morphological inference
        # is already a strong positive indicator.
        score = CONFIDENCE_BASE_SCORE

        # Positive Signals
        # 1. Sibling has matching patronymic (+0.40)
        for sib_handle in person.siblings_handles:
            sib = self._repository.get_person_proxy(sib_handle)
            if sib and sib.has_patronymic:
                score += CONFIDENCE_SCORE_SIBLING
                break

        # 2. Parent surname has Slavic suffix (+0.20)
        surnames_to_check = father.surnames if father else person.surnames
        if any(SLAVIC_SURNAME_PATTERN.search(s) for s in surnames_to_check):
            score += CONFIDENCE_SCORE_SLAVIC_SURNAME

        # Negative Signals
        # 1. Absence of Cyrillic Characters (-0.20)
        if not has_cyrillic(person.display_name):
            score += PENALTY_NON_CYRILLIC

        if father and father.given_name:
            # 2. Ambiguous multi-word father's name (-0.40)
            if re.search(r"[\s\-]", father.given_name.strip()):
                score += PENALTY_MULTI_WORD_FATHER

            # 3. Uncertain father's name (e.g. contains brackets or question marks) (-0.50)
            if re.search(r"[\?\[\]\(\)]", father.given_name):
                score += PENALTY_UNCERTAIN_FATHER

        # 4. Reference Year is Medieval (<1500) (-0.30)
        if ref_year is not None and ref_year < 1500:
            score += PENALTY_MEDIEVAL_YEAR

        return max(0.0, min(score, 1.0))
