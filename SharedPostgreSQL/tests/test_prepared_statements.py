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
Unit tests for Connection.execute_prepared() and the generic-plan session
setting it relies on.

Lookups by treeid plus a per-tree key run as prepared statements with a
generic plan, so a tree that the planner's statistics don't know yet (one
being imported) still gets the index on the whole key instead of a
(treeid, <other column>) index plus a filter. That PostgreSQL then picks
that index is server behavior, verified manually against a real
PostgreSQL 16 instance (see the pull request this test accompanies). These
tests only check the SQL the addon sends.

psycopg2 is stubbed so no real database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_prepared_statements -v
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
    from SharedPostgreSQL.sharedpostgresql import Connection
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)


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
    conn._Connection__prepared = {}
    return conn, cursor


def _sent(cursor):
    return [call.args for call in cursor.execute.call_args_list]


LOOKUP = "SELECT 1 FROM person WHERE handle = ? AND treeid = ?"


class TestExecutePrepared(unittest.TestCase):
    def test_first_call_prepares_then_executes(self):
        conn, cursor = _make_connection()
        conn.execute_prepared(LOOKUP, ["h1", 4])
        self.assertEqual(
            _sent(cursor),
            [
                (
                    "PREPARE gramps_stmt_0 AS "
                    "SELECT 1 FROM person WHERE handle = $1 AND treeid = $2",
                    None,
                ),
                ("EXECUTE gramps_stmt_0 (%s, %s)", ["h1", 4]),
            ],
        )

    def test_later_calls_only_execute(self):
        conn, cursor = _make_connection()
        conn.execute_prepared(LOOKUP, ["h1", 4])
        cursor.reset_mock()
        conn.execute_prepared(LOOKUP, ["h2", 4])
        self.assertEqual(_sent(cursor), [("EXECUTE gramps_stmt_0 (%s, %s)", ["h2", 4])])

    def test_each_query_gets_its_own_statement(self):
        conn, cursor = _make_connection()
        conn.execute_prepared(LOOKUP, ["h1", 4])
        conn.execute_prepared(
            "UPDATE person SET json_data = ? WHERE handle = ? AND treeid = ?",
            ["{}", "h1", 4],
        )
        self.assertEqual(
            _sent(cursor)[2],
            (
                "PREPARE gramps_stmt_1 AS "
                "UPDATE person SET json_data = $1 WHERE handle = $2 AND treeid = $3",
                None,
            ),
        )

    def test_failed_prepare_is_retried(self):
        conn, cursor = _make_connection()
        cursor.execute.side_effect = [RuntimeError("boom"), None]
        with self.assertRaises(RuntimeError):
            conn.execute_prepared(LOOKUP, ["h1", 4])
        cursor.reset_mock(side_effect=True)
        conn.execute_prepared(LOOKUP, ["h1", 4])
        self.assertTrue(_sent(cursor)[0][0].startswith("PREPARE gramps_stmt_0 AS"))


class TestGenericPlanSession(unittest.TestCase):
    def test_connect_forces_generic_plans(self):
        with mock.patch.object(Connection, "check_collation"):
            conn = Connection(uuid="u")
        cursor = conn._Connection__cursor
        cursor.execute.assert_any_call("SET plan_cache_mode = force_generic_plan")


if __name__ == "__main__":
    unittest.main()
