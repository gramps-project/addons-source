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
Manages UI configuration options for the WebSearch Gramplet in Gramps.
"""

from types import SimpleNamespace

from gramps.gen.plug.menu import (
    BooleanListOption,
    BooleanOption,
    EnumeratedListOption,
    StringOption,
)

from constants import (
    ALL_COLUMNS,
    ALL_COLUMNS_LOCALIZED,
    ALL_ICONS,
    ALL_ICONS_LOCALIZED,
    COMMON_CSV_FILE_NAME,
    CROSS_CSV_FILE_NAME,
    DEFAULT_AI_PROVIDER,
    DEFAULT_DISPLAY_COLUMNS,
    DEFAULT_DISPLAY_ICONS,
    DEFAULT_MIDDLE_NAME_HANDLING,
    DEFAULT_SHOW_ATTRIBUTE_LINKS,
    DEFAULT_SHOW_INTERNET_LINKS,
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    STATIC_CSV_FILE_NAME,
    UID_CSV_FILE_NAME,
    AIProviders,
    MiddleNameHandling,
    URLCompactnessLevel,
)
from translation_helper import _
from website_loader import WebsiteLoader


class SettingsUIManager:
    """
    SettingsUIManager class for managing user configuration options.

    This class handles the creation and management of user-configurable settings
    for the WebSearch gramplet in Gramps. It builds various types of options such
    as boolean toggles, enumerated lists, and string inputs.

    Key Features:
    - Manages and organizes configuration settings.
    - Supports enabling/disabling specific CSV files for web searches.
    - Allows customization of name handling, URL formats, and OpenAI integration.
    - Provides a method to print the current settings for debugging.

    Attributes:
    - config_ini_manager: Manages reading and writing settings to the configuration file.
    - opts: A list of option objects representing different settings.

    Methods:
    - build_options(): Constructs and returns a list of settings options.
    - add_csv_files_option(): Adds an option to enable/disable CSV files for searches.
    - add_boolean_option(): Adds a boolean toggle option.
    - add_enum_option(): Adds an enumerated list option with localized descriptions.
    - add_string_option(): Adds a string input option.
    """

    def __init__(self, config_ini_manager):
        """
        Initialize the SettingsUIManager.

        Args:
            config_ini_manager: An instance of ConfigINIManager
            used to get and set configuration values.
        """
        self.config_ini_manager = config_ini_manager
        self.opts = []

    def build_options(self):
        """
        Build the list of configuration options for the settings UI.

        Returns:
            list: A list of Gramps Option objects representing user-configurable settings.
        """
        self.opts.clear()
        self.add_csv_files_option()
        self.add_enum_option(
            "websearch.middle_name_handling",
            _("Middle Name Handling"),
            SimpleNamespace(
                enum_class=MiddleNameHandling,
                default=DEFAULT_MIDDLE_NAME_HANDLING,
                descriptions={
                    MiddleNameHandling.LEAVE_ALONE.value: _("Leave alone"),
                    MiddleNameHandling.SEPARATE.value: _("Separate"),
                    MiddleNameHandling.REMOVE.value: _("Remove"),
                },
            ),
        )
        self.add_boolean_option(
            "websearch.show_short_url", "Show Shortened URL", DEFAULT_SHOW_SHORT_URL
        )
        self.add_enum_option(
            "websearch.url_compactness_level",
            _("URL Compactness Level"),
            SimpleNamespace(
                enum_class=URLCompactnessLevel,
                default=DEFAULT_URL_COMPACTNESS_LEVEL,
                descriptions={
                    URLCompactnessLevel.SHORTEST.value: _(
                        "Shortest - No Prefix, No Keys"
                    ),
                    URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value: _(
                        "Compact - No Prefix, Keys Without Attributes"
                    ),
                    URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value: _(
                        "Compact - No Prefix, Keys With Attributes"
                    ),
                    URLCompactnessLevel.LONG.value: _(
                        "Long - Without Prefix on the Left"
                    ),
                },
            ),
        )
        self.add_string_option(
            "websearch.url_prefix_replacement",
            _("URL Prefix Replacement"),
            DEFAULT_URL_PREFIX_REPLACEMENT,
        )

        # AI Provider selection (OpenAI, Mistral, etc.)
        self.add_enum_option(
            "websearch.ai_provider",
            _("AI Provider"),
            SimpleNamespace(
                enum_class=AIProviders,
                default=DEFAULT_AI_PROVIDER,
                descriptions={
                    AIProviders.DISABLED.value: _("(Disabled)"),
                    AIProviders.OPENAI.value: _("OpenAI"),
                    AIProviders.MISTRAL.value: _("Mistral AI"),
                },
            ),
        )

        self.add_string_option(
            "websearch.openai_api_key",
            _("OpenAI API Key"),
            "",
        )
        self.add_string_option(
            "websearch.openai_model",
            _("OpenAI Model"),
            "",
        )
        self.add_string_option(
            "websearch.mistral_api_key",
            _("Mistral API Key"),
            "",
        )
        self.add_string_option(
            "websearch.mistral_model",
            _("Mistral Model"),
            "",
        )
        self.add_boolean_option(
            "websearch.show_attribute_links",
            _("Show Links From the 'Attributes' tab"),
            DEFAULT_SHOW_ATTRIBUTE_LINKS,
        )
        self.add_boolean_option(
            "websearch.show_internet_links",
            _("Show Links From the 'Internet' tab"),
            DEFAULT_SHOW_INTERNET_LINKS,
        )
        self.add_boolean_option(
            "websearch.show_note_links",
            _("Show Links From the Notes"),
            DEFAULT_SHOW_INTERNET_LINKS,
        )
        self.add_display_columns_option()
        self.add_display_icons_option()

        return self.opts

    def add_csv_files_option(self):
        """
        Add an option to enable or disable available CSV files for use in WebSearch.
        """
        all_files, selected_files = WebsiteLoader.get_all_and_selected_files(
            self.config_ini_manager
        )

        priority_files = [
            COMMON_CSV_FILE_NAME,
            UID_CSV_FILE_NAME,
            STATIC_CSV_FILE_NAME,
            CROSS_CSV_FILE_NAME,
        ]

        def sort_key(f):
            try:
                return (0, priority_files.index(f))
            except ValueError:
                return (1, f.lower())

        all_files.sort(key=sort_key)

        opt = BooleanListOption(_("Enable CSV Files"))
        for file in all_files:
            opt.add_button(file, file in selected_files)
        self.opts.append(opt)

    def add_display_columns_option(self):
        """Add a list of checkbox options for displaying columns."""
        opt = BooleanListOption(_("Display Columns"))

        selected_columns = self.config_ini_manager.get_list(
            "websearch.display_columns",
            DEFAULT_DISPLAY_COLUMNS,
        )
        for column in ALL_COLUMNS:
            label = ALL_COLUMNS_LOCALIZED.get(column, column)
            opt.add_button(label, column in selected_columns)

        self.opts.append(opt)

    def add_display_icons_option(self):
        """Add a list of checkbox options for displaying icons."""
        opt = BooleanListOption(_("Display Icons"))

        selected_icons = self.config_ini_manager.get_list(
            "websearch.display_icons",
            DEFAULT_DISPLAY_ICONS,
        )
        for icon in ALL_ICONS:
            label = ALL_ICONS_LOCALIZED.get(icon, icon)
            opt.add_button(label, icon in selected_icons)

        self.opts.append(opt)

    def add_boolean_option(self, config_key, label, default):
        """Add a boolean toggle option to the settings."""
        value = self.config_ini_manager.get_boolean_option(config_key, default)
        opt = BooleanOption(label, value)
        self.opts.append(opt)

    def add_enum_option(self, config_key, label, options):
        """Adds an enumerated list option to the settings."""
        enum_class = options.enum_class
        default = options.default
        descriptions = options.descriptions

        opt = EnumeratedListOption(label, default)
        for item in enum_class:
            display_text = (
                descriptions.get(item.value, item.value) if descriptions else item.value
            )
            opt.add_item(item.value, _(display_text))
        opt.set_value(self.config_ini_manager.get_enum(config_key, enum_class, default))
        self.opts.append(opt)

    def add_string_option(self, config_key, label, default=""):
        """Add a string input option to the settings."""
        value = self.config_ini_manager.get_string(config_key, default)
        opt = StringOption(label, value)
        self.opts.append(opt)
