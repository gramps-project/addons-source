#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

"""
Mappers and translation utilities for Gramps-specific objects.
This module handles the conversion between Gramps internal types
and the domain entities defined in name_processor.entities.
"""

from gramps.gen.lib import Person as GrampsPerson

from name_processor.models.person import Gender


def map_gramps_gender_to_person(gramps_gender_int: int) -> Gender:
    """Maps Gramps gender integers to domain Gender enum."""
    gender_map = {
        GrampsPerson.MALE: Gender.MALE,
        GrampsPerson.FEMALE: Gender.FEMALE,
    }
    return gender_map.get(gramps_gender_int, Gender.UNKNOWN)


def map_person_gender_to_gramps(gender: Gender) -> int:
    """Maps domain Gender enum to Gramps gender integers."""
    gender_map = {
        Gender.MALE: GrampsPerson.MALE,
        Gender.FEMALE: GrampsPerson.FEMALE,
    }
    return gender_map.get(gender, GrampsPerson.UNKNOWN)
