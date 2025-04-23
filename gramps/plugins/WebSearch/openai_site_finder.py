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
Provides the OpenaiSiteFinder class, which uses OpenAI to suggest genealogy-related
websites in JSON format.
"""

import sys
import traceback

try:
    import openai
except ImportError:
    print(
        "⚠ OpenAI module is missing. Install it using: `pip install openai`.",
        file=sys.stderr,
    )

from site_finder_prompt import BasePromptBuilder
from models import AIDomainData


# pylint: disable=too-few-public-methods
class OpenaiSiteFinder:
    """
    OpenaiSiteFinder class for retrieving genealogy-related websites using OpenAI.

    This class interacts with OpenAI's API to fetch a list of genealogy research websites
    while excluding certain domains and filtering results based on locale preferences.
    """

    def __init__(self, api_key, model):
        """Initialize the OpenaiSiteFinder with an OpenAI API key."""
        self.api_key = api_key
        self.model = model
        self.prompt_builder = BasePromptBuilder()

    def find_sites(self, ai_domain_data: AIDomainData):
        """Query OpenAI to find genealogy research websites."""

        system_message, user_message = self.prompt_builder.build_prompt(ai_domain_data)

        try:
            client = openai.OpenAI(api_key=self.api_key)
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
            )
            return completion.choices[0].message.content
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return "[]"
