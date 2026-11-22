#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 David Straub
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
Unit tests for the statements SharedPostgreSQL runs when a tree is opened.

Gramps Web opens the tree on every request, so load() should run as few
statements as possible:

  - all metadata is read with one query
  - table, column and collation checks run once per process
  - the surname list and gender stats are read on first access, and a
    write after a read-only open keeps the stored gender stats

psycopg2 is stubbed with a connection backed by SQLite that understands the
few PostgreSQL-only statements the addon sends, so the addon's own
Connection runs unchanged and no server is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_open_queries -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

# -------------------------------------------------------------------------
#
# Stub psycopg2 before the addon is imported so no real DB driver is needed
#
# -------------------------------------------------------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

_mock_psycopg2 = mock.MagicMock()
_mock_psycopg2.paramstyle = "format"
_mock_psycopg2.OperationalError = Exception
sys.modules.setdefault("psycopg2", _mock_psycopg2)

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
try:
    import gramps
except ImportError as _err:
    raise unittest.SkipTest("gramps package not available: %s" % _err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

try:
    from gramps.gen.db import DbTxn
    from gramps.gen.db.dbconst import DBMODE_R, DBMODE_W
    from gramps.gen.lib import Name, Note, Person, Surname
    from gramps.gen.lib.serialize import JSONSerializer

    from SharedPostgreSQL import sharedpostgresql
    from SharedPostgreSQL.sharedpostgresql import SharedPostgreSQL
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)


# -------------------------------------------------------------------------
#
# psycopg2 stand-in backed by SQLite
#
# -------------------------------------------------------------------------
class _FakeServer:
    """One database: an SQLite connection plus the statements sent to it."""

    count = 0

    def __init__(self):
        _FakeServer.count += 1
        self.dbname = "gramps%d" % _FakeServer.count
        self.sqlite = sqlite3.connect(":memory:", isolation_level=None)
        self.collations = set()
        self.prepared = {}
        self.statements = []

    def connect(self, *args, **kwargs):
        return _FakeConnection(self)


class _FakeInfo:
    def __init__(self, server):
        self._server = server
        self.host = "localhost"
        self.port = 5432
        self.dbname = server.dbname

    @property
    def transaction_status(self):
        if self._server.sqlite.in_transaction:
            return object()
        return sharedpostgresql.psycopg2.extensions.TRANSACTION_STATUS_IDLE


class _FakeConnection:
    def __init__(self, server):
        self.server = server
        self.info = _FakeInfo(server)
        self.autocommit = False

    def cursor(self):
        return _FakeCursor(self.server)

    def close(self):
        pass


class _FakeCursor:
    """Runs the PostgreSQL statements the addon sends on SQLite."""

    def __init__(self, server):
        self.server = server
        self.cursor = server.sqlite.cursor()
        self.arraysize = 1

    def execute(self, sql, args=None):
        self.server.statements.append(sql)
        sql, args = self._translate(sql, list(args or []))
        self.cursor.execute(sql, args)

    def _translate(self, sql, args):
        nothing = "SELECT 1 WHERE 0"
        if sql.startswith("SET ") or re.match(r"ALTER TABLE \w+ SET \(", sql):
            return nothing, []
        if "FROM pg_collation" in sql:
            if args[0] in self.server.collations:
                return "SELECT 1", []
            return nothing, []
        match = re.match(r'CREATE COLLATION "([^"]+)"', sql)
        if match:
            self.server.collations.add(match.group(1))
            return nothing, []
        if "information_schema.tables" in sql:
            return "SELECT COUNT(*) FROM sqlite_master WHERE name = ?", args
        if "information_schema.columns" in sql:
            return "SELECT COUNT(*) FROM pragma_table_info(?) WHERE name = ?", args
        match = re.match(r"PREPARE (\w+) AS (.*)", sql, re.S)
        if match:
            self.server.prepared[match.group(1)] = re.sub(
                r"\$(\d+)", r"?\1", match.group(2)
            )
            return nothing, []
        match = re.match(r"EXECUTE (\w+) ", sql)
        if match:
            return self.server.prepared[match.group(1)], args
        if sql.startswith("DEALLOCATE "):
            return nothing, []
        sql = sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY")
        # SQLite wants table constraints after all columns
        match = re.match(
            r"(CREATE TABLE \w+ \()(.*)(PRIMARY KEY \([^)]*\)), (.*)\)$", sql
        )
        if match:
            head, before, key, after = match.groups()
            sql = f"{head}{before}{after}, {key})"
        sql = re.sub(r'COLLATE "[^"]+"', "", sql)
        sql = re.sub(r"\bILIKE\b", "LIKE", sql)
        return sql.replace("%s", "?"), args

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchmany(self, size=None):
        return self.cursor.fetchmany(size or self.arraysize)

    def close(self):
        self.cursor.close()


