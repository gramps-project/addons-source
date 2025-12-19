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
Schema migration support for PostgreSQL Enhanced.

This module handles automatic schema upgrades when opening
existing databases with newer versions of the driver.
"""

import logging
from psycopg import sql

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------

# Track our internal schema changes separate from Gramps DBAPI version
# Format: (major, minor, patch)
# - major: Breaking changes requiring manual migration
# - minor: Automatic migrations (like VARCHAR to TEXT)
# - patch: Bug fixes with no schema changes
INTERNAL_SCHEMA_VERSION = (1, 1, 0)  # Version 1.1.0 adds TEXT migration

# Migration history
MIGRATIONS = {
    (1, 0, 0): "Initial PostgreSQL Enhanced schema",
    (1, 1, 0): "Convert VARCHAR(255) to TEXT for long string support",
}

# -------------------------------------------------------------------------
#
# Migration Functions
#
# -------------------------------------------------------------------------

def migrate_1_0_to_1_1(conn, table_prefix=""):
    """
    Migrate from version 1.0 to 1.1
    - Convert VARCHAR(255) columns to TEXT
    """
    logger = logging.getLogger(".PostgreSQLEnhanced.Migration")
    logger.info("Migrating schema from 1.0 to 1.1: VARCHAR(255) to TEXT")

    migrations = [
        # Metadata table
        (f"{table_prefix}metadata", "setting", "TEXT"),

        # Gender stats table
        (f"{table_prefix}gender_stats", "given_name", "TEXT"),

        # Surname table
        ("surname", "surname", "TEXT"),  # Note: no prefix for surname table

        # Name group table
        ("name_group", "name", "TEXT"),  # Note: no prefix for name_group table
        ("name_group", "grouping", "TEXT"),

        # Reference table - class columns
        (f"{table_prefix}reference", "obj_class", "TEXT"),
        (f"{table_prefix}reference", "ref_class", "TEXT"),
    ]

    # Also need to migrate any dynamic columns in object tables
    # These would have been created as VARCHAR(255) by default
    object_tables = [
        "person", "family", "event", "place", "source",
        "citation", "media", "repository", "note", "tag"
    ]

    with conn.cursor() as cur:
        # First, get list of all VARCHAR(255) columns in object tables
        for obj_type in object_tables:
            table_name = f"{table_prefix}{obj_type}"

            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                    AND table_schema = 'public'
                    AND data_type = 'character varying'
                    AND character_maximum_length = 255
            """, [table_name])

            for (column_name,) in cur.fetchall():
                migrations.append((table_name, column_name, "TEXT"))

        # Now perform all migrations
        success_count = 0
        for table, column, new_type in migrations:
            try:
                # Check if table and column exist
                cur.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_name = %s
                        AND column_name = %s
                        AND table_schema = 'public'
                """, [table, column])

                if cur.fetchone()[0] > 0:
                    # Column exists, migrate it
                    alter_sql = sql.SQL(
                        "ALTER TABLE {} ALTER COLUMN {} TYPE {}"
                    ).format(
                        sql.Identifier(table),
                        sql.Identifier(column),
                        sql.SQL(new_type)
                    )

                    cur.execute(alter_sql)
                    logger.debug(f"Migrated {table}.{column} to {new_type}")
                    success_count += 1

            except Exception as e:
                logger.warning(f"Could not migrate {table}.{column}: {e}")
                # Continue with other migrations

    logger.info(f"Migration complete: {success_count} columns converted to TEXT")
    return True


# -------------------------------------------------------------------------
#
# SchemaMigrator class
#
# -------------------------------------------------------------------------

class SchemaMigrator:
    """
    Handles automatic schema migrations for PostgreSQL Enhanced.
    """

    def __init__(self, connection, table_prefix=""):
        """
        Initialize the migrator.

        :param connection: PostgreSQLConnection instance
        :param table_prefix: Table prefix for shared database mode
        """
        self.conn = connection
        self.table_prefix = table_prefix
        self.log = logging.getLogger(".PostgreSQLEnhanced.SchemaMigrator")

    def get_internal_version(self):
        """
        Get the internal schema version from the database.

        Returns tuple (major, minor, patch) or (1, 0, 0) if not set.
        """
        try:
            self.conn.execute(
                f"""
                SELECT json_data
                FROM {self.table_prefix}metadata
                WHERE setting = 'internal_schema_version'
                """
            )
            row = self.conn.fetchone()
            if row and row[0]:
                version = row[0]
                if isinstance(version, dict):
                    return tuple(version.get('version', [1, 0, 0]))
                elif isinstance(version, (list, tuple)):
                    return tuple(version)
            return (1, 0, 0)  # Default to 1.0.0 for existing databases
        except Exception as e:
            self.log.debug(f"Could not get internal version: {e}")
            return (1, 0, 0)

    def set_internal_version(self, version):
        """
        Set the internal schema version in the database.

        :param version: Tuple (major, minor, patch)
        """
        from psycopg.types.json import Jsonb

        version_data = {'version': list(version)}

        self.conn.execute(
            f"""
            INSERT INTO {self.table_prefix}metadata (setting, json_data)
            VALUES ('internal_schema_version', %s)
            ON CONFLICT (setting) DO UPDATE
            SET json_data = EXCLUDED.json_data
            """,
            [Jsonb(version_data)]
        )

    def check_and_migrate(self):
        """
        Check if migrations are needed and apply them.

        This is called automatically when opening a database.
        """
        current_version = self.get_internal_version()
        target_version = INTERNAL_SCHEMA_VERSION

        if current_version >= target_version:
            # No migration needed
            return True

        self.log.info(
            f"Database schema migration needed: {current_version} -> {target_version}"
        )

        # Apply migrations in order
        if current_version < (1, 1, 0) and target_version >= (1, 1, 0):
            # Apply VARCHAR to TEXT migration
            if not migrate_1_0_to_1_1(self.conn, self.table_prefix):
                return False

        # Update version
        self.set_internal_version(target_version)
        self.conn.commit()

        self.log.info(f"Schema migration complete: now at version {target_version}")
        return True

    def get_migration_status(self):
        """
        Get information about migration status.

        Returns dict with current version and available migrations.
        """
        current = self.get_internal_version()
        target = INTERNAL_SCHEMA_VERSION

        status = {
            'current_version': f"{current[0]}.{current[1]}.{current[2]}",
            'target_version': f"{target[0]}.{target[1]}.{target[2]}",
            'up_to_date': current >= target,
            'migrations_available': []
        }

        # List available migrations
        for version, description in MIGRATIONS.items():
            if version > current and version <= target:
                status['migrations_available'].append({
                    'version': f"{version[0]}.{version[1]}.{version[2]}",
                    'description': description
                })

        return status