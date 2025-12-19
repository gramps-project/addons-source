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
# from search_capabilities import SearchCapabilities, SearchAPI  # TODO: Add when needed
from concurrency import PostgreSQLConcurrency

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
# PostgreSQLEnhancedBase - Shared implementation
#
# ------------------------------------------------------------
class PostgreSQLEnhancedBase(DBAPI):
    """
    PostgreSQL Enhanced base implementation for Gramps.

    Provides advanced PostgreSQL features while maintaining
    full compatibility with the standard Gramps DBAPI interface.

    This is the base class - use PostgreSQLEnhancedMonolithic or
    PostgreSQLEnhancedSeparate subclasses.
    """

    def __init__(self, force_mode=None):
        """Initialize the PostgreSQL Enhanced backend."""
        super().__init__()
        # Store forced mode (set by subclass)
        self.force_mode = force_mode
        # Initialize logger
        self.log = logging.getLogger(__name__)
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
        self.search_capabilities = None
        self.search_api = None
        self.concurrency = None
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

        # Detect Gramps Web environment
        self.grampsweb_active = self._detect_grampsweb_environment()
        if self.grampsweb_active:
            LOG.info("PostgreSQL Enhanced: Gramps Web environment detected")

    def requires_login(self):
        """
        Returns True for backends that require a login dialog, else False.

        PostgreSQL requires username/password authentication.
        Gramps will prompt for credentials before calling load().
        """
        return True

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
        Initialize PostgreSQL Enhanced using Gramps standard ConfigManager.

        :param directory: Path to database directory
        :type directory: str
        :param username: Database username (overrides config)
        :type username: str
        :param password: Database password (overrides config)
        :type password: str
        :raises DbConnectionError: If configuration cannot be loaded or connection fails
        """
        from gramps.gen.utils.configmanager import ConfigManager
        from gramps.gen.config import config as global_config

        # Extract tree ID from directory
        tree_id = os.path.basename(directory.rstrip('/'))
        self.directory = directory
        self.tree_id = tree_id
        self.path = directory

        LOG.info("Initializing tree '%s' with force_mode='%s'", tree_id, self.force_mode)

        # Check for GrampsWeb environment variable mode
        explicit_env_mode = os.environ.get('POSTGRESQL_ENHANCED_MODE') == 'monolithic'

        if explicit_env_mode:
            # GrampsWeb mode - use environment variables
            config_dict = self._build_config_from_env()
            host = config_dict['host']
            port = config_dict['port']
            db_user = config_dict['user']
            actual_password = config_dict['password']
            db_name = config_dict['database']

            self.table_prefix = f"tree_{tree_id}_"
            self.shared_db_mode = True

            LOG.info("Environment variable mode - database=%s, prefix=%s", db_name, self.table_prefix)

        else:
            # Standard Gramps mode - use ConfigManager
            config_file = os.path.join(directory, 'settings.ini')
            config_mgr = ConfigManager(config_file)

            # Register configuration keys
            config_mgr.register('database.host', 'localhost')
            config_mgr.register('database.port', 5432)
            config_mgr.register('database.user', 'gramps_user')
            config_mgr.register('database.shared-database', 'gramps_shared')
            config_mgr.register('database.pool-size', 5)

            # Load or create configuration
            if not os.path.exists(config_file):
                LOG.info("Creating settings.ini for tree %s", tree_id)

                # Check for connection_info.txt migration
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                old_config_file = os.path.join(plugin_dir, 'connection_info.txt')

                if os.path.exists(old_config_file):
                    # Migrate from connection_info.txt
                    LOG.info("Migrating from connection_info.txt")
                    old_config = self._read_config_file(old_config_file)

                    config_mgr.set('database.host', old_config.get('host', 'localhost'))
                    config_mgr.set('database.port', int(old_config.get('port', '5432')))
                    config_mgr.set('database.user', old_config.get('user', 'gramps_user'))
                    config_mgr.set('database.shared-database',
                                  old_config.get('shared_database_name', 'gramps_shared'))
                    config_mgr.set('database.pool-size', int(old_config.get('pool_size', '5')))
                else:
                    # Use defaults from global Gramps config
                    LOG.info("Using defaults from global Gramps preferences")
                    config_mgr.set('database.host',
                                  global_config.get('database.host') or 'localhost')
                    port_str = global_config.get('database.port') or '5432'
                    config_mgr.set('database.port',
                                  int(port_str) if port_str else 5432)
                    config_mgr.set('database.user', 'gramps_user')
                    config_mgr.set('database.shared-database', 'gramps_shared')
                    config_mgr.set('database.pool-size', 5)

                config_mgr.save()
                LOG.info("Created settings.ini at %s", config_file)

            # Load configuration
            config_mgr.load()

            # Get connection parameters from settings.ini
            host = config_mgr.get('database.host')
            port = config_mgr.get('database.port')
            db_user = config_mgr.get('database.user')

            # Determine database name based on force_mode
            if self.force_mode == 'separate':
                db_name = tree_id
                self.table_prefix = ""
                self.shared_db_mode = False
                LOG.info("Separate mode: database=%s", db_name)

                # Try to create database if it doesn't exist
                config_dict = {
                    'host': host,
                    'port': port,
                    'user': db_user,
                    'password': password or ''
                }
                self._ensure_database_exists(db_name, config_dict)
            else:
                db_name = config_mgr.get('database.shared-database') or 'gramps_shared'
                safe_tree_id = re.sub(r"[^a-zA-Z0-9_]", "_", tree_id)
                self.table_prefix = f"tree_{safe_tree_id}_"
                self.shared_db_mode = True
                LOG.info("Monolithic mode: database=%s, prefix=%s", db_name, self.table_prefix)

            # Username/password from parameters override config
            # (password never stored in settings.ini for security)
            actual_password = password or ''

        # Override username if provided as parameter
        actual_user = username or db_user or 'gramps_user'

        # Build connection string
        connection_string = f"postgresql://{actual_user}:{actual_password}@{host}:{port}/{db_name}"

        # Parse connection options
        self._parse_connection_options(connection_string)

        # Create connection
        try:
            self.dbapi = PostgreSQLConnection(connection_string, actual_user, actual_password)

            # In monolithic mode, wrap the connection to add table prefixes
            if self.table_prefix:
                self.dbapi = TablePrefixWrapper(self.dbapi, self.table_prefix)

        except Exception as e:
            raise DbConnectionError(str(e), connection_string) from e

        # Initialize components - wrapped in try/finally to ensure connection cleanup
        try:
            # Set serializer
            self.serializer = JSONSerializer()

            # Initialize schema
            schema = PostgreSQLSchema(
                self.dbapi,
                use_jsonb=self._use_jsonb,
                table_prefix=self.table_prefix,
            )
            schema.check_and_init_schema()

            # Initialize migration manager
            self.migration_manager = MigrationManager(self.dbapi)

            # Initialize enhanced queries if JSONB is enabled
            if self._use_jsonb:
                self.enhanced_queries = EnhancedQueries(self.dbapi)

            # Initialize concurrency features (graceful degradation if fails)
            try:
                self.concurrency = PostgreSQLConcurrency(self.dbapi)
                LOG.debug("Concurrency features initialized")
            except Exception as e:
                LOG.warning("Could not initialize concurrency features: %s", e)
                self.concurrency = None

            # Log success
            LOG.info("PostgreSQL Enhanced initialized successfully")

            # Set database as writable
            self.readonly = False
            self._is_open = True

        except Exception as e:
            # Clean up connection on initialization failure
            LOG.error("Initialization failed, closing connection: %s", e)
            if hasattr(self, 'dbapi') and self.dbapi:
                try:
                    self.dbapi.close()
                except Exception:
                    pass  # Ignore errors during cleanup
            raise

    def json_extract_expression(self, json_column, json_path):
        """
        Generate PostgreSQL-specific JSON extraction expression.

        Converts JSONPath notation to PostgreSQL JSONB operators.

        :param json_column: Name of the JSON column
        :type json_column: str
        :param json_path: JSONPath expression (e.g., '$.type' or '$.date.sort')
        :type json_path: str
        :returns: PostgreSQL JSONB extraction expression
        :rtype: str
        """
        path = json_path.strip("$").strip(".")

        if not path:
            return json_column

        # Parse path into components
        parts = []
        current = ""
        in_bracket = False

        for char in path:
            if char == "[":
                if current:
                    parts.append(("key", current))
                    current = ""
                in_bracket = True
            elif char == "]":
                parts.append(("index", current))
                current = ""
                in_bracket = False
            elif char == "." and not in_bracket:
                if current:
                    parts.append(("key", current))
                    current = ""
            else:
                current += char

        if current:
            parts.append(("key", current))

        # Build PostgreSQL JSONB expression
        expr = json_column
        for i, (ptype, value) in enumerate(parts):
            is_last = i == len(parts) - 1

            if ptype == "key":
                if is_last:
                    expr = "(%s->>%s)" % (expr, repr(value))
                else:
                    expr = "(%s->%s)" % (expr, repr(value))
            elif ptype == "index":
                expr = "(%s->%s)" % (expr, value)

        return expr

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
        callback=None,
        mode=None,
        force_schema_upgrade=False,
        force_bsddb_upgrade=False,
        force_bsddb_downgrade=False,
        force_python_upgrade=False,
        update=True,
        user=None,
        password=None,
        username=None,
        *args,
        **kwargs,
    ):
        """
        Load database - Gramps compatibility method v1.4.

        Enhanced for full Gramps Web compatibility while maintaining PostgreSQL-native design.

        :param directory: Path to database directory or connection string
        :type directory: str
        :param callback: Progress callback function (unused)
        :type callback: callable
        :param mode: Database mode (DBMODE_R for read-only, DBMODE_W for read-write)
        :type mode: str
        :param force_schema_upgrade: Force schema upgrade (ignored - PostgreSQL handles this)
        :type force_schema_upgrade: bool
        :param force_bsddb_upgrade: Force BSDDB upgrade (ignored)
        :type force_bsddb_upgrade: bool
        :param force_bsddb_downgrade: Force BSDDB downgrade (ignored)
        :type force_bsddb_downgrade: bool
        :param force_python_upgrade: Force Python upgrade (ignored)
        :type force_python_upgrade: bool
        :param update: Whether to update files (kept for compatibility)
        :type update: bool
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

        .. versionchanged:: 1.4
            Added full DBAPI compatibility attributes for Gramps Web.
        """
        # Handle both 'user' and 'username' parameters
        actual_username = username or user or None
        actual_password = password or None

        # Store original directory for later use
        self._original_directory = directory

        # Call our initialize method
        self._initialize(directory, actual_username, actual_password)

        # ===== BLOCK 1: TRIVIAL FLAGS AND ATTRIBUTES =====
        # CRITICAL: This flag is required for Gramps Web to work
        self.db_is_open = True

        # Support read-only mode
        from gramps.gen.db.dbconst import DBMODE_R
        self.readonly = mode == DBMODE_R if mode else False

        # Initialize change tracking counter
        self.has_changed = 0

        # Set minimal directory attributes for compatibility
        self._directory = directory
        self.path = directory  # Some Gramps code expects this

        # Set serializer (always JSON for PostgreSQL Enhanced)
        self.set_serializer("json")

        # ===== END BLOCK 1 =====

        # ===== BLOCK 2: BOOKMARKS AND BASIC METADATA =====
        # Initialize all bookmark collections (required for Gramps Web)
        self._initialize_bookmarks()

        # Load name formats and researcher info
        from gramps.gen.lib import Researcher
        self.name_formats = self._get_metadata("name_formats", [])
        self.owner = self._get_metadata("researcher", default=Researcher())

        # Initialize all custom type attributes
        self._initialize_custom_types()

        # Load gender statistics
        from gramps.gen.lib import GenderStats
        gstats = self._get_metadata("gender_stats", {})
        self.genderStats = GenderStats(gstats)

        # ===== END BLOCK 2 =====

        # ===== BLOCK 3: MODE-AWARE METADATA (ID COUNTERS & SURNAME LIST) =====
        # Initialize ID counters with mode awareness (critical for monolithic mode)
        self._initialize_id_counters()

        # Load surname list with mode awareness (must be isolated per tree)
        self.surname_list = self._get_mode_aware_surname_list()

        # ===== END BLOCK 3 =====

        # ===== BLOCK 4: RECENT FILES TRACKING =====
        # Update recent files to fix "Last Accessed: NEVER" issue
        self._update_recent_files()

        # ===== END BLOCK 4 =====

        # Set up the undo manager without calling parent's full load
        # which tries to run upgrades on non-existent files

        # Detect if we're running under GrampsWeb
        grampsweb_mode = self._detect_grampsweb_mode()

        if grampsweb_mode:
            # Use our PostgreSQL undo that has get_transactions
            try:
                from .undo_postgresql import DbUndoPostgreSQL
                self.undodb = DbUndoPostgreSQL(self, self.dbapi)
                self.log.info("Using PostgreSQL-native undo system with transaction history")
            except ImportError:
                self.log.warning("Failed to import DbUndoPostgreSQL, falling back to generic")
                from gramps.gen.db.generic import DbGenericUndo
                self.undolog = None
                self.undodb = DbGenericUndo(self, self.undolog)
        else:
            # Regular Gramps desktop - use standard undo for now
            from gramps.gen.db.generic import DbGenericUndo
            self.undolog = None
            self.undodb = DbGenericUndo(self, self.undolog)

        self.undodb.open()

        # Set proper version to avoid upgrade prompts
        self._set_metadata("version", "21")

        return True

    def _initialize_bookmarks(self):
        """
        Initialize all bookmark collections.

        .. versionadded:: 1.4
            Required for Gramps Web compatibility.
        """
        # Initialize bookmark attributes if they don't exist
        if not hasattr(self, 'bookmarks'):
            from gramps.gen.utils.bookmarks import Bookmarks
            self.bookmarks = Bookmarks()
            self.family_bookmarks = Bookmarks()
            self.event_bookmarks = Bookmarks()
            self.source_bookmarks = Bookmarks()
            self.citation_bookmarks = Bookmarks()
            self.repo_bookmarks = Bookmarks()
            self.media_bookmarks = Bookmarks()
            self.place_bookmarks = Bookmarks()
            self.note_bookmarks = Bookmarks()

        # Load bookmark data from metadata
        self.bookmarks.load(self._get_metadata("bookmarks", []))
        self.family_bookmarks.load(self._get_metadata("family_bookmarks", []))
        self.event_bookmarks.load(self._get_metadata("event_bookmarks", []))
        self.source_bookmarks.load(self._get_metadata("source_bookmarks", []))
        self.citation_bookmarks.load(self._get_metadata("citation_bookmarks", []))
        self.repo_bookmarks.load(self._get_metadata("repo_bookmarks", []))
        self.media_bookmarks.load(self._get_metadata("media_bookmarks", []))
        self.place_bookmarks.load(self._get_metadata("place_bookmarks", []))
        self.note_bookmarks.load(self._get_metadata("note_bookmarks", []))

    def _initialize_custom_types(self):
        """
        Initialize all custom type attributes.

        These populate UI dropdowns in Gramps.

        .. versionadded:: 1.4
            Required for Gramps Web UI functionality.
        """
        # Initialize all custom type attributes with empty sets as defaults
        self.event_names = self._get_metadata("event_names", set())
        self.family_attributes = self._get_metadata("fattr_names", set())
        self.individual_attributes = self._get_metadata("pattr_names", set())
        self.source_attributes = self._get_metadata("sattr_names", set())
        self.marker_names = self._get_metadata("marker_names", set())
        self.child_ref_types = self._get_metadata("child_refs", set())
        self.family_rel_types = self._get_metadata("family_rels", set())
        self.event_role_names = self._get_metadata("event_roles", set())
        self.name_types = self._get_metadata("name_types", set())
        self.origin_types = self._get_metadata("origin_types", set())
        self.repository_types = self._get_metadata("repo_types", set())
        self.note_types = self._get_metadata("note_types", set())
        self.source_media_types = self._get_metadata("sm_types", set())
        self.url_types = self._get_metadata("url_types", set())
        self.media_attributes = self._get_metadata("mattr_names", set())
        self.event_attributes = self._get_metadata("eattr_names", set())
        self.place_types = self._get_metadata("place_types", set())

    def _initialize_id_counters(self):
        """
        Initialize ID generation counters with mode awareness.

        In monolithic mode, each tree must have its own counters to prevent
        ID collisions between trees.

        .. versionadded:: 1.4
            Mode-aware ID counter initialization.
        """
        if hasattr(self, 'table_prefix') and self.table_prefix:
            # Monolithic mode: prefix counters with tree ID
            prefix = self.table_prefix.rstrip('_')
            self.cmap_index = self._get_metadata(f"{prefix}_cmap_index", 0)
            self.smap_index = self._get_metadata(f"{prefix}_smap_index", 0)
            self.emap_index = self._get_metadata(f"{prefix}_emap_index", 0)
            self.pmap_index = self._get_metadata(f"{prefix}_pmap_index", 0)
            self.fmap_index = self._get_metadata(f"{prefix}_fmap_index", 0)
            self.lmap_index = self._get_metadata(f"{prefix}_lmap_index", 0)
            self.omap_index = self._get_metadata(f"{prefix}_omap_index", 0)
            self.rmap_index = self._get_metadata(f"{prefix}_rmap_index", 0)
            self.nmap_index = self._get_metadata(f"{prefix}_nmap_index", 0)
        else:
            # Separate mode: standard counters
            self.cmap_index = self._get_metadata("cmap_index", 0)
            self.smap_index = self._get_metadata("smap_index", 0)
            self.emap_index = self._get_metadata("emap_index", 0)
            self.pmap_index = self._get_metadata("pmap_index", 0)
            self.fmap_index = self._get_metadata("fmap_index", 0)
            self.lmap_index = self._get_metadata("lmap_index", 0)
            self.omap_index = self._get_metadata("omap_index", 0)
            self.rmap_index = self._get_metadata("rmap_index", 0)
            self.nmap_index = self._get_metadata("nmap_index", 0)

    def _get_mode_aware_surname_list(self):
        """
        Get surname list with mode awareness.

        In monolithic mode, returns surnames only from the current tree's table.
        In separate mode, returns surnames from the single person table.

        .. versionadded:: 1.4
            Mode-aware surname list retrieval.
        """
        try:
            if hasattr(self, 'table_prefix') and self.table_prefix:
                # Monolithic mode: query only this tree's person table
                table_name = f"{self.table_prefix}person"
            else:
                # Separate mode: standard person table
                table_name = "person"

            query = f"""
                SELECT DISTINCT
                    json_data->'primary_name'->>'surname' as surname
                FROM {table_name}
                WHERE json_data IS NOT NULL
                AND json_data->'primary_name'->>'surname' IS NOT NULL
                AND json_data->'primary_name'->>'surname' != ''
                ORDER BY surname
            """

            result = self.dbapi.execute(query)
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            LOG.warning(f"Failed to load surname list: {e}")
            return []

    def _detect_grampsweb_mode(self):
        """
        Detect if running under GrampsWeb without importing it.

        :returns: True if running under GrampsWeb, False otherwise
        :rtype: bool
        """
        # Check for GrampsWeb-specific environment variables
        if os.environ.get('GRAMPSWEB_TREE'):
            return True

        # Check if gramps_webapi is in sys.modules (already imported)
        import sys
        if 'gramps_webapi' in sys.modules:
            return True

        # Check call stack for GrampsWeb
        import inspect
        for frame_info in inspect.stack():
            if 'gramps_webapi' in frame_info.filename:
                return True

        return False

    def _update_recent_files(self):
        """
        Update Gramps' recent files tracking with current timestamp.

        Creates meaningful virtual PostgreSQL paths instead of filesystem paths.
        Fixes the "Last Accessed: NEVER" issue.

        .. versionadded:: 1.4
            Recent files tracking for PostgreSQL databases.
        """
        try:
            from gramps.gen.recentfiles import recent_files

            # Create a meaningful virtual path for PostgreSQL
            if hasattr(self, 'table_prefix') and self.table_prefix:
                # Monolithic mode: use tree identifier
                tree_id = self.table_prefix.rstrip('_').replace('tree_', '')
                virtual_path = f"postgresql://monolithic/{tree_id}"
                display_name = f"PostgreSQL Tree: {tree_id}"
            else:
                # Separate mode: use database/directory name
                if hasattr(self, '_original_directory') and self._original_directory:
                    if '/' in str(self._original_directory):
                        db_name = self._original_directory.split('/')[-1]
                    else:
                        db_name = self._original_directory
                else:
                    db_name = "postgresql_db"
                virtual_path = f"postgresql://separate/{db_name}"
                display_name = f"PostgreSQL: {db_name}"

            # Get the tree name from metadata if available
            tree_name = self._get_metadata("name", display_name)

            # Update recent files with current timestamp
            recent_files(virtual_path, tree_name)

            LOG.debug(f"Updated recent files: {virtual_path} -> {tree_name}")

        except Exception as e:
            # Don't fail the entire load if recent files update fails
            LOG.warning(f"Could not update recent files tracking: {e}")

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
                        # Strip inline comments before storing value
                        value = value.split('#')[0].strip()
                        config[key.strip()] = value
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

    def _build_config_from_env(self):
        """
        Build configuration from environment variables for monolithic mode.

        Used by GrampsWeb when POSTGRESQL_ENHANCED_MODE=monolithic is set.
        All GRAMPSWEB_POSTGRES_* environment variables should be configured.

        :return: Configuration dictionary
        :rtype: dict
        """
        return {
            'host': os.environ.get('GRAMPSWEB_POSTGRES_HOST', 'localhost'),
            'port': os.environ.get('GRAMPSWEB_POSTGRES_PORT', '5432'),
            'database': os.environ.get('GRAMPSWEB_POSTGRES_DB', 'gramps'),
            'user': os.environ.get('GRAMPSWEB_POSTGRES_USER', 'gramps'),
            'password': os.environ.get('GRAMPSWEB_POSTGRES_PASSWORD', ''),
            'database_mode': 'monolithic'
        }

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

    def search_all_text(self, search_term, limit=100):
        """
        Full-text search across all text fields using modern PostgreSQL features.

        Uses tsvector full-text search when available, with fallback to ILIKE.

        :param search_term: Text to search for
        :type search_term: str
        :param limit: Maximum results to return
        :type limit: int
        :returns: List of search results
        :rtype: list
        """
        # Use modern SearchAPI with tsvector if available
        if self.search_api:
            return self.search_api.fulltext_search(
                search_term,
                limit=limit,
                obj_types=[
                    'person', 'family', 'event', 'place', 'source',
                    'note', 'citation', 'media', 'repository', 'tag'
                ]
            )

        # Fallback to enhanced queries ILIKE search if JSONB enabled
        elif self.enhanced_queries:
            return self.enhanced_queries.search_all_text(search_term, limit)

        else:
            raise RuntimeError(_("Full-text search requires JSONB support or search capabilities"))

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

    def get_descendants_tree(self, person_handle, max_depth=None):
        """
        Get complete descendants tree for a person.

        :param person_handle: Root person's handle
        :type person_handle: str
        :param max_depth: Maximum generations to retrieve
        :type max_depth: int
        :returns: Hierarchical structure of descendants
        :rtype: dict
        :raises RuntimeError: If enhanced queries not available
        """
        if not self.enhanced_queries:
            raise RuntimeError(_("Enhanced queries require JSONB support"))
        return self.enhanced_queries.get_descendants_tree(person_handle, max_depth)

    def find_potential_duplicates(self, threshold=0.8):
        """
        Find potential duplicate persons using name similarity.

        Requires pg_trgm extension for trigram similarity.

        :param threshold: Similarity threshold (0.0 to 1.0)
        :type threshold: float
        :returns: List of potential duplicate pairs
        :rtype: list
        :raises RuntimeError: If enhanced queries not available
        """
        if not self.enhanced_queries:
            raise RuntimeError(_("Enhanced queries require JSONB support"))
        return self.enhanced_queries.find_potential_duplicates(threshold)

    # -------------------------------------------------------------------------
    # Concurrency control methods
    # -------------------------------------------------------------------------

    def setup_real_time_notifications(self, channels=None):
        """
        Set up real-time notifications for multi-user collaboration.

        :param channels: List of channels to listen on
        :type channels: list[str]
        :returns: Success status
        :rtype: bool
        """
        if not self.concurrency:
            return False
        return self.concurrency.setup_listen_notify(channels)

    def notify_object_change(self, obj_type, handle, change_type, payload=None):
        """
        Notify other users of object changes.

        :param obj_type: Type of object (person, family, etc.)
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param change_type: Type of change (create, update, delete)
        :type change_type: str
        :param payload: Additional data to send
        :type payload: dict
        :returns: Success status
        :rtype: bool
        """
        if not self.concurrency:
            return False
        return self.concurrency.notify_change(obj_type, handle, change_type, payload)

    def add_change_listener(self, obj_type, callback):
        """
        Add a listener for object changes.

        :param obj_type: Type of object to listen for
        :type obj_type: str
        :param callback: Function to call when changes occur
        :type callback: callable
        """
        if self.concurrency:
            self.concurrency.add_change_listener(obj_type, callback)

    def acquire_object_lock(self, obj_type, handle, exclusive=True, timeout=5.0):
        """
        Acquire advisory lock on object for concurrent access control.

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param exclusive: Whether to acquire exclusive lock
        :type exclusive: bool
        :param timeout: Lock acquisition timeout in seconds
        :type timeout: float
        :returns: True if lock acquired successfully
        :rtype: bool
        """
        if not self.concurrency:
            return True  # Allow access if concurrency not available
        return self.concurrency.acquire_object_lock(obj_type, handle, exclusive, timeout)

    def release_object_lock(self, obj_type, handle):
        """
        Release advisory lock on object.

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :returns: Success status
        :rtype: bool
        """
        if not self.concurrency:
            return True
        return self.concurrency.release_object_lock(obj_type, handle)

    def object_lock(self, obj_type, handle, exclusive=True, timeout=5.0):
        """
        Create a context manager for object locking.

        Usage:
            with db.object_lock('person', handle):
                # Perform operations on the person object
                person = db.get_person_from_handle(handle)
                # ... modify person ...
                db.commit_person(person, trans)

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param exclusive: Whether to acquire exclusive lock
        :type exclusive: bool
        :param timeout: Lock acquisition timeout
        :type timeout: float
        :returns: Context manager for the lock
        """
        if not self.concurrency:
            # Return a dummy context manager that does nothing
            class DummyLock:
                def __enter__(self): return self
                def __exit__(self, *args): pass
            return DummyLock()
        return self.concurrency.object_lock(obj_type, handle, exclusive, timeout)

    def begin_transaction_with_isolation(self, isolation_level='READ_COMMITTED'):
        """
        Begin transaction with specific isolation level.

        :param isolation_level: Isolation level (READ_UNCOMMITTED, READ_COMMITTED, REPEATABLE_READ, SERIALIZABLE)
        :type isolation_level: str
        :returns: Success status
        :rtype: bool
        """
        if not self.concurrency:
            # Fallback to basic transaction
            try:
                self.dbapi.execute("BEGIN")
                return True
            except Exception:
                return False
        return self.concurrency.begin_transaction(isolation_level)

    def check_object_version(self, obj_type, handle, expected_version):
        """
        Check if object has been modified since expected version (optimistic concurrency control).

        :param obj_type: Type of object
        :type obj_type: str
        :param handle: Object handle
        :type handle: str
        :param expected_version: Expected version timestamp
        :type expected_version: float
        :raises ConcurrencyError: If object was modified by another user
        """
        if self.concurrency:
            self.concurrency.check_object_version(obj_type, handle, expected_version)

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

    def get_dbid(self):
        """
        Return unique database identifier.
        Required by Gramps Web for tree identification.

        :returns: Unique database identifier (UUID)
        :rtype: str
        """
        # Try to get from metadata first
        try:
            dbid = self.get_metadata('dbid')
            if dbid:
                return dbid
        except Exception:
            pass

        # Generate new UUID and store it
        import uuid
        dbid = str(uuid.uuid4())
        try:
            self.set_metadata('dbid', dbid)
        except Exception as e:
            LOG.warning("Could not store database ID in metadata: %s", e)

        return dbid

    def _detect_grampsweb_environment(self):
        """
        Detect if running under Gramps Web.

        :returns: True if Gramps Web environment variables are present
        :rtype: bool
        """
        grampsweb_indicators = [
            'GRAMPSWEB_TREE',           # Multi-tree mode indicator
            'GRAMPSWEB_USER_DB_URI',    # User database URI
            'GRAMPSWEB_NEW_DB_BACKEND', # Backend specification
            'GRAMPSWEB_POSTGRES_HOST',  # PostgreSQL configuration
        ]

        for indicator in grampsweb_indicators:
            if os.environ.get(indicator):
                LOG.debug("Gramps Web detected via %s", indicator)
                return True

        return False

    def is_read_only(self):
        """
        Check if database is read-only.
        Used by Gramps Web for UI permission handling.

        :returns: True if database is read-only
        :rtype: bool
        """
        return getattr(self, 'readonly', False)

    def get_mediapath(self):
        """
        Get media directory path.
        Used by Gramps Web for media file handling.

        :returns: Path to media directory or None
        :rtype: str or None
        """
        # Check metadata first
        try:
            path = self.get_metadata('mediapath')
            if path:
                return path
        except Exception:
            pass

        # Default to subdirectory of tree directory
        if hasattr(self, 'directory') and self.directory:
            return os.path.join(self.directory, 'media')

        return None

    def set_mediapath(self, path):
        """
        Set media directory path.

        :param path: Path to media directory
        :type path: str
        """
        try:
            self.set_metadata('mediapath', path)
        except Exception as e:
            LOG.warning("Could not store media path in metadata: %s", e)

    # ========================================================================
    # Search API for Gramps Web and other consumers
    # ========================================================================

    def search(self, query, search_type='auto', limit=100, **kwargs):
        """
        Unified search interface for Gramps Web compatibility.

        :param query: Search query string
        :type query: str
        :param search_type: Type of search ('auto', 'exact', 'fuzzy', 'phonetic', 'semantic')
        :type search_type: str
        :param limit: Maximum number of results
        :type limit: int
        :returns: List of search results with handles and relevance
        :rtype: list
        """
        if not self.search_api:
            # Fallback to basic search if capabilities not initialized
            return self._basic_search_fallback(query, limit, **kwargs)

        return self.search_api.search(query, search_type, limit=limit, **kwargs)

    def setup_fulltext_search(self):
        """
        Set up PostgreSQL native full-text search.
        This replaces the need for sifts entirely.
        """
        LOG.info("Setting up PostgreSQL native full-text search")

        # Add search vectors to all object tables
        for obj_type in ['person', 'family', 'event', 'place', 'source', 'citation',
                        'repository', 'media', 'note', 'tag']:
            table = self.schema._table_name(obj_type)

            try:
                # Add search column if not exists
                with self.dbapi.execute(f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS search_vector tsvector
                """):
                    pass

                # Create GIN index for fast searching
                with self.dbapi.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table}_search
                    ON {table} USING GIN(search_vector)
                """):
                    pass

                # Create trigger to auto-update search vector
                with self.dbapi.execute(f"""
                    CREATE OR REPLACE FUNCTION {table}_search_trigger()
                    RETURNS trigger AS $$
                    BEGIN
                        NEW.search_vector := to_tsvector('simple',
                            coalesce(NEW.json_data::text, ''));
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;

                    DROP TRIGGER IF EXISTS {table}_search_update ON {table};

                    CREATE TRIGGER {table}_search_update
                    BEFORE INSERT OR UPDATE ON {table}
                    FOR EACH ROW
                    EXECUTE FUNCTION {table}_search_trigger();
                """):
                    pass

                # Update existing rows
                with self.dbapi.execute(f"""
                    UPDATE {table}
                    SET search_vector = to_tsvector('simple', coalesce(json_data::text, ''))
                    WHERE search_vector IS NULL
                """):
                    pass

                LOG.debug(f"Full-text search enabled for {table}")

            except Exception as e:
                LOG.warning(f"Could not setup full-text search for {table}: {e}")

    def get_search_capabilities(self):
        """
        Get available search capabilities for Gramps Web.

        :returns: Dictionary of available search features
        :rtype: dict
        """
        if not self.search_capabilities:
            return {
                'level': 'basic',
                'features': ['basic_search'],
                'extensions': {}
            }

        return {
            'level': self.search_capabilities.search_level,
            'features': self.search_capabilities.get_available_features(),
            'extensions': self.search_capabilities.capabilities
        }

    def enable_search_extension(self, extension):
        """
        Try to enable a search extension if available.

        :param extension: Extension name (pg_trgm, fuzzystrmatch, etc.)
        :type extension: str
        :returns: True if successful
        :rtype: bool
        """
        if not self.search_capabilities:
            return False

        return self.search_capabilities.enable_extension(extension)

    def _basic_search_fallback(self, query, limit=100, **kwargs):
        """
        Basic search fallback when advanced features unavailable.
        Uses ILIKE for case-insensitive matching.
        """
        results = []
        query_pattern = f"%{query}%"

        # Search persons
        table = self.schema._table_name('person')
        with self.dbapi.execute(f"""
            SELECT handle, gramps_id, json_data
            FROM {table}
            WHERE json_data::text ILIKE %s
            LIMIT %s
        """, (query_pattern, limit)) as cur:
            for row in cur.fetchall():
                results.append({
                    'type': 'person',
                    'handle': row[0],
                    'gramps_id': row[1],
                    'data': row[2],
                    'relevance': 1.0
                })

        return results

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

    # ========================================================================
    # Public Metadata Methods for GrampsWeb Compatibility
    # ========================================================================

    def set_metadata(self, key, value):
        """
        Public wrapper for _set_metadata.
        Required by GrampsWeb for metadata storage.

        :param key: Metadata key
        :type key: str
        :param value: Metadata value
        :type value: Any
        """
        return self._set_metadata(key, value)

    def get_metadata(self, key, default=None):
        """
        Public wrapper for _get_metadata.
        Required by GrampsWeb for metadata retrieval.

        :param key: Metadata key
        :type key: str
        :param default: Default value if key not found
        :type default: Any
        :returns: Metadata value or default
        :rtype: Any
        """
        result = self._get_metadata(key, "_")
        return default if result == "_" else result

    # ========================================================================
    # Transaction History Support for GrampsWeb
    # ========================================================================

    def get_transactions(self, page=1, pagesize=20, old_data=False, new_data=False,
                        ascending=False, before=None, after=None):
        """
        Get transaction history with pagination.
        Required by GrampsWeb API for /api/transactions/history/

        :param page: Page number (1-based)
        :type page: int
        :param pagesize: Number of transactions per page
        :type pagesize: int
        :param old_data: Include old data in transactions
        :type old_data: bool
        :param new_data: Include new data in transactions
        :type new_data: bool
        :param ascending: Sort ascending by timestamp
        :type ascending: bool
        :param before: Filter transactions before this timestamp
        :type before: datetime or None
        :param after: Filter transactions after this timestamp
        :type after: datetime or None
        :returns: Tuple of (transactions list, total count)
        :rtype: tuple
        """
        # For now, return empty results to prevent errors
        # TODO: Implement actual transaction history from undo table
        transactions = []
        total_count = 0

        # If we have undo data, we could query it here
        # This would require querying the undo table with proper filtering

        return transactions, total_count

    # ========================================================================
    # Gramps Web Multi-Tree Support (Class Methods)
    # ========================================================================

    @classmethod
    def create_tree(cls, tree_id=None, name=None):
        """
        Create a new family tree.
        Required by Gramps Web API for POST /api/trees/

        :param tree_id: Optional tree identifier (UUID if not provided)
        :type tree_id: str or None
        :param name: Optional human-readable tree name
        :type name: str or None
        :returns: Tree identifier for the created tree
        :rtype: str
        """
        import uuid
        import tempfile

        # Generate tree ID if not provided
        if not tree_id:
            tree_id = str(uuid.uuid4())

        # Determine tree directory
        gramps_home = os.environ.get('GRAMPS_HOME', tempfile.gettempdir())
        tree_dir = os.path.join(gramps_home, 'gramps_tree_%s' % tree_id)
        os.makedirs(tree_dir, exist_ok=True)

        # Determine database mode from environment
        database_mode = os.environ.get('POSTGRESQL_ENHANCED_MODE', 'separate')

        # Create connection_info.txt
        config_path = os.path.join(tree_dir, 'connection_info.txt')
        with open(config_path, 'w') as f:
            f.write("# PostgreSQL Enhanced Configuration\n")
            f.write("# Auto-generated for Gramps Web\n\n")
            f.write("# Connection details\n")
            f.write("host = %s\n" % os.environ.get('GRAMPSWEB_POSTGRES_HOST', 'localhost'))
            f.write("port = %s\n" % os.environ.get('GRAMPSWEB_POSTGRES_PORT', '5432'))
            f.write("user = %s\n" % os.environ.get('GRAMPSWEB_POSTGRES_USER', 'gramps'))
            f.write("password = %s\n" % os.environ.get('GRAMPSWEB_POSTGRES_PASSWORD', ''))
            f.write("\n# Database mode\n")
            f.write("database_mode = %s\n" % database_mode)

            if database_mode == 'monolithic':
                f.write("\n# Monolithic mode configuration\n")
                f.write("monolithic_database = %s\n" %
                       os.environ.get('GRAMPSWEB_POSTGRES_DB', 'gramps'))
                f.write("tree_prefix = tree_%s_\n" % tree_id[:8])

        # Write database.txt
        with open(os.path.join(tree_dir, 'database.txt'), 'w') as f:
            f.write('postgresqlenhanced')

        # Write name.txt
        with open(os.path.join(tree_dir, 'name.txt'), 'w') as f:
            f.write(name or 'Tree %s' % tree_id[:8])

        # Initialize the database
        try:
            db = cls()
            db._initialize(tree_dir, None, None)

            # Set initial metadata
            db.set_metadata('dbid', tree_id)
            db.set_metadata('name', name or 'Tree %s' % tree_id[:8])
            db.set_metadata('created', str(time.time()))

            LOG.info("Created tree %s in %s mode", tree_id, database_mode)

        except Exception as e:
            LOG.error("Failed to create tree %s: %s", tree_id, e)
            raise

        return tree_id

    @classmethod
    def list_trees(cls):
        """
        List available family trees.
        Optional for Gramps Web multi-tree mode.

        :returns: List of tree dictionaries with id, name, and path
        :rtype: list
        """
        trees = []

        # For monolithic mode, query the database
        if os.environ.get('POSTGRESQL_ENHANCED_MODE') == 'monolithic':
            try:
                # Connect to monolithic database
                conn_params = {
                    'host': os.environ.get('GRAMPSWEB_POSTGRES_HOST', 'localhost'),
                    'port': int(os.environ.get('GRAMPSWEB_POSTGRES_PORT', 5432)),
                    'dbname': os.environ.get('GRAMPSWEB_POSTGRES_DB', 'gramps'),
                    'user': os.environ.get('GRAMPSWEB_POSTGRES_USER', 'gramps'),
                    'password': os.environ.get('GRAMPSWEB_POSTGRES_PASSWORD', ''),
                }

                with psycopg.connect(**conn_params) as conn:
                    with conn.cursor() as cur:
                        # Query for all tree prefixes
                        cur.execute("""
                            SELECT DISTINCT
                                substring(tablename from 'tree_(.*)_metadata') as tree_id
                            FROM pg_tables
                            WHERE tablename LIKE 'tree_%_metadata'
                        """)

                        for row in cur.fetchall():
                            tree_id = row[0]
                            trees.append({
                                'id': tree_id,
                                'name': 'Tree %s' % tree_id,
                                'mode': 'monolithic'
                            })

            except Exception as e:
                LOG.error("Failed to list trees from database: %s", e)

        # Also check file system
        gramps_home = os.environ.get('GRAMPS_HOME', '/tmp')
        if os.path.exists(gramps_home):
            for entry in os.listdir(gramps_home):
                if entry.startswith('gramps_tree_'):
                    tree_dir = os.path.join(gramps_home, entry)
                    tree_id = entry.replace('gramps_tree_', '')

                    # Read name if available
                    name_file = os.path.join(tree_dir, 'name.txt')
                    name = 'Tree %s' % tree_id[:8]
                    if os.path.exists(name_file):
                        try:
                            with open(name_file) as f:
                                name = f.read().strip()
                        except:
                            pass

                    # Check database mode
                    mode = 'separate'
                    config_file = os.path.join(tree_dir, 'connection_info.txt')
                    if os.path.exists(config_file):
                        with open(config_file) as f:
                            if 'database_mode = monolithic' in f.read():
                                mode = 'monolithic'

                    trees.append({
                        'id': tree_id,
                        'name': name,
                        'path': tree_dir,
                        'mode': mode
                    })

        return trees


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


# ------------------------------------------------------------
#
# Mode-specific wrapper classes
#
# ------------------------------------------------------------
class PostgreSQLEnhancedMonolithic(PostgreSQLEnhancedBase):
    """
    PostgreSQL Enhanced with Monolithic mode.

    All family trees share one PostgreSQL database with table prefixes.
    Recommended for most users.
    """

    def __init__(self):
        """Initialize with monolithic mode forced."""
        super().__init__(force_mode="monolithic")


class PostgreSQLEnhancedSeparate(PostgreSQLEnhancedBase):
    """
    PostgreSQL Enhanced with Separate mode.

    Each family tree gets its own PostgreSQL database.
    For advanced users requiring complete tree isolation.
    """

    def __init__(self):
        """Initialize with separate mode forced."""
        super().__init__(force_mode="separate")