# -------------------------------------------------------------------------
#
# Base class
#
# -------------------------------------------------------------------------
PEOPLE = [
    # (given name, surname, gender)
    ("Anna", "Zeller", Person.FEMALE),
    ("Bernd", "Albers", Person.MALE),
    ("Anna", "Albers", Person.FEMALE),
    ("Chris", "Meyer", Person.UNKNOWN),
]


class OpenTestCase(unittest.TestCase):
    """A tree with a few people on a fresh fake server."""

    def setUp(self):
        self.server = _FakeServer()
        self.addCleanup(self.server.sqlite.close)
        patcher = mock.patch.object(
            sharedpostgresql.psycopg2, "connect", side_effect=self.server.connect
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(sharedpostgresql._EXISTING.clear)
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        with open(os.path.join(self.directory, "settings.ini"), "w") as ini:
            ini.write(
                "[database]\ndbname='gramps'\nhost='localhost'\nport='5432'\n\n"
                "[tree]\nuuid='testtree'\n"
            )
        db = self.open(DBMODE_W)
        with DbTxn("add people", db) as txn:
            for given, surname, gender in PEOPLE:
                db.add_person(self.make_person(given, surname, gender), txn)
        db.close()
        self.stored_gender_stats = self.read_gender_stats_table()
        # start the tests like a new process would
        sharedpostgresql._EXISTING.clear()

    def open(self, mode=DBMODE_R):
        db = SharedPostgreSQL()
        db.load(self.directory, mode=mode, username="user", password="secret")
        return db

    def open_recording(self, mode=DBMODE_R):
        """Open the tree; return it and the statements load() ran."""
        del self.server.statements[:]
        db = self.open(mode)
        statements = list(self.server.statements)
        del self.server.statements[:]
        return db, statements

    @staticmethod
    def make_person(given, surname, gender):
        name = Name()
        name.set_first_name(given)
        name.add_surname(Surname())
        name.get_primary_surname().set_surname(surname)
        person = Person()
        person.set_primary_name(name)
        person.set_gender(gender)
        return person

    def read_gender_stats_table(self):
        rows = self.server.sqlite.execute(
            "SELECT given_name, female, male, unknown FROM gender_stats"
        ).fetchall()
        return {row[0]: tuple(row[1:]) for row in rows}


# -------------------------------------------------------------------------
#
# TestOpenStatements
#
# -------------------------------------------------------------------------
class TestOpenStatements(OpenTestCase):
    """The statements a read-only open runs."""

    def test_metadata_is_read_with_one_query(self):
        db, statements = self.open_recording()
        self.addCleanup(db.close)
        metadata = [sql for sql in statements if "FROM metadata" in sql]
        self.assertEqual(
            metadata, ["SELECT setting, json_data FROM metadata WHERE treeid = %s"]
        )

    def test_first_open_in_process_checks_schema(self):
        db, statements = self.open_recording()
        self.addCleanup(db.close)
        self.assertTrue(any("information_schema" in sql for sql in statements))
        self.assertTrue(any("pg_collation" in sql for sql in statements))

    def test_later_open_skips_schema_and_collation_checks(self):
        self.open().close()
        db, statements = self.open_recording()
        self.addCleanup(db.close)
        for sql in statements:
            self.assertNotIn("information_schema", sql)
            self.assertNotIn("pg_collation", sql)
            self.assertNotIn("CREATE COLLATION", sql)
        self.assertEqual(len(statements), 3, statements)

    def test_surnames_and_gender_stats_are_not_read_on_open(self):
        db, statements = self.open_recording()
        self.addCleanup(db.close)
        for sql in statements:
            self.assertNotIn("FROM person", sql)
            self.assertNotIn("FROM gender_stats", sql)

    def test_read_only_close_runs_no_statements(self):
        db = self.open()
        del self.server.statements[:]
        db.close()
        self.assertEqual(self.server.statements, [])

    def test_get_metadata_queries_after_load(self):
        db = self.open()
        self.addCleanup(db.close)
        del self.server.statements[:]
        self.assertEqual(db._get_metadata("version"), str(db.VERSION[0]))
        self.assertEqual(
            self.server.statements,
            ["SELECT json_data FROM metadata " "WHERE setting = %s AND treeid = %s"],
        )

    def test_change_after_load_is_seen(self):
        db = self.open()
        self.addCleanup(db.close)
        other = self.open(DBMODE_W)
        other._set_metadata("default-person-handle", "H1")
        other.close()
        self.assertEqual(db.get_default_handle(), "H1")


# -------------------------------------------------------------------------
#
# TestMetadataValues
#
# -------------------------------------------------------------------------
class TestMetadataValues(OpenTestCase):
    """Values read with the one query match those read one by one."""

    def test_values_are_loaded(self):
        db = self.open(DBMODE_W)
        db.bookmarks.append("H1")
        db.event_names.add("Custom event")
        db.cmap_index = 7
        db.close()
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.bookmarks.get(), ["H1"])
        self.assertEqual(db.event_names, {"Custom event"})
        self.assertEqual(db.cmap_index, 7)

    def test_missing_key_gives_default(self):
        self.server.sqlite.execute(
            "DELETE FROM metadata WHERE setting IN ('cmap_index', 'event_names')"
        )
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.cmap_index, 0)
        self.assertEqual(db.event_names, set())

    def test_null_value_is_deserialized(self):
        self.server.sqlite.execute(
            "UPDATE metadata SET json_data = NULL WHERE setting = 'cmap_index'"
        )
        to_object = JSONSerializer.metadata_to_object

        def deserialize(string):
            if string is None:
                return "from NULL"
            return to_object(string)

        with mock.patch.object(
            JSONSerializer, "metadata_to_object", side_effect=deserialize
        ):
            db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.cmap_index, "from NULL")

    def test_unconverted_tree_uses_blob_metadata(self):
        # a tree whose version has no JSON value yet is read as blobs
        self.server.sqlite.execute(
            "UPDATE metadata SET json_data = NULL WHERE setting = 'version'"
        )
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.serializer.metadata_field, "value")
        self.assertEqual(db.cmap_index, 0)


