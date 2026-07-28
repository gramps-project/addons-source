#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2016 Douglas S. Blank <doug.blank@gmail.com>
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
Unit tests for the SharedPostgreSQL SQL dialect translations.

These tests cover every rewrite rule applied before a query reaches psycopg2:
  - qmark -> format paramstyle  (? -> %s)
  - REGEXP operator             (REGEXP -> ~)
  - autoincrement primary key   (INTEGER PRIMARY KEY -> SERIAL PRIMARY KEY)
  - BLOB column type            (BLOB -> BYTEA)
  - two-arg LIMIT               (LIMIT offset, count -> LIMIT count OFFSET offset)
  - unlimited LIMIT             (LIMIT -1 -> LIMIT ALL)

and the column naming applied by _quote_column().

psycopg2 is stubbed so no real database is required.  gramps core is
required for the import chain; the whole module is skipped cleanly if
it is not present.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_sql_translations -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import os
import sys
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
# Gramps modules (required by the addon's import chain)
#
# -------------------------------------------------------------------------
try:
    import gramps
except ImportError as _err:
    raise unittest.SkipTest("gramps package not available: %s" % _err)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

try:
    from SharedPostgreSQL.sharedpostgresql import Connection, Cursor, SharedPostgreSQL
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)

# The addon imports shareddbapi by bare name, the way Gramps loads addons, so
# reach the base class through the MRO rather than importing it a second time.
SharedDBAPI = SharedPostgreSQL.__bases__[0]


# -------------------------------------------------------------------------
#
# Helpers
#
# -------------------------------------------------------------------------


def _make_connection():
    """Return a (Connection, mock_cursor) pair without touching psycopg2."""
    conn = Connection.__new__(Connection)
    cursor = mock.MagicMock()
    conn._Connection__cursor = cursor
    return conn, cursor


def _translated(sql):
    """Return the SQL string that Connection.execute() would pass to psycopg2."""
    conn, cursor = _make_connection()
    conn.execute(sql)
    return cursor.execute.call_args[0][0]


# -------------------------------------------------------------------------
#
# TestExecuteQmarkParamstyle
#
# -------------------------------------------------------------------------
class TestExecuteQmarkParamstyle(unittest.TestCase):
    """? -> %s substitution."""

    def test_single_placeholder(self):
        self.assertEqual(
            _translated("SELECT * FROM person WHERE gramps_id = ?"),
            "SELECT * FROM person WHERE gramps_id = %s",
        )

    def test_multiple_placeholders(self):
        result = _translated("INSERT INTO t (treeid, a) VALUES (?, ?)")
        self.assertEqual(result.count("%s"), 2)
        self.assertNotIn("?", result)

    def test_no_placeholders_unchanged(self):
        sql = "SELECT * FROM person"
        self.assertEqual(_translated(sql), sql)


# -------------------------------------------------------------------------
#
# TestExecuteRegexpOperator
#
# -------------------------------------------------------------------------
class TestExecuteRegexpOperator(unittest.TestCase):
    """REGEXP -> ~ substitution."""

    def test_regexp_replaced(self):
        result = _translated("SELECT * FROM person WHERE name REGEXP 'foo'")
        self.assertIn(" ~ ", result)
        self.assertNotIn("REGEXP", result)

    def test_no_regexp_unchanged(self):
        sql = "SELECT * FROM person WHERE name = 'foo'"
        self.assertEqual(_translated(sql), sql)


# -------------------------------------------------------------------------
#
# TestExecuteSerialPrimaryKey
#
# -------------------------------------------------------------------------
class TestExecuteSerialPrimaryKey(unittest.TestCase):
    """INTEGER PRIMARY KEY -> SERIAL PRIMARY KEY.

    The trees table relies on the treeid being assigned automatically when a
    new tree is inserted, which in PostgreSQL requires SERIAL.
    """

    def test_trees_table_uses_serial(self):
        result = _translated(
            "CREATE TABLE trees (treeid INTEGER PRIMARY KEY, uuid VARCHAR(32))"
        )
        self.assertIn("treeid SERIAL PRIMARY KEY", result)
        self.assertNotIn("INTEGER PRIMARY KEY", result)

    def test_plain_integer_column_unchanged(self):
        sql = "ALTER TABLE person ADD COLUMN priority INTEGER"
        self.assertEqual(_translated(sql), sql)


