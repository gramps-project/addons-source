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
Unit tests for SharedPostgreSQL._create_settings().

Several processes can open a never-before-opened tree at the same time, and
each would generate its own tree UUID.  Initialization is therefore serialized
on a PostgreSQL advisory lock rather than on the filesystem, which may not
order concurrent writes to settings.ini.  These tests cover:

  - the advisory lock key derived from the tree directory
  - the losing process adopting the winner's settings.ini
  - the lock being taken before settings.ini is inspected
  - the connection being closed (releasing the lock) even on failure

The concurrency itself is not exercised here; that needs a real server and
several processes.  psycopg2 is stubbed so no database is required.

Run with::

    python3 -m unittest SharedPostgreSQL.tests.test_initialize -v
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
except Exception as _err:
    raise unittest.SkipTest("SharedPostgreSQL module unavailable: %s" % _err)


# -------------------------------------------------------------------------
#
# Base class
#
# -------------------------------------------------------------------------
class CreateSettingsTestCase(unittest.TestCase):
    """Shared fixture: an empty tree directory and a stubbed connection."""

    def setUp(self):
        self.pg = SharedPostgreSQL.__new__(SharedPostgreSQL)
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.config_file = os.path.join(self.tmpdir, "settings.ini")

    def make_config_mgr(self, config_file=None):
        """A ConfigManager registered the way _initialize() registers it."""
        config_mgr = ConfigManager(config_file or self.config_file)
        config_mgr.register("database.dbname", "")
        config_mgr.register("database.host", "")
        config_mgr.register("database.port", "")
        config_mgr.register("tree.uuid", "")
        return config_mgr

    def create_settings(self, directory=None, config_mgr=None, conn=None):
        """Run _create_settings() against a stubbed psycopg2 connection."""
        directory = directory or self.tmpdir
        config_file = os.path.join(directory, "settings.ini")
        if config_mgr is None:
            config_mgr = self.make_config_mgr(config_file)
        conn = conn if conn is not None else mock.MagicMock()
        with mock.patch.object(
            sharedpostgresql.psycopg2, "connect", return_value=conn
        ) as connect:
            self.pg._create_settings(config_file, config_mgr, directory, None, None)
        return conn, connect

    @staticmethod
    def lock_key(conn):
        """The advisory lock key passed to pg_advisory_lock()."""
        sql, params = conn.cursor.return_value.execute.call_args[0]
        assert "pg_advisory_lock" in sql, sql
        return params[0]

    def stored_uuid(self, config_file=None):
        """Read tree.uuid back from the settings file on disk."""
        config_mgr = self.make_config_mgr(config_file)
        config_mgr.load()
        return config_mgr.get("tree.uuid")


# -------------------------------------------------------------------------
#
# TestAdvisoryLockKey
#
# -------------------------------------------------------------------------
class TestAdvisoryLockKey(CreateSettingsTestCase):
    """The lock key is derived deterministically from the tree directory."""

    def test_same_directory_gives_same_key(self):
        """Racing processes must agree on the key or the lock cannot bind."""
        first, _ = self.create_settings()
        second, _ = self.create_settings()
        self.assertEqual(self.lock_key(first), self.lock_key(second))

    def test_trailing_separator_gives_same_key(self):
        """abspath() normalizes the path, so a trailing slash is harmless."""
        plain, _ = self.create_settings(directory=self.tmpdir)
        slashed, _ = self.create_settings(directory=self.tmpdir + os.sep)
        self.assertEqual(self.lock_key(plain), self.lock_key(slashed))

    def test_different_directories_give_different_keys(self):
        """Unrelated trees must not serialize against each other."""
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        mine, _ = self.create_settings()
        theirs, _ = self.create_settings(directory=other)
        self.assertNotEqual(self.lock_key(mine), self.lock_key(theirs))

    def test_key_fits_signed_64_bit(self):
        """pg_advisory_lock takes a bigint; a wider value is a runtime error."""
        conn, _ = self.create_settings()
        self.assertGreaterEqual(self.lock_key(conn), -(2**63))
        self.assertLess(self.lock_key(conn), 2**63)

    def test_high_bit_digest_yields_negative_key(self):
        """A digest with the top bit set must wrap to a negative bigint.

        Reading the digest unsigned would produce a value above 2**63 that
        PostgreSQL rejects, and only for the fraction of paths whose hash
        happens to have that bit set -- so pin it down explicitly.
        """
        digest = mock.MagicMock()
        digest.digest.return_value = b"\xff" * 32
        with mock.patch.object(
            sharedpostgresql.hashlib, "sha256", return_value=digest
        ):
            conn, _ = self.create_settings()
        self.assertEqual(self.lock_key(conn), -1)


