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

    @patch("name_processor.repositories.gramps_write.update_or_add_patronymic")
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

    @patch("name_processor.repositories.gramps_write.Name", create=True)
    @patch("name_processor.repositories.gramps_write.NameType")
    def test_preserve_primary_name_copies_to_alternate_names(
        self, mock_name_type, mock_name_class
    ):
        """Test that preserve_primary_name copies primary name to alternate names."""
        mock_person = Mock()
        mock_primary_name = Mock()
        mock_person.get_primary_name.return_value = mock_primary_name

        # Configure mock to accept source keyword argument in constructor
        mock_name_instance = Mock()
        mock_name_class.side_effect = lambda **kwargs: mock_name_instance

        self.write_repo.preserve_primary_name(mock_person)

        mock_name_class.assert_called_once_with(source=mock_primary_name)
        mock_name_type.assert_called_once_with(mock_name_type.AKA)
        mock_person.add_alternate_name.assert_called_once()

    def test_preserve_primary_name_does_nothing_when_no_primary_name(self):
        """Test that preserve_primary_name does nothing when person has no primary name."""
        mock_person = Mock()
        mock_person.get_primary_name.return_value = None

        self.write_repo.preserve_primary_name(mock_person)

        mock_person.add_alternate_name.assert_not_called()

    @patch("name_processor.repositories.gramps_write.DbTxn")
    def test_apply_first_name_correction_without_preserve(self, mock_dbtxn):
        """Test apply_first_name_correction without preserving alt name."""
        mock_txn = MagicMock()
        mock_dbtxn.return_value.__enter__.return_value = mock_txn

        mock_person = Mock()
        mock_primary_name = Mock()
        mock_person.get_primary_name.return_value = mock_primary_name
        self.mock_db.get_person_from_handle.return_value = mock_person

        self.write_repo.apply_first_name_correction(
            mock_txn, "handle123", "NewName", preserve_alt=False
        )

        self.mock_db.get_person_from_handle.assert_called_once_with("handle123")
        mock_primary_name.set_first_name.assert_called_once_with("NewName")
        self.mock_db.commit_person.assert_called_once_with(mock_person, mock_txn)
        mock_person.add_alternate_name.assert_not_called()

    @patch("name_processor.repositories.gramps_write.Name")
    @patch("name_processor.repositories.gramps_write.NameType")
    @patch("name_processor.repositories.gramps_write.DbTxn")
    def test_apply_first_name_correction_with_preserve(
        self, mock_dbtxn, mock_name_type, mock_name_class
    ):
        """Test apply_first_name_correction with preserving alt name."""
        mock_txn = MagicMock()
        mock_dbtxn.return_value.__enter__.return_value = mock_txn

        mock_person = Mock()
        mock_primary_name = Mock()
        mock_person.get_primary_name.return_value = mock_primary_name
        self.mock_db.get_person_from_handle.return_value = mock_person

        self.write_repo.apply_first_name_correction(
            mock_txn, "handle123", "NewName", preserve_alt=True
        )

        self.mock_db.get_person_from_handle.assert_called_once_with("handle123")
        mock_name_class.assert_called_once_with(source=mock_primary_name)
        mock_name_type.assert_called_once_with(mock_name_type.AKA)
        mock_person.add_alternate_name.assert_called_once()
        mock_primary_name.set_first_name.assert_called_once_with("NewName")
        self.mock_db.commit_person.assert_called_once_with(mock_person, mock_txn)

    @patch("name_processor.repositories.gramps_write.DbTxn")
    def test_apply_first_name_correction_raises_when_person_not_found(self, mock_dbtxn):
        """Test apply_first_name_correction raises ValueError when person not found."""
        mock_txn = MagicMock()
        mock_dbtxn.return_value.__enter__.return_value = mock_txn
        self.mock_db.get_person_from_handle.return_value = None

        with self.assertRaises(ValueError) as context:
            self.write_repo.apply_first_name_correction(
                mock_txn, "bad_handle", "NewName"
            )

        self.assertIn("bad_handle", str(context.exception))


if __name__ == "__main__":
    unittest.main()
