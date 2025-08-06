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
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
PostgreSQL Enhanced Database Backend for Gramps

This backend provides advanced PostgreSQL features including:
- JSONB storage for powerful queries
- Full compatibility with existing Gramps data
- Migration from SQLite and standard PostgreSQL backends
- Advanced relationship queries using recursive CTEs
- Full-text search capabilities
- Optional extensions support (pgvector, Apache AGE, PostGIS)
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import logging
import os
import re
import pickle
import sys
from urllib.parse import urlparse, parse_qs

# -------------------------------------------------------------------------
#
# PostgreSQL modules
#
# -------------------------------------------------------------------------
try:
    import psycopg
    from psycopg import sql

    # from psycopg.types.json import Jsonb  # Currently unused
    # from psycopg.rows import dict_row  # Currently unused

    PSYCOPG_AVAILABLE = True
    PSYCOPG_VERSION = tuple(map(int, psycopg.__version__.split(".")[:2]))
except ImportError:
    PSYCOPG_AVAILABLE = False
    PSYCOPG_VERSION = (0, 0)

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

# from gramps.gen.db.dbconst import ARRAYSIZE  # Currently unused
from gramps.plugins.db.dbapi.dbapi import DBAPI
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.lib.serialize import JSONSerializer

# Get translation function for addon
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Import local modules - use relative imports for addon modules
from connection import PostgreSQLConnection
from schema import PostgreSQLSchema
from migration import MigrationManager
from queries import EnhancedQueries
from schema_columns import REQUIRED_COLUMNS

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------
MIN_PSYCOPG_VERSION = (3, 1)
MIN_POSTGRESQL_VERSION = 15

# Import debugging utilities
try:
    from debug_utils import DebugContext

    DEBUG_AVAILABLE = True
except ImportError:
    # Fallback if debug_utils not available
    DEBUG_AVAILABLE = False


# Create logger
LOG = logging.getLogger(".PostgreSQLEnhanced")

# Enable debug logging if environment variable is set
DEBUG_ENABLED = os.environ.get("GRAMPS_POSTGRESQL_DEBUG")
if DEBUG_ENABLED:
    LOG.setLevel(logging.DEBUG)
    # Also add a file handler for detailed debugging
    debug_handler = logging.FileHandler(
        os.path.expanduser("~/.gramps/postgresql_enhanced_debug.log")
    )
    debug_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
    )
    LOG.addHandler(debug_handler)
    LOG.debug("Debug logging enabled for PostgreSQL Enhanced")

    if DEBUG_AVAILABLE:
        LOG.debug("Advanced debugging features available")


