#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       Douglas Blank
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""Tests for ``goql_completion.py``, the adapter from
gramps-object-query-language's own completer to the popup's item shape --
pure logic, no GTK, no database. GOQL's completer has its own extensive
tests; these check the adaptation (line/column, the suffix to insert, the
hint fields) and a few end-to-end results through it.

Run with::

    python3 -m unittest GOQLFilter.tests.test_goql_completion -v
"""

import os
import sys
import unittest
from unittest.mock import patch

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import goql_completion
    from goql_completion import _cursor_offset, get_completion_items
except ImportError as exc:
    raise unittest.SkipTest(
        "goql_completion import failed (likely missing "
        "gramps-object-query-language): %s" % exc
    )

if goql_completion.complete is None:
    raise unittest.SkipTest("gramps-object-query-language older than 0.5.13")


def _at_end(source, namespace="Person"):
    lines = source.split("\n")
    return get_completion_items(source, len(lines), len(lines[-1]), namespace)


def _names(items):
    return [item["name"] for item in items]


# ------------------------------------------------------------
#
# CursorOffsetTest
#
# ------------------------------------------------------------
class CursorOffsetTest(unittest.TestCase):
    def test_first_line(self):
        self.assertEqual(_cursor_offset("gender == 1", 1, 6), 6)

    def test_later_line_counts_earlier_lines_and_newlines(self):
        self.assertEqual(_cursor_offset("gender == 1\nand bi", 2, 6), 18)

    def test_out_of_range_is_clamped(self):
        self.assertEqual(_cursor_offset("ab\ncd", 9, 99), 5)


# ------------------------------------------------------------
#
# AdapterTest
#
# ------------------------------------------------------------
class AdapterTest(unittest.TestCase):
    def test_complete_is_the_rest_of_the_name(self):
        [item] = _at_end("birth.date.so")
        self.assertEqual(item["name"], "sortval")
        self.assertEqual(item["complete"], "rtval")
        self.assertEqual(item["cursor_offset"], 0)
        self.assertEqual(item["kind"], "field")
        self.assertEqual(item["detail"], "integer")

    def test_multiline_source(self):
        items = get_completion_items("gender == 1\nand birth.date.so", 2, 17, "Person")
        self.assertEqual(_names(items), ["sortval"])

    def test_cursor_mid_text(self):
        items = get_completion_items("birth.date.so > 0", 1, 13, "Person")
        self.assertEqual(items[0]["complete"], "rtval")

    def test_unknown_namespace_returns_no_completions(self):
        self.assertEqual(_at_end("bi", "NoSuchType"), [])

    def test_older_goql_turns_completion_off(self):
        with patch.object(goql_completion, "complete", None):
            self.assertEqual(_at_end("bi"), [])


# ------------------------------------------------------------
#
# ThroughGoqlTest -- a few end-to-end results, to catch an API change
#
# ------------------------------------------------------------
class ThroughGoqlTest(unittest.TestCase):
    def test_start_of_a_condition_has_no_operators(self):
        names = _names(_at_end(""))
        self.assertIn("birth", names)
        self.assertNotIn("==", names)

    def test_named_values_for_a_coded_field(self):
        self.assertEqual(_names(_at_end("type.value == ", "Event")), ["EventType."])
        self.assertEqual(_names(_at_end("gender == Person.M")), ["MALE"])

    def test_a_complete_name_gets_what_follows_it(self):
        [item] = _at_end("primary_name.date")
        self.assertEqual(item["name"], "date.")
        self.assertEqual(item["complete"], ".")

    def test_function_arguments(self):
        self.assertEqual(_names(_at_end("Date(")), ['"'])

    def test_family_namespace_differs_from_person(self):
        self.assertIn("father", _names(_at_end("fa", "Family")))
        self.assertNotIn("father", _names(_at_end("fa", "Person")))


if __name__ == "__main__":
    unittest.main()
