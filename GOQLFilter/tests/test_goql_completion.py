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

"""Tests for ``goql_completion.py``'s completion source -- pure logic, no
GTK, no database, matching the module's own "no display needed" design.

Run with::

    python3 -m unittest GOQLFilter.tests.test_goql_completion -v
"""

import os
import sys
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    from goql_completion import get_completion_items
except ImportError as exc:
    raise unittest.SkipTest(
        "goql_completion import failed (likely missing "
        "gramps-object-query-language): %s" % exc
    )


def _names(source, line, column, namespace):
    return sorted(
        item["name"] for item in get_completion_items(source, line, column, namespace)
    )


# ------------------------------------------------------------
#
# TopLevelCompletionTest
#
# ------------------------------------------------------------
class TopLevelCompletionTest(unittest.TestCase):
    def test_person_top_level_includes_columns_relationships_and_keywords(self):
        names = _names("", 1, 0, "Person")
        for expected in ("gender", "birth", "death", "families", "and", "or", "not"):
            self.assertIn(expected, names)

    def test_person_top_level_includes_constant_class_names(self):
        names = _names("", 1, 0, "Person")
        self.assertIn("Person", names)
        self.assertIn("EventType", names)

    def test_top_level_includes_comparison_operators(self):
        """A blank Tab press shows the comparison operators too -- most are
        a single character, so they only ever surface with an empty
        prefix, but they should still be there to see."""
        names = _names("", 1, 0, "Person")
        for op in ("==", "!=", "<", "<=", ">", ">="):
            self.assertIn(op, names)

    def test_family_namespace_differs_from_person(self):
        family_names = _names("", 1, 0, "Family")
        self.assertIn("father", family_names)
        self.assertIn("mother", family_names)
        self.assertIn("children", family_names)
        self.assertNotIn("birth", family_names)
        self.assertNotIn("death", family_names)

    def test_top_level_prefix_filters_matches(self):
        names = _names("gen", 1, 3, "Person")
        self.assertIn("gender", names)
        self.assertNotIn("birth", names)

    def test_unknown_namespace_returns_no_completions(self):
        names = _names("", 1, 0, "NotARealType")
        self.assertEqual(names, [])


# ------------------------------------------------------------
#
# DottedConstantCompletionTest
#
# ------------------------------------------------------------
class DottedConstantCompletionTest(unittest.TestCase):
    def test_person_dot_lists_gender_constants(self):
        source = "gender == Person."
        names = _names(source, 1, len(source), "Person")
        self.assertEqual(names, sorted(["FEMALE", "MALE", "OTHER", "UNKNOWN"]))

    def test_person_dot_prefix_filters_to_matching_constants(self):
        source = "gender == Person.MA"
        items = get_completion_items(source, 1, len(source), "Person")
        self.assertEqual([(i["name"], i["complete"]) for i in items], [("MALE", "LE")])

    def test_unrecognized_class_name_before_dot_returns_no_completions(self):
        source = "primary_name."
        names = _names(source, 1, len(source), "Person")
        self.assertEqual(names, [])

    def test_dotted_completion_ignores_the_active_namespace(self):
        """`Date.MOD_ABOUT` is valid regardless of which namespace
        (Person/Family/...) the expression is being written for -- the
        constant-class table isn't namespace-scoped."""
        source = "birth.date.modifier == Date."
        names = _names(source, 1, len(source), "Family")
        self.assertIn("MOD_ABOUT", names)


if __name__ == "__main__":
    unittest.main()
