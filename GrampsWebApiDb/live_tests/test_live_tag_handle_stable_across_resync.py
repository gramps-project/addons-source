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
LIVE test (see README.md): does a Tag attached to a Person keep the same
*local* handle across two directly-consecutive real resyncs against the
live server -- and does an otherwise-unrelated edit to that Person still
push cleanly afterward?

Reported live (addons-source#1030, TODO.md gap 8): a Person's Tag
reference came back under a different raw handle on each of three
separate, directly-consecutive resyncs within one Gramps session, with
nothing about the tag itself ever edited. Every local explanation was
ruled out (ImportXml preserves handles it's given verbatim for anything
absent from the target database, which every object is right after this
addon's own "clear local mirror" step -- confirmed by the same logs'
Person handle staying stable across the same resyncs); what's left is
gramps-web-api's own export generator apparently not treating a Tag as a
persisted object with a stable handle, minting a fresh one per export.

This test does not depend on that server behavior actually reproducing
today to be useful: _snapshot_tag_handles_by_name()/
_restabilize_tag_handles() (grampswebapidb.py) exist to keep this
mirror's own local handle stable regardless of what the server's export
does from one call to the next, so the assertion below (same local
handle before and after a second resync) is what the fix guarantees --
this is the live, real-server, real-ImportXml counterpart to
tests/test_grampswebapidb.py's TestRestabilizeTagHandles, which proves
the mechanism itself works but necessarily fakes the "server sends a
different handle" half by hand.
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

#: Distinct from live_harness.TEST_TAG (the sweep-and-cleanup marker,
#: attached to *every* object these tests create): this is the tag under
#: test, the one whose *handle* has to survive a resync unchanged. Kept
#: separate so a reader isn't left wondering whether tag_list[0] or
#: tag_list[1] is the one this test is actually about.
STABLE_TAG_NAME = "LiveTestStableTagName"


class TestTagHandleStableAcrossResync(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.marker_tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.created = []  # [(class_name, handle), ...], for cleanup

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _push_add(self, obj_class, gramps_obj, message):
        payload = [
            {
                "type": "add",
                "_class": obj_class,
                "handle": gramps_obj.handle,
                "old": None,
                "new": object_to_dict(gramps_obj),
            }
        ]
        self.client.post("/transactions/", data=payload, params={"message": message})
        self.created.append((obj_class, gramps_obj.handle))

    def _make_tagged_person(self):
        # get_or_create_tag() mints its own handle server-side -- this
        # test doesn't get to choose it, same as the live report's own
        # tag was whatever the server already happened to be using.
        stable_tag_handle = self.client.get_or_create_tag(STABLE_TAG_NAME)
        self.created.append(("Tag", stable_tag_handle))

        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_P3")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestStableTag")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.marker_tag_handle)
        person.add_tag(stable_tag_handle)
        self._push_add("Person", person, "live test fixture: tagged person")
        return person

    def _force_full_resync(self, db):
        """Directly drive _full_resync_async() to completion -- the same
        method a real push conflict's _resync_after_conflict_async()
        wraps (see that method's own docstring: "a thin, purpose-named
        wrapper around _full_resync_async()") -- without needing to
        manufacture an actual conflicting edit first. self._syncing is
        held for the duration the same way every real caller holds it
        (_start_push(), _poll_tick()), so the background poll timer
        politely skips its own tick instead of racing this one (see
        _poll_tick()'s own "a sync is already running" guard)."""
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

    def test_tag_handle_survives_a_second_resync(self):
        person = self._make_tagged_person()

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)  # bootstrap: first reimport

            local_tag_after_bootstrap = db.get_tag_from_name(STABLE_TAG_NAME)
            self.assertIsNotNone(
                local_tag_after_bootstrap,
                "the tagged person's bootstrap didn't bring the tag over at all",
            )
            handle_after_bootstrap = local_tag_after_bootstrap.handle
            local_person = db.get_person_from_handle(person.handle)
            self.assertIn(handle_after_bootstrap, local_person.get_tag_list())

            # A second, directly-consecutive full resync -- exactly what
            # a real push conflict's _resync_after_conflict_async() would
            # trigger, and exactly the shape the live report hit (three
            # of these within one session, each downloading its own
            # fresh server export).
            self._force_full_resync(db)

            local_tag_after_resync = db.get_tag_from_name(STABLE_TAG_NAME)
            self.assertIsNotNone(
                local_tag_after_resync,
                "the tag vanished from the local mirror after a resync",
            )
            handle_after_resync = local_tag_after_resync.handle
            print(
                f"[tag handle] after bootstrap={handle_after_bootstrap}  "
                f"after resync={handle_after_resync}"
            )
            self.assertEqual(
                handle_after_bootstrap,
                handle_after_resync,
                "the tag's local handle changed across a resync -- "
                "_restabilize_tag_handles() should have kept it stable "
                "regardless of what the server's own export did (see "
                "TODO.md gap 8)",
            )
            # Not a bare len(get_tag_handles()) count: this is a large,
            # shared demo tree with plenty of its own pre-existing Tags
            # unrelated to this test (confirmed live -- a fixed count of
            # 2 failed immediately with 9 real ones present). What
            # matters is that *this specific* tag name has no leftover
            # duplicate from the reimport.
            matching = [
                h
                for h in db.get_tag_handles()
                if db.get_tag_from_handle(h).get_name() == STABLE_TAG_NAME
            ]
            self.assertEqual(
                matching,
                [handle_after_resync],
                "expected exactly one local Tag named "
                f"{STABLE_TAG_NAME!r} -- an extra one means the "
                "reimport's own duplicate was not cleaned up",
            )

            # The real-world consequence, same shape as the birth/death
            # live test: an edit that has nothing to do with the tag
            # should still push cleanly. diff_items() compares the whole
            # object, so a tag_list entry that silently drifted after
            # this resync would make this push conflict too.
            local_person = db.get_person_from_handle(person.handle)
            self.assertEqual(local_person.get_tag_list().count(handle_after_resync), 1)

            with DbTxn("live test: add unrelated attribute", db) as trans:
                p = db.get_person_from_handle(person.handle)
                attr = Attribute()
                attr.set_type("LiveTestTagAttr")
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
                "an edit unrelated to the tag was falsely rejected as a "
                "conflict -- almost certainly caused by the tag's handle "
                "drifting across the resync",
            )
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
