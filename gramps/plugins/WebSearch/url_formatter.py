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
This module provides the UrlFormatter class used to generate compact, readable URLs
for genealogy search links in the WebSearch Gramplet.

It includes logic for trimming, simplifying, and reconstructing URLs based on
user preferences and key replacement patterns.
"""

import re

from constants import (
    DEFAULT_QUERY_PARAMETERS_REPLACEMENT,
    DEFAULT_SHOW_SHORT_URL,
    DEFAULT_URL_COMPACTNESS_LEVEL,
    DEFAULT_URL_PREFIX_REPLACEMENT,
    URL_PREFIXES_TO_TRIM,
    URLCompactnessLevel,
)


class UrlFormatter:
    """
    UrlFormatter class for formatting genealogy-related search URLs.

    This class provides methods to process and format URLs for genealogy search queries.
    It removes unnecessary query parameters, trims prefixes, and compacts URLs based on
    user-defined settings.

    Key Features:
    - Supports multiple URL compactness levels (shortest, compact, long).
    - Removes query parameters for a cleaner URL representation.
    - Allows prefix replacement for better readability.
    - Extracts and validates pattern keys within URL templates.

    Attributes:
    - config_ini_manager: Manages configuration settings for URL formatting.

    Methods:
    - format(url, keys): Formats the given URL based on user settings.
    - format_shortest(url): Returns a trimmed URL with removed query parameters.
    - format_compact_no_attributes(url, keys): Compacts URL while keeping only
      relevant keys.
    - format_compact_with_attributes(url, keys): Compacts URL, keeping both
      keys and attributes.
    - format_long(url): Returns the full URL with trimmed prefixes.
    - trim_url_prefix(url): Removes unnecessary prefixes from URLs.
    - remove_url_query_params(url): Strips query parameters from the URL.
    - append_keys_to_url(url, keys, show_attribute): Appends formatted
      keys to the URL.
    - check_pattern_keys(url_pattern, data): Checks and validates pattern
      keys in URL templates.
    """

    def __init__(self, config_ini_manager):
        """
        Initialize the UrlFormatter with a config manager.

        Args:
            config_ini_manager: An instance of ConfigINIManager for retrieving settings.
        """
        self.config_ini_manager = config_ini_manager
        self.init(self.config_ini_manager)

    def init(self, config_ini_manager):
        """
        Initialize internal keys based on configuration settings.

        Args:
            config_ini_manager: The configuration manager object.
        """
        self.__show_short_url = config_ini_manager.get_boolean_option(
            "websearch.show_short_url", DEFAULT_SHOW_SHORT_URL
        )
        self.__url_compactness_level = config_ini_manager.get_enum(
            "websearch.url_compactness_level",
            URLCompactnessLevel,
            DEFAULT_URL_COMPACTNESS_LEVEL,
        )
        self.__url_prefix_replacement = config_ini_manager.get_string(
            "websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT
        )

    def format(self, url, keys):
        """
        Format the URL based on the selected compactness level and settings.

        Args:
            url (str): The original URL to format.
            keys (dict): A dictionary of keys to include in the formatted URL.

        Returns:
            str: The formatted URL.
        """
        self.init(self.config_ini_manager)

        if not self.__show_short_url or not self.__url_compactness_level:
            return url

        if self.__url_compactness_level == URLCompactnessLevel.SHORTEST.value:
            return self.format_shortest(url)

        if (
            self.__url_compactness_level
            == URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value
        ):
            return self.format_compact_no_attributes(url, keys)

        if (
            self.__url_compactness_level
            == URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value
        ):
            return self.format_compact_with_attributes(url, keys)

        if self.__url_compactness_level == URLCompactnessLevel.LONG.value:
            return self.format_long(url)

        return url

    def format_shortest(self, url):
        """
        Return the shortest version of the URL by removing prefixes and query parameters.

        Args:
            url (str): The original URL.

        Returns:
            str: The shortest formatted URL.
        """
        return self.remove_url_query_params(self.trim_url_prefix(url))

    def format_compact_no_attributes(self, url, keys):
        """
        Format the URL compactly with keys, excluding attribute names.

        Args:
            url (str): The original URL.
            keys (dict): Dictionary containing keys to append.

        Returns:
            str: The compact URL.
        """
        clean_url = self.remove_url_query_params(self.trim_url_prefix(url))
        return self.append_keys_to_url(clean_url, keys, False)

    def format_compact_with_attributes(self, url, keys):
        """
        Format the URL compactly with keys and their attribute names.

        Args:
            url (str): The original URL.
            keys (dict): Dictionary containing keys to append.

        Returns:
            str: The compact URL.
        """
        clean_url = self.remove_url_query_params(self.trim_url_prefix(url))
        return self.append_keys_to_url(clean_url, keys, True)

    def format_long(self, url):
        """
        Return the full version of the URL with trimmed prefix.

        Args:
            url (str): The original URL.

        Returns:
            str: The long format URL.
        """
        return self.trim_url_prefix(url)

    def trim_url_prefix(self, url):
        """
        Trim the protocol and www prefix from a URL.

        Args:
            url (str): The original URL.

        Returns:
            str: The URL without common prefixes.
        """
        for prefix in URL_PREFIXES_TO_TRIM:
            if url.startswith(prefix):
                return self.__url_prefix_replacement + url[len(prefix) :]
        return url

    def remove_url_query_params(self, url):
        """
        Remove query parameters from the URL (everything after '?').

        Args:
            url (str): The original URL.

        Returns:
            str: URL without query parameters.
        """
        return url.split("?")[0]

    def append_keys_to_url(self, url, keys, show_attribute):
        """
        Append keys to the URL as query-like parameters.

        Args:
            url (str): The base URL.
            keys (dict): Dictionary with a list of replaced_keys.
            show_attribute (bool): Whether to include key names in the output.

        Returns:
            str: The URL with appended keys.
        """
        replaced_keys = keys.get("replaced_keys", [])
        if replaced_keys:
            formatted_keys = []
            for var in replaced_keys:
                for key, value in var.items():
                    formatted_keys.append(
                        f"{key}={value}" if show_attribute else f"{value}"
                    )
            return (
                url
                + DEFAULT_QUERY_PARAMETERS_REPLACEMENT
                + DEFAULT_QUERY_PARAMETERS_REPLACEMENT.join(formatted_keys)
            )
        return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT

    def check_pattern_keys(self, url_pattern, data):
        """
        Check which keys in the URL pattern exist and are non-empty.

        Args:
            url_pattern (str): A URL template string with placeholders.
            data (dict): Dictionary with available data values.

        Returns:
            dict: A dictionary containing replaced, missing, and empty keys.
        """
        pattern_keys = re.findall(r"%\((.*?)\)s", url_pattern)

        replaced_keys = []
        not_found_keys = []
        empty_keys = []

        for key in pattern_keys:
            value = data.get(key)
            if value is None:
                not_found_keys.append(key)
            elif value == "":
                empty_keys.append(key)
            else:
                replaced_keys.append({key: value})

        return {
            "replaced_keys": replaced_keys,
            "not_found_keys": not_found_keys,
            "empty_keys": empty_keys,
        }
