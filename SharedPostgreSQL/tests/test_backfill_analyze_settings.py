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
Unit tests for SharedPostgreSQL._backfill_analyze_settings().

_create_schema() sets a fixed autovacuum analyze threshold on every
per-tree table of a new database. A database created before that has none,
so the addon adds whatever is missing the first time a process connects to
it. These tests cover:

  - a table with neither setting gets both, each table in its own
    transaction with a lock timeout
  - a table that already has the settings is left alone
  - a value an operator chose for one setting is kept
  - a failure (checking or altering) never stops the database opening, and
    one table failing doesn't stop the others
  - _initialize() runs the check once per database per process
  - PER_TREE_TABLES matches the tables _create_schema() creates

Whether autovacuum then acts on the settings is PostgreSQL server
behavior; see the pull request for that verification. psycopg2 is stubbed
so no database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_backfill_analyze_settings -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import os
import shutil
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
    from gramps.gen.utils.configmanager import ConfigManager

    from SharedPostgreSQL import sharedpostgresql
    from SharedPostgreSQL.sharedpostgresql import SharedPostgreSQL
    from SharedPostgreSQL.shareddbapi import (
        PER_TREE_TABLES,
        SHARED_TABLE_ANALYZE_SCALE_FACTOR,
        SHARED_TABLE_ANALYZE_THRESHOLD,
    )
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)

# The addon imports shareddbapi by bare name, the way Gramps loads addons, so
# reach the base class through the MRO rather than importing it directly.
SharedDBAPI = SharedPostgreSQL.__bases__[0]

SCALE = "autovacuum_analyze_scale_factor"
THRESHOLD = "autovacuum_analyze_threshold"
BOTH_SET = [
    "%s=%s" % (SCALE, SHARED_TABLE_ANALYZE_SCALE_FACTOR),
    "%s=%s" % (THRESHOLD, SHARED_TABLE_ANALYZE_THRESHOLD),
]


def _make_db(rows):
    """A SharedPostgreSQL whose connection reports `rows` -- (table,
    reloptions) pairs -- for the settings check."""
    db = SharedPostgreSQL.__new__(SharedPostgreSQL)
    db.dbapi = mock.MagicMock()
    db.dbapi.fetchall.return_value = rows
    return db


def _calls(db):
    """Every call on the connection, as (method, sql-or-None)."""
    result = []
    for call in db.dbapi.method_calls:
        name = call[0]
        if name in ("begin", "commit", "rollback"):
            result.append((name, None))
        elif name == "execute":
            result.append((name, call.args[0]))
    return result


def _alters(db):
    return [sql for name, sql in _calls(db) if sql and sql.startswith("ALTER")]


