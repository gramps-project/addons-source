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
Unit tests for the FileTable class.

This module tests the core functionality of the FileTable class, including:
- Creating records with uniqueness and required field validation
- Bulk creation with duplicate handling
- Updating records with enforcement of unique constraints
- Deleting records by ID and by field
- Finding, filtering, and counting records
- Checking for record existence
- Ordering records by fields
- Migrating records (adding and removing fields)

Mocks are used to avoid real file operations during tests.
Each test ensures that the file table behaves correctly according to its configuration.
"""

import unittest
import os

from models import DBFileTableConfig
from constants import DuplicateHandlingMode, DB_FILE_TABLE_DIR
from db_file_table import (
    DBFileTable,
    DuplicateEntryError,
)


class TestDBFileTable(unittest.TestCase):
    """Test cases for DBFileTable class."""

    def setUp(self):
        """Set up mock configuration and mock file data."""
        self.config = DBFileTableConfig(
            filename="mock_file.json",
            cache_fields=["id", "email"],
            unique_fields=["email"],
            required_fields=["name"],
            set_created_at=True,
            set_updated_at=True,
            on_bulk_duplicate=DuplicateHandlingMode.THROW_ERROR.value,
        )
        self.filepath = os.path.join(DB_FILE_TABLE_DIR, self.config.filename)
        self.db = DBFileTable(self.config)

    def tearDown(self):
        """Clean up created files after each test."""
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def test_create_record(self):
        """Test the creation of a new record."""
        record = {"name": "John", "email": "john@example.com"}
        created = self.db.create(record.copy())
        self.assertIn("id", created)
        self.assertEqual(created["email"], "john@example.com")
        self.assertEqual(created["name"], "John")
        self.assertIn("created_at", created)
        self.assertIn("updated_at", created)
        all_records = self.db.all()
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0]["id"], created["id"])

    def test_create_record_with_duplicate_email(self):
        """Test creating a record with a duplicate email."""
        self.db.create({"name": "John", "email": "john@example.com"})
        duplicate_record = {"name": "Jane", "email": "john@example.com"}
        with self.assertRaises(DuplicateEntryError):
            self.db.create(duplicate_record)

    def test_update_record(self):
        """Test updating an existing record."""
        record = self.db.create({"name": "John", "email": "john@example.com"})
        record_id = record["id"]
        updates = {"name": "John Doe"}
        updated = self.db.update(record_id, updates)
        self.assertTrue(updated)
        updated_record = self.db.read_by_id(record_id)
        self.assertEqual(updated_record["name"], "John Doe")

    def test_update_record_with_duplicate_email(self):
        """Test updating a record to a duplicate email from another record."""
        self.db.create({"name": "John", "email": "john@example.com"})
        record2 = self.db.create({"name": "Jane", "email": "jane@example.com"})

        with self.assertRaises(DuplicateEntryError):
            self.db.update(record2["id"], {"email": "john@example.com"})

    def test_delete_record(self):
        """Test deleting a record."""
        record = self.db.create({"name": "John", "email": "john@example.com"})
        record_id = record["id"]
        deleted = self.db.delete(record_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.db.read_by_id(record_id))

    def test_delete_non_existent_record(self):
        """Test deleting a non-existent record."""
        self.db.create({"name": "John", "email": "john@example.com"})

        deleted = self.db.delete(999)
        self.assertFalse(deleted)

    def test_get_by_field(self):
        """Test getting records by a specific field."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Jane", "email": "jane@example.com"})
        result = self.db.get_by_field("email", "john@example.com")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["email"], "john@example.com")
        self.assertEqual(result[0]["name"], "John")

    def test_filter(self):
        """Test filtering records by multiple conditions."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "John", "email": "other@example.com"})
        self.db.create({"name": "Jane", "email": "mark@example.com"})
        result = self.db.filter(name="John", email="john@example.com")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "John")
        self.assertEqual(result[0]["email"], "john@example.com")

    def test_count(self):
        """Test counting records."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Jane", "email": "jane@example.com"})
        total = self.db.count()
        self.assertEqual(total, 2)

    def test_exists(self):
        """Test checking if a record exists."""
        self.db.create({"name": "John", "email": "john@example.com"})
        exists = self.db.exists("email", "john@example.com")
        self.assertTrue(exists)
        not_exists = self.db.exists("email", "jane@example.com")
        self.assertFalse(not_exists)

    def test_order_by(self):
        """Test ordering records by a field."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Alice", "email": "alice@example.com"})
        result = self.db.order_by("name", reverse=True)
        self.assertEqual(result[0]["name"], "John")
        self.assertEqual(result[1]["name"], "Alice")

    def test_migrate_add_field(self):
        """Test adding a new field to existing records."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.migrate_add_field("phone", "unknown")
        data = self.db.all()
        self.assertTrue(all("phone" in record for record in data))
        self.assertTrue(all(record["phone"] == "unknown" for record in data))

    def test_migrate_remove_field(self):
        """Test removing a field from records."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.migrate_remove_field("name")
        data = self.db.all()
        self.assertTrue(all("name" not in record for record in data))

    def test_create_without_timestamps(self):
        """Ensure timestamps are not set when disabled in config."""
        self.db.config.set_created_at = False
        self.db.config.set_updated_at = False
        record = self.db.create({"name": "John", "email": "john@example.com"})
        self.assertNotIn("created_at", record)
        self.assertNotIn("updated_at", record)

    def test_bulk_create_throw_error(self):
        """Ensure bulk_create raises on duplicate when THROW_ERROR is set."""
        records = [
            {"name": "John", "email": "john@example.com"},
            {"name": "Jane", "email": "john@example.com"},
        ]
        with self.assertRaises(DuplicateEntryError):
            self.db.bulk_create(records)

    def test_id_autoincrement(self):
        """Ensure that IDs are auto-incremented sequentially."""
        r1 = self.db.create({"name": "John", "email": "john1@example.com"})
        r2 = self.db.create({"name": "Jane", "email": "john2@example.com"})
        self.assertEqual(r2["id"], r1["id"] + 1)

    def test_read_by_id_not_found(self):
        """Ensure read_by_id returns None for non-existent ID."""
        result = self.db.read_by_id(999)
        self.assertIsNone(result)

    def test_delete_by_field(self):
        """Ensure records can be deleted by field value."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Jane", "email": "jane@example.com"})
        deleted = self.db.delete_by_field("name", "John")
        self.assertTrue(deleted)
        remaining = self.db.get_by_field("name", "John")
        self.assertEqual(len(remaining), 0)

    def test_query_chain(self):
        """Ensure chained query using where() returns correct records."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Jane", "email": "jane@example.com"})
        result = self.db.query().where(name="Jane").get()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["email"], "jane@example.com")

    def test_missing_required_field_raises(self):
        """Ensure missing required field raises an error on create."""
        self.db.config.required_fields.append("email")
        with self.assertRaises(Exception):
            self.db.create({"name": "No Email"})

    def test_id_first_in_create(self):
        """Test that 'id' is the first key in a newly created record."""
        record = {"name": "John", "email": "john@example.com"}
        created = self.db.create(record.copy())
        self.assertEqual(list(created.keys())[0], "id")

    def test_id_first_in_update(self):
        """Test that 'id' remains the first key after update."""
        created = self.db.create({"name": "John", "email": "john@example.com"})
        record_id = created["id"]
        self.db.update(record_id, {"name": "Johnny"})
        updated = self.db.read_by_id(record_id)
        self.assertEqual(list(updated.keys())[0], "id")

    def test_query_exists_and_count(self):
        """Test the exists() and count() query methods."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Jane", "email": "jane@example.com"})

        query = self.db.query().where(name="Jane")
        self.assertTrue(query.exists())
        self.assertEqual(query.count(), 1)

        empty_query = self.db.query().where(name="Nonexistent")
        self.assertFalse(empty_query.exists())
        self.assertEqual(empty_query.count(), 0)

    def test_query_sort_by(self):
        """Test sort_by direction in queries."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Alice", "email": "alice@example.com"})

        results_asc = self.db.query().sort_by("name", "asc").get()
        self.assertEqual(results_asc[0]["name"], "Alice")
        self.assertEqual(results_asc[1]["name"], "John")

        results_desc = self.db.query().sort_by("name", "desc").get()
        self.assertEqual(results_desc[0]["name"], "John")
        self.assertEqual(results_desc[1]["name"], "Alice")

    def test_values_list(self):
        """Test values_list returns correct field values from filtered records."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Alice", "email": "alice@example.com"})
        self.db.create({"name": "Bob", "email": "bob@example.com"})

        result = self.db.query().where("name", "Alice").values_list("email")
        self.assertEqual(result, ["alice@example.com"])

    def test_all_values_list(self):
        """Test all_values_list returns correct field values from all records."""
        self.db.create({"name": "John", "email": "john@example.com"})
        self.db.create({"name": "Alice", "email": "alice@example.com"})
        self.db.create({"name": "Bob", "email": "bob@example.com"})

        result = self.db.query().all_values_list("name")
        self.assertEqual(set(result), {"John", "Alice", "Bob"})

    def test_delete_persists_to_file(self):
        """Test that deleting a record via query removes it from both memory and file."""
        self.db.create({"name": "John", "id": 1})
        self.db.create({"name": "Jane", "id": 2})

        assert self.db.count() == 2
        self.db.query().where("name", "John").delete()
        assert self.db.count() == 1
        remaining = self.db.all()
        assert remaining[0]["name"] == "Jane"

    def test_sorting_order(self):
        """Test _sort_record_fields orders fields as expected."""

        sorted_record = self.db.create(
            {
                "updated_at": "2025-05-03T10:00:00",
                "name": "Example",
                "saves_record_id": 22,
                "created_at": "2025-05-03T09:00:00",
                "source_file_path": "/tmp/file.csv",
                "visits_record_id": 12,
            }
        )

        expected_keys = [
            "id",
            "saves_record_id",
            "visits_record_id",
            "name",
            "source_file_path",
            "created_at",
            "updated_at",
        ]

        self.assertEqual(list(sorted_record.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
