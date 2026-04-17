#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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

"""
Unit tests for ``form_validator`` — the pure-Python validation layer
for Form addon XML definition files.

These tests do not touch Gramps or GTK, so they run in every CI job.

Run with::

    python3 -m unittest Form.tests.test_form_validator -v
"""

# ------------------------
# Python modules
# ------------------------
import os
import sys
import tempfile
import textwrap
import unittest
import xml.dom.minidom

# ------------------------
# Gramps specific
# ------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from form_validator import (
    parse_and_validate,
    split_family_title,
    validate_form_dom,
    VALID_SECTION_TYPES,
)


def _dom_from_string(xml_text: str) -> xml.dom.minidom.Document:
    """Parse an XML string into a DOM for validator testing."""
    return xml.dom.minidom.parseString(xml_text)


# ---------------------------------------------------------------------------
# split_family_title — belt-and-braces helper used by FamilySection
# ---------------------------------------------------------------------------
class TestSplitFamilyTitle(unittest.TestCase):
    """
    Regression coverage for Gramps bug 11707 — ``FamilySection`` used to
    crash with ``ValueError: not enough values to unpack (expected 2,
    got 1)`` when a form's ``<section type='family'>`` title did not
    contain a ``/`` separator.
    """

    def test_two_parts(self):
        self.assertEqual(split_family_title("Groom/Bride"), ("Groom", "Bride"))

    def test_no_separator_returns_empty_second(self):
        self.assertEqual(split_family_title("Couple"), ("Couple", ""))

    def test_empty_string_returns_two_empties(self):
        self.assertEqual(split_family_title(""), ("", ""))

    def test_only_separator(self):
        self.assertEqual(split_family_title("/"), ("", ""))

    def test_leading_separator(self):
        self.assertEqual(split_family_title("/Bride"), ("", "Bride"))

    def test_trailing_separator(self):
        self.assertEqual(split_family_title("Groom/"), ("Groom", ""))

    def test_multiple_separators_only_split_once(self):
        self.assertEqual(split_family_title("A/B/C"), ("A", "B/C"))

    def test_whitespace_preserved(self):
        self.assertEqual(
            split_family_title(" Groom / Bride "),
            (" Groom ", " Bride "),
        )


