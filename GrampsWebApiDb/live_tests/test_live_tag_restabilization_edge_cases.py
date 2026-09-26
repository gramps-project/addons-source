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
LIVE test (see README.md): three variations on _restabilize_tag_handles()
(grampswebapidb.py, TODO.md gap 8) that
test_live_tag_handle_stable_across_resync.py doesn't cover -- that test
only exercises the exact reported shape (same tag, same name, same
content, just a churned handle). These check the edge cases the fix's
own name-based identity has to get right, or at least not get
dangerously wrong, once real editing enters the picture:

1. The server-side tag's *content* (not just its handle) genuinely
   changes between two resyncs -- does the revived local object under
   the old, stable handle pick up the new content, or does it get stuck
   showing whatever the tag looked like at bootstrap?

2. The tag is *renamed* on the server between two resyncs --
   _restabilize_tag_handles() keys identity on name, so this is outside
   what it can recognize as "the same tag" by design (see that
   function's own docstring). This checks that a rename doesn't
   corrupt anything or produce a false conflict, only (at worst) leaves
   a harmless, unreferenced local Tag under the old name.

3. The tag is attached to a Family, not a Person -- confirms the fix's
   loop over "every non-Tag primary object" actually covers more than
   the one type every other test here happens to use.
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
from gramps.gen.lib import Attribute, Family, Name, Person, Surname  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402


class _LiveTagRestabilizationTestCase(unittest.TestCase):
    """Shared plumbing for this file's three scenarios."""

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

    def _push_update(self, obj_class, handle, old_dict, new_dict, message):
        payload = [
            {
                "type": "update",
                "_class": obj_class,
                "handle": handle,
                "old": old_dict,
                "new": new_dict,
            }
        ]
        self.client.post("/transactions/", data=payload, params={"message": message})

    def _open_mirror(self):
        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        db.load(mirror_dir)  # bootstrap: first reimport
        return db, mirror_dir

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

    def _push_unrelated_edit_and_check(self, db, person_handle):
        """Same real-world-consequence check every other live test in
        this directory ends with: an edit unrelated to whatever this
        test is actually about should still push cleanly."""
        with DbTxn("live test: add unrelated attribute", db) as trans:
            p = db.get_person_from_handle(person_handle)
            attr = Attribute()
            attr.set_type("LiveTestEdgeCaseAttr")
            attr.set_value("hello")
            p.add_attribute(attr)
            db.commit_person(p, trans)
        live_harness.pump_glib(5)
        server_person = self.client.get(f"/people/{person_handle}")
        return any(
            a.get("value") == "hello" for a in server_person.get("attribute_list", [])
        )


class TestTagContentUpdateSurvivesRestabilization(_LiveTagRestabilizationTestCase):
    TAG_NAME = "LiveTestContentUpdateTag"

    def test_new_content_is_adopted_under_the_stable_old_handle(self):
        tag_handle = self.client.get_or_create_tag(self.TAG_NAME)
        self.created.append(("Tag", tag_handle))
        tag_before = self.client.get(f"/tags/{tag_handle}")

        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_P5")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestContentUpdate")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.marker_tag_handle)
        person.add_tag(tag_handle)
        self._push_add("Person", person, "live test fixture: person with updatable tag")

        db, mirror_dir = self._open_mirror()
        try:
            handle_after_bootstrap = db.get_tag_from_name(self.TAG_NAME).handle

            # A real, out-of-band content edit -- exactly what a user
            # changing the tag's color in gramps-connect's own UI would
            # produce -- between the bootstrap and the next resync.
            tag_old_dict = {
                "_class": "Tag",
                "handle": tag_handle,
                "name": tag_before["name"],
                "color": tag_before["color"],
                "priority": tag_before["priority"],
                "change": tag_before["change"],
            }
            tag_new_dict = dict(tag_old_dict, color="#ff0000000000")
            self._push_update(
                "Tag", tag_handle, tag_old_dict, tag_new_dict, "live test: recolor tag"
            )

            self._force_full_resync(db)

            local_tag = db.get_tag_from_name(self.TAG_NAME)
            print(
                f"[tag] handle after bootstrap={handle_after_bootstrap}  "
                f"after resync={local_tag.handle}  color={local_tag.get_color()!r}"
            )
            self.assertEqual(
                local_tag.handle,
                handle_after_bootstrap,
                "the tag's local handle should stay stable across the "
                "resync regardless of the content edit",
            )
            self.assertEqual(
                local_tag.get_color(),
                "#ff0000000000",
                "the tag's real content edit (color) was not adopted -- "
                "restabilization revived stale bootstrap-time content "
                "under the stable handle instead of the reimport's own "
                "current data",
            )
            pushed = self._push_unrelated_edit_and_check(db, person.handle)
            print(f"[push result] attribute reached the server: {pushed}")
            self.assertTrue(pushed)
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


