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
Shared test infrastructure for Gramps addon integration tests.

Module-level initialisation puts the addons-source root on :data:`sys.path`
and sets :envvar:`GRAMPS_RESOURCES` so ``gramps`` is importable. Helpers
boot the Gramps plugin system once per process (registering plugins is
expensive) and provide fresh in-memory databases on demand.

Usage — in any :class:`unittest.TestCase`::

    from tests.gramps_test_env import GrampsTestCase

    class MyPluginTest(GrampsTestCase):
        def test_registered(self) -> None:
            pdata = self.plugin_registry.get_plugin("im_sqz")
            self.assertIsNotNone(pdata)
"""

# ------------------------
# Python modules
# ------------------------
import os
import shutil
import sys
import tempfile
import unittest
from typing import Any, ClassVar

# ------------------------
# Path + environment bootstrap (runs at import)
# ------------------------
ADDONS_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDONS_ROOT not in sys.path:
    sys.path.insert(0, ADDONS_ROOT)

if "GRAMPS_RESOURCES" not in os.environ:
    try:
        import gramps  # noqa: F401

        os.environ["GRAMPS_RESOURCES"] = os.path.dirname(
            os.path.dirname(gramps.__file__)
        )
    except ImportError:
        pass


# ------------------------
# GTK availability
# ------------------------
def _has_gtk() -> bool:
    """Return whether GTK 3.0 is importable on this host.

    :returns: ``True`` if ``gi.repository.Gtk`` can be loaded, else ``False``.
    """
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401

        return True
    except (ImportError, ValueError):
        return False


HAS_GTK: bool = _has_gtk()


# ------------------------
# Plugin-manager singleton
# ------------------------
_plugin_cache: dict[str, Any] = {}


# Dialog classes an addon might instantiate at import / load-on-reg time.
_GUI_DIALOG_NAMES = (
    "ErrorDialog",
    "WarningDialog",
    "OkDialog",
    "InfoDialog",
    "QuestionDialog",
    "QuestionDialog2",
    "DBErrorDialog",
    "RunDatabaseRepair",
)

def neutralize_gui_dialogs() -> None:
    """Replace ``gramps.gui.dialog`` dialogs with no-ops for the test process.

    Some addons pop a *blocking* modal (``ErrorDialog(...).run()``) at import or
    load-on-reg time when an optional dependency is missing — e.g.
    ``lxmlGramplet`` on a host without ``python3-lxml``. Loading such an addon
    in a test would otherwise hang on the modal (under a display) or scatter
    dialogs on the developer's screen. Safe to call more than once.
    """
    try:
        import gramps.gui.dialog as gd
    except Exception:
        return

    class _NoDialog:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.response = 0

        def run(self, *args: Any, **kwargs: Any) -> int:
            return 0

        def __getattr__(self, name: str) -> Any:
            return lambda *a, **k: None

    for name in _GUI_DIALOG_NAMES:
        if hasattr(gd, name):
            setattr(gd, name, _NoDialog)


def get_plugin_manager_and_registry() -> tuple[Any, Any]:
    """Return the Gramps plugin manager and registry, initialising on first call.

    Registration scans every addon's ``.gpr.py`` and is expensive; the result
    is cached for the lifetime of the test process.

    :returns: Tuple of ``(plugin_manager, plugin_registry)``.
    :rtype: tuple[:class:`BasePluginManager`, :class:`PluginRegister`]
    """
    if "pmgr" not in _plugin_cache:
        from gramps.gen.const import PLUGINS_DIR
        from gramps.gen.plug import BasePluginManager, PluginRegister

        # reg_plugins(load_on_reg=True) runs addon load-on-reg callbacks in
        # this process; neutralise dialogs first so none can block or show UI.
        neutralize_gui_dialogs()
        pmgr = BasePluginManager.get_instance()
        pmgr.reg_plugins(PLUGINS_DIR, None, None)
        pmgr.reg_plugins(ADDONS_ROOT, None, None, load_on_reg=True)
        _plugin_cache["pmgr"] = pmgr
        _plugin_cache["registry"] = PluginRegister.get_instance()
    return _plugin_cache["pmgr"], _plugin_cache["registry"]


def make_gramps_user() -> Any:
    """Return a headless :class:`gramps.cli.user.User` for batch import/export.

    :returns: A ``User`` configured with ``auto_accept=True`` and ``quiet=True``.
    """
    from gramps.cli.user import User

    return User(auto_accept=True, quiet=True)


def strict_mode() -> bool:
    """Whether ``GRAMPS_ADDON_TEST_STRICT`` opts into gating on advisory results.

    Off by default so a headless developer run is not flaky on failures that
    are really about the environment (no display, missing GI/typelib, a native
    GTK abort). A CI lane with a full runtime can set the variable to promote
    those advisories to hard failures — see the ``make.py test`` docs.

    :returns: ``True`` when the variable is set to a truthy value.
    """
    return os.environ.get("GRAMPS_ADDON_TEST_STRICT", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# ------------------------------------------------------------
#
# GrampsTestCase
#
# ------------------------------------------------------------
class GrampsTestCase(unittest.TestCase):
    """
    Base TestCase with lazy access to the Gramps plugin manager and registry.

    Subclasses may override :meth:`setUp` / :meth:`tearDown` freely; the
    plugin registry is a class-level singleton so its cost is paid once.
    """

    plugin_manager: ClassVar[Any] = None
    plugin_registry: ClassVar[Any] = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.plugin_manager, cls.plugin_registry = get_plugin_manager_and_registry()


# ------------------------------------------------------------
#
# GrampsDbTestCase
#
# ------------------------------------------------------------
class GrampsDbTestCase(GrampsTestCase):
    """
    Base class that also provisions a fresh in-memory SQLite Gramps DB per test.

    The database is available as ``self.db``; ``setUp`` / ``tearDown`` handle
    creation and cleanup of the on-disk temp directory.
    """

    db: Any = None
    _tmpdir: str = ""

    def setUp(self) -> None:
        super().setUp()
        from gramps.gen.db.utils import make_database

        self._tmpdir = tempfile.mkdtemp(prefix="gramps_test_")
        self.db = make_database("sqlite")
        self.db.load(os.path.join(self._tmpdir, "test_db"), None)

    def tearDown(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        super().tearDown()
