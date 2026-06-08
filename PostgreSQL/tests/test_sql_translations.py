#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015-2016 Douglas S. Blank <doug.blank@gmail.com>
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
Unit tests for the PostgreSQL SQL dialect translations in Connection.execute().

These tests cover every rewrite rule applied before a query reaches psycopg2:
  - qmark → format paramstyle  (? → %s)
  - REGEXP operator             (REGEXP → ~)
  - two-arg LIMIT               (LIMIT offset, count → LIMIT count OFFSET offset)
  - unlimited LIMIT             (LIMIT -1 → LIMIT ALL)

psycopg2 is stubbed so no real database is required.  gramps core is
required for the import chain; the whole module is skipped cleanly if
it is not present.

Run with::

    python3 -m unittest PostgreSQL.tests.test_sql_translations -v
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
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(
        os.path.dirname(gramps.__file__)
    )

try:
    from PostgreSQL.postgresql import Connection, PostgreSQL
except Exception as _err:
    raise unittest.SkipTest("PostgreSQL module unavailable: %s" % _err)


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
    """? → %s substitution."""

    def test_single_placeholder(self):
        self.assertEqual(
            _translated("SELECT * FROM person WHERE gramps_id = ?"),
            "SELECT * FROM person WHERE gramps_id = %s",
        )

    def test_multiple_placeholders(self):
        result = _translated("INSERT INTO t (a, b) VALUES (?, ?)")
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
    """REGEXP → ~ substitution."""

    def test_regexp_replaced(self):
        result = _translated("SELECT * FROM person WHERE name REGEXP 'foo'")
        self.assertIn(" ~ ", result)
        self.assertNotIn("REGEXP", result)

    def test_no_regexp_unchanged(self):
        sql = "SELECT * FROM person WHERE name = 'foo'"
        self.assertEqual(_translated(sql), sql)


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
# TestPostgreSQLSqlType
#
# -------------------------------------------------------------------------
class TestPostgreSQLSqlType(unittest.TestCase):
    """PostgreSQL._sql_type maps BLOB → bytea; other types pass through."""

    def setUp(self):
        self.pg = PostgreSQL.__new__(PostgreSQL)

    def test_blob_becomes_bytea(self):
        with mock.patch.object(
            PostgreSQL.__bases__[0], "_sql_type", return_value="BLOB"
        ):
            self.assertEqual(self.pg._sql_type("blob_field", 0), "bytea")

    def test_text_unchanged(self):
        with mock.patch.object(
            PostgreSQL.__bases__[0], "_sql_type", return_value="TEXT"
        ):
            self.assertEqual(self.pg._sql_type("text_field", 255), "TEXT")

    def test_integer_unchanged(self):
        with mock.patch.object(
            PostgreSQL.__bases__[0], "_sql_type", return_value="INTEGER"
        ):
            self.assertEqual(self.pg._sql_type("int_field", 0), "INTEGER")


# -------------------------------------------------------------------------
#
# TestPostgreSQLQuoteColumn
#
# -------------------------------------------------------------------------
class TestPostgreSQLQuoteColumn(unittest.TestCase):
    """PostgreSQL._quote_column appends _ to reserved words only."""

    def setUp(self):
        self.pg = PostgreSQL.__new__(PostgreSQL)

    def test_desc_reserved(self):
        self.assertEqual(self.pg._quote_column("desc"), "desc_")

    def test_order_reserved(self):
        self.assertEqual(self.pg._quote_column("order"), "order_")

    def test_where_reserved(self):
        self.assertEqual(self.pg._quote_column("where"), "where_")

    def test_select_reserved(self):
        self.assertEqual(self.pg._quote_column("select"), "select_")

    def test_normal_column_unchanged(self):
        self.assertEqual(self.pg._quote_column("gramps_id"), "gramps_id")

    def test_handle_unchanged(self):
        self.assertEqual(self.pg._quote_column("handle"), "handle")

    def test_change_unchanged(self):
        self.assertEqual(self.pg._quote_column("change"), "change")


if __name__ == "__main__":
    unittest.main()
