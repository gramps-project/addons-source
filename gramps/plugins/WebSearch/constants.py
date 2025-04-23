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
This module defines various enumerations and constants used in the
WebSearch Gramplet for Gramps.

Enums:
- MiddleNameHandling: Specifies how to handle middle names.
- SupportedNavTypes: Defines navigation types for web searches.
- PersonDataKeys: Stores keys related to personal data.
- FamilyDataKeys: Stores keys related to family data.
- CsvColumnNames: Stores CSV column names for site categorization.
- URLCompactnessLevel: Defines URL formatting levels.
- PlaceDataKeys: Stores keys related to place information.
- SourceDataKeys: Stores keys related to source information.

Constants:
- Paths for storing visited and saved links, icons, and skipped domains.
- Default settings for URL handling and file management.
- Category icons for different genealogy-related sections.

These enums and constants help standardize data representation and
ensure consistency in website data processing.
"""

import os
from enum import Enum

from gramps.gen.const import USER_DATA

from translation_helper import _

# --------------------------
# ENUMS
# --------------------------


class MiddleNameHandling(Enum):
    """Specifies strategies for handling middle names in generated URLs."""

    LEAVE_ALONE = "leave alone"
    SEPARATE = "separate"
    REMOVE = "remove"


class SupportedNavTypes(Enum):
    """Enumerates supported navigation types in Gramps for WebSearch."""

    PEOPLE = "People"
    PLACES = "Places"
    SOURCES = "Sources"
    FAMILIES = "Families"
    EVENTS = "Events"
    CITATIONS = "Citations"
    MEDIA = "Media"
    NOTES = "Notes"
    REPOSITORIES = "Repositories"


SUPPORTED_NAV_TYPE_VALUES = {nt.value for nt in SupportedNavTypes}


class PersonDataKeys(Enum):
    """Defines all available key keys for 'Person' navigation type."""

    GIVEN = "given"
    MIDDLE = "middle"
    SURNAME = "surname"
    BIRTH_YEAR = "birth_year"
    BIRTH_YEAR_FROM = "birth_year_from"
    BIRTH_YEAR_TO = "birth_year_to"
    BIRTH_YEAR_BEFORE = "birth_year_before"
    BIRTH_YEAR_AFTER = "birth_year_after"
    DEATH_YEAR = "death_year"
    DEATH_YEAR_FROM = "death_year_from"
    DEATH_YEAR_TO = "death_year_to"
    DEATH_YEAR_BEFORE = "death_year_before"
    DEATH_YEAR_AFTER = "death_year_after"
    BIRTH_PLACE = "birth_place"
    DEATH_PLACE = "death_place"
    BIRTH_ROOT_PLACE = "birth_root_place"
    DEATH_ROOT_PLACE = "death_root_place"

    SYSTEM_LOCALE = "locale"


class FamilyDataKeys(Enum):
    """Defines all available key keys for 'Family' navigation type."""

    FATHER_GIVEN = "father_given"
    FATHER_MIDDLE = "father_middle"
    FATHER_SURNAME = "father_surname"
    FATHER_BIRTH_YEAR = "father_birth_year"
    FATHER_BIRTH_YEAR_FROM = "father_birth_year_from"
    FATHER_BIRTH_YEAR_TO = "father_birth_year_to"
    FATHER_BIRTH_YEAR_BEFORE = "father_birth_year_before"
    FATHER_BIRTH_YEAR_AFTER = "father_birth_year_after"
    FATHER_DEATH_YEAR = "father_death_year"
    FATHER_DEATH_YEAR_FROM = "father_death_year_from"
    FATHER_DEATH_YEAR_TO = "father_death_year_to"
    FATHER_DEATH_YEAR_BEFORE = "father_death_year_before"
    FATHER_DEATH_YEAR_AFTER = "father_death_year_after"
    FATHER_BIRTH_PLACE = "father_birth_place"
    FATHER_BIRTH_ROOT_PLACE = "father_birth_root_place"
    FATHER_DEATH_PLACE = "father_death_place"
    FATHER_DEATH_ROOT_PLACE = "father_death_root_place"

    MOTHER_GIVEN = "mother_given"
    MOTHER_MIDDLE = "mother_middle"
    MOTHER_SURNAME = "mother_surname"
    MOTHER_BIRTH_YEAR = "mother_birth_year"
    MOTHER_BIRTH_YEAR_FROM = "mother_birth_year_from"
    MOTHER_BIRTH_YEAR_TO = "mother_birth_year_to"
    MOTHER_BIRTH_YEAR_BEFORE = "mother_birth_year_before"
    MOTHER_BIRTH_YEAR_AFTER = "mother_birth_year_after"
    MOTHER_DEATH_YEAR = "mother_death_year"
    MOTHER_DEATH_YEAR_FROM = "mother_death_year_from"
    MOTHER_DEATH_YEAR_TO = "mother_death_year_to"
    MOTHER_DEATH_YEAR_BEFORE = "mother_death_year_before"
    MOTHER_DEATH_YEAR_AFTER = "mother_death_year_after"
    MOTHER_BIRTH_PLACE = "mother_birth_place"
    MOTHER_BIRTH_ROOT_PLACE = "mother_birth_root_place"
    MOTHER_DEATH_PLACE = "mother_death_place"
    MOTHER_DEATH_ROOT_PLACE = "mother_death_root_place"

    MARRIAGE_YEAR = "marriage_year"
    MARRIAGE_YEAR_FROM = "marriage_year_from"
    MARRIAGE_YEAR_TO = "marriage_year_to"
    MARRIAGE_YEAR_BEFORE = "marriage_year_before"
    MARRIAGE_YEAR_AFTER = "marriage_year_after"
    MARRIAGE_PLACE = "marriage_place"
    MARRIAGE_ROOT_PLACE = "marriage_root_place"

    DIVORCE_YEAR = "divorce_year"
    DIVORCE_YEAR_FROM = "divorce_year_from"
    DIVORCE_YEAR_TO = "divorce_year_to"
    DIVORCE_YEAR_BEFORE = "divorce_year_before"
    DIVORCE_YEAR_AFTER = "divorce_year_after"
    DIVORCE_PLACE = "divorce_place"
    DIVORCE_ROOT_PLACE = "divorce_root_place"

    SYSTEM_LOCALE = "locale"


class CsvColumnNames(Enum):
    """Defines expected column headers for CSV files."""

    NAV_TYPE = "Navigation type"
    TITLE = "Title"
    IS_ENABLED = "Is enabled"
    URL = "URL"
    COMMENT = "Comment"


class URLCompactnessLevel(Enum):
    """Enumerates levels of URL compactness in formatting."""

    SHORTEST = "shortest"
    COMPACT_NO_ATTRIBUTES = "compact_no_attributes"
    COMPACT_WITH_ATTRIBUTES = "compact_with_attributes"
    LONG = "long"


class PlaceDataKeys(Enum):
    """Defines all key keys for the 'Place' navigation type."""

    PLACE = "place"
    ROOT_PLACE = "root_place"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    TYPE = "type"
    TITLE = "title"
    SYSTEM_LOCALE = "locale"


class SourceDataKeys(Enum):
    """Defines key keys for source-based navigation."""

    TITLE = "source_title"
    FULL_ABBREVIATION = "full_abbreviation"
    ARCHIVE_CODE = "archive_code"
    COLLECTION_NUMBER = "collection_number"
    SERIES_NUMBER = "series_number"
    FILE_NUMBER = "file_number"
    SYSTEM_LOCALE = "locale"


class AIProviders(Enum):
    """Enumeration of supported AI providers."""

    DISABLED = ""
    OPENAI = "openai"
    MISTRAL = "mistral"


class SourceTypes(Enum):
    """Enumeration of source types for links."""

    COMMON = "COMMON"
    UID = "UID"
    STATIC = "STATIC"
    CROSS = "CROSS"
    ATTRIBUTE = "ATTRIBUTE"
    INTERNET = "INTERNET"
    NOTE = "NOTE"
    COMMUNITY = "COMMUNITY"
    ARCHIVE = "ARCHIVE"
    FORUM = "FORUM"


SUPPORTED_SOURCE_TYPE_VALUES = {st.value for st in SourceTypes}


SOURCE_TYPE_SORT_ORDER = {
    SourceTypes.COMMON.value: "A",
    SourceTypes.UID.value: "B",
    SourceTypes.STATIC.value: "C",
    SourceTypes.CROSS.value: "D",
    SourceTypes.ATTRIBUTE.value: "E",
    SourceTypes.INTERNET.value: "F",
    SourceTypes.NOTE.value: "G",
    SourceTypes.COMMUNITY.value: "H",
    SourceTypes.ARCHIVE.value: "I",
    SourceTypes.FORUM.value: "J",
}

SOURCE_TYPES_HIDE_KEYS_COUNT = [
    SourceTypes.STATIC.value,
    SourceTypes.ATTRIBUTE.value,
    SourceTypes.INTERNET.value,
    SourceTypes.NOTE.value,
    SourceTypes.COMMUNITY.value,
    SourceTypes.ARCHIVE.value,
    SourceTypes.FORUM.value,
]

SOURCE_TYPES_WITH_FIXED_LINKS = [
    SourceTypes.STATIC.value,
    SourceTypes.ATTRIBUTE.value,
    SourceTypes.INTERNET.value,
    SourceTypes.NOTE.value,
    SourceTypes.COMMUNITY.value,
    SourceTypes.ARCHIVE.value,
    SourceTypes.FORUM.value,
]

VIEW_IDS_MAPPING = {
    "dashboardview": None,
    "personlistview": "Person",
    "relview": None,
    "familyview": "Family",
    "family_tree_view": None,
    "eventview": "Event",
    "placetreeview": "Place",
    "sourceview": "Source",
    "citationlistview": "Citation",
    "repoview": None,
    "mediaview": "Media",
    "noteview": None,
    "geo1": None,
}


# --------------------------
# CONSTANTS
# --------------------------

RIGHT_MOUSE_BUTTON = 3
URL_SAFE_CHARS = ":/?&="

COMMON_UID_SIGN = ""

ICON_SIZE = 16
UID_ICON_WIDTH = 32
UID_ICON_HEIGHT = 12
URL_PREFIXES_TO_TRIM = ["https://www.", "http://www.", "https://", "http://"]
COMMON_CSV_FILE_NAME = "common-links.csv"
UID_CSV_FILE_NAME = "uid-links.csv"
STATIC_CSV_FILE_NAME = "static-links.csv"
CROSS_CSV_FILE_NAME = "cross-links.csv"
ALL_COLUMNS = ["icons", "file_identifier", "keys", "title", "url", "comment"]
DEFAULT_DISPLAY_COLUMNS = [
    "icons",
    "file_identifier",
    "keys",
    "title",
    "url",
    "comment",
]
ALL_COLUMNS_LOCALIZED = {
    "icons": _("Column - Icons"),
    "file_identifier": _("Column - Source Types (flags)"),
    "keys": _("Column - Keys"),
    "title": _("Column - Title"),
    "url": _("Column - Website Url"),
    "comment": _("Column - Comment"),
}
ALL_ICONS = [
    "visited",
    "saved",
    "uid",
    "flag",
    "pin",
    "earth",
    "cross",
    "user_data",
    "attribute",
    "internet",
    "note",
]
DEFAULT_DISPLAY_ICONS = [
    "visited",
    "saved",
    "uid",
    "flag",
    "pin",
    "earth",
    "cross",
    "user_data",
    "attribute",
    "internet",
    "note",
]
ALL_ICONS_LOCALIZED = {
    "visited": _("Icon - Visited URLs (checkmark)"),
    "saved": _("Icon - Saved URLs (floppy disk)"),
    "uid": _("Icon - URLs linked to UID attributes (UID badge)"),
    "flag": _("Icon - URLs from regional CSV files (flag)"),
    "pin": _("Icon - URLs from static CSV files (red pin)"),
    "earth": _("Icon - URLs from common CSV files (earth)"),
    "cross": _("Icon - URLs from cross CSV files (shuffle arrows)"),
    "user_data": _("Icon - URLs from custom user directory (spreadsheet icon)"),
    "attribute": _("Icon - URLs from the 'Attributes' tab ('A' icon)"),
    "internet": _("Icon - URLs from the 'Internet' tab ('I' icon)"),
    "note": _("Icon - URLs from the 'Notes' tab ('N' icon)"),
}

CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "configs")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
CSV_DIR = os.path.join(ASSETS_DIR, "csv")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
FLAGS_DIR = os.path.join(ICONS_DIR, "flags")
USER_DATA_BASE_DIR = os.path.join(USER_DATA, "WebSearch")
USER_DATA_CSV_DIR = os.path.join(USER_DATA_BASE_DIR, "csv")
USER_DATA_JSON_DIR = os.path.join(USER_DATA_BASE_DIR, "json")

INTERFACE_FILE_PATH = os.path.join(os.path.dirname(__file__), "interface.xml")
CONFIG_FILE_PATH = os.path.join(CONFIGS_DIR, "config.ini")
ATTRIBUTE_MAPPING_FILE_PATH = os.path.join(CONFIGS_DIR, "attribute_mapping.json")
VISITED_HASH_FILE_PATH = os.path.join(DATA_DIR, "visited_links.txt")
SAVED_HASH_FILE_PATH = os.path.join(DATA_DIR, "saved_links.txt")
HIDDEN_HASH_FILE_PATH = os.path.join(DATA_DIR, "hidden_links.txt")
SKIPPED_DOMAIN_SUGGESTIONS_FILE_PATH = os.path.join(
    DATA_DIR, "skipped_domain_suggestions.txt"
)
ICON_VISITED_PATH = os.path.join(ICONS_DIR, "emblem-default.png")
ICON_SAVED_PATH = os.path.join(ICONS_DIR, "media-floppy.png")
ICON_UID_PATH = os.path.join(ICONS_DIR, "uid.png")
ICON_USER_DATA_PATH = os.path.join(ICONS_DIR, "user-file.png")
ICON_PIN_PATH = os.path.join(ICONS_DIR, "pin.png")
ICON_EARTH_PATH = os.path.join(ICONS_DIR, "earth.png")
ICON_CROSS_PATH = os.path.join(ICONS_DIR, "cross.png")
ICON_ATTRIBUTE_PATH = os.path.join(ICONS_DIR, "attribute.png")
ICON_INTERNET_PATH = os.path.join(ICONS_DIR, "internet.png")
ICON_NOTE_PATH = os.path.join(ICONS_DIR, "note.png")

STYLE_CSS_PATH = os.path.join(ASSETS_DIR, "style.css")
DEFAULT_ATTRIBUTE_MAPPING_FILE_PATH = os.path.join(
    CONFIGS_DIR, "attribute_mapping.json"
)
USER_DATA_ATTRIBUTE_MAPPING_FILE_PATH = os.path.join(
    USER_DATA_JSON_DIR, "attribute_mapping.json"
)


DEFAULT_CATEGORY_ICON = "gramps-gramplet"
DEFAULT_SHOW_SHORT_URL = False
DEFAULT_URL_PREFIX_REPLACEMENT = ""
DEFAULT_QUERY_PARAMETERS_REPLACEMENT = "..."
DEFAULT_URL_COMPACTNESS_LEVEL = URLCompactnessLevel.COMPACT_NO_ATTRIBUTES.value
DEFAULT_MIDDLE_NAME_HANDLING = MiddleNameHandling.SEPARATE.value
DEFAULT_ENABLED_FILES = [COMMON_CSV_FILE_NAME, UID_CSV_FILE_NAME, STATIC_CSV_FILE_NAME]
DEFAULT_SHOW_ATTRIBUTE_LINKS = True
DEFAULT_SHOW_INTERNET_LINKS = True
DEFAULT_SHOW_NOTE_LINKS = True
DEFAULT_AI_PROVIDER = AIProviders.DISABLED.value

DEFAULT_COLUMNS_ORDER = ["icons", "file_identifier", "keys", "title", "url", "comment"]

CATEGORY_ICON = {
    "Dashboard": "gramps-gramplet",
    "People": "gramps-person",
    "Relationships": "gramps-relation",
    "Families": "gramps-family",
    "Events": "gramps-event",
    "Ancestry": "gramps-pedigree",
    "Places": "gramps-place",
    "Geography": "gramps-geo",
    "Sources": "gramps-source",
    "Repositories": "gramps-repository",
    "Media": "gramps-media",
    "Notes": "gramps-notes",
    "Citations": "gramps-citation",
}

URL_REGEX = r"https?://[^\s]+"
URL_RSTRIP = ".,!?);]"
