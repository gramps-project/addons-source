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
LIVE test (see README.md): when a local edit conflicts, gets resynced and
retried, and *that retry conflicts again* (grampswebapidb.py's
_after_conflict_resync(), the `if undo or is_retry:` "Giving up..."
branch), is the original edit left with any trace at all -- a "message"
Note, anything -- or does it vanish with nothing but a log line?

Also exercises the related, narrower claim in _record_conflict_notes()'s
own docstring: that a genuine field-level collision's conflict-note is
"safe even if *that* push itself hits a conflict, since attaching a note
is a list-valued change merge() already unions correctly." This test
forces a *real* scalar collision (both sides set Person.gender to
different values) so that claim is exercised for real, under the real
GLibTaskRunner/IoRunner async timing (not InlineTaskRunner's
fully-synchronous collapse, which cannot reproduce the self._syncing
timing window this claim depends on -- see live_harness.py and the
addon's tests/ suite for that contrast).

The *first* conflict is a genuinely real one: a real, independent REST
edit lands on the server before the local edit's first push, so that
push's own "Object has changed" rejection is the server's real answer,
not a mock.

The *second* conflict -- on the retry's own nested push specifically --
is injected deterministically instead of by racing a second real edit:
webapi_client.py's IoRunner starts a fresh background thread per network
call (confirmed by reading taskrunner.py), so the retry's own nested push
and the conflict-note's own best-effort send
(_send_note_payload_best_effort()) run concurrently with no ordering
guarantee between them -- a real property of the production code. A
second real out-of-band edit races unpredictably against *both*, which
were what this test's first draft actually hit (the note-send losing the
race instead of the intended target, nondeterministically). Matching on
the retry's own fixed commit message ("Retry local change after server
conflict") and raising WebApiPushConflict for that one call only keeps
every other push -- the original edit's, and the note's own send --
genuinely real, while still deterministically exercising
_after_conflict_resync()'s give-up branch.
"""

import os
import shutil
import sys
import time
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


class TestRepeatedConflictNoteTrail(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.created = []

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _make_person(self):
        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_P2")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestRepeatedConflict")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.tag_handle)
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
            "/transactions/", data=payload, params={"message": "live test fixture: person"}
        )
        self.created.append(("Person", person.handle))
        return person, object_to_dict(person)

    def _out_of_band_gender_flip(self, handle, known_dict, new_gender_value, label):
        """A real REST edit, independent of the addon under test --
        simulates a second, concurrent editor.

        ``known_dict`` must be the object_to_dict()/to_json() shape (what
        old_unchanged() actually compares against server-side) -- *not* a
        GET /people/<handle> response, which serializes via
        GrampsJSONEncoder.extract_object() instead: a materially different
        shape (no "_class" tags, GrampsType fields flattened to their
        display string, ...) that old_unchanged()'s diff_items() will
        reject outright. See grampswebapidb.py's own module docstring on
        why those two shapes aren't interchangeable. Tests here therefore
        track the known-good object_to_dict() state themselves (starting
        from creation) rather than re-fetching it over REST.

        Returns the new known_dict, for the caller to chain further edits
        against.
        """
        import copy

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

    def test_two_real_conflicts_in_a_row_leave_some_trace_or_dont(self):
        person, known_dict = self._make_person()

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)  # bootstrap while the person is still gender=UNKNOWN

            # *Now* make the mirror stale, after it's already loaded --
            # this is what makes the addon's own first push conflict for
            # real (doing this before load() would just have the
            # bootstrap absorb it, and the first push would never
            # conflict at all -- caught by this test's own first draft).
            known_dict = self._out_of_band_gender_flip(
                person.handle, known_dict, 1, "live test: out-of-band edit #1 (gender->MALE)"
            )

            # Force conflict #2 deterministically, on the *retry's own*
            # nested push specifically (grampswebapidb.py's
            # _retry_after_conflict() commits under the fixed description
            # "Retry local change after server conflict") -- see the
            # module docstring on why this is injected rather than raced
            # with a second real out-of-band edit: IoRunner starts a
            # fresh thread per network call, so the retry's own push and
            # the conflict-note's own best-effort send run concurrently
            # with no ordering guarantee, and a real second edit landed
            # unpredictably against either one. Every *other* push here
            # (the original edit's, and the note's own send) still goes
            # out for real.
            real_push = db.web_client.push_transaction

            def hooked_push(payload, **kwargs):
                if kwargs.get("message") == "Retry local change after server conflict":
                    raise grampswebapidb.WebApiPushConflict("Object has changed")
                return real_push(payload, **kwargs)

            db.web_client.push_transaction = hooked_push

            with DbTxn("live test: local edit racing a hot object", db) as trans:
                p = db.get_person_from_handle(person.handle)
                p.set_gender(Person.FEMALE)  # collides with out-of-band edit #1's value
                attr = Attribute()
                attr.set_type("LiveTestRepeatedConflictAttr")
                attr.set_value("should this survive?")
                p.add_attribute(attr)
                db.commit_person(p, trans)

            # Let every async chain this triggered (push -> conflict ->
            # resync -> retry -> push -> conflict -> resync -> give up ->
            # any note-commit -> its own push/queue) actually finish.
            live_harness.pump_glib(20)


            server_person = self.client.get(f"/people/{person.handle}")
            server_gender = server_person.get("gender")
            server_notes = server_person.get("note_list", [])
            print(f"[server] gender={server_gender!r}  note_list={server_notes!r}")

            note_texts = []
            for note_handle in server_notes:
                note = self.client.get(f"/notes/{note_handle}")
                note_texts.append(note.get("text", {}).get("string", ""))
                self.created.append(("Note", note_handle))
            print(f"[server] note text(s): {note_texts}")

            has_message_note = any(
                "conflicted" in t.lower() or "message" in t.lower()
                for t in note_texts
            )
            self.assertTrue(
                note_texts,
                "the local edit was discarded by two real conflicts in a "
                "row, and no trace (no Note) was left on the server-side "
                "object at all -- see _after_conflict_resync()'s give-up "
                "branch",
            )
            self.assertTrue(
                has_message_note,
                f"note(s) exist but none look like a conflict/message "
                f"note: {note_texts!r}",
            )

        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
