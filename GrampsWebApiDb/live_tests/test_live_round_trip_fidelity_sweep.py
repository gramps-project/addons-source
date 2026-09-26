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
LIVE test (see README.md): a battery of the "other round-trip-fidelity
candidates" TODO.md gap 7 lists but nobody had checked yet -- each one
would show up the same way the confirmed ones did (birth_ref_index/
death_ref_index, gramps_id widening, Unicode NFC, Tag handle churn): a
field that came back from a real bootstrap resync silently different
from what was actually pushed, which diff_items() would treat as a real
edit on this object's very next push regardless of what that edit
actually touched.

All fixtures are pushed once and bootstrapped through a single real
WebApiDB mirror -- one round trip, several independent checks -- rather
than a separate bootstrap per concern, which is the expensive part of
every test in this directory. Kept as one test method per concern
anyway (not one giant method) so a failure names exactly which fidelity
gap reproduced, but they share one class-level fixture pass.

Checks, and why each was picked from TODO.md's list:

- Empty string vs. None/omitted-element ambiguity on an Attribute value.
- Note styled-text tag ranges/line-ending normalization: "\\r\\n" cannot
  survive a resync at all (XML 1.0 itself mandates normalizing it to
  "\\n" in any compliant parser -- confirmed live, now TODO.md gap 9),
  so this check instead confirms the *fix*'s guarantee --
  _normalize_line_endings() -- that the local mirror always lands on
  "\\n"-only consistently, the same form a resync forces regardless.
- Place lat/long precision (stored as a string in Gramps, per TODO.md,
  so unlikely but "worth remembering if it ever comes up").
- Event ref list order on a Person with two events -- the general case
  gap 8's tag-list-order theory is a specific instance of; TODO.md
  lists this among the "lower confidence" candidates.
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

from gramps.gen.lib import (  # noqa: E402
    Attribute,
    Event,
    EventRef,
    EventRoleType,
    EventType,
    Name,
    Note,
    NoteType,
    Person,
    Place,
    Surname,
)
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402


