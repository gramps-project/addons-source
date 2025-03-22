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

import os
import csv
import sys
import hashlib

from constants import *

class WebsiteLoader:
    """
    WebsiteLoader is responsible for managing genealogy-related websites stored in CSV files.
    It provides methods to load, filter, and retrieve websites based on user settings.

    Features:
    - Reads website data from CSV files stored in the `assets/csv` directory.
    - Supports enabling/disabling websites via user-defined configuration.
    - Generates unique hash values for tracking visited and saved websites.
    - Maintains a list of skipped domains to avoid irrelevant suggestions.
    - Extracts domains and locales for AI-based recommendations.
    """

    locales = set()
    domains = set()
    include_global = False

    @staticmethod
    def get_csv_files():
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
        csv_files = WebsiteLoader.get_csv_files()
        selected_files = config_ini_manager.get_list("websearch.enabled_files", DEFAULT_ENABLED_FILES)
        return [file for file in csv_files if os.path.basename(file) in selected_files]

    @staticmethod
    def get_all_and_selected_files(config_ini_manager):
        all_files = [os.path.basename(f) for f in WebsiteLoader.get_csv_files()]
        selected_files = config_ini_manager.get_list("websearch.enabled_files", DEFAULT_ENABLED_FILES)
        return all_files, selected_files

    @staticmethod
    def generate_hash(string: str) -> str:
        return hashlib.sha256(string.encode()).hexdigest()[:16]

    @staticmethod
    def has_hash_in_file(hash_value: str, file_path) -> bool:
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as file:
            return hash_value in file.read().splitlines()

    @staticmethod
    def has_string_in_file(string_value: str, file_path) -> bool:
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as file:
            return string_value in file.read().splitlines()

    @staticmethod
    def save_hash_to_file(hash_value: str, file_path):
        if not WebsiteLoader.has_hash_in_file(hash_value, file_path):
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(hash_value + "\n")

    @staticmethod
    def save_string_to_file(string_value: str, file_path):
        if not WebsiteLoader.has_string_in_file(string_value, file_path):
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(string_value + "\n")

    @staticmethod
    def load_skipped_domains() -> set:
        if not os.path.exists(SKIPPED_DOMAIN_SUGGESTIONS_FILE_PATH):
            return set()
        with open(SKIPPED_DOMAIN_SUGGESTIONS_FILE_PATH, "r", encoding="utf-8") as file:
            return {line.strip() for line in file if line.strip()}

    @staticmethod
    def save_skipped_domain(domain: str):
        with open(SKIPPED_DOMAIN_SUGGESTIONS_FILE_PATH, "a", encoding="utf-8") as file:
            file.write(domain + "\n")

    @classmethod
    def load_websites(cls, config_ini_manager):
        websites = []
        selected_csv_files = cls.get_selected_csv_files(config_ini_manager)

        for selected_file_path in selected_csv_files:
            if not os.path.exists(selected_file_path):
                continue

            locale = os.path.splitext(os.path.basename(selected_file_path))[0].replace("-links", "").upper()
            is_custom_file = selected_file_path.startswith(USER_DATA_CSV_DIR)

            with open(selected_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]

                for row in reader:
                    if not row:
                        continue

                    nav_type = row.get(CsvColumnNames.NAV_TYPE.value, "").strip()
                    title = row.get(CsvColumnNames.TITLE.value, "").strip()
                    is_enabled = row.get(CsvColumnNames.IS_ENABLED.value, "").strip()
                    url = row.get(CsvColumnNames.URL.value, "").strip()
                    comment = row.get(CsvColumnNames.COMMENT.value, None)

                    if not all([nav_type, title, is_enabled, url]):
                        print(f"⚠️ Some data are missing in: {selected_file_path}. A row is skipped: {row}", file=sys.stderr)
                        continue

                    websites.append([nav_type, locale, title, is_enabled, url, comment, is_custom_file])
        return websites

    @classmethod
    def get_domains_data(cls, config_ini_manager):
        selected_csv_files = cls.get_selected_csv_files(config_ini_manager)
        cls.locales = set()
        cls.domains = set()
        cls.include_global = False

        for selected_file_path in selected_csv_files:
            if not os.path.exists(selected_file_path):
                continue

            locale = os.path.splitext(os.path.basename(selected_file_path))[0].replace("-links", "").upper()
            if locale == "COMMON":
                cls.include_global = True
            else:
                cls.locales.add(locale)

            with open(selected_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]

                for row in reader:
                    if not row:
                        continue
                    url = row.get(CsvColumnNames.URL.value, "").strip()
                    domain = url.split("/")[2] if "//" in url else url
                    cls.domains.add(domain)

        return cls.locales, cls.domains, cls.include_global
