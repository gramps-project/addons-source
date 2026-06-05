# -*- coding: utf-8 -*-
"""
Rule: WarnModernSuffixArchaicEra
Flags pre-1918 records using modern formal endings and suggests possessive genitives.
"""

from name_processor.services.audit_rules.base import BaseRule
from name_processor.models.audit import RuleContext, ProposedChange
from name_processor.models.audit import Gender
from name_processor.models.constants import (
    SEVERITY_WARNING,
    LOCALE_EAST_SLAVIC,
    REFORM_YEAR,
)
from name_processor.services.morphology import MorphologyService


class WarnModernSuffixArchaicEra(BaseRule):
    """Flags pre-1918 records using modern formal endings and suggests possessive genitives."""

    rule_id = "WARN_MODERN_SUFFIX_ARCHAIC_ERA"

    @property
    def severity(self) -> str:
        return SEVERITY_WARNING

    @property
    def supported_locales(self) -> set[str]:
        return LOCALE_EAST_SLAVIC

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (None, 1917)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        if not ctx.current_patronymic or (
            ctx.reference_year is not None and ctx.reference_year >= REFORM_YEAR
        ):
            return None

        modern_suffixes = ("ович", "евич", "ич", "овна", "евна", "ична", "инична")

        if any(ctx.current_patronymic.endswith(s) for s in modern_suffixes):
            is_male = ctx.gender == Gender.MALE
            # Adjust condition to respect the user toggle
            pre_reform = MorphologyService.is_pre_reform(ctx, use_pre_reform)

            if ctx.father_given_name:
                suggested = MorphologyService.generate_east_slavic_patronymic(
                    ctx.father_given_name,
                    is_male=is_male,
                    year=1850,
                    pre_reform_script=pre_reform,
                )
            else:
                suggested = MorphologyService.modern_to_archaic(
                    ctx.current_patronymic, is_male=is_male, pre_reform=pre_reform
                )

            if suggested and suggested != ctx.current_patronymic:
                return ProposedChange(
                    explanation=f"Historical anachronism: Modern patronymic suffix in pre-{REFORM_YEAR} era ({ctx.reference_year}).",
                    suggested_string=suggested,
                )

        return None
