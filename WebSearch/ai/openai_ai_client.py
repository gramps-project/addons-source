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
Module for interacting with OpenAI API for AI-based requests.

This module contains the `OpenaiAIClient` class, which handles the communication
with the OpenAI API. It is designed to make a request to OpenAI's API for
generating responses based on input prompts.

Ensure that the OpenAI Python library is installed before using this module.
"""

import sys
import traceback

from ai.base_request import BaseRequest


# pylint: disable=too-few-public-methods
class OpenaiAIClient:
    """
    A client for interacting with the OpenAI API.
    This class provides functionality to send requests to the OpenAI API for
    generating AI responses. It uses an API key and model identifier to authenticate and specify
    the OpenAI model to use.
    """

    def __init__(self, api_key, model):
        """Initialize the OpenAI AI client."""
        self.api_key = api_key
        self.model = model

    def request(self, base_request: BaseRequest):
        """
        Sends a request to the OpenAI API and returns the response.
        This method constructs the prompt using the provided `base_request`, sends it to
        OpenAI's API, and parses the response.
        """
        try:
            import openai  # pylint: disable=import-outside-toplevel
        except ImportError:
            print(
                "⚠ OpenAI module is missing. Install it using: `pip install openai`.",
                file=sys.stderr,
            )
            return base_request.parse_response("{}")

        try:

            client = openai.OpenAI(api_key=self.api_key)
            system_msg, user_msg = base_request.build_prompt()

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
            )

            raw_data_text = response.choices[0].message.content

            if not raw_data_text or not raw_data_text.strip():
                print("❌ Error. Received empty AI response.", file=sys.stderr)
                return base_request.parse_response("{}")

            return base_request.parse_response(raw_data_text)

        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return base_request.parse_response("{}")
