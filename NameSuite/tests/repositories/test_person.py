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
        self.mock_db = Mock()
        self.mock_gramps_person = Mock()
        self.mock_gramps_person.get_handle.return_value = "p123"

        # Patch the GrampsPerson reference in the module to use our mock constants
        import name_processor.repositories.person as repo_module

        repo_module.GrampsPerson = MockGrampsPerson
        repo_module.NameOriginType = MockNameOriginType

        self.proxy = GrampsPersonProxy(self.mock_gramps_person, self.mock_db)

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

    def test_father_handle_found(self):
        self.mock_gramps_person.get_parent_family_handle_list.return_value = ["fam1"]
        mock_family = Mock()
        mock_family.get_father_handle.return_value = "father123"
        self.mock_db.get_family_from_handle.return_value = mock_family

        self.assertEqual(self.proxy.father_handle, "father123")

    def test_mother_handle_not_found(self):
        self.mock_gramps_person.get_parent_family_handle_list.return_value = []
        self.assertIsNone(self.proxy.mother_handle)

    def test_children_handles(self):
        self.mock_gramps_person.get_family_handle_list.return_value = ["fam1", "fam2"]

        mock_fam1 = Mock()
        mock_child1 = Mock(ref="child1")
        mock_child2 = Mock(ref="child2")
        mock_fam1.get_child_ref_list.return_value = [mock_child1, mock_child2]

        mock_fam2 = Mock()
        mock_child3 = Mock(ref="child3")
        mock_fam2.get_child_ref_list.return_value = [mock_child3]

        self.mock_db.get_family_from_handle.side_effect = [mock_fam1, mock_fam2]

        self.assertEqual(self.proxy.children_handles, ["child1", "child2", "child3"])

    def test_siblings_handles_excludes_self(self):
        # Proxy's own handle is "p123"
        self.mock_gramps_person.get_parent_family_handle_list.return_value = [
            "parent_fam"
        ]

        mock_fam = Mock()
        mock_self = Mock(ref="p123")
        mock_sibling = Mock(ref="sib456")
        mock_fam.get_child_ref_list.return_value = [mock_self, mock_sibling]

        self.mock_db.get_family_from_handle.return_value = mock_fam

        self.assertEqual(self.proxy.siblings_handles, ["sib456"])

    def test_event_years(self):
        mock_ref1 = Mock(ref="e1")
        mock_ref2 = Mock(ref="e2")
        self.mock_gramps_person.get_event_ref_list.return_value = [mock_ref1, mock_ref2]

        mock_event1 = Mock()
        mock_date1 = Mock()
        mock_date1.is_empty.return_value = False
        mock_date1.get_year.return_value = 1850
        mock_event1.get_date_object.return_value = mock_date1

        mock_event2 = Mock()
        mock_date2 = Mock()
        mock_date2.is_empty.return_value = True  # Empty date should be skipped
        mock_event2.get_date_object.return_value = mock_date2

        self.mock_db.get_event_from_handle.side_effect = [mock_event1, mock_event2]

        self.assertEqual(self.proxy.event_years, [1850])

    def test_given_name(self):
        mock_primary_name = Mock()
        mock_primary_name.get_first_name.return_value = "Ivan"
        self.mock_gramps_person.get_primary_name.return_value = mock_primary_name

        self.assertEqual(self.proxy.given_name, "Ivan")


if __name__ == "__main__":
    unittest.main()
