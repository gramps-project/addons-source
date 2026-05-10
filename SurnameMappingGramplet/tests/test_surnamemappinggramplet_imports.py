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
Regression test for SurnameMappingGramplet plugin-registration imports.

Historically ``SurnameMappingGramplet/SurnameMappingGramplet.py``
used Python-2 / Gramps-3 era pre-namespace imports::

    import gtk                        # PyGTK, lowercase
    from gen.plug import Gramplet

Neither resolves on Python 3 / Gramps 5+. Coupled with the addon's
.gpr.py filename typo (``.grp.py`` instead of ``.gpr.py``, fixed
elsewhere in this PR), the addon was completely invisible to Gramps
— and would have failed registration anyway once the typo was
fixed.

This test verifies the module imports cleanly on Python 3 with the
``SurnameMappingGramplet`` class exposed as a Gramplet subclass.

NOTE: the addon's ``init()`` → ``build_gui()`` methods still use
several PyGTK-era GTK 2 APIs (``Gtk.Toolbar.insert_stock``,
``Gtk.STOCK_*``, ``Gtk.DIALOG_MODAL``, the old ``Gtk.Table.attach``
keyword arguments, etc.) that don't work as-is on modern PyGObject.
Those only fire when a user actually opens the gramplet — they
don't block plugin registration. Fixing them is a separate
follow-up; this test pins down the import-time path only.
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


class TestSurnameMappingGrampletImports(unittest.TestCase):
    """Regression: the module must import on Python 3 / Gramps 5+."""

    def test_module_imports_and_exposes_class(self):
        """SurnameMappingGramplet.py must import cleanly and expose
        its ``SurnameMappingGramplet`` Gramplet subclass.

        Before the Py2 → Py3 namespace migration this fails at
        line 28 with ``ModuleNotFoundError: No module named 'gtk'``.
        """
        # Addon dir and impl module share the name; use the explicit
        # submodule path. (Same trap as libaccess; see gramps bug
        # 0012691 family.)
        from SurnameMappingGramplet import SurnameMappingGramplet as mod

        self.assertTrue(
            hasattr(mod, "SurnameMappingGramplet"),
            "SurnameMappingGramplet class must be defined after import",
        )
        from gramps.gen.plug import Gramplet

        self.assertTrue(
            issubclass(mod.SurnameMappingGramplet, Gramplet),
            "SurnameMappingGramplet must be a Gramplet subclass",
        )


if __name__ == "__main__":
    unittest.main()
