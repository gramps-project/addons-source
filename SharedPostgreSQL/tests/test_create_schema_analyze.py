#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Douglas S. Blank <doug.blank@gmail.com>
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
Unit tests for the per-tree-table analyze threshold set in _create_schema().

On a shared database every tree's rows live in the same tables, so
autovacuum's default analyze threshold -- a fixed count plus a fraction of
the *whole* table's row count -- is sized against all trees combined.
_create_schema() sets a fixed, table-size-independent
autovacuum_analyze_threshold (and disables the scale factor) on each
per-tree table so autovacuum notices and re-analyzes after any one tree's
typical-sized batch of changes.

This only checks that _create_schema() issues the expected ALTER TABLE
statements for the expected tables, using the module's own constants --
not that autovacuum actually acts on them. Whether autovacuum picks up a
storage parameter and reanalyzes on schedule is PostgreSQL server behavior,
not addon logic; it isn't something a unit test can honestly assert without
a live server, and was verified manually against a real PostgreSQL 16
instance (see the pull request this test accompanies).

psycopg2 is stubbed so no real database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_create_schema_analyze -v
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
    from SharedPostgreSQL.sharedpostgresql import SharedPostgreSQL
    from SharedPostgreSQL.shareddbapi import (
        SHARED_TABLE_ANALYZE_SCALE_FACTOR,
        SHARED_TABLE_ANALYZE_THRESHOLD,
    )
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)

# The addon imports shareddbapi by bare name, the way Gramps loads addons, so
# reach the base class through the MRO rather than importing it a second time.
SharedDBAPI = SharedPostgreSQL.__bases__[0]

PER_TREE_TABLES = {
    "person",
    "family",
    "source",
    "citation",
    "event",
    "media",
    "place",
    "repository",
    "note",
    "tag",
    "reference",
    "name_group",
    "metadata",
    "gender_stats",
}


def _make_dbapi_instance():
    """A SharedDBAPI instance with every collaborator of _create_schema
    mocked out, so only the code under test runs."""
    db = SharedDBAPI.__new__(SharedDBAPI)
    db.dbapi = mock.MagicMock()
    db._create_secondary_columns = mock.MagicMock()
    db._quote_column = lambda name: name
    return db


class TestCreateSchemaAnalyzeThresholds(unittest.TestCase):
    def _executed_alter_table_sql(self, db):
        return [
            call.args[0]
            for call in db.dbapi.execute.call_args_list
            if call.args[0].startswith("ALTER TABLE")
        ]

    def test_sets_threshold_on_every_per_tree_table(self):
        db = _make_dbapi_instance()
        db._create_schema(json_data=True)

        altered_tables = set()
        for sql in self._executed_alter_table_sql(db):
            table = sql.split()[2]
            altered_tables.add(table)
            self.assertIn(
                f"autovacuum_analyze_scale_factor = {SHARED_TABLE_ANALYZE_SCALE_FACTOR}",
                sql,
            )
            self.assertIn(
                f"autovacuum_analyze_threshold = {SHARED_TABLE_ANALYZE_THRESHOLD}",
                sql,
            )

        self.assertEqual(altered_tables, PER_TREE_TABLES)

    def test_alters_after_creating_the_table(self):
        db = _make_dbapi_instance()
        db._create_schema(json_data=True)

        statements = [call.args[0] for call in db.dbapi.execute.call_args_list]
        for sql in self._executed_alter_table_sql(db):
            table = sql.split()[2]
            create_stmt_index = next(
                i
                for i, s in enumerate(statements)
                if s.startswith(f"CREATE TABLE {table} ")
            )
            alter_stmt_index = statements.index(sql)
            self.assertLess(create_stmt_index, alter_stmt_index)


if __name__ == "__main__":
    unittest.main()