# -------------------------------------------------------------------------
#
# TestExecuteBlobType
#
# -------------------------------------------------------------------------
class TestExecuteBlobType(unittest.TestCase):
    """BLOB -> BYTEA substitution."""

    def test_metadata_table_blob_replaced(self):
        result = _translated(
            "CREATE TABLE metadata "
            "(treeid INTEGER, setting VARCHAR(50), json_data TEXT, value BLOB)"
        )
        self.assertIn("BYTEA", result)
        self.assertNotIn("BLOB", result)

    def test_blob_data_column_replaced(self):
        result = _translated(
            "CREATE TABLE person "
            "(treeid INTEGER, handle VARCHAR(50), blob_data BLOB)"
        )
        self.assertIn("blob_data BYTEA", result)

    def test_blob_word_boundary_not_in_identifier(self):
        """BLOB as part of a longer identifier is not replaced."""
        result = _translated("SELECT blobfield FROM person")
        self.assertEqual(result, "SELECT blobfield FROM person")

    def test_multiple_blob_columns_all_replaced(self):
        result = _translated("CREATE TABLE t (a BLOB, b TEXT, c BLOB)")
        self.assertEqual(result.count("BYTEA"), 2)
        self.assertNotIn("BLOB", result)


# -------------------------------------------------------------------------
#
# TestExecuteLimitTranslations
#
# -------------------------------------------------------------------------
class TestExecuteLimitTranslations(unittest.TestCase):
    """LIMIT dialect translations."""

    def test_limit_minus_one_becomes_all(self):
        result = _translated("SELECT * FROM person LIMIT -1")
        self.assertIn("LIMIT ALL", result)
        self.assertNotIn("-1", result)

    def test_limit_offset_comma_count(self):
        result = _translated("SELECT * FROM person LIMIT 5, 10")
        self.assertIn("LIMIT 10 OFFSET 5", result)

    def test_limit_offset_comma_minus_one(self):
        result = _translated("SELECT * FROM person LIMIT 5, -1")
        self.assertIn("LIMIT ALL OFFSET 5", result)

    def test_plain_limit_unchanged(self):
        result = _translated("SELECT * FROM person LIMIT 10")
        self.assertEqual(result, "SELECT * FROM person LIMIT 10")

    def test_limit_with_offset_clause_unchanged(self):
        result = _translated("SELECT * FROM person LIMIT 10 OFFSET 5")
        self.assertEqual(result, "SELECT * FROM person LIMIT 10 OFFSET 5")


# -------------------------------------------------------------------------
#
# TestExecuteLeavesIdentifiersAlone
#
# -------------------------------------------------------------------------
class TestExecuteLeavesIdentifiersAlone(unittest.TestCase):
    """Identifiers are no longer rewritten by blind substring replacement.

    The previous implementation replaced every occurrence of "desc", which
    also corrupted unrelated identifiers.  Column naming is now the job of
    _quote_column(), so execute() must leave identifiers untouched.
    """

    def test_desc_column_not_rewritten(self):
        sql = "SELECT handle FROM media ORDER BY desc_"
        self.assertEqual(_translated(sql), sql)

    def test_description_not_corrupted(self):
        sql = "SELECT description FROM event"
        self.assertEqual(_translated(sql), sql)

    def test_descending_order_not_corrupted(self):
        sql = "SELECT handle FROM person ORDER BY surname desc"
        self.assertEqual(_translated(sql), sql)


# -------------------------------------------------------------------------
#
# TestCursorTranslatesToo
#
# -------------------------------------------------------------------------
class TestCursorTranslatesToo(unittest.TestCase):
    """Cursor.execute applies the same translations as Connection.execute.

    Unlike core dbapi, shareddbapi passes bound parameters to cursor queries
    in order to filter by treeid, so the cursor needs translation as well.
    """

    def test_cursor_translates_placeholders(self):
        cursor_obj = Cursor.__new__(Cursor)
        inner = mock.MagicMock()
        cursor_obj._Cursor__cursor = inner
        cursor_obj.execute("SELECT handle FROM person WHERE treeid = ?", [1])
        self.assertEqual(
            inner.execute.call_args[0][0],
            "SELECT handle FROM person WHERE treeid = %s",
        )


