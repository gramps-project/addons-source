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
LIVE test (see README.md): WebApiHandler.push_transaction()'s conflict
detection turns on one exact string match -- webapi_client.py's
_raise_for_push_conflict() reads a 400 response body's
``error.message`` and only raises WebApiPushConflict if it equals
_CONFLICT_MESSAGE ("Object has changed"); any other 400 body re-raises
the plain HTTPError instead, on the theory that it's this addon's own
bug (a malformed payload), not a real conflict to resync from.

tests/test_webapi_client.py's TestPushTransaction covers both branches
(test_object_changed_400_raises_push_conflict,
test_other_400_reasons_are_not_conflicts) entirely against a mocked
HTTPError carrying a hand-built body -- it can prove the *parsing* is
right, not that gramps-web-api's real old_unchanged()/apply_transactions()
(gramps_webapi/api/tasks.py) still spells the message exactly
"Object has changed", still answers 400 (not some other code) for a
stale "old" snapshot, and still answers 400 with a *different* message
(not that exact string) for a payload that's malformed for an unrelated
reason. Any of those drifting would either miss a real conflict (worse:
looks like this addon's own bug and propagates as an unhandled
HTTPError) or misreport an unrelated bug as a resync-worthy conflict.
"""

import os
import sys

import unittest

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG

sys.path.insert(0, live_harness.ADDON_DIR)

from gramps.gen.lib import Name, Person, Surname  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402

from webapi_client import WebApiHandler, WebApiPushConflict  # noqa: E402
from urllib.error import HTTPError  # noqa: E402


class TestPushTransactionSyncConflictDetection(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.handler = WebApiHandler(
            live_harness.SERVER_URL,
            username=live_harness.USERNAME,
            password=live_harness.PASSWORD,
        )
        self.created = []  # [(class_name, handle), ...], for cleanup

    def tearDown(self):
        for obj_class, handle in reversed(self.created):
            self.client.delete_object(obj_class, handle)

    def _make_person(self, gramps_id):
        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id(gramps_id)
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestSyncConflict")
        name.set_surname_list([surname])
        person.set_primary_name(name)
        person.add_tag(self.tag_handle)
        return person

    def test_stale_old_snapshot_raises_push_conflict(self):
        person = self._make_person("LT_SYNC_CONFLICT_P1")
        old_snapshot = object_to_dict(person)
        self.handler.push_transaction(
            [
                {
                    "type": "add",
                    "_class": "Person",
                    "handle": person.handle,
                    "old": None,
                    "new": old_snapshot,
                }
            ],
            message="live test fixture: create person",
        )
        self.created.append(("Person", person.handle))

        # Simulate a concurrent edit by someone else: the server's copy
        # moves on from old_snapshot, but this handler's local "old" (as
        # if it were a mirror that hasn't resynced yet) does not.
        concurrently_edited = dict(old_snapshot)
        concurrently_edited["gender"] = 1
        self.handler.push_transaction(
            [
                {
                    "type": "update",
                    "_class": "Person",
                    "handle": person.handle,
                    "old": old_snapshot,
                    "new": concurrently_edited,
                }
            ],
            message="live test fixture: concurrent edit",
        )

        # Now push against the now-stale old_snapshot -- the real server
        # should reject this with 400 "Object has changed", and the
        # handler should turn that into WebApiPushConflict, not let the
        # raw HTTPError(400) through.
        stale_edit = dict(old_snapshot)
        stale_edit["gender"] = 2
        with self.assertRaises(WebApiPushConflict) as ctx:
            self.handler.push_transaction(
                [
                    {
                        "type": "update",
                        "_class": "Person",
                        "handle": person.handle,
                        "old": old_snapshot,
                        "new": stale_edit,
                    }
                ],
                message="live test: push against a stale snapshot",
            )
        print(f"[conflict] raised as expected: {ctx.exception}")

    def test_malformed_payload_400_is_not_mistaken_for_a_conflict(self):
        # An "add" with a nonsense _class in "new": old_unchanged() passes
        # trivially (no prior object at this handle, old=None), but
        # gramps_object_from_dict() then fails to resolve the class name,
        # which apply_transactions() (gramps_webapi/api/tasks.py) catches
        # and re-aborts as 400 "Error while processing transaction" -- a
        # different message than the conflict sentinel, so this must
        # surface as a plain HTTPError, not WebApiPushConflict.
        bad_handle = live_harness._new_handle()
        with self.assertRaises(HTTPError) as ctx:
            self.handler.push_transaction(
                [
                    {
                        "type": "add",
                        "_class": "Person",
                        "handle": bad_handle,
                        "old": None,
                        "new": {"_class": "NotARealGrampsClass", "handle": bad_handle},
                    }
                ],
                message="live test: deliberately malformed payload",
            )
        print(f"[non-conflict 400] propagated as expected: {ctx.exception}")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
