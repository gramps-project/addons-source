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

"""Tests for ``goql_highlight.py``'s token classification -- pure logic, no
GTK, no database.

Run with::

    python3 -m unittest GOQLFilter.tests.test_goql_highlight -v
"""

import os
import sys
import unittest

ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    from goql_highlight import classify_tokens
except ImportError as exc:
    raise unittest.SkipTest(
        "goql_highlight import failed (likely missing "
        "gramps-object-query-language): %s" % exc
    )


def _spans_by_text(source):
    """(category, matched substring) pairs, in source order -- easier to
    assert against than raw line/column spans."""
    lines = source.splitlines()
    result = []
    for start_line, start_col, end_line, end_col, category in classify_tokens(source):
        text = (
            lines[start_line][start_col:end_col]
            if start_line == end_line
            else "<multiline>"
        )
        result.append((category, text))
    return result


# ------------------------------------------------------------
#
# ClassifyTokensTest
#
# ------------------------------------------------------------
class ClassifyTokensTest(unittest.TestCase):
    def test_classifies_operator_constant_class_keyword_string_and_number(self):
        source = "gender == Person.MALE and 'Anderson' in primary_name.surname_list[0].surname"
        spans = _spans_by_text(source)
        self.assertIn(("operator", "=="), spans)
        self.assertIn(("constant-class", "Person"), spans)
        self.assertIn(("keyword", "and"), spans)
        self.assertIn(("string", "'Anderson'"), spans)
        self.assertIn(("keyword", "in"), spans)
        self.assertIn(("number", "0"), spans)

    def test_plain_field_names_are_not_classified(self):
        spans = _spans_by_text("gender == Person.MALE")
        categories_by_text = dict((text, category) for category, text in spans)
        self.assertNotIn("gender", categories_by_text)

    def test_incomplete_expression_still_yields_tokens_before_the_break(self):
        """An unterminated string is the normal state of this buffer mid-typing,
        not an error to surface -- whatever tokenized cleanly before it is
        still returned."""
        spans = _spans_by_text("gender == Person.MALE and 'Anders")
        self.assertIn(("operator", "=="), spans)
        self.assertIn(("constant-class", "Person"), spans)
        self.assertIn(("keyword", "and"), spans)

    def test_empty_source_yields_no_spans(self):
        self.assertEqual(list(classify_tokens("")), [])

    def test_like_date_exists_count_are_keywords(self):
        spans = _spans_by_text(
            "like(x, 'A%') and exists(children) and count(events) > 1"
        )
        categories_by_text = dict((text, category) for category, text in spans)
        self.assertEqual(categories_by_text.get("like"), "keyword")
        self.assertEqual(categories_by_text.get("exists"), "keyword")
        self.assertEqual(categories_by_text.get("count"), "keyword")

    def test_comparison_operators_are_all_recognized(self):
        for op in ("==", "!=", "<", "<=", ">", ">="):
            spans = _spans_by_text("gender %s 1" % op)
            self.assertIn(("operator", op), spans, "missing operator %r" % op)


if __name__ == "__main__":
    unittest.main()
