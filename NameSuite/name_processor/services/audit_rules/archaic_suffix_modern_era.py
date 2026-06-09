# -*- coding: utf-8 -*-
"""
Rule: WarnArchaicSuffixModernEra
Flags post-1918 records using archaic/informal possessive endings.
"""

from NameSuite.name_processor.services.audit_rules.base import BaseRule
from NameSuite.name_processor.models.audit import RuleContext, ProposedChange
from NameSuite.name_processor.models.audit import Gender
from NameSuite.name_processor.models.constants import (
    SEVERITY_WARNING,
    LOCALE_EAST_SLAVIC,
    REFORM_YEAR,
)
from NameSuite.name_processor.services.morphology import MorphologyService


class WarnArchaicSuffixModernEra(BaseRule):
    """Flags post-1918 records using archaic/informal possessive endings."""

    rule_id = "WARN_ARCHAIC_SUFFIX_MODERN_ERA"

    @property
    def severity(self) -> str:
        return SEVERITY_WARNING

    @property
    def supported_locales(self) -> set[str]:
        return LOCALE_EAST_SLAVIC

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (REFORM_YEAR, None)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        if not ctx.current_patronymic or (
            ctx.reference_year is not None and ctx.reference_year < REFORM_YEAR
        ):
            return None

        # Archaic endings (including pre-reform orthographic variants)
        archaic_suffixes = ("ов", "ев", "ин", "ова", "ева", "ина", "овъ", "евъ", "инъ")

        if any(ctx.current_patronymic.endswith(s) for s in archaic_suffixes):
            is_male = ctx.gender == Gender.MALE

            if ctx.father_given_name:
                suggested = MorphologyService.generate_east_slavic_patronymic(
                    father_name=ctx.father_given_name,
                    is_male=is_male,
                    year=1950,
                    pre_reform_script=False,
                )
            else:
                suggested = MorphologyService.archaic_to_modern(
                    ctx.current_patronymic, is_male=is_male
                )

            if suggested and suggested != ctx.current_patronymic:
                return ProposedChange(
                    explanation=f"Historical anachronism: Archaic genitive suffix in post-{REFORM_YEAR} era ({ctx.reference_year}).",
                    suggested_string=suggested,
                )

        return None
