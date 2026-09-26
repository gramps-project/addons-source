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
LIVE test (see README.md): does a genuinely ambiguous birth/death event
arrangement -- one ImportXml's "first PRIMARY-role BIRTH-type ref"
heuristic guesses wrong -- actually survive a real GrampsWebApiDb
bootstrap resync against the live server incorrectly, and does that then
cause a *false* push conflict on a completely unrelated edit (add an
attribute), exactly as grampswebapidb.py's own module docstring predicts
for _snapshot_birth_death_indices()?

This is the direct, unmocked version of the reasoning chain investigated
in chat for the original bug report -- that investigation's own decisive
test (reimporting the *actual* reported person's real export, diffed
against the live server's own object_to_dict()) came back clean, ruling
the theory out for that specific person. This test instead *constructs* a
person deliberately shaped to trigger the known gap, to check whether the
mechanism is real at all, independent of whether it explains that one bug
report.
"""

import json
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

from gramps.gen.lib import (  # noqa: E402
    Attribute,
    Event,
    EventRef,
    EventRoleType,
    EventType,
    Name,
    Person,
    Surname,
)
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402


class TestBirthDeathIndexBootstrap(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
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

    def _make_ambiguous_person(self):
        """Two Birth-type events, both role=Primary (a real, legal Gramps
        state -- e.g. two disputed birth dates from different sources),
        with the person's *true* birth_ref_index deliberately pointing at
        the second one. ImportXml's recompute heuristic (see
        _snapshot_birth_death_indices()'s docstring) always picks the
        *first* PRIMARY-role BIRTH-type ref, i.e. index 0 -- wrong here by
        construction."""
        birth1 = Event()
        birth1.set_handle(live_harness._new_handle())
        birth1.set_gramps_id("LT_E1")
        birth1.set_type(EventType.BIRTH)
        self._push_add("Event", birth1, "live test fixture: birth event 1")

        birth2 = Event()
        birth2.set_handle(live_harness._new_handle())
        birth2.set_gramps_id("LT_E2")
        birth2.set_type(EventType.BIRTH)
        self._push_add("Event", birth2, "live test fixture: birth event 2")

        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_P1")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestAmbiguousBirth")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.tag_handle)

        ref1 = EventRef()
        ref1.set_reference_handle(birth1.handle)
        ref1.set_role(EventRoleType.PRIMARY)
        ref2 = EventRef()
        ref2.set_reference_handle(birth2.handle)
        ref2.set_role(EventRoleType.PRIMARY)
        person.set_event_ref_list([ref1, ref2])
        # The deliberate, true choice: birth2 (index 1), not birth1.
        person.birth_ref_index = 1
        self._push_add("Person", person, "live test fixture: ambiguous-birth person")
        return person

    def test_bootstrap_resync_preserves_or_loses_true_birth_index(self):
        person = self._make_ambiguous_person()

        key = mint_api_key()
        import os

        os.environ["GRAMPS_WEB_API_KEY"] = key
        grampswebapidb = import_webapidb()

        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)
            local_person = db.get_person_from_handle(person.handle)
            local_index = local_person.birth_ref_index
            print(
                f"[birth_ref_index] server truth=1  local mirror after "
                f"bootstrap={local_index}"
            )
            if local_index != 1:
                print(
                    "CONFIRMED: bootstrap resync lost the true birth_ref_index "
                    "-- ImportXml's heuristic (index 0) won, matching the "
                    "known gap in _bootstrap_full_resync()."
                )

            # Now the real-world consequence: an edit that has *nothing* to
            # do with birth/death should still push cleanly if the index
            # is right, and should conflict if it's wrong (see module
            # docstring: diff_items() treats birth_ref_index as ordinary
            # content, so it rides along in every push's full "old"
            # snapshot).
            from gramps.gen.db import DbTxn

            with DbTxn("live test: add unrelated attribute", db) as trans:
                p = db.get_person_from_handle(person.handle)
                attr = Attribute()
                attr.set_type("LiveTestAttr")
                attr.set_value("hello")
                p.add_attribute(attr)
                db.commit_person(p, trans)

            live_harness.pump_glib(3)

            server_person = self.client.get(f"/people/{person.handle}")
            pushed = any(
                a.get("value") == "hello" for a in server_person.get("attribute_list", [])
            )
            print(f"[push result] attribute reached the server: {pushed}")
            self.assertEqual(
                local_index,
                1,
                "bootstrap resync produced the wrong birth_ref_index locally "
                "(ImportXml's document-order heuristic, not the true "
                "server value) -- see _bootstrap_full_resync()'s known gap",
            )
            self.assertTrue(
                pushed,
                "an edit unrelated to birth/death was falsely rejected as a "
                "conflict -- almost certainly caused by the wrong "
                "birth_ref_index riding along in the push's full 'old' "
                "snapshot",
            )
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
