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
        self.database1 = make_database("bsddb")
        try:
            os.mkdir("/tmp/bsddb_exportsql_1")
        except:
            pass
        self.database1.write_version("/tmp/bsddb_exportsql_1")
        self.database1.load("/tmp/bsddb_exportsql_1")

        importXML(self.database1, gramps_path + "/example/gramps/example.gramps", User())
        exportSQL(self.database1, "/tmp/exported1.sql")

        self.database2 = make_database("bsddb")
        try:
            os.mkdir("/tmp/bsddb_exportsql_2")
        except:
            pass
        self.database2.write_version("/tmp/bsddb_exportsql_2")

        self.database2.load("/tmp/bsddb_exportsql_2")

    def test_export_sql(self):
        importSQL(self.database2, "/tmp/exported1.sql", User())


