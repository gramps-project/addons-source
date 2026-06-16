from gramps.gen.db.utils import make_database
from gramps.plugins.importer.importxml import importData as importXML
from gramps.cli.user import User

from ..ImportSql import importData as importSQL
from ..ExportSql import exportData as exportSQL

import unittest
import os

gramps_path = os.environ["GRAMPS_RESOURCES"]

class ExportSQLTestCase (unittest.TestCase):

    def setUp(self):
        self.database1 = make_database("sqlite")
        try:
            os.mkdir("/tmp/bsddb_exportsql_1")
        except:
            pass
        self.database1.load("/tmp/bsddb_exportsql_1")

        importXML(self.database1, gramps_path +
                  "/example/gramps/example.gramps", User())
        exportSQL(self.database1, "/tmp/exported1.sql", User(), None)

        self.database2 = make_database("sqlite")
        try:
            os.mkdir("/tmp/bsddb_exportsql_2")
        except:
            pass

        self.database2.load("/tmp/bsddb_exportsql_2")

    def test_export_sql(self):
        importSQL(self.database2, "/tmp/exported1.sql", User())

        # Round-trip regression. Before this assertion the body merely called
        # importSQL with no check, so the export/import Person-arity break on
        # core 6.1 (familysearch_sync, the 22nd serialize field) was only
        # caught by the crash in setUp. Assert the SQL re-import (database2)
        # reproduces the people exported from the source tree (database1):
        # the count matches and every source person survives with the same
        # identity. Holds on both core 6.0 (21-field Person) and 6.1 (22).
        src_count = self.database1.get_number_of_people()
        self.assertGreater(src_count, 0)
        self.assertEqual(self.database2.get_number_of_people(), src_count)

        for handle in self.database1.get_person_handles():
            src = self.database1.get_person_from_handle(handle)
            dst = self.database2.get_person_from_handle(handle)
            self.assertIsNotNone(
                dst, "person %s missing after round-trip" % handle)
            self.assertEqual(src.get_gramps_id(), dst.get_gramps_id())
            self.assertEqual(src.get_gender(), dst.get_gender())
            src_name = src.get_primary_name()
            dst_name = dst.get_primary_name()
            self.assertEqual(
                src_name.get_first_name(), dst_name.get_first_name())
            self.assertEqual(
                src_name.get_surname(), dst_name.get_surname())
