#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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

"""Integration tests for the Import and Merge tool.

These tests exercise ``ImportMerge.do_commits`` against a real Gramps SQLite
database.  We call the method unbound with a stub ``self`` so the GUI
(ManagedWindow + Gtk dialog) doesn't need to be instantiated — the data-path
logic is what we're verifying.

Regression coverage:

* Gramps bug 0014056 — Adding a Tag via the Import Merge tool raised
  ``AttributeError: 'SQLite' object has no attribute 'has_tag_gramps_id'``
  because Tag is a table object and has no gramps_id.
"""

# ------------------------
# Python modules
# ------------------------
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

# The ImportMerge module imports Gtk at module load — skip the whole file if
# gi/Gtk aren't available (headless-without-GTK environments). On systems
# where both GTK3 and GTK4 are present, pin Gtk to 3.0 before any gramps
# import (mirrors what gramps.grampsapp does at startup); otherwise
# PyGObject loads GTK4 and the gramps.gui import chain crashes on
# Gtk.IconSize.MENU (a GTK3-only enum).
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError, AttributeError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# ------------------------
# Gramps modules
# ------------------------
from gramps.gen.db import DbTxn
from gramps.gen.db.base import DbReadBase
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Tag

# ------------------------
# Gramps specific
# ------------------------
from ImportMerge.importmerge import ImportMerge, S_ADD, S_DIFFERS, A_ADD


def _make_db(suffix: str) -> tuple[DbReadBase, str]:
    """Create a fresh on-disk Gramps SQLite DB inside a temp directory.

    :param suffix: Short label used in the temp-directory prefix.
    :returns: A ``(db, tmpdir)`` tuple — the caller owns ``tmpdir`` and must
        remove it.
    """
    tmpdir = tempfile.mkdtemp(prefix="gramps_test_%s_" % suffix)
    db_path = os.path.join(tmpdir, "db_%s" % suffix)
    os.makedirs(db_path)
    db = make_database("sqlite")
    db.load(db_path, None)
    return db, tmpdir


def _add_tag(db: DbReadBase, name: str) -> str:
    """Add a Tag to ``db`` and return its handle.

    :param db: The database to add the tag to.
    :param name: The tag name.
    :returns: The handle of the newly-created tag.
    """
    tag = Tag()
    tag.set_name(name)
    with DbTxn("add tag", db, batch=True) as trans:
        handle = db.add_tag(tag, trans)
    return handle


# ------------------------------------------------------------
#
# ImportMergeTagTestCase
#
# ------------------------------------------------------------
class ImportMergeTagTestCase(unittest.TestCase):
    """Regression tests for bug 0014056 (Tag handling in do_commits)."""

    def setUp(self) -> None:
        self.db1, self.tmp1 = _make_db("db1")
        self.db2, self.tmp2 = _make_db("db2")

    def tearDown(self) -> None:
        for db in (self.db1, self.db2):
            try:
                db.close()
            except Exception:
                pass
        shutil.rmtree(self.tmp1, ignore_errors=True)
        shutil.rmtree(self.tmp2, ignore_errors=True)

    def _make_stub(self) -> SimpleNamespace:
        """Stub ``self`` for ``ImportMerge.do_commits`` — no GUI attributes."""
        return SimpleNamespace(
            db1=self.db1,
            db2=self.db2,
            added={},
            missing={},
            diffs={},
        )

    def test_add_tag_does_not_crash(self) -> None:
        """Regression for bug 0014056 — adding a Tag via do_commits must succeed.

        Before the fix, this raised ``AttributeError: 'SQLite' object has no
        attribute 'has_tag_gramps_id'`` because the generic GID-conflict check
        didn't special-case Tag (a table object without a gramps_id field).
        """
        tag_handle = _add_tag(self.db2, "Imported")
        stub = self._make_stub()

        with DbTxn("import merge", self.db1, batch=True) as trans:
            ImportMerge.do_commits(stub, S_ADD, "Tag", tag_handle, A_ADD, trans)

        self.assertEqual(self.db1.get_number_of_tags(), 1)
        committed = self.db1.get_tag_from_handle(tag_handle)
        self.assertIsNotNone(committed)
        self.assertEqual(committed.get_name(), "Imported")

    def test_differing_tag_does_not_crash(self) -> None:
        """S_DIFFERS branch must also skip the gramps_id check for Tag.

        Same root cause as the S_ADD path: the GID-conflict block at the end
        of the S_DIFFERS branch dereferences ``item.gramps_id`` and calls
        ``has_tag_gramps_id`` — both fail for Tag objects.
        """
        tag_handle = _add_tag(self.db1, "Original")
        tag2 = Tag()
        tag2.set_handle(tag_handle)
        tag2.set_name("Modified")
        with DbTxn("seed db2", self.db2, batch=True) as trans:
            self.db2.add_tag(tag2, trans)

        stub = self._make_stub()

        def fake_diff_result(
            action: int, obj_type: str, hndl: str
        ) -> tuple[Tag | None, Tag | None, Tag | None]:
            item1 = self.db1.get_tag_from_handle(hndl)
            item2 = self.db2.get_tag_from_handle(hndl)
            return item1, item2, item2

        stub.diff_result = fake_diff_result
        stub.check_diffs = lambda *a, **kw: False
        stub.check_added = lambda *a, **kw: False
        stub.check_miss = lambda *a, **kw: False

        with DbTxn("import merge", self.db1, batch=True) as trans:
            ImportMerge.do_commits(stub, S_DIFFERS, "Tag", tag_handle, A_ADD, trans)

        committed = self.db1.get_tag_from_handle(tag_handle)
        self.assertIsNotNone(committed)
        self.assertEqual(committed.get_name(), "Modified")


if __name__ == "__main__":
    unittest.main()
