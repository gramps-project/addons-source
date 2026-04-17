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
Shared pytest fixtures for Gramps addon integration tests.

These fixtures boot Gramps headlessly and provide a plugin manager that has
scanned the addons-source tree, so every addon's .gpr.py registration is
available for inspection and loading.

Usage — in any addon's test file::

    def test_plugin_registers(gramps_plugin_registry):
        pdata = gramps_plugin_registry.get_plugin("im_sqz")
        assert pdata is not None
        assert pdata.name == "TMG Project Backup"

    def test_import_runs(gramps_db, gramps_user, gramps_plugin_manager):
        pdata = gramps_plugin_manager.get_instance() \\
            .__pgr.get_plugin("im_sqz")
        # ... load module and call import_function
"""

import os
import sys
import tempfile
import shutil

import pytest


# ---------------------------------------------------------------------------
# Ensure the addons-source root is on sys.path so addon modules are importable
# ---------------------------------------------------------------------------
ADDONS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDONS_ROOT not in sys.path:
    sys.path.insert(0, ADDONS_ROOT)


# ---------------------------------------------------------------------------
# Gramps environment — must happen before any gramps import
# ---------------------------------------------------------------------------
def _ensure_gramps_env():
    """Set GRAMPS_RESOURCES if not already set and gramps is importable."""
    if "GRAMPS_RESOURCES" not in os.environ:
        try:
            import gramps
            gramps_root = os.path.dirname(os.path.dirname(gramps.__file__))
            os.environ["GRAMPS_RESOURCES"] = gramps_root
        except ImportError:
            pass


_ensure_gramps_env()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def gramps_user():
    """A headless Gramps CLI User suitable for import/export/report calls."""
    from gramps.cli.user import User
    return User(auto_accept=True, quiet=True)


@pytest.fixture(scope="session")
def gramps_plugin_manager():
    """
    The Gramps BasePluginManager singleton, with both the built-in plugins
    and all addons from this repository registered.

    Use this to load plugin modules and call their entry points.
    """
    from gramps.gen.const import PLUGINS_DIR, USER_PLUGINS
    from gramps.gen.plug import BasePluginManager

    pmgr = BasePluginManager.get_instance()
    # Register built-in Gramps plugins (database backends, etc.)
    pmgr.reg_plugins(PLUGINS_DIR, None, None)
    # Register all addons in this repository
    pmgr.reg_plugins(ADDONS_ROOT, None, None, load_on_reg=True)
    return pmgr


@pytest.fixture(scope="session")
def gramps_plugin_registry(gramps_plugin_manager):
    """
    The PluginRegister instance containing all registered PluginData objects.

    Useful for querying what plugins are available::

        pdata = gramps_plugin_registry.get_plugin("im_sqz")
        all_imports = gramps_plugin_registry.import_plugins()
    """
    from gramps.gen.plug import PluginRegister
    return PluginRegister.get_instance()


@pytest.fixture
def gramps_db(gramps_plugin_manager):
    """
    A fresh in-memory Gramps SQLite database for each test.

    The database is created, opened, and torn down automatically::

        def test_import(gramps_db, gramps_user):
            from TMGimporter.libtmg import tmg_import_pipeline
            tmg_import_pipeline(gramps_db, dataset_id=1, user=None, ...)
            assert gramps_db.get_number_of_people() > 0
    """
    from gramps.gen.db.utils import make_database

    tmpdir = tempfile.mkdtemp(prefix="gramps_test_")
    db = make_database("sqlite")
    db.load(os.path.join(tmpdir, "test_db"), None)
    yield db
    try:
        db.close()
    except Exception:
        pass
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="session")
def gramps_db_session(gramps_plugin_manager):
    """
    A session-scoped in-memory Gramps database — shared across all tests in
    the session.  Use for expensive setup (e.g., importing a large file once
    and running many assertions against it).
    """
    from gramps.gen.db.utils import make_database

    tmpdir = tempfile.mkdtemp(prefix="gramps_test_session_")
    db = make_database("sqlite")
    db.load(os.path.join(tmpdir, "test_db"), None)
    yield db
    try:
        db.close()
    except Exception:
        pass
    shutil.rmtree(tmpdir, ignore_errors=True)
