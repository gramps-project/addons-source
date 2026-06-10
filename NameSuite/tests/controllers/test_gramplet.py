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
from unittest.mock import Mock, MagicMock

from name_processor.controllers.gramplet import GrampletController
from name_processor.models.infer import PatronymicInferenceStatus


class TestGrampletController(unittest.TestCase):
    def setUp(self):
        """Provide fresh mocks for every test."""
        self.mocks = {
            "view": Mock(),
            "patronymic_service": Mock(),
            "read_repo": Mock(),
            "write_repo": Mock(),
        }
        self.controller = GrampletController(
            view=self.mocks["view"],
            patronymic_service=self.mocks["patronymic_service"],
            read_repo=self.mocks["read_repo"],
            write_repo=self.mocks["write_repo"],
        )

    def test_on_active_changed_with_none_handle(self):
        # Act
        self.controller.on_active_changed(None)

        # Assert
        self.assertIsNone(self.controller.current_handle)
        self.mocks["view"].show_status_message.assert_called_once_with(
            PatronymicInferenceStatus.NO_ACTIVE_PERSON, apply_sensitive=False
        )
        self.mocks["read_repo"].get_person_proxy.assert_not_called()

    def test_on_active_changed_person_not_found(self):
        # Arrange
        self.mocks["read_repo"].get_person_proxy.return_value = None

        # Act
        self.controller.on_active_changed("h123")

        # Assert
        self.assertEqual(self.controller.current_handle, "h123")
        self.mocks["read_repo"].get_person_proxy.assert_called_once_with("h123")
        self.mocks["view"].show_status_message.assert_called_once_with(
            PatronymicInferenceStatus.NO_ACTIVE_PERSON, apply_sensitive=False
        )

    def test_on_active_changed_success(self):
        # Arrange
        mock_person = Mock()
        mock_person.father_handle = "f456"
        mock_father = Mock()

        mock_result = MagicMock()
        mock_result.status = PatronymicInferenceStatus.SUCCESS
        mock_result.patronymic = "Ivanovich"
        mock_result.father_name = "Ivan"

        # Setup read_repo to return the person, then the father
        self.mocks["read_repo"].get_person_proxy.side_effect = [
            mock_person,
            mock_father,
        ]
        self.mocks["patronymic_service"].infer_patronymic.return_value = mock_result

        # Act
        self.controller.on_active_changed("h123")

        # Assert
        self.mocks["patronymic_service"].infer_patronymic.assert_called_once_with(
            mock_person, mock_father
        )
        self.assertEqual(self.controller._suggested_patronymic, "Ivanovich")
        self.mocks["view"].show_suggestion.assert_called_once_with("Ivanovich", "Ivan")

    def test_on_apply_clicked_does_nothing_if_no_suggestion(self):
        # Arrange
        self.controller.current_handle = "h123"
        self.controller._suggested_patronymic = None

        # Act
        self.controller.on_apply_clicked()

        # Assert
        self.mocks["write_repo"].update_patronymic_names.assert_not_called()

    def test_on_apply_clicked_success(self):
        # Arrange
        self.controller.current_handle = "h123"
        self.controller._suggested_patronymic = "Ivanovich"

        # Act
        self.controller.on_apply_clicked()

        # Assert
        self.mocks["write_repo"].update_patronymic_names.assert_called_once_with(
            {"h123": "Ivanovich"}
        )
        self.mocks["view"].show_status_message.assert_called_once_with(
            PatronymicInferenceStatus.SUCCESS, apply_sensitive=False
        )


if __name__ == "__main__":
    unittest.main()
