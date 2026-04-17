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
Integration tests for the Form addon loader — covers
``gramps-project/gramps#11707`` (*ValueError: not enough values to
unpack* when a form's ``<section type='family'>`` title lacks the
``X/Y`` separator).

Scenarios covered:

* Malformed XML produces an ``ErrorDialog`` rather than a bare traceback.
* A partially-broken file still loads its well-formed ``<form>`` entries.
* The shipped built-in definition files load cleanly without any error
  dialogs being raised.

Run with::

    python3 -m unittest Form.tests.test_integration_form -v
"""

# ------------------------
# Python modules
# ------------------------
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

# ------------------------
# Gramps modules
# ------------------------
try:
    import gi  # noqa: F401
    import gramps
except ImportError as exc:
    raise unittest.SkipTest(
        "Form integration tests require 'gi' and 'gramps': %s" % exc
    )

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

# ------------------------
# Gramps specific
# ------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)


# ---------------------------------------------------------------------------
# Shared harness
# ---------------------------------------------------------------------------
class FormLoaderTestCase(unittest.TestCase):
    """
    Base class that imports the Form addon's ``form`` module and
    redirects its ``ErrorDialog`` to an in-memory list instead of
    opening a GTK dialog.

    Subclasses access :attr:`shown` to inspect captured dialog calls
    and use :meth:`_write` to drop XML files into an isolated
    temporary directory.
    """

    def setUp(self) -> None:
        import form

        self.form = form
        self.shown: list[tuple[str, str]] = []

        def _fake_error_dialog(*args, **kwargs):
            title = str(args[0]) if args else ""
            body = str(args[1]) if len(args) > 1 else ""
            self.shown.append((title, body))

        error_patch = patch.object(form, "ErrorDialog", _fake_error_dialog)
        error_patch.start()
        self.addCleanup(error_patch.stop)

        self.tmp_dir = tempfile.mkdtemp(prefix="form-integration-")
        self.addCleanup(shutil.rmtree, self.tmp_dir, True)

    def _write(self, filename: str, content: str) -> None:
        """Write an XML fixture into the test's temporary directory."""
        path = os.path.join(self.tmp_dir, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _patch_definition_files(self, files: list[str]) -> None:
        """Redirect the loader to the given filenames (inside tmp_dir)."""
        files_patch = patch.object(self.form, "definition_files", files)
        files_patch.start()
        self.addCleanup(files_patch.stop)


# ---------------------------------------------------------------------------
# Error-dialog wiring
# ---------------------------------------------------------------------------
class TestErrorDialogWiring(FormLoaderTestCase):
    """
    Exercises the four failure modes the loader now surfaces via
    :class:`ErrorDialog` instead of an unhandled traceback.
    """

    def test_malformed_xml_shows_error_dialog(self) -> None:
        """XML syntax errors should raise an ErrorDialog, not a traceback."""
        self._write("custom.xml", "<forms><form id='F1'><unclosed></forms>")
        self._patch_definition_files(["custom.xml"])

        instance = self.form.Form(definition_dir=self.tmp_dir)

        self.assertTrue(self.shown, "no ErrorDialog was displayed")
        title, body = self.shown[0]
        self.assertIn("XML syntax error", title)
        self.assertIn("custom.xml", body)
        self.assertEqual(list(instance.get_form_ids()), [])

    def test_invalid_family_title_shows_error_dialog(self) -> None:
        """
        The exact condition from bug 11707 — a family section with a
        non-``X/Y`` title — must be surfaced as an ErrorDialog at load
        time rather than an unhandled exception when the user later
        opens the form.
        """
        self._write(
            "custom.xml",
            textwrap.dedent("""\
                <forms>
                    <form id='F1' type='Marriage' title='Bad Marriage'>
                        <section role='Family' type='family' title='Couple'/>
                    </form>
                </forms>
                """),
        )
        self._patch_definition_files(["custom.xml"])

        self.form.Form(definition_dir=self.tmp_dir)

        self.assertTrue(
            self.shown, "no ErrorDialog was displayed for invalid family title"
        )
        title, body = self.shown[0]
        self.assertIn("Invalid Form definition file", title)
        self.assertIn("Name1/Name2", body)

    def test_partially_broken_file_still_loads_valid_forms(self) -> None:
        """A broken <form> must not stop sibling <form> elements loading."""
        self._write(
            "custom.xml",
            textwrap.dedent("""\
                <forms>
                    <form id='GOOD' type='Census' title='Good Census'>
                        <section role='Primary' type='person'/>
                    </form>
                    <form id='BAD' type='Marriage' title='Bad Marriage'>
                        <section role='Family' type='family' title='Couple'/>
                    </form>
                </forms>
                """),
        )
        self._patch_definition_files(["custom.xml"])

        instance = self.form.Form(definition_dir=self.tmp_dir)
        loaded_ids = list(instance.get_form_ids())

        self.assertIn("GOOD", loaded_ids, "valid form should still load")
        self.assertNotIn("BAD", loaded_ids, "invalid form should be skipped")
        self.assertTrue(self.shown, "the broken form should have been reported")

    def test_missing_role_attribute_shows_error_dialog(self) -> None:
        """A section missing its ``role`` attribute is reported clearly."""
        self._write(
            "custom.xml",
            textwrap.dedent("""\
                <forms>
                    <form id='F1' type='Census' title='x'>
                        <section type='person'/>
                    </form>
                </forms>
                """),
        )
        self._patch_definition_files(["custom.xml"])

        self.form.Form(definition_dir=self.tmp_dir)

        self.assertTrue(self.shown)
        _, body = self.shown[0]
        self.assertIn("role", body)

    def test_invalid_section_type_shows_error_dialog(self) -> None:
        """Unknown section types produce a clear error, not a later crash."""
        self._write(
            "custom.xml",
            textwrap.dedent("""\
                <forms>
                    <form id='F1' type='Census' title='x'>
                        <section role='Primary' type='bogus'/>
                    </form>
                </forms>
                """),
        )
        self._patch_definition_files(["custom.xml"])

        instance = self.form.Form(definition_dir=self.tmp_dir)

        self.assertTrue(self.shown)
        _, body = self.shown[0]
        self.assertIn("bogus", body)
        self.assertNotIn("F1", list(instance.get_form_ids()))


# ---------------------------------------------------------------------------
# Shipped files load cleanly
# ---------------------------------------------------------------------------
class TestShippedFilesLoadCleanly(FormLoaderTestCase):
    """
    The built-in definition files that ship with the addon must load
    without triggering a single ErrorDialog, otherwise end users would
    see a popup every time they opened Gramps.
    """

    def test_shipped_files_load_without_errors(self) -> None:
        instance = self.form.Form()

        self.assertFalse(
            self.shown,
            "Built-in definition files triggered ErrorDialog calls:\n"
            + "\n".join("%s: %s" % (t, b) for t, b in self.shown),
        )
        self.assertTrue(
            list(instance.get_form_ids()),
            "no forms loaded from built-in definition files",
        )


if __name__ == "__main__":
    unittest.main()
