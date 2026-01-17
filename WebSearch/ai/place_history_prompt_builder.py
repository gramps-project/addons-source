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
Module that defines the `PlaceHistoryPromptBuilder` class, which is responsible for
building prompts for generating historical administrative data about a place.

This module provides a concrete implementation of the `BasePromptBuilder` class and
contains the necessary methods for generating system and user messages. The system
message provides context for the AI, and the user message contains detailed instructions
for generating a chronological table of historical administrative divisions.

The class is specifically designed for generating AI-based prompts related to the
reconstruction of the administrative history of locations.

Functions in this module help build and structure the data needed for the AI to generate
accurate and structured historical information, including details like foundation date,
administrative hierarchy, and significant historical periods.
"""

from ai.base_prompt_builder import BasePromptBuilder
from models import PlaceHistoryRequestData


class PlaceHistoryPromptBuilder(BasePromptBuilder):
    """
    A concrete implementation of the `BasePromptBuilder` class responsible for constructing
    prompts related to the administrative history of locations.

    This class builds system and user messages to generate historical administrative
    information using AI. The system message provides context for the AI, and the user message
    contains detailed instructions to construct a chronological table of historical administrative
    divisions.
    """

    def get_system_message(self) -> str:
        return "You are a historian reconstructing the administrative history of locations."

    def get_user_message(self, data: PlaceHistoryRequestData) -> str:
        """
        Generate the AI instruction message for creating a chronological table of historical
        administrative divisions.
        """
        coords_hint = ""
        if data.latitude and data.longitude:
            coords_hint = (
                f" Approximate coordinates to help locate the place: {data.latitude}, "
                f"{data.longitude}."
            )
        language = data.language or "en"

        return (
            f"You are tasked with creating a chronological table of historical administrative "
            f"divisions for the place '{data.name}'.\n"
            f"The currently known full administrative hierarchy of the place "
            f"is: {data.full_hierarchy}.\n"
            f"{coords_hint}\n"
            f"The response must be written entirely in the target language '{language}'.\n"
            f"Search for the most accurate historical and geographical information from reliable "
            f"sources.\n"
            f"Format the response strictly as a pure JSON object without any markdown formatting, "
            f"code blocks, backticks, language tags, or any extra text.\n"
            f"The JSON object must contain exactly four parts:\n"
            f"1. 'foundation_info' (object) with the following fields:\n"
            f"   - foundation_date (string): the founding date of the place. Allowed formats:\n"
            f"       * YYYY (e.g., 1750)\n"
            f"       * YYYY-MM (e.g., 1750-05)\n"
            f"       * YYYY-MM-DD (e.g., 1750-05-12)\n"
            f"       * Century format (e.g., '18th century', 'approximately 17th century' and "
            f"similar with 'before', 'after' words e.t.c.) if no exact date is known.\n"
            f"   - foundation_comment (string): optional, a short comment about the foundation "
            f"(may be empty).\n"
            f"2. 'location_info' (object) with the following fields:\n"
            f"   - latitude (string): the current latitude of the "
            f"place (if known, otherwise empty).\n"
            f"   - longitude (string): the current longitude of the place "
            f"(if known, otherwise empty).\n"
            f"3. 'history' (array of objects), each object must include:\n"
            f"   - date_from (string): the start date of the period (formats: YYYY, YYYY-MM, or "
            f"YYYY-MM-DD).\n"
            f"   - date_to (string): the end date of the period, or 'present' if ongoing"
            f" (formats: YYYY, YYYY-MM, YYYY-MM-DD, or 'present').\n"
            f"   - administrative_division (string): the full description of the administrative "
            f"hierarchy during that period.\n"
            f"   - comment (string): required, a short comment about the period.\n"
            f"     ⚠ The comment must clearly describe what significant change occurred at the "
            f"beginning (date_from) and what significant change occurred at the end (date_to) of "
            f"the period.\n"
            f"     ⚠ Use clear phrasing like 'from ... to ...' to explicitly indicate the changes "
            f"over the period.\n"
            f"4. 'place_type' (string): The administrative type of the place. Choose one of the "
            f"following types and justify your choice based on the known hierarchy and "
            f"geographical data: ['Borough', 'Building', 'City', 'Country', 'County', "
            f"'Department', 'District', 'Farm','Hamlet', 'Locality', 'Municipality', "
            f"'Neighborhood', 'Number', 'Parish', 'Province', 'Region', 'State', 'Street', "
            f"'Town', 'Unknown', 'Village'].\n"
            f"⚠ Important additional requirements:\n"
            f"- Always provide the most precise date available.\n"
            f"- If a major historical event is known (e.g., independence, administrative reform, "
            f"creation of a new administrative unit), you MUST use the full format YYYY-MM-DD.\n"
            f"- If only month and year are known, use YYYY-MM.\n"
            f"- If only year is known, use YYYY.\n"
            f"- The precision of 'date_from' and 'date_to' must match the precision mentioned in "
            f"the comment.\n"
            f"- If coordinates are unknown, leave 'latitude' and 'longitude' fields as empty "
            f"strings.\n"
            f"- All parts of the response — including:\n"
            f"    • Dates in century format (e.g., '17th century') — must be translated "
            f"appropriately.\n"
            f"    • Special keywords such as 'present' — must be translated appropriately.\n"
            f"    • Comments, administrative division names, and phrases like 'from ... to ...' — "
            f"must all be written fully in the target language '{language}'.\n"
            f"    • Only the 'place_type' field must not be translated and must remain "
            f"in English.\n"
            f"- No English words or templates must remain if the target language is different.\n"
            f"- Return only the clean JSON object structured exactly as described, without any "
            f"extra explanations or formatting.\n"
        )
