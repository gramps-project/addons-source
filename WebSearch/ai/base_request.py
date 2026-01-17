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
Module defining the abstract base class for requests that interact with AI services.

This module includes the `BaseRequest` class, which serves as the base class for all request
classes that handle interaction with AI services. It defines essential methods for building
prompts, parsing responses, and obtaining task IDs, which must be implemented by subclasses.
"""

from abc import ABC, abstractmethod


class BaseRequest(ABC):
    """
    Abstract base class for handling requests to AI services.

    This class defines the necessary interface for making requests to AI services, including
    building prompts, parsing responses, and identifying task IDs. Any AI request class should
    inherit from this base class and implement these methods.
    """

    @abstractmethod
    def build_prompt(self) -> tuple[str, str]:
        """
        Build the system and user messages to be sent to the AI service.
        This method should construct the necessary prompts for interacting with the AI service.
        """

    @abstractmethod
    def parse_response(self, response: str):
        """
        Parse the response from the AI service.
        This method processes the raw response returned by the AI service, extracting
        and formatting relevant information.
        """

    @abstractmethod
    def task_id(self) -> str:
        """
        Get the unique task ID associated with the AI request.
        This method returns the task ID for tracking the AI request's progress or results.
        """
