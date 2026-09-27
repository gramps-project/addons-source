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
LIVE test (see README.md): does the real server actually honor
``keys=handle,birth_ref_index,death_ref_index`` on GET /people/, and does
WebApiHandler.get_person_birth_death_indices() still come back with the
right values when it asks for only those three fields instead of a full
Person per row?

tests/test_webapi_client.py's TestPersonBirthDeathIndices only proves the
request is *shaped* right (the right query string, the right dict built
from a canned response) -- it can't prove gramps-web-api's ``keys`` query
arg (GrampsJSONEncoder.response()/extract_object(), see
gramps_webapi/api/resources/base.py) actually filters server-side rather
than being silently ignored, which would make this addon's "slimmed
payload" fix a no-op cutting nothing.
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

from gramps.gen.lib import (  # noqa: E402
    Event,
    EventRef,
    EventRoleType,
    EventType,
    Name,
    Person,
    Surname,
)
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402

from webapi_client import WebApiHandler  # noqa: E402


class TestPersonBirthDeathIndicesKeys(unittest.TestCase):
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

    def _make_person_with_known_indices(self):
        # Two Birth-type refs and two Death-type refs so the true index
        # (1, not the default 0) is unambiguous evidence that the keys=
        # filtered response really carries these two fields through,
        # rather than this test passing by coincidence on an all-zero
        # default.
        birth1 = Event()
        birth1.set_handle(live_harness._new_handle())
        birth1.set_gramps_id("LT_BDK_E1")
        birth1.set_type(EventType.BIRTH)
        self._push_add("Event", birth1, "live test fixture: birth event 1")

        birth2 = Event()
        birth2.set_handle(live_harness._new_handle())
        birth2.set_gramps_id("LT_BDK_E2")
        birth2.set_type(EventType.BIRTH)
        self._push_add("Event", birth2, "live test fixture: birth event 2")

        death1 = Event()
        death1.set_handle(live_harness._new_handle())
        death1.set_gramps_id("LT_BDK_E3")
        death1.set_type(EventType.DEATH)
        self._push_add("Event", death1, "live test fixture: death event 1")

        death2 = Event()
        death2.set_handle(live_harness._new_handle())
        death2.set_gramps_id("LT_BDK_E4")
        death2.set_type(EventType.DEATH)
        self._push_add("Event", death2, "live test fixture: death event 2")

        person = Person()
        person.set_handle(live_harness._new_handle())
        person.set_gramps_id("LT_BDK_P1")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestBirthDeathIndexKeys")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        person.set_primary_name(name)
        person.add_tag(self.tag_handle)

        refs = []
        for event in (birth1, birth2, death1, death2):
            ref = EventRef()
            ref.set_reference_handle(event.handle)
            ref.set_role(EventRoleType.PRIMARY)
            refs.append(ref)
        person.set_event_ref_list(refs)
        person.birth_ref_index = 1
        person.death_ref_index = 1
        self._push_add("Person", person, "live test fixture: birth/death index keys")
        return person

    def test_keys_filtered_request_still_returns_true_indices(self):
        person = self._make_person_with_known_indices()

        handler = WebApiHandler(
            live_harness.SERVER_URL,
            username=live_harness.USERNAME,
            password=live_harness.PASSWORD,
        )
        indices = handler.get_person_birth_death_indices()

        self.assertIn(
            person.handle,
            indices,
            "person missing from the keys=-filtered /people/ listing",
        )
        print(
            f"[birth_death_indices] handle={person.handle} "
            f"expected=(1, 1) got={indices[person.handle]}"
        )
        self.assertEqual(indices[person.handle], (1, 1))


if __name__ == "__main__":
    unittest.main()