class TestTagRenameDoesNotCorruptTheMirror(_LiveTagRestabilizationTestCase):
    OLD_NAME = "LiveTestRenameTagOld"
    NEW_NAME = "LiveTestRenameTagNew"

    def test_rename_leaves_a_clean_mirror_and_no_false_conflict(self):
        tag_handle = self.client.get_or_create_tag(self.OLD_NAME)
        self.created.append(("Tag", tag_handle))
        tag_before = self.client.get(f"/tags/{tag_handle}")

        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_P6")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestRenameTag")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.marker_tag_handle)
        person.add_tag(tag_handle)
        self._push_add("Person", person, "live test fixture: person with renamable tag")

        db, mirror_dir = self._open_mirror()
        try:
            self.assertIsNotNone(db.get_tag_from_name(self.OLD_NAME))

            tag_old_dict = {
                "_class": "Tag",
                "handle": tag_handle,
                "name": tag_before["name"],
                "color": tag_before["color"],
                "priority": tag_before["priority"],
                "change": tag_before["change"],
            }
            tag_new_dict = dict(tag_old_dict, name=self.NEW_NAME)
            self._push_update(
                "Tag", tag_handle, tag_old_dict, tag_new_dict, "live test: rename tag"
            )

            self._force_full_resync(db)

            # _restabilize_tag_handles() keys identity on name (see its
            # own docstring) -- a rename is, by design, indistinguishable
            # from "the old tag is gone and a new one showed up" here.
            # What matters is that this doesn't corrupt anything: the
            # Person ends up pointing at a real, correctly-named local
            # Tag, and nothing about this makes an unrelated edit
            # falsely conflict.
            local_person = db.get_person_from_handle(person.handle)
            new_tag = db.get_tag_from_name(self.NEW_NAME)
            self.assertIsNotNone(
                new_tag, "the renamed tag never made it into the local mirror"
            )
            print(
                f"[tag] renamed tag's local handle={new_tag.handle}  "
                f"person.tag_list={local_person.get_tag_list()}"
            )
            self.assertIn(
                new_tag.handle,
                local_person.get_tag_list(),
                "the person's tag_list doesn't reference the renamed "
                "tag's local handle at all",
            )

            pushed = self._push_unrelated_edit_and_check(db, person.handle)
            print(f"[push result] attribute reached the server: {pushed}")
            self.assertTrue(
                pushed,
                "an edit unrelated to the tag rename was falsely "
                "rejected as a conflict",
            )
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


class TestTagOnAFamilyIsAlsoRestabilized(_LiveTagRestabilizationTestCase):
    TAG_NAME = "LiveTestFamilyTag"

    def test_family_tag_handle_survives_a_resync(self):
        tag_handle = self.client.get_or_create_tag(self.TAG_NAME)
        self.created.append(("Tag", tag_handle))

        family = Family()
        family.set_handle(live_harness._new_handle())
        family.set_gramps_id("LT_F1")
        family.add_tag(self.marker_tag_handle)
        family.add_tag(tag_handle)
        self._push_add("Family", family, "live test fixture: tagged family")

        db, mirror_dir = self._open_mirror()
        try:
            handle_after_bootstrap = db.get_tag_from_name(self.TAG_NAME).handle
            local_family = db.get_family_from_handle(family.handle)
            self.assertIn(handle_after_bootstrap, local_family.get_tag_list())

            self._force_full_resync(db)

            local_tag = db.get_tag_from_name(self.TAG_NAME)
            local_family = db.get_family_from_handle(family.handle)
            print(
                f"[family tag] after bootstrap={handle_after_bootstrap}  "
                f"after resync={local_tag.handle}  "
                f"family.tag_list={local_family.get_tag_list()}"
            )
            self.assertEqual(local_tag.handle, handle_after_bootstrap)
            self.assertIn(local_tag.handle, local_family.get_tag_list())
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
