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

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import (
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
