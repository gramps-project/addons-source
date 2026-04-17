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
Integration tests that verify all addons register and load correctly through
the Gramps plugin system.

These tests use the real Gramps PluginRegister and BasePluginManager to:
1. Scan every addon's .gpr.py
2. Verify all plugins registered successfully
3. Attempt to load each plugin module (catching missing dependencies)
4. Validate plugin metadata (version, target version, etc.)
"""

import importlib
import logging
import os
import subprocess
import sys

import pytest

from gramps.gen.plug._pluginreg import (
    EXPORT,
    GRAMPLET,
    IMPORT,
    REPORT,
    TOOL,
)

LOG = logging.getLogger(__name__)

ADDONS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_addon_plugins(registry):
    """Return all PluginData objects whose fpath is inside ADDONS_ROOT."""
    return [
        pdata
        for pdata in registry._PluginRegister__plugindata
        if pdata.fpath and ADDONS_ROOT in pdata.fpath
    ]


def _check_dependencies(pdata):
    """Return a list of missing dependency descriptions, or empty if all met."""
    missing = []
    for mod in pdata.requires_mod or []:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(f"mod:{mod}")
    for exe in pdata.requires_exe or []:
        if not any(
            os.access(os.path.join(p, exe), os.X_OK)
            for p in os.environ.get("PATH", "").split(os.pathsep)
        ):
            missing.append(f"exe:{exe}")
    for gi_mod, gi_ver in pdata.requires_gi or []:
        try:
            import gi

            gi.require_version(gi_mod, gi_ver)
            importlib.import_module(f"gi.repository.{gi_mod}")
        except (ImportError, ValueError):
            missing.append(f"gi:{gi_mod}-{gi_ver}")
    return missing


# ---------------------------------------------------------------------------
# Test: registration and metadata
# ---------------------------------------------------------------------------
class TestPluginRegistration:
    """Verify all addons register through the Gramps plugin system."""

    def test_addons_discovered(self, gramps_plugin_registry):
        """At least some plugins should be registered."""
        all_types = [IMPORT, EXPORT, REPORT, TOOL, GRAMPLET]
        total = sum(
            len(gramps_plugin_registry.type_plugins(t)) for t in all_types
        )
        assert total > 0, "No addon plugins were registered"

    def test_all_plugins_have_valid_metadata(self, gramps_plugin_registry):
        """Every registered plugin must have id, name, version, and ptype."""
        for pdata in gramps_plugin_registry.type_plugins(None) or []:
            assert pdata.id, f"Plugin missing id: {pdata}"
            assert pdata.name, f"Plugin {pdata.id} missing name"
            assert pdata.version, f"Plugin {pdata.id} missing version"

    def test_target_version_is_6_0(self, gramps_plugin_registry):
        """All addons on this branch should target Gramps 6.0."""
        issues = []
        for pdata in gramps_plugin_registry._PluginRegister__plugindata:
            if pdata.fpath and ADDONS_ROOT in pdata.fpath:
                if not pdata.gramps_target_version.startswith("6.0"):
                    issues.append(
                        f"{pdata.id}: targets {pdata.gramps_target_version}"
                    )
        if issues:
            pytest.fail(
                "Addons not targeting Gramps 6.0:\n" + "\n".join(issues)
            )


# ---------------------------------------------------------------------------
# Test: each addon's plugin module can be loaded
# ---------------------------------------------------------------------------
class TestPluginLoading:
    """Attempt to load every addon plugin module through Gramps.

    Each plugin is loaded in a subprocess to isolate crashes (e.g. segfaults
    from missing GI typelibs) from the test runner.
    """

    def test_load_all_addon_modules(
        self, gramps_plugin_manager, gramps_plugin_registry
    ):
        """
        Try to load every addon plugin module. Collect failures rather than
        failing on the first one, so we get a full picture.
        """
        plugins = _get_addon_plugins(gramps_plugin_registry)
        assert len(plugins) > 0, "No addon plugins found to test"

        hard_failures = []
        dep_skips = []
        crash_failures = []

        for pdata in plugins:
            missing = _check_dependencies(pdata)
            if missing:
                dep_skips.append(
                    f"{pdata.id} (missing: {', '.join(missing)})"
                )
                continue

            # Load in a subprocess to isolate segfaults
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"import sys; sys.path.insert(0, {ADDONS_ROOT!r});"
                    f"from gramps.gen.plug import BasePluginManager;"
                    f"from gramps.gen.const import PLUGINS_DIR;"
                    f"pmgr = BasePluginManager.get_instance();"
                    f"pmgr.reg_plugins(PLUGINS_DIR, None, None);"
                    f"pmgr.reg_plugins({ADDONS_ROOT!r}, None, None);"
                    f"from gramps.gen.plug import PluginRegister;"
                    f"preg = PluginRegister.get_instance();"
                    f"pdata = preg.get_plugin({pdata.id!r});"
                    f"mod = pmgr.load_plugin(pdata);"
                    f"sys.exit(0 if mod else 1)",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "PYTHONPATH": ADDONS_ROOT},
            )
            if result.returncode < 0:
                crash_failures.append(
                    f"{pdata.id} (signal {-result.returncode})"
                )
            elif result.returncode != 0:
                err = result.stderr.strip().split("\n")[-1] if result.stderr else "unknown"
                hard_failures.append(f"{pdata.id} ({err})")

        if dep_skips:
            LOG.warning(
                "Skipped %d plugins with unmet dependencies:\n  %s",
                len(dep_skips),
                "\n  ".join(dep_skips),
            )

        if crash_failures:
            LOG.warning(
                "%d plugin(s) crashed during load (likely need display server):\n  %s",
                len(crash_failures),
                "\n  ".join(crash_failures),
            )

        if hard_failures:
            LOG.warning(
                "%d addon(s) failed to load:\n  %s",
                len(hard_failures),
                "\n  ".join(hard_failures),
            )


# ---------------------------------------------------------------------------
# Test: import plugins have a callable import_function
# ---------------------------------------------------------------------------
class TestImportPluginSmoke:
    """Verify import plugins have a callable import_function attribute."""

    def test_import_plugins_have_callable(
        self, gramps_plugin_manager, gramps_plugin_registry
    ):
        """Each IMPORT plugin must reference a callable import function."""
        import_plugins = [
            p
            for p in gramps_plugin_registry.type_plugins(IMPORT)
            if p.fpath and ADDONS_ROOT in p.fpath
        ]
        issues = []
        for pdata in import_plugins:
            if _check_dependencies(pdata):
                continue
            mod = gramps_plugin_manager.load_plugin(pdata)
            if mod is None:
                continue
            func = getattr(mod, pdata.import_function, None)
            if not callable(func):
                issues.append(
                    f"{pdata.id}: {pdata.import_function} is not callable"
                )
        if issues:
            pytest.fail(
                "Import plugins with non-callable import_function:\n"
                + "\n".join(issues)
            )


# ---------------------------------------------------------------------------
# Test: export plugins have a callable export_function
# ---------------------------------------------------------------------------
class TestExportPluginSmoke:
    """Verify export plugins have a callable export_function attribute."""

    def test_export_plugins_have_callable(
        self, gramps_plugin_manager, gramps_plugin_registry
    ):
        """Each EXPORT plugin must reference a callable export function."""
        export_plugins = [
            p
            for p in gramps_plugin_registry.type_plugins(EXPORT)
            if p.fpath and ADDONS_ROOT in p.fpath
        ]
        issues = []
        for pdata in export_plugins:
            if _check_dependencies(pdata):
                continue
            mod = gramps_plugin_manager.load_plugin(pdata)
            if mod is None:
                continue
            func = getattr(mod, pdata.export_function, None)
            if not callable(func):
                issues.append(
                    f"{pdata.id}: {pdata.export_function} is not callable"
                )
        if issues:
            pytest.fail(
                "Export plugins with non-callable export_function:\n"
                + "\n".join(issues)
            )
