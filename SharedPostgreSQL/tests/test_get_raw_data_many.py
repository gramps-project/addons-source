#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Doug Blank
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
Unit tests for SharedDBAPI._get_raw_data_many().

The shared database holds the objects of every tree, so reading many objects
at once must only return those of the open tree, like _get_raw_data() does.

The statement is run against an in-memory SQLite table with the same columns
as the shared tables, which understands the same ``?`` placeholders the addon
writes before translating them for PostgreSQL. psycopg2 is stubbed so no
real database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_get_raw_data_many -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import json
import os
import sqlite3
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

from gramps.gen.db.dbconst import FAMILY_KEY, PERSON_KEY
from gramps.gen.lib.serialize import JSONSerializer

try:
    from SharedPostgreSQL.sharedpostgresql import SharedPostgreSQL
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)

# The addon imports shareddbapi by bare name, the way Gramps loads addons, so
# reach the base class and its module through the MRO.
SharedDBAPI = SharedPostgreSQL.__bases__[0]
shareddbapi = sys.modules[SharedDBAPI.__module__]

TREE = "tree-a"
OTHER_TREE = "tree-b"


class _FakeDbapi:
    """The part of the addon's Connection that _get_raw_data_many() uses,
    backed by SQLite, counting the statements it runs."""

    def __init__(self, treeid):
        self.treeid = treeid
        self.statements = []
        self._conn = sqlite3.connect(":memory:")
        self._cursor = self._conn.cursor()
        for table in ("person", "family"):
            self._conn.execute(
                f"CREATE TABLE {table} (treeid TEXT, handle TEXT, json_data TEXT, "
                "PRIMARY KEY (treeid, handle))"
            )

    def add(self, table, treeid, handle, gramps_id):
        data = {"_class": table.capitalize(), "handle": handle, "gramps_id": gramps_id}
        self._conn.execute(
            f"INSERT INTO {table} VALUES (?, ?, ?)",
            [treeid, handle, json.dumps(data)],
        )

    def execute(self, sql, args=None):
        self.statements.append(sql)
        self._cursor.execute(sql, args or [])

    def fetchall(self):
        return self._cursor.fetchall()


def _make_db(treeid=TREE):
    db = SharedDBAPI.__new__(SharedDBAPI)
    db.dbapi = _FakeDbapi(treeid)
    db.serializer = JSONSerializer()
    return db


def _ids(results):
    """{handle: gramps_id} of the yielded (handle, raw data) pairs."""
    return {handle: data["gramps_id"] for handle, data in results}


class TestGetRawDataMany(unittest.TestCase):
    def test_reads_objects_of_the_open_tree(self):
        db = _make_db()
        db.dbapi.add("person", TREE, "H1", "I1")
        db.dbapi.add("person", TREE, "H2", "I2")
        self.assertEqual(
            _ids(db._get_raw_data_many(PERSON_KEY, ["H1", "H2"])),
            {"H1": "I1", "H2": "I2"},
        )

    def test_leaves_out_objects_of_other_trees(self):
        db = _make_db()
        db.dbapi.add("person", TREE, "H1", "I1")
        # the same handle in another tree, and one only in another tree
        db.dbapi.add("person", OTHER_TREE, "H1", "OTHER")
        db.dbapi.add("person", OTHER_TREE, "H2", "I2")
        self.assertEqual(
            _ids(db._get_raw_data_many(PERSON_KEY, ["H1", "H2"])), {"H1": "I1"}
        )

    def test_leaves_out_missing_handles_and_reads_duplicates_once(self):
        db = _make_db()
        db.dbapi.add("person", TREE, "H1", "I1")
        results = list(db._get_raw_data_many(PERSON_KEY, ["H1", "MISSING", "H1"]))
        self.assertEqual(_ids(results), {"H1": "I1"})
        self.assertEqual(len(results), 1)

    def test_reads_the_table_of_the_object_type(self):
        db = _make_db()
        db.dbapi.add("person", TREE, "H1", "I1")
        db.dbapi.add("family", TREE, "H1", "F1")
        self.assertEqual(_ids(db._get_raw_data_many(FAMILY_KEY, ["H1"])), {"H1": "F1"})

    def test_no_handles_runs_no_query(self):
        db = _make_db()
        self.assertEqual(list(db._get_raw_data_many(PERSON_KEY, [])), [])
        self.assertEqual(db.dbapi.statements, [])

    def test_reads_a_batch_per_query(self):
        db = _make_db()
        handles = [f"H{i}" for i in range(7)]
        for i, handle in enumerate(handles):
            db.dbapi.add("person", TREE, handle, f"I{i}")
        with mock.patch.object(shareddbapi, "RAW_DATA_BATCH_SIZE", 3):
            results = _ids(db._get_raw_data_many(PERSON_KEY, iter(handles)))
        self.assertEqual(results, {h: f"I{i}" for i, h in enumerate(handles)})
        self.assertEqual(len(db.dbapi.statements), 3)

    def test_caller_may_query_between_yields(self):
        db = _make_db()
        for i in range(3):
            db.dbapi.add("person", TREE, f"H{i}", f"I{i}")
        seen = []
        for handle, _data in db._get_raw_data_many(PERSON_KEY, ["H0", "H1", "H2"]):
            seen.append(handle)
            # another statement on the same cursor must not cut the batch short
            db.dbapi.execute("SELECT 1")
        self.assertEqual(sorted(seen), ["H0", "H1", "H2"])


if __name__ == "__main__":
    unittest.main()
