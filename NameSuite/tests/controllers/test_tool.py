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
from unittest.mock import MagicMock

from name_processor.controllers.tool import ToolController


class TestToolController(unittest.TestCase):
    def test_controller_initialization(self):
        mock_dbstate = MagicMock()
        mock_tool = MagicMock(dbstate=mock_dbstate)

        # Instantiate without real DB
        controller = ToolController(
            tool_instance=mock_tool,
            view=MagicMock(),
            read_repo=MagicMock(),
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=MagicMock(),
        )
        self.assertEqual(controller.dbstate, mock_dbstate)

    def test_update_preserve_alt(self) -> None:
        mock_dbstate = MagicMock()
        mock_tool = MagicMock(dbstate=mock_dbstate)
        mock_view = MagicMock()

        controller = ToolController(
            tool_instance=mock_tool,
            view=mock_view,
            read_repo=MagicMock(),
            write_repo=MagicMock(),
            patronymic_service=MagicMock(),
            renamer_service=MagicMock(),
            alt_names_service=MagicMock(),
            audit_service=MagicMock(),
            chronology_service=MagicMock(),
        )

        from name_processor.models.renamer import ProposedRename

        proposal1 = ProposedRename(
            handle="handle1",
            gramps_id="I0001",
            display_name="Ivan Ivanov",
            original_given_name="Ivan",
            proposed_given_name="Ioann",
            alt_action="Overwrite",
        )
        controller._rename_candidates["handle1"] = proposal1

        # Toggle preserve on (active=True)
        controller.update_preserve_alt(True)

        self.assertEqual(proposal1.alt_action, "Preserve")
        mock_view.update_given_store_actions.assert_called_once_with("Preserve")

        # Toggle preserve off (active=False)
        mock_view.reset_mock()
        controller.update_preserve_alt(False)

        self.assertEqual(proposal1.alt_action, "Overwrite")
        mock_view.update_given_store_actions.assert_called_once_with("Overwrite")


if __name__ == "__main__":
    unittest.main()
