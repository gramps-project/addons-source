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
Module for building AI prompts and handling domain-specific requests for genealogical research.

This module includes the `SitePromptBuilder` class, which constructs the system and user messages
for retrieving genealogical research websites from an AI service. The class supports constructing
prompts based on the provided `AIDomainData`, which includes country codes and domains relevant to
genealogical research.

The module also provides functionality for merging and formatting domain exclusions, as well as
creating a well-structured JSON response for the AI request, ensuring the returned websites conform
to specific criteria.

Key functionalities:
- Building system and user messages for AI interaction
- Structuring genealogical research websites based on country codes and domains
- Returning a clean, well-structured JSON response with the relevant website data
"""

from ai.base_prompt_builder import BasePromptBuilder
from models import AIUrlData


class CommunityPromptBuilder(BasePromptBuilder):
    """
    A concrete implementation of the BasePromptBuilder class that constructs prompts
    for generating genealogical research website suggestions through AI.

    This class handles the construction of system and user messages for the AI, which
    includes gathering and structuring the necessary information for the request.
    """

    def get_system_message(self) -> str:
        return (
            "You assist in finding resources for genealogical research. "
            "Return ONLY a pure JSON object without any markdown formatting, code blocks, "
            "backticks, language tags, or any extra text. "
            "JSON must contain a single key 'sites', where the value is an array of objects. "
            "Each object inside 'sites' must have exactly two keys: 'domain' and 'url'. "
            "Do not include any additional text, explanations, or comments outside the JSON. "
        )

    def get_user_message(self, data: AIUrlData) -> str:
        """Constructs the system message for the AI, instructing it on how to respond."""

        if not data.country_codes:
            country_codes_text = "only globally used"
            country_codes_str = ""
        else:
            country_codes_text = (
                "both regional and globally used" if data.include_global else "regional"
            )
            country_codes_str = ", ".join(sorted(data.country_codes))

        # Skipped urls
        excluded_urls_str = self.get_all_urls(data)

        return (
            f"I am looking for additional genealogical research websites.\n"
            "Return exactly 10 websites, structured inside a JSON object with a key 'sites':\n"
            f"- 10 {country_codes_text} community-curated sources like telegram groups, facebook "
            "groups, reddit threads, discord servers, YouTube channels "
            f"etc. (locales: {country_codes_str}), but excluding any forums, archives etc.\n"
            f"Exclude also the following urls: {excluded_urls_str}.\n"
            "Each item in the 'sites' array must contain exactly two keys: 'domain' and 'url'.\n"
            'Example: {"sites": [{"domain": "example.com", "url": "https://example.com"}]}\n'
            "If no suitable websites are found, return an object with an empty "
            f"array: {{'sites': []}}.\n"
            "Do not include any explanations or extra text outside the JSON object."
        )

    def get_all_urls(self, data: AIUrlData):
        """
        Combines skipped and regular urls into a single formatted string.
        This method merges the sets of skipped and regular urls from the given AIDomainData
        and returns them as a sorted, comma-separated string. If both are empty, returns "none".
        """
        skipped = set(data.skipped_urls or [])
        regular = set(data.community_urls or [])
        all_excluded_urls = skipped | regular

        excluded_urls_str = (
            ", ".join(sorted(all_excluded_urls)) if all_excluded_urls else "none"
        )

        return excluded_urls_str
