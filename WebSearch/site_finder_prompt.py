# ----------------------------------------------------------------------------
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
# ----------------------------------------------------------------------------


"""
This module provides a base class for generating AI prompt messages related to
genealogy website suggestions.

It supports both regular (regional/global) and community-contributed genealogy websites.
The AI is instructed to return exactly 10 relevant websites:
- 5 based on `regular_domains` and `regular_country_codes`
- 5 based on `community_urls` and `community_country_codes`

All results must be returned as a JSON array with strictly defined format.
"""

from models import AIDomainData


class BasePromptBuilder:
    """
    Base class for building AI prompt messages for genealogy website suggestions.

    It uses the provided domain and country data to instruct an AI model to generate
    additional relevant website links, divided equally between regular and community-based sources.
    """

    def get_system_message(self) -> str:
        """
        Returns the system message to guide the AI's behavior.

        This message sets the strict format expectations: a JSON array of objects
        with only 'domain' and 'url' keys and no extra explanations.
        """
        return (
            "You assist in finding resources for genealogical research. "
            "Your response must be strictly formatted as a JSON array of objects "
            "with only two keys: 'domain' and 'url'. Do not include any additional text, "
            "explanations, or comments."
        )

    def get_user_message(self, ai_domain_data: AIDomainData) -> str:
        """
        Generates the user-facing prompt that instructs the AI to return genealogy websites.

        The prompt requests:
        - 5 websites based on regular domains and country codes
        - 5 websites based on community URLs and country codes
        - All results must exclude `skipped_domains` if specified

        Args:
            ai_domain_data (AIDomainData): Structured input data including domains, URLs,
                                           country codes, and flags.

        Returns:
            str: The user prompt string for the AI model.
        """

        # Regular section
        if not ai_domain_data.regular_country_codes:
            regular_codes_text = "only globally used"
            regular_codes_str = "none"
        else:
            regular_codes_text = (
                "both regional and globally used"
                if ai_domain_data.include_global
                else "regional"
            )
            regular_codes_str = ", ".join(sorted(ai_domain_data.regular_country_codes))

        # Community section
        if ai_domain_data.community_country_codes:
            community_codes_str = ", ".join(
                sorted(ai_domain_data.community_country_codes)
            )
        else:
            community_codes_str = "none"

        # Skipped domains
        excluded_domains_str = self.get_all_domains(ai_domain_data)

        return (
            f"I am looking for additional genealogical research websites.\n"
            "Please return exactly 10 websites as a JSON array:\n"
            f"- 5 relevant to {regular_codes_text} resources including forums "
            f"(locales: {regular_codes_str})\n"
            f"- 5 based on community-curated sources like groups, channels "
            f"but excluding forums (locales: {community_codes_str})\n"
            f"Exclude the following domains: {excluded_domains_str}.\n"
            "Each item must include only two keys: 'domain' and 'url'.\n"
            'Example: [{"domain": "example.com", "url": "https://example.com"}]\n'
            "If no suitable websites are found, return an empty array: [].\n"
            "Do not include any explanations or extra text in the response."
        )

    def build_prompt(self, ai_domain_data: AIDomainData):
        """Build the full prompt tuple for the AI request."""
        return (
            self.get_system_message(),
            self.get_user_message(ai_domain_data),
        )

    def get_all_domains(self, ai_domain_data: AIDomainData):
        """
        Combines skipped and regular domains into a single formatted string.
        This method merges the sets of skipped and regular domains from the given AIDomainData
        and returns them as a sorted, comma-separated string. If both are empty, returns "none".
        """
        skipped = set(ai_domain_data.skipped_domains or [])
        regular = set(ai_domain_data.regular_domains or [])
        all_excluded_domains = skipped | regular

        excluded_domains_str = (
            ", ".join(sorted(all_excluded_domains)) if all_excluded_domains else "none"
        )

        return excluded_domains_str
