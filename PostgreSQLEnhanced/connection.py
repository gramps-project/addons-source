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
PostgreSQL Enhanced connection handling for Gramps

Provides advanced connection management including:
- Multiple connection string formats
- Connection pooling support
- SSL/TLS configuration
- Query translation and optimization
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
import os
import re
from urllib.parse import urlparse, parse_qs
from contextlib import contextmanager

# -------------------------------------------------------------------------
#
# PostgreSQL modules
#
# -------------------------------------------------------------------------
import psycopg
from psycopg import sql

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db.dbconst import ARRAYSIZE


# -------------------------------------------------------------------------
#
# PostgreSQLConnection class
#
# -------------------------------------------------------------------------
class PostgreSQLConnection:
    """
    PostgreSQL Enhanced connection wrapper that provides:
    - Advanced connection management
    - Query translation for SQLite compatibility
    - Performance optimizations
    - Connection pooling support
    """

    def __init__(self, connection_info, username=None, password=None):
        """
        Create a new PostgreSQL Enhanced connection.

        Handles various connection string formats:
        - postgresql://user:pass@host:port/dbname?sslmode=require
        - postgres://...  (alias)
        - host:port:dbname:schema
        - dbname (local connection)

        Environment variables are also supported:
        - PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
        """
        self.log = logging.getLogger(".PostgreSQLEnhanced")
        self._pool = None
        self._connection = None
        self._savepoints = []
        self._persistent_cursor = None
        self._persistent_conn = None
        self._last_cursor = None
        self.schema = "public"  # Default schema

        # Parse connection string
        conninfo, options = self._parse_connection_string(
            connection_info, username, password
        )

        # Log connection attempt
        self.log.debug(
            "Connecting to PostgreSQL: %s", self._sanitize_conninfo(conninfo)
        )

        # Handle connection pooling if requested
        pool_size = options.get("pool_size", 0)
        if pool_size > 1:
            self._create_pool(conninfo, pool_size)
        else:
            self._create_connection(conninfo)

        # Set up the connection
        self._setup_connection()

        # Configure JSONB handling for Gramps compatibility
        self._setup_jsonb_handling()

        # Track prepared statements
        self._prepared_statements = {}

        # Setup collation support
        self._collations = []
        self.check_collation(glocale)

        # Store options from parsing
        self.schema = options.get("schema", "public")

    def _parse_connection_string(
        self, connection_info, username, password
    ):  # pylint: disable=too-many-branches
        """
        Parse various connection string formats.

        Returns: (conninfo, options) tuple
        """
        options = {}

        self.log.debug("Parsing connection string: %s", connection_info)

        if connection_info.startswith(("postgresql://", "postgres://")):
            # URL format - parse options from query string
            parsed = urlparse(connection_info)
            if parsed.query:
                options = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                # Remove options from connection string
                base_url = connection_info.split("?")[0]
                conninfo = base_url
            else:
                conninfo = connection_info

        elif ":" in connection_info and connection_info.count(":") >= 2:
            # Traditional format: host:port:dbname[:schema]
            parts = connection_info.split(":")
            host = parts[0] or "localhost"
            port = parts[1] or "5432"
            dbname = parts[2]

            conninfo = "host=%s port=%s dbname=%s" % (host, port, dbname)
            if username:
                conninfo += " user=%s" % username
            if password:
                conninfo += " password=%s" % password

            # Handle schema if provided
            if len(parts) > 3:
                options["schema"] = parts[3]
            else:
                options["schema"] = "public"

        else:
            # Simple database name or key=value format
            if "=" in connection_info:
                # Already in key=value format
                conninfo = connection_info
            else:
                # Just a database name
                conninfo = "dbname=%s" % connection_info

            if username:
                conninfo += " user=%s" % username
            if password:
                conninfo += " password=%s" % password
            options["schema"] = "public"

        # Add any environment variables not already in conninfo
        self._add_environment_variables(conninfo)

        self.log.debug("Final conninfo: %s, options: %s", conninfo, options)
        return conninfo, options

    def _sanitize_conninfo(self, conninfo):
        """Sanitize connection info for logging (hide passwords)."""
        # Hide password in connection string

        sanitized = re.sub(r"password=[^ ]+", "password=***", conninfo)
        sanitized = re.sub(r":[^:@]+@", ":***@", sanitized)
        return sanitized

    def _add_environment_variables(self, conninfo):
        """Add PostgreSQL environment variables to connection string."""
        env_mapping = {
            "PGHOST": "host",
            "PGPORT": "port",
            "PGUSER": "user",
            "PGPASSWORD": "password",
            "PGDATABASE": "dbname",
            "PGSSLMODE": "sslmode",
        }

        for env_var, param in env_mapping.items():
            if env_var in os.environ and param not in conninfo:
                conninfo += " %s=%s" % (param, os.environ[env_var])

        return conninfo

    def _create_connection(self, conninfo):
        """Create a single database connection."""
        self.log.debug("Creating connection with conninfo: %s", conninfo)
        self._connection = psycopg.connect(conninfo)
        self._connection.autocommit = False

    def _create_pool(self, conninfo, pool_size):
        """Create a connection pool."""
        # Note: psycopg3 has built-in pool support
        from psycopg_pool import (
            ConnectionPool,
        )  # pylint: disable=import-outside-toplevel

        self._pool = ConnectionPool(
            conninfo,
            min_size=1,
            max_size=pool_size,
            timeout=30.0,
        )
        self.log.info("Created connection pool with size %s", pool_size)

    def _setup_connection(self):
        """Set up the connection with required functions and settings."""
        with self._get_cursor() as cur:
            # Create REGEXP function for SQLite compatibility
            cur.execute(
                """
                CREATE OR REPLACE FUNCTION regexp(pattern text, string text)
                RETURNS boolean AS $$
                BEGIN
                    RETURN string ~ pattern;
                END;
                $$ LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE;
            """
            )

            # Create case-insensitive regexp function
            cur.execute(
                """
                CREATE OR REPLACE FUNCTION regexpi(pattern text, string text)
                RETURNS boolean AS $$
                BEGIN
                    RETURN string ~* pattern;
                END;
                $$ LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE;
            """
            )

            # Set search_path if schema was specified
            if hasattr(self, "schema") and self.schema != "public":
                cur.execute(
                    sql.SQL("SET search_path TO {}, public").format(
                        sql.Identifier(self.schema)
                    )
                )

            self._commit()

    def _setup_jsonb_handling(self):
        """Configure JSONB to return as JSON strings for Gramps compatibility."""
        # We handle JSONB conversion in fetchone/fetchall/fetchmany instead

    @contextmanager
    def _get_cursor(self, row_factory=None):
        """Get a cursor from connection or pool."""
        if self._pool:
            with self._pool.connection() as conn:
                with conn.cursor(row_factory=row_factory) as cur:
                    yield cur
        else:
            with self._connection.cursor(row_factory=row_factory) as cur:
                yield cur

    def check_collation(self, locale):
        """
        Check and setup collation for locale.
        PostgreSQL has built-in collation support.
        """
        collation = locale.get_collation()

        # PostgreSQL uses different collation names than Gramps
        # Map common Gramps collations to PostgreSQL
        collation_map = {
            "en_US.UTF-8": "en_US.utf8",
            "en_GB.UTF-8": "en_GB.utf8",
            "de_DE.UTF-8": "de_DE.utf8",
            "fr_FR.UTF-8": "fr_FR.utf8",
        }

        pg_collation = collation_map.get(collation, collation)

        # Check if collation exists
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM pg_collation
                WHERE collname = %s
            """,
                [pg_collation],
            )

            if cur.fetchone()[0] == 0:
                self.log.warning("Collation %s not found, using default", pg_collation)
                pg_collation = "default"

        if pg_collation not in self._collations:
            self._collations.append(pg_collation)

        return pg_collation

    def _convert_args_for_postgres(self, query, args):
        """
        Convert SQLite-style arguments to PostgreSQL-compatible types.

        Specifically handles:
        - Integer to boolean conversion for 'private' column
        - Other type conversions as needed
        """
        if not args:
            return args

        # Check if this is an UPDATE statement with 'private' column
        if "private = " in query.lower():
            # Convert args to list for modification
            converted_args = list(args)

            # Find position of 'private' in the SET clause
            sets_part = query.lower().split("set")[1].split("where")[0]
            columns = [
                col.strip().split("=")[0].strip() for col in sets_part.split(",")
            ]

            # Convert integer to boolean for 'private' column
            for i, col in enumerate(columns):
                if col == "private" and i < len(converted_args):
                    val = converted_args[i]
                    if isinstance(val, int):
                        converted_args[i] = bool(val)

            return converted_args

        return args

    def execute(self, query, args=None):
        """
        Execute an SQL statement.

        Provides SQLite compatibility by:
        - Converting ? placeholders to %s
        - Translating SQLite-specific syntax
        - Optimizing common queries
        - Converting data types for PostgreSQL
        - Handling GENERATED column UPDATE errors
        """
        # Translate query for PostgreSQL
        pg_query = self._translate_query(query)

        # Convert arguments for PostgreSQL compatibility
        pg_args = self._convert_args_for_postgres(pg_query, args)

        self.log.debug("SQL: %s", pg_query)
        if pg_args:
            self.log.debug("Args: %s", pg_args)

        # Get a persistent cursor for DBAPI compatibility
        if not hasattr(self, "_persistent_cursor") or self._persistent_cursor is None or self._persistent_cursor.closed:
            if self._pool:
                # For pools, get a connection from the pool
                self._persistent_conn = self._pool.getconn()
                self._persistent_cursor = self._persistent_conn.cursor()
            else:
                self._persistent_cursor = self._connection.cursor()

        # Execute query
        cur = self._persistent_cursor
        try:
            if pg_args:
                cur.execute(pg_query, pg_args)
            else:
                cur.execute(pg_query)
        except Exception as e:
            # Rollback on errors to prevent "current transaction is aborted" errors
            self.rollback()
            raise e

        # Store cursor reference for compatibility
        self._last_cursor = cur

        # Return the cursor (stays open for fetch operations)
        return cur

    def _translate_query(self, query):
        """
        Translate SQLite query to PostgreSQL.

        More sophisticated than the basic addon's approach.
        """
        # Convert ? placeholders to %s
        if "?" in query:
            query = query.replace("?", "%s")

        # No longer needed - we handle JSONB at the psycopg3 level
        # in _setup_jsonb_handling()

        # Handle REGEXP operator
        query = re.sub(r"\bREGEXP\b", "~", query, flags=re.IGNORECASE)

        # Handle LIMIT syntax
        # SQLite: LIMIT offset, count
        # PostgreSQL: LIMIT count OFFSET offset
        limit_match = re.search(r"LIMIT\s+(\d+)\s*,\s*(-?\d+)", query, re.IGNORECASE)
        if limit_match:
            offset, count = limit_match.groups()
            if count == "-1":
                count = "ALL"
            query = re.sub(
                r"LIMIT\s+\d+\s*,\s*-?\d+",
                "LIMIT %s OFFSET {offset}" % count,
                query,
                flags=re.IGNORECASE,
            )

        # Handle LIMIT -1 (SQLite for no limit)
        query = re.sub(r"LIMIT\s+-1\b", "LIMIT ALL", query, flags=re.IGNORECASE)

        # Handle SQLite type names
        query = query.replace("BLOB", "BYTEA")
        query = query.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")

        # Handle DESC as column name (PostgreSQL reserved word)
        # This is more targeted than the basic addon
        if re.search(r"\b(desc)\b(?!\s+(ASC|DESC|LIMIT))", query, re.IGNORECASE):
            query = re.sub(r"\b(desc)\b", "desc_", query, flags=re.IGNORECASE)

        return query

    def convert_jsonb_in_row(self, row):
        """Convert JSONB dicts to JSON strings in a row."""
        if row is None:
            return None

        import json  # pylint: disable=import-outside-toplevel

        converted = []
        for value in row:
            if isinstance(value, (dict, list)):
                # This is JSONB data - convert to string for Gramps
                converted.append(json.dumps(value))
            else:
                converted.append(value)
        return tuple(converted)

    def fetchone(self):
        """Fetch one row from the last query."""
        if hasattr(self, "_last_cursor") and self._last_cursor:
            row = self._last_cursor.fetchone()
            return self.convert_jsonb_in_row(row)
        return None

    def fetchall(self):
        """Fetch all rows from the last query."""
        if hasattr(self, "_last_cursor") and self._last_cursor:
            rows = self._last_cursor.fetchall()
            return [self.convert_jsonb_in_row(row) for row in rows]
        return []

    def fetchmany(self, size=ARRAYSIZE):
        """Fetch many rows from the last query."""
        if hasattr(self, "_last_cursor") and self._last_cursor:
            rows = self._last_cursor.fetchmany(size)
            return [self.convert_jsonb_in_row(row) for row in rows]
        return []

    def commit(self):
        """Commit the current transaction."""
        if self._pool:
            # Pool handles transactions per connection
            pass
        else:
            self._connection.commit()

    def _commit(self):
        """Internal commit method."""
        if self._connection:
            self._connection.commit()

    def rollback(self):
        """Rollback the current transaction."""
        if self._pool:
            # Pool handles transactions per connection
            pass
        else:
            self._connection.rollback()
        self._savepoints.clear()

    def begin(self):
        """
        Begin a transaction.

        PostgreSQL starts transactions automatically, but we
        track this for savepoint support.
        """
        # Create a savepoint for nested transaction support
        savepoint_name = "sp_%s" % len(self._savepoints)
        self.execute("SAVEPOINT %s" % savepoint_name)
        self._savepoints.append(savepoint_name)

    def begin_savepoint(self, name=None):
        """Create a named savepoint."""
        if not name:
            name = "sp_%s" % len(self._savepoints)
        self.execute("SAVEPOINT %s" % name)
        self._savepoints.append(name)
        return name

    def rollback_savepoint(self, name):
        """Rollback to a specific savepoint."""
        if name in self._savepoints:
            self.execute("ROLLBACK TO SAVEPOINT %s" % name)
            # Remove this and all later savepoints
            idx = self._savepoints.index(name)
            self._savepoints = self._savepoints[:idx]

    def close(self):
        """Close the database connection."""
        if self._pool:
            self._pool.close()
        elif self._connection:
            self._connection.close()

    def cursor(self):
        """Return a cursor object."""
        # Return the persistent cursor to maintain compatibility
        if not hasattr(self, "_persistent_cursor") or self._persistent_cursor is None or self._persistent_cursor.closed:
            if self._pool:
                # For pools, get a connection from the pool
                self._persistent_conn = self._pool.getconn()
                self._persistent_cursor = self._persistent_conn.cursor()
            else:
                self._persistent_cursor = self._connection.cursor()
        # Wrap the cursor to handle JSONB conversion
        return CursorWrapper(self._persistent_cursor, self)

    def table_exists(self, table_name):
        """Check if a table exists."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
            """,
                [table_name],
            )
            return cur.fetchone()[0]

    def column_exists(self, table_name, column_name):
        """Check if a column exists in a table."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = %s
                    AND column_name = %s
                )
            """,
                [table_name, column_name],
            )
            return cur.fetchone()[0]

    def index_exists(self, index_name):
        """Check if an index exists."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND indexname = %s
                )
            """,
                [index_name],
            )
            return cur.fetchone()[0]

    def drop_column(self, table_name, column_name):
        """
        Drop a column from a table.

        PostgreSQL has supported this for a long time,
        unlike SQLite which added it recently.
        """
        self.execute(
            sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(
                sql.Identifier(table_name), sql.Identifier(column_name)
            )
        )

    def get_server_info(self):
        """Get PostgreSQL server information."""
        info = {}
        with self._get_cursor() as cur:
            # Version
            cur.execute("SELECT version()")
            info["version"] = cur.fetchone()[0]

            # Current database
            cur.execute("SELECT current_database()")
            info["database"] = cur.fetchone()[0]

            # Current user
            cur.execute("SELECT current_user")
            info["user"] = cur.fetchone()[0]

            # Server encoding
            cur.execute("SHOW server_encoding")
            info["encoding"] = cur.fetchone()[0]

        return info

    def __getattr__(self, name):
        """
        Delegate any missing methods to the connection object.
        This ensures compatibility with any DBAPI methods we missed.
        """
        if self._connection:
            return getattr(self._connection, name)
        raise AttributeError(
            "'%s' object has no attribute '{name}'" % self.__class__.__name__
        )


# -------------------------------------------------------------------------
#
# CursorWrapper class
#
# -------------------------------------------------------------------------
class CursorWrapper:
    """
    Wrapper for psycopg3 cursor that converts JSONB to strings for Gramps.

    This wrapper ensures that JSONB data is automatically converted to
    JSON strings when fetched, maintaining compatibility with Gramps
    which expects string representations of JSON data.
    """

    def __init__(self, cursor, connection):
        """
        Initialize cursor wrapper.

        :param cursor: psycopg cursor to wrap
        :type cursor: psycopg.Cursor
        :param connection: Parent connection object
        :type connection: PostgreSQLConnection
        """
        self._cursor = cursor
        self._connection = connection

    def __getattr__(self, name):
        """
        Delegate all other attributes to the wrapped cursor.

        :param name: Attribute name
        :type name: str
        :returns: Attribute from wrapped cursor
        :rtype: Any
        """
        return getattr(self._cursor, name)

    def execute(self, query, params=None):
        """
        Execute query through the wrapped cursor.

        :param query: SQL query to execute
        :type query: str
        :param params: Optional query parameters
        :type params: tuple or list or None
        :returns: Result of cursor execute
        :rtype: Any
        """
        return self._cursor.execute(query, params)

    def fetchone(self):
        """
        Fetch one row, converting JSONB to strings.

        :returns: Single row with JSONB converted to strings
        :rtype: tuple or None
        """
        row = self._cursor.fetchone()
        return self._connection.convert_jsonb_in_row(row)

    def fetchall(self):
        """
        Fetch all rows, converting JSONB to strings.

        :returns: List of rows with JSONB converted to strings
        :rtype: list
        """
        rows = self._cursor.fetchall()
        return [self._connection.convert_jsonb_in_row(row) for row in rows]

    def fetchmany(self, size=None):
        """
        Fetch many rows, converting JSONB to strings.

        :param size: Number of rows to fetch
        :type size: int or None
        :returns: List of rows with JSONB converted to strings
        :rtype: list
        """
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        return [self._connection.convert_jsonb_in_row(row) for row in rows]

    def __enter__(self):
        """
        Context manager entry.

        :returns: Self for use in with statement
        :rtype: CursorWrapper
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit.

        Note: Does not close the cursor as it's persistent.

        :param exc_type: Exception type if an exception occurred
        :type exc_type: type or None
        :param exc_val: Exception value if an exception occurred
        :type exc_val: Exception or None
        :param exc_tb: Exception traceback if an exception occurred
        :type exc_tb: traceback or None
        """
        # Don't close the cursor - it's persistent
