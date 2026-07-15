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
Regression test for the "initial_panel" preferences crash.

Gramps core's ``GrampsPreferences.__init__`` (gramps/gui/configure.py)
gained an ``initial_panel`` keyword argument so callers like
``ViewManager.preferences_activate`` can open the dialog directly on a
specific panel. The Themes addon replaces ``GrampsPreferences.__init__``
with ``MyPrefs.__init__`` (see ``themes_load.py``), which did not accept
the new keyword, raising:

    TypeError: MyPrefs.__init__() got an unexpected keyword argument
    'initial_panel'

every time preferences were opened from a context that passes
``initial_panel`` (e.g. a "Configure" button tied to a specific panel).

Construct ``MyPrefs`` via ``__new__`` and stub out
``ConfigureDialog.__init__``/``setup_configs`` (they build a real GTK
dialog and are irrelevant to this bug) so the test stays a fast, headless
unit test.
"""

import os
import sys
import unittest
from unittest import mock

# Pin Gtk to 3.0 before importing -- themes.py imports
# gi.repository.Gdk.Screen directly, which GTK 4's Gdk does not provide.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# Make sure the addon module is importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import themes  # pylint: disable=wrong-import-position


def _make_prefs():
    """Return a bare MyPrefs instance (no real __init__ run yet)."""
    return themes.MyPrefs.__new__(themes.MyPrefs)


class TestMyPrefsInitialPanel(unittest.TestCase):
    """Regression guard for the initial_panel TypeError."""

    def test_init_accepts_initial_panel_keyword(self):
        """MyPrefs.__init__ must accept the initial_panel keyword that
        GrampsPreferences.__init__ now takes; otherwise
        ViewManager.preferences_activate's call raises TypeError."""
        import inspect

        sig = inspect.signature(themes.MyPrefs.__init__)
        self.assertIn("initial_panel", sig.parameters)
        self.assertIsNone(sig.parameters["initial_panel"].default)

    def test_init_selects_requested_panel(self):
        """Passing initial_panel='colors' must select that panel, the
        same behaviour ViewManager relies on for GrampsPreferences."""
        prefs = _make_prefs()

        def fake_configure_init(self, *_args, **_kwargs):
            self.window = mock.MagicMock()

        with mock.patch.object(
            themes.ConfigureDialog, "__init__", fake_configure_init
        ), mock.patch.object(
            themes.MyPrefs, "setup_configs", mock.MagicMock(), create=True
        ), mock.patch.object(
            themes.MyPrefs, "select_panel", mock.MagicMock(), create=True
        ) as select_panel:
            themes.MyPrefs.__init__(
                prefs, mock.MagicMock(), mock.MagicMock(), initial_panel="colors"
            )

        select_panel.assert_called_once_with("colors")

    def test_init_without_initial_panel_does_not_select(self):
        """The default (no initial_panel) must behave exactly as
        before: no panel selection call, dialog opens on its default
        page."""
        prefs = _make_prefs()

        def fake_configure_init(self, *_args, **_kwargs):
            self.window = mock.MagicMock()

        with mock.patch.object(
            themes.ConfigureDialog, "__init__", fake_configure_init
        ), mock.patch.object(
            themes.MyPrefs, "setup_configs", mock.MagicMock(), create=True
        ), mock.patch.object(
            themes.MyPrefs, "select_panel", mock.MagicMock(), create=True
        ) as select_panel:
            themes.MyPrefs.__init__(prefs, mock.MagicMock(), mock.MagicMock())

        select_panel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
