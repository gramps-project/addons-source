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
from unittest.mock import Mock

from name_processor.repositories.person import GrampsPersonProxy
from name_processor.models.person import Gender


# Mocking Gramps constants used in the proxy
class MockGrampsPerson:
    MALE = 0
    FEMALE = 1


class MockNameOriginType:
    PATRONYMIC = 2
    GIVEN = 0


class TestGrampsPersonProxy(unittest.TestCase):
    def setUp(self):
        self.mock_gramps_person = Mock()
        self.mock_gramps_person.get_handle.return_value = "p123"

        # Patch the GrampsPerson reference in the module to use our mock constants
        import name_processor.repositories.person as repo_module

        repo_module.GrampsPerson = MockGrampsPerson
        repo_module.NameOriginType = MockNameOriginType

        self.proxy = GrampsPersonProxy(self.mock_gramps_person)

    def test_handle(self):
        self.assertEqual(self.proxy.handle, "p123")

    def test_gender_male(self):
        self.mock_gramps_person.get_gender.return_value = MockGrampsPerson.MALE
        self.assertEqual(self.proxy.gender, Gender.MALE)

    def test_gender_female_or_other(self):
        self.mock_gramps_person.get_gender.return_value = MockGrampsPerson.FEMALE
        self.assertEqual(self.proxy.gender, Gender.FEMALE)

    def test_has_patronymic_true(self):
        mock_primary_name = Mock()
        mock_surname1 = Mock()
        mock_surname1.get_origintype.return_value = MockNameOriginType.GIVEN
        mock_surname2 = Mock()
        mock_surname2.get_origintype.return_value = MockNameOriginType.PATRONYMIC

        mock_primary_name.get_surname_list.return_value = [mock_surname1, mock_surname2]
        self.mock_gramps_person.get_primary_name.return_value = mock_primary_name

        self.assertTrue(self.proxy.has_patronymic)

    def test_has_patronymic_false(self):
        mock_primary_name = Mock()
        mock_surname = Mock()
        mock_surname.get_origintype.return_value = MockNameOriginType.GIVEN

        mock_primary_name.get_surname_list.return_value = [mock_surname]
        self.mock_gramps_person.get_primary_name.return_value = mock_primary_name

        self.assertFalse(self.proxy.has_patronymic)

    def test_given_name(self):
        mock_primary_name = Mock()
        mock_primary_name.get_first_name.return_value = "Ivan"
        self.mock_gramps_person.get_primary_name.return_value = mock_primary_name

        self.assertEqual(self.proxy.given_name, "Ivan")


if __name__ == "__main__":
    unittest.main()