# -------------------------------------------------------------------------
#
# TestSharedPostgreSQLSqlType
#
# -------------------------------------------------------------------------
class TestSharedPostgreSQLSqlType(unittest.TestCase):
    """SharedPostgreSQL._sql_type maps BLOB -> bytea; other types pass through."""

    def setUp(self):
        self.pg = SharedPostgreSQL.__new__(SharedPostgreSQL)

    def test_blob_becomes_bytea(self):
        with mock.patch.object(SharedDBAPI, "_sql_type", return_value="BLOB"):
            self.assertEqual(self.pg._sql_type("blob_field", 0), "bytea")

    def test_text_unchanged(self):
        with mock.patch.object(SharedDBAPI, "_sql_type", return_value="TEXT"):
            self.assertEqual(self.pg._sql_type("text_field", 255), "TEXT")

    def test_integer_unchanged(self):
        with mock.patch.object(SharedDBAPI, "_sql_type", return_value="INTEGER"):
            self.assertEqual(self.pg._sql_type("int_field", 0), "INTEGER")


# -------------------------------------------------------------------------
#
# TestSharedPostgreSQLQuoteColumn
#
# -------------------------------------------------------------------------
class TestSharedPostgreSQLQuoteColumn(unittest.TestCase):
    """SharedPostgreSQL._quote_column returns the physical column names."""

    def setUp(self):
        self.pg = SharedPostgreSQL.__new__(SharedPostgreSQL)

    def test_desc_reserved(self):
        self.assertEqual(self.pg._quote_column("desc"), "desc_")

    def test_description_keeps_legacy_name(self):
        """Existing databases have desc_ription, created by the old rewrite."""
        self.assertEqual(self.pg._quote_column("description"), "desc_ription")

    def test_normal_column_unchanged(self):
        self.assertEqual(self.pg._quote_column("gramps_id"), "gramps_id")

    def test_handle_unchanged(self):
        self.assertEqual(self.pg._quote_column("handle"), "handle")

    def test_change_unchanged(self):
        self.assertEqual(self.pg._quote_column("change"), "change")

    def test_base_class_is_identity(self):
        base = SharedDBAPI.__new__(SharedDBAPI)
        self.assertEqual(base._quote_column("desc"), "desc")


# -------------------------------------------------------------------------
#
# TestSecondaryColumnNaming
#
# -------------------------------------------------------------------------
class TestSecondaryColumnNaming(unittest.TestCase):
    """Every Gramps secondary field maps to the column an existing database has.

    Guards against a rename of the two fields whose physical column names were
    fixed by the previous substring rewrite.
    """

    def setUp(self):
        self.pg = SharedPostgreSQL.__new__(SharedPostgreSQL)

    def test_media_desc_field(self):
        from gramps.gen.lib import Media

        fields = [field[0] for field in Media.get_secondary_fields()]
        self.assertIn("desc", fields)
        self.assertEqual(self.pg._quote_column("desc"), "desc_")

    def test_event_description_field(self):
        from gramps.gen.lib import Event

        fields = [field[0] for field in Event.get_secondary_fields()]
        self.assertIn("description", fields)
        self.assertEqual(self.pg._quote_column("description"), "desc_ription")

    def test_no_other_field_needs_renaming(self):
        """Only desc and description were affected by the old rewrite."""
        from gramps.gen.lib import (
            Citation,
            Event,
            Family,
            Media,
            Note,
            Person,
            Place,
            Repository,
            Source,
            Tag,
        )

        affected = set()
        for cls in (
            Person,
            Family,
            Event,
            Place,
            Repository,
            Source,
            Citation,
            Media,
            Note,
            Tag,
        ):
            for field, _type, _length in cls.get_secondary_fields():
                if "desc" in field:
                    affected.add(field)
        self.assertEqual(affected, {"desc", "description"})


if __name__ == "__main__":
    unittest.main()
