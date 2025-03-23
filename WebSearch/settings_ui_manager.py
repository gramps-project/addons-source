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
    EnumeratedListOption,
    StringOption,
    BooleanOption,
)

from website_loader import WebsiteLoader
from constants import (
    DEFAULT_MIDDLE_NAME_HANDLING,
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    DEFAULT_USE_OPEN_AI,
    DEFAULT_SHOW_URL_COLUMN,
    DEFAULT_SHOW_VARS_COLUMN,
    DEFAULT_SHOW_USER_DATA_ICON,
    DEFAULT_SHOW_FLAG_ICONS,
    DEFAULT_SHOW_ATTRIBUTE_LINKS,
    MiddleNameHandling,
    URLCompactnessLevel,
)

from translation_helper import _


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
                        "Shortest - No Prefix, No Variables"
                    ),
                    URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value: _(
                        "Compact - No Prefix, Variables Without Attributes"
                    ),
                    URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value: _(
                        "Compact - No Prefix, Variables With Attributes"
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
        self.add_boolean_option(
            "websearch.use_openai", _("Use OpenAI"), DEFAULT_USE_OPEN_AI
        )
        self.add_string_option("websearch.openai_api_key", _("OpenAI API Key"))
        self.add_boolean_option(
            "websearch.show_url_column",
            _("Display 'Website URL' Column"),
            DEFAULT_SHOW_URL_COLUMN,
        )
        self.add_boolean_option(
            "websearch.show_vars_column",
            _("Display 'Vars' Column"),
            DEFAULT_SHOW_VARS_COLUMN,
        )
        self.add_boolean_option(
            "websearch.show_user_data_icon",
            _("Show User Data Icon"),
            DEFAULT_SHOW_USER_DATA_ICON,
        )
        self.add_boolean_option(
            "websearch.show_flag_icons", _("Show Flag Icons"), DEFAULT_SHOW_FLAG_ICONS
        )
        self.add_boolean_option(
            "websearch.show_attribute_links",
            _("Show Links From Attributes"),
            DEFAULT_SHOW_ATTRIBUTE_LINKS,
        )

        return self.opts

    def add_csv_files_option(self):
        """
        Add an option to enable or disable available CSV files for use in WebSearch.
        """
        all_files, selected_files = WebsiteLoader.get_all_and_selected_files(
            self.config_ini_manager
        )
        opt = BooleanListOption(_("Enable CSV Files"))
        for file in all_files:
            opt.add_button(file, file in selected_files)
        self.opts.append(opt)

    def add_boolean_option(self, config_key, label, default):
        """
        Add a boolean toggle option to the settings.

        Args:
            config_key (str): The configuration key.
            label (str): The display label for the option.
            default (bool): The default value.
        """
        value = self.config_ini_manager.get_boolean_option(config_key, default)
        opt = BooleanOption(label, value)
        self.opts.append(opt)

    def add_enum_option(self, config_key, label, options):
        """
        Adds an enumerated list option to the settings.

        This method creates a list of enumerated options and adds them to the settings UI.
        The options are defined by the provided `enum_class`, with an optional description
        for each value.

        Args:
            config_key (str): The configuration key used to store the selected value.
            label (str): The label to display for the option in the UI.
            options (SimpleNamespace): An object containing the following attributes:
                - enum_class (Enum): The enumeration class defining the available options.
                - default: The default value to be selected from the enumeration.
                - descriptions (dict, optional): A dictionary with localized display labels for
                  each enum value. If not provided, the enum values are used as labels.
        """
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
        """
        Add a string input option to the settings.

        Args:
            config_key (str): The configuration key.
            label (str): The display label for the option.
            default (str, optional): The default string value.
        """
        value = self.config_ini_manager.get_string(config_key, default)
        opt = StringOption(label, value)
        self.opts.append(opt)
