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
Diagnostic (not a test -- see sweep.py for the same "utility script, not
test_*.py" shape): does gramps-web-api's own POST /exporters/gramps/file
actually mint a different raw handle for the *same* Tag across two
directly-consecutive export requests, with nothing edited in between?

TODO.md gap 8 is explicit that this is inferred, not confirmed by reading
gramps-web-api's own source (out of scope for this addon's repo) --
every live client-side symptom (a Person's tag_list disagreeing across
resyncs, Person/Event/... handles all staying stable meanwhile) is
consistent with it, but nothing had actually pulled two raw exports and
diffed the XML directly. This script does exactly that, once, and prints
the answer -- deliberately not written as an assertion-bearing test:
"the server currently has this bug" is not a property this addon should
pin a passing/failing test suite to, and if gramps-web-api ever fixes it,
this script printing "STABLE" is the desired outcome, not a failure to
chase down.

Bypasses GrampsWebApiDb/ImportXml entirely -- WebApiHandler.download_export()
straight from webapi_client.py, gzip + a plain XML parse -- so nothing
about *this addon's own* reimport handling (set_prefixes(), ImportXml's
handle-preservation logic, this addon's new _restabilize_tag_handles())
is anywhere in the loop. Whatever this prints is the server's own raw
behavior, full stop.
"""

import gzip
import os
import re
import sys
import xml.etree.ElementTree as ET

LIVE_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if LIVE_TESTS_DIR not in sys.path:
    sys.path.insert(0, LIVE_TESTS_DIR)

import live_harness
from live_harness import RestClient, TEST_TAG

sys.path.insert(0, live_harness.ADDON_DIR)

from webapi_client import WebApiHandler  # noqa: E402

DIAGNOSTIC_TAG_NAME = "LiveTestExportHandleDiagnosticTag"


def _tag_handle_by_name(export_bytes, tag_name):
    """{name: handle} isn't needed -- just this one tag's handle, or
    None if the export has no <tag> element with this name at all
    (shouldn't happen once the fixture below has created it server-
    side, but a plain XML parse should never raise for a well-formed
    export either way)."""
    try:
        xml_bytes = gzip.decompress(export_bytes)
    except OSError:
        xml_bytes = export_bytes  # not actually gzipped -- use as-is
    root = ET.fromstring(xml_bytes)
    # The exported document's default namespace makes every tag name
    # {namespace}tag -- match on the local name only rather than
    # threading the exact namespace URI (version-specific, e.g.
    # ".../xml/1.7.1/") through this script.
    for tag_elem in root.iter():
        if tag_elem.tag.rsplit("}", 1)[-1] != "tag":
            continue
        if tag_elem.get("name") == tag_name:
            return tag_elem.get("handle")
    return None


def main():
    client = RestClient()
    marker_handle = client.get_or_create_tag(TEST_TAG)
    diagnostic_handle = client.get_or_create_tag(DIAGNOSTIC_TAG_NAME)
    print(
        f"[fixture] {DIAGNOSTIC_TAG_NAME!r} created server-side as {diagnostic_handle}"
    )

    try:
        handler = WebApiHandler(
            live_harness.SERVER_URL,
            username=live_harness.USERNAME,
            password=live_harness.PASSWORD,
        )

        print("Requesting export #1 ...")
        export_1 = handler.download_export()
        handle_1 = _tag_handle_by_name(export_1, DIAGNOSTIC_TAG_NAME)
        print(f"  export #1 handle: {handle_1}")

        print("Requesting export #2 (no edits in between) ...")
        export_2 = handler.download_export()
        handle_2 = _tag_handle_by_name(export_2, DIAGNOSTIC_TAG_NAME)
        print(f"  export #2 handle: {handle_2}")

        if handle_1 is None or handle_2 is None:
            print(
                "INCONCLUSIVE: the diagnostic tag was missing from at least "
                "one export -- can't compare."
            )
        elif handle_1 == handle_2:
            print(
                "STABLE: both exports agree on this Tag's handle. "
                "TODO.md gap 8's server-side theory does not reproduce "
                "right now for this account/tree -- worth re-checking "
                "gap 8's status before assuming it's still live."
            )
        else:
            print(
                "CHURNED: the same Tag got a different handle on each "
                "export, confirming TODO.md gap 8's theory directly "
                "against the server's own raw XML, independent of "
                "anything this addon does with it."
            )
    finally:
        client.delete_object("Tag", diagnostic_handle)


if __name__ == "__main__":
    main()
