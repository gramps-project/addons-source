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
Regression test for SourceReferences plugin-registration imports.

Historically ``SourceReferences/SourceReferences.py`` used Python-2 /
Gramps-3 era pre-namespace imports::

    from ListModel import ListModel, NOSORT
    from Utils import navigation_label
    from gen.plug import Gramplet
    import gtk

— none of which resolve on Python 3 / Gramps 5+. The addon failed
plugin registration with ``ModuleNotFoundError: No module named
'ListModel'`` before reaching any of its actual code, so it was
completely unusable in modern Gramps.

This test verifies the module imports cleanly on Python 3, with the
``SourceReferences`` class exposed and ready for plugin registration.
"""

import os
import sys
import unittest

# clipboard / editor imports inside SourceReferences.py transitively
# touch GTK-3-only enums (Gtk.IconSize.MENU, etc.). Pin Gtk to 3.0
# before importing so the underlying gramps.gui chain is happy.
# Skip cleanly if GTK 3 is not available.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# Make sure addon modules are importable from the parent directory.
# Required when this test is loaded via its dotted path
# (``SourceReferences.tests.test_sourcereferences_imports``) rather
# than via ``unittest discover`` from inside ``tests/``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSourceReferencesImports(unittest.TestCase):
    """Regression: the module must import on Python 3 / Gramps 5+."""

    def test_module_imports_and_exposes_class(self):
        """SourceReferences.py must import cleanly and expose its
        ``SourceReferences`` Gramplet subclass.

        Before the Py2 → Py3 namespace migration this test fails
        immediately with ``ModuleNotFoundError: No module named
        'ListModel'`` on line 23.
        """
        # The addon directory and the implementation module share
        # the name ``SourceReferences``; with a ``tests/`` subdir
        # alongside, the directory becomes a namespace package and
        # a bare ``import SourceReferences`` binds the package, not
        # the .py file. Use the explicit submodule path. (Same
        # workaround as libaccess; see gramps bug 0012691 family.)
        from SourceReferences import SourceReferences as mod

        self.assertTrue(
            hasattr(mod, "SourceReferences"),
            "SourceReferences class must be defined after import",
        )
        # Sanity check the class actually inherits from Gramplet — if
        # the migration accidentally broke the class hierarchy this
        # would catch it.
        from gramps.gen.plug import Gramplet

        self.assertTrue(
            issubclass(mod.SourceReferences, Gramplet),
            "SourceReferences must be a Gramplet subclass",
        )


if __name__ == "__main__":
    unittest.main()
