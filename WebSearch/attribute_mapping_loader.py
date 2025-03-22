import json
import os
import re
import sys
from constants import *

class AttributeMappingLoader:
    """
    AttributeMappingLoader loads and processes attribute mappings from a JSON file.

    It matches URLs against predefined regular expressions and extracts relevant variables
    for genealogical research in the WebSearch gramplet.
    """

    def __init__(self):
        if os.path.exists(USER_DATA_ATTRIBUTE_MAPPING_FILE_PATH):
            self.mapping_file = USER_DATA_ATTRIBUTE_MAPPING_FILE_PATH
        else:
            self.mapping_file = DEFAULT_ATTRIBUTE_MAPPING_FILE_PATH
        self.mappings = self.load_mappings()

    def load_mappings(self):
        try:
            with open(self.mapping_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠ Error loading attribute mappings: {e}", file=sys.stderr)
            return []

    def get_attributes_for_nav_type(self, nav_type, entity):
        uids_data = []

        try:
            for attribute in entity.get_attribute_list():
                attr_name = attribute.get_type().type2base()
                attr_value = attribute.get_value()

                for mapping in self.mappings:
                    if mapping["nav_type"].lower() == nav_type.lower() and attr_name.lower() == mapping["attribute_name"].lower():
                        uids_data.append({
                            "nav_type": mapping["nav_type"],
                            "attribute_name": mapping["attribute_name"],
                            "url_regex": mapping["url_regex"],
                            "variable_name": mapping["variable_name"],
                            "value": attr_value
                        })
        except Exception as e:
            print(f"❌ Error processing {nav_type} attributes: {e}", file=sys.stderr)

        return uids_data

    def add_matching_variables_to_data(self, uids_data, url_pattern):
        filtered_uids_data = {}
        try:
            for uid_entry in uids_data:
                if re.match(uid_entry["url_regex"], url_pattern, re.IGNORECASE):
                    filtered_uids_data[uid_entry["variable_name"]] = uid_entry["value"]
        except Exception as e:
            print(f"❌ Error adding matching variables: {e}", file=sys.stderr)

        return filtered_uids_data