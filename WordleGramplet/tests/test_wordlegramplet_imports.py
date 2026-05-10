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
Regression test for WordleGramplet plugin-registration imports.

Historically ``WordleGramplet/WordleGramplet.py`` had two import
problems that broke plugin registration on Python 3:

  - ``from itertools import imap`` (``imap`` is a Py2 builtin
    removed in Py3 — ``map`` is already lazy on Py3).
  - ``from gen.plug import Gramplet`` and two other ``gen.plug.*``
    imports — Gramps-3 era pre-namespace paths that no longer
    resolve in Gramps 5+ (the modules live under ``gramps.gen.*``).

The addon failed plugin registration with ``cannot import name
'imap' from 'itertools'`` (the first error Python hit); once that
was fixed in isolation the next line down then raised
``ModuleNotFoundError: No module named 'gen'``. This test pins
down that the module imports cleanly end-to-end.
"""

import os
import sys
import unittest

# Pin Gtk to 3.0 before importing — the gramps.gen.plug import
# chain transitively touches GTK-3-only enums in gramps.gui.
# Skip cleanly if GTK 3 is not available.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# Make sure addon modules are importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWordleGrampletImports(unittest.TestCase):
    """Regression: the module must import on Python 3 / Gramps 5+."""

    def test_module_imports_and_exposes_class(self):
        """WordleGramplet.py must import cleanly and expose its
        ``WordleGramplet`` class as a Gramplet subclass.

        Before the migration this fails with either
        ``ImportError: cannot import name 'imap' from 'itertools'``
        (on the unfixed tree) or
        ``ModuleNotFoundError: No module named 'gen'`` (after the
        narrow imap-only fix in this PR's earlier revision).
        """
        # Addon dir and impl module share the name ``WordleGramplet``;
        # under dotted-path loading the dir becomes a namespace
        # package, so use the explicit submodule path. (Same trap as
        # libaccess; see gramps bug 0012691 family.)
        from WordleGramplet import WordleGramplet as mod

        self.assertTrue(
            hasattr(mod, "WordleGramplet"),
            "WordleGramplet class must be defined after import",
        )
        from gramps.gen.plug import Gramplet

        self.assertTrue(
            issubclass(mod.WordleGramplet, Gramplet),
            "WordleGramplet must be a Gramplet subclass",
        )


if __name__ == "__main__":
    unittest.main()
