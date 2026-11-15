#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Kevin White
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""Tests for the file picker in the Find Missing Media dialog.

Each New Path entry has a folder button.  Choosing a file fills that row and
every other empty row whose missing file has the same name.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import os
import shutil
import tempfile
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from . import gwizard_gtk_fakes as fakes

Gtk = fakes.install()

from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Media
import gwizard_common as gc
import gwizardmediafix as mf

_CHOOSER = "gwizardmediafix.Gtk.FileChooserDialog"
_MF_DLG = "gwizardmediafix.OkDialog"


def setUpModule() -> None:
    """Install the GTK fakes for this module's tests."""
    fakes.install()


def tearDownModule() -> None:
    """Restore the real GTK classes for other test modules."""
    fakes.uninstall()


class _DbState:
    """Minimal stand-in for Gramps' DbState."""

    def __init__(self, db: object) -> None:
        self.db = db


# ------------------------------------------------------------
#
# PickFileTest
#
# ------------------------------------------------------------
class PickFileTest(unittest.TestCase):
    """Choosing a file for one row fills the rows missing the same file name."""

    def setUp(self) -> None:
        self.db = make_database("sqlite")
        self.db.load(":memory:")
        self.dbstate = _DbState(self.db)
        self.tmp = tempfile.mkdtemp()
        self.base = os.path.join(self.tmp, "MediaBase")
        os.makedirs(self.base)
        self.db.set_mediapath(self.base)

    def tearDown(self) -> None:
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add_media(self, path: str, desc: str = "") -> str:
        """Add a media record and return its handle."""
        with DbTxn("add media", self.db) as trans:
            media = Media()
            media.set_path(path)
            media.set_description(desc)
            return self.db.add_media(media, trans)

    def touch(self, *parts: str) -> str:
        """Create a small file under the temp folder and return its path."""
        path = os.path.join(self.tmp, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(path)
        return path

    def open_dialog(self) -> mf.FindMissingMediaDialog:
        """Open the dialog and build its rows (as show_dialog would)."""
        return mf.FindMissingMediaDialog(dbstate=self.dbstate)

    def target_for(self, dlg: mf.FindMissingMediaDialog, handle: str) -> Any:
        """Return the row for a media handle."""
        for target in dlg.row_targets:
            if target["entry"]["handle"] == handle:
                return target
        raise AssertionError("no row for %s" % handle)

    def pick(self, dlg: mf.FindMissingMediaDialog, target: Any, path: Any) -> None:
        """Press a row's folder button and choose *path* (None = Cancel)."""
        chooser = MagicMock()
        chooser.run.return_value = (
            Gtk.ResponseType.OK if path else Gtk.ResponseType.CANCEL
        )
        chooser.get_filename.return_value = path
        with patch(_CHOOSER, return_value=chooser):
            dlg.cb_pick_file(MagicMock(), target)

    def test_each_row_has_a_folder_button(self) -> None:
        """Pressing a row's folder button opens the picker for that row."""
        h_one = self.add_media("Old/one.jpg", "One")
        h_two = self.add_media("Old/two.jpg", "Two")
        created: list[Any] = []
        real_button = Gtk.Button

        def make_button(*args: Any, **kwargs: Any) -> Any:
            button = real_button(*args, **kwargs)
            created.append(button)
            return button

        with patch("gwizardmediafix.Gtk.Button", make_button):
            dlg = self.open_dialog()
        folder_buttons = [b for b in created if b.get_tooltip_text()]
        self.assertEqual(len(folder_buttons), 2)

        chooser = MagicMock()
        chooser.run.return_value = Gtk.ResponseType.OK
        chooser.get_filename.return_value = self.touch("MediaBase", "two.jpg")
        with patch(_CHOOSER, return_value=chooser):
            folder_buttons[1].clicked()
        self.assertEqual(
            self.target_for(dlg, h_two)["path_entry"].get_text(), "two.jpg"
        )
        self.assertEqual(self.target_for(dlg, h_one)["path_entry"].get_text(), "")

    def test_pick_fills_same_name_rows(self) -> None:
        """Rows missing a file of the same name are filled; others are not."""
        h_first = self.add_media("Old/census.jpg", "First")
        h_same = self.add_media("Old/census.jpg", "Same folder")
        h_moved = self.add_media("Elsewhere/census.jpg", "Other folder")
        h_other = self.add_media("Old/portrait.jpg", "Other name")
        h_typed = self.add_media("Old/census.jpg", "Already typed")
        picked = self.touch("MediaBase", "scans", "census.jpg")

        dlg = self.open_dialog()
        self.target_for(dlg, h_typed)["path_entry"].set_text("keep/this.jpg")
        self.pick(dlg, self.target_for(dlg, h_first), picked)

        self.assertEqual(
            self.target_for(dlg, h_first)["path_entry"].get_text(),
            "scans/census.jpg",
        )
        self.assertIn(
            "Also filled 2 other records",
            self.target_for(dlg, h_first)["hint_label"].text,
        )
        same = self.target_for(dlg, h_same)
        self.assertEqual(same["path_entry"].get_text(), "scans/census.jpg")
        self.assertIn("Same file as", same["hint_label"].text)
        moved = self.target_for(dlg, h_moved)
        self.assertEqual(moved["path_entry"].get_text(), "scans/census.jpg")
        self.assertIn("different folder", moved["hint_label"].text)
        self.assertEqual(self.target_for(dlg, h_other)["path_entry"].get_text(), "")
        self.assertEqual(
            self.target_for(dlg, h_typed)["path_entry"].get_text(), "keep/this.jpg"
        )

    def test_every_same_name_row_is_filled(self) -> None:
        """A pick fills every other row missing the same file name."""
        h_first = self.add_media("Old/census.jpg", "First")
        h_second = self.add_media("Old/census.jpg", "Second")
        picked = self.touch("MediaBase", "census.jpg")

        dlg = self.open_dialog()
        self.pick(dlg, self.target_for(dlg, h_first), picked)

        self.assertEqual(
            self.target_for(dlg, h_second)["path_entry"].get_text(), "census.jpg"
        )

    def test_cancel_changes_nothing(self) -> None:
        """Cancelling the picker leaves the row empty."""
        h_first = self.add_media("Old/census.jpg", "First")
        dlg = self.open_dialog()
        target = self.target_for(dlg, h_first)
        self.pick(dlg, target, None)
        self.assertEqual(target["path_entry"].get_text(), "")
        self.assertNotIn("picked", target)

    def test_file_outside_base_is_kept_absolute(self) -> None:
        """A file outside the media base path is entered as its full path."""
        h_first = self.add_media("Old/census.jpg", "First")
        picked = self.touch("Elsewhere", "census.jpg")
        dlg = self.open_dialog()
        target = self.target_for(dlg, h_first)
        self.pick(dlg, target, picked)
        self.assertEqual(target["path_entry"].get_text(), picked)

    def test_pick_replaces_queued_copy(self) -> None:
        """Choosing a file drops a copy queued by "Copy from folder..."."""
        h_first = self.add_media("Old/census.jpg", "First")
        picked = self.touch("MediaBase", "census.jpg")
        dlg = self.open_dialog()
        target = self.target_for(dlg, h_first)
        target["copy_src"] = self.touch("Source", "census.jpg")
        self.pick(dlg, target, picked)
        self.assertNotIn("copy_src", target)

    def test_apply_repoints_all_filled_records(self) -> None:
        """Apply stores the chosen file, relative to the base path, for every row."""
        h_first = self.add_media("Old/census.jpg", "First")
        h_same = self.add_media("Old/census.jpg", "Same folder")
        picked = self.touch("MediaBase", "scans", "census.jpg")

        dlg = self.open_dialog()
        self.pick(dlg, self.target_for(dlg, h_first), picked)
        with patch(_MF_DLG):
            dlg.cb_apply(MagicMock())

        for handle in (h_first, h_same):
            self.assertEqual(
                self.db.get_media_from_handle(handle).get_path(), "scans/census.jpg"
            )

    def test_base_path_changed_after_pick(self) -> None:
        """A chosen file is stored relative to the base path in force at Apply."""
        h_first = self.add_media("Old/census.jpg", "First")
        picked = self.touch("MediaBase", "scans", "census.jpg")

        dlg = self.open_dialog()
        self.pick(dlg, self.target_for(dlg, h_first), picked)
        new_base = os.path.join(self.base, "scans")
        dlg.path_entry.set_text(new_base)
        dlg.cb_set_mediapath()
        with patch(_MF_DLG):
            dlg.cb_apply(MagicMock())

        self.assertEqual(
            self.db.get_media_from_handle(h_first).get_path(), "census.jpg"
        )

    def test_next_pick_starts_in_last_folder(self) -> None:
        """The picker opens in the folder of the previous pick."""
        h_first = self.add_media("Old/census.jpg", "First")
        h_second = self.add_media("Old/portrait.jpg", "Second")
        picked = self.touch("Elsewhere", "census.jpg")
        dlg = self.open_dialog()
        self.pick(dlg, self.target_for(dlg, h_first), picked)

        chooser = MagicMock()
        chooser.run.return_value = Gtk.ResponseType.CANCEL
        with patch(_CHOOSER, return_value=chooser):
            dlg.cb_pick_file(MagicMock(), self.target_for(dlg, h_second))
        chooser.set_current_folder.assert_called_once_with(
            os.path.join(self.tmp, "Elsewhere")
        )


# Test discovery imports every test module before running any, so take the
# fakes off Gtk again now that the GWizard modules are imported; other Gramps
# tests need the real widgets.  setUpModule puts them back for this module.
fakes.uninstall()


if __name__ == "__main__":
    unittest.main()
