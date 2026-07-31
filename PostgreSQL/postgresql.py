#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2016 Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2016-2017 Nick Hall
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

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import psycopg2
import os
import re

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.plugins.db.dbapi.dbapi import DBAPI
from gramps.gen.utils.configmanager import ConfigManager
from gramps.gen.config import config
from gramps.gen.db.dbconst import ARRAYSIZE
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import (
    Citation, Event, Family, Media, Note, Person, Place, Repository, Source, Tag
)
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

psycopg2.paramstyle = "format"


# -------------------------------------------------------------------------
#
# PostgreSQL class
#
# -------------------------------------------------------------------------
class PostgreSQL(DBAPI):

    dialect = "postgresql"

    def _sql_type(self, schema_type, max_length):
        result = super()._sql_type(schema_type, max_length)
        return "bytea" if result == "BLOB" else result

    def _quote_column(self, col):
        # Remove this method when gramps PR #2178 (dbapi _quote_column) is merged.
        _RESERVED = {"desc", "order", "where", "select"}
        return f"{col}_" if col in _RESERVED else col

    def _create_secondary_columns(self):
        # Remove override when gramps PR #2178 (_quote_column) is merged into core.
        for cls in (Person, Family, Event, Place, Repository, Source, Citation, Media, Note, Tag):
            table_name = cls.__name__.lower()
            for field, schema_type, max_length in cls.get_secondary_fields():
                if field != "handle":
                    sql_type = self._sql_type(schema_type, max_length)
                    self.dbapi.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN"
                        f" {self._quote_column(field)} {sql_type}"
                    )

    def _update_secondary_values(self, obj):
        # Remove override when gramps PR #2178 (_quote_column) is merged into core.
        table = obj.__class__.__name__
        fields = [field[0] for field in obj.get_secondary_fields()]
        sets = []
        values = []
        for field in fields:
            sets.append(f"{self._quote_column(field)} = ?")
            values.append(getattr(obj, field))

        if table == "Person":
            given_name, surname = self._get_person_data(obj)
            sets.append("given_name = ?")
            values.append(given_name)
            sets.append("surname = ?")
            values.append(surname)
        if table == "Place":
            handle = self._get_place_data(obj)
            sets.append("enclosed_by = ?")
            values.append(handle)

        if len(values) > 0:
            table_name = table.lower()
            self.dbapi.execute(
                f'UPDATE {table_name} SET {", ".join(sets)} where handle = ?',
                self._sql_cast_list(values) + [obj.handle],
            )

    def get_media_handles(self, sort_handles=False, locale=glocale):
        # Remove override when gramps PR #2178 (_quote_column) is merged into core.
        if sort_handles:
            self.dbapi.execute(
                "SELECT handle FROM media "
                f"ORDER BY {self._quote_column('desc')} "
                f'COLLATE "{self._collation(locale)}"'
            )
        else:
            self.dbapi.execute("SELECT handle FROM media")
        return [row[0] for row in self.dbapi.fetchall()]

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

        if not os.path.exists(config_file):
            name_file = os.path.join(directory, "name.txt")
            with open(name_file, "r", encoding="utf8") as file:
                dbname = file.readline().strip()
            config_mgr.set("database.dbname", dbname)
            config_mgr.set("database.host", config.get("database.host"))
            config_mgr.set("database.port", config.get("database.port"))
            config_mgr.save()

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

        try:
            self.dbapi = Connection(**dbkwargs)
        except psycopg2.OperationalError as msg:
            raise DbConnectionError(str(msg), config_file)


# -------------------------------------------------------------------------
#
# Connection class
#
# -------------------------------------------------------------------------
class Connection:

    def __init__(self, *args, **kwargs):
        self.__connection = psycopg2.connect(*args, **kwargs)
        self.__connection.autocommit = True
        self.__cursor = self.__connection.cursor()
        self.check_collation(glocale)

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
        sql = args[0].replace("?", "%s")      # qmark → format paramstyle
        sql = sql.replace(" REGEXP ", " ~ ")  # SQLite REGEXP → PostgreSQL ~
        # SQLite LIKE is case-insensitive (ASCII); PostgreSQL LIKE is
        # case-sensitive, so use ILIKE for equivalent behavior. Note that
        # PostgreSQL's ILIKE case-folding follows the connection's locale/
        # collation, while SQLite's is ASCII-only, so non-ASCII patterns may
        # fold slightly differently between the two backends.
        sql = re.sub(r"\bLIKE\b", "ILIKE", sql, flags=re.IGNORECASE)
        # TODO: remove when gramps PR #2178 (_quote_column) is merged into core
        sql = sql.replace("ON media(desc)", "ON media(desc_)")
        sql = re.sub(r'\bBLOB\b', 'BYTEA', sql)  # SQLite BLOB → PostgreSQL BYTEA
        sql = re.sub(r'\bLIMIT\s+(-?\d+)\s*,\s*(-?\d+)',
                     lambda m: f'LIMIT {"ALL" if m.group(2) == "-1" else m.group(2)} OFFSET {m.group(1)}',
                     sql, flags=re.IGNORECASE)  # LIMIT offset, count → LIMIT count OFFSET offset
        sql = re.sub(r'\bLIMIT\s+-1\b', 'LIMIT ALL', sql, flags=re.IGNORECASE)  # LIMIT -1 → LIMIT ALL
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
        """Drop a column from a table.
        :param table_name: name of the table to drop the column from.
        :type table_name: str
        :param column_name: name of the column to drop.
        :type column_name: str
        """
        self.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name};")

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
        self.__cursor.execute(*args, **kwargs)

    def fetchmany(self):
        """
        Fetches the next set of rows of a query result, returning a list. An
        empty list is returned when no more rows are available.
        """
        try:
            return self.__cursor.fetchmany()
        except:
            return None
