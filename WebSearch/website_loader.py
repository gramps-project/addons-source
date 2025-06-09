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
This module provides the WebsiteLoader class responsible for managing
CSV-based website data for the WebSearch Gramplet in Gramps.

It supports loading genealogy websites from both built-in and user-defined
CSV files, handles state tracking via hash files, and extracts country_code/domain
information for site suggestions and filtering.
"""

import csv
import hashlib
import os
import sys

from constants import (
    CSV_DIR,
    DEFAULT_ENABLED_FILES,
    USER_DATA_CSV_DIR,
    SUPPORTED_NAV_TYPE_VALUES,
    SUPPORTED_SOURCE_TYPE_VALUES,
    CsvColumnNames,
    SourceTypes,
)
from models import WebsiteEntry, AIDomainData, AIUrlData


class WebsiteLoader:
    """
    WebsiteLoader is responsible for managing genealogy-related websites stored in CSV files.
    It provides methods to load, filter, and retrieve websites based on user settings.

    Features:
    - Reads website data from CSV files stored in the `assets/csv` directory.
    - Supports enabling/disabling websites via user-defined configuration.
    - Generates unique hash values for tracking visited and saved websites.
    - Maintains a list of skipped domains to avoid irrelevant suggestions.
    - Extracts domains and country_codes for AI-based recommendations.
    """

    @staticmethod
    def get_csv_files():
        """
        Returns a list of all available CSV file paths from both built-in and user directories.
        """
        files = {}
        if os.path.exists(CSV_DIR):
            for f in os.listdir(CSV_DIR):
                if f.endswith(".csv"):
                    files[f] = os.path.join(CSV_DIR, f)
        if os.path.exists(USER_DATA_CSV_DIR):
            for f in os.listdir(USER_DATA_CSV_DIR):
                if f.endswith(".csv"):
                    files[f] = os.path.join(USER_DATA_CSV_DIR, f)
        return list(files.values())

    @staticmethod
    def get_selected_csv_files(config_ini_manager):
        """Returns only the user-enabled CSV file paths based on current configuration."""
        csv_files = WebsiteLoader.get_csv_files()
        selected_files = config_ini_manager.get_list(
            "websearch.enabled_files", DEFAULT_ENABLED_FILES
        )
        return [file for file in csv_files if os.path.basename(file) in selected_files]

    @staticmethod
    def get_all_and_selected_files(config_ini_manager):
        """Returns a tuple of (all_files, selected_files), where both are filename lists."""
        all_files = [os.path.basename(f) for f in WebsiteLoader.get_csv_files()]
        selected_files = config_ini_manager.get_list(
            "websearch.enabled_files", DEFAULT_ENABLED_FILES
        )
        return all_files, selected_files

    @staticmethod
    def generate_hash(string: str) -> str:
        """Generates a 16-character SHA-256 hash for a given string (used for link tracking)."""
        return hashlib.sha256(string.encode()).hexdigest()[:16]

    @staticmethod
    def has_hash_in_file(hash_value: str, file_path) -> bool:
        """Checks if the given hash exists in the specified file."""
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as file:
            return hash_value in file.read().splitlines()

    @staticmethod
    def has_string_in_file(string_value: str, file_path) -> bool:
        """Checks if the given string exists in the specified file."""
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as file:
            return string_value in file.read().splitlines()

    @staticmethod
    def save_hash_to_file(hash_value: str, file_path):
        """Appends the hash to the file only if it doesn't already exist."""
        if not WebsiteLoader.has_hash_in_file(hash_value, file_path):
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(hash_value + "\n")

    @staticmethod
    def save_string_to_file(string_value: str, file_path):
        """Appends the string to the file only if it doesn't already exist."""
        if not WebsiteLoader.has_string_in_file(string_value, file_path):
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(string_value + "\n")

    @classmethod
    def load_websites(cls, config_ini_manager):
        """
        Loads websites from selected CSV files into a list of SimpleNamespace objects.

        Each CSV row is parsed and expanded into one or more website entries based on nav types.
        The resulting objects contain structured website data for use in the WebSearch Gramplet.

        Returns:
            list[SimpleNamespace]: Each object contains the following attributes:
                - nav_type (str): Navigation type (e.g. "person", "family", etc.)
                - country_code (Optional[str]): Country code derived from filename (e.g. "UA")
                - source_type (Optional[str]): Source type derived from filename (e.g. "COMMUNITY")
                - title (str): Human-readable title of the website
                - is_enabled (str): Raw 'is_enabled' value from CSV (usually "1" or "0")
                - url (str): URL or pattern from the CSV row
                - comment (Optional[str]): Optional comment field
                - is_custom_file (bool): True if the file comes from the user CSV folder
        """
        websites = []
        selected_csv_files = cls.get_selected_csv_files(config_ini_manager)

        for selected_file_path in selected_csv_files:
            if not os.path.exists(selected_file_path):
                continue

            file_identifier = cls.extract_file_identifier(selected_file_path)
            country_code, source_type = cls.parse_file_identifier(file_identifier)
            is_custom_file = selected_file_path.startswith(USER_DATA_CSV_DIR)

            with open(selected_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames:
                    continue
                reader.fieldnames = [
                    name.strip() if name else name for name in reader.fieldnames
                ]

                for row in reader:
                    if not row:
                        continue

                    nav_type_raw = row.get(CsvColumnNames.NAV_TYPE.value, "").strip()
                    title = row.get(CsvColumnNames.TITLE.value, "").strip()
                    is_enabled = row.get(CsvColumnNames.IS_ENABLED.value, "").strip()
                    url = row.get(CsvColumnNames.URL.value, "").strip()
                    comment = row.get(CsvColumnNames.COMMENT.value, None)

                    if not all([nav_type_raw, title, is_enabled, url]):
                        print(
                            f"⚠️ Some data missing in: {selected_file_path}. A row is skipped: "
                            f"{row}",
                            file=sys.stderr,
                        )
                        continue

                    nav_types = cls.expand_nav_types(nav_type_raw)
                    for nav_type in nav_types:
                        websites.append(
                            WebsiteEntry(
                                nav_type=nav_type,
                                country_code=country_code,
                                source_type=source_type,
                                title=title,
                                is_enabled=is_enabled,
                                url_pattern=url,
                                comment=comment,
                                is_custom_file=is_custom_file,
                                source_file_path=selected_file_path,
                            )
                        )

        return websites

    @staticmethod
    def expand_nav_types(nav_type_raw):
        """
        Parses and expands navigation type field from CSV, handling '*' as all supported types.
        """
        nav_type_raw = nav_type_raw.strip()
        if nav_type_raw == "*":
            return SUPPORTED_NAV_TYPE_VALUES

        return [
            nt.strip()
            for nt in nav_type_raw.split(",")
            if nt.strip() in SUPPORTED_NAV_TYPE_VALUES
        ]

    @classmethod
    def get_domains_data(cls, config_ini_manager):
        """
        Scans selected CSV files and extracts domains, country_codes and URLs
        grouped by source type.
        """
        selected_csv_files = cls.get_selected_csv_files(config_ini_manager)

        country_codes = set()
        regular_domains = set()
        include_global = False

        for selected_file_path in selected_csv_files:

            if not os.path.exists(selected_file_path):
                continue

            file_identifier = cls.extract_file_identifier(selected_file_path)
            country_code, source_type = cls.parse_file_identifier(file_identifier)
            if source_type == SourceTypes.COMMON.value:
                include_global = True

            if source_type == SourceTypes.COMMUNITY.value and country_code:
                country_codes.add(country_code)

            with open(selected_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [
                    name.strip() if name else name for name in reader.fieldnames
                ]

                for row in reader:
                    if not row:
                        continue
                    url = row.get(CsvColumnNames.URL.value, "").strip()
                    if not url:
                        continue

                    if source_type in [
                        SourceTypes.COMMON.value,
                        SourceTypes.UID.value,
                        SourceTypes.STATIC.value,
                        SourceTypes.CROSS.value,
                        SourceTypes.ARCHIVE.value,
                        SourceTypes.FORUM.value,
                    ]:
                        domain = url.split("/")[2] if "//" in url else url
                        regular_domains.add(domain)

        return AIDomainData(
            country_codes=country_codes,
            regular_domains=regular_domains,
            include_global=include_global,
        )

    @classmethod
    def get_urls_data(cls, config_ini_manager):
        """
        Scans selected CSV files and extracts urls, country_codes and URLs
        grouped by source type.
        """
        selected_csv_files = cls.get_selected_csv_files(config_ini_manager)

        country_codes = set()
        community_urls = set()
        include_global = False

        for selected_file_path in selected_csv_files:

            if not os.path.exists(selected_file_path):
                continue

            file_identifier = cls.extract_file_identifier(selected_file_path)
            country_code, source_type = cls.parse_file_identifier(file_identifier)
            if source_type == SourceTypes.COMMON.value:
                include_global = True

            if source_type == SourceTypes.COMMUNITY.value and country_code:
                country_codes.add(country_code)

            with open(selected_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [
                    name.strip() if name else name for name in reader.fieldnames
                ]

                for row in reader:
                    if not row:
                        continue
                    url = row.get(CsvColumnNames.URL.value, "").strip()
                    if not url:
                        continue

                    if source_type == SourceTypes.COMMUNITY.value:
                        community_urls.add(url)

        return AIUrlData(
            country_codes=country_codes,
            community_urls=community_urls,
            include_global=include_global,
        )

    @staticmethod
    def parse_file_identifier(file_identifier):
        """
        Parses a file identifier string into a country code and a source type.

        The file identifier is typically derived from the filename by removing the extension
        and the '-links' suffix. For example:
            - "UA-COMMUNITY" → country_code = "UA", source_type = "COMMUNITY"
            - "COMMON" → country_code = None, source_type = "COMMON"
            - "PL" → country_code = "PL", source_type = None
            - "PL-STATIC" → country_code = "PL", source_type = "STATIC"
        """
        parts = file_identifier.upper().split("-")

        source_type = None
        country_code = None

        for part in parts:
            if part in SUPPORTED_SOURCE_TYPE_VALUES and source_type is None:
                source_type = part
            elif part not in SUPPORTED_SOURCE_TYPE_VALUES and country_code is None:
                country_code = part

            if source_type and country_code:
                break

        return country_code, source_type

    @staticmethod
    def extract_file_identifier(file_path: str) -> str:
        """
        Extracts a normalized file identifier from the given file path.

        This method:
        - Removes the file extension (e.g., ".csv")
        - Strips the "-links" suffix if present
        - Converts the result to uppercase

        This identifier is used to derive source type and country code via `parse_file_identifier`.

        Example:
            "pl-links.csv" → "PL"
            "ua-community-links.csv" → "UA-COMMUNITY"
            "common-links.csv" → "COMMON"

        Args:
            file_path (str): Full path to the CSV file.

        Returns:
            str: Normalized, uppercase file identifier.
        """
        return (
            os.path.splitext(os.path.basename(file_path))[0]
            .replace("-links", "")
            .upper()
        )
