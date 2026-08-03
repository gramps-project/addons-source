#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2016 Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2016-2017 Nick Hall
# Copyright (C) 2022-2025 David Straub
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
Backend for PostgreSQL database.
"""

import hashlib
import os
import re
from uuid import uuid4

import psycopg2
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db.dbconst import ARRAYSIZE
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.lib.json_utils import dict_to_string
from gramps.gen.utils.configmanager import ConfigManager

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

from shareddbapi import SharedDBAPI

psycopg2.paramstyle = "format"


# -------------------------------------------------------------------------
#
# SharedPostgreSQL class
#
# -------------------------------------------------------------------------
class SharedPostgreSQL(SharedDBAPI):
    dialect = "postgresql"

    # Column names as they physically exist in shared PostgreSQL databases.
    # "desc" is reserved in PostgreSQL and was renamed by the old blanket
    # substring rewrite, which also caught "description" as a side effect.
    # Both names are kept so existing databases stay readable.
    _COLUMN_NAMES = {"desc": "desc_", "description": "desc_ription"}

    def _quote_column(self, col):
        return self._COLUMN_NAMES.get(col, col)

    def _sql_type(self, schema_type, max_length):
        result = super()._sql_type(schema_type, max_length)
        return "bytea" if result == "BLOB" else result

    def get_summary(self):
        """
        Return a diction of information about this database
        backend.
        """
        summary = super().get_summary()
        summary.update(
            {
                _("Database version"): psycopg2.__version__,
                _("Database module location"): psycopg2.__file__,
            }
        )
        return summary

    def requires_login(self):
        return True

    def _initialize(self, directory, username, password):
        config_file = os.path.join(directory, "settings.ini")
        config_mgr = ConfigManager(config_file)
        config_mgr.register("database.dbname", "")
        config_mgr.register("database.host", "")
        config_mgr.register("database.port", "")
        config_mgr.register("tree.uuid", "")

        if not os.path.exists(config_file):
            self._create_settings(config_file, config_mgr, directory, username, password)

        config_mgr.load()

        dbkwargs = {}
        for key in config_mgr.get_section_settings("database"):
            value = config_mgr.get("database." + key)
            if value:
                dbkwargs[key] = value
        if username:
            dbkwargs["user"] = username
        if password:
            dbkwargs["password"] = password

        uuid = config_mgr.get("tree.uuid")

        if not uuid:
            raise ValueError("No tree UUID found.")
        try:
            self.dbapi = Connection(uuid=uuid, **dbkwargs)
        except psycopg2.OperationalError as msg:
            raise DbConnectionError(str(msg), config_file)

    def _create_settings(self, config_file, config_mgr, directory, username, password):
        """Create settings.ini for a tree that has not been initialized yet."""
        host = config.get("database.host")
        port = config.get("database.port")
        dbkwargs = {"dbname": "gramps", "host": host, "port": port}
        if username:
            dbkwargs["user"] = username
        if password:
            dbkwargs["password"] = password
        # Two processes opening a brand-new tree at the same time would each
        # generate a UUID and overwrite each other's settings.ini. Serialize
        # on the database, since the filesystem may not do so itself.
        digest = hashlib.sha256(os.path.abspath(directory).encode()).digest()
        lock_key = int.from_bytes(digest[:8], "big", signed=True)
        try:
            conn = psycopg2.connect(**dbkwargs)
        except psycopg2.OperationalError as msg:
            raise DbConnectionError(str(msg), config_file)
        try:
            conn.autocommit = True
            # The lock is released when the connection closes.
            conn.cursor().execute("SELECT pg_advisory_lock(%s)", [lock_key])
            if not os.path.exists(config_file):
                config_mgr.set("database.dbname", "gramps")
                config_mgr.set("database.host", host)
                config_mgr.set("database.port", port)
                config_mgr.set("tree.uuid", uuid4().hex)
                config_mgr.save()
        finally:
            conn.close()


# -------------------------------------------------------------------------
#
# Connection class
#
# -------------------------------------------------------------------------
class Connection:
    def __init__(self, *args, uuid, **kwargs):
        self.__connection = psycopg2.connect(*args, **kwargs)
        self.__connection.autocommit = True
        self.__cursor = self.__connection.cursor()
        self.uuid = uuid
        self._treeid = ""
        self.check_collation(glocale)

    @property
    def treeid(self):
        """Return an integer treeid from the UUID."""
        # return cached value
        treeid = self._get_treeid()
        if treeid:
            return treeid
        # create new ID
        self.execute("INSERT INTO trees (uuid) VALUES (%s)", [self.uuid])
        # set schema version for the new tree
        self._update_schema_version()
        return self.treeid

    def _get_treeid(self):
        """Get the tree ID"""
        # return cached value
        if self._treeid:
            return self._treeid
        # try to fetch ID from database
        self.execute("SELECT treeid FROM trees WHERE uuid = %s", [self.uuid])
        row = self.fetchone()
        if row:
            self._treeid = row[0]
            return self._treeid
        return None

    def _update_schema_version(self):
        """Update the schema version for the tree."""
        treeid = self._get_treeid()
        if not treeid:
            raise ValueError("Tree ID not found")
        version = SharedPostgreSQL.VERSION[0]
        version_str = dict_to_string({"type": "str", "value": str(version)})
        self.execute(
            f"INSERT INTO metadata (treeid, setting, json_data) VALUES (?, ?, ?)",
            [treeid, "version", version_str],
        )

    def _schema_version_exists(self):
        """Check if the schema version exists."""
        treeid = self._get_treeid()
        if not treeid:
            raise ValueError("Tree ID not found")
        self.execute(
            "SELECT COUNT(*) FROM metadata WHERE treeid = ? AND setting = ? AND json_data IS NOT NULL",
            [treeid, "version"],
        )
        row = self.fetchone()
        if not row:
            return False
        count = row[0]
        return count > 0

    def check_collation(self, locale):
        """
        Checks that a collation exists and if not creates it.

        :param locale: Locale to be checked.
        :type locale: A GrampsLocale object.
        """
        collation = locale.get_collation()
        # Use pg_collation to check existence rather than IF NOT EXISTS, which
        # requires PostgreSQL 12+.
        self.execute("SELECT 1 FROM pg_collation WHERE collname = %s", [collation])
        if not self.fetchone():
            self.execute(
                "CREATE COLLATION \"%s\" (LOCALE = '%s')"
                % (collation, locale.collation)
            )

    def execute(self, *args, **kwargs):
        sql = _translate_sql(args[0])
        if len(args) > 1:
            args = args[1]
        else:
            args = None
        try:
            self.__cursor.execute(sql, args, **kwargs)
        except:
            self.__cursor.execute("rollback")
            raise

    def fetchone(self):
        try:
            return self.__cursor.fetchone()
        except:
            return None

    def fetchall(self):
        return self.__cursor.fetchall()

    def begin(self):
        self.__cursor.execute("BEGIN;")

    def commit(self):
        self.__cursor.execute("COMMIT;")

    def rollback(self):
        self.__connection.rollback()

    def table_exists(self, table):
        self.__cursor.execute(
            "SELECT COUNT(*) " "FROM information_schema.tables " "WHERE table_name=%s;",
            [table],
        )
        return self.fetchone()[0] != 0

    def column_exists(self, table, column):
        """
        Test whether the specified SQL column exists in the specified table.
        :param table: table name to check.
        :type table: str
        :param column: column name to check.
        :type column: str
        :returns: True if the column exists, False otherwise.
        :rtype: bool
        """
        self.__cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        return self.fetchone()[0] != 0

    def drop_column(self, table_name, column_name):
        pass  # we never delete columns on shared databases!

    def close(self):
        self.__connection.close()

    def cursor(self):
        return Cursor(self.__connection)


# -------------------------------------------------------------------------
#
# Cursor class
#
# -------------------------------------------------------------------------
class Cursor:
    def __init__(self, connection):
        self.__connection = connection

    def __enter__(self):
        self.__cursor = self.__connection.cursor()
        self.__cursor.arraysize = ARRAYSIZE
        return self

    def __exit__(self, *args, **kwargs):
        self.__cursor.close()

    def execute(self, *args, **kwargs):
        """
        Executes an SQL statement.

        :param args: arguments to be passed to the sqlite3 execute statement
        :type args: list
        :param kwargs: arguments to be passed to the sqlite3 execute statement
        :type kwargs: list
        """
        sql = _translate_sql(args[0])
        if len(args) > 1:
            args = args[1]
        else:
            args = None
        self.__cursor.execute(sql, args, **kwargs)

    def fetchmany(self):
        """
        Fetches the next set of rows of a query result, returning a list. An
        empty list is returned when no more rows are available.
        """
        try:
            return self.__cursor.fetchmany()
        except:
            return None


def _translate_sql(query):
    """
    Translate an SQLite-flavoured SQL statement to PostgreSQL.

    :param query: the statement to translate.
    :type query: str
    :returns: the translated statement.
    :rtype: str
    """
    sql = query.replace("?", "%s")  # qmark -> format paramstyle
    sql = sql.replace(" REGEXP ", " ~ ")  # SQLite REGEXP -> PostgreSQL ~
    # SQLite LIKE is case-insensitive (ASCII), PostgreSQL's is not; ILIKE is
    # the case-insensitive equivalent. Its folding follows the connection
    # locale, so non-ASCII patterns may fold differently than under SQLite.
    sql = re.sub(r"\bLIKE\b", "ILIKE", sql, flags=re.IGNORECASE)
    sql = sql.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
    sql = re.sub(r"\bBLOB\b", "BYTEA", sql)  # SQLite BLOB -> PostgreSQL BYTEA
    # LIMIT offset, count -> LIMIT count OFFSET offset; a count of -1 means all
    sql = re.sub(
        r"\bLIMIT\s+(-?\d+)\s*,\s*(-?\d+)",
        lambda m: f'LIMIT {"ALL" if m.group(2) == "-1" else m.group(2)}'
        f" OFFSET {m.group(1)}",
        sql,
        flags=re.IGNORECASE,
    )
    sql = re.sub(r"\bLIMIT\s+-1\b", "LIMIT ALL", sql, flags=re.IGNORECASE)
    return sql
