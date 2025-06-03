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
Module for interacting with the Mistral AI API to handle requests for generating AI responses.

This module defines the `MistralAIClient` class, which provides the functionality to send
requests to the Mistral AI service and retrieve generated responses related to the provided prompts.
"""

import sys
import traceback

from ai.base_request import BaseRequest


# pylint: disable=too-few-public-methods
class MistralAIClient:
    """
    Client for interacting with the Mistral AI service.

    This class is responsible for sending requests to the Mistral API for generating AI responses.
    It manages the API key, model, and communication with the Mistral API endpoint.

    Attributes:
        api_key (str): The API key used to authenticate requests with the Mistral API.
        model (str): The model to be used by the Mistral API for generating responses.
        api_url (str): The base URL for the Mistral API's chat completions endpoint.
    """

    def __init__(self, api_key, model):
        """Initialize the Mistral AI client with the provided API key and model."""
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.mistral.ai/v1/chat/completions"

    def request(self, base_request: BaseRequest):
        """
        Send a request to the Mistral API and retrieve the generated response.

        This method constructs the necessary payload, sends a POST request to the Mistral API,
        and processes the response. If an error occurs, it returns an empty response.
        """
        try:
            import requests  # pylint: disable=import-outside-toplevel
        except ImportError:
            return base_request.parse_response("{}")

        try:

            system_msg, user_msg = base_request.build_prompt()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
            }

            response = requests.post(
                self.api_url, json=payload, headers=headers, timeout=60
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data["choices"][0]["message"]["content"]

            if not raw_text or not raw_text.strip():
                print("❌ Error. Received empty response from AI.", file=sys.stderr)
                return base_request.parse_response("{}")

            return base_request.parse_response(raw_text)

        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return base_request.parse_response("{}")