# ---------------------------------------------------------------------------
# validate_form_dom — happy path
# ---------------------------------------------------------------------------
class TestValidateFormDomValid(unittest.TestCase):

    def test_minimal_valid_form(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='Test Census'>
                    <section role='Primary' type='multi'/>
                </form>
            </forms>
        """))
        self.assertEqual(validate_form_dom(dom), [])

    def test_valid_family_section_with_slashed_title(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Marriage' title='Test Marriage'>
                    <section role='Family' type='family' title='Groom/Bride'/>
                </form>
            </forms>
        """))
        self.assertEqual(validate_form_dom(dom), [])

    def test_valid_person_section_without_title(self):
        """Person sections may legitimately omit the title attribute."""
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='Test'>
                    <section role='Primary' type='person'/>
                </form>
            </forms>
        """))
        self.assertEqual(validate_form_dom(dom), [])

    def test_empty_forms_element_is_valid(self):
        dom = _dom_from_string("<forms/>")
        self.assertEqual(validate_form_dom(dom), [])


# ---------------------------------------------------------------------------
# validate_form_dom — structural errors
# ---------------------------------------------------------------------------
class TestValidateFormDomErrors(unittest.TestCase):

    def test_missing_forms_root(self):
        dom = _dom_from_string("<other/>")
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)
        self.assertIn("<forms>", errors[0])

    def test_form_missing_id_attribute(self):
        dom = _dom_from_string("<forms><form type='Census' title='x'/></forms>")
        errors = validate_form_dom(dom)
        self.assertTrue(any("missing required attribute 'id'" in e for e in errors))

    def test_form_missing_title_attribute(self):
        dom = _dom_from_string("<forms><form id='F1' type='Census'/></forms>")
        errors = validate_form_dom(dom)
        self.assertTrue(any("missing required attribute 'title'" in e for e in errors))

    def test_form_missing_type_attribute(self):
        dom = _dom_from_string("<forms><form id='F1' title='x'/></forms>")
        errors = validate_form_dom(dom)
        self.assertTrue(any("missing required attribute 'type'" in e for e in errors))

    def test_section_missing_role_attribute(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section type='person'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertTrue(any("'role'" in e for e in errors))

    def test_section_empty_role_attribute(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section role='' type='person'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertTrue(any("'role'" in e for e in errors))

    def test_section_missing_type_attribute(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section role='Primary'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertTrue(any("'type'" in e for e in errors))

    def test_section_empty_type_attribute(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section role='Primary' type=''/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertTrue(any("'type'" in e for e in errors))

    def test_section_invalid_type(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section role='Primary' type='bogus'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid type 'bogus'", errors[0])
        for valid in VALID_SECTION_TYPES:
            self.assertIn(valid, errors[0])

    def test_section_type_is_case_sensitive(self):
        """
        A real custom.xml in the wild used ``type='Person'`` instead of
        ``type='person'``. The validator rejects it so the user sees a
        clear error rather than silently loading a broken form.
        """
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='AusCemIndex' type='AusCemIndex' title='x'>
                    <section role='Primary' type='Person'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid type 'Person'", errors[0])

    def test_family_section_without_title_is_rejected(self):
        """
        Reproduction of bug 11707 at the validation layer: a family
        section without a slashed title produces a clear error instead
        of a ValueError crash in the GUI.
        """
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Marriage' title='x'>
                    <section role='Family' type='family'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)
        self.assertIn("Name1/Name2", errors[0])

    def test_family_section_with_single_part_title_is_rejected(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Marriage' title='x'>
                    <section role='Family' type='family' title='Couple'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)
        self.assertIn("Couple", errors[0])

    def test_family_section_with_blank_part_is_rejected(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Marriage' title='x'>
                    <section role='Family' type='family' title='Groom/'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)

    def test_family_section_with_three_parts_is_rejected(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Marriage' title='x'>
                    <section role='Family' type='family' title='A/B/C'/>
                </form>
            </forms>
        """))
        errors = validate_form_dom(dom)
        self.assertEqual(len(errors), 1)

    def test_multiple_errors_aggregated(self):
        dom = _dom_from_string(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section role='A' type='bogus'/>
                    <section type='person'/>
                </form>
                <form title='Unnamed' type='Census'/>
            </forms>
        """))
        errors = validate_form_dom(dom)
        # 1 for invalid type + 1 for missing role + 1 for missing id
        self.assertGreaterEqual(len(errors), 3)


# ---------------------------------------------------------------------------
# parse_and_validate — file-level entry point
# ---------------------------------------------------------------------------
class TestParseAndValidate(unittest.TestCase):

    def _write(self, content: str) -> str:
        """Write a temporary XML file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".xml")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.remove, path)
        return path

    def test_valid_file(self):
        path = self._write(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Census' title='x'>
                    <section role='Primary' type='person'/>
                </form>
            </forms>
        """))
        dom, errors = parse_and_validate(path)
        self.assertIsNotNone(dom)
        self.assertEqual(errors, [])

    def test_xml_syntax_error_reports_cleanly(self):
        path = self._write("<forms><form><unclosed></forms>")
        dom, errors = parse_and_validate(path)
        self.assertIsNone(dom)
        self.assertEqual(len(errors), 1)
        self.assertIn("XML syntax error", errors[0])

    def test_missing_file_reports_cleanly(self):
        dom, errors = parse_and_validate("/nonexistent/path.xml")
        self.assertIsNone(dom)
        self.assertEqual(len(errors), 1)

    def test_invalid_structure_returns_errors_and_dom(self):
        path = self._write(textwrap.dedent("""\
            <forms>
                <form id='F1' type='Marriage' title='x'>
                    <section role='Family' type='family' title='NoSlash'/>
                </form>
            </forms>
        """))
        dom, errors = parse_and_validate(path)
        self.assertIsNotNone(dom)
        self.assertEqual(len(errors), 1)


# ---------------------------------------------------------------------------
# Sanity: the shipped built-in definition files must validate
# ---------------------------------------------------------------------------
class TestShippedDefinitionFilesValidate(unittest.TestCase):
    """
    Every built-in ``form_*.xml`` file shipped with the addon must pass
    validation.  If this test fails, the addon would refuse to load one
    of its own definition files for end users.
    """

    FORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_all_builtin_form_files_validate(self):
        import glob

        files = sorted(glob.glob(os.path.join(self.FORM_DIR, "form_*.xml")))
        self.assertGreater(len(files), 0, "no form_*.xml files discovered")
        for path in files:
            with self.subTest(form_file=os.path.basename(path)):
                dom, errors = parse_and_validate(path)
                self.assertIsNotNone(dom, f"failed to parse {path}")
                self.assertEqual(
                    errors,
                    [],
                    f"validation errors in {path}:\n" + "\n".join(errors),
                )


if __name__ == "__main__":
    unittest.main()
