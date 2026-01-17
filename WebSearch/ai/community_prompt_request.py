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
Module for handling Site Prompt Requests for AI-based queries.

This module defines the `SitePromptRequest` class, which handles the creation of prompts
for generating AI responses related to genealogy site suggestions. It builds and sends the request,
and processes the response from the AI provider.
"""

import sys
import json

from ai.base_request import BaseRequest
from ai.community_prompt_builder import CommunityPromptBuilder
from models import AIUrlData


class CommunityPromptRequest(BaseRequest):
    """
    Class for handling site prompt requests to an AI provider.

    This class is responsible for constructing prompts based on domain data and sending them to
    an AI service. It also processes the AI responses and returns the relevant site data.

    Attributes:
        data (AIUrlData): The domain data used to generate the prompt.
        prompt_builder (SitePromptBuilder): A builder used to create the prompt for the AI.
    """

    def __init__(self, data: AIUrlData, prompt_builder: CommunityPromptBuilder):
        """Initialize the SitePromptRequest with domain data and a prompt builder."""
        self.data = data
        self.prompt_builder = prompt_builder

    def build_prompt(self):
        """Build the prompt for the AI provider using the provided prompt builder."""
        return self.prompt_builder.build_prompt(self.data)

    def parse_response(self, response: str):
        """Parse the response from the AI provider and extract the relevant site data."""
        try:
            data = json.loads(response)
            if not isinstance(data, dict):
                print(
                    "❌ Error. Invalid JSON structure: expected a JSON object.", file=sys.stderr
                )
                return []

            if not data:
                return []

            sites = data.get("sites")
            if isinstance(sites, list):
                return sites

            print("❌ Error. 'sites' key missing or invalid.", file=sys.stderr)
            return []
        except json.JSONDecodeError:
            print("❌ Error. Failed to decode JSON.", file=sys.stderr)
            return []

    def task_id(self):
        """Get the task identifier for the site prompt request."""
        return "site_prompts"
