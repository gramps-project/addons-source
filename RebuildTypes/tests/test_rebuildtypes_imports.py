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
Regression test for RebuildTypes plugin-registration imports.

Historically ``RebuildTypes/RebuildTypes.py`` used Gramps-3 era
pre-namespace imports::

    from gui.plug import tool
    from QuestionDialog import OkDialog

Neither resolves on Gramps 5+ (modules now under ``gramps.gui.*``).
The addon failed plugin registration with ``ModuleNotFoundError:
No module named 'gui'`` and was completely unusable.

The April 19 plugin-registration smoke test reported a different
error (``RuntimeError: could not create new GType: UndoableEntry``)
which appears to have been a downstream symptom or a stale report;
the actual first error on a current Py3 / Gramps 5 environment is
the ``ModuleNotFoundError`` above. If a GType conflict surfaces
after the import migration, that's a separate concern for a
gramps-core PR (cf. #2299 for the analogous gui.clipboard
headless-import fix).

This test verifies the module imports cleanly on Py3 / Gramps 5+
with the ``RebuildTypes`` class exposed.
"""

import os
import sys
import unittest

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRebuildTypesImports(unittest.TestCase):
    """Regression: module must import on Python 3 / Gramps 5+."""

    def test_module_imports_and_exposes_class(self):
        """``RebuildTypes.py`` must import cleanly and expose its
        ``RebuildTypes`` Tool subclass.

        Before the migration this fails at line 31 with
        ``ModuleNotFoundError: No module named 'gui'``.
        """
        # Addon dir and impl module share the name; use the explicit
        # submodule path. (Same trap as libaccess; see gramps bug
        # 0012691 family.)
        from RebuildTypes import RebuildTypes as mod

        self.assertTrue(
            hasattr(mod, "RebuildTypes"),
            "RebuildTypes class must be defined after import",
        )
        from gramps.gui.plug.tool import Tool

        self.assertTrue(
            issubclass(mod.RebuildTypes, Tool),
            "RebuildTypes must be a Tool subclass",
        )


if __name__ == "__main__":
    unittest.main()
