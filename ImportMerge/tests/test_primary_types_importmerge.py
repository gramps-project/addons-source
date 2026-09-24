#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Ian Davis
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

"""Tests for the Import and Merge tool with primary types beyond the core ten.

The DNA test cases run only when ``gramps.gen.lib`` provides ``DNATest`` and
``DNAMatch``, as it does on the dna-core branch.  The remaining cases run on
any Gramps 6.1 build.
"""

# ------------------------
# Python modules
# ------------------------
import os
import shutil
import tempfile
import unittest
from types import MethodType, SimpleNamespace

# ------------------------
# Gramps modules
# ------------------------
import gramps.gen.lib
from gramps.gen.db import DbTxn
from gramps.gen.db.base import DbWriteBase
from gramps.gen.db.dbconst import CLASS_TO_KEY_MAP
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Person

# ------------------------
# Gramps specific
# ------------------------
from ImportMerge import importmerge
from ImportMerge.importmerge import (
    A_ADD,
    A_MERGE_L,
    GID,
    HNDL,
    ImportMerge,
    MySa,
    OBJ_LST,
    S_ADD,
    S_DIFFERS,
    SORT,
)

HAS_DNA = hasattr(gramps.gen.lib, "DNATest") and hasattr(gramps.gen.lib, "DNAMatch")
CORE_TYPES = [
    "Family",
    "Person",
    "Citation",
    "Event",
    "Media",
    "Note",
    "Place",
    "Repository",
    "Source",
    "Tag",
]


def _make_db(suffix: str) -> tuple[DbWriteBase, str]:
    """Create an empty on-disk SQLite database in a new temporary directory.

    :param suffix: Short label used in the temporary directory prefix.
    :returns: A ``(db, tmpdir)`` tuple; the caller removes ``tmpdir``.
    """
    tmpdir = tempfile.mkdtemp(prefix="gramps_test_%s_" % suffix)
    db_path = os.path.join(tmpdir, "db_%s" % suffix)
    os.makedirs(db_path)
    db = make_database("sqlite")
    db.load(db_path, None)
    return db, tmpdir


class _Rows:
    """A stand-in for the ``Gtk.ListStore`` that holds the diff rows."""

    def __init__(self, rows: list[tuple]) -> None:
        self.rows = list(rows)

    def __getitem__(self, index: int) -> tuple:
        return self.rows[index]

    def append(self, row: tuple) -> int:
        """Append a row and return its index as the row iterator."""
        self.rows.append(row)
        return len(self.rows) - 1


# ------------------------------------------------------------
#
# ObjectTypeTestCase
#
# ------------------------------------------------------------
class ObjectTypeTestCase(unittest.TestCase):
    """Tests for the list of compared object types."""

    def test_core_types_keep_their_order(self) -> None:
        """The ten core types lead the list in their original order."""
        self.assertEqual(OBJ_LST[: len(CORE_TYPES)], CORE_TYPES)

    def test_every_database_type_is_compared(self) -> None:
        """Every primary type known to the database is in the list."""
        self.assertLessEqual(set(CLASS_TO_KEY_MAP), set(OBJ_LST))

    def test_type_index_fits_sort_packing(self) -> None:
        """The type index fits the four bits the SORT column holds it in."""
        self.assertLessEqual(len(OBJ_LST), 16)

    def test_signal_names_map_to_types(self) -> None:
        """Each type is found again from the lower-case database signal name."""
        for obj_type in OBJ_LST:
            with self.subTest(obj_type=obj_type):
                self.assertEqual(importmerge.OBJ_BY_SIGNAL[obj_type.lower()], obj_type)


