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
Provides the MistralSiteFinder class, which uses Mistral AI to suggest genealogy-related
websites in JSON format.
"""

import sys
import traceback

from site_finder_prompt import BasePromptBuilder
from models import AIDomainData


# pylint: disable=too-few-public-methods
class MistralSiteFinder:
    """
    MistralSiteFinder class for retrieving genealogy-related websites using Mistral AI.

    This class interacts with Mistral's API to fetch a list of genealogy research websites
    while excluding certain domains and filtering results based on locale preferences.
    """

    def __init__(self, api_key, model):
        """Initialize the MistralSiteFinder with a Mistral API key."""
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.prompt_builder = BasePromptBuilder()

    def find_sites(self, ai_domain_data: AIDomainData):
        """Query Mistral to find genealogy research websites."""

        try:
            import requests
        except ImportError:
            print(
                "⚠ The 'requests' module is missing. Install it using: `pip install requests`.",
                file=sys.stderr,
            )
            return "[]"

        system_message, user_message = self.prompt_builder.build_prompt(ai_domain_data)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
        }

        try:
            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return "[]"
