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
Module for managing file-based table operations with support for caching, uniqueness enforcement,
and timestamps. This module provides simple data manipulation operations such as:

- Creating, updating, reading, and deleting records (CRUD operations).
- Ensuring unique fields across records and enforcing required fields.
- Adding automatic timestamps (`created_at`, `updated_at`) when enabled.
- Managing indexes for faster search operations based on cache fields.
- Handling bulk record creation with duplicate handling strategies.

Classes:
    DBFileTable: A class that encapsulates operations on a file-based table
    (using JSON as storage), including support for uniqueness checks, required fields, timestamps.
    FileTableError: Base class for exceptions raised by `DBFileTable`.
    DuplicateEntryError: Raised when an attempt is made to insert a duplicate value in a unique
    field.
    MissingRequiredFieldError: Raised when a required field is missing from a record.

Example usage:
    # Creating and working with a file-based table
    db = DBFileTable(config=DBFileTableConfig(filepath="my_table.json",
    cache_fields=['id', 'email'], required_fields=['name']))

    # Create a new record
    new_id = db.create({'name': 'John', 'age': 30, 'email': 'john@example.com'})

    # Read a record by its ID
    record = db.read_by_id(new_id)

    # Read a record by a field (email in this case)
    record_by_email = db.first_by_field('email', 'john@example.com')

    # Update a record
    db.update(new_id, {'age': 31})

    # Delete a record by ID
    db.delete(new_id)

    # Delete records by a specific field
    db.delete_by_field('name', 'Jane')

    # Find records by a specific field (e.g., all people named 'John')
    people_named_john = db.get_by_field('name', 'John')

    # Filter records based on multiple conditions (e.g., people named 'John' with age 31)
    adults_named_john = db.filter(name='John', age=31)

    # Count the total number of records
    total_records = db.count()

    # Check if a record exists by field and value
    exists = db.exists('name', 'John')

    # Sort records by a field (e.g., by age)
    sorted_records = db.order_by('age')

    # Migrate: Add a new field to all records
    db.migrate_add_field('phone', default_value='unknown')

    # Migrate: Remove a field from all records
    db.migrate_remove_field('age')

    # Retrieve all records from the table
    all_records = db.all()
