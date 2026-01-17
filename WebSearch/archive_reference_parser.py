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
This module provides utilities for parsing textual archive references into structured components.

It supports both Cyrillic and Latin formats commonly found in Ukrainian and international archival
systems. Typical input formats include codes like "ДААРК-142-1-15" or descriptive forms
like "ф. 142, оп. 1, сп. 15". The parser extracts the following fields:
- archive_code
- collection_number (fund)
- series_number (inventory)
- file_number (case)

The parsed data can be used for building search URLs to external services such as
DuckArchive Inspector or FamilySearch image collections.
"""


import re
from typing import Optional, Dict, List

ParsedArchiveRef = Dict[str, Optional[str]]


class ArchiveReferenceParser:
    """
    Parses textual archive references like "ДААРК-142-1-15" or "ф. 142, оп. 1, сп. 15"
    into structured parts: archive_code, collection_number, series_number, file_number.
    """

    ARCHIVE_PATTERNS_FULL: List[tuple] = [
        # 142-1-15
        # ДААРК 142-1-15
        # ДААРК-142-1-15
        (
            r"(?:(?P<archive_code>[А-ЯІЇЄҐA-Z]{2,})[\s-]+)?"
            r"(?P<collection_number>[A-Za-zА-Яа-яІіЇїЄєҐґ]?\d+)"
            r"[-–](?P<series_number>\d+)"
            r"[-–](?P<file_number>\d+)",
            ["archive_code", "collection_number", "series_number", "file_number"],
        ),
        # ф. 142 оп. 1 сп. 15
        # ф. 142. оп. 1. сп. 15
        # ф. 142, оп. 1, сп. 15
        # ДААРК ф. 142 оп. 1 сп. 15
        # ДААРК, ф. р142, оп. 1, сп. 15
        # ДААРК. ф. 142. оп. 1. сп. 15
        (
            r"(?:(?P<archive_code>[А-ЯІЇЄҐA-Z]{2,})(?:[\s]*[.,]?[\s]*))?"
            r"(фонд|Фонд|ф|Ф|Fund|FUND|F|f|Collection|COLLECTION|Coll|coll)\.*(?:[\s]*[.,]?[\s]*)"
            r"(?P<collection_number>[A-Za-zА-Яа-яІіЇїЄєҐґ]?\d+)"
            r"(?:[\s]*[.,]?[\s]*)"
            r"(опис|Опис|ОПИС|оп|Оп|ОП|Inventory|INVENTORY|inventory|Inv|INV|inv|Series|SERIES|series|Ser|SER|ser)\.*"  # pylint: disable=line-too-long
            r"(?:[\s]*[.,]?[\s]*)"
            r"(?P<series_number>\d+)"
            r"(?:[\s]*[.,]?[\s]*)"
            r"(справа|Справа|СПРАВА|сп|Сп|СП|File|FILE|file|Fl|FL|fl|Item|ITEM|item|It|IT|it)\.*"
            r"(?:[\s]*[.,]?[\s]*)"
            r"(?P<file_number>\d+)",
            ["archive_code", "collection_number", "series_number", "file_number"],
        ),
    ]

    ARCHIVE_PATTERNS_CODE_ONLY: List[tuple] = [
        # archive code only from repository name, etc.
        (r"\b(?P<archive_code>[А-ЯІЇЄҐA-Z]{2,})\b", ["archive_code"]),
    ]

    TEST_CASES_FULL: List[str] = [
        "142-1-15",
        "ДААРК 142-1-15",
        "ДААРК-142-1-15",
        "ф. 142 оп. 1 сп. 15",
        "ф. 142. оп. 1. сп. 15",
        "ф. 142, оп. 1, сп. 15",
        "Ф. 142 Оп. 1 Сп. 15",
        "Ф. 142. Оп. 1. Сп. 15",
        "Ф. 142, Оп. 1, Сп. 15",
        "ДААРК ф. 142 оп. 1 сп. 15",
        "ДААРК, ф. 142, оп. 1, сп. 15",
        "ДААРК. ф. 142. оп. 1. сп. 15",
        "Fund 142 Inventory 1 File 15",
        "Collection. 142, Series. 1, Item. 15",
        "coll 142 inv 1 fl 15",
        "F. 142. Ser. 1. It. 15",
        "TNA Collection, 142. Inventory. 1 File. 15",
        "TNA Coll 142 Ser 1 It 15",
        "TNA Collection 142, Inv. 1, File 15",
        "р142-1-15",
        "ДААРК р142-1-15",
        "ДААРК-р142-1-15",
        "ф. р142 оп. 1 сп. 15",
        "ф. р142. оп. 1. сп. 15",
        "ф. Р142, оп. 1, сп. 15",
        "Ф. р142 Оп. 1 Сп. 15",
        "Ф. Р142. Оп. 1. Сп. 15",
        "Ф. Р142, Оп. 1, Сп. 15",
        "ДААРК ф. р142 оп. 1 сп. 15",
        "ДААРК, ф. Р142, оп. 1, сп. 15",
        "ДААРК. ф. р142. оп. 1. сп. 15",
        "Fund p142 Inventory 1 File 15",
        "Collection. P142, Series. 1, Item. 15",
        "coll p142 inv 1 fl 15",
        "F. P142. Ser. 1. It. 15",
        "TNA Collection, p142. Inventory. 1 File. 15",
        "TNA Coll P142 Ser 1 It 15",
        "TNA Collection P142, Inv. 1, File 15",
    ]

    TEST_CASES_CODE_ONLY: List[str] = [
        "ДААРК",
        "TNA",
        "NARA",
        "PRONI",
        "LAC",
        "NYPL",
        "DAARK",
        "NARA (USA)",
        "PRONI, Belfast",
        "TNA - The National Archives",
    ]

    @classmethod
    def parse_full_reference(cls, text: str) -> Optional[ParsedArchiveRef]:
        """Parses a full archive reference string into parts."""
        text = text.strip()
        for pattern, keys in cls.ARCHIVE_PATTERNS_FULL:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {key: match.group(key) for key in keys}
        return None

    @classmethod
    def parse_archive_code(cls, text: str) -> Optional[ParsedArchiveRef]:
        """Parses only the archive_code (usually from repository title)."""
        text = text.strip()
        for pattern, keys in cls.ARCHIVE_PATTERNS_CODE_ONLY:
            match = re.search(pattern, text)
            if match:
                return {
                    key: match.group(key)
                    for key in keys
                    if match.group(key) is not None
                }
        return None
