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
Tests for the i18n module to ensure translation path calculation is correct.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Mock Gramps before importing the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from compat_mocks import mock_gramps

mock_gramps()

from name_processor.views.i18n import _ADDON_ROOT


class TestI18nPathCalculation(unittest.TestCase):
    """Test that the i18n module correctly calculates the addon root path."""

    def test_addon_root_points_to_correct_directory(self):
        """Test that _ADDON_ROOT points to the NameSuite directory."""
        # The addon root should be the NameSuite directory
        # i18n.py is at name_processor/views/i18n.py
        # So _ADDON_ROOT should be 3 directories up
        expected_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        # Since this test is in tests/presentation/, we need to go up 4 levels to reach NameSuite
        # But the i18n module is in name_processor/views/, so from there it's 3 levels up
        # Let's verify the actual path structure
        i18n_file = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "name_processor",
                "views",
                "i18n.py",
            )
        )
        calculated_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(i18n_file)))
        )

        self.assertEqual(_ADDON_ROOT, calculated_root)

    def test_locale_directory_exists_at_addon_root(self):
        """Test that the locale directory exists at the calculated addon root."""
        locale_path = os.path.join(_ADDON_ROOT, "locale")
        # The locale directory should exist (or po/ as the source)
        # In development, translations are in po/, but installed they're in locale/
        # We'll check for po/ since that's what exists in the repo
        po_path = os.path.join(_ADDON_ROOT, "po")
        self.assertTrue(
            os.path.exists(po_path),
            f"Expected po/ directory at {po_path}, but it doesn't exist. "
            f"_ADDON_ROOT is: {_ADDON_ROOT}",
        )

    def test_addon_root_contains_expected_structure(self):
        """Test that the addon root contains the expected directory structure."""
        # The addon root should contain key directories
        expected_dirs = ["name_processor", "po"]
        for dir_name in expected_dirs:
            dir_path = os.path.join(_ADDON_ROOT, dir_name)
            self.assertTrue(
                os.path.exists(dir_path),
                f"Expected {dir_name}/ directory at {dir_path}, but it doesn't exist. "
                f"_ADDON_ROOT is: {_ADDON_ROOT}",
            )

    def test_dirnest_count_matches_file_location(self):
        """Test that the number of dirname calls matches the file's actual location."""
        # i18n.py is at name_processor/views/i18n.py
        # From there to NameSuite/ is: views -> name_processor -> NameSuite (3 levels)
        # So we need 3 dirname calls

        i18n_file = os.path.join(_ADDON_ROOT, "name_processor", "views", "i18n.py")
        self.assertTrue(
            os.path.exists(i18n_file),
            f"Expected i18n.py at {i18n_file}, but it doesn't exist. "
            f"_ADDON_ROOT is: {_ADDON_ROOT}",
        )

        # Verify the path calculation
        calculated = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(i18n_file)))
        )
        self.assertEqual(
            calculated,
            _ADDON_ROOT,
            f"Path calculation mismatch. Expected {_ADDON_ROOT}, got {calculated}",
        )

    def test_moving_file_breaks_path_calculation(self):
        """Test that moving i18n.py to a different location would break the path calculation."""
        # This test documents the expected behavior: if i18n.py is moved,
        # the dirname count needs to be updated

        # Simulate moving i18n.py to name_processor/i18n.py (one level up from current)
        hypothetical_location = os.path.join(_ADDON_ROOT, "name_processor", "i18n.py")

        # If we used the current 3-dirname calculation on the hypothetical location:
        wrong_calculation = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(hypothetical_location)))
        )

        # This would point to the parent of NameSuite (e.g., /home/db/projects/gramps/)
        # which is WRONG - it should point to NameSuite itself
        self.assertNotEqual(
            wrong_calculation,
            _ADDON_ROOT,
            "Moving i18n.py without updating dirname count would break path calculation",
        )

        # The correct calculation for the hypothetical location would be 2 dirname calls
        correct_hypothetical = os.path.dirname(
            os.path.dirname(os.path.abspath(hypothetical_location))
        )
        # This should equal _ADDON_ROOT
        self.assertEqual(
            correct_hypothetical,
            _ADDON_ROOT,
            "If i18n.py were moved to name_processor/, 2 dirname calls would be correct",
        )


if __name__ == "__main__":
    unittest.main()
