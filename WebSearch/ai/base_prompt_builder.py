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
Abstract base class for constructing prompts for AI interactions.

This class serves as the base for all prompt builder classes that interact with AI services.
It defines the required interface for creating system and user messages to send to the AI,
as well as a method to combine them into a complete prompt.

Classes inheriting from `BasePromptBuilder` must implement the methods for generating
the system and user messages specific to their use case.
"""

from abc import ABC, abstractmethod


class BasePromptBuilder(ABC):
    """
    Abstract base class for constructing prompts for AI interactions.

    This class defines the common interface and structure for building system and user messages
    that are used to interact with AI services. Any subclass must implement the methods for
    generating specific system and user messages. The class also provides a method for combining
    those messages into a complete prompt.
    """

    @abstractmethod
    def get_system_message(self) -> str:
        """Generate the system message for the AI prompt."""

    @abstractmethod
    def get_user_message(self, data) -> str:
        """Generate the user message for the AI prompt."""

    def build_prompt(self, data):
        """Combines the system and user messages into a full prompt."""
        return self.get_system_message(), self.get_user_message(data)