"""

import json
import os
from datetime import datetime, timezone
from collections import OrderedDict

from models import DBFileTableConfig
from constants import DuplicateHandlingMode, DB_FILE_TABLE_DIR
from record_query import RecordQuery


class DBFileTable:
    """A simple file-based table with optional caching, uniqueness support."""

    def __init__(self, config: DBFileTableConfig):
        """Initialize DBFileTable with file path, optional caching settings."""

        self.config = config
        self._meta = {"record_count": 0, "last_id": 0}
        self._update_config()
        self.filepath = os.path.join(DB_FILE_TABLE_DIR, self.config.filename)
        self._indexes = {field: {} for field in self.config.cache_fields}

        self._data = []
        self._ensure_directory_exists()
        self._initialize_data()
        self._data = self._load_data()

    def _update_config(self):
        if "id" not in self.config.required_fields:
            self.config.required_fields.append("id")

    def _ensure_directory_exists(self):
        """Ensure the directory for the file exists."""
        directory = os.path.dirname(self.filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _initialize_data(self):
        """Check if the file exists, initialize empty data."""
        if not os.path.exists(self.filepath):
            self.save_data([])

    def _load_data(self):
        """
        Load data and meta from the file.
        Use only in read-only methods. Write methods must use self._data directly!
        """
        with open(self.filepath, "r", encoding="utf-8") as f:
            content = json.load(f)
            if isinstance(content, list):  # legacy format
                self._data = content
                self._meta = {
                    "record_count": len(content),
                    "last_id": max(
                        (
                            r.get("id", 0)
                            for r in content
                            if isinstance(r.get("id"), int)
                        ),
                        default=0,
                    ),
                }
            else:
                self._meta = content.get("meta", {})
                self._data = content.get("data", [])
        return self._data

    def _sort_record_fields(self, record):
        """Sort fields in a record: id → *_record_id → other → created_at → updated_at."""
        id_part = [("id", record["id"])] if "id" in record else []

        record_id_parts = [
            (k, v) for k, v in record.items() if k.endswith("_record_id") and k != "id"
        ]

        tail_keys = []
        if "created_at" in record:
            tail_keys.append(("created_at", record["created_at"]))
        if "updated_at" in record:
            tail_keys.append(("updated_at", record["updated_at"]))

        core_keys = [
            (k, v)
            for k, v in record.items()
            if k != "id"
            and not k.endswith("_record_id")
            and k != "created_at"
            and k != "updated_at"
        ]

        return OrderedDict(id_part + record_id_parts + core_keys + tail_keys)

    def save_data(self, data):
        """Save data and meta to the file."""
        self._update_records_count()
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(
                {"meta": self._meta, "data": data}, f, ensure_ascii=False, indent=2
            )
        if self.config.cache_fields:
            self._build_indexes()

    def _build_indexes(self):
        """Build indexes for cached fields."""
        self._indexes = {field: {} for field in self.config.cache_fields}
        data = self._data
        for record in data:
            for field in self.config.cache_fields:
                value = record.get(field)
                if value is not None:
                    self._indexes[field][value] = record

    def _update_records_count(self):
        """Update the record count in meta."""
        self._meta["record_count"] = len(self._data)

    def _get_max_id(self):
        """Get and return the max ID, update if necessary."""
        return self._meta.get("last_id", 0)

    def _check_unique_fields(self, record, exclude_id=None):
        """Check that unique fields do not conflict with existing records."""
        data = self._data
        for field in self.config.unique_fields:
            value = record.get(field)
            if value is not None and any(
                existing.get(field) == value
                and (exclude_id is None or existing.get("id") != exclude_id)
                for existing in data
            ):
                raise DuplicateEntryError(field, value)

    def _set_timestamps(self, record, is_new=True):
        """Set created_at and/or updated_at timestamps based on config and is_new flag."""
        now = datetime.now(timezone.utc).isoformat()
        if is_new and self.config.set_created_at:
            record["created_at"] = now
        if self.config.set_updated_at:
            record["updated_at"] = now

    def _check_required_fields(self, record):
        """Check that all required fields are present and not None."""
        for field in self.config.required_fields:
            if field not in record or record[field] is None:
                raise MissingRequiredFieldError(field)

    def _set_id(self, record):
        record_id = self._get_max_id() + 1
        record["id"] = record_id
        self._meta["last_id"] = record_id
        return record_id

    def create(self, record):
        """Create a new record with unique ID and enforce unique and required fields."""

        #if "id" in record:
        #    print("❌ Error. external 'id' will be ignored in create()")

        record_id = self._set_id(record)
        self._set_timestamps(record, is_new=True)
        self._check_unique_fields(record)
        self._check_required_fields(record)
        record = self._sort_record_fields(record)
        self._data.append(record)
        self.save_data(self._data)
        return self.read_by_id(record_id)

    def bulk_create(self, records):
        """Create multiple records with control over duplicate handling."""
        created_records = []
        for record in records:
            try:
                created_records.append(self.create(record))
            except ValueError:
                if (
                    self.config.on_bulk_duplicate
                    == DuplicateHandlingMode.THROW_ERROR.value
                ):
                    raise
                if (
                    self.config.on_bulk_duplicate
                    == DuplicateHandlingMode.IGNORE_DUPLICATES.value
                ):
                    continue
        return created_records

    def update(self, record_id, updates):
        """Update a record by its ID with optional unique and required field enforcement."""
        updated = False

        for i, record in enumerate(self._data):
            if record.get("id") == record_id:
                temp_record = record.copy()
                temp_record.update(updates)

                self._check_unique_fields(temp_record, exclude_id=record_id)
                self._check_required_fields(temp_record)

                for key, value in updates.items():
                    record[key] = value

                self._set_timestamps(record, is_new=False)
                self._data[i] = self._sort_record_fields(record)
                updated = True
                break

        if updated:
            self.save_data(self._data)
        return updated

    def read_by_id(self, record_id):
        """Read a record by its unique ID."""
        return self.first_by_field("id", record_id)

    def first_by_field(self, field_name, value):
        """Find the first record by a specific field."""
        if field_name in self._indexes:
            return self._indexes[field_name].get(value)
        data = self._load_data()
        for record in data:
            if record.get(field_name) == value:
                return record
        return None

    def get_by_field(self, field_name, value):
        """Get all records matching a specific field."""
        data = self._load_data()
        return [record for record in data if record.get(field_name) == value]

    def delete(self, record_id):
        """Delete a record by its unique ID."""
        new_data = [record for record in self._data if record.get("id") != record_id]
        if len(new_data) != len(self._data):
            self._data = new_data
            self.save_data(self._data)
            return True
        return False

    def delete_by_field(self, field_name, value):
        """Delete records by a specific field."""
        new_data = [record for record in self._data if record.get(field_name) != value]
        if len(new_data) != len(self._data):
            self._data = new_data
            self.save_data(self._data)
            return True
        return False

    def filter(self, **conditions):
        """Filter records matching multiple conditions."""
        data = self._load_data()
        return [
            record
            for record in data
            if all(record.get(field) == value for field, value in conditions.items())
        ]

    def count(self):
        """Count the number of records."""
        data = self._load_data()
        return len(data)

    def exists(self, field_name, value):
        """Check if a record exists by field and value."""
        data = self._load_data()
        return any(record.get(field_name) == value for record in data)

    def order_by(self, field_name, reverse=False):
        """Return all records ordered by a field."""

        def get_sort_key(record):
            return record.get(field_name, None)

        data = self._load_data()
        return sorted(data, key=get_sort_key, reverse=reverse)

    def migrate_add_field(self, field_name, default_value=None):
        """Add a new field to all records with a default value."""
        data = self._load_data()
        for record in data:
            if field_name not in record:
                record[field_name] = default_value
        self.save_data(data)

    def migrate_remove_field(self, field_name):
        """Remove a field from all records."""
        data = self._load_data()
        for record in data:
            record.pop(field_name, None)
        self.save_data(data)

    def all(self):
        """Return all records from the table."""
        return self._data

    def query(self):
        """Start a new query chain from all records."""
        return RecordQuery(self._data, dbtable=self)


class FileTableError(Exception):
    """Base exception for DBFileTable."""


class DuplicateEntryError(FileTableError):
    """Raised when a duplicate value is found for a unique field."""

    def __init__(self, field, value):
        super().__init__(f"Duplicate value for unique field '{field}': {value}")
        self.field = field
        self.value = value


class MissingRequiredFieldError(FileTableError):
    """Raised when a required field is missing in the record."""

    def __init__(self, field):
        super().__init__(f"Missing required field: {field}")
        self.field = field


class DatabaseVersionError(Exception):
    """Raised when database version is incompatible."""
