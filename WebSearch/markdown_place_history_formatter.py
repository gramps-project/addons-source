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
Module for formatting historical administrative divisions information into Markdown.

This module contains the `MarkdownPlaceHistoryFormatter` class, which is a concrete implementation
of the abstract `PlaceHistoryFormatter`. It is responsible for formatting historical administrative
divisions data for a given place into Markdown format. The formatted output includes details such
as foundation date, geographical coordinates, administrative history periods, and additional
metadata provided to AI. The data is displayed with localized labels and structured in a
human-readable way.
"""

from models import PlaceHistoryRequestData
from place_history_formatter import PlaceHistoryFormatter
from translation_helper import _
from helpers import format_iso_datetime


class MarkdownPlaceHistoryFormatter(PlaceHistoryFormatter):
    """
    Concrete implementation of PlaceHistoryFormatter that formats data into Markdown.
    """

    def format(
        self, results, data: PlaceHistoryRequestData, place_history_record
    ) -> str:
        """
        Format the historical administrative divisions information for a place in Markdown format.
        """
        if not results:
            return _("No data available.")

        parts = []

        # Prepare localized labels
        title_label = _("HISTORICAL ADMINISTRATIVE DIVISIONS OF")
        foundation_date_label = _("Foundation date:")
        note_label = _("Note:")
        coordinates_label = _("Coordinates:")
        admin_history_label = _("Administrative history")
        data_provided_label = _("Data provided to AI:")
        name_label = _("Name")
        hierarchy_label = _("Full hierarchy")
        language_label = _("Language")
        latitude_label = _("Latitude")
        longitude_label = _("Longitude")
        place_type_label = _("Place Type:")
        request_time_label = _("Last Retrieved At:")

        # Title
        place_name = data.name
        parts.append(f"# 🏙️ {title_label} {place_name.upper()}")
        parts.append("")

        # Foundation info
        foundation_info = results.get("foundation_info", {})
        foundation_date = foundation_info.get("foundation_date", "")
        foundation_comment = foundation_info.get("foundation_comment", "")
        if foundation_date:
            parts.append(f"📅 **{foundation_date_label}** {foundation_date}")
        if foundation_comment:
            parts.append(f"💬 **{note_label}** {foundation_comment}")

        # Coordinates
        location_info = results.get("location_info", {})
        latitude = location_info.get("latitude", "")
        longitude = location_info.get("longitude", "")
        if latitude and longitude:
            map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
            parts.append(
                f"📍 {coordinates_label} [{latitude}, {longitude}]({map_link})"
            )

        place_type = results.get("place_type", _("Unknown"))
        parts.append(f"🔠 **{place_type_label}** {place_type}")
        formatted_updated_at = format_iso_datetime(
            place_history_record.get("updated_at")
        )
        parts.append(f"⏰ **{request_time_label}** {formatted_updated_at}")
        parts.append("")
        parts.append(f"## 🗺 {admin_history_label}")
        parts.append("")

        # History periods
        history = results.get("history", [])
        for item in history:
            date_from = item.get("date_from", "")
            date_to = item.get("date_to", "")
            division = item.get("administrative_division", "")
            comment = item.get("comment", "").strip()

            parts.append(f"✦ **{date_from} → {date_to}**")
            parts.append(f"  ↳ {division}")
            if comment:
                parts.append(f"     📝 *{comment}*")
            parts.append("")

        # Footer: input place_data info
        parts.append("")
        parts.append("────────────────────────────")
        parts.append("")
        parts.append(f"##### {data_provided_label}")
        parts.append(f"{self.small_key_value(name_label, data.name)}")
        parts.append(f"{self.small_key_value(hierarchy_label, data.full_hierarchy)}")
        parts.append(f"{self.small_key_value(language_label, data.language)}")
        parts.append(f"{self.small_key_value(latitude_label, data.latitude)}")
        parts.append(f"{self.small_key_value(longitude_label, data.longitude)}")

        return "\n".join(parts)

    def small_key_value(self, key: str, value: str) -> str:
        """
        Format a key-value pair for footer block with small text.

        Example output:
        {small|**Name:** Piryatin}
        """
        return f"{{small_bold|{key}:}} {{small|{value}}}"
