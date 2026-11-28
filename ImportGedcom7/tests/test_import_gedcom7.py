#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 David Straub
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

"""Tests for the GEDCOM 7 importer."""

import os
import sys
import tempfile
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps_gedcom7  # noqa: F401
except ImportError as err:
    raise unittest.SkipTest("gramps_gedcom7 not available: %s" % err)

from gramps.gen.db.utils import make_database

from ImportGedcom7.import_gedcom7 import import_data

GEDCOM = """0 HEAD
1 GEDC
2 VERS 7.0
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
0 @I2@ INDI
1 NAME Jane /Doe/
1 SEX F
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
0 TRLR
"""


class MockUser:
    """Records the errors an importer reports instead of displaying them."""

    def __init__(self):
        self.errors = []

    def notify_error(self, title, error=""):
        self.errors.append((title, error))

    def notify_db_error(self, error):
        self.errors.append(("db error", error))


class TestImportGedcom7(unittest.TestCase):
    def setUp(self):
        self.db = make_database("sqlite")
        self.db.load(tempfile.mkdtemp(prefix="importgedcom7_"))
        self.user = MockUser()
        self.tmpdir = tempfile.mkdtemp(prefix="importgedcom7_files_")

    def tearDown(self):
        self.db.close()

    def _write(self, name, content, mode="w"):
        path = os.path.join(self.tmpdir, name)
        with open(path, mode) as file:
            file.write(content)
        return path

    def test_import(self):
        path = self._write("test.ged7", GEDCOM)
        info = import_data(self.db, path, self.user)
        self.assertEqual(self.user.errors, [])
        # Gramps treats a None result as a failed import
        self.assertIsNotNone(info)
        self.assertEqual(self.db.get_number_of_people(), 2)
        self.assertEqual(self.db.get_number_of_families(), 1)

    def test_import_info_reports_counts(self):
        path = self._write("test.ged7", GEDCOM)
        info = import_data(self.db, path, self.user)
        text = info.info_text()
        self.assertIn("2", text)
        self.assertIn("1", text)

    def test_invalid_file(self):
        path = self._write("invalid.ged7", "this is not a GEDCOM file\n")
        info = import_data(self.db, path, self.user)
        self.assertIsNone(info)
        self.assertEqual(len(self.user.errors), 1)
        self.assertEqual(self.db.get_number_of_people(), 0)

    def test_invalid_encoding(self):
        path = self._write(
            "latin1.ged7", "0 HEAD\n1 NOTE \xe9\n".encode("latin-1"), "wb"
        )
        info = import_data(self.db, path, self.user)
        self.assertIsNone(info)
        self.assertEqual(len(self.user.errors), 1)

    def test_missing_file(self):
        info = import_data(self.db, os.path.join(self.tmpdir, "nope.ged7"), self.user)
        self.assertIsNone(info)
        self.assertEqual(len(self.user.errors), 1)


if __name__ == "__main__":
    unittest.main()
