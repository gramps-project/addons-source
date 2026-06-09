# -*- coding: utf-8 -*-
"""
Mappers and translation utilities for Gramps-specific objects.
This module handles the conversion between Gramps internal types
and the domain entities defined in name_processor.entities.
"""

from gramps.gen.lib import Person as GrampsPerson

from NameSuite.name_processor.models.person import Gender


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