# ------------------------------------------------------------
#
# DatabaseTestCase
#
# ------------------------------------------------------------
class DatabaseTestCase(unittest.TestCase):
    """Base class providing a tree database and an import database."""

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
        """Return a stub ``self`` for unbound ``ImportMerge`` method calls."""
        stub = SimpleNamespace(
            db1=self.db1,
            db2=self.db2,
            sa=[MySa(self.db1), MySa(self.db2)],
            added={},
            missing={},
            diffs={},
        )
        for name in ("diff_result", "check_added", "check_miss", "check_diffs"):
            setattr(stub, name, MethodType(getattr(ImportMerge, name), stub))
        return stub

    def _add_person(self, db: DbWriteBase, gramps_id: str) -> str:
        """Add a Person to ``db`` and return its handle."""
        person = Person()
        person.set_gramps_id(gramps_id)
        with DbTxn("add person", db) as trans:
            return db.add_person(person, trans)


# ------------------------------------------------------------
#
# EditCallbackTestCase
#
# ------------------------------------------------------------
class EditCallbackTestCase(DatabaseTestCase):
    """Tests for rows added when an object in the import is edited."""

    def _run_add(self, signal_name: str, handle: str) -> tuple:
        """Deliver an add signal and return the diff row it appends."""
        stub = self._make_stub()
        stub.diff_list = _Rows([("", "", "", "", 0, "other", "", 0)])
        stub.diff_iter = 0
        ImportMerge.edit_callback(stub, signal_name, "add", [handle])
        self.assertIn(handle, stub.added)
        return stub.diff_list[stub.added[handle]]

    def test_add_person(self) -> None:
        """A new Person in the import is listed as Added."""
        handle = self._add_person(self.db2, "I0001")
        row = self._run_add("person", handle)
        self.assertEqual(row[HNDL], handle)
        self.assertEqual(OBJ_LST[row[SORT] & 15], "Person")

    @unittest.skipUnless(HAS_DNA, "DNA classes not available")
    def test_add_dnatest(self) -> None:
        """A new DNATest in the import is listed as Added with its own type."""
        test = gramps.gen.lib.DNATest()
        test.set_gramps_id("T0001")
        with DbTxn("add test", self.db2) as trans:
            handle = self.db2.add_dnatest(test, trans)
        row = self._run_add("dnatest", handle)
        self.assertEqual(OBJ_LST[row[SORT] & 15], "DNATest")
        self.assertEqual(row[GID], "T0001")


