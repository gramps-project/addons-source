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
Provides the EntityDataBuilder class for constructing structured data dictionaries
used in WebSearch Gramplet.
"""

import sys
import traceback

from gramps.gen.lib.eventtype import EventType

from helpers import get_system_locale
from person_data_extractor import PersonDataExtractor
from place_data_extractor import PlaceDataExtractor
from event_data_extractor import EventDataExtractor
from attribute_mapping_loader import AttributeMappingLoader

from constants import (
    DEFAULT_MIDDLE_NAME_HANDLING,
    MiddleNameHandling,
    PersonDataKeys,
    FamilyDataKeys,
    PlaceDataKeys,
    SourceDataKeys,
)


class EntityDataBuilder:
    """
    Builds structured data dictionaries for different entity types in Gramps.

    Supports extraction of names, years, places, and attributes from persons,
    families, places, and sources. Designed to support search URL generation
    in the WebSearch Gramplet.
    """

    def __init__(self, dbstate, config_ini_manager):
        self.db = dbstate.db
        self.config_ini_manager = config_ini_manager
        self.system_locale = get_system_locale()
        self.attribute_loader = AttributeMappingLoader()

    def get_person_data(self, person):
        """Extracts structured personal and date-related data from a Person object."""
        try:
            name = person.get_primary_name().get_first_name().strip()
            middle_name_handling = self.config_ini_manager.get_enum(
                "websearch.middle_name_handling",
                MiddleNameHandling,
                DEFAULT_MIDDLE_NAME_HANDLING,
            )

            if middle_name_handling == MiddleNameHandling.SEPARATE.value:
                given, middle = (
                    (name.split(" ", 1) + [None])[:2] if name else (None, None)
                )
            elif middle_name_handling == MiddleNameHandling.REMOVE.value:
                given, middle = (
                    (name.split(" ", 1) + [None])[:2] if name else (None, None)
                )
                middle = None
            elif middle_name_handling == MiddleNameHandling.LEAVE_ALONE.value:
                given, middle = name, None
            else:
                given, middle = name, None

            surname = person.get_primary_name().get_primary().strip() or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            given, middle, surname = None, None, None

        (
            birth_year,
            birth_year_from,
            birth_year_to,
            birth_year_before,
            birth_year_after,
        ) = PersonDataExtractor.get_birth_years(self.db, person)
        (
            death_year,
            death_year_from,
            death_year_to,
            death_year_before,
            death_year_after,
        ) = PersonDataExtractor.get_death_years(self.db, person)

        person_data = {
            PersonDataKeys.GIVEN.value: given or "",
            PersonDataKeys.MIDDLE.value: middle or "",
            PersonDataKeys.SURNAME.value: surname or "",
            PersonDataKeys.BIRTH_YEAR.value: birth_year or "",
            PersonDataKeys.BIRTH_YEAR_FROM.value: birth_year_from or "",
            PersonDataKeys.BIRTH_YEAR_TO.value: birth_year_to or "",
            PersonDataKeys.BIRTH_YEAR_BEFORE.value: birth_year_before or "",
            PersonDataKeys.BIRTH_YEAR_AFTER.value: birth_year_after or "",
            PersonDataKeys.DEATH_YEAR.value: death_year or "",
            PersonDataKeys.DEATH_YEAR_FROM.value: death_year_from or "",
            PersonDataKeys.DEATH_YEAR_TO.value: death_year_to or "",
            PersonDataKeys.DEATH_YEAR_BEFORE.value: death_year_before or "",
            PersonDataKeys.DEATH_YEAR_AFTER.value: death_year_after or "",
            PersonDataKeys.BIRTH_PLACE.value: PersonDataExtractor.get_birth_place(
                self.db, person
            )
            or "",
            PersonDataKeys.BIRTH_ROOT_PLACE.value: PersonDataExtractor.get_birth_root_place(
                self.db, person
            )
            or "",
            PersonDataKeys.DEATH_PLACE.value: PersonDataExtractor.get_death_place(
                self.db, person
            )
            or "",
            PersonDataKeys.DEATH_ROOT_PLACE.value: PersonDataExtractor.get_death_root_place(
                self.db, person
            )
            or "",
            PersonDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        attribute_keys = self.attribute_loader.get_attributes_for_nav_type(
            "Person", person
        )

        return person_data, attribute_keys

    def get_family_data(self, family):
        """Extracts structured data related to a family, including parents and events."""
        father = (
            self.db.get_person_from_handle(family.get_father_handle())
            if family.get_father_handle()
            else None
        )
        mother = (
            self.db.get_person_from_handle(family.get_mother_handle())
            if family.get_mother_handle()
            else None
        )

        father_data, father_attribute_keys = (
            self.get_person_data(father) if father else {}
        )
        mother_data, mother_attribute_keys = (
            self.get_person_data(mother) if mother else {}
        )

        marriage_year = marriage_year_from = marriage_year_to = marriage_year_before = (
            marriage_year_after
        ) = ""
        marriage_place = marriage_root_place = None

        divorce_year = divorce_year_from = divorce_year_to = divorce_year_before = (
            divorce_year_after
        ) = ""
        divorce_place = divorce_root_place = None

        event_ref_list = family.get_event_ref_list()
        for event_ref in event_ref_list:
            event = self.db.get_event_from_handle(event_ref.get_reference_handle())
            event_type = event.get_type()
            event_place = EventDataExtractor.get_event_place(self.db, event)
            event_root_place = PlaceDataExtractor.get_root_place_name(
                self.db, event_place
            )
            if event_type == EventType.MARRIAGE:
                (
                    marriage_year,
                    marriage_year_from,
                    marriage_year_to,
                    marriage_year_before,
                    marriage_year_after,
                ) = EventDataExtractor.get_event_years(event)
                marriage_place = PlaceDataExtractor.get_place_name(event_place)
                marriage_root_place = event_root_place
            if event_type == EventType.DIVORCE:
                (
                    divorce_year,
                    divorce_year_from,
                    divorce_year_to,
                    divorce_year_before,
                    divorce_year_after,
                ) = EventDataExtractor.get_event_years(event)
                divorce_place = PlaceDataExtractor.get_place_name(event_place)
                divorce_root_place = event_root_place

        family_data = {
            FamilyDataKeys.FATHER_GIVEN.value: father_data.get(
                PersonDataKeys.GIVEN.value, ""
            ),
            FamilyDataKeys.FATHER_MIDDLE.value: father_data.get(
                PersonDataKeys.MIDDLE.value, ""
            ),
            FamilyDataKeys.FATHER_SURNAME.value: father_data.get(
                PersonDataKeys.SURNAME.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_FROM.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_TO.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_BEFORE.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_YEAR_AFTER.value: father_data.get(
                PersonDataKeys.BIRTH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR.value: father_data.get(
                PersonDataKeys.DEATH_YEAR.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_FROM.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_TO.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_BEFORE.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_YEAR_AFTER.value: father_data.get(
                PersonDataKeys.DEATH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_PLACE.value: father_data.get(
                PersonDataKeys.BIRTH_PLACE.value, ""
            ),
            FamilyDataKeys.FATHER_BIRTH_ROOT_PLACE.value: father_data.get(
                PersonDataKeys.BIRTH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_PLACE.value: father_data.get(
                PersonDataKeys.DEATH_PLACE.value, ""
            ),
            FamilyDataKeys.FATHER_DEATH_ROOT_PLACE.value: father_data.get(
                PersonDataKeys.DEATH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_GIVEN.value: mother_data.get(
                PersonDataKeys.GIVEN.value, ""
            ),
            FamilyDataKeys.MOTHER_MIDDLE.value: mother_data.get(
                PersonDataKeys.MIDDLE.value, ""
            ),
            FamilyDataKeys.MOTHER_SURNAME.value: mother_data.get(
                PersonDataKeys.SURNAME.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_FROM.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_TO.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_BEFORE.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_YEAR_AFTER.value: mother_data.get(
                PersonDataKeys.BIRTH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_FROM.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_FROM.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_TO.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_TO.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_BEFORE.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_BEFORE.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_YEAR_AFTER.value: mother_data.get(
                PersonDataKeys.DEATH_YEAR_AFTER.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_PLACE.value: mother_data.get(
                PersonDataKeys.BIRTH_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_BIRTH_ROOT_PLACE.value: mother_data.get(
                PersonDataKeys.BIRTH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_PLACE.value: mother_data.get(
                PersonDataKeys.DEATH_PLACE.value, ""
            ),
            FamilyDataKeys.MOTHER_DEATH_ROOT_PLACE.value: mother_data.get(
                PersonDataKeys.DEATH_ROOT_PLACE.value, ""
            ),
            FamilyDataKeys.MARRIAGE_YEAR.value: marriage_year or "",
            FamilyDataKeys.MARRIAGE_YEAR_FROM.value: marriage_year_from or "",
            FamilyDataKeys.MARRIAGE_YEAR_TO.value: marriage_year_to or "",
            FamilyDataKeys.MARRIAGE_YEAR_BEFORE.value: marriage_year_before or "",
            FamilyDataKeys.MARRIAGE_YEAR_AFTER.value: marriage_year_after or "",
            FamilyDataKeys.MARRIAGE_PLACE.value: marriage_place or "",
            FamilyDataKeys.MARRIAGE_ROOT_PLACE.value: marriage_root_place or "",
            FamilyDataKeys.DIVORCE_YEAR.value: divorce_year or "",
            FamilyDataKeys.DIVORCE_YEAR_FROM.value: divorce_year_from or "",
            FamilyDataKeys.DIVORCE_YEAR_TO.value: divorce_year_to or "",
            FamilyDataKeys.DIVORCE_YEAR_BEFORE.value: divorce_year_before or "",
            FamilyDataKeys.DIVORCE_YEAR_AFTER.value: divorce_year_after or "",
            FamilyDataKeys.DIVORCE_PLACE.value: divorce_place or "",
            FamilyDataKeys.DIVORCE_ROOT_PLACE.value: divorce_root_place or "",
            FamilyDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        return family_data

    def get_place_data(self, place):
        """Extracts structured place data such as name, coordinates, and type."""
        place_name = root_place_name = latitude = longitude = place_type = None
        try:
            place_name = PlaceDataExtractor.get_place_name(place)
            root_place_name = PlaceDataExtractor.get_root_place_name(self.db, place)
            place_title = PlaceDataExtractor.get_place_title(self.db, place)
            latitude = PlaceDataExtractor.get_place_latitude(place)
            longitude = PlaceDataExtractor.get_place_longitude(place)
            place_type = PlaceDataExtractor.get_place_type(place)
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)

        place_data = {
            PlaceDataKeys.PLACE.value: place_name or "",
            PlaceDataKeys.ROOT_PLACE.value: root_place_name or "",
            PlaceDataKeys.LATITUDE.value: latitude or "",
            PlaceDataKeys.LONGITUDE.value: longitude or "",
            PlaceDataKeys.TYPE.value: place_type or "",
            PlaceDataKeys.TITLE.value: place_title or "",
            PlaceDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        return place_data

    def get_source_data(self, source):
        """Extracts basic information from a source object, including title and locale."""
        try:
            title = source.get_title() or None
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            title = None

        source_data = {
            SourceDataKeys.TITLE.value: title or "",
            SourceDataKeys.SYSTEM_LOCALE.value: self.system_locale or "",
        }

        return source_data
