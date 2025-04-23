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
This module provides the ModelRowGenerator class, responsible for generating
data rows for the GTK ListStore model in the WebSearch Gramplet.

The class utilizes website data and common entity data to produce structured
rows that include icons, formatted URLs, and metadata necessary for display.
"""

import json
import os
import re
import sys
import traceback

from gi.repository import GdkPixbuf

from constants import (
    CATEGORY_ICON,
    DEFAULT_CATEGORY_ICON,
    DEFAULT_DISPLAY_ICONS,
    FLAGS_DIR,
    HIDDEN_HASH_FILE_PATH,
    ICON_ATTRIBUTE_PATH,
    ICON_CROSS_PATH,
    ICON_EARTH_PATH,
    ICON_INTERNET_PATH,
    ICON_NOTE_PATH,
    ICON_PIN_PATH,
    ICON_SAVED_PATH,
    ICON_SIZE,
    ICON_UID_PATH,
    ICON_USER_DATA_PATH,
    ICON_VISITED_PATH,
    SAVED_HASH_FILE_PATH,
    SOURCE_TYPE_SORT_ORDER,
    UID_ICON_HEIGHT,
    UID_ICON_WIDTH,
    VISITED_HASH_FILE_PATH,
    SOURCE_TYPES_HIDE_KEYS_COUNT,
    SUPPORTED_SOURCE_TYPE_VALUES,
    SOURCE_TYPES_WITH_FIXED_LINKS,
    SourceTypes,
)
from helpers import is_true
from models import WebsiteEntry, LinkContext


class ModelRowGenerator:
    """
    A utility class to generate formatted rows for the WebSearch Gramplet's ListStore model.

    This class processes website and entity data to generate structured rows,
    including formatted URLs, icons, and metadata for proper display.
    """

    def __init__(self, deps):
        """Initializes the ModelRowGenerator with required dependencies."""
        self.website_loader = deps.website_loader
        self.url_formatter = deps.url_formatter
        self.attribute_loader = deps.attribute_loader
        self.config_ini_manager = deps.config_ini_manager

    def generate(self, link_context: LinkContext, website_data: WebsiteEntry):
        """Generates a structured data row for the ListStore model."""
        # pylint: disable=too-many-locals
        try:
            if website_data.nav_type != link_context.nav_type or not is_true(
                website_data.is_enabled
            ):
                return None

            obj_handle = link_context.obj.get_handle()
            if self.should_be_hidden_link(
                website_data.url_pattern, link_context.nav_type, obj_handle
            ):
                return None

            if website_data.source_type in SOURCE_TYPES_WITH_FIXED_LINKS:
                final_url = formatted_url = website_data.url_pattern
                (
                    pattern_keys_info,
                    pattern_keys_json,
                    replaced_keys_count,
                    total_keys_count,
                ) = self.get_empty_keys()
            else:
                (
                    combined_keys,
                    matched_attribute_keys,
                    pattern_keys_info,
                    pattern_keys_json,
                ) = self.prepare_data_keys(
                    link_context.core_keys,
                    link_context.attribute_keys,
                    website_data.url_pattern,
                )

                final_url, formatted_url = self.prepare_urls(
                    website_data.url_pattern, combined_keys, pattern_keys_info
                )

                website_data.source_type, should_skip = self.evaluate_uid_source_type(
                    website_data.source_type, pattern_keys_info, matched_attribute_keys
                )
                if should_skip:
                    return None

            icon_name = CATEGORY_ICON.get(link_context.nav_type, DEFAULT_CATEGORY_ICON)
            hash_value = self.website_loader.generate_hash(f"{final_url}|{obj_handle}")
            visited_icon, visited_icon_visible = self.get_visited_icon_data(hash_value)
            saved_icon, saved_icon_visible = self.get_saved_icon_data(hash_value)
            user_data_icon, user_data_icon_visible = self.get_user_data_icon_data(
                website_data.is_custom_file
            )
            file_identifier_icon, file_identifier_icon_visible = (
                self.get_file_identifier_icon_data(
                    website_data.country_code, website_data.source_type
                )
            )
            replaced_keys_count = len(pattern_keys_info["replaced_keys"])
            total_keys_count = self.get_total_keys_count(pattern_keys_info)
            keys_color = self.get_keys_color(replaced_keys_count, total_keys_count)
            file_identifier_text = self.get_file_identifier_text(
                website_data.country_code, website_data.source_type
            )
            display_keys_count = self.get_display_keys_count(website_data.source_type)
            file_identifier_sort = self.get_file_identifier_sort(
                website_data.country_code, website_data.source_type
            )

            return {
                "icon_name": icon_name,
                "title": website_data.title,
                "final_url": final_url,
                "comment": website_data.comment,
                "url_pattern": website_data.url_pattern,
                "keys_json": pattern_keys_json,
                "formatted_url": formatted_url,
                "visited_icon": visited_icon,
                "saved_icon": saved_icon,
                "nav_type": link_context.nav_type,
                "visited_icon_visible": visited_icon_visible,
                "saved_icon_visible": saved_icon_visible,
                "obj_handle": obj_handle,
                "replaced_keys_count": replaced_keys_count,
                "total_keys_count": total_keys_count,
                "keys_color": keys_color,
                "user_data_icon": user_data_icon,
                "user_data_icon_visible": user_data_icon_visible,
                "display_keys_count": display_keys_count,
                "file_identifier_text": file_identifier_text,
                "file_identifier_text_visible": not file_identifier_icon_visible,
                "file_identifier_icon": file_identifier_icon,
                "file_identifier_icon_visible": file_identifier_icon_visible,
                "file_identifier_sort": file_identifier_sort,
                "source_type": website_data.source_type,
                "country_code": website_data.country_code,
            }
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return None

    def should_be_hidden_link(self, url_pattern, nav_type, obj_handle):
        """Determine if a link should be skipped based on hidden hash entries."""
        return self.website_loader.has_string_in_file(
            f"{url_pattern}|{obj_handle}|{nav_type}", HIDDEN_HASH_FILE_PATH
        ) or self.website_loader.has_string_in_file(
            f"{url_pattern}|{nav_type}", HIDDEN_HASH_FILE_PATH
        )

    def prepare_data_keys(self, core_keys, attribute_keys, url_pattern):
        """
        Combines core entity keys with matched attribute keys relevant to the URL pattern.
        """
        matched_attribute_keys = self.attribute_loader.add_matching_keys_to_data(
            attribute_keys, url_pattern
        )
        combined_keys = core_keys.copy()
        combined_keys.update(matched_attribute_keys)
        pattern_keys_info = self.url_formatter.check_pattern_keys(
            url_pattern, combined_keys
        )
        pattern_keys_json = json.dumps(pattern_keys_info)
        return (
            combined_keys,
            matched_attribute_keys,
            pattern_keys_info,
            pattern_keys_json,
        )

    def prepare_urls(self, url_pattern, combined_keys, keys):
        """Generate final and formatted URLs using combined keys and pattern keys info."""
        final_url = self.safe_percent_format(url_pattern, combined_keys)
        formatted_url = self.url_formatter.format(final_url, keys)
        return final_url, formatted_url

    def evaluate_uid_source_type(self, source_type, keys, matched_attribute_keys):
        """
        Check if the source_type should be changed to UID and whether the link should be skipped.
        """
        should_skip = False
        final_source_type = source_type
        try:
            replaced_keys_set = {list(var.keys())[0] for var in keys["replaced_keys"]}
            if any(var in replaced_keys_set for var in matched_attribute_keys.keys()):
                final_source_type = SourceTypes.UID.value
            if final_source_type == SourceTypes.UID.value and not replaced_keys_set:
                should_skip = True
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        return final_source_type, should_skip

    def get_empty_keys(self):
        """Return an empty pattern keys dictionary, its JSON, and zero counts."""
        keys = {
            "replaced_keys": [],
            "not_found_keys": [],
            "empty_keys": [],
        }
        return keys, json.dumps(keys), 0, 0

    def get_display_keys_count(self, source_type):
        """Return False if key count display is not needed for this source_type."""
        display_keys_count = True
        if source_type in SOURCE_TYPES_HIDE_KEYS_COUNT:
            display_keys_count = False
        return display_keys_count

    def get_total_keys_count(self, pattern_keys_info):
        """Calculate total number of keys from pattern keys info."""
        return (
            len(pattern_keys_info["not_found_keys"])
            + len(pattern_keys_info["replaced_keys"])
            + len(pattern_keys_info["empty_keys"])
        )

    def get_file_identifier_text(self, country_code, source_type):
        """Return file_identifier text unless it is a special source type (like UID or STATIC)."""

        if country_code:
            return country_code

        if source_type in SUPPORTED_SOURCE_TYPE_VALUES:
            return source_type

        return ""

    def get_keys_color(self, replaced_keys_count, total_keys_count):
        """Determine color based on how many keys were replaced in the URL."""
        keys_color = "black"
        if replaced_keys_count == total_keys_count:
            keys_color = "green"
        elif replaced_keys_count not in (total_keys_count, 0):
            keys_color = "orange"
        elif replaced_keys_count == 0:
            keys_color = "red"
        return keys_color

    def get_file_identifier_sort(self, country_code, source_type):
        """
        Return sorting key for the file_identifier based on predefined source type order.
        Source types take priority if recognized, otherwise fall back to a prefixed country code.
        """
        if source_type in SOURCE_TYPE_SORT_ORDER:
            return SOURCE_TYPE_SORT_ORDER[source_type]

        if country_code:
            return f"Z_{country_code.upper()}"

        return "ZZZ"

    def safe_percent_format(self, template: str, data: dict) -> str:
        """
        Safely replaces %(key)s-style placeholders in the template with values from data.
        Leaves unknown keys untouched and prevents TypeError.
        """

        def replacer(match):
            key = match.group(1)
            return str(data.get(key, f"%({key})s"))

        try:
            pattern = re.compile(r"%\(([a-zA-Z0-9_.-]+)\)s")
            return pattern.sub(replacer, template)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"❌ URL formatting error: {e}\nTemplate: {template}\nData: {data}",
                file=sys.stderr,
            )
            return template

    def get_file_identifier_icon_data(self, country_code, source_type):
        """Returns an appropriate flag or icon based on the country_code and source_type."""

        special_icons = {
            SourceTypes.COMMON.value: ("earth", ICON_EARTH_PATH, ICON_SIZE, ICON_SIZE),
            SourceTypes.STATIC.value: ("pin", ICON_PIN_PATH, ICON_SIZE, ICON_SIZE),
            SourceTypes.CROSS.value: ("cross", ICON_CROSS_PATH, ICON_SIZE, ICON_SIZE),
            SourceTypes.UID.value: (
                "uid",
                ICON_UID_PATH,
                UID_ICON_WIDTH,
                UID_ICON_HEIGHT,
            ),
            SourceTypes.ATTRIBUTE.value: (
                "attribute",
                ICON_ATTRIBUTE_PATH,
                ICON_SIZE,
                ICON_SIZE,
            ),
            SourceTypes.INTERNET.value: (
                "internet",
                ICON_INTERNET_PATH,
                ICON_SIZE,
                ICON_SIZE,
            ),
            SourceTypes.NOTE.value: ("note", ICON_NOTE_PATH, ICON_SIZE, ICON_SIZE),
        }

        if source_type in special_icons:
            icon_name, path, width, height = special_icons[source_type]
            if not self.display_icon(icon_name):
                return None, False
            return self.load_icon(path, width, height, label=source_type)

        if not country_code or not self.display_icon("flag"):
            return None, False

        country_code = country_code.lower()
        flag_filename = f"{country_code}.png"
        flag_path = os.path.join(FLAGS_DIR, flag_filename)
        if os.path.exists(flag_path):
            return self.load_icon(flag_path, ICON_SIZE, ICON_SIZE, label=country_code)

        return None, False

    def load_icon(self, path, width, height, label=""):
        """Try to load and resize an icon. Returns (pixbuf, visible)."""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)
            return pixbuf, True
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"❌ Error loading icon '{path}' {f'for {label}' if label else ''}: {e}",
                file=sys.stderr,
            )
            return None, False

    def get_user_data_icon_data(self, is_custom_file):
        """Returns the user data icon if the entry is from a user-defined source."""
        user_data_icon = None
        user_data_icon_visible = False

        if not self.display_icon("user_data"):
            return user_data_icon, user_data_icon_visible

        if is_custom_file:
            try:
                user_data_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_USER_DATA_PATH, ICON_SIZE, ICON_SIZE
                )
                user_data_icon_visible = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return user_data_icon, user_data_icon_visible

    def get_visited_icon_data(self, hash_value):
        """Returns the visited icon if the URL hash exists in the visited list."""
        visited_icon = None
        visited_icon_visible = False

        if not self.display_icon("visited"):
            return visited_icon, visited_icon_visible

        if self.website_loader.has_hash_in_file(hash_value, VISITED_HASH_FILE_PATH):
            try:
                visited_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_VISITED_PATH, ICON_SIZE, ICON_SIZE
                )
                visited_icon_visible = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return visited_icon, visited_icon_visible

    def get_saved_icon_data(self, hash_value):
        """Returns the saved icon if the URL hash exists in the saved list."""
        saved_icon = None
        saved_icon_visible = False

        if not self.display_icon("saved"):
            return saved_icon, saved_icon_visible

        if self.website_loader.has_hash_in_file(hash_value, SAVED_HASH_FILE_PATH):
            try:
                saved_icon = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    ICON_SAVED_PATH, ICON_SIZE, ICON_SIZE
                )
                saved_icon_visible = True
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"❌ Error loading icon: {e}", file=sys.stderr)
        return saved_icon, saved_icon_visible

    def display_icon(self, icon_name):
        """Check if the given icon is in the list of display icons."""
        self.update_display_icons()
        return icon_name in self._display_icons

    def update_display_icons(self):
        """Returns the current state of the flag icons setting."""
        self._display_icons = self.config_ini_manager.get_list(
            "websearch.display_icons", DEFAULT_DISPLAY_ICONS
        )
