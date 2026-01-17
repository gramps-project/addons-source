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
Provides static methods for extracting structured place-related data from Gramps Place objects.
Includes utilities for accessing coordinates, type, hierarchy, and display title.
"""

import sys
import traceback

from gramps.gen.lib.placetype import PlaceType


class PlaceDataExtractor:
    """
    A collection of static methods to extract place-related information,
    such as latitude, longitude, type, hierarchical names, and titles.
    """

    @staticmethod
    def get_place_latitude(place):
        """Returns the latitude of the place if available."""
        try:
            if place is None:
                return None
            latitude = place.get_latitude()
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return None
        return latitude

    @staticmethod
    def get_place_longitude(place):
        """Returns the longitude of the place if available."""
        try:
            if place is None:
                return None
            longitude = place.get_longitude()
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return None
        return longitude

    @staticmethod
    def get_place_type(place):
        """Returns the place type as a string or XML identifier."""
        try:
            if place is None:
                return None

            place_type = place.get_type()
            if isinstance(place_type, str):
                place_type_value = place_type
            elif isinstance(place_type, PlaceType):
                place_type_value = place_type.xml_str()
            else:
                place_type_value = None

        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return None
        return place_type_value

    @staticmethod
    def get_place_name(place):
        """Returns the primary name value of the given place."""
        try:
            if place is None:
                return None
            name = place.get_name()
            if name is None:
                return None
            value = name.get_value()
            return value or None
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return None

    @staticmethod
    def get_root_place_name(db, place):
        """Returns the root place name by traversing place hierarchy upward."""
        try:
            if place is None:
                return None
            name = place.get_name()
            if name is None:
                return None
            root_place_name = name.get_value()
            place_ref = (
                place.get_placeref_list()[0] if place.get_placeref_list() else None
            )
            while place_ref:
                p = db.get_place_from_handle(place_ref.get_reference_handle())
                if p:
                    root_place_name = p.get_name().get_value()
                    place_ref = (
                        p.get_placeref_list()[0] if p.get_placeref_list() else None
                    )
                else:
                    break
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return None

        return root_place_name

    @staticmethod
    def get_place_title(db, place):
        """Returns a full hierarchical title for the place (including parents)."""
        try:
            if not place:
                return ""
            name = place.get_name()
            if not name:
                return ""
            place_names = [name.get_value()]
            place_ref = (
                place.get_placeref_list()[0] if place.get_placeref_list() else None
            )
            while place_ref:
                parent_place = db.get_place_from_handle(
                    place_ref.get_reference_handle()
                )
                if parent_place:
                    place_names.append(parent_place.get_name().get_value())
                    place_ref = (
                        parent_place.get_placeref_list()[0]
                        if parent_place.get_placeref_list()
                        else None
                    )
                else:
                    break

            return ", ".join(place_names) if place_names else ""
        except Exception:  # pylint: disable=broad-exception-caught
            print(traceback.format_exc(), file=sys.stderr)
            return ""
