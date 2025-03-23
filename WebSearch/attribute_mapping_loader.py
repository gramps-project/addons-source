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

"""Module for loading and applying attribute mappings from JSON to Gramps objects.

Used by the WebSearch Gramplet to match user-defined attributes to variable placeholders
in URL templates based on navigation type and regular expressions.
"""

import json
import os
import re
import sys
from constants import (
    USER_DATA_ATTRIBUTE_MAPPING_FILE_PATH,
    DEFAULT_ATTRIBUTE_MAPPING_FILE_PATH,
)


class AttributeMappingLoader:
    """
    Loads and processes attribute mappings from a JSON file.

    This class is responsible for reading a mapping file that defines how custom attributes
    in Gramps should be interpreted as variables for constructing URLs in the WebSearch Gramplet.
    """

    def __init__(self):
        """
        Initializes the AttributeMappingLoader.

        It chooses between a user-defined or default JSON mapping file and loads its content
        into memory for further processing.
        """
        if os.path.exists(USER_DATA_ATTRIBUTE_MAPPING_FILE_PATH):
            self.mapping_file = USER_DATA_ATTRIBUTE_MAPPING_FILE_PATH
        else:
            self.mapping_file = DEFAULT_ATTRIBUTE_MAPPING_FILE_PATH
        self.mappings = self.load_mappings()

    def load_mappings(self):
        """
        Loads attribute mappings from the selected JSON file.

        Returns:
            list: A list of mapping dictionaries, or an empty list if loading fails.
        """
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"❌ Error loading attribute mappings: {e}", file=sys.stderr)
            return []

    def get_attributes_for_nav_type(self, nav_type, entity):
        """
        Retrieves attribute mappings relevant to a given navigation type and entity.

        Args:
            nav_type (str): The navigation type (e.g., "People", "Places").
            entity: The Gramps object (e.g., a Person) containing attributes.

        Returns:
            list: A list of dictionaries with matched mappings and attribute values.
        """
        uids_data = []

        try:
            for attribute in entity.get_attribute_list():
                attr_name = attribute.get_type().type2base()
                attr_value = attribute.get_value()

                for mapping in self.mappings:
                    if (
                        mapping["nav_type"].lower() == nav_type.lower()
                        and attr_name.lower() == mapping["attribute_name"].lower()
                    ):
                        uids_data.append(
                            {
                                "nav_type": mapping["nav_type"],
                                "attribute_name": mapping["attribute_name"],
                                "url_regex": mapping["url_regex"],
                                "variable_name": mapping["variable_name"],
                                "value": attr_value,
                            }
                        )
        except Exception as e:
            print(f"❌ Error processing {nav_type} attributes: {e}", file=sys.stderr)

        return uids_data

    def add_matching_variables_to_data(self, uids_data, url_pattern):
        """
        Filters and extracts only those variables whose regex matches the given URL.

        Args:
            uids_data (list): List of attribute data with mapping information.
            url_pattern (str): The target URL pattern to match.

        Returns:
            dict: Dictionary of variable names and values to be inserted into the URL.
        """
        filtered_uids_data = {}
        try:
            for uid_entry in uids_data:
                if re.match(uid_entry["url_regex"], url_pattern, re.IGNORECASE):
                    filtered_uids_data[uid_entry["variable_name"]] = uid_entry["value"]
        except Exception as e:
            print(f"❌ Error adding matching variables: {e}", file=sys.stderr)

        return filtered_uids_data
