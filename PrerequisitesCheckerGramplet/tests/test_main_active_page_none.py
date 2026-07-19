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
Regression test for Mantis bug 13966.

When the family tree is closed while the
``PrerequisitesCheckerGramplet`` gramplet is still being stepped by
the gramplet framework's ``_updater`` / ``next(self._generator)``
loop, ``self.uistate.viewmanager.active_page`` becomes ``None``. The
gramplet's ``main()`` reads ``…active_page.bottombar`` unguarded and
raises ``AttributeError: 'NoneType' object has no attribute
'bottombar'``.

This test drives ``main()`` once with a stub ``uistate`` whose
``active_page`` is ``None`` and asserts the generator exits cleanly
(via ``StopIteration``) without ``AttributeError``.
"""

import importlib.util
import os
import unittest
from unittest import mock

# The addon's module file (PrerequisitesCheckerGramplet.py) shares its
# basename with the package directory; the dotted-path loader registers
# the directory as a namespace package first, so a plain
# `import PrerequisitesCheckerGramplet` then binds the package rather
# than the submodule (the bug 0012691 trap). Load the module file
# directly to sidestep that.
_addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_module_path = os.path.join(_addon_dir, "PrerequisitesCheckerGramplet.py")
_spec = importlib.util.spec_from_file_location(
    "PrerequisitesCheckerGramplet_module", _module_path
)
pcg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pcg)


class TestMainHandlesActivePageNone(unittest.TestCase):
    """main() must not raise when viewmanager.active_page is None.

    Bug 13966: on tree close, the framework still pumps the generator
    via _gramplet.py:331 _updater → next(self._generator). The gramplet
    assumes an active page exists; on close it doesn't.
    """

    def _make_gramplet(self, active_page):
        # Build a gramplet instance without running Gramplet.__init__
        # (which constructs Gtk widgets). We only need to exercise
        # main() with the minimum attributes it reads.
        gramplet = pcg.PrerequisitesCheckerGramplet.__new__(
            pcg.PrerequisitesCheckerGramplet
        )
        gramplet.count = 0
        gramplet.latest_gramps_version = False
        gramplet.has_run = False

        # The crash path: main() reads
        # self.uistate.viewmanager.active_page.bottombar
        uistate = mock.MagicMock()
        uistate.viewmanager.active_page = active_page
        gramplet.uistate = uistate

        # dbstate.db.is_open() — only reached when active_page is
        # truthy with a bottombar. Stubbed for completeness.
        gramplet.dbstate = mock.MagicMock()
        gramplet.dbstate.db.is_open.return_value = False
        return gramplet

    def test_main_does_not_crash_when_active_page_is_none(self):
        """The exact bug 13966 traceback: active_page is None on tree
        close, the unguarded ``.bottombar`` raises AttributeError."""
        gramplet = self._make_gramplet(active_page=None)
        generator = gramplet.main()
        # The framework calls next() on the generator. The bug
        # surfaces on the very first next() — before any yield.
        # Post-fix: main() must return cleanly (StopIteration), not
        # raise AttributeError.
        with self.assertRaises(StopIteration):
            next(generator)

    def test_main_still_works_on_non_dashboard_view(self):
        """Regression guard: when a real page IS active, the existing
        bottombar / db-open / count<3 short-circuit chain still runs.
        With db closed and the bottombar truthy, main() returns early
        (no yield) just as before — same StopIteration on first
        next()."""
        active_page = mock.MagicMock()
        active_page.bottombar = mock.MagicMock()  # truthy
        gramplet = self._make_gramplet(active_page=active_page)
        gramplet.dbstate.db.is_open.return_value = False
        generator = gramplet.main()
        with self.assertRaises(StopIteration):
            next(generator)

    def test_main_on_dashboard_with_pending_version_yields(self):
        """Regression guard: on the dashboard (bottombar falsy) with
        the upstream-version fetch still in flight (latest_gramps_version
        is False), main() yields rather than returning. Bug 13966's
        guard must not change this path."""
        active_page = mock.MagicMock()
        active_page.bottombar = False  # dashboard
        gramplet = self._make_gramplet(active_page=active_page)
        # latest_gramps_version is False (default) → enters the
        # `while … is False: yield True` loop and yields.
        generator = gramplet.main()
        self.assertTrue(next(generator),
                        "Dashboard path should yield True while the "
                        "latest-version fetch is pending")


if __name__ == "__main__":
    unittest.main()
