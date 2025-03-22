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

import re
from constants import *

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
    - Extracts and validates pattern variables within URL templates.

    Attributes:
    - config_ini_manager: Manages configuration settings for URL formatting.

    Methods:
    - format(url, variables): Formats the given URL based on user settings.
    - format_shortest(url): Returns a trimmed URL with removed query parameters.
    - format_compact_no_attributes(url, variables): Compacts URL while keeping only relevant variables.
    - format_compact_with_attributes(url, variables): Compacts URL, keeping both variables and attributes.
    - format_long(url): Returns the full URL with trimmed prefixes.
    - trim_url_prefix(url): Removes unnecessary prefixes from URLs.
    - remove_url_query_params(url): Strips query parameters from the URL.
    - append_variables_to_url(url, variables, show_attribute): Appends formatted variables to the URL.
    - check_pattern_variables(url_pattern, data): Checks and validates pattern variables in URL templates.
    """
    def __init__(self, config_ini_manager):
        self.config_ini_manager = config_ini_manager
        self.init(self.config_ini_manager)

    def init(self, config_ini_manager):
        self.__show_short_url = config_ini_manager.get_boolean_option("websearch.show_short_url", DEFAULT_SHOW_SHORT_URL)
        self.__url_compactness_level = config_ini_manager.get_enum("websearch.url_compactness_level", URLCompactnessLevel, DEFAULT_URL_COMPACTNESS_LEVEL)
        self.__url_prefix_replacement = config_ini_manager.get_string("websearch.url_prefix_replacement", DEFAULT_URL_PREFIX_REPLACEMENT)

    def format(self, url, variables):
        self.init(self.config_ini_manager)

        if not self.__show_short_url or not self.__url_compactness_level:
            return url

        if self.__url_compactness_level == URLCompactnessLevel.SHORTEST.value:
            return self.format_shortest(url)
        elif self.__url_compactness_level == URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value:
            return self.format_compact_no_attributes(url, variables)
        elif self.__url_compactness_level == URLCompactnessLevel.COMPACT_WITH_ATTRIBUTES.value:
            return self.format_compact_with_attributes(url, variables)
        elif self.__url_compactness_level == URLCompactnessLevel.LONG.value:
            return self.format_long(url)

        return url

    def format_shortest(self, url):
        return self.remove_url_query_params(self.trim_url_prefix(url))

    def format_compact_no_attributes(self, url, variables):
        clean_url = self.remove_url_query_params(self.trim_url_prefix(url))
        return self.append_variables_to_url(clean_url, variables, False)

    def format_compact_with_attributes(self, url, variables):
        clean_url = self.remove_url_query_params(self.trim_url_prefix(url))
        return self.append_variables_to_url(clean_url, variables, True)

    def format_long(self, url):
        return self.trim_url_prefix(url)

    def trim_url_prefix(self, url):
        for prefix in URL_PREFIXES_TO_TRIM:
            if url.startswith(prefix):
                return self.__url_prefix_replacement + url[len(prefix):]
        return url

    def remove_url_query_params(self, url):
        return url.split('?')[0]

    def append_variables_to_url(self, url, variables, show_attribute):
        replaced_variables = variables.get('replaced_variables', [])
        if replaced_variables:
            formatted_vars = []
            for var in replaced_variables:
                for key, value in var.items():
                    formatted_vars.append(f"{key}={value}" if show_attribute else f"{value}")
            return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT + DEFAULT_QUERY_PARAMETERS_REPLACEMENT.join(formatted_vars)
        return url + DEFAULT_QUERY_PARAMETERS_REPLACEMENT

    def check_pattern_variables(self, url_pattern, data):
        pattern_variables = re.findall(r"%\((.*?)\)s", url_pattern)

        replaced_variables = []
        not_found_variables = []
        empty_variables = []

        for variable in pattern_variables:
            value = data.get(variable)
            if value is None:
                not_found_variables.append(variable)
            elif value == "":
                empty_variables.append(variable)
            else:
                replaced_variables.append({variable: value})

        return {
           "replaced_variables": replaced_variables,
           "not_found_variables": not_found_variables,
           "empty_variables": empty_variables,
       }