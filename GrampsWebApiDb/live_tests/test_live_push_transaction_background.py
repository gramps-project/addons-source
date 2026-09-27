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
LIVE test (see README.md): does WebApiHandler.push_transaction(background=True)
actually round-trip against the real server -- both the success path and
the conflict path -- the way push_transaction()'s own docstring says a
backgrounded push must behave identically to a synchronous one?

tests/test_webapi_client.py's TestPushTransaction covers this with a
mocked 202 body naming a task id, then a mocked GET /tasks/<id> answering
"state": "SUCCESS" or "state": "FAILURE" with a canned result_object --
proving push_transaction()/wait_for_task() parse whatever shape the
test hands them, not that a real gramps-web-api server's actual
Celery-task status body still uses those exact keys
("task"/"id" in the 202 body; "state"/"result_object" in the task
status), and not that a real conflict on the backgrounded path still
gets there the way the docstring describes: run_task() re-aborting the
inline (no Celery configured) path as HTTP 500 with the same
{"error": {"message": "Object has changed"}} body a synchronous 400
carries, checked in push_transaction()'s own `except HTTPError` branch,
distinct from a *genuinely* queued task's FAILURE state, which
wait_for_task() parses via _task_error_message()/_CONFLICT_MESSAGE
instead. This test doesn't know or control which of those two the demo
server takes (whether it has a Celery queue configured) -- it just
asserts the outcome either way actually produces, so it exercises
whichever real path the server has.
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


class TestPushTransactionBackground(unittest.TestCase):
    def setUp(self):
        self.client = RestClient()
        self.tag_handle = self.client.get_or_create_tag(TEST_TAG)
        self.handler = WebApiHandler(
            live_harness.SERVER_URL,
            username=live_harness.USERNAME,
            password=live_harness.PASSWORD,
        )
        self.assertTrue(
            self.handler.supports_background_transactions(),
            "server reports it doesn't support background transactions -- "
            "this test needs gramps-web-api >= BACKGROUND_MIN_API_VERSION",
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
        surname.set_surname("LiveTestBackgroundPush")
        name.set_surname_list([surname])
        person.set_primary_name(name)
        person.add_tag(self.tag_handle)
        return person

    def test_background_push_completes_successfully(self):
        person = self._make_person("LT_BGPUSH_P1")
        payload = [
            {
                "type": "add",
                "_class": "Person",
                "handle": person.handle,
                "old": None,
                "new": object_to_dict(person),
            }
        ]
        # No exception means push_transaction() correctly recognized
        # whatever the server answered (200 inline, or 202 + a real
        # wait_for_task() poll to SUCCESS) as done, not a failure.
        self.handler.push_transaction(
            payload, background=True, message="live test: background push"
        )
        self.created.append(("Person", person.handle))

        server_person = self.client.get(f"/people/{person.handle}")
        print(f"[background push] server gramps_id: {server_person.get('gramps_id')}")
        self.assertEqual(server_person.get("gramps_id"), "LT_BGPUSH_P1")

    def test_background_push_with_stale_old_raises_push_conflict(self):
        person = self._make_person("LT_BGPUSH_P2")
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
                background=True,
                message="live test: stale background push",
            )
        print(f"[background conflict] raised as expected: {ctx.exception}")


if __name__ == "__main__":
    unittest.main()
