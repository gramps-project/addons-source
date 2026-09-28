#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Douglas S. Blank <doug.blank@gmail.com>
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
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
LIVE test (see README.md) for TODO.md gap 9's open risk: a Note the
server stores with "\\r\\n" line endings comes back "\\n"-only after a
reimport (XML 1.0 mandates it), so an edit to that Note sends an "old"
snapshot the server's own copy doesn't match. Runs the same edit
against a "\\n"-only Note as a control.
"""

import os
import shutil
import sys
import time
import unittest

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG, import_webapidb, mint_api_key, new_mirror_dir

sys.path.insert(0, live_harness.ADDON_DIR)

from gramps.gen.db import DbTxn  # noqa: E402
from gramps.gen.lib import Note, NoteType  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402

MARKER = "live test edit"


class TestCrlfNoteEditConflict(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.created = []

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _make_note(self, text, gramps_id):
        note = Note()
        note.set_handle(live_harness._new_handle())
        note.set_gramps_id(gramps_id)
        note.set_type(NoteType.GENERAL)
        note.set(text)
        note.add_tag(self.tag_handle)
        payload = [
            {
                "type": "add",
                "_class": "Note",
                "handle": note.handle,
                "old": None,
                "new": object_to_dict(note),
            }
        ]
        self.client.post(
            "/transactions/", data=payload, params={"message": "live test fixture: note"}
        )
        self.created.append(("Note", note.handle))
        return note

    def _server_text(self, handle):
        return self.client.get(f"/notes/{handle}")["text"]["string"]

    def _run_case(self, label, text, gramps_id):
        note = self._make_note(text, gramps_id)
        print(f"[{label}] server stores text as {self._server_text(note.handle)!r}")

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)
            print(f"[{label}] local mirror has text as {db.get_note_from_handle(note.handle).get()!r}")

            with self.assertLogs(".grampswebapidb", level="DEBUG") as cm:
                with DbTxn("live test: edit note", db) as trans:
                    n = db.get_note_from_handle(note.handle)
                    n.set(n.get() + "\n" + MARKER)
                    db.commit_note(n, trans)
                deadline = time.monotonic() + 90
                pushed = False
                while time.monotonic() < deadline and not pushed:
                    live_harness.pump_glib(3)
                    pushed = MARKER in self._server_text(note.handle)
                live_harness.pump_glib(3)

            conflicted = any("Server rejected" in line for line in cm.output)
            for line in cm.output:
                if "conflict-diff" in line or "Server rejected" in line or "Giving up" in line:
                    print(f"[{label}]   {line}")
            print(f"[{label}] first push conflicted: {conflicted}  edit reached server: {pushed}")
            print(f"[{label}] server text after: {self._server_text(note.handle)!r}")
            return conflicted, pushed
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)

    def test_crlf_note_on_server(self):
        conflicted, pushed = self._run_case("CRLF", "Line one\r\nLine two", "LT_CRLF_N1")
        self.assertFalse(conflicted, "spurious conflict editing a CRLF-stored Note")
        self.assertTrue(pushed)

    def test_lf_note_on_server(self):
        conflicted, pushed = self._run_case("LF", "Line one\nLine two", "LT_CRLF_N2")
        self.assertFalse(conflicted, "spurious conflict editing an LF-stored Note")
        self.assertTrue(pushed)


if __name__ == "__main__":
    unittest.main()
