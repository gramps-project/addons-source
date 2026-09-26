#!/usr/bin/env python3
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
Diagnostic (not a test -- see sweep.py/diagnose_export_tag_handle_stability
.py for the same "utility script, printing an answer, not asserting a
must-stay-broken behavior" shape). TODO.md gap 8's "Update (2026-09-26)"
narrowed the still-open theories behind the live tag_list[0] mismatch
report to two, neither checked directly yet:

1. Does this addon's own `message`/`todo-open` convention tags
   (grampswebapidb.py's MESSAGE_TAG_NAME/MESSAGE_TODO_OPEN_TAG_NAME,
   shared with gramps-connect's notesApi.ts) behave like the plain tag
   diagnose_export_tag_handle_stability.py already found stable, or do
   *these specific* tags churn on export where an ordinary one doesn't
   -- plausible if gramps-web-api implements this one convention as a
   synthesized/derived view over something else, rather than a real
   persisted Tag row.

2. `_walk_conflict_diff()`'s list comparison is positional (`zip(old,
   new)`), so a Person with more than one Tag whose *order* changes
   between two exports -- each tag's own identity otherwise perfectly
   stable -- would present exactly as "tag_list[0] differs" too, and
   _restabilize_tag_handles() (keyed on name, not position) does
   nothing for a pure reordering. Never checked: does the order gramps-
   web-api serializes a multi-tag tag_list in actually stay fixed
   across two directly-consecutive exports of the same, unedited data?

Both checked here the same way as diagnose_export_tag_handle_stability.py:
two direct WebApiHandler.download_export() calls, no edits in between,
raw XML compared -- this addon's own reimport/restabilization code is
nowhere in the loop, so whatever this prints is the server's own raw
behavior.
"""

import gzip
import os
import sys
import xml.etree.ElementTree as ET

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG

sys.path.insert(0, live_harness.ADDON_DIR)

from gramps.gen.lib import Name, Person, Surname  # noqa: E402
from gramps.gen.lib.json_utils import object_to_dict  # noqa: E402
from webapi_client import WebApiHandler  # noqa: E402

#: This addon's own convention tag names (grampswebapidb.py) -- see
#: _get_or_create_tag()/_record_conflict_notes() there.
MESSAGE_TAG_NAME = "message"
MESSAGE_TODO_OPEN_TAG_NAME = "todo-open"

ORDER_TEST_PERSON_ID = "LT_DIAG_ORDER"


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _tag_handles_by_name(export_bytes):
    """{name: handle} for every <tag> element in one export."""
    try:
        xml_bytes = gzip.decompress(export_bytes)
    except OSError:
        xml_bytes = export_bytes
    root = ET.fromstring(xml_bytes)
    return {
        elem.get("name"): elem.get("handle")
        for elem in root.iter()
        if _local(elem.tag) == "tag"
    }


def _person_tagref_order(export_bytes, gramps_id):
    """The exact ordered list of <tagref hlink="..."/> values under the
    <person id=gramps_id> element -- None if that person isn't in this
    export at all."""
    try:
        xml_bytes = gzip.decompress(export_bytes)
    except OSError:
        xml_bytes = export_bytes
    root = ET.fromstring(xml_bytes)
    for person_elem in root.iter():
        if _local(person_elem.tag) != "person":
            continue
        if person_elem.get("id") != gramps_id:
            continue
        return [
            child.get("hlink")
            for child in person_elem
            if _local(child.tag) == "tagref"
        ]
    return None


def check_message_tags(handler, client):
    print("=" * 70)
    print("Check 1: this addon's own 'message'/'todo-open' tags")
    print("=" * 70)
    # get_or_create_tag() finds these if a prior real session already
    # created them (very likely on this shared demo tree -- see
    # _record_conflict_notes() and this repo's own live-test history),
    # or creates them fresh via the same plain object-add transaction
    # diagnose_export_tag_handle_stability.py already found stable --
    # any difference here is specifically about *these* tags/names, not
    # about how they were created.
    message_handle = client.get_or_create_tag(MESSAGE_TAG_NAME)
    todo_handle = client.get_or_create_tag(MESSAGE_TODO_OPEN_TAG_NAME)
    print(f"[fixture] {MESSAGE_TAG_NAME!r} -> {message_handle}")
    print(f"[fixture] {MESSAGE_TODO_OPEN_TAG_NAME!r} -> {todo_handle}")

    print("Requesting export #1 ...")
    by_name_1 = _tag_handles_by_name(handler.download_export())
    print("Requesting export #2 (no edits in between) ...")
    by_name_2 = _tag_handles_by_name(handler.download_export())

    for name in (MESSAGE_TAG_NAME, MESSAGE_TODO_OPEN_TAG_NAME):
        h1, h2 = by_name_1.get(name), by_name_2.get(name)
        print(f"  {name!r}: export#1={h1}  export#2={h2}")
        if h1 is None or h2 is None:
            print(f"  INCONCLUSIVE for {name!r}: missing from at least one export.")
        elif h1 == h2:
            print(f"  STABLE for {name!r}.")
        else:
            print(
                f"  CHURNED for {name!r} -- unlike an ordinary tag, this "
                "convention tag's handle is NOT stable across exports."
            )


def check_tag_list_order(handler, client):
    print()
    print("=" * 70)
    print("Check 2: a Person's multi-tag tag_list order")
    print("=" * 70)
    marker_handle = client.get_or_create_tag(TEST_TAG)
    # Three fresh, distinctly-named tags -- order among them has no
    # other reason to be meaningful, so any instability is purely about
    # export/serialization order, not tag identity.
    tag_names = ["LiveTestOrderTagAlpha", "LiveTestOrderTagBeta", "LiveTestOrderTagGamma"]
    tag_handles = [client.get_or_create_tag(name) for name in tag_names]
    for name, handle in zip(tag_names, tag_handles):
        print(f"[fixture] {name!r} -> {handle}")

    person = Person()
    person.set_handle(live_harness._new_handle())
    person.set_gramps_id(ORDER_TEST_PERSON_ID)
    name_obj = Name()
    surname = Surname()
    surname.set_surname("LiveTestTagOrderDiagnostic")
    name_obj.set_surname_list([surname])
    name_obj.set_first_name("Addon")
    person.set_primary_name(name_obj)
    person.add_tag(marker_handle)
    for handle in tag_handles:
        person.add_tag(handle)
    payload = [
        {
            "type": "add",
            "_class": "Person",
            "handle": person.handle,
            "old": None,
            "new": object_to_dict(person),
        }
    ]
    client.post(
        "/transactions/",
        data=payload,
        params={"message": "live diagnostic fixture: tag-order person"},
    )
    print(f"[fixture] person {ORDER_TEST_PERSON_ID} -> {person.handle}")

    try:
        print("Requesting export #1 ...")
        order_1 = _person_tagref_order(handler.download_export(), ORDER_TEST_PERSON_ID)
        print(f"  export #1 tagref order: {order_1}")
        print("Requesting export #2 (no edits in between) ...")
        order_2 = _person_tagref_order(handler.download_export(), ORDER_TEST_PERSON_ID)
        print(f"  export #2 tagref order: {order_2}")

        if order_1 is None or order_2 is None:
            print("INCONCLUSIVE: the diagnostic person was missing from an export.")
        elif order_1 == order_2:
            print(
                "STABLE: identical tagref order both times. Reordering does "
                "not reproduce right now for this account/tree."
            )
        elif sorted(order_1) == sorted(order_2):
            print(
                "REORDERED: same four tag handles both times, but in a "
                "different order -- this alone would present as "
                "'tag_list[0] differs' (or [1]/[2]/[3]) to "
                "_walk_conflict_diff(), with no tag identity actually "
                "unstable and nothing _restabilize_tag_handles() (keyed "
                "on name, not position) can do about it."
            )
        else:
            print(
                "DIFFERENT SETS entirely (not just reordered) -- see the "
                "raw order lists above; this doesn't match either of "
                "gap 8's two open theories cleanly."
            )
    finally:
        client.delete_object("Person", person.handle)
        for handle in tag_handles:
            client.delete_object("Tag", handle)


def main():
    client = RestClient()
    handler = WebApiHandler(
        live_harness.SERVER_URL,
        username=live_harness.USERNAME,
        password=live_harness.PASSWORD,
    )
    check_message_tags(handler, client)
    check_tag_list_order(handler, client)


if __name__ == "__main__":
    main()