# ------------------------------------------------------------
#
# PostgreSQLEnhanced
#
# ------------------------------------------------------------
class PostgreSQLEnhanced(DBAPI):
    """
    PostgreSQL Enhanced interface for Gramps.

    Provides advanced PostgreSQL features while maintaining
    full compatibility with the standard Gramps DBAPI interface.
    """

    def __init__(self):
        """Initialize the PostgreSQL Enhanced backend."""
        super().__init__()
        # Check psycopg3 availability
        if not PSYCOPG_AVAILABLE:
            raise ImportError(
                _(
                    "psycopg3 is required for PostgreSQL Enhanced support. "
                    "Install with: pip install 'psycopg[binary]'"
                )
            )

        # Check psycopg3 version
        if PSYCOPG_VERSION < MIN_PSYCOPG_VERSION:
            raise ImportError(
                _(
                    "psycopg3 version %(installed)s is too old. "
                    "Version %(required)s or newer is required."
                )
                % {
                    "installed": ".".join(map(str, PSYCOPG_VERSION)),
                    "required": ".".join(map(str, MIN_PSYCOPG_VERSION)),
                }
            )
        # Initialize components
        self.migration_manager = None
        self.enhanced_queries = None
        self._use_jsonb = True  # Default to using JSONB

        # Initialize attributes that are set in _initialize
        self.directory = None
        self.table_prefix = ""
        self.shared_db_mode = False
        self.path = None
        self.dbapi = None
        self.serializer = None
        self.readonly = False
        self._is_open = False
        self.undolog = None
        self.undodb = None

        # Initialize debug context if available
        self._debug_context = None
        if DEBUG_ENABLED and DEBUG_AVAILABLE:
            self._debug_context = DebugContext(LOG)
            LOG.debug("Debug context initialized")

    def get_summary(self):
        """
        Return a dictionary of information about this database backend.
        """
        summary = super().get_summary()

        # Basic info
        summary.update(
            {
                _("Database Backend"): "PostgreSQL Enhanced",
                _("Database module"): "psycopg %(val)s" % {"val": psycopg.__version__},
                _("Database module location"): psycopg.__file__,
                _("JSONB support"): _("Yes") if self._use_jsonb else _("No"),
            }
        )

        # Get PostgreSQL version and features if connected
        if hasattr(self, "dbapi") and self.dbapi:
            try:
                # PostgreSQL version
                self.dbapi.execute("SELECT version()")
                version_str = self.dbapi.fetchone()[0]
                match = re.search(r"PostgreSQL (\d+)\.(\d+)", version_str)
                if match:
                    pg_version = "%s.%s" % (match.group(1), match.group(2))
                    pg_major = int(match.group(1))
                else:
                    pg_version = "Unknown"
                    pg_major = 0

                summary[_("Database version")] = pg_version

                # Check if version meets requirements
                if pg_major < MIN_POSTGRESQL_VERSION:
                    summary[_("Version warning")] = _(
                        "PostgreSQL %(version)s is below recommended "
                        "version %(recommended)s"
                    ) % {"version": pg_major, "recommended": MIN_POSTGRESQL_VERSION}

                # Check for extensions
                self.dbapi.execute(
                    """
                    SELECT extname, extversion
                    FROM pg_extension
                    WHERE extname IN ('pgvector', 'age', 'postgis', 'hstore', 'pg_trgm')
                    ORDER BY extname
                """
                )
                extensions = ["%s {ver}" % name for name, ver in self.dbapi.fetchall()]
                if extensions:
                    summary[_("Extensions")] = ", ".join(extensions)

                # Database statistics
                self.dbapi.execute(
                    """
                    SELECT
                        pg_database_size(current_database()) as db_size,
                        (SELECT count(*) FROM person) as person_count,
                        (SELECT count(*) FROM family) as family_count,
                        (SELECT count(*) FROM event) as event_count
                """
                )
                stats = self.dbapi.fetchone()
                if stats and stats[0]:
                    # Format size nicely
                    size_mb = stats[0] / (1024 * 1024)
                    if size_mb < 1024:
                        size_str = "%(val)s MB" % {"val": round(size_mb, 1)}
                    else:
                        size_str = "%(val)s GB" % {"val": round(size_mb/1024, 1)}

                    summary[_("Database size")] = size_str
                    if stats[1] is not None:
                        summary[_("Statistics")] = _(
                            "%(persons)d persons, %(families)d families, "
                            "%(events)d events"
                        ) % {
                            "persons": stats[1] or 0,
                            "families": stats[2] or 0,
                            "events": stats[3] or 0,
                        }

            except (psycopg.Error, AttributeError, TypeError) as e:
                LOG.debug("Error getting database info: %s", e)

        return summary

    def _initialize(self, directory, username, password):
        """
        Initialize the PostgreSQL Enhanced database connection.

        The 'directory' parameter contains connection information:

        * postgresql://user:pass@host:port/dbname
        * host:port:dbname:schema
        * dbname (for local connection)

        Special features can be enabled via query parameters:

        * ?use_jsonb=false  (disable JSONB, use blob only)
        * ?pool_size=10     (connection pool size)

        :param directory: Path to database directory or connection string
        :type directory: str
        :param username: Database username (may be overridden by config)
        :type username: str
        :param password: Database password (may be overridden by config)
        :type password: str
        :raises DbConnectionError: If configuration cannot be loaded or connection fails
        """
        # Check if this is a Gramps file-based path
        # (like /home/user/.local/share/gramps/grampsdb/xxx)
        # or a test directory with connection_info.txt
        config_file = (
            os.path.join(directory, "connection_info.txt") if directory else None
        )
        if (
            directory
            and os.path.isabs(directory)
            and (
                "/grampsdb/" in directory
                or (config_file and os.path.exists(config_file))
            )
        ):
            # Extract tree name from path
            path_parts = directory.rstrip("/").split("/")
            tree_name = path_parts[-1] if path_parts else "gramps_default"

            # Store directory for config file lookup
            self.directory = directory

            # Load connection configuration
            config = self._load_connection_config(directory)

            if config["database_mode"] == "separate":
                # Separate database per tree
                db_name = tree_name
                self.table_prefix = ""
                self.shared_db_mode = False

                # Try to create database if it doesn't exist
                if config.get("user") and config.get("password"):
                    self._ensure_database_exists(db_name, config)
            else:
                # Shared database with table prefixes
                db_name = config.get("shared_database_name", "gramps_shared")
                # Sanitize tree name for use as table prefix
                # Ensure prefix starts with 'tree_' to avoid PostgreSQL identifier issues
                # (identifiers can't start with numbers)
                safe_tree_name = re.sub(r"[^a-zA-Z0-9_]", "_", tree_name)
                self.table_prefix = "tree_%s_" % safe_tree_name
                self.shared_db_mode = True
                LOG.info(
                    "Using shared database mode with prefix: %s", self.table_prefix
                )

            # Build connection string
            connection_string = (
                "postgresql://%s:%s@%s:%s/%s" % (
                    config['user'],
                    config['password'],
                    config['host'],
                    config['port'],
                    db_name
                )
            )

            LOG.info(
                "Tree name: '%s', Database: '%s', Mode: '%s'",
                tree_name,
                db_name,
                config["database_mode"],
            )
        else:
            # Direct connection string
            connection_string = directory
            self.table_prefix = ""
            self.shared_db_mode = False

        # Parse connection options
        self._parse_connection_options(connection_string)

        # Store path for compatibility
        self.path = directory

        # Create connection
        try:
            self.dbapi = PostgreSQLConnection(connection_string, username, password)

            # In monolithic mode, wrap the connection to add table prefixes
            if hasattr(self, "table_prefix") and self.table_prefix:
                self.dbapi = TablePrefixWrapper(self.dbapi, self.table_prefix)

        except Exception as e:
            raise DbConnectionError(str(e), connection_string) from e

        # Set serializer - DBAPI expects JSONSerializer
        # JSONSerializer has object_to_data method that DBAPI needs
        self.serializer = JSONSerializer()

        # Initialize schema with table prefix if in shared mode
        schema = PostgreSQLSchema(
            self.dbapi,
            use_jsonb=self._use_jsonb,
            table_prefix=getattr(self, "table_prefix", ""),
        )
        schema.check_and_init_schema()

        # Initialize migration manager
        self.migration_manager = MigrationManager(self.dbapi)

        # Initialize enhanced queries if JSONB is enabled
        if self._use_jsonb:
            self.enhanced_queries = EnhancedQueries(self.dbapi)

        # Log successful initialization
        LOG.info("PostgreSQL Enhanced initialized successfully")

        # Set database as writable
        self.readonly = False
        self._is_open = True

    def is_open(self):
        """
        Return True if the database is open.

        :returns: Whether the database connection is currently open
        :rtype: bool
        """
        return getattr(self, "_is_open", False)

    def open(self, _value=None):
        """
        Open database - compatibility method for Gramps.

        :param value: Unused parameter for compatibility
        :type value: object
        :returns: Always returns True as database is opened in load()
        :rtype: bool
        """
        # Database is already open from load()
        return True

    def load(
        self,
        directory,
        _callback=None,
        _mode=None,
        _force_schema_upgrade=False,
        _force_bsddb_upgrade=False,
        _force_bsddb_downgrade=False,
        _force_python_upgrade=False,
        user=None,
        password=None,
        username=None,
        *_args,
        **_kwargs,
    ):
        """
        Load database - Gramps compatibility method.

        Gramps calls this with various parameters, we only need directory, username, and password.

        :param directory: Path to database directory or connection string
        :type directory: str
        :param callback: Progress callback function (unused)
        :type callback: callable
        :param mode: Database mode (unused)
        :type mode: str
        :param force_schema_upgrade: Force schema upgrade (unused)
        :type force_schema_upgrade: bool
        :param force_bsddb_upgrade: Force BSDDB upgrade (unused)
        :type force_bsddb_upgrade: bool
        :param force_bsddb_downgrade: Force BSDDB downgrade (unused)
        :type force_bsddb_downgrade: bool
        :param force_python_upgrade: Force Python upgrade (unused)
        :type force_python_upgrade: bool
        :param user: Database username (alternative to username)
        :type user: str
        :param password: Database password
        :type password: str
        :param username: Database username (alternative to user)
        :type username: str
        :param args: Additional positional arguments (unused)
        :param kwargs: Additional keyword arguments (unused)
        :returns: Always returns True
        :rtype: bool
        """
        # Handle both 'user' and 'username' parameters
        actual_username = username or user or None
        actual_password = password or None

        # Call our initialize method
        self._initialize(directory, actual_username, actual_password)

        # Set up the undo manager without calling parent's full load
        # which tries to run upgrades on non-existent files
        from gramps.gen.db.generic import DbGenericUndo

        self.undolog = None
        self.undodb = DbGenericUndo(self, self.undolog)
        self.undodb.open()

        # Set proper version to avoid upgrade prompts
        self._set_metadata("version", "21")

    def _read_config_file(self, config_path):
        """
        Read a connection_info.txt file.

        :param config_path: Path to config file
        :type config_path: str
        :returns: Dictionary of configuration values
        :rtype: dict
        """
        config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
        return config

    def _load_connection_config(self, directory):
        """
        Load connection configuration from connection_info.txt.

        Priority order:
        1. Central plugin config (for monolithic mode)
        2. Per-tree config (for separate mode)
        3. Defaults

        :param directory: Path to the database directory containing config file
        :type directory: str
        :returns: Dictionary containing connection configuration
        :rtype: dict
        """
        # First, try central config location
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        central_config_path = os.path.join(plugin_dir, "connection_info.txt")

        # Check if central config exists and what mode it specifies
        if os.path.exists(central_config_path):
            central_config = self._read_config_file(central_config_path)
            if central_config.get("database_mode") == "monolithic":
                # In monolithic mode, ALWAYS use central config
                LOG.info("Using central config for monolithic mode from %s", central_config_path)
                return central_config

        # For separate mode or if no central config, check per-tree config
        config_path = os.path.join(directory, "connection_info.txt")
        config = {
            "host": "localhost",
            "port": "5432",
            "user": "gramps_user",
            "password": "gramps",
            "database_mode": "separate",
            "shared_database_name": "gramps_shared",
        }

        if os.path.exists(config_path):
            LOG.info("Loading connection config from: %s", config_path)
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
        else:
            LOG.warning(
                "No connection_info.txt found at %s, using defaults", config_path
            )
            # Try to create template for user
            template_path = os.path.join(
                os.path.dirname(__file__), "connection_info_template.txt"
            )
            if os.path.exists(template_path):
                try:
                    import shutil

                    shutil.copy(template_path, config_path)
                    LOG.info("Created connection_info.txt template at %s", config_path)
                    # Now read the template we just created
                    with open(config_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, value = line.split("=", 1)
                                config[key.strip()] = value.strip()
                    LOG.info("Loaded configuration from template")
                except (OSError, IOError, shutil.Error) as e:
                    LOG.debug("Could not create config template: %s", e)

        return config

    def _ensure_database_exists(self, db_name, config):
        """
        Create PostgreSQL database if it doesn't exist (for separate database mode).

        :param db_name: Name of the database to create
        :type db_name: str
        :param config: Database connection configuration
        :type config: dict
        :raises psycopg.Error: If database creation fails
        """
        try:
            # Connect to 'postgres' database to check/create the target database
            temp_conn_string = (
                "postgresql://%s:%s@%s:%s/postgres" % (
                    config['user'],
                    config['password'],
                    config['host'],
                    config['port']
                )
            )
            temp_conn = psycopg.connect(temp_conn_string)
            temp_conn.autocommit = True

            with temp_conn.cursor() as cur:
                # Check if database exists
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [db_name])
                if not cur.fetchone():
                    # Create database using template with extensions
                    LOG.info("Creating new PostgreSQL database: %s", db_name)
                    cur.execute(
                        sql.SQL("CREATE DATABASE {} TEMPLATE template_gramps").format(
                            sql.Identifier(db_name)
                        )
                    )
                    LOG.info("Successfully created database: %s", db_name)
                else:
                    LOG.info("Database already exists: %s", db_name)

            temp_conn.close()

        except psycopg.errors.InsufficientPrivilege:
            LOG.error(
                "User '%s' lacks CREATE DATABASE privilege. "
                "Please create database '%s' manually or grant CREATEDB privilege.",
                config["user"],
                db_name,
            )
            raise
        except Exception as e:
            LOG.error("Error checking/creating database: %s", e)
            raise

    def _parse_connection_options(self, connection_string):
        """
        Parse connection options from the connection string.

        :param connection_string: PostgreSQL connection string with optional parameters
        :type connection_string: str
        """
        if connection_string.startswith("postgresql://"):
            parsed = urlparse(connection_string)
            if parsed.query:
                params = parse_qs(parsed.query)
                # Check for JSONB disable flag
                if "use_jsonb" in params:
                    self._use_jsonb = params["use_jsonb"][0].lower() != "false"

    def _update_secondary_values(self, obj):
        """
        Update secondary columns from JSONB data.

        This extracts values from the JSONB column and updates the
        secondary columns that DBAPI expects for queries.

        :param obj: Gramps object to update secondary values for
        :type obj: gramps.gen.lib.PrimaryObject
        """
        table = obj.__class__.__name__.lower()
        # Use table prefix if in shared mode
        table_name = (
            f"{self.table_prefix}{table}" if hasattr(self, "table_prefix") else table
        )

        # Build UPDATE statement based on object type
        if table in REQUIRED_COLUMNS:
            sets = []

            for col_name, json_path in REQUIRED_COLUMNS[table].items():
                sets.append(f"{col_name} = ({json_path})")

            if sets:
                # Execute UPDATE using JSONB extraction
                query = f"""
                    UPDATE {table_name}
                    SET {', '.join(sets)}
                    WHERE handle = %s
                """
                self.dbapi.execute(query, [obj.handle])

        # Also handle derived fields that DBAPI adds
        if table == "person":
            # Extract given_name and surname if not already in REQUIRED_COLUMNS
            if "given_name" not in REQUIRED_COLUMNS.get("person", {}):
                self.dbapi.execute(
                    f"""
                    UPDATE {table_name}
                    SET given_name = COALESCE(
                        json_data->'primary_name'->>'first_name', ''),
                        surname = COALESCE(
                            json_data->'primary_name'->'surname_list'->0->>'surname', '')
                    WHERE handle = %s
                """,
                    [obj.handle],
                )
        elif table == "place":
            # Handle enclosed_by if not in REQUIRED_COLUMNS
            if "enclosed_by" not in REQUIRED_COLUMNS.get("place", {}):
                self.dbapi.execute(
                    f"""
                    UPDATE {table_name}
                    SET enclosed_by = json_data->>'enclosed_by'
                    WHERE handle = %s
                """,
                    [obj.handle],
                )

    def close(self, *_args, **_kwargs):
        """
        Close the database connection.

        :param args: Additional positional arguments (unused)
        :param kwargs: Additional keyword arguments (unused)
        """
        if hasattr(self, "dbapi") and self.dbapi:
            self.dbapi.close()
        self._is_open = False
        # Don't call super().close() as it expects file operations

    # Migration methods
    def has_migration_available(self):
        """
        Check if migration from another backend is available.

        :returns: True if migration is available, False otherwise
        :rtype: bool
        """
        if self.migration_manager:
            return self.migration_manager.detect_migration_needed() is not None
        return False

    def migrate_from_sqlite(self, sqlite_path, callback=None):
        """
        Migrate data from a SQLite database.

        :param sqlite_path: Path to SQLite database file
        :type sqlite_path: str
        :param callback: Progress callback function
        :type callback: callable
        :returns: True if migration successful
        :rtype: bool
        :raises RuntimeError: If migration manager not initialized
        """
        if not self.migration_manager:
            raise RuntimeError(_("Migration manager not initialized"))

        return self.migration_manager.migrate_from_sqlite(sqlite_path, callback)

    def migrate_from_postgresql(self, callback=None):
        """
        Upgrade from standard PostgreSQL backend to Enhanced.

        :param callback: Progress callback function
        :type callback: callable
        :returns: True if migration successful
        :rtype: bool
        :raises RuntimeError: If migration manager not initialized
        """
        if not self.migration_manager:
            raise RuntimeError(_("Migration manager not initialized"))

        return self.migration_manager.upgrade_to_enhanced(callback)

    # Enhanced query methods (only available with JSONB)
    def find_common_ancestors(self, handle1, handle2):
        """
        Find common ancestors between two people.

        :param handle1: Handle of the first person
        :type handle1: str
        :param handle2: Handle of the second person
        :type handle2: str
        :returns: List of common ancestor handles
        :rtype: list
        :raises RuntimeError: If enhanced queries not available
        """
        if not self.enhanced_queries:
            raise RuntimeError(_("Enhanced queries require JSONB support"))
        return self.enhanced_queries.find_common_ancestors(handle1, handle2)

    def find_relationship_path(self, handle1, handle2, max_depth=15):
        """
        Find the shortest relationship path between two people.

        :param handle1: Handle of the first person
        :type handle1: str
        :param handle2: Handle of the second person
        :type handle2: str
        :param max_depth: Maximum relationship depth to search
        :type max_depth: int
        :returns: List of handles representing the path
        :rtype: list
        :raises RuntimeError: If enhanced queries not available
        """
        if not self.enhanced_queries:
            raise RuntimeError(_("Enhanced queries require JSONB support"))
        return self.enhanced_queries.find_relationship_path(handle1, handle2, max_depth)

    def search_all_text(self, search_term):
        """
        Full-text search across all text fields.

        :param search_term: Text to search for
        :type search_term: str
        :returns: Dictionary of search results by object type
        :rtype: dict
        :raises RuntimeError: If enhanced queries not available
        """
        if not self.enhanced_queries:
            raise RuntimeError(_("Enhanced queries require JSONB support"))
        return self.enhanced_queries.search_all_text(search_term)

    def get_statistics(self):
        """
        Get detailed database statistics.

        :returns: Dictionary containing database statistics
        :rtype: dict
        """
        stats = {
            "backend": "PostgreSQL Enhanced",
            "jsonb_enabled": self._use_jsonb,
            "psycopg_version": psycopg.__version__,
        }

        if self.enhanced_queries:
            stats.update(self.enhanced_queries.get_statistics())

        return stats

    def commit_person(self, person, trans, change_time=None):
        """
        Override commit_person to handle NULL first names gracefully.

        The Gramps core genderstats module doesn't handle NULL first names,
        causing AttributeError when it tries to call split() on None.
        This is a common case in genealogy (unknown names, especially for women).

        We temporarily patch the genderstats function to handle None.

        :param person: Person object to commit
        :type person: Person
        :param trans: Transaction object
        :type trans: DbTxn
        :param change_time: Optional timestamp for the change
        :type change_time: int or None
        """
        LOG.debug("=== COMMIT PERSON START ===")
        LOG.debug("Handle: %s, Gramps ID: %s", person.handle, person.gramps_id)
        LOG.debug("Primary name: %s", person.primary_name)
        LOG.debug("Change time: %s", change_time)
        # Import the genderstats module
        from gramps.gen.lib import genderstats

        # Save the original function
        original_get_key_from_name = genderstats._get_key_from_name

        # Create a patched version that handles None
        def patched_get_key_from_name(name):
            """Perform patched get key from name operation."""
            if name is None:
                return ""
            return original_get_key_from_name(name)

        # Temporarily patch the function
        genderstats._get_key_from_name = patched_get_key_from_name
        try:
            # Call the parent method with the patched function and change_time
            super().commit_person(person, trans, change_time)
        finally:
            # Restore the original function
            genderstats._get_key_from_name = original_get_key_from_name

    def get_person_from_handle(self, handle):
        """
        Override to return None instead of raising exception for nonexistent handles.

        This matches the expected Gramps behavior.

        :param handle: Handle of the person to retrieve
        :type handle: str
        :returns: Person object or None if not found
        :rtype: Person or None
        """
        LOG.debug("Getting person with handle: %s", handle)
        try:
            return super().get_person_from_handle(handle)
        except Exception:
            return None

    def get_family_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the family to retrieve
        :type handle: str
        :returns: Family object or None if not found
        :rtype: Family or None
        """
        LOG.debug("Getting family with handle: %s", handle)
        try:
            return super().get_family_from_handle(handle)
        except Exception:
            return None

    def get_dbname(self):
        """
        Return a string identifier for the database.
        For PostgreSQL, return connection info instead of a filename.
        """
        if hasattr(self, 'table_prefix') and self.table_prefix:
            return "postgresql:%(val)s" % {"val": self.table_prefix.rstrip('_')}
        return "postgresql:database"

    def get_save_path(self):
        """
        Return a path-like string for the database.
        The verify tool uses this to create an MD5 hash for storing ignored issues.
        For PostgreSQL, we return a unique string based on the tree ID.
        """
        if hasattr(self, 'table_prefix') and self.table_prefix:
            # Return something that can be hashed consistently for this tree
            return "postgresql_%(val)s" % {"val": self.table_prefix.rstrip('_')}
        return "postgresql_database"

    def get_event_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the event to retrieve
        :type handle: str
        :returns: Event object or None if not found
        :rtype: Event or None
        """
        LOG.debug("Getting event with handle: %s", handle)
        try:
            return super().get_event_from_handle(handle)
        except Exception:
            return None

    def get_place_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the place to retrieve
        :type handle: str
        :returns: Place object or None if not found
        :rtype: Place or None
        """
        LOG.debug("Getting place with handle: %s", handle)
        try:
            return super().get_place_from_handle(handle)
        except Exception:
            return None

    def get_source_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the source to retrieve
        :type handle: str
        :returns: Source object or None if not found
        :rtype: Source or None
        """
        LOG.debug("Getting source with handle: %s", handle)
        try:
            return super().get_source_from_handle(handle)
        except Exception:
            return None

    def get_citation_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the citation to retrieve
        :type handle: str
        :returns: Citation object or None if not found
        :rtype: Citation or None
        """
        LOG.debug("Getting citation with handle: %s", handle)
        try:
            return super().get_citation_from_handle(handle)
        except Exception:
            return None

    def get_repository_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the repository to retrieve
        :type handle: str
        :returns: Repository object or None if not found
        :rtype: Repository or None
        """
        LOG.debug("Getting repository with handle: %s", handle)
        try:
            return super().get_repository_from_handle(handle)
        except Exception:
            return None

    def get_media_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the media to retrieve
        :type handle: str
        :returns: Media object or None if not found
        :rtype: Media or None
        """
        LOG.debug("Getting media with handle: %s", handle)
        try:
            return super().get_media_from_handle(handle)
        except Exception:
            return None

    def get_note_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the note to retrieve
        :type handle: str
        :returns: Note object or None if not found
        :rtype: Note or None
        """
        LOG.debug("Getting note with handle: %s", handle)
        try:
            return super().get_note_from_handle(handle)
        except Exception:
            return None

    def get_tag_from_handle(self, handle):
        """
        Override to return None for nonexistent handles.

        :param handle: Handle of the tag to retrieve
        :type handle: str
        :returns: Tag object or None if not found
        :rtype: Tag or None
        """
        LOG.debug("Getting tag with handle: %s", handle)
        try:
            return super().get_tag_from_handle(handle)
        except Exception:
            return None

    def _order_by_person_key(self, person):
        """
        Override to handle NULL names properly.

        The parent class doesn't handle None values in names,
        causing concatenation errors in concurrent updates.
        """
        if person.primary_name and person.primary_name.surname_list:
            surname = person.primary_name.surname_list[0]
            surname_text = surname.surname if surname.surname else ""
            first_name = person.primary_name.first_name if person.primary_name.first_name else ""
            return surname_text + " " + first_name
        return ""

    def _get_metadata(self, key, default="_"):
        """
        Override to handle table prefixes in monolithic mode.

        :param key: Metadata key to retrieve
        :type key: str
        :param default: Default value if key not found
        :type default: object
        :returns: Metadata value or default
        :rtype: object
        """
        if hasattr(self, "table_prefix") and self.table_prefix:
            # In monolithic mode, use prefixed table name
            self.dbapi.execute(
                f"SELECT 1 FROM {self.table_prefix}metadata WHERE setting = %s", [key]
            )
        else:
            # In separate mode, use standard query
            self.dbapi.execute("SELECT 1 FROM metadata WHERE setting = ?", [key])
        row = self.dbapi.fetchone()
        if row:
            prefix = (
                self.table_prefix
                if hasattr(self, "table_prefix") and self.table_prefix
                else ""
            )
            self.dbapi.execute(
                f"SELECT value FROM {prefix}metadata WHERE setting = %s",
                [key],
            )
            row = self.dbapi.fetchone()
            if row and row[0]:
                try:
                    return pickle.loads(row[0])
                except (pickle.PickleError, TypeError, ValueError):
                    return row[0]
        if default == "_":
            return []
        return default

    def _set_metadata(self, key, value, use_txn=True):
        """
        Override to handle table prefixes in monolithic mode.
        Uses INSERT ... ON CONFLICT to avoid concurrent update errors.

        :param key: Metadata key to set
        :type key: str
        :param value: Value to store
        :type value: object
        :param use_txn: Whether to use transaction
        :type use_txn: bool
        """
        import psycopg

        # Retry logic for concurrent access
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if use_txn:
                    self._txn_begin()

                prefix = (
                    self.table_prefix
                    if hasattr(self, "table_prefix") and self.table_prefix
                    else ""
                )
                table_name = "%smetadata" % prefix

                # Use UPSERT (INSERT ... ON CONFLICT) to avoid race conditions
                # This is atomic and handles concurrent access properly
                self.dbapi.execute(
                    f"""
                    INSERT INTO {table_name} (setting, value)
                    VALUES (%s, %s)
                    ON CONFLICT (setting)
                    DO UPDATE SET value = EXCLUDED.value
                    """,
                    [key, pickle.dumps(value)]
                )

                if use_txn:
                    self._txn_commit()

                # Success, exit retry loop
                break

            except psycopg.errors.SerializationFailure as e:
                # Rollback and retry for serialization failures
                if use_txn:
                    try:
                        self._txn_abort()
                    except Exception:
                        pass

                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.01 * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    raise


