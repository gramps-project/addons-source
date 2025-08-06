#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025       Greg Lamberson
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#

"""
PostgreSQL Enhanced Schema Column Definitions

This module defines all the columns expected by Gramps DBAPI
for each table type, with their JSONB extraction paths.
"""

# Required columns for each table type based on DBAPI expectations
# Note: These are REAL columns, not GENERATED, because Gramps updates them directly
REQUIRED_COLUMNS = {
    "person": {
        "given_name": "json_data->'primary_name'->>'first_name'",
        "surname": "json_data->'primary_name'->'surname_list'->0->>'surname'",
        "gramps_id": "json_data->>'gramps_id'",
        "gender": "CAST(json_data->>'gender' AS INTEGER)",
        "death_ref_index": "CAST(json_data->>'death_ref_index' AS INTEGER)",
        "birth_ref_index": "CAST(json_data->>'birth_ref_index' AS INTEGER)",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "family": {
        "gramps_id": "json_data->>'gramps_id'",
        "father_handle": "json_data->>'father_handle'",
        "mother_handle": "json_data->>'mother_handle'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "event": {
        "gramps_id": "json_data->>'gramps_id'",
        "description": "json_data->>'description'",
        "place": "json_data->>'place'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "place": {
        "enclosed_by": "json_data->>'enclosed_by'",
        "gramps_id": "json_data->>'gramps_id'",
        "title": "json_data->>'title'",
        "long": "json_data->>'long'",
        "lat": "json_data->>'lat'",
        "code": "json_data->>'code'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "source": {
        "gramps_id": "json_data->>'gramps_id'",
        "title": "json_data->>'title'",
        "author": "json_data->>'author'",
        "pubinfo": "json_data->>'pubinfo'",
        "abbrev": "json_data->>'abbrev'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "citation": {
        "gramps_id": "json_data->>'gramps_id'",
        "page": "json_data->>'page'",
        "confidence": "CAST(json_data->>'confidence' AS INTEGER)",
        "source_handle": "json_data->>'source_handle'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "repository": {
        "gramps_id": "json_data->>'gramps_id'",
        "name": "json_data->>'name'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "media": {
        "gramps_id": "json_data->>'gramps_id'",
        "path": "json_data->>'path'",
        "mime": "json_data->>'mime'",
        "desc_": "json_data->>'desc'",  # desc is a reserved word, so column is desc_
        "checksum": "json_data->>'checksum'",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "note": {
        "gramps_id": "json_data->>'gramps_id'",
        "format": "CAST(json_data->>'format' AS INTEGER)",
        "change": "CAST(json_data->>'change' AS INTEGER)",
        "private": "CAST(json_data->>'private' AS BOOLEAN)",
    },
    "tag": {
        "name": "json_data->>'name'",
        "color": "json_data->>'color'",
        "priority": "CAST(json_data->>'priority' AS INTEGER)",
        "change": "CAST(json_data->>'change' AS INTEGER)",
    },
}

# Indexes required by DBAPI
REQUIRED_INDEXES = {
    "person": ["gramps_id", "surname"],
    "family": ["gramps_id"],
    "event": ["gramps_id"],
    "place": ["gramps_id", "enclosed_by"],
    "source": ["gramps_id"],
    "citation": ["gramps_id"],
    "repository": ["gramps_id"],
    "media": ["gramps_id"],
    "note": ["gramps_id"],
    "tag": ["name"],
}
