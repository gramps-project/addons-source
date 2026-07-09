"""
Tests for the extract_header_comment() utility in script_utils.

extract_header_comment() pulls the leading '#'-comment block out of a
script's source, for use as a fallback Open-dialog preview when a file
has no catalogued entry in SCRIPT_DESCRIPTIONS. It lives in script_utils.py
(no GTK or Gramps imports required) precisely so it can be imported and
tested directly, without pulling in the full (GTK-dependent) GrampyScript
module.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from script_utils import extract_header_comment


class TestExtractHeaderComment(unittest.TestCase):
    def test_single_line_header(self):
        source = "# Title\n\nfor p in people():\n    row(p)\n"
        self.assertEqual(extract_header_comment(source), "Title")

    def test_multi_line_header(self):
        source = "# Title\n#\n# A longer description.\n\nrow(1)\n"
        self.assertEqual(
            extract_header_comment(source), "Title\n\nA longer description."
        )

    def test_no_header_returns_empty(self):
        source = "for p in people():\n    row(p)\n"
        self.assertEqual(extract_header_comment(source), "")

    def test_leading_blank_lines_before_header_are_skipped(self):
        source = "\n\n# Title\n\nrow(1)\n"
        self.assertEqual(extract_header_comment(source), "Title")

    def test_stops_at_first_code_line(self):
        source = "# Title\nrow(1)  # not part of the header\n"
        self.assertEqual(extract_header_comment(source), "Title")

    def test_empty_source_returns_empty(self):
        self.assertEqual(extract_header_comment(""), "")

    def test_hash_only_lines_become_blank_lines(self):
        source = "# Title\n#\n# More.\n"
        self.assertEqual(extract_header_comment(source), "Title\n\nMore.")


if __name__ == "__main__":
    unittest.main()
