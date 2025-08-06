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
PostgreSQL Enhanced schema management for Gramps

Handles:
- Schema creation with dual storage (blob + JSONB)
- Schema versioning and upgrades
- Index optimization
- PostgreSQL-specific features
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
import pickle
import sys
import os
from psycopg import sql
from psycopg.types.json import Jsonb

# Import local modules using relative imports
from schema_columns import REQUIRED_COLUMNS, REQUIRED_INDEXES

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
SCHEMA_VERSION = 21  # Must match Gramps DBAPI version

# Gramps object types
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
# PostgreSQLSchema class
#
# -------------------------------------------------------------------------
class PostgreSQLSchema:
    """
    Manages PostgreSQL schema for Gramps Enhanced.

    Features:
    - Dual storage (blob + JSONB)
    - Automatic schema creation
    - Version management
    - Index optimization
    - Future upgrade support
    """

    def __init__(self, connection, use_jsonb=True, table_prefix=""):
        """
        Initialize schema manager.

        :param connection: PostgreSQLConnection instance
        :param use_jsonb: Whether to create JSONB columns
        :param table_prefix: Prefix for table names (for shared database mode)
        """
        self.conn = connection
        self.use_jsonb = use_jsonb
        self.table_prefix = table_prefix
        self.log = logging.getLogger(".PostgreSQLEnhanced.Schema")

    def _table_name(self, base_name):
        """Get actual table name with prefix if in shared mode."""
        return f"{self.table_prefix}{base_name}"

    def check_and_init_schema(self):
        """
        Check if schema exists and initialize if needed.

        This is called automatically when a database is opened,
        similar to SQLite's automatic table creation.
        """
        # Check if metadata table exists
        if not self.conn.table_exists(self._table_name("metadata")):
            # First time setup - create all tables
            self.log.info(
                "Creating new PostgreSQL Enhanced schema%s",
                " with prefix: " + self.table_prefix if self.table_prefix else "",
            )
            self._create_schema()
        else:
            # Check schema version and upgrade if needed
            current_version = self._get_schema_version()
            if current_version < SCHEMA_VERSION:
                self.log.info(
                    "Upgrading schema from v%s to v%s", current_version, SCHEMA_VERSION
                )
                self._upgrade_schema(current_version)

    def _create_schema(self):
        """
        Create the initial database schema.

        Creates tables that match SQLite schema but with
        PostgreSQL enhancements.
        """
        # Create metadata table
        if self.use_jsonb:
            # Enhanced metadata with JSON support
            # JSONSerializer expects json_data column for metadata
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name('metadata')} (
                    setting VARCHAR(255) PRIMARY KEY,
                    value BYTEA,  -- Keep for compatibility
                    json_data JSONB,  -- JSONSerializer uses this
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
        else:
            # Basic metadata (blob only)
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name('metadata')} (
                    setting VARCHAR(255) PRIMARY KEY,
                    value BYTEA
                )
            """
            )

        # Create object tables
        for obj_type in OBJECT_TYPES:
            self._create_object_table(obj_type)

        # Create reference table (for backlinks)
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table_name('reference')} (
                obj_handle VARCHAR(50),
                obj_class VARCHAR(50),
                ref_handle VARCHAR(50),
                ref_class VARCHAR(50),
                PRIMARY KEY (obj_handle, obj_class, ref_handle, ref_class)
            )
        """
        )

        # Create indexes for references
        self.conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_reference_ref
                ON {self._table_name('reference')} (ref_handle, ref_class)
        """
        )

        self.conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_reference_obj
                ON {self._table_name('reference')} (obj_handle, obj_class)
        """
        )

        # Create gender stats table
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table_name('gender_stats')} (
                given_name VARCHAR(255) PRIMARY KEY,
                male INTEGER DEFAULT 0,
                female INTEGER DEFAULT 0,
                unknown INTEGER DEFAULT 0
            )
        """
        )

        # Create surname list table
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS surname (
                surname VARCHAR(255) PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """
        )

        # Create name group table
        # DBAPI expects columns named 'name' and 'grouping'
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS name_group (
                name VARCHAR(255) PRIMARY KEY,
                grouping VARCHAR(255)
            )
        """
        )

        # Create PostgreSQL-specific features FIRST (includes extensions)
        if self.use_jsonb:
            self._create_enhanced_features()

        # Set initial schema version
        self._set_schema_version(SCHEMA_VERSION)

        self.conn.commit()
        self.log.info("PostgreSQL Enhanced schema created successfully")

    def _create_object_table(self, obj_type):
        """Create a table for a specific object type with regular secondary columns."""
        if self.use_jsonb:
            # Build regular column definitions (not GENERATED)
            regular_columns = []
            if obj_type in REQUIRED_COLUMNS:
                for col_name, json_path in REQUIRED_COLUMNS[obj_type].items():
                    # Determine column type
                    col_type = "VARCHAR(255)"
                    if "INTEGER" in json_path:
                        col_type = "INTEGER"
                    elif "BOOLEAN" in json_path:
                        col_type = "BOOLEAN"
                    elif col_name in [
                        "title",
                        "desc_",
                        "description",
                        "author",
                        "pubinfo",
                        "abbrev",
                        "page",
                        "name",
                        "path",
                        "given_name",
                        "surname",
                    ]:
                        col_type = "TEXT"
                    elif col_name in [
                        "father_handle",
                        "mother_handle",
                        "source_handle",
                        "place",
                        "enclosed_by",
                    ]:
                        col_type = "VARCHAR(50)"

                    # Regular columns that will be updated by _update_secondary_values
                    regular_columns.append(f"{col_name} {col_type}")

            # Join column definitions
            regular_cols_sql = ""
            if regular_columns:
                regular_cols_sql = (
                    ",\n                    ".join(regular_columns)
                    + ",\n                    "
                )

            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name(obj_type)} (
                    handle VARCHAR(50) PRIMARY KEY,
                    json_data JSONB NOT NULL,  -- JSONSerializer stores here
                    {regular_cols_sql}change_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create indexes on secondary columns
            if obj_type in REQUIRED_INDEXES:
                for column in REQUIRED_INDEXES[obj_type]:
                    self.conn.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}{obj_type}_{column}
                        ON {self._table_name(obj_type)} ({column})
                    """
                    )

            # Create GIN index for general JSONB queries
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}{obj_type}_json
                    ON {self._table_name(obj_type)} USING GIN (json_data)
            """
            )

            # Create object-specific indexes
            self._create_object_specific_indexes(obj_type)

        else:
            # Basic table (blob only)
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name(obj_type)} (
                    handle VARCHAR(50) PRIMARY KEY,
                    blob_data BYTEA
                )
            """
            )

    def _create_object_specific_indexes(self, obj_type):
        """Create indexes specific to each object type."""
        # Indexes on secondary columns are already created above

        # Then add our enhanced indexes for better performance
        if obj_type == "person":
            # Name searches
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}person_names
                    ON {self._table_name('person')} USING GIN ((json_data->'names'))
            """
            )

            # Birth/death dates
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}person_birth_date
                    ON {self._table_name('person')}
                    ((json_data->'birth_ref_index'->>'date'))
            """
            )

        elif obj_type == "family":
            # Parent searches
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}family_parents
                    ON {self._table_name('family')}
                    USING GIN ((json_data->'parent_handles'))
            """
            )

        elif obj_type == "event":
            # Event type and date
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}event_type_date
                    ON {self._table_name('event')}
                    ((json_data->>'type'), (json_data->>'date'))
            """
            )

        elif obj_type == "place":
            # Place hierarchy
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}place_hierarchy
                    ON {self._table_name('place')}
                    USING GIN ((json_data->'placeref_list'))
            """
            )

        elif obj_type == "source":
            # Source title
            self.conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}source_title
                    ON {self._table_name('source')} ((json_data->>'title'))
            """
            )

        elif obj_type == "note":
            # Full-text search on notes
            try:
                # Check if pg_trgm is loaded
                cur = self.conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'
                    )
                """
                )
                if cur.fetchone()[0]:
                    self.conn.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS idx_{self.table_prefix}note_text_trgm
                            ON {self._table_name('note')} USING GIN
                            ((json_data->>'text') gin_trgm_ops)
                    """
                    )
            except Exception as e:
                self.log.debug("Could not create trigram index on notes: %s", e)

    def _create_enhanced_features(self):
        """Create PostgreSQL-specific enhanced features."""

        # Create custom functions for common queries
        self.conn.execute(
            """
            CREATE OR REPLACE FUNCTION get_person_name(json_data JSONB)
            RETURNS TEXT AS $$
            DECLARE
                name_obj JSONB;
            BEGIN
                name_obj := json_data->'names'->0;
                RETURN COALESCE(
                    name_obj->>'first_name' || ' ' || name_obj->>'surname',
                    name_obj->>'first_name',
                    name_obj->>'surname',
                    'Unknown'
                );
            END;
            $$ LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE;
        """
        )

        # Create function for relationship queries
        self.conn.execute(
            f"""
            CREATE OR REPLACE FUNCTION get_family_members(family_handle TEXT)
            RETURNS TABLE(handle TEXT, role TEXT) AS $$
            BEGIN
                -- Get parents
                RETURN QUERY
                SELECT jsonb_array_elements_text(f.json_data->'parent_handles'), 'parent'::TEXT
                FROM {self._table_name('family')} f
                WHERE f.handle = family_handle;

                -- Get children
                RETURN QUERY
                SELECT jsonb_array_elements_text(f.json_data->'child_ref_list'), 'child'::TEXT
                FROM {self._table_name('family')} f
                WHERE f.handle = family_handle;
            END;
            $$ LANGUAGE plpgsql STABLE PARALLEL SAFE;
        """
        )

        # Enable extensions if available
        self._enable_useful_extensions()

    def _enable_useful_extensions(self):
        """Enable PostgreSQL extensions that benefit genealogy queries."""

        extensions = [
            ("pg_trgm", "Trigram similarity searches"),
            ("btree_gin", "Better GIN index performance"),
            ("intarray", "Array operations"),
        ]

        for ext_name, description in extensions:
            if self._check_extension_available(ext_name):
                try:
                    self.conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext_name}")
                    self.log.info("Enabled %s extension: %s", ext_name, description)
                except Exception as e:
                    self.log.debug("Could not enable %s: %s", ext_name, e)

    def _check_extension_available(self, extension_name):
        """Check if a PostgreSQL extension is available."""
        self.conn.execute(
            """
            SELECT COUNT(*) FROM pg_available_extensions
            WHERE name = %s
        """,
            [extension_name],
        )
        return self.conn.fetchone()[0] > 0

    def _get_schema_version(self):
        """Get current schema version from metadata."""
        self.conn.execute(
            f"SELECT value FROM {self._table_name('metadata')} WHERE setting = 'schema_version'"
        )
        row = self.conn.fetchone()
        if row and row[0]:
            return pickle.loads(row[0])
        return 0

    def _set_schema_version(self, version):
        """Set schema version in metadata."""
        if self.use_jsonb:
            self.conn.execute(
                f"""
                INSERT INTO {self._table_name('metadata')} (setting, value, json_data)
                VALUES ('schema_version', %s, %s)
                ON CONFLICT (setting) DO UPDATE
                SET value = EXCLUDED.value,
                    json_data = EXCLUDED.json_data,
                    updated_at = CURRENT_TIMESTAMP
            """,
                [pickle.dumps(version), Jsonb(version)],
            )
        else:
            self.conn.execute(
                f"""
                INSERT INTO {self._table_name('metadata')} (setting, value)
                VALUES ('schema_version', %s)
                ON CONFLICT (setting) DO UPDATE
                SET value = EXCLUDED.value
            """,
                [pickle.dumps(version)],
            )

    def _upgrade_schema(self, from_version):
        """
        Upgrade schema from one version to another.

        This method will handle future schema upgrades.
        """
        # Future schema upgrades will be implemented here
        # For now, just update the version
        if from_version < 1:
            # Initial version - no upgrades needed yet
            pass

        # Update version
        self._set_schema_version(SCHEMA_VERSION)
        self.conn.commit()

    def get_schema_info(self):
        """Get information about the current schema."""
        info = {
            "version": self._get_schema_version(),
            "use_jsonb": self.use_jsonb,
            "tables": {},
        }

        # Get table information
        self.conn.execute(
            """
            SELECT table_name,
                   pg_size_pretty(pg_total_relation_size(table_schema||'.'||table_name)) as size,
                   (SELECT COUNT(*) FROM information_schema.columns c
                    WHERE c.table_name = t.table_name) as column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        )

        for table_name, size, column_count in self.conn.fetchall():
            info["tables"][table_name] = {"size": size, "columns": column_count}

        return info
