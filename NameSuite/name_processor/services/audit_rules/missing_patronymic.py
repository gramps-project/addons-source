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
Rule: InfoMissingPatronymic
Flags if a person is missing a patronymic but one can be inferred from the father's name.
"""

from __future__ import annotations

from name_processor.services.audit_rules.base import BaseRule
from name_processor.models.audit import ProposedChange, RuleContext
from name_processor.models.person import Gender
from name_processor.models.constants import LOCALE_EAST_SLAVIC, SEVERITY_INFO
from name_processor.services.morphology import MorphologyService


class InfoMissingPatronymic(BaseRule):
    """Flags if a person is missing a patronymic but one can be inferred."""

    rule_id = "INFO_MISSING_PATRONYMIC"

    @property
    def severity(self) -> str:
        return SEVERITY_INFO

    @property
    def supported_locales(self) -> set[str]:
        return LOCALE_EAST_SLAVIC

    @property
    def active_era(self) -> tuple[int | None, int | None]:
        return (None, None)

    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        if ctx.current_patronymic:
            return None

        if not ctx.father_given_name:
            return None

        if ctx.gender not in (Gender.MALE, Gender.FEMALE):
            return None

        is_male = ctx.gender == Gender.MALE
        pre_reform = MorphologyService.is_pre_reform(ctx, use_pre_reform)

        suggested = MorphologyService.generate_east_slavic_patronymic(
            ctx.father_given_name,
            is_male=is_male,
            year=ctx.reference_year,
            pre_reform_script=pre_reform,
        )

        if suggested:
            return ProposedChange(
                explanation="Missing patronymic: A patronymic can be inferred from the father's given name.",
                suggested_string=suggested,
            )

        return None
