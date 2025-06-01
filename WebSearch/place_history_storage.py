#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

"""
Module for managing the storage and retrieval of historical administrative
divisions data.

This module defines the `PlaceHistoryStorage` class, which handles:
- Saving place history results to a JSON file in a predefined directory.
- Loading place history results from existing JSON files.
- Ensuring the directory structure exists before saving data.

The data typically contains historical administrative divisions of a place,
formatted in JSON for easy retrieval and reuse.
"""

import json
import os
import sys
from constants import ADMINISTRATIVE_DIVISIONS_DIR


class PlaceHistoryStorage:
    """
    Class for handling the saving and loading of place history data to and from files.
    """

    @staticmethod
    def save_results_to_file(place_history_record, results):
        """
        Save the results to a JSON file in the ADMINISTRATIVE_DIVISIONS_DIR.
        The filename will be generated using place name and place handle.
        """
        # Ensure the directory exists
        if not os.path.exists(ADMINISTRATIVE_DIVISIONS_DIR):
            os.makedirs(ADMINISTRATIVE_DIVISIONS_DIR)

        # Generate a unique filename using place name and handle
        file_path = place_history_record.get("file_path")

        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(results, file, ensure_ascii=False, indent=4)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ Error saving results to file: {e}", file=sys.stderr)

    @staticmethod
    def load_results_from_file(place_history_record):
        """
        Load the results from a JSON file in the ADMINISTRATIVE_DIVISIONS_DIR.
        Returns the data if the file exists, otherwise returns None.
        """
        file_path = place_history_record.get("file_path")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    results = json.load(file)
                return results
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error loading results from file: {e}", file=sys.stderr)
                return None
        return None
