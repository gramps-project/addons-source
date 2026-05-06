# The Sqlite module imports Gtk at module load — skip the whole file if
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


