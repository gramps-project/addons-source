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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Regression test for issue 46: GraphView/graphview.py raised a bare Exception
at *module import* when the GraphViz ``dot`` binary (or GooCanvas) was
unavailable (graphview.py:111-113 / :120-122). The module-level raise
duplicates the registration-layer gate (``requires_exe=["dot"]`` /
``requires_gi=[("GooCanvas", ...)]`` in graphview.gpr.py) that Gramps' plugin
manager already owns, and breaks every direct importer -- including this
addon's own test collection, which crashes during import on a host lacking
``dot``.

The module must instead import without a side-effecting failure when a
declared dependency is absent; whether the plugin loads stays the sole
responsibility of the ``requires_*`` gate at registration time.

This test drives the *production* ``GraphView.graphview`` import in a fresh
child interpreter with the ``dot`` binary made unfindable (an empty ``PATH``,
so ``gramps.gen.utils.file.search_for("dot")`` returns 0 exactly as it does on
a host without GraphViz). Pre-fix the child import raises and exits non-zero;
post-fix it imports cleanly and exits zero.

The Gtk/GooCanvas-bound production module is imported only *inside the child
process*, never at this test module's top level, so the headless test
collector never executes a GUI import during collection -- this module imports
only the stdlib.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

# addons-source root = GraphView/tests/<this file> -> parents[2]. The child
# interpreter imports the real GraphView.graphview namespace package from here.
_ADDONS_ROOT = Path(__file__).resolve().parents[2]

# Import the production module and the class the brief's success criterion names.
# `import GraphView.graphview` runs the whole module body (the lines that, pre-fix,
# raise when GooCanvas/dot are absent); the DotSvgGenerator import proves the
# success criterion's second clause. A non-zero exit means the import raised.
_CHILD = (
    "import GraphView.graphview\n"
    "from GraphView.graphview import DotSvgGenerator\n"
    "assert DotSvgGenerator is not None\n"
)


class GraphViewImportTest(unittest.TestCase):
    """The plugin module must import even when its declared external deps are absent."""

    def test_module_imports_with_dot_unavailable(self):
        # Simulate the GraphViz `dot` binary being unavailable: an empty PATH
        # makes search_for("dot") (gramps.gen.utils.file:236-240) return 0, so
        # _DOT_FOUND is falsy -- pre-fix that triggers the module-level
        # `raise Exception("GraphViz ... required")` at graphview.py:120-122.
        env = dict(os.environ)
        env["PATH"] = ""
        # Keep the inherited PYTHONPATH (carries the gi_bootstrap GI version pin),
        # and put the addons-source root first so `import GraphView` resolves.
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_ADDONS_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)

        result = subprocess.run(
            [sys.executable, "-c", _CHILD],
            cwd=str(_ADDONS_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            "importing GraphView.graphview with `dot` unavailable must not raise; "
            "child exited %s\n--- stderr ---\n%s" % (result.returncode, result.stderr),
        )


if __name__ == "__main__":
    unittest.main()
