#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Douglas S. Blank
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

"""
Standalone tests for PDFForms/generate_pdf.py.

No Gramps installation required.  Skip automatically when reportlab is absent.

Run with::

    python3 -m unittest PDFForms.tests.test_generate_pdf -v
    # or directly:
    python3 PDFForms/tests/test_generate_pdf.py
"""

import os
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

# Make ``import generate_pdf`` resolve to PDFForms/generate_pdf.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import generate_pdf
except ImportError as exc:
    raise unittest.SkipTest("reportlab not available: %s" % exc)

from generate_pdf import (
    _col_widths,
    _required_avail_w,
    _split_camel,
    _wrap_text,
    generate_form_pdf,
    list_forms,
    load_form,
    MIN_COL_W,
    MAX_COL_W,
)


# ---------------------------------------------------------------------------
# Helpers shared by multiple test classes
# ---------------------------------------------------------------------------

def _make_xml_dir(tmp_dir, xml_text):
    """Write a custom.xml into *tmp_dir* and return the dir path."""
    path = os.path.join(tmp_dir, "custom.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    return tmp_dir


SIMPLE_MULTI_XML = textwrap.dedent("""\
    <?xml version='1.0' encoding='UTF-8'?>
    <forms>
        <form id='TEST1' type='Census' title='Test Census' date='1800-01-01'>
            <heading><_attribute>County</_attribute></heading>
            <section role='Primary' type='multi'>
                <column><_attribute>Name</_attribute><size>50</size></column>
                <column><_attribute>Age</_attribute><size>25</size></column>
                <column><_attribute>Occupation</_attribute><size>25</size></column>
            </section>
        </form>
    </forms>
""")

MIXED_SECTIONS_XML = textwrap.dedent("""\
    <?xml version='1.0' encoding='UTF-8'?>
    <forms>
        <form id='TEST2' type='Marriage' title='Test Marriage'>
            <section role='Family' type='family' title='Groom/Bride'>
                <column><_attribute>Name</_attribute><size>60</size></column>
                <column><_attribute>Age</_attribute><size>20</size></column>
                <column><_attribute>Occupation</_attribute><size>20</size></column>
            </section>
            <section role='Witness' type='person' title='Witness'>
                <column><_attribute>Name</_attribute><size>70</size></column>
                <column><_attribute>Residence</_attribute><size>30</size></column>
            </section>
        </form>
    </forms>
""")


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

class TestListAndLoadForms(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _make_xml_dir(self.tmp, SIMPLE_MULTI_XML)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_list_forms_finds_form(self):
        forms = list_forms(self.tmp)
        ids = [f[0] for f in forms]
        self.assertIn("TEST1", ids)

    def test_load_form_returns_correct_title(self):
        form = load_form("TEST1", self.tmp)
        self.assertIsNotNone(form)
        self.assertEqual(form["title"], "Test Census")

    def test_load_form_headings(self):
        form = load_form("TEST1", self.tmp)
        self.assertEqual(form["headings"], ["County"])

    def test_load_form_section_columns(self):
        form = load_form("TEST1", self.tmp)
        cols = form["sections"][0]["columns"]
        self.assertEqual([c["attribute"] for c in cols], ["Name", "Age", "Occupation"])

    def test_load_form_missing_returns_none(self):
        self.assertIsNone(load_form("NOSUCHFORM", self.tmp))


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

class TestColWidths(unittest.TestCase):

    def _cols(self, sizes):
        return [{"size": s} for s in sizes]

    def test_proportional_allocation(self):
        widths = _col_widths(self._cols([50, 50]), 100)
        self.assertAlmostEqual(widths[0], widths[1], places=1)
        self.assertAlmostEqual(sum(widths), 100, places=1)

    def test_zero_sizes_give_equal_widths(self):
        widths = _col_widths(self._cols([0, 0, 0]), 90)
        self.assertAlmostEqual(widths[0], 30, places=1)

    def test_minimum_clamp_applied(self):
        # One huge column forces the other to MIN_COL_W
        widths = _col_widths(self._cols([99, 1]), 200)
        self.assertGreaterEqual(min(widths), MIN_COL_W)

    def test_maximum_clamp_applied(self):
        # Tiny available width: all columns clamped down
        widths = _col_widths(self._cols([50, 50]), 10000)
        self.assertLessEqual(max(widths), MAX_COL_W)


class TestSplitCamelAndWrap(unittest.TestCase):

    def test_split_camel_basic(self):
        self.assertEqual(_split_camel("WindowRooms"), "Window Rooms")

    def test_split_camel_already_spaced(self):
        self.assertEqual(_split_camel("hello world"), "hello world")

    def test_wrap_short_text_stays_one_line(self):
        from reportlab.pdfgen import canvas
        import io
        # Build a throwaway canvas just for stringWidth()
        c = canvas.Canvas(io.BytesIO())
        lines = _wrap_text("Name", 200, c, "Helvetica", 8)
        self.assertEqual(len(lines), 1)

    def test_wrap_long_text_breaks(self):
        from reportlab.pdfgen import canvas
        import io
        c = canvas.Canvas(io.BytesIO())
        long_text = "This Is A Very Long Column Header That Should Wrap"
        lines = _wrap_text(long_text, 30, c, "Helvetica", 8)
        self.assertGreater(len(lines), 1)


# ---------------------------------------------------------------------------
# PDF generation — integration smoke tests
# ---------------------------------------------------------------------------

class TestGenerateFormPDF(unittest.TestCase):

    def setUp(self):
        self.xml_tmp = tempfile.mkdtemp()
        self.out_tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.xml_tmp)
        shutil.rmtree(self.out_tmp)

    def _out(self, name="out.pdf"):
        return os.path.join(self.out_tmp, name)

    def _form(self, xml, form_id):
        _make_xml_dir(self.xml_tmp, xml)
        return load_form(form_id, self.xml_tmp)

    def _assert_valid_pdf(self, path):
        self.assertTrue(os.path.exists(path), "output file was not created")
        with open(path, "rb") as f:
            header = f.read(4)
        self.assertEqual(header, b"%PDF", "output is not a PDF file")

    # -- basic section types ------------------------------------------------

    def test_multi_section(self):
        form = self._form(SIMPLE_MULTI_XML, "TEST1")
        generate_form_pdf(form, rows=5, output_path=self._out())
        self._assert_valid_pdf(self._out())

    def test_person_and_family_sections(self):
        form = self._form(MIXED_SECTIONS_XML, "TEST2")
        generate_form_pdf(form, rows=1, output_path=self._out())
        self._assert_valid_pdf(self._out())

    def test_many_rows(self):
        form = self._form(SIMPLE_MULTI_XML, "TEST1")
        generate_form_pdf(form, rows=100, output_path=self._out())
        self._assert_valid_pdf(self._out())

    # -- regression: new_page() was undefined (NameError on page overflow) --

    def test_page_break_does_not_raise(self):
        """
        Force the page-break branch to fire by suppressing height expansion,
        then verify a valid PDF is still produced.

        Before the fix, `new_page()` was called but never defined, raising
        NameError: name 'new_page' is not defined.
        """
        # Build a form with enough sections to overflow a single A4 page.
        many_sections = "\n".join(
            f"""\
            <section role='Sec{i}' type='multi'>
                <column><_attribute>Name</_attribute><size>50</size></column>
                <column><_attribute>Age</_attribute><size>50</size></column>
            </section>"""
            for i in range(15)
        )
        xml = textwrap.dedent(f"""\
            <?xml version='1.0' encoding='UTF-8'?>
            <forms>
                <form id='PAGED' type='Census' title='Paged Form'>
                    {many_sections}
                </form>
            </forms>
        """)
        form = self._form(xml, "PAGED")
        out = self._out()
        # Patch _required_page_height to return 0 so ph stays at base A4
        # height, guaranteeing the 15-section form overflows onto a new page.
        with patch.object(generate_pdf, "_required_page_height", return_value=0):
            generate_form_pdf(form, rows=1, output_path=out)
        self._assert_valid_pdf(out)


if __name__ == "__main__":
    unittest.main()
