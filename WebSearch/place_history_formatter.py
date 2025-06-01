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
Module for defining the abstract base class for formatting place history data.

This module contains the `PlaceHistoryFormatter` abstract class, which defines the interface
for formatting historical administrative divisions information for a place. Concrete subclasses
should implement the `format` method to return the formatted string representation of the
place history.

The `PlaceHistoryFormatter` class provides the foundation for different formatting strategies.
"""

from abc import ABC, abstractmethod


class PlaceHistoryFormatter(ABC):
    """
    Abstract base class for formatting place history data.
    """

    @abstractmethod
    def format(self, results, data, place_history_record) -> str:
        """
        Method to format historical administrative divisions information for a place.

        Args:
            results (dict):
                Historical data containing foundation information, location,
                administrative periods, and other metadata.
            data (PlaceHistoryRequestData):
                Basic information about the place, such as name, language, coordinates, etc.
            place_history_record (dict):
                Record from the database containing file path, event identifiers,
                timestamps, and potentially additional metadata linked to the place.
        """