# -------------------------------------------------------------------------
#
# TestCreateSettingsRace
#
# -------------------------------------------------------------------------
class TestCreateSettingsRace(CreateSettingsTestCase):
    """Only the process holding the lock may generate the tree UUID."""

    def test_winner_writes_uuid(self):
        """Baseline: an uncontended call does create the settings file."""
        self.create_settings()
        self.assertTrue(os.path.exists(self.config_file))
        self.assertTrue(self.stored_uuid())

    def test_loser_adopts_winners_uuid(self):
        """A settings file appearing while we block on the lock is kept.

        This is the failure that wedged trees before the lock existed: both
        processes generated a UUID and the second overwrote the first, so the
        data written under the first UUID became unreachable.
        """
        conn = mock.MagicMock()
        conn.cursor.return_value.execute.side_effect = self._win_race
        self.create_settings(conn=conn)
        self.assertEqual(self.stored_uuid(), "winner")

    def test_loser_leaves_file_byte_identical(self):
        """The loser must not rewrite the file at all, not even equivalently."""
        conn = mock.MagicMock()
        conn.cursor.return_value.execute.side_effect = self._win_race
        self.create_settings(conn=conn)
        with open(self.config_file, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), self._WINNER_INI)

    _WINNER_INI = "[database]\ndbname='gramps'\n\n[tree]\nuuid='winner'\n\n"

    def _win_race(self, *args, **kwargs):
        """Simulate another process winning while this one waits for the lock."""
        with open(self.config_file, "w", encoding="utf-8") as fh:
            fh.write(self._WINNER_INI)


# -------------------------------------------------------------------------
#
# TestCreateSettingsLockOrdering
#
# -------------------------------------------------------------------------
class TestCreateSettingsLockOrdering(CreateSettingsTestCase):
    """The lock must be held before settings.ini is inspected."""

    def test_lock_precedes_existence_check(self):
        """Checking first and locking second would reopen the race window."""
        events = []
        real_exists = os.path.exists

        def recording_exists(path):
            if path == self.config_file:
                events.append("exists")
            return real_exists(path)

        conn = mock.MagicMock()
        conn.cursor.return_value.execute.side_effect = lambda *a, **k: events.append(
            "lock"
        )
        with mock.patch("os.path.exists", recording_exists):
            self.create_settings(conn=conn)

        self.assertEqual(events, ["lock", "exists"])


# -------------------------------------------------------------------------
#
# TestCreateSettingsLockRelease
#
# -------------------------------------------------------------------------
class TestCreateSettingsLockRelease(CreateSettingsTestCase):
    """The lock is released by closing the session, so close() must always run.

    There is no explicit pg_advisory_unlock; a session level lock is dropped
    when the connection ends.  A leaked connection would therefore block every
    other process opening the same tree.
    """

    def test_connection_closed_on_success(self):
        conn, _ = self.create_settings()
        conn.close.assert_called_once_with()

    def test_connection_closed_when_save_fails(self):
        config_mgr = mock.MagicMock()
        config_mgr.save.side_effect = RuntimeError("read-only filesystem")
        conn = mock.MagicMock()
        with self.assertRaises(RuntimeError):
            self.create_settings(config_mgr=config_mgr, conn=conn)
        conn.close.assert_called_once_with()

    def test_connection_closed_when_lock_fails(self):
        conn = mock.MagicMock()
        conn.cursor.return_value.execute.side_effect = RuntimeError("lock timeout")
        with self.assertRaises(RuntimeError):
            self.create_settings(conn=conn)
        conn.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
