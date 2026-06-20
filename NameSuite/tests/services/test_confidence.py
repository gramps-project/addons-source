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

from __future__ import annotations

import unittest

from name_processor.services.confidence import (
    ConfidenceService,
    has_cyrillic,
)


class MockConfidenceSubject:
    """Mock implementation of ConfidenceSubject protocol for testing."""

    def __init__(
        self,
        handle: str = "p123",
        display_name: str = "Ivan Ivanov",
        surnames: list[str] | None = None,
        given_name: str | None = None,
        has_patronymic: bool = False,
    ) -> None:
        self._handle = handle
        self._display_name = display_name
        self._surnames = surnames or []
        self._given_name = given_name
        self._has_patronymic = has_patronymic

    @property
    def handle(self) -> str:
        return self._handle

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def surnames(self) -> list[str]:
        return self._surnames

    @property
    def given_name(self) -> str | None:
        return self._given_name

    @property
    def has_patronymic(self) -> bool:
        return self._has_patronymic


class MockConfidenceRepository:
    """Mock implementation of ConfidenceRepository protocol for testing."""

    def __init__(
        self,
        subjects: dict[str, MockConfidenceSubject] | None = None,
        siblings_map: dict[str, list[str]] | None = None,
    ) -> None:
        self._subjects = subjects or {}
        self._siblings_map = siblings_map or {}

    def get_person(self, handle: str) -> MockConfidenceSubject | None:
        return self._subjects.get(handle)

    def get_siblings_handles(self, person_handle: str) -> list[str]:
        return self._siblings_map.get(person_handle, [])