# ------------------------------------------------------------
#
# TablePrefixWrapper
#
# ------------------------------------------------------------
class TablePrefixWrapper:
    """
    Wraps a database connection to automatically add table prefixes in queries.

    This allows the standard DBAPI to work with prefixed tables in monolithic mode.

    :param connection: Database connection to wrap
    :type connection: psycopg.Connection
    :param table_prefix: Prefix to add to table names
    :type table_prefix: str
    """

    # Tables that should have prefixes
    PREFIXED_TABLES = {
        "person",
        "family",
        "event",
        "place",
        "source",
        "citation",
        "repository",
        "media",
        "note",
        "tag",
        "metadata",
        "reference",
        "gender_stats",
    }

    # Tables that are shared (no prefix)
    SHARED_TABLES = {"name_group", "surname"}

    def __init__(self, connection, table_prefix):
        """Initialize wrapper with connection and prefix."""
        self._connection = connection
        self._prefix = table_prefix

    def execute(self, query, params=None):
        """Execute query with table prefixes added."""
        # Add prefixes to table names in the query
        modified_query = self._add_table_prefixes(query)

        # Log for debugging
        if query != modified_query:
            LOG.debug("Query modified: %s -> %s", query, modified_query)

        return self._connection.execute(modified_query, params)

    def cursor(self):
        """Return a wrapped cursor that prefixes queries."""
        # NO FALLBACK: Must wrap cursor to catch ALL queries
        return CursorPrefixWrapper(self._connection.cursor(), self._prefix)

    def _add_table_prefixes(self, query):
        """Add table prefixes to a query."""
        # NO FALLBACK: We must handle ALL query patterns comprehensively

        modified = query

        for table in self.PREFIXED_TABLES:
            # Match table name as whole word (not part of another word)
            # Handle ALL SQL patterns that DBAPI might generate
            patterns = [
                # SELECT patterns - MUST handle queries without keywords before FROM
                (
                    r"\bSELECT\s+(.+?)\s+FROM\s+(%s)\b" % table,
                    lambda m: f"SELECT {m.group(1)} FROM {self._prefix}{m.group(2)}",
                ),
                # Basic patterns with keywords before table name
                (r"\b(FROM)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(JOIN)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(INTO)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(UPDATE)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(DELETE\s+FROM)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(INSERT\s+INTO)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(ALTER\s+TABLE)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (
                    r"\b(DROP\s+TABLE\s+IF\s+EXISTS)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (
                    r"\b(CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (r"\b(CREATE\s+TABLE)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (
                    r"\b(CREATE\s+INDEX\s+\S+\s+ON)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (
                    r"\b(CREATE\s+UNIQUE\s+INDEX\s+\S+\s+ON)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (
                    r"\b(DROP\s+INDEX\s+IF\s+EXISTS\s+\S+\s+ON)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (r"\b(REFERENCES)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                # EXISTS patterns
                (r"\b(EXISTS)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (
                    r"\bEXISTS\s*\(\s*SELECT\s+.+?\s+FROM\s+(%s)\b" % table,
                    lambda m: m.group(0).replace(
                        f"FROM {m.group(1)}", f"FROM {self._prefix}{m.group(1)}"
                    ),
                ),
                # Table name in WHERE clauses with table.column syntax
                (r"\b(%s)\.(\w+)" % table, r"%(val)s\1.\2" % {"val": self._prefix}),
            ]

            for pattern, replacement in patterns:
                if callable(replacement):
                    # Use callable for complex replacements
                    modified = re.sub(
                        pattern, replacement, modified, flags=re.IGNORECASE | re.DOTALL
                    )
                else:
                    modified = re.sub(
                        pattern, replacement, modified, flags=re.IGNORECASE
                    )

        return modified

    def __getattr__(self, name):
        """Forward all other attributes to the wrapped connection."""
        return getattr(self._connection, name)


# ------------------------------------------------------------
#
# CursorPrefixWrapper
#
# ------------------------------------------------------------
class CursorPrefixWrapper:
    """
    Wraps a database cursor to automatically add table prefixes in queries.

    :param cursor: Database cursor to wrap
    :type cursor: psycopg.Cursor
    :param table_prefix: Prefix to add to table names
    :type table_prefix: str
    """

    def __init__(self, cursor, table_prefix):
        """
        Initialize wrapper with cursor and prefix.

        :param cursor: Database cursor to wrap
        :type cursor: psycopg.Cursor
        :param table_prefix: Prefix to add to table names
        :type table_prefix: str
        """
        self._cursor = cursor
        self._prefix = table_prefix

    def execute(self, query, params=None):
        """
        Execute query with table prefixes added.

        :param query: SQL query string
        :type query: str
        :param params: Query parameters
        :type params: list or tuple
        :returns: Query result
        :rtype: psycopg.Cursor
        """
        # Reuse the same prefix logic from TablePrefixWrapper
        modified_query = self._add_table_prefixes(query)

        # Log for debugging
        if query != modified_query:
            LOG.debug("Cursor query modified: %s -> %s", query, modified_query)

        return self._cursor.execute(modified_query, params)

    def _add_table_prefixes(self, query):
        """
        Add table prefixes to a query.

        :param query: SQL query string
        :type query: str
        :returns: Query with table names prefixed
        :rtype: str
        """
        # NO FALLBACK: We must handle ALL query patterns comprehensively

        modified = query

        # Use same tables as TablePrefixWrapper
        prefixed_tables = TablePrefixWrapper.PREFIXED_TABLES

        for table in prefixed_tables:
            # Match table name as whole word (not part of another word)
            # Handle ALL SQL patterns that DBAPI might generate
            patterns = [
                # SELECT patterns - MUST handle queries without keywords before FROM
                (
                    r"\bSELECT\s+(.+?)\s+FROM\s+(%s)\b" % table,
                    lambda m: f"SELECT {m.group(1)} FROM {self._prefix}{m.group(2)}",
                ),
                # Basic patterns with keywords before table name
                (r"\b(FROM)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(JOIN)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(INTO)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(UPDATE)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(DELETE\s+FROM)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(INSERT\s+INTO)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (r"\b(ALTER\s+TABLE)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (
                    r"\b(DROP\s+TABLE\s+IF\s+EXISTS)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (
                    r"\b(CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (r"\b(CREATE\s+TABLE)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (
                    r"\b(CREATE\s+INDEX\s+\S+\s+ON)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (
                    r"\b(CREATE\s+UNIQUE\s+INDEX\s+\S+\s+ON)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (
                    r"\b(DROP\s+INDEX\s+IF\s+EXISTS\s+\S+\s+ON)\s+(%s)\b" % table,
                    r"\1 %(val)s\2" % {"val": self._prefix},
                ),
                (r"\b(REFERENCES)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                # EXISTS patterns
                (r"\b(EXISTS)\s+(%s)\b" % table, r"\1 %(val)s\2" % {"val": self._prefix}),
                (
                    r"\bEXISTS\s*\(\s*SELECT\s+.+?\s+FROM\s+(%s)\b" % table,
                    lambda m: m.group(0).replace(
                        f"FROM {m.group(1)}", f"FROM {self._prefix}{m.group(1)}"
                    ),
                ),
                # Table name in WHERE clauses with table.column syntax
                (r"\b(%s)\.(\w+)" % table, r"%(val)s\1.\2" % {"val": self._prefix}),
            ]

            for pattern, replacement in patterns:
                if callable(replacement):
                    # Use callable for complex replacements
                    modified = re.sub(
                        pattern, replacement, modified, flags=re.IGNORECASE | re.DOTALL
                    )
                else:
                    modified = re.sub(
                        pattern, replacement, modified, flags=re.IGNORECASE
                    )

        return modified

    def __enter__(self):
        """
        Support context manager protocol.

        :returns: Self for use in with statement
        :rtype: CursorPrefixWrapper
        """
        self._cursor.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Support context manager protocol.

        :param exc_type: Exception type if any
        :type exc_type: type
        :param exc_val: Exception value if any
        :type exc_val: Exception
        :param exc_tb: Exception traceback if any
        :type exc_tb: traceback
        """
        return self._cursor.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        """
        Forward all other attributes to the wrapped cursor.

        :param name: Attribute name
        :type name: str
        :returns: Attribute value from wrapped cursor
        :rtype: object
        """
        return getattr(self._cursor, name)
