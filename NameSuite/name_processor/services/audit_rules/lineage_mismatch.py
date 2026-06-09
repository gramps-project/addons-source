# -*- coding: utf-8 -*-
"""
Rule: ErrLineageMismatch
Flags if the patronymic base/root does not match the linked biological father's name.
"""

from NameSuite.name_processor.services.audit_rules.base import BaseRule
from NameSuite.name_processor.models.audit import RuleContext, ProposedChange
from NameSuite.name_processor.models.constants import SEVERITY_ERROR
from NameSuite.name_processor.models.person import Gender
from NameSuite.name_processor.models.constants import (
    LOCALE_EAST_SLAVIC,
    LOCALE_RU,
    REFORM_YEAR,
)
from NameSuite.name_processor.services.morphology import MorphologyService


class ErrLineageMismatch(BaseRule):
    """Flags if the patronymic base/root does not match the linked biological father's name."""

    rule_id = "ERR_LINEAGE_MISMATCH"

    @property
    def severity(self) -> str:
        return SEVERITY_ERROR

    @property
    def supported_locales(self) -> set[str]:
        return LOCALE_EAST_SLAVIC

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (None, None)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        if not ctx.father_given_name or not ctx.current_patronymic:
            return None

        is_male = ctx.gender == Gender.MALE
        pre_reform = MorphologyService.is_pre_reform(ctx, use_pre_reform)

        # Resolve target expected patronymic for active context
        expected = MorphologyService.generate_east_slavic_patronymic(
            ctx.father_given_name,
            is_male=is_male,
            year=ctx.reference_year,
            pre_reform_script=pre_reform,
        )

        if not expected or ctx.current_patronymic == expected:
            return None

        # Cross-reference pre-1918 and post-1918 variant states to avoid flagging anachronisms as lineage mismatch
        expected_modern = MorphologyService.generate_east_slavic_patronymic(
            ctx.father_given_name,
            is_male=is_male,
            year=REFORM_YEAR + 10,
            pre_reform_script=False,
        )
        expected_archaic = MorphologyService.generate_east_slavic_patronymic(
            ctx.father_given_name,
            is_male=is_male,
            year=REFORM_YEAR - 10,
            pre_reform_script=(ctx.locale == LOCALE_RU),
        )

        opposite_modern = MorphologyService.generate_east_slavic_patronymic(
            ctx.father_given_name,
            is_male=not is_male,
            year=REFORM_YEAR + 10,
            pre_reform_script=False,
        )
        opposite_archaic = MorphologyService.generate_east_slavic_patronymic(
            ctx.father_given_name,
            is_male=not is_male,
            year=REFORM_YEAR - 10,
            pre_reform_script=(ctx.locale == LOCALE_RU),
        )

        # If it matches the opposite gender expected base, route it to ErrGenderMismatch.rule_id instead
        if ctx.current_patronymic in (opposite_modern, opposite_archaic):
            return None

        # If the patronymic is already matches one of our expected era variants, skip (let the era warning handle it)
        if ctx.current_patronymic in (expected_modern, expected_archaic):
            return None

        return ProposedChange(
            explanation=f"Lineage mismatch: The patronymic does not match father's given name '{ctx.father_given_name}'.",
            suggested_string=expected,
        )
