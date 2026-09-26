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
LIVE test (see README.md): does a Tag's local handle survive the *exact*
shape the addons-source#1030 report actually happened in -- a real push
conflict, a real resync, a real retry, a real second conflict, a second
real resync -- rather than a resync forced directly by test code
(test_live_tag_handle_stable_across_resync.py) or a conflict-retry chain
on an object with no tag at all
(test_live_repeated_conflict_note_trail.py, this file's own direct
template)?

TODO.md gap 8's "further update" ran four isolated checks (a plain tag,
this addon's own message/todo-open tags, tag-list reordering, two
genuinely legacy tags) and found all four stable -- but every one of
them was a resync triggered directly by test code, sequentially, with
nothing else going on. This test instead drives the real
_push_payload_async() -> conflict -> _resync_after_conflict_async() ->
_retry_after_conflict() -> conflict -> resync -> give-up chain on a
tagged Person, under real GLibTaskRunner/IoRunner async timing (see
test_live_repeated_conflict_note_trail.py's own docstring on why that
distinction matters -- InlineTaskRunner's synchronous collapse cannot
reproduce this timing at all). Two resyncs happen inside this one
chain, back to back, exactly matching the report's own shape.

Captures every WARNING _log_conflict_field_diffs()/_walk_conflict_diff()
emit during the whole chain (the same diagnostic mechanism that
surfaced the original "tag_list[0] differs" report) via
self.assertLogs(), so this also directly answers "would the original
diagnostic still flag anything for this tag today" -- not just "does
the handle happen to match at the end."
"""

import copy
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

STABLE_TAG_NAME = "LiveTestConflictChainTag"


class TestTagSurvivesRealConflictRetryChain(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.marker_tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.stable_tag_handle = self.client.get_or_create_tag(STABLE_TAG_NAME)
        self.created = [("Tag", self.stable_tag_handle)]

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _make_person(self):
        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_P7")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestConflictChainTagPerson")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.marker_tag_handle)
        person.add_tag(self.stable_tag_handle)
        person.set_gender(Person.UNKNOWN)
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
        return person, object_to_dict(person)

    def _out_of_band_gender_flip(self, handle, known_dict, new_gender_value, label):
        """Same real, independent REST edit test_live_repeated_conflict_
        note_trail.py uses to make the first push conflict for real --
        see that file's own docstring on why known_dict, not a fresh
        GET, is what has to be diffed against here."""
        new = copy.deepcopy(known_dict)
        new["gender"] = new_gender_value
        payload = [
            {
                "type": "update",
                "_class": "Person",
                "handle": handle,
                "old": known_dict,
                "new": new,
            }
        ]
        self.client.post("/transactions/", data=payload, params={"message": label})
        return new

    def test_tag_handle_survives_a_real_two_conflict_retry_chain(self):
        person, known_dict = self._make_person()

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)  # bootstrap while gender is still UNKNOWN

            handle_after_bootstrap = db.get_tag_from_name(STABLE_TAG_NAME).handle
            local_person = db.get_person_from_handle(person.handle)
            self.assertIn(handle_after_bootstrap, local_person.get_tag_list())

            # Makes the mirror stale *after* it's already loaded, so the
            # addon's own first push conflicts for real -- see
            # test_live_repeated_conflict_note_trail.py's own comment on
            # why this has to happen after load(), not before.
            known_dict = self._out_of_band_gender_flip(
                person.handle,
                known_dict,
                1,
                "live test: out-of-band edit #1 (gender->MALE)",
            )

            # Force conflict #2 deterministically, on the retry's own
            # nested push specifically -- same injection
            # test_live_repeated_conflict_note_trail.py uses, for the
            # same reason (a second real out-of-band edit races
            # unpredictably against both the retry's push and the
            # conflict-note's own best-effort send).
            real_push = db.web_client.push_transaction

            def hooked_push(payload, **kwargs):
                if kwargs.get("message") == "Retry local change after server conflict":
                    raise grampswebapidb.WebApiPushConflict("Object has changed")
                return real_push(payload, **kwargs)

            db.web_client.push_transaction = hooked_push

            with self.assertLogs(".grampswebapidb", level="WARNING") as cm:
                with DbTxn("live test: local edit racing a hot object", db) as trans:
                    p = db.get_person_from_handle(person.handle)
                    p.set_gender(Person.FEMALE)  # collides with out-of-band edit #1
                    attr = Attribute()
                    attr.set_type("LiveTestConflictChainAttr")
                    attr.set_value("hello")
                    p.add_attribute(attr)
                    db.commit_person(p, trans)

                # Let the whole chain -- push -> conflict -> resync ->
                # retry -> push -> conflict -> resync -> give up -> any
                # note-commit -- actually finish. Two full resyncs
                # happen inside this one window.
                live_harness.pump_glib(20)

            tag_list_warnings = [line for line in cm.output if "tag_list" in line]
            print("[captured conflict-diff warnings]")
            for line in cm.output:
                print(f"  {line}")
            self.assertFalse(
                tag_list_warnings,
                "the real conflict-retry chain's own diagnostic flagged "
                f"a tag_list disagreement: {tag_list_warnings!r} -- gap "
                "8 reproduced under real timing",
            )

            handle_after_chain = db.get_tag_from_name(STABLE_TAG_NAME).handle
            local_person = db.get_person_from_handle(person.handle)
            print(
                f"[tag handle] after bootstrap={handle_after_bootstrap}  "
                f"after real conflict-retry chain={handle_after_chain}  "
                f"person.tag_list={local_person.get_tag_list()}"
            )
            self.assertEqual(
                handle_after_bootstrap,
                handle_after_chain,
                "the tag's local handle changed across the real "
                "conflict-retry chain (two resyncs) -- gap 8 reproduced "
                "under real timing",
            )
            self.assertIn(handle_after_chain, local_person.get_tag_list())
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
