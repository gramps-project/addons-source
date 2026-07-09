# The Sqlite module imports Gtk at module load — skip the whole file if
# gi/Gtk aren't available (headless-without-GTK environments). On systems
# where both GTK3 and GTK4 are present, pin Gtk to 3.0 before any gramps
# import (mirrors what gramps.grampsapp does at startup); otherwise
# PyGObject loads GTK4 and the gramps.gui import chain crashes on
# Gtk.IconSize.MENU (a GTK3-only enum).
import unittest

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError, AttributeError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

import os
import shutil

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import (
    ChildRef,
    Event,
    EventRef,
    EventType,
    Family,
    FamilyRelType,
    Name,
    Person,
    Surname,
)
from gramps.cli.user import User

from ..ImportSql import importData as importSQL
from ..ExportSql import exportData as exportSQL


def _make_person(db, txn, gid, first, surname_str, gender=Person.MALE, fsid=None):
    """Add a minimal Person to *db* inside *txn*, return the handle."""
    person = Person()
    person.gramps_id = gid
    person.gender = gender
    name = Name()
    name.set_first_name(first)
    sn = Surname()
    sn.set_surname(surname_str)
    name.set_surname_list([sn])
    person.set_primary_name(name)
    if fsid is not None:
        person.familysearch_sync.fsid = fsid
        person.familysearch_sync.is_root = True
    db.add_person(person, txn)
    return person.handle


def _make_family(db, txn, gid, father_h, mother_h):
    """Add a minimal Family to *db* inside *txn*, return the handle."""
    fam = Family()
    fam.gramps_id = gid
    fam.set_father_handle(father_h)
    fam.set_mother_handle(mother_h)
    fam.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
    db.add_family(fam, txn)
    return fam.handle


def _make_event(db, txn, gid, etype=EventType.BIRTH):
    """Add a minimal Event to *db* inside *txn*, return the handle."""
    evt = Event()
    evt.gramps_id = gid
    evt.set_type(EventType(etype))
    db.add_event(evt, txn)
    return evt.handle


def _build_source_db(path):
    """Build a minimal source Gramps database at *path* and return it."""
    db = make_database("sqlite")
    os.makedirs(path, exist_ok=True)
    db.load(path)
    with DbTxn("build test db", db) as txn:
        father_h = _make_person(db, txn, "I0001", "Alice", "Smith",
                                gender=Person.FEMALE, fsid="FS-ALICE-001")
        mother_h = _make_person(db, txn, "I0002", "Bob", "Jones",
                                gender=Person.MALE)
        child_h = _make_person(db, txn, "I0003", "Carol", "Smith",
                               gender=Person.FEMALE)
        _make_family(db, txn, "F0001", father_h, mother_h)
        _make_event(db, txn, "E0001", EventType.BIRTH)
    return db


# -------------------------------------------------------------------------
#
# SqliteRoundTripTest
#
# -------------------------------------------------------------------------
class SqliteRoundTripTest(unittest.TestCase):
    """Fast round-trip tests using a small synthetic database."""

    def setUp(self):
        self.src_db = _build_source_db("/tmp/sqlite_rt_src")
        exportSQL(self.src_db, "/tmp/sqlite_rt.sql", User(), None)

        self.dst_db = make_database("sqlite")
        os.makedirs("/tmp/sqlite_rt_dst", exist_ok=True)
        self.dst_db.load("/tmp/sqlite_rt_dst")
        importSQL(self.dst_db, "/tmp/sqlite_rt.sql", User())

    def test_person_count(self):
        """Person count must match after round-trip."""
        self.assertEqual(
            self.dst_db.get_number_of_people(),
            self.src_db.get_number_of_people(),
        )

    def test_person_identity(self):
        """Person gramps_id, gender, and primary name must survive round-trip."""
        for handle in self.src_db.get_person_handles():
            src = self.src_db.get_person_from_handle(handle)
            dst = self.dst_db.get_person_from_handle(handle)
            self.assertIsNotNone(dst, "person %s missing" % handle)
            self.assertEqual(src.get_gramps_id(), dst.get_gramps_id())
            self.assertEqual(src.get_gender(), dst.get_gender())
            self.assertEqual(
                src.get_primary_name().get_first_name(),
                dst.get_primary_name().get_first_name(),
            )
            self.assertEqual(
                src.get_primary_name().get_surname(),
                dst.get_primary_name().get_surname(),
            )

    def test_family_count(self):
        """Family count must match after round-trip."""
        self.assertEqual(
            self.dst_db.get_number_of_families(),
            self.src_db.get_number_of_families(),
        )

    def test_family_identity(self):
        """Father/mother handles must survive round-trip."""
        for handle in self.src_db.get_family_handles():
            src = self.src_db.get_family_from_handle(handle)
            dst = self.dst_db.get_family_from_handle(handle)
            self.assertIsNotNone(dst, "family %s missing" % handle)
            self.assertEqual(src.get_father_handle(), dst.get_father_handle())
            self.assertEqual(src.get_mother_handle(), dst.get_mother_handle())

    def test_event_count(self):
        """Event count must match after round-trip."""
        self.assertEqual(
            self.dst_db.get_number_of_events(),
            self.src_db.get_number_of_events(),
        )

    def test_familysearch_sync(self):
        """familysearch_sync fields must survive round-trip."""
        for handle in self.src_db.get_person_handles():
            src = self.src_db.get_person_from_handle(handle)
            dst = self.dst_db.get_person_from_handle(handle)
            if dst is None:
                continue
            self.assertEqual(
                src.familysearch_sync.serialize(),
                dst.familysearch_sync.serialize(),
                "familysearch_sync mismatch for %s" % src.get_gramps_id(),
            )
        # Explicit check for the person we know has a non-default fsid
        alice_src = next(
            p for h in self.src_db.get_person_handles()
            if (p := self.src_db.get_person_from_handle(h)).get_gramps_id() == "I0001"
        )
        alice_dst = self.dst_db.get_person_from_handle(alice_src.handle)
        self.assertIsNotNone(alice_dst)
        self.assertEqual(alice_dst.familysearch_sync.fsid, "FS-ALICE-001")
        self.assertTrue(alice_dst.familysearch_sync.is_root)