# ------------------------------------------------------------
#
# DNATestCase
#
# ------------------------------------------------------------
@unittest.skipUnless(HAS_DNA, "DNA classes not available")
class DNATestCase(DatabaseTestCase):
    """Tests for DNATest and DNAMatch objects."""

    def _add_test(
        self, db: DbWriteBase, gramps_id: str, account: str, handle: str | None = None
    ) -> str:
        """Add a DNATest to ``db`` and return its handle."""
        test = gramps.gen.lib.DNATest()
        if handle:
            test.set_handle(handle)
        test.set_gramps_id(gramps_id)
        test.set_account_name(account)
        test.set_provider(
            gramps.gen.lib.DNAProviderType(gramps.gen.lib.DNAProviderType.ANCESTRY)
        )
        with DbTxn("add test", db) as trans:
            return db.add_dnatest(test, trans)

    def _make_match(self, gramps_id: str, subject: str, match: str):
        """Return a DNAMatch between two tests, with one segment."""
        dna_match = gramps.gen.lib.DNAMatch()
        dna_match.set_gramps_id(gramps_id)
        dna_match.set_subject_test_handle(subject)
        dna_match.set_match_test_handle(match)
        dna_match.set_shared_cm(55.0)
        dna_match.add_segment(self._make_segment("1", 1000, 2000))
        return dna_match

    def _make_segment(self, chromosome: str, start: int, end: int):
        """Return a DNASegment spanning ``start`` to ``end`` on a chromosome."""
        segment = gramps.gen.lib.DNASegment()
        segment.set_chromosome(chromosome)
        segment.set_start_bp(start)
        segment.set_end_bp(end)
        return segment

    def _provider(self) -> str:
        """Return the display string of the provider the tests use."""
        return str(
            gramps.gen.lib.DNAProviderType(gramps.gen.lib.DNAProviderType.ANCESTRY)
        )

    def test_describe_dnatest(self) -> None:
        """A DNATest is described by its account name and provider."""
        handle = self._add_test(self.db1, "T0001", "alice")
        test = self.db1.get_dnatest_from_handle(handle)
        self.assertEqual(
            MySa(self.db1).describe(test), ("T0001", "alice (%s)" % self._provider())
        )

    def test_describe_dnamatch(self) -> None:
        """A DNAMatch is described by the labels of both of its tests."""
        subject = self._add_test(self.db1, "T0001", "alice")
        match = self._add_test(self.db1, "T0002", "bob")
        dna_match = self._make_match("M0001", subject, match)
        provider = self._provider()
        self.assertEqual(
            MySa(self.db1).describe(dna_match),
            ("M0001", "alice (%s) - bob (%s)" % (provider, provider)),
        )

    def test_add_test_and_match(self) -> None:
        """Added tests and a match keep their handles and references."""
        subject = self._add_test(self.db2, "T0001", "alice")
        match = self._add_test(self.db2, "T0002", "bob")
        with DbTxn("add match", self.db2) as trans:
            match_handle = self.db2.add_dnamatch(
                self._make_match("M0001", subject, match), trans
            )
        stub = self._make_stub()
        with DbTxn("import merge", self.db1, batch=True) as trans:
            for obj_type, handle in (
                ("DNATest", subject),
                ("DNATest", match),
                ("DNAMatch", match_handle),
            ):
                ImportMerge.do_commits(stub, S_ADD, obj_type, handle, A_ADD, trans)

        committed = self.db1.get_dnamatch_from_handle(match_handle)
        self.assertEqual(committed.get_gramps_id(), "M0001")
        self.assertEqual(committed.get_subject_test_handle(), subject)
        self.assertEqual(committed.get_match_test_handle(), match)
        self.assertEqual(
            self.db1.get_dnatest_from_handle(subject).get_account_name(), "alice"
        )

    def test_gramps_id_collision(self) -> None:
        """An added DNATest whose Gramps ID is taken receives a free one."""
        self._add_test(self.db1, "T0001", "alice")
        imported = self._add_test(self.db2, "T0001", "bob")
        stub = self._make_stub()
        with DbTxn("import merge", self.db1, batch=True) as trans:
            ImportMerge.do_commits(stub, S_ADD, "DNATest", imported, A_ADD, trans)

        committed = self.db1.get_dnatest_from_handle(imported)
        self.assertNotEqual(committed.get_gramps_id(), "T0001")

    def test_merge_into_original(self) -> None:
        """Merge into original keeps tree scalars and unions the segments."""
        subject = self._add_test(self.db1, "T0001", "alice")
        match = self._add_test(self.db1, "T0002", "bob")
        self._add_test(self.db2, "T0001", "alice", handle=subject)
        self._add_test(self.db2, "T0002", "bob", handle=match)
        tree_match = self._make_match("M0001", subject, match)
        with DbTxn("add match", self.db1) as trans:
            match_handle = self.db1.add_dnamatch(tree_match, trans)
        import_match = self._make_match("M0001", subject, match)
        import_match.set_handle(match_handle)
        import_match.set_shared_cm(70.0)
        import_match.add_segment(self._make_segment("2", 5000, 6000))
        with DbTxn("add match", self.db2) as trans:
            self.db2.add_dnamatch(import_match, trans)

        stub = self._make_stub()
        with DbTxn("import merge", self.db1, batch=True) as trans:
            ImportMerge.do_commits(
                stub, S_DIFFERS, "DNAMatch", match_handle, A_MERGE_L, trans
            )

        committed = self.db1.get_dnamatch_from_handle(match_handle)
        self.assertEqual(committed.get_shared_cm(), 55.0)
        self.assertEqual(
            sorted(seg.get_chromosome() for seg in committed.get_segment_list()),
            ["1", "2"],
        )


if __name__ == "__main__":
    unittest.main()