class TestConfidenceService(unittest.TestCase):
    def setUp(self):
        self.mock_repository = MockConfidenceRepository()
        self.service = ConfidenceService(self.mock_repository)

    def test_base_score_only(self):
        """Test that base score is returned when no signals apply."""
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        result = self.service.calculate(person.handle, None, None)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)

    def test_sibling_with_patronymic(self):
        """Test positive signal: sibling has patronymic."""
        sibling = MockConfidenceSubject(
            handle="sib1", has_patronymic=True, display_name="Петр Петров"
        )
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[sibling.handle] = sibling
        self.mock_repository._siblings_map[person.handle] = [sibling.handle]

        result = self.service.calculate(person.handle, None, None)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.CONFIDENCE_SCORE_SIBLING
        )
        self.assertEqual(result, expected)

    def test_sibling_without_patronymic(self):
        """Test that sibling without patronymic doesn't add score."""
        sibling = MockConfidenceSubject(
            handle="sib1", has_patronymic=False, display_name="Петр Петров"
        )
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[sibling.handle] = sibling
        self.mock_repository._siblings_map[person.handle] = [sibling.handle]

        result = self.service.calculate(person.handle, None, None)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)

    def test_slavic_surname_father(self):
        """Test positive signal: father has Slavic surname suffix."""
        father = MockConfidenceSubject(handle="father1", surnames=["Иванов", "Петров"])
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.CONFIDENCE_SCORE_SLAVIC_SURNAME
        )
        self.assertEqual(result, expected)

    def test_slavic_surname_person(self):
        """Test positive signal: person has Slavic surname suffix when no father."""
        person = MockConfidenceSubject(
            display_name="Иван Иванов", surnames=["Иванов", "Петров"]
        )
        self.mock_repository._subjects[person.handle] = person

        result = self.service.calculate(person.handle, None, None)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.CONFIDENCE_SCORE_SLAVIC_SURNAME
        )
        self.assertEqual(result, expected)

    def test_non_slavic_surname(self):
        """Test that non-Slavic surname doesn't add score."""
        father = MockConfidenceSubject(handle="father1", surnames=["Smith", "Jones"])
        person = MockConfidenceSubject(display_name="John Smith")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        # Base score + non-Cyrillic penalty (no Slavic surname bonus)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.PENALTY_NON_CYRILLIC
        )
        self.assertEqual(result, expected)

    def test_penalty_non_cyrillic(self):
        """Test negative signal: absence of Cyrillic characters."""
        person = MockConfidenceSubject(display_name="John Smith")
        self.mock_repository._subjects[person.handle] = person

        result = self.service.calculate(person.handle, None, None)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.PENALTY_NON_CYRILLIC
        )
        self.assertEqual(result, expected)

    def test_cyrillic_display_name(self):
        """Test that Cyrillic display name doesn't incur penalty."""
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person

        result = self.service.calculate(person.handle, None, None)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)

    def test_penalty_multi_word_father(self):
        """Test negative signal: multi-word father's name."""
        father = MockConfidenceSubject(handle="father1", given_name="Ivan Ivanovich")
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.PENALTY_MULTI_WORD_FATHER
        )
        self.assertEqual(result, expected)

    def test_penalty_hyphenated_father_name(self):
        """Test negative signal: hyphenated father's name."""
        father = MockConfidenceSubject(handle="father1", given_name="Jean-Pierre")
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.PENALTY_MULTI_WORD_FATHER
        )
        self.assertEqual(result, expected)

    def test_no_penalty_single_word_father(self):
        """Test that single-word father's name doesn't incur penalty."""
        father = MockConfidenceSubject(handle="father1", given_name="Ivan")
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)

    def test_penalty_uncertain_father(self):
        """Test negative signal: uncertain father's name with brackets."""
        father = MockConfidenceSubject(handle="father1", given_name="Ivan [?]")
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        # Base score + penalty = 0.4 + (-0.5) = -0.1, clamped to 0.0
        expected = 0.0
        self.assertEqual(result, expected)

    def test_penalty_uncertain_father_parentheses(self):
        """Test negative signal: uncertain father's name with parentheses."""
        father = MockConfidenceSubject(handle="father1", given_name="Ivan (unknown)")
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        # Base score + penalty = 0.4 + (-0.5) = -0.1, clamped to 0.0
        expected = 0.0
        self.assertEqual(result, expected)

    def test_penalty_medieval_year(self):
        """Test negative signal: medieval reference year."""
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person

        result = self.service.calculate(person.handle, None, 1400)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.PENALTY_MEDIEVAL_YEAR
        )
        self.assertEqual(result, expected)

    def test_no_penalty_modern_year(self):
        """Test that modern year doesn't incur penalty."""
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person

        result = self.service.calculate(person.handle, None, 1850)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)

    def test_no_penalty_none_year(self):
        """Test that None year doesn't incur penalty."""
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person

        result = self.service.calculate(person.handle, None, None)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)

    def test_combined_signals(self):
        """Test combination of multiple signals."""
        sibling = MockConfidenceSubject(
            handle="sib1", has_patronymic=True, display_name="Петр Петров"
        )
        father = MockConfidenceSubject(
            handle="father1", surnames=["Иванов"], given_name="Ivan"
        )
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father
        self.mock_repository._subjects[sibling.handle] = sibling
        self.mock_repository._siblings_map[person.handle] = [sibling.handle]

        result = self.service.calculate(person.handle, father.handle, 1800)
        expected = (
            ConfidenceService.CONFIDENCE_BASE_SCORE
            + ConfidenceService.CONFIDENCE_SCORE_SIBLING
            + ConfidenceService.CONFIDENCE_SCORE_SLAVIC_SURNAME
        )
        self.assertEqual(result, expected)

    def test_score_clamped_at_maximum(self):
        """Test that score is clamped at 1.0 maximum."""
        sibling = MockConfidenceSubject(
            handle="sib1", has_patronymic=True, display_name="Петр Петров"
        )
        father = MockConfidenceSubject(
            handle="father1", surnames=["Иванов"], given_name="Ivan"
        )
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father
        self.mock_repository._subjects[sibling.handle] = sibling
        self.mock_repository._siblings_map[person.handle] = [sibling.handle]

        result = self.service.calculate(person.handle, father.handle, 1800)
        self.assertEqual(result, 1.0)

    def test_score_clamped_at_minimum(self):
        """Test that score is clamped at 0.0 minimum."""
        person = MockConfidenceSubject(display_name="John Smith")
        father = MockConfidenceSubject(
            handle="father1", surnames=["Smith"], given_name="John [?]"
        )
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, 1400)
        self.assertEqual(result, 0.0)

    def test_no_father_given_name(self):
        """Test that penalties requiring father's given name are skipped when None."""
        father = MockConfidenceSubject(handle="father1", given_name=None)
        person = MockConfidenceSubject(display_name="Иван Иванов")
        self.mock_repository._subjects[person.handle] = person
        self.mock_repository._subjects[father.handle] = father

        result = self.service.calculate(person.handle, father.handle, None)
        self.assertEqual(result, ConfidenceService.CONFIDENCE_BASE_SCORE)


class TestHasCyrillic(unittest.TestCase):
    def test_has_cyrillic_true(self):
        """Test that Cyrillic characters are detected."""
        self.assertTrue(has_cyrillic("Иван"))
        self.assertTrue(has_cyrillic("Иванов"))
        self.assertTrue(has_cyrillic("Петр Петрович"))

    def test_has_cyrillic_false(self):
        """Test that non-Cyrillic characters are not detected."""
        self.assertFalse(has_cyrillic("Ivan"))
        self.assertFalse(has_cyrillic("John Smith"))
        self.assertFalse(has_cyrillic("123"))

    def test_has_cyrillic_mixed(self):
        """Test that mixed text with Cyrillic is detected."""
        self.assertTrue(has_cyrillic("Ivan Иванов"))


if __name__ == "__main__":
    unittest.main()
