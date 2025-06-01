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
Utility functions for use across Gramplet modules.

Includes:
- Boolean string parsing (`is_true`)
- Retrieval of system locale from GRAMPS_LOCALE
"""

from datetime import datetime

from gramps.gen.const import GRAMPS_LOCALE as glocale

from gramps.gen.lib import AttributeType
from gramps.gen.lib.srcattrtype import SrcAttributeType


def is_true(value: str) -> bool:
    """
    Checks whether a given string value represents a boolean 'true'.

    Accepts common variants like "1", "true", "yes", "y".
    """
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def get_system_locale() -> str:
    """
    Extracts the system locale string from the GRAMPS_LOCALE object.
    """
    return (
        glocale.language[0] if isinstance(glocale.language, list) else glocale.language
    )


def format_iso_datetime(iso_string: str) -> str:
    """Format ISO 8601 datetime string to a more readable format."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ""


def get_attribute_name(attr_type):
    """Returns the name of the attribute type or None if unsupported."""
    if isinstance(attr_type, AttributeType):
        return attr_type.type2base()
    if isinstance(attr_type, SrcAttributeType):
        return attr_type.string
    return None


def get_handle_lookup(db):
    """
    Return a dictionary mapping navigation types to their corresponding
    get_*_from_handle methods from the database.
    """
    return {
        "People": db.get_person_from_handle,
        "Families": db.get_family_from_handle,
        "Events": db.get_event_from_handle,
        "Media": db.get_media_from_handle,
        "Sources": db.get_source_from_handle,
        "Citations": db.get_citation_from_handle,
        "Repositories": db.get_repository_from_handle,
        "Places": db.get_place_from_handle,
        "Notes": db.get_note_from_handle,
        "Person": db.get_person_from_handle,
        "Family": db.get_family_from_handle,
        "Event": db.get_event_from_handle,
        "Source": db.get_source_from_handle,
        "Citation": db.get_citation_from_handle,
        "Repository": db.get_repository_from_handle,
        "Place": db.get_place_from_handle,
        "Note": db.get_note_from_handle,
    }
