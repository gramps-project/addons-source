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

import unittest

from name_processor.services.audit_rules.gender_mismatch import (
    ErrGenderMismatch,
)
from name_processor.services.audit_rules.missing_patronymic import (
    InfoMissingPatronymic,
)
from name_processor.models.audit import RuleContext
from name_processor.models.person import Gender


class TestGenderMismatchRule(unittest.TestCase):
    def test_gender_mismatch_rule(self):
        rule = ErrGenderMismatch()
        ctx = RuleContext(
            person_handle="h1",
            gramps_id="I0001",
            display_name="Test",
            gender=Gender.MALE,
            current_patronymic="Ивановна",  # Incorrect suffix
            father_given_name="Иван",
            reference_year=2000,
            locale="ru",
        )

        change = rule.evaluate(ctx, use_pre_reform=False)
        self.assertIsNotNone(change)
        self.assertIn("Иванович", change.suggested_string)


class TestMissingPatronymicRule(unittest.TestCase):
    def test_missing_patronymic_rule_has_patronymic(self):
        rule = InfoMissingPatronymic()
        ctx = RuleContext(
            person_handle="h1",
            gramps_id="I0001",
            display_name="Test",
            gender=Gender.MALE,
            current_patronymic="Иванович",
            father_given_name="Иван",
            reference_year=2000,
            locale="ru",
        )
        change = rule.evaluate(ctx, use_pre_reform=False)
        self.assertIsNone(change)

    def test_missing_patronymic_rule_no_father(self):
        rule = InfoMissingPatronymic()
        ctx = RuleContext(
            person_handle="h1",
            gramps_id="I0001",
            display_name="Test",
            gender=Gender.MALE,
            current_patronymic="",
            father_given_name="",
            reference_year=2000,
            locale="ru",
        )
        change = rule.evaluate(ctx, use_pre_reform=False)
        self.assertIsNone(change)

    def test_missing_patronymic_rule_unknown_gender(self):
        rule = InfoMissingPatronymic()
        ctx = RuleContext(
            person_handle="h1",
            gramps_id="I0001",
            display_name="Test",
            gender=Gender.UNKNOWN,
            current_patronymic="",
            father_given_name="Иван",
            reference_year=2000,
            locale="ru",
        )
        change = rule.evaluate(ctx, use_pre_reform=False)
        self.assertIsNone(change)

    def test_missing_patronymic_rule_suggests_male(self):
        rule = InfoMissingPatronymic()
        ctx = RuleContext(
            person_handle="h1",
            gramps_id="I0001",
            display_name="Test",
            gender=Gender.MALE,
            current_patronymic="",
            father_given_name="Иван",
            reference_year=2000,
            locale="ru",
        )
        change = rule.evaluate(ctx, use_pre_reform=False)
        self.assertIsNotNone(change)
        self.assertEqual(change.suggested_string, "Иванович")

    def test_missing_patronymic_rule_suggests_female(self):
        rule = InfoMissingPatronymic()
        ctx = RuleContext(
            person_handle="h1",
            gramps_id="I0001",
            display_name="Test",
            gender=Gender.FEMALE,
            current_patronymic="",
            father_given_name="Иван",
            reference_year=2000,
            locale="ru",
        )
        change = rule.evaluate(ctx, use_pre_reform=False)
        self.assertIsNotNone(change)
        self.assertEqual(change.suggested_string, "Ивановна")


if __name__ == "__main__":
    unittest.main()
