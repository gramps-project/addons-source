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
LIVE test (see README.md) for TODO.md gap 7: a Person whose name has a
diacritic (the live report's "Zieliński") produced a spurious "Object
has changed" on the very first push after a clean bootstrap, with no
other editor involved.

Stores the same name on the server in each Unicode normalization form
-- NFD (decomposed: "n" + U+0301 COMBINING ACUTE ACCENT) and NFC
(precomposed: U+0144) -- bootstraps a fresh mirror, then pushes one
unrelated edit (an attribute). If the local mirror's copy of the name
doesn't match the server's byte-for-byte, that push's "old" snapshot
won't either, and the server rejects it.
"""

import os
import shutil
import sys
import time
import unicodedata
import unittest

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG, import_webapidb, mint_api_key, new_mirror_dir

sys.path.insert(0, live_harness.ADDON_DIR)

from gramps.gen.db import DbTxn  # noqa: E402
from gramps.gen.lib import Attribute, Name, Person, Surname  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402

SURNAME = "Zieliński"


def _form(text):
    if unicodedata.is_normalized("NFC", text) and unicodedata.is_normalized("NFD", text):
        return "ASCII"
    if unicodedata.is_normalized("NFC", text):
        return "NFC"
    if unicodedata.is_normalized("NFD", text):
        return "NFD"
    return "mixed"


class TestUnicodeNormalizationConflict(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.created = []

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _make_person(self, surname_text, gramps_id):
        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id(gramps_id)
        name = Name()
        surname = Surname()
        surname.set_surname(surname_text)
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.tag_handle)
        payload = [
            {
                "type": "add",
                "_class": "Person",
                "handle": person.handle,
                "old": None,
                "new": object_to_dict(person),
            }
        ]
        self.client.post(
            "/transactions/", data=payload, params={"message": "live test fixture: person"}
        )
        self.created.append(("Person", person.handle))
        return person

    def _run_case(self, form, gramps_id):
        surname_text = unicodedata.normalize(form, SURNAME)
        person = self._make_person(surname_text, gramps_id)

        server_surname = self.client.get(f"/people/{person.handle}")["primary_name"][
            "surname_list"
        ][0]["surname"]
        print(f"[{form}] server stores surname as {_form(server_surname)}")

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)
            local_surname = (
                db.get_person_from_handle(person.handle)
                .get_primary_name()
                .get_surname_list()[0]
                .get_surname()
            )
            print(f"[{form}] local mirror has surname as {_form(local_surname)}")

            with self.assertLogs(".grampswebapidb", level="DEBUG") as cm:
                with DbTxn("live test: add unrelated attribute", db) as trans:
                    p = db.get_person_from_handle(person.handle)
                    attr = Attribute()
                    attr.set_type("LiveTestUnicodeAttr")
                    attr.set_value("hello")
                    p.add_attribute(attr)
                    db.commit_person(p, trans)
                deadline = time.monotonic() + 90
                pushed = False
                while time.monotonic() < deadline and not pushed:
                    live_harness.pump_glib(3)
                    pushed = any(
                        a.get("value") == "hello"
                        for a in self.client.get(f"/people/{person.handle}").get(
                            "attribute_list", []
                        )
                    )
                live_harness.pump_glib(3)

            conflicted = any("Server rejected" in line for line in cm.output)
            for line in cm.output:
                if "conflict-diff" in line or "Server rejected" in line:
                    print(f"[{form}]   {line}")
            print(f"[{form}] first push conflicted: {conflicted}  edit reached server: {pushed}")
            return conflicted, pushed
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)

    def test_nfd_name_on_server(self):
        conflicted, pushed = self._run_case("NFD", "LT_UNI_NFD")
        self.assertFalse(conflicted, "spurious conflict on an NFD-stored name")
        self.assertTrue(pushed)

    def test_nfc_name_on_server(self):
        conflicted, pushed = self._run_case("NFC", "LT_UNI_NFC")
        self.assertFalse(conflicted, "spurious conflict on an NFC-stored name")
        self.assertTrue(pushed)


if __name__ == "__main__":
    unittest.main()
