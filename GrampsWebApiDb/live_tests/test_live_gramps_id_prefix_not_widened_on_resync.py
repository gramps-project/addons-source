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
LIVE test (see README.md): if this *local* Gramps installation's own ID
Formats preference (Edit > Preferences > ID Formats) is wider than the
server's own -- e.g. "I%08d" locally against a server tree using plain
"I%04d" -- does a real bootstrap (or a later resync) against the live
server silently rewrite the server's own gramps_id values to match it?

Reported live (addons-source#1030, TODO.md gap 7's local-ID-Formats
finding): a user's local ID Formats preference of "I%08d" made every
Person's gramps_id come back 8 digits locally (e.g. "I00001106") where
the server itself used plain 4-digit ids ("I1106"). gramps_id is part of
the payload transaction_to_json() sends on every push, so that mismatch
alone made the server's own byte-for-byte "Object has changed" check
reject the very next edit to *any* object -- independent of any real
conflict.

gramps.gen.db.generic.DbGeneric.__init__() itself defaults every prefix
to "I%04d" (etc.) -- confirmed by reading the source -- so a plain
WebApiDB(), constructed the way this file's own live tests always do
(bypassing Gramps' own DbState, which is what would normally apply this
user's *real* global preference before load() ever runs), already
starts out matching a plain-4-digit server. This test deliberately calls
set_prefixes() with a wide format first, standing in for that real
global preference DbState.change_database_noclose() would otherwise
have applied, exactly the shape TestReimportPreservesServerGrampsIds
(tests/test_grampswebapidb.py) already covers against a real local
database -- this is that test's live, real-server, real-ImportXml
counterpart.
"""

import os
import shutil
import sys
import unittest

# README.md's documented invocation (`cd live_tests && python3 test_live_
# ....py`) has Python add this script's own directory to sys.path
# automatically, which is what a bare `import live_harness` relies on.
# That doesn't happen under `python3 -m unittest GrampsWebApiDb.live_
# tests.test_live_...` (the invocation style the addon's own tests/
# suite uses, per the repo's CLAUDE.md) -- sys.path there only has the
# caller's cwd, not this directory -- so add it explicitly.
LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG, import_webapidb, mint_api_key, new_mirror_dir

sys.path.insert(0, live_harness.ADDON_DIR)

from gramps.gen.db import DbTxn  # noqa: E402
from gramps.gen.lib import Attribute, Name, Person, Surname  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402

#: A normal-looking, "I" + all-digits id, deliberately short so a wrongly
#: widened result ("I00042424" instead of "I42424") is unmistakable at a
#: glance -- id2user_format() (gen/db/generic.py) only reformats an id
#: that starts with the prefix's own literal string and is all-digits
#: after that, which is why the addon's *other* live-test fixtures (ids
#: like "LT_P1") never trigger this mechanism at all and had to be
#: avoided here on purpose.
TEST_GRAMPS_ID = "I42424"

#: This test's stand-in for a real user's own global ID Formats
#: preference -- 8-digit zero-padded, matching the live report exactly.
WIDE_PREFIXES = dict(
    person="I%08d",
    media="O%08d",
    family="F%08d",
    source="S%08d",
    citation="C%08d",
    place="P%08d",
    event="E%08d",
    repository="R%08d",
    note="N%08d",
)


class TestGrampsIdPrefixNotWidenedOnResync(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.created = []  # [(class_name, handle), ...], for cleanup

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _make_person(self):
        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id(TEST_GRAMPS_ID)
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestIdPrefix")
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
            "/transactions/",
            data=payload,
            params={"message": "live test fixture: person"},
        )
        self.created.append(("Person", person.handle))
        return person

    def _force_full_resync(self, db):
        """Directly drive _full_resync_async() to completion -- see
        test_live_tag_handle_stable_across_resync.py's own helper for
        why this is the faithful way to trigger a second real resync
        without manufacturing an actual conflicting edit first."""
        db._syncing = True
        result = {}
        try:
            db._full_resync_async(
                on_done=lambda v: result.update(done=True),
                on_error=lambda exc: result.update(error=exc),
            )
            live_harness.pump_glib(20)
        finally:
            db._syncing = False
        if "error" in result:
            raise result["error"]
        self.assertIn("done", result, "resync did not complete within the pump window")

    def test_bootstrap_and_a_later_resync_both_preserve_the_servers_id(self):
        person = self._make_person()

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            # Stand-in for DbState.change_database_noclose() applying
            # this user's own (unusually wide) global ID Formats
            # preference when a real Gramps session opens this tree --
            # deliberately done *before* load(), the same ordering a
            # real session uses (cli/grampscli.py's read_file():
            # dbstate.change_database() runs before db.load()).
            db.set_prefixes(
                WIDE_PREFIXES["person"],
                WIDE_PREFIXES["media"],
                WIDE_PREFIXES["family"],
                WIDE_PREFIXES["source"],
                WIDE_PREFIXES["citation"],
                WIDE_PREFIXES["place"],
                WIDE_PREFIXES["event"],
                WIDE_PREFIXES["repository"],
                WIDE_PREFIXES["note"],
            )

            db.load(mirror_dir)  # bootstrap: first reimport

            local_person = db.get_person_from_handle(person.handle)
            print(
                f"[gramps_id] server={TEST_GRAMPS_ID!r}  "
                f"local after bootstrap={local_person.gramps_id!r}"
            )
            self.assertEqual(
                local_person.gramps_id,
                TEST_GRAMPS_ID,
                "bootstrap widened the server's own gramps_id to match "
                "this (simulated) local ID Formats preference -- "
                "_reimport_preserving_server_gramps_ids() should have "
                "kept it byte-for-byte (see TODO.md gap 7)",
            )

            # A second, directly-consecutive full resync -- the plain
            # _full_resync_async() path (not _bootstrap_full_resync()),
            # exercising the *other* of the two call sites
            # _reimport_preserving_server_gramps_ids() has to cover.
            self._force_full_resync(db)

            local_person = db.get_person_from_handle(person.handle)
            print(f"[gramps_id] local after resync={local_person.gramps_id!r}")
            self.assertEqual(
                local_person.gramps_id,
                TEST_GRAMPS_ID,
                "a later resync widened the server's own gramps_id -- "
                "same gap as the bootstrap case, just the other call site",
            )

            # The neutralization is scoped to the reimport only -- this
            # user's own (simulated) preference must still apply to
            # anything created locally afterward.
            self.assertEqual(db.person_prefix, WIDE_PREFIXES["person"])
            self.assertTrue(db.find_next_note_gramps_id().startswith("N"))
            self.assertEqual(len(db.find_next_note_gramps_id()), 9)  # "N" + 8 digits

            # The real-world consequence, same shape as this directory's
            # other live tests: an edit that has nothing to do with
            # gramps_id should still push cleanly. gramps_id rides along
            # in every push's full payload, so a widened one would make
            # this conflict even though nothing relevant was ever
            # touched.
            with DbTxn("live test: add unrelated attribute", db) as trans:
                p = db.get_person_from_handle(person.handle)
                attr = Attribute()
                attr.set_type("LiveTestIdPrefixAttr")
                attr.set_value("hello")
                p.add_attribute(attr)
                db.commit_person(p, trans)

            live_harness.pump_glib(5)

            server_person = self.client.get(f"/people/{person.handle}")
            pushed = any(
                a.get("value") == "hello"
                for a in server_person.get("attribute_list", [])
            )
            print(f"[push result] attribute reached the server: {pushed}")
            self.assertTrue(
                pushed,
                "an edit unrelated to gramps_id was falsely rejected as a "
                "conflict -- almost certainly caused by a widened "
                "gramps_id riding along in the push's full payload",
            )
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
