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
Provides utility methods to extract structured date-related information
from Gramps event objects, such as exact year, date spans, and modifiers.
"""

import sys
import traceback

from gramps.gen.lib import Date


class EventDataExtractor:
    """
    Extracts and interprets date information from Gramps Event objects,
    including exact year, year ranges, and modifiers like 'before' or 'after'.
    """

    @staticmethod
    def get_event_place(db, event):
        """Returns the place object associated with the given event."""
        try:
            if event is None:
                return None
            place_ref = event.get_place_handle()
            if not place_ref:
                return None
            return db.get_place_from_handle(place_ref) or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            return None

    @staticmethod
    def get_event_exact_year(event):
        """Returns the exact year from a non-compound event date."""
        try:
            if event is None:
                return None
            date = event.get_date_object()
            if date and not date.is_compound():
                return date.get_year() or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
        return None

    @staticmethod
    def get_event_years(event):
        """Returns a tuple of year values extracted from an event's date object."""
        year = None
        year_from = None
        year_to = None
        year_before = None
        year_after = None

        if not event:
            return year, year_from, year_to, year_before, year_after
        date = event.get_date_object()
        if not date or date.is_empty():
            return year, year_from, year_to, year_before, year_after
        try:
            modifier = date.get_modifier()
            if modifier in [Date.MOD_NONE, Date.MOD_ABOUT]:
                year = date.get_year() or None
                year_from = date.get_year() or None
                year_to = date.get_year() or None
            if modifier in [Date.MOD_AFTER]:
                year_after = date.get_year() or None
            if modifier in [Date.MOD_BEFORE]:
                year_before = date.get_year() or None
            if modifier in [Date.MOD_SPAN, Date.MOD_RANGE]:
                start_date = date.get_start_date()
                stop_date = date.get_stop_date()
                year_from = start_date[2] if start_date else None
                year_to = stop_date[2] if stop_date else None
            return year, year_from, year_to, year_before, year_after
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
        return year, year_from, year_to, year_before, year_after
