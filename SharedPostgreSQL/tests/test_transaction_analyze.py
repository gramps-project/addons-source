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
Unit tests for the post-batch-commit ANALYZE fix.

On a shared database every tree's rows live in the same tables, so
autovacuum's analyze threshold is sized against *all* trees' rows combined.
A batch transaction (an import, or a bulk tool such as "Check and Repair")
can write a large number of rows for one tree without ever crossing that
threshold, leaving the planner working from stale statistics for the data
just written -- see the discussion this fixes for the failure mode.

These tests cover:
  - _get_txn_tables() mapping a transaction's touched object types to table
    names, including the REFERENCE_KEY special case
  - _analyze_tables() issuing one ANALYZE per table
  - transaction_commit() calling _analyze_tables() for a batch transaction
  - transaction_commit() NOT calling it for a normal (non-batch) transaction

psycopg2 is stubbed so no real database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_transaction_analyze -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import os
import sys
import unittest
from collections import defaultdict
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
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)

from gramps.gen.db.dbconst import (
    CITATION_KEY,
    FAMILY_KEY,
    PERSON_KEY,
    REFERENCE_KEY,
    TXNADD,
    TXNDEL,
    TXNUPD,
)

# The addon imports shareddbapi by bare name, the way Gramps loads addons, so
# reach the base class through the MRO rather than importing it a second time.
SharedDBAPI = SharedPostgreSQL.__bases__[0]


# -------------------------------------------------------------------------
#
# Helpers
#
# -------------------------------------------------------------------------


class _FakeTxn(defaultdict):
    """
    Minimal stand-in for a gramps.gen.db.txn.DbTxn: a defaultdict(list) keyed
    by (obj_type, trans_type) -> [(handle, data), ...] -- missing keys read as
    [], same as the real class -- plus the attributes transaction_commit()
    reads.
    """

    def __init__(self, batch, initial=None):
        super().__init__(list)
        if initial:
            self.update(initial)
        self.batch = batch

    def get_description(self):
        return "Test transaction"


def _make_dbapi_instance():
    """A SharedDBAPI instance with every collaborator of transaction_commit
    mocked out, so only the code under test runs."""
    db = SharedDBAPI.__new__(SharedDBAPI)
    db.dbapi = mock.MagicMock()
    db.undodb = mock.MagicMock()
    db.reindex_reference_map = mock.MagicMock()
    db.emit = mock.MagicMock()
    db._after_commit = mock.MagicMock()
    db.transaction = mock.MagicMock()
    db.has_changed = 0
    return db


# -------------------------------------------------------------------------
#
# TestGetTxnTables
#
# -------------------------------------------------------------------------
class TestGetTxnTables(unittest.TestCase):
    def test_maps_object_types_to_table_names(self):
        db = _make_dbapi_instance()
        txn = _FakeTxn(
            True,
            {
                (PERSON_KEY, TXNADD): [("h1", None)],
                (FAMILY_KEY, TXNUPD): [("h2", None)],
            },
        )
        self.assertEqual(db._get_txn_tables(txn), {"person", "family"})

    def test_reference_key_maps_to_reference_table(self):
        db = _make_dbapi_instance()
        txn = _FakeTxn(True, {(REFERENCE_KEY, TXNADD): [("h1", None)]})
        self.assertEqual(db._get_txn_tables(txn), {"reference"})

    def test_multiple_trans_types_same_table_deduplicated(self):
        db = _make_dbapi_instance()
        txn = _FakeTxn(
            True,
            {
                (CITATION_KEY, TXNADD): [("h1", None)],
                (CITATION_KEY, TXNDEL): [("h2", None)],
            },
        )
        self.assertEqual(db._get_txn_tables(txn), {"citation"})

    def test_empty_transaction_yields_no_tables(self):
        db = _make_dbapi_instance()
        self.assertEqual(db._get_txn_tables(_FakeTxn(True)), set())


# -------------------------------------------------------------------------
#
# TestAnalyzeTables
#
# -------------------------------------------------------------------------
class TestAnalyzeTables(unittest.TestCase):
    def test_issues_one_analyze_per_table(self):
        db = _make_dbapi_instance()
        db._analyze_tables({"person", "family"})
        executed = {call.args[0] for call in db.dbapi.execute.call_args_list}
        self.assertEqual(executed, {"ANALYZE person", "ANALYZE family"})

    def test_no_tables_no_calls(self):
        db = _make_dbapi_instance()
        db._analyze_tables(set())
        db.dbapi.execute.assert_not_called()


# -------------------------------------------------------------------------
#
# TestTransactionCommitAnalyzesOnlyForBatch
#
# -------------------------------------------------------------------------
class TestTransactionCommitAnalyzesOnlyForBatch(unittest.TestCase):
    def test_batch_commit_analyzes_touched_tables(self):
        db = _make_dbapi_instance()
        txn = _FakeTxn(True, {(PERSON_KEY, TXNADD): [("h1", None)]})
        db.transaction_commit(txn)
        db.dbapi.execute.assert_called_once_with("ANALYZE person")

    def test_non_batch_commit_does_not_analyze(self):
        db = _make_dbapi_instance()
        txn = _FakeTxn(False, {(PERSON_KEY, TXNADD): [("h1", None)]})
        db.transaction_commit(txn)
        db.dbapi.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