# -------------------------------------------------------------------------
#
# TestLazyData
#
# -------------------------------------------------------------------------
class TestLazyData(OpenTestCase):
    """The surname list and gender stats are read when first used."""

    def test_surname_list(self):
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.surname_list, ["Albers", "Meyer", "Zeller"])
        self.assertEqual(db.get_surname_list(), ["Albers", "Meyer", "Zeller"])

    def test_gender_stats(self):
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.genderStats.stats, self.stored_gender_stats)
        self.assertEqual(db.genderStats.guess_gender("Anna"), Person.FEMALE)
        self.assertEqual(db.get_gender_stats(), self.stored_gender_stats)

    def test_stored_gender_stats_are_counted(self):
        self.assertEqual(self.stored_gender_stats["Anna"], (0, 2, 0))

    def test_write_after_read_only_open_keeps_gender_stats(self):
        # Gramps Web opens read-only and may allow writes afterwards
        db = self.open()
        db.readonly = False
        with DbTxn("add note", db) as txn:
            db.add_note(Note("text"), txn)
        db.close()
        self.assertEqual(self.read_gender_stats_table(), self.stored_gender_stats)
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.genderStats.stats, self.stored_gender_stats)

    def test_person_added_after_read_only_open_is_counted(self):
        db = self.open()
        db.readonly = False
        with DbTxn("add person", db) as txn:
            db.add_person(self.make_person("Anna", "Neu", Person.FEMALE), txn)
        db.close()
        expected = dict(self.stored_gender_stats, Anna=(0, 3, 0))
        self.assertEqual(self.read_gender_stats_table(), expected)
        db = self.open()
        self.addCleanup(db.close)
        self.assertEqual(db.surname_list, ["Albers", "Meyer", "Neu", "Zeller"])

    def test_assigned_values_are_kept(self):
        db = self.open()
        self.addCleanup(db.close)
        db.surname_list = ["X"]
        self.assertEqual(db.surname_list, ["X"])


# -------------------------------------------------------------------------
#
# TestExistenceChecks
#
# -------------------------------------------------------------------------
class TestExistenceChecks(OpenTestCase):
    """Only checks that found the table or column outside a transaction
    are remembered."""

    def connection(self):
        conn = sharedpostgresql.Connection(uuid="testtree", dbname="gramps")
        del self.server.statements[:]
        return conn

    def schema_checks(self):
        return [sql for sql in self.server.statements if "information_schema" in sql]

    def test_existing_table_is_checked_once(self):
        conn = self.connection()
        self.assertTrue(conn.table_exists("person"))
        self.assertTrue(conn.table_exists("person"))
        self.assertEqual(len(self.schema_checks()), 1)

    def test_missing_table_is_checked_again(self):
        conn = self.connection()
        self.assertFalse(conn.table_exists("nonexistent"))
        self.assertFalse(conn.column_exists("person", "nonexistent"))
        self.assertFalse(conn.table_exists("nonexistent"))
        self.assertFalse(conn.column_exists("person", "nonexistent"))
        self.assertEqual(len(self.schema_checks()), 4)

    def test_check_inside_transaction_is_not_remembered(self):
        conn = self.connection()
        conn.begin()
        self.assertTrue(conn.column_exists("person", "handle"))
        conn.rollback()
        self.assertTrue(conn.column_exists("person", "handle"))
        self.assertEqual(len(self.schema_checks()), 2)

    def test_other_database_is_checked(self):
        self.connection().table_exists("person")
        self.server.dbname = "other"
        self.connection().table_exists("person")
        self.assertEqual(len(self.schema_checks()), 1)


if __name__ == "__main__":
    unittest.main()
