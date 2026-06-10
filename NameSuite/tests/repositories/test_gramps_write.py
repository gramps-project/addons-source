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
from unittest.mock import Mock, patch, MagicMock

from name_processor.repositories.gramps_write import (
    is_patronymic_origin,
    update_or_add_patronymic,
    GrampsWriteRepository,
)


# Mock Gramps Constants
class MockNameOriginType:
    PATRONYMIC = 2
    GIVEN = 0


class TestIsPatronymicOrigin(unittest.TestCase):
    def setUp(self):
        # autouse equivalent: patch NameOriginType for every test in this class
        patcher = patch(
            "name_processor.repositories.gramps_write.NameOriginType",
            MockNameOriginType,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_is_patronymic_origin(self):
        self.assertTrue(is_patronymic_origin(MockNameOriginType.PATRONYMIC))
        self.assertTrue(is_patronymic_origin(str(MockNameOriginType.PATRONYMIC)))
        self.assertFalse(is_patronymic_origin(MockNameOriginType.GIVEN))
        self.assertFalse(is_patronymic_origin(None))
        self.assertFalse(is_patronymic_origin("invalid_int"))


class TestUpdateOrAddPatronymic(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            "name_processor.repositories.gramps_write.NameOriginType",
            MockNameOriginType,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_update_or_add_patronymic_updates_existing(self):
        mock_primary = Mock()
        mock_surname1 = Mock()
        mock_surname1.get_origintype.return_value = MockNameOriginType.GIVEN
        mock_surname1.get_surname.return_value = "Smith"

        mock_surname2 = Mock()
        mock_surname2.get_origintype.return_value = MockNameOriginType.PATRONYMIC
        mock_surname2.get_surname.return_value = "OldPatronymic"

        mock_primary.get_surname_list.return_value = [mock_surname1, mock_surname2]

        result = update_or_add_patronymic(mock_primary, "NewPatronymic")

        self.assertEqual(result, "OldPatronymic")
        mock_surname2.set_surname.assert_called_once_with("NewPatronymic")
        mock_primary.add_surname.assert_not_called()

    @patch("name_processor.repositories.gramps_write.Surname")
    def test_update_or_add_patronymic_adds_new(self, mock_surname_class):
        mock_primary = Mock()
        mock_surname_existing = Mock()
        mock_surname_existing.get_origintype.return_value = MockNameOriginType.GIVEN
        mock_primary.get_surname_list.return_value = [mock_surname_existing]

        mock_new_surname = Mock()
        mock_surname_class.return_value = mock_new_surname

        result = update_or_add_patronymic(mock_primary, "NewPatronymic")

        self.assertEqual(result, "")
        mock_new_surname.set_surname.assert_called_once_with("NewPatronymic")
        mock_new_surname.set_origintype.assert_called_once_with(
            MockNameOriginType.PATRONYMIC
        )
        mock_new_surname.set_primary.assert_called_once_with(False)
        mock_primary.add_surname.assert_called_once_with(mock_new_surname)


class TestGrampsWriteRepository(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            "name_processor.repositories.gramps_write.NameOriginType",
            MockNameOriginType,
        )
        self.addCleanup(patcher.stop)
        patcher.start()

        self.mock_db = MagicMock()
        self.write_repo = GrampsWriteRepository(self.mock_db)

    @patch(
        "name_processor.repositories.gramps_write.update_or_add_patronymic"
    )
    @patch("name_processor.repositories.gramps_write.DbTxn")
    def test_update_patronymic_names(self, mock_dbtxn, mock_update_func):
        mock_txn_instance = MagicMock()
        mock_dbtxn.return_value.__enter__.return_value = mock_txn_instance

        mock_person = Mock()
        mock_primary = Mock()
        mock_person.get_primary_name.return_value = mock_primary
        self.mock_db.get_person_from_handle.return_value = mock_person

        # Act
        self.write_repo.update_patronymic_names({"h1": "Ivanovich"})

        # Assert
        mock_update_func.assert_called_once_with(mock_primary, "Ivanovich")
        self.mock_db.commit_person.assert_called_once_with(
            mock_person, mock_txn_instance
        )


if __name__ == "__main__":
    unittest.main()
