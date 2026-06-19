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

from gramps.gen.db.utils import make_database
from gramps.gen.lib import Event, EventRef, EventType, Family, FamilyRelType, Name, Person
from gramps.gen.lib import Surname
from gramps.plugins.importer.importxml import importData as importXML
from gramps.cli.user import User

from ..ImportSql import importData as importSQL
from ..ExportSql import exportData as exportSQL

gramps_path = os.environ["GRAMPS_RESOURCES"]


# -------------------------------------------------------------------------
#
# ExportSQLTestCase
#
# -------------------------------------------------------------------------
class ExportSQLTestCase(unittest.TestCase):
    """Round-trip export/import tests for the SQLite addon."""

    def setUp(self):
        """Set up source and destination databases loaded with example data."""
        self.database1 = make_database("sqlite")
        try:
            os.mkdir("/tmp/bsddb_exportsql_1")
        except Exception:
            pass
        self.database1.load("/tmp/bsddb_exportsql_1")

        importXML(
            self.database1,
            gramps_path + "/example/gramps/example.gramps",
            User(),
        )
        exportSQL(self.database1, "/tmp/exported1.sql", User(), None)

        self.database2 = make_database("sqlite")
        try:
            os.mkdir("/tmp/bsddb_exportsql_2")
        except Exception:
            pass
        self.database2.load("/tmp/bsddb_exportsql_2")

    def test_person_count_round_trip(self):
        """Person count must match after export/import round-trip."""
        importSQL(self.database2, "/tmp/exported1.sql", User())
        src_count = self.database1.get_number_of_people()
        self.assertGreater(src_count, 0)
        self.assertEqual(self.database2.get_number_of_people(), src_count)

    def test_person_identity_round_trip(self):
        """Every person must survive round-trip with identical core fields."""
        importSQL(self.database2, "/tmp/exported1.sql", User())
        for handle in self.database1.get_person_handles():
            src = self.database1.get_person_from_handle(handle)
            dst = self.database2.get_person_from_handle(handle)
            self.assertIsNotNone(dst, "person %s missing after round-trip" % handle)
            self.assertEqual(src.get_gramps_id(), dst.get_gramps_id())
            self.assertEqual(src.get_gender(), dst.get_gender())
            src_name = src.get_primary_name()
            dst_name = dst.get_primary_name()
            self.assertEqual(src_name.get_first_name(), dst_name.get_first_name())
            self.assertEqual(src_name.get_surname(), dst_name.get_surname())

    def test_familysearch_sync_round_trip(self):
        """familysearch_sync data must survive the SQLite round-trip."""
        importSQL(self.database2, "/tmp/exported1.sql", User())
        for handle in self.database1.get_person_handles():
            src = self.database1.get_person_from_handle(handle)
            dst = self.database2.get_person_from_handle(handle)
            if dst is None:
                continue
            src_fs = src.familysearch_sync
            dst_fs = dst.familysearch_sync
            self.assertEqual(
                src_fs.serialize(),
                dst_fs.serialize(),
                "familysearch_sync mismatch for person %s" % handle,
            )

    def test_family_count_round_trip(self):
        """Family count must match after export/import round-trip."""
        importSQL(self.database2, "/tmp/exported1.sql", User())
        src_count = self.database1.get_number_of_families()
        self.assertGreater(src_count, 0)
        self.assertEqual(self.database2.get_number_of_families(), src_count)

    def test_family_identity_round_trip(self):
        """Every family must survive round-trip with same father/mother handles."""
        importSQL(self.database2, "/tmp/exported1.sql", User())
        for handle in self.database1.get_family_handles():
            src = self.database1.get_family_from_handle(handle)
            dst = self.database2.get_family_from_handle(handle)
            self.assertIsNotNone(
                dst, "family %s missing after round-trip" % handle
            )
            self.assertEqual(src.get_gramps_id(), dst.get_gramps_id())
            self.assertEqual(src.get_father_handle(), dst.get_father_handle())
            self.assertEqual(src.get_mother_handle(), dst.get_mother_handle())

    def test_event_count_round_trip(self):
        """Event count must match after export/import round-trip."""
        importSQL(self.database2, "/tmp/exported1.sql", User())
        src_count = self.database1.get_number_of_events()
        self.assertGreater(src_count, 0)
        self.assertEqual(self.database2.get_number_of_events(), src_count)


# -------------------------------------------------------------------------
#
# FamilySearchSyncRoundTripTest
#
# -------------------------------------------------------------------------
class FamilySearchSyncRoundTripTest(unittest.TestCase):
    """
    Unit test for familysearch_sync round-trip on a synthetic Person with
    non-default FamilySearchSync values.  Does not require the example file.
    """

    def setUp(self):
        """Create a minimal database with one person containing fs sync data."""
        self.database1 = make_database("sqlite")
        try:
            os.mkdir("/tmp/bsddb_fssync_1")
        except Exception:
            pass
        self.database1.load("/tmp/bsddb_fssync_1")

        self.database2 = make_database("sqlite")
        try:
            os.mkdir("/tmp/bsddb_fssync_2")
        except Exception:
            pass
        self.database2.load("/tmp/bsddb_fssync_2")

        # Create a person with a non-trivial familysearch_sync state
        from gramps.gen.db import DbTxn

        with DbTxn("add test person", self.database1) as txn:
            person = Person()
            person.gramps_id = "I9999"
            person.gender = Person.MALE
            primary_name = Name()
            primary_name.set_first_name("Test")
            surname = Surname()
            surname.set_surname("Sync")
            primary_name.set_surname_list([surname])
            person.set_primary_name(primary_name)
            # Set some familysearch_sync data
            person.familysearch_sync.fsid = "FS-TESTID-001"
            person.familysearch_sync.is_root = True
            person.familysearch_sync.conflict = False
            self.database1.add_person(person, txn)
            self.person_handle = person.handle

    def test_familysearch_sync_preserved(self):
        """Non-default familysearch_sync fields must survive the SQL round-trip."""
        exportSQL(self.database1, "/tmp/fssync_test.sql", User(), None)
        importSQL(self.database2, "/tmp/fssync_test.sql", User())

        dst = self.database2.get_person_from_handle(self.person_handle)
        self.assertIsNotNone(dst, "person missing after round-trip")
        self.assertEqual(dst.gramps_id, "I9999")
        self.assertEqual(dst.familysearch_sync.fsid, "FS-TESTID-001")
        self.assertTrue(dst.familysearch_sync.is_root)
        self.assertFalse(dst.familysearch_sync.conflict)
