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

"""Configuration manager for the WebSearch Gramplet.

This module handles reading and writing user settings (such as AI API key,
URL formatting preferences, enabled data sources, display toggles, etc.) from
a configuration file using Gramps' config system.
"""

import os

from gramps.gen.config import config as configman

from constants import (
    CONFIG_FILE_PATH,
    CONFIGS_DIR,
    DEFAULT_AI_PROVIDER,
    DEFAULT_COLUMNS_ORDER,
    DEFAULT_DISPLAY_COLUMNS,
    DEFAULT_DISPLAY_ICONS,
    DEFAULT_ENABLED_FILES,
    DEFAULT_MIDDLE_NAME_HANDLING,
    DEFAULT_SHOW_ATTRIBUTE_LINKS,
    DEFAULT_SHOW_INTERNET_LINKS,
    DEFAULT_SHOW_NOTE_LINKS,
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    DEFAULT_ENABLED_PLACE_HISTORY,
    DEFAULT_CUSTOM_COUNTRY_CODE_FOR_AI_NOTES,
)


class ConfigINIManager:
    """
    Manages reading and writing WebSearch Gramplet settings from config.ini.

    This includes toggles for features like OpenAI integration, middle name handling,
    URL compactness, enabled CSV files, and display options for the UI.
    """

    def __init__(self):
        """Initializes the configuration manager and registers default settings."""
        self.config_file = CONFIG_FILE_PATH
        if not os.path.exists(self.config_file):
            with open(self.config_file, "w", encoding="utf-8"):
                pass

        self.config = configman.register_manager(os.path.join(CONFIGS_DIR, "config"))
        self.config.register("websearch.enabled_files", DEFAULT_ENABLED_FILES)
        self.config.register(
            "websearch.middle_name_handling", DEFAULT_MIDDLE_NAME_HANDLING
        )
        self.config.register(
            "websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT
        )
        self.config.register("websearch.show_short_url", DEFAULT_SHOW_SHORT_URL)
        self.config.register(
            "websearch.url_compactness_level", DEFAULT_URL_COMPACTNESS_LEVEL
        )
        self.config.register("websearch.ai_provider", DEFAULT_AI_PROVIDER)
        self.config.register("websearch.openai_api_key", "")
        self.config.register("websearch.openai_model", "")
        self.config.register("websearch.mistral_api_key", "")
        self.config.register("websearch.mistral_model", "")
        self.config.register("websearch.columns_order", DEFAULT_COLUMNS_ORDER)
        self.config.register(
            "websearch.show_attribute_links", DEFAULT_SHOW_ATTRIBUTE_LINKS
        )
        self.config.register(
            "websearch.show_internet_links", DEFAULT_SHOW_INTERNET_LINKS
        )
        self.config.register("websearch.show_note_links", DEFAULT_SHOW_NOTE_LINKS)
        self.config.register("websearch.display_columns", DEFAULT_DISPLAY_COLUMNS)
        self.config.register("websearch.display_icons", DEFAULT_DISPLAY_ICONS)

        self.config.register(
            "websearch.enabled_place_history", DEFAULT_ENABLED_PLACE_HISTORY
        )
        self.config.register(
            "websearch.custom_country_code_for_ai_notes",
            DEFAULT_CUSTOM_COUNTRY_CODE_FOR_AI_NOTES,
        )

        self.config.load()

    def get_boolean_option(self, key, default=True):
        """Returns a boolean value from the config by key, or the default if not found."""
        value = self.config.get(key)
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def get_enum(self, key, enum_class, default):
        """Returns a value from the config if it's valid within the provided enum class."""
        value = self.config.get(key)
        return value if value in [e.value for e in enum_class] else default

    def get_string(self, key, default=""):
        """Returns a trimmed string value from the config, or a default if missing."""
        return (self.config.get(key) or default).strip()

    def set_boolean_option(self, key, value):
        """Sets a boolean option in the config and saves the file."""
        if isinstance(value, str):
            value = value.lower() == "true"
        self.config.set(key, bool(value))
        self.save()

    def set_enum(self, key, value):
        """Sets an enum value in the config and saves the file."""
        self.config.set(key, value)
        self.save()

    def set_string(self, key, value):
        """Sets a string value in the config after trimming and saves the file."""
        self.config.set(key, (value or "").strip())
        self.save()

    def set_list(self, key, order):
        """Sets a list value in the config and saves the file if input is valid."""
        if isinstance(order, list):
            self.config.set(key, order)
            self.save()
        else:
            print("❌ Error. Invalid data format. Must be a list.")

    def get_list(self, key, default=None):
        """Returns a list from the config, or a default list if the value is invalid."""
        value = self.config.get(key)
        if isinstance(value, list):
            return value
        if default is None:
            default = []
        return default

    def save(self):
        """Saves the current configuration to file."""
        self.config.save()

    def set_boolean_list(self, key, values):
        """Sets a list of boolean values in the config and saves the file."""
        if isinstance(values, list):
            self.config.set(key, values)
            self.save()
        else:
            print(f"❌ Error. {key}: {type(values)}")
