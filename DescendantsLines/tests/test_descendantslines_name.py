#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Gramps Development Team
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
Regression test for Mantis bug 5965.

The DescendantsLines report wrote its graphic to the report's own persisted
"Destination" option (``output_fn``). That option keeps its value across Gramps
sessions, so the graphic produced for the current run carried the *previous*
session's name instead of the destination the user chose for the current run.

The production report (``DescendantsLines.py``) derives the graphic filename
through ``descendantslines_output.derive_output_filename``; this test drives
that same function directly (the report module itself imports ``cairo`` and
``gramps.gui``-adjacent modules at load and cannot be imported headlessly).

Pre-fix the module / function does not exist, so the import fails (RED). Post-
fix the function exists and the current-run destination wins over the stale
option (GREEN).
"""

import os
import sys
import unittest

# Make the addon's sibling modules importable from the addon directory, matching
# the JSON / DescendantBooks test convention (the modules are imported by their
# bare name, the way Gramps loads them with the addon dir on sys.path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from descendantslines_output import derive_output_filename


class TestDescendantsLinesOutputName(unittest.TestCase):
    """The graphic must be named for the CURRENT run, not a prior session."""

    def test_current_run_destination_overrides_stale_option(self):
        """The destination chosen for this run wins over the persisted option.

        Bug 5965: ``option_destination`` holds the previous session's name. The
        derived filename must reflect the current run's destination and carry no
        trace of the stale option's basename.
        """
        stale_option = os.path.join("/home", "user", "prev_session_name.png")
        current_run = os.path.join("/home", "user", "this_run_name")

        result = derive_output_filename(current_run, stale_option, "PNG")

        self.assertEqual(result, os.path.join("/home", "user", "this_run_name.png"))
        self.assertNotIn(
            "prev_session_name",
            result,
            "graphic carried the previous session's stale name",
        )

    def test_running_twice_tracks_each_runs_name(self):
        """Two runs with different current destinations yield different names.

        The persisted option is identical across both runs (it is the stale
        carry-over); only the current-run destination differs, and the output
        name must follow it each time — the success criterion's "run twice".
        """
        stale_option = os.path.join("/home", "user", "DescendantsLines.png")

        first = derive_output_filename(
            os.path.join("/home", "user", "alice_tree"), stale_option, "PNG"
        )
        second = derive_output_filename(
            os.path.join("/home", "user", "bob_tree"), stale_option, "PNG"
        )

        self.assertEqual(first, os.path.join("/home", "user", "alice_tree.png"))
        self.assertEqual(second, os.path.join("/home", "user", "bob_tree.png"))
        self.assertNotEqual(first, second)

    def test_falls_back_to_option_when_no_current_destination(self):
        """With no current-run destination, the persisted option is used.

        (e.g. CLI without an explicit document output) — behaviour unchanged
        from before the fix, with the format extension forced.
        """
        option = os.path.join("/home", "user", "DescendantsLines.png")

        result = derive_output_filename(None, option, "PDF")

        self.assertEqual(result, os.path.join("/home", "user", "DescendantsLines.pdf"))

    def test_distinct_from_document_destination_to_avoid_clobber(self):
        """The graphic name must differ from the document's own output path.

        The standard report document is written/closed AFTER the graphic is
        drawn; if the graphic shared the document's exact path the document's
        close() would clobber it. A ``-chart`` suffix keeps them distinct.
        """
        doc_path = os.path.join("/home", "user", "tree.png")

        result = derive_output_filename(doc_path, "", "PNG")

        self.assertNotEqual(result, doc_path)
        self.assertEqual(result, os.path.join("/home", "user", "tree-chart.png"))


if __name__ == "__main__":
    unittest.main()
