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
Migration utilities for PostgreSQL Enhanced

Supports migration from:
- SQLite databases
- Standard PostgreSQL addon (blob-only)
- Future: Other database backends
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
import pickle
import sqlite3
from datetime import datetime

# -------------------------------------------------------------------------
#
# PostgreSQL modules
#
# -------------------------------------------------------------------------
from psycopg.types.json import Jsonb

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------
OBJECT_TYPES = [
    "person",
    "family",
    "event",
    "place",
    "source",
    "citation",
    "media",
    "repository",
    "note",
    "tag",
]


# -------------------------------------------------------------------------
#
# MigrationManager class
#
# -------------------------------------------------------------------------
class MigrationManager:
    """
    Manages migration from other database backends to PostgreSQL Enhanced.

    Features:
    - SQLite to PostgreSQL migration
    - PostgreSQL standard to Enhanced migration
    - Progress callbacks
    - Data verification
    - Rollback support
    """

    def __init__(self, connection):
        """
        Initialize migration manager.

        :param connection: PostgreSQLConnection instance
        :type connection: PostgreSQLConnection
        """
        self.conn = connection
        self.log = logging.getLogger(".PostgreSQLEnhanced.Migration")

    def detect_migration_needed(self):
        """
        Detect if migration from another backend is needed.

        :returns: Migration type needed or None
        :rtype: str or None

        Possible return values:
        - 'sqlite': SQLite database detected
        - 'postgresql_standard': Standard PostgreSQL addon detected
        - 'needs_jsonb': Tables exist but no JSONB columns
        - None: No migration needed
        """
        # Check if tables exist
        if not self.conn.table_exists("person"):
            return None

        # Check for JSONB columns
        if not self.conn.column_exists("person", "json_data"):
            # Tables exist but no JSONB - standard PostgreSQL
            return "postgresql_standard"

        # Check if JSONB columns are empty
        self.conn.execute(
            """
            SELECT COUNT(*) FROM person
            WHERE json_data IS NOT NULL
        """
        )
        json_count = self.conn.fetchone()[0]

        if json_count == 0:
            # JSONB columns exist but are empty
            return "needs_jsonb"

        return None

    def migrate_from_sqlite(self, sqlite_path, callback=None):
        """
        Migrate data from a SQLite database.

        :param sqlite_path: Path to SQLite database file
        :type sqlite_path: str
        :param callback: Progress callback function(current, total, message)
        :type callback: callable or None
        :returns: Dictionary with migration statistics
        :rtype: dict
        """
        self.log.info("Starting migration from SQLite: %s", sqlite_path)

        stats = {
            "start_time": datetime.now(),
            "objects_migrated": {},
            "errors": [],
            "warnings": [],
        }

        try:
            # Open SQLite connection
            source = sqlite3.connect(sqlite_path)
            source.row_factory = sqlite3.Row

            # Calculate total objects
            total_objects = 0
            for obj_type in OBJECT_TYPES:
                cursor = source.execute("SELECT COUNT(*) FROM %s" % obj_type)
                count = cursor.fetchone()[0]
                total_objects += count
                stats["objects_migrated"][obj_type] = 0

            if callback:
                callback(0, total_objects, _("Starting migration..."))

            # Begin transaction
            self.conn.execute("BEGIN")

            try:
                current = 0

                # Migrate each object type
                for obj_type in OBJECT_TYPES:
                    if callback:
                        callback(
                            current,
                            total_objects,
                            _("Migrating %s objects..." % obj_type),
                        )

                    count = self._migrate_object_type(source, obj_type)
                    stats["objects_migrated"][obj_type] = count
                    current += count

                    if callback:
                        callback(
                            current,
                            total_objects,
                            _("Migrated %s {obj_type} objects" % count),
                        )

                # Migrate metadata
                self._migrate_metadata(source)

                # Migrate references
                self._migrate_references(source)

                # Migrate additional tables
                self._migrate_additional_tables(source)

                # Commit transaction
                self.conn.commit()

                if callback:
                    callback(total_objects, total_objects, _("Migration completed!"))

            except Exception as e:
                # Rollback on error
                self.conn.rollback()
                stats["errors"].append(str(e))
                self.log.error("Migration failed: %s", e)
                raise

            finally:
                source.close()

        except Exception as e:
            stats["errors"].append(str(e))
            self.log.error("Migration error: %s", e)
            raise

        stats["end_time"] = datetime.now()
        stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

        return stats

    def _migrate_object_type(self, source, obj_type):
        """
        Migrate all objects of a specific type.

        :param source: SQLite database connection
        :type source: sqlite3.Connection
        :param obj_type: Type of object to migrate
        :type obj_type: str
        :returns: Number of objects migrated
        :rtype: int
        """
        count = 0

        # Get all objects from SQLite
        cursor = source.execute("SELECT handle, blob_data FROM %s" % obj_type)

        for row in cursor:
            handle = row["handle"]
            blob_data = row["blob_data"]

            try:
                # Deserialize to get JSON representation
                obj = pickle.loads(blob_data)

                # Convert to JSON
                # Note: This is simplified - real implementation would
                # need proper object-to-dict conversion
                json_data = self._object_to_json(obj, obj_type)

                # Insert into PostgreSQL
                self.conn.execute(
                    f"""
                    INSERT INTO {obj_type} (handle, blob_data, json_data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (handle) DO UPDATE
                    SET blob_data = EXCLUDED.blob_data,
                        json_data = EXCLUDED.json_data
                """,
                    [handle, blob_data, Jsonb(json_data)],
                )

                count += 1

            except Exception as e:
                self.log.warning("Error migrating %s %s: %s", obj_type, handle, e)

        return count

    def _object_to_json(self, obj, obj_type):
        """
        Convert a Gramps object to JSON representation.

        This is a simplified version - the real implementation
        would use Gramps' built-in serialization.

        :param obj: Gramps object to convert
        :type obj: object
        :param obj_type: Type of object
        :type obj_type: str
        :returns: JSON-compatible dictionary
        :rtype: dict
        """
        # Get the serialized form
        if hasattr(obj, "serialize"):
            data = obj.serialize()
        else:
            data = obj

        # Convert to dictionary
        # This would need proper mapping for each object type
        json_data = {
            "handle": (
                data[0] if isinstance(data, (list, tuple)) else data.get("handle")
            ),
            "gramps_id": (
                data[1]
                if isinstance(data, (list, tuple)) and len(data) > 1
                else data.get("gramps_id")
            ),
            "_class": obj_type,
        }

        # Add raw data for now
        json_data["_raw"] = data

        return json_data

    def _migrate_metadata(self, source):
        """Migrate metadata table."""
        cursor = source.execute("SELECT setting, value FROM metadata")

        for row in cursor:
            setting = row["setting"]
            value = row["value"]

            # Skip schema version - we'll set our own
            if setting == "schema_version":
                continue

            self.conn.execute(
                """
                INSERT INTO metadata (setting, value)
                VALUES (%s, %s)
                ON CONFLICT (setting) DO UPDATE
                SET value = EXCLUDED.value
            """,
                [setting, value],
            )

    def _migrate_references(self, source):
        """Migrate reference table."""
        cursor = source.execute(
            """
            SELECT obj_handle, obj_class, ref_handle, ref_class
            FROM reference
        """
        )

        for row in cursor:
            self.conn.execute(
                """
                INSERT INTO reference
                (obj_handle, obj_class, ref_handle, ref_class)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """,
                [
                    row["obj_handle"],
                    row["obj_class"],
                    row["ref_handle"],
                    row["ref_class"],
                ],
            )

    def _migrate_additional_tables(self, source):
        """Migrate additional tables like gender_stats, surname, etc."""

        # Gender stats
        if self._table_exists_in_sqlite(source, "gender_stats"):
            cursor = source.execute(
                """
                SELECT given_name, male, female, unknown
                FROM gender_stats
            """
            )

            for row in cursor:
                self.conn.execute(
                    """
                    INSERT INTO gender_stats
                    (given_name, male, female, unknown)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (given_name) DO UPDATE
                    SET male = EXCLUDED.male,
                        female = EXCLUDED.female,
                        unknown = EXCLUDED.unknown
                """,
                    [row["given_name"], row["male"], row["female"], row["unknown"]],
                )

        # Surname list
        if self._table_exists_in_sqlite(source, "surname"):
            cursor = source.execute("SELECT surname, count FROM surname")

            for row in cursor:
                self.conn.execute(
                    """
                    INSERT INTO surname (surname, count)
                    VALUES (%s, %s)
                    ON CONFLICT (surname) DO UPDATE
                    SET count = EXCLUDED.count
                """,
                    [row["surname"], row["count"]],
                )

    def _table_exists_in_sqlite(self, connection, table_name):
        """Check if a table exists in SQLite database."""
        cursor = connection.execute(
            """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name=?
        """,
            [table_name],
        )
        return cursor.fetchone()[0] > 0

    def upgrade_to_enhanced(self, callback=None):
        """
        Upgrade from standard PostgreSQL backend to Enhanced.

        This adds JSONB columns and populates them from blob data.

        :param callback: Progress callback function
        :return: Dictionary with upgrade statistics
        """
        self.log.info("Upgrading to PostgreSQL Enhanced")

        stats = {"start_time": datetime.now(), "objects_upgraded": {}, "errors": []}

        # Calculate total objects
        total_objects = 0
        for obj_type in OBJECT_TYPES:
            self.conn.execute("SELECT COUNT(*) FROM %s" % obj_type)
            count = self.conn.fetchone()[0]
            total_objects += count

        if callback:
            callback(0, total_objects, _("Starting upgrade..."))

        current = 0

        # Add JSONB columns if they don't exist
        for obj_type in OBJECT_TYPES:
            if not self.conn.column_exists(obj_type, "json_data"):
                self.conn.execute(
                    f"""
                    ALTER TABLE {obj_type}
                    ADD COLUMN json_data JSONB
                """
                )

                self.conn.execute(
                    f"""
                    ALTER TABLE {obj_type}
                    ADD COLUMN gramps_id VARCHAR(50)
                    GENERATED ALWAYS AS (json_data->>'gramps_id') STORED
                """
                )

                self.conn.execute(
                    f"""
                    ALTER TABLE {obj_type}
                    ADD COLUMN change_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """
                )

        # Populate JSONB from blob data
        for obj_type in OBJECT_TYPES:
            if callback:
                callback(current, total_objects, _("Upgrading %s objects..." % obj_type))

            count = self._upgrade_object_type(obj_type)
            stats["objects_upgraded"][obj_type] = count
            current += count

        # Create indexes
        if callback:
            callback(current, total_objects, _("Creating indexes..."))

        from .schema import PostgreSQLSchema

        schema = PostgreSQLSchema(self.conn, use_jsonb=True)
        for obj_type in OBJECT_TYPES:
            schema._create_object_specific_indexes(obj_type)

        self.conn.commit()

        if callback:
            callback(total_objects, total_objects, _("Upgrade completed!"))

        stats["end_time"] = datetime.now()
        stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

        return stats

    def _upgrade_object_type(self, obj_type):
        """Upgrade all objects of a specific type to include JSONB."""
        count = 0

        # Get all objects with blob data but no JSON
        self.conn.execute(
            f"""
            SELECT handle, blob_data
            FROM {obj_type}
            WHERE blob_data IS NOT NULL
            AND json_data IS NULL
        """
        )

        rows = self.conn.fetchall()

        for handle, blob_data in rows:
            try:
                # Deserialize blob
                obj = pickle.loads(blob_data)

                # Convert to JSON
                json_data = self._object_to_json(obj, obj_type)

                # Update with JSON data
                self.conn.execute(
                    f"""
                    UPDATE {obj_type}
                    SET json_data = %s
                    WHERE handle = %s
                """,
                    [Jsonb(json_data), handle],
                )

                count += 1

            except Exception as e:
                self.log.warning("Error upgrading %s %s: %s", obj_type, handle, e)

        return count

    def verify_migration(self):
        """
        Verify data integrity after migration.

        Returns dictionary with verification results.
        """
        results = {"valid": True, "checks": {}, "errors": []}

        for obj_type in OBJECT_TYPES:
            # Check blob vs JSON counts
            self.conn.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(blob_data) as blob_count,
                    COUNT(json_data) as json_count
                FROM {obj_type}
            """
            )

            total, blob_count, json_count = self.conn.fetchone()

            results["checks"][obj_type] = {
                "total": total,
                "blob_count": blob_count,
                "json_count": json_count,
                "valid": blob_count == json_count,
            }

            if blob_count != json_count:
                results["valid"] = False
                results["errors"].append(
                    "%s: blob_count (%s) != json_count (%s)" % (
                        obj_type, blob_count, json_count
                    )
                )

        return results