# -------------------------------------------------------------------------
#
# TestBackfill
#
# -------------------------------------------------------------------------
class TestBackfill(unittest.TestCase):
    def test_table_without_settings_gets_both(self):
        db = _make_db([("event", None)])
        db._backfill_analyze_settings()
        self.assertEqual(
            _alters(db),
            [
                "ALTER TABLE event SET (%s = %s, %s = %s)"
                % (
                    SCALE,
                    SHARED_TABLE_ANALYZE_SCALE_FACTOR,
                    THRESHOLD,
                    SHARED_TABLE_ANALYZE_THRESHOLD,
                )
            ],
        )

    def test_each_alter_is_its_own_transaction_with_lock_timeout(self):
        """The lock is held only for that one statement, and opening the
        database doesn't wait long behind a VACUUM on the table."""
        db = _make_db([("event", None), ("person", [])])
        db._backfill_analyze_settings()
        calls = _calls(db)[1:]  # skip the check query
        self.assertEqual(len(calls), 8)
        for start in (0, 4):
            begin, timeout, alter, commit = calls[start : start + 4]
            self.assertEqual(begin, ("begin", None))
            self.assertIn("SET LOCAL lock_timeout", timeout[1])
            self.assertTrue(alter[1].startswith("ALTER TABLE"))
            self.assertEqual(commit, ("commit", None))

    def test_table_with_settings_is_left_alone(self):
        db = _make_db([("event", BOTH_SET), ("person", ["fillfactor=90"] + BOTH_SET)])
        db._backfill_analyze_settings()
        self.assertEqual(_alters(db), [])
        db.dbapi.begin.assert_not_called()

    def test_operator_value_is_kept(self):
        """Only the missing setting is added; a different threshold an
        operator set is not overwritten."""
        db = _make_db([("event", ["%s=250" % THRESHOLD])])
        db._backfill_analyze_settings()
        self.assertEqual(
            _alters(db),
            [
                "ALTER TABLE event SET (%s = %s)"
                % (SCALE, SHARED_TABLE_ANALYZE_SCALE_FACTOR)
            ],
        )

    def test_check_asks_for_every_per_tree_table(self):
        db = _make_db([])
        db._backfill_analyze_settings()
        sql, params = db.dbapi.execute.call_args_list[0].args
        self.assertIn("to_regclass", sql)
        self.assertEqual(params, [list(PER_TREE_TABLES)])

    def test_failed_check_does_not_raise(self):
        db = _make_db([])
        db.dbapi.execute.side_effect = RuntimeError("permission denied")
        with self.assertLogs(sharedpostgresql.LOG, "WARNING"):
            db._backfill_analyze_settings()
        db.dbapi.begin.assert_not_called()

    def test_failed_alter_does_not_raise_or_stop_the_rest(self):
        db = _make_db([("event", None), ("person", None)])

        def execute(sql, *args):
            if sql.startswith("ALTER TABLE event"):
                raise RuntimeError("must be owner of table event")

        db.dbapi.execute.side_effect = execute
        with self.assertLogs(sharedpostgresql.LOG, "WARNING") as logs:
            db._backfill_analyze_settings()
        self.assertIn("must be owner of table event", logs.output[0])
        self.assertEqual(db.dbapi.rollback.call_count, 1)
        self.assertEqual(db.dbapi.commit.call_count, 1)  # person's
        self.assertTrue(
            any(sql.startswith("ALTER TABLE person") for sql in _alters(db))
        )


# -------------------------------------------------------------------------
#
# TestOncePerDatabase
#
# -------------------------------------------------------------------------
class TestOncePerDatabase(unittest.TestCase):
    """gramps-web-api opens the database for every request, so the check
    must not run on every open."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        patcher = mock.patch.object(
            sharedpostgresql, "_ANALYZE_SETTINGS_CHECKED", set()
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(sharedpostgresql, "Connection")
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_settings(self, dbname):
        directory = tempfile.mkdtemp(dir=self.tmpdir)
        config_mgr = ConfigManager(os.path.join(directory, "settings.ini"))
        for key in ("database.dbname", "database.host", "database.port", "tree.uuid"):
            config_mgr.register(key, "")
        config_mgr.set("database.dbname", dbname)
        config_mgr.set("database.host", "localhost")
        config_mgr.set("database.port", "5432")
        config_mgr.set("tree.uuid", "0123456789abcdef")
        config_mgr.save()
        return directory

    def open(self, directory):
        db = SharedPostgreSQL.__new__(SharedPostgreSQL)
        with mock.patch.object(
            SharedPostgreSQL, "_backfill_analyze_settings"
        ) as backfill:
            db._initialize(directory, None, None)
        return backfill.call_count

    def test_runs_once_per_database(self):
        directory = self.write_settings("gramps")
        self.assertEqual(self.open(directory), 1)
        self.assertEqual(self.open(directory), 0)
        # Another tree in the same database shares its tables.
        self.assertEqual(self.open(self.write_settings("gramps")), 0)

    def test_runs_again_for_another_database(self):
        self.assertEqual(self.open(self.write_settings("gramps")), 1)
        self.assertEqual(self.open(self.write_settings("other")), 1)


# -------------------------------------------------------------------------
#
# TestPerTreeTables
#
# -------------------------------------------------------------------------
class TestPerTreeTables(unittest.TestCase):
    def test_matches_create_schema(self):
        """A table added to _create_schema() must be added to
        PER_TREE_TABLES too, or older databases never get its settings."""
        db = SharedDBAPI.__new__(SharedDBAPI)
        db.dbapi = mock.MagicMock()
        db._create_secondary_columns = mock.MagicMock()
        db._quote_column = lambda name: name
        db._create_schema(json_data=True)
        self.assertEqual(set(db._per_tree_tables), set(PER_TREE_TABLES))


if __name__ == "__main__":
    unittest.main()
