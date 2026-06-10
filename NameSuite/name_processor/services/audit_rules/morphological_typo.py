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

"""
Rule: WarnMorphologicalTypo
Detects invalid consecutive duplicate characters at joint boundaries (e.g. Андрееевич).
"""

import re

from name_processor.services.audit_rules.base import BaseRule
from name_processor.models.audit import RuleContext, ProposedChange
from name_processor.models.audit import Gender
from name_processor.models.constants import (
    SEVERITY_WARNING,
    LOCALE_EAST_SLAVIC,
)
from name_processor.services.morphology import MorphologyService


class WarnMorphologicalTypo(BaseRule):
    """Detects invalid consecutive duplicate characters at joint boundaries (e.g. Андрееевич)."""

    rule_id = "WARN_MORPHOLOGICAL_TYPO"

    @property
    def severity(self) -> str:
        return SEVERITY_WARNING

    @property
    def supported_locales(self) -> set[str]:
        return LOCALE_EAST_SLAVIC

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (None, None)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        if not ctx.current_patronymic:
            return None

        # 1. Typo checks on raw string (e.g. 3 consecutive identical letters like "еее")
        if re.search(r"(.)\1\1+", ctx.current_patronymic):
            # Compress consecutive duplicates to help suggest correction
            suggested = re.sub(r"(.)\1\1+", r"\1", ctx.current_patronymic)
            # Re-generate from father's name if present for maximum accuracy
            if ctx.father_given_name:
                is_male = ctx.gender == Gender.MALE
                pre_reform = MorphologyService.is_pre_reform(ctx, use_pre_reform)
                gen_expected = MorphologyService.generate_east_slavic_patronymic(
                    ctx.father_given_name,
                    is_male=is_male,
                    year=ctx.reference_year,
                    pre_reform_script=pre_reform,
                )
                if gen_expected:
                    suggested = gen_expected

            if suggested != ctx.current_patronymic:
                return ProposedChange(
                    explanation="Spelling anomaly: Contains invalid duplicate letter repetitions at morphological boundaries.",
                    suggested_string=suggested,
                )

        # 2. Check if a duplicate letter differs only from morphological standard
        if ctx.father_given_name:
            is_male = ctx.gender == Gender.MALE
            pre_reform = MorphologyService.is_pre_reform(ctx, use_pre_reform)
            expected = MorphologyService.generate_east_slavic_patronymic(
                ctx.father_given_name,
                is_male=is_male,
                year=ctx.reference_year,
                pre_reform_script=pre_reform,
            )
            if expected and ctx.current_patronymic != expected:
                # Check if they are identical after stripping consecutive repeats
                # Restrict compression to vowels commonly involved in joint transitions
                # to avoid masking valid typos in the root name (e.g., double consonants)
                def compress(s: str) -> str:
                    return re.sub(r"([еиоа])\1+", r"\1", s)

                if compress(ctx.current_patronymic) == compress(expected):
                    return ProposedChange(
                        explanation="Spelling anomaly: Joint spelling differs from standard naming morphology.",
                        suggested_string=expected,
                    )

        return None
