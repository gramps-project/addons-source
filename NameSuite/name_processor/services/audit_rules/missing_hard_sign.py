# -*- coding: utf-8 -*-
"""
Rule: WarnMissingHardSign
Flags pre-1918 Russian names missing a terminal orthographic hard sign 'ъ'.
"""

from name_processor.services.audit_rules.base import BaseRule
from name_processor.models.audit import RuleContext, ProposedChange
from name_processor.models.constants import (
    SEVERITY_WARNING,
    LOCALE_RU,
    REFORM_YEAR,
)
from name_processor.services.morphology import MorphologyService


class WarnMissingHardSign(BaseRule):
    """Flags pre-1918 Russian names missing a terminal orthographic hard sign 'ъ'."""

    rule_id = "WARN_MISSING_HARD_SIGN"

    @property
    def severity(self) -> str:
        return SEVERITY_WARNING

    @property
    def supported_locales(self) -> set[str]:
        return {LOCALE_RU}

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (None, 1917)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        # Short-circuit if pre-reform rules are disabled by the user
        if (
            not ctx.current_patronymic
            or not use_pre_reform
            or (ctx.reference_year is not None and ctx.reference_year >= REFORM_YEAR)
            or ctx.locale != LOCALE_RU
        ):
            return None

        # Re-apply pre-reform orthography mapping on the current value
        reformed = MorphologyService.apply_pre_reform_orthography(
            ctx.current_patronymic
        )

        if reformed != ctx.current_patronymic:
            return ProposedChange(
                explanation="Orthographical anomaly: Missing historical pre-revolutionary terminal hard signs (ъ) or decimal (і).",
                suggested_string=reformed,
            )

        return None
