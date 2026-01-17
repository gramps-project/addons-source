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
Module that defines the `PlaceHistoryRequest` class, responsible for constructing
requests for historical administrative data related to a specific place.

This module contains the `PlaceHistoryRequest` class, which is used to create a request
for generating the historical administrative divisions of a place. The class makes use
of the `PlaceHistoryPromptBuilder` to generate the AI prompt and the `PlaceHistoryRequestData`
to provide the relevant data for constructing the prompt.

The class also provides methods for parsing the AI response and validating the required
fields (`foundation_info` and `history`) in the JSON response. The task ID is used to
identify this specific type of request.

Functions in this module allow for the building, sending, and processing of requests
to the AI for generating administrative history data about locations.
"""

import json

from ai.base_request import BaseRequest
from ai.place_history_prompt_builder import PlaceHistoryPromptBuilder
from models import PlaceHistoryRequestData


class PlaceHistoryRequest(BaseRequest):
    """
    Class that constructs a request to retrieve historical administrative data for a place.

    This class is responsible for building a prompt using the `PlaceHistoryPromptBuilder`
    and sending it to the AI service for generating historical administrative divisions of
    a specific place. The class also validates the response from the AI to ensure it contains
    the required data fields.
    """

    def __init__(
        self,
        place_history_request_data: PlaceHistoryRequestData,
        prompt_builder: PlaceHistoryPromptBuilder,
    ):
        """
        Initializes a PlaceHistoryRequest object with the provided place data and prompt builder.
        """
        self.place_history_request_data = place_history_request_data
        self.prompt_builder = prompt_builder

    def build_prompt(self):
        """Builds the system and user messages for the AI request."""
        return self.prompt_builder.build_prompt(self.place_history_request_data)

    def parse_response(self, response: str):
        """
        Parses the AI response and validates the presence of required fields.
        The method checks if the response contains the fields 'foundation_info' and 'history',
        both of which are required for processing the place's historical data. If the response
        is invalid or does not contain these fields, it returns an empty dictionary.
        """
        try:
            data = json.loads(response)
            if not isinstance(data, dict):
                raise ValueError(
                    "Expected a JSON object with 'foundation_info' and 'history' fields."
                )
            if "foundation_info" not in data or "history" not in data:
                raise ValueError(
                    "Missing required 'foundation_info' or 'history' fields."
                )
            return data
        except json.JSONDecodeError:
            return {}

    def task_id(self):
        """Returns the unique task ID for this request."""
        return "place_history"