# -------------------------------------------------------------------------
#
# SqliteOrderRoundTripTest
#
# -------------------------------------------------------------------------
class SqliteOrderRoundTripTest(unittest.TestCase):
    """Round-trip tests for GUI-reorderable lists (children, spouses).

    Every such list is stored in the generic `link` table on export and
    read back with no ordering guarantee beyond a `seq` column; these
    tests catch a regression to that unordered behavior.
    """

    def setUp(self):
        for path in ("/tmp/sqlite_order_rt_src", "/tmp/sqlite_order_rt_dst"):
            shutil.rmtree(path, ignore_errors=True)
        if os.path.exists("/tmp/sqlite_order_rt.sql"):
            os.remove("/tmp/sqlite_order_rt.sql")

        self.src_db = make_database("sqlite")
        os.makedirs("/tmp/sqlite_order_rt_src", exist_ok=True)
        self.src_db.load("/tmp/sqlite_order_rt_src")

        with DbTxn("build order test db", self.src_db) as txn:
            father_h = _make_person(self.src_db, txn, "I0001", "Dad", "Smith")
            mother_h = _make_person(self.src_db, txn, "I0002", "Mom", "Smith")
            # Created in this order, but birth order (set below) differs.
            self.alpha_h = _make_person(self.src_db, txn, "I0003", "Alpha", "Smith")
            self.beta_h = _make_person(self.src_db, txn, "I0004", "Beta", "Smith")
            self.gamma_h = _make_person(self.src_db, txn, "I0005", "Gamma", "Smith")

            fam = Family()
            fam.gramps_id = "F0001"
            fam.set_father_handle(father_h)
            fam.set_mother_handle(mother_h)
            fam.set_relationship(FamilyRelType(FamilyRelType.MARRIED))
            # Birth order: Gamma, Alpha, Beta -- not creation order.
            for h in (self.gamma_h, self.alpha_h, self.beta_h):
                cref = ChildRef()
                cref.set_reference_handle(h)
                fam.add_child_ref(cref)
            self.src_db.add_family(fam, txn)
            self.fam_handle = fam.handle

            for h in (self.alpha_h, self.beta_h, self.gamma_h):
                p = self.src_db.get_person_from_handle(h)
                p.add_family_handle(self.fam_handle)
                self.src_db.commit_person(p, txn)

            self.person_h = _make_person(self.src_db, txn, "I0006", "Ivan", "Jones")
            w1_h = _make_person(self.src_db, txn, "I0007", "Wilma1", "Brown",
                                gender=Person.FEMALE)
            w2_h = _make_person(self.src_db, txn, "I0008", "Wilma2", "Green",
                                gender=Person.FEMALE)
            w3_h = _make_person(self.src_db, txn, "I0009", "Wilma3", "White",
                                gender=Person.FEMALE)
            self.fam1 = _make_family(self.src_db, txn, "F0002", self.person_h, w1_h)
            self.fam2 = _make_family(self.src_db, txn, "F0003", self.person_h, w2_h)
            self.fam3 = _make_family(self.src_db, txn, "F0004", self.person_h, w3_h)
            p = self.src_db.get_person_from_handle(self.person_h)
            p.add_family_handle(self.fam1)
            p.add_family_handle(self.fam2)
            p.add_family_handle(self.fam3)
            self.src_db.commit_person(p, txn)

        # Simulate the "Reorder families" tool with a second commit that
        # doesn't touch object identity, only list order.
        with DbTxn("reorder families", self.src_db) as txn:
            p = self.src_db.get_person_from_handle(self.person_h)
            p.set_family_handle_list([self.fam3, self.fam1, self.fam2])
            self.src_db.commit_person(p, txn)

        exportSQL(self.src_db, "/tmp/sqlite_order_rt.sql", User(), None)

        self.dst_db = make_database("sqlite")
        os.makedirs("/tmp/sqlite_order_rt_dst", exist_ok=True)
        self.dst_db.load("/tmp/sqlite_order_rt_dst")
        importSQL(self.dst_db, "/tmp/sqlite_order_rt.sql", User())

    def test_child_ref_order(self):
        """Family child_ref_list order (birth order) must survive round-trip."""
        src_family = self.src_db.get_family_from_handle(self.fam_handle)
        dst_family = self.dst_db.get_family_from_handle(self.fam_handle)
        self.assertIsNotNone(dst_family)
        src_order = [cr.ref for cr in src_family.get_child_ref_list()]
        dst_order = [cr.ref for cr in dst_family.get_child_ref_list()]
        self.assertEqual(src_order, [self.gamma_h, self.alpha_h, self.beta_h])
        self.assertEqual(dst_order, src_order)

    def test_family_list_order(self):
        """Person family_list order (spouse order) must survive round-trip."""
        src_person = self.src_db.get_person_from_handle(self.person_h)
        dst_person = self.dst_db.get_person_from_handle(self.person_h)
        self.assertIsNotNone(dst_person)
        src_order = src_person.get_family_handle_list()
        dst_order = dst_person.get_family_handle_list()
        self.assertEqual(src_order, [self.fam3, self.fam1, self.fam2])
        self.assertEqual(dst_order, src_order)
