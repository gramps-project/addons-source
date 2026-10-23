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
Unit tests for the ANALYZE that a batch transaction runs on tables it inserts
into (SharedDBAPI._count_batch_insert()).

A batch transaction (an import, a bulk tool) is a single transaction, so
until it commits the planner has no statistics for a new tree's rows and
serves handle lookups from the wrong index. Analyzing at a few row-count
milestones inside the transaction fixes the plan; that PostgreSQL then
picks the primary key is server behavior, verified manually against a real
PostgreSQL 16 instance (see the pull request this test accompanies). This
only checks when the addon issues ANALYZE.

psycopg2 is stubbed so no real database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_batch_analyze -v
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
        BATCH_ANALYZE_AT_ROWS,
    )
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)

# The addon imports shareddbapi by bare name, the way Gramps loads addons, so
# reach the base class through the MRO rather than importing it directly.
SharedDBAPI = SharedPostgreSQL.__bases__[0]


def _make_dbapi_instance():
    """A SharedDBAPI instance inside a batch transaction, with the DB-API
    connection mocked out."""
    db = SharedDBAPI.__new__(SharedDBAPI)
    db.dbapi = mock.MagicMock()
    db.transaction = None
    db.transaction_begin(mock.MagicMock(batch=True))
    db.dbapi.reset_mock()
    return db


def _analyzed(db):
    return [
        call.args[0]
        for call in db.dbapi.execute.call_args_list
        if call.args[0].startswith("ANALYZE")
    ]


class TestBatchAnalyze(unittest.TestCase):
    def test_analyzes_at_each_milestone_only(self):
        db = _make_dbapi_instance()
        for count in range(1, BATCH_ANALYZE_AT_ROWS[-1] + 2):
            db._count_batch_insert("person")
            expected = [c for c in BATCH_ANALYZE_AT_ROWS if c <= count]
            self.assertEqual(len(_analyzed(db)), len(expected))
        self.assertEqual(set(_analyzed(db)), {"ANALYZE person"})

    def test_counts_each_table_separately(self):
        db = _make_dbapi_instance()
        for _ in range(BATCH_ANALYZE_AT_ROWS[0]):
            db._count_batch_insert("person")
        for _ in range(BATCH_ANALYZE_AT_ROWS[0] - 1):
            db._count_batch_insert("event")
        self.assertEqual(_analyzed(db), ["ANALYZE person"])

    def test_counts_restart_with_each_transaction(self):
        db = _make_dbapi_instance()
        for _ in range(BATCH_ANALYZE_AT_ROWS[0] - 1):
            db._count_batch_insert("person")
        db.transaction_begin(mock.MagicMock(batch=True))
        db._count_batch_insert("person")
        self.assertEqual(_analyzed(db), [])


if __name__ == "__main__":
    unittest.main()