class TestRoundTripFidelitySweep(unittest.TestCase):
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

    def test_round_trip_fidelity_sweep(self):
        # -- Fixture: Person with an explicit empty-string attribute value
        empty_value_person = Person()
        empty_value_person.set_handle(live_harness._new_handle())
        empty_value_person.set_gramps_id("LT_DIAG_EMPTY")
        name = Name()
        surname = Surname()
        surname.set_surname("LiveTestEmptyValue")
        name.set_surname_list([surname])
        name.set_first_name("Addon")
        empty_value_person.set_primary_name(name)
        empty_value_person.add_tag(self.tag_handle)
        attr = Attribute()
        attr.set_type("LiveTestEmptyAttr")
        attr.set_value("")
        empty_value_person.add_attribute(attr)
        self._push_add(
            "Person", empty_value_person, "live diagnostic fixture: empty attribute value"
        )

        # -- Fixture: Note with CRLF line endings
        crlf_note = Note()
        crlf_note.set_handle(live_harness._new_handle())
        crlf_note.set_gramps_id("LT_DIAG_CRLF")
        crlf_note.set_type(NoteType.GENERAL)
        crlf_note.set("Line one\r\nLine two\r\nLine three")
        crlf_note.add_tag(self.tag_handle)
        self._push_add("Note", crlf_note, "live diagnostic fixture: CRLF note")

        # -- Fixture: Place with a high-precision lat/long
        precise_place = Place()
        precise_place.set_handle(live_harness._new_handle())
        precise_place.set_gramps_id("LT_DIAG_PLACE")
        precise_place.set_title("LiveTestPrecisePlace")
        precise_place.set_latitude("51.50735123456789")
        precise_place.set_longitude("-0.12775987654321")
        precise_place.add_tag(self.tag_handle)
        self._push_add("Place", precise_place, "live diagnostic fixture: precise place")

        # -- Fixture: Person with two events, checked for ref-list order
        event_a = Event()
        event_a.set_handle(live_harness._new_handle())
        event_a.set_gramps_id("LT_DIAG_EA")
        event_a.set_type(EventType.OCCUPATION)
        self._push_add("Event", event_a, "live diagnostic fixture: event A")
        event_b = Event()
        event_b.set_handle(live_harness._new_handle())
        event_b.set_gramps_id("LT_DIAG_EB")
        event_b.set_type(EventType.RESIDENCE)
        self._push_add("Event", event_b, "live diagnostic fixture: event B")

        order_person = Person()
        order_person.set_handle(live_harness._new_handle())
        order_person.set_gramps_id("LT_DIAG_ORDER2")
        name2 = Name()
        surname2 = Surname()
        surname2.set_surname("LiveTestEventOrder")
        name2.set_surname_list([surname2])
        name2.set_first_name("Addon")
        order_person.set_primary_name(name2)
        order_person.add_tag(self.tag_handle)
        ref_a = EventRef()
        ref_a.set_reference_handle(event_a.handle)
        ref_a.set_role(EventRoleType.PRIMARY)
        ref_b = EventRef()
        ref_b.set_reference_handle(event_b.handle)
        ref_b.set_role(EventRoleType.PRIMARY)
        order_person.set_event_ref_list([ref_a, ref_b])
        self._push_add(
            "Person", order_person, "live diagnostic fixture: event ref order person"
        )

        os.environ["GRAMPS_WEB_API_KEY"] = mint_api_key()
        grampswebapidb = import_webapidb()
        mirror_dir = new_mirror_dir()
        db = grampswebapidb.WebApiDB()
        try:
            db.load(mirror_dir)  # bootstrap: the one real reimport this test uses

            with self.subTest("empty string attribute value"):
                local = db.get_person_from_handle(empty_value_person.handle)
                values = [
                    a.get_value()
                    for a in local.get_attribute_list()
                    if a.get_type().string == "LiveTestEmptyAttr"
                ]
                print(f"[empty-value] pushed='' -> local={values!r}")
                self.assertEqual(
                    values,
                    [""],
                    "an explicit empty-string Attribute value did not "
                    "survive a bootstrap resync as an empty string",
                )

            with self.subTest("CRLF line endings"):
                # Confirmed live 2026-09-26 (TODO.md gap 9): "\r\n"
                # cannot survive a bootstrap resync byte-for-byte --
                # XML 1.0's own spec mandates any compliant parser
                # collapse it to "\n" in character data, so this is
                # structural, not a bug to chase on the reimport side.
                # The fix (_normalize_line_endings(), grampswebapidb.py)
                # is instead about *consistency*: this local mirror must
                # always land on "\n"-only, the same form ImportXml's
                # own parsing already forces here, so a later edit made
                # *through this addon* (which now also normalizes on
                # every commit) never disagrees with what a resync
                # would produce.
                local_note = db.get_note_from_handle(crlf_note.handle)
                local_text = local_note.get()
                expected = crlf_note.get().replace("\r\n", "\n")
                print(f"[crlf] pushed={crlf_note.get()!r}  local={local_text!r}")
                self.assertEqual(
                    local_text,
                    expected,
                    "a Note's line endings did not come back consistently "
                    "normalized to '\\n' after a bootstrap resync -- see "
                    "TODO.md gap 9",
                )

            with self.subTest("place lat/long precision"):
                local_place = db.get_place_from_handle(precise_place.handle)
                print(
                    f"[place] pushed lat={precise_place.get_latitude()!r} "
                    f"long={precise_place.get_longitude()!r}  "
                    f"local lat={local_place.get_latitude()!r} "
                    f"long={local_place.get_longitude()!r}"
                )
                self.assertEqual(local_place.get_latitude(), precise_place.get_latitude())
                self.assertEqual(
                    local_place.get_longitude(), precise_place.get_longitude()
                )

            with self.subTest("event ref list order"):
                local_order_person = db.get_person_from_handle(order_person.handle)
                local_order = [
                    ref.ref for ref in local_order_person.get_event_ref_list()
                ]
                pushed_order = [event_a.handle, event_b.handle]
                print(f"[event order] pushed={pushed_order}  local={local_order}")
                self.assertEqual(
                    local_order,
                    pushed_order,
                    "event_ref_list order did not survive a bootstrap "
                    "resync -- see TODO.md gap 7's 'reference-list "
                    "reordering' candidate",
                )
        finally:
            db.close()
            shutil.rmtree(mirror_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
