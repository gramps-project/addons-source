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
Provides utilities to extract birth/death events, years, and places
for a given person from the Gramps database.

Delegates event- and place-specific logic to dedicated extractor modules.
"""

import sys
import traceback

from event_data_extractor import EventDataExtractor
from place_data_extractor import PlaceDataExtractor


class PersonDataExtractor:
    """
    Extracts birth and death event data for a person, including
    dates and associated places, using the Gramps database API.

    Uses EventDataExtractor and PlaceDataExtractor for deeper logic.
    """

    @staticmethod
    def get_birth_event(db, person):
        """Returns the birth event object for the given person."""
        try:
            if person is None:
                return None
            ref = person.get_birth_ref()
            if ref is None:
                return None
            return db.get_event_from_handle(ref.get_reference_handle()) or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    @staticmethod
    def get_death_event(db, person):
        """Returns the death event object for the given person."""
        try:
            ref = person.get_death_ref()
            if ref is None:
                return None
            return db.get_event_from_handle(ref.get_reference_handle()) or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    @staticmethod
    def get_birth_year(db, person):
        """Returns the exact birth year from a person's birth event."""
        event = PersonDataExtractor.get_birth_event(db, person)
        return EventDataExtractor.get_event_exact_year(event)

    @staticmethod
    def get_death_year(db, person):
        """Returns the exact year of the person's death."""
        event = PersonDataExtractor.get_death_event(db, person)
        return EventDataExtractor.get_event_exact_year(event)

    @staticmethod
    def get_birth_years(db, person):
        """Returns different birth year formats from the person's birth event."""
        event = PersonDataExtractor.get_birth_event(db, person)
        year, year_from, year_to, year_before, year_after = (
            EventDataExtractor.get_event_years(event)
        )
        return year, year_from, year_to, year_before, year_after

    @staticmethod
    def get_death_years(db, person):
        """Returns different death year formats from the person's death event."""
        event = PersonDataExtractor.get_death_event(db, person)
        year, year_from, year_to, year_before, year_after = (
            EventDataExtractor.get_event_years(event)
        )
        return year, year_from, year_to, year_before, year_after

    @staticmethod
    def get_birth_place(db, person):
        """Returns the place name associated with the person's birth."""
        event = PersonDataExtractor.get_birth_event(db, person)
        place = EventDataExtractor.get_event_place(db, event)
        return PlaceDataExtractor.get_place_name(place)

    @staticmethod
    def get_birth_root_place(db, person):
        """Returns the root place name from the person's birth event."""
        event = PersonDataExtractor.get_birth_event(db, person)
        place = EventDataExtractor.get_event_place(db, event)
        return PlaceDataExtractor.get_root_place_name(db, place)

    @staticmethod
    def get_death_place(db, person):
        """Returns the place name associated with the person's death."""
        event = PersonDataExtractor.get_death_event(db, person)
        place = EventDataExtractor.get_event_place(db, event)
        return PlaceDataExtractor.get_place_name(place)

    @staticmethod
    def get_death_root_place(db, person):
        """Returns the root place name from the person's death event."""
        event = PersonDataExtractor.get_death_event(db, person)
        place = EventDataExtractor.get_event_place(db, event)
        return PlaceDataExtractor.get_root_place_name(db, place)
