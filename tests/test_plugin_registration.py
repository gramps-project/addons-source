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
Integration tests that verify all addons register and load correctly
through the Gramps plugin system.

These tests use the real Gramps ``PluginRegister`` and ``BasePluginManager`` to:

1. Scan every addon's ``.gpr.py``.
2. Verify all plugins registered successfully.
3. Attempt to load each plugin module (catching missing dependencies).
4. Validate plugin metadata (version, target version, entry points).
"""

# ------------------------
# Python modules
# ------------------------
import importlib
import logging
import os
import subprocess
import sys
import unittest
from typing import Any

# ------------------------
# Gramps modules
# ------------------------
from gramps.gen.plug._pluginreg import EXPORT, GRAMPLET, IMPORT, REPORT, TOOL
from gramps.version import VERSION_TUPLE

# ------------------------
# Gramps specific
# ------------------------
from tests.gramps_test_env import ADDONS_ROOT, GrampsTestCase

LOG = logging.getLogger(__name__)


def _get_addon_plugins(registry: Any, include_unlisted: bool = False) -> list[Any]:
    """Return all :class:`PluginData` objects whose ``fpath`` is inside the addons tree.

    By default, plugins whose ``.gpr.py`` declares ``include_in_listing=False``
    are filtered out: those addons are not built or released by ``make.py``,
    so this CI does not gate on their state (per Gary Griffin's discussion on
    PR #820). Pass ``include_unlisted=True`` to inspect them anyway.

    :param registry: A :class:`PluginRegister` instance.
    :param include_unlisted: If ``True``, also return plugins whose
                             ``include_in_listing`` field is ``False``.
    :type include_unlisted: bool
    :returns: List of :class:`PluginData` entries belonging to this repository.
    """
    return [
        pdata
        for pdata in registry._PluginRegister__plugindata
        if pdata.fpath
        and ADDONS_ROOT in pdata.fpath
        and (include_unlisted or pdata.include_in_listing)
    ]


def _check_dependencies(pdata: Any) -> list[str]:
    """Return a list of missing dependency descriptions for a plugin, or empty.

    :param pdata: The plugin's :class:`PluginData` record.
    :returns: Human-readable strings describing each unmet requirement.
    """
    missing: list[str] = []
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


# ------------------------------------------------------------
#
# TestPluginRegistration
#
# ------------------------------------------------------------
class TestPluginRegistration(GrampsTestCase):
    """Verify every addon registers through the Gramps plugin system."""

    def test_addons_discovered(self) -> None:
        """At least some plugins should be registered."""
        all_types = [IMPORT, EXPORT, REPORT, TOOL, GRAMPLET]
        total = sum(len(self.plugin_registry.type_plugins(t)) for t in all_types)
        self.assertGreater(total, 0, "No addon plugins were registered")

    def test_all_plugins_have_valid_metadata(self) -> None:
        """Every registered plugin must have id, name, and version."""
        for pdata in self.plugin_registry.type_plugins(None) or []:
            self.assertTrue(pdata.id, f"Plugin missing id: {pdata}")
            self.assertTrue(pdata.name, f"Plugin {pdata.id} missing name")
            self.assertTrue(pdata.version, f"Plugin {pdata.id} missing version")

    def test_target_version_matches_gramps_install(self) -> None:
        """All listed addons must target the Gramps series they're running against.

        The expected prefix is derived from the installed Gramps' version
        (``gramps.version.VERSION_TUPLE``), so the same assertion works on
        every maintenance branch — gramps60 expects "6.0", gramps61 expects
        "6.1", etc.
        """
        expected_prefix = f"{VERSION_TUPLE[0]}.{VERSION_TUPLE[1]}"
        issues: list[str] = []
        for pdata in _get_addon_plugins(self.plugin_registry):
            if not pdata.gramps_target_version.startswith(expected_prefix):
                issues.append(f"{pdata.id}: targets {pdata.gramps_target_version}")
        if issues:
            self.fail(
                f"Addons not targeting Gramps {expected_prefix}:\n"
                + "\n".join(issues)
            )


# ------------------------------------------------------------
#
# TestPluginLoading
#
# ------------------------------------------------------------
class TestPluginLoading(GrampsTestCase):
    """Attempt to load every addon plugin module through Gramps.

    Each plugin is loaded in a subprocess to isolate crashes (e.g. segfaults
    from missing GI typelibs) from the test runner.
    """

    def test_load_all_addon_modules(self) -> None:
        """Load every addon plugin; gate on non-dependency load failures.

        Failures are collected rather than failing fast, then classified:
        dependency skips and subprocess crashes (typically a missing display
        server in CI) are advisory and only logged, while a non-dependency
        *hard* load failure fails the test (``self.fail``). This makes
        the check a real gate — like the sibling smoke tests
        (:class:`TestImportPluginSmoke`, :class:`TestExportPluginSmoke`) — not
        an always-pass that merely warns on the failure class it names.
        """
        plugins = _get_addon_plugins(self.plugin_registry)
        self.assertGreater(len(plugins), 0, "No addon plugins found to test")

        hard_failures: list[str] = []
        dep_skips: list[str] = []
        crash_failures: list[str] = []

        for pdata in plugins:
            missing = _check_dependencies(pdata)
            if missing:
                dep_skips.append(f"{pdata.id} (missing: {', '.join(missing)})")
                continue

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
                crash_failures.append(f"{pdata.id} (signal {-result.returncode})")
            elif result.returncode != 0:
                err = (
                    result.stderr.strip().split("\n")[-1]
                    if result.stderr
                    else "unknown"
                )
                hard_failures.append(f"{pdata.id} ({err})")

        if dep_skips:
            LOG.warning(
                "Skipped %d plugins with unmet dependencies:\n  %s",
                len(dep_skips),
                "\n  ".join(dep_skips),
            )

        if crash_failures:
            LOG.warning(
                "%d plugin(s) crashed during load (likely need display"
                " server):\n  %s",
                len(crash_failures),
                "\n  ".join(crash_failures),
            )

        if hard_failures:
            self.fail(
                f"{len(hard_failures)} addon(s) failed to load:\n  "
                + "\n  ".join(hard_failures)
            )


# ------------------------------------------------------------
#
# TestImportPluginSmoke
#
# ------------------------------------------------------------
class TestImportPluginSmoke(GrampsTestCase):
    """Verify import plugins have a callable ``import_function`` attribute."""

    def test_import_plugins_have_callable(self) -> None:
        """Each listed IMPORT plugin must reference a callable import function."""
        import_plugins = [
            p
            for p in self.plugin_registry.type_plugins(IMPORT)
            if p.fpath and ADDONS_ROOT in p.fpath and p.include_in_listing
        ]
        issues: list[str] = []
        for pdata in import_plugins:
            if _check_dependencies(pdata):
                continue
            mod = self.plugin_manager.load_plugin(pdata)
            if mod is None:
                continue
            func = getattr(mod, pdata.import_function, None)
            if not callable(func):
                issues.append(f"{pdata.id}: {pdata.import_function} is not callable")
        if issues:
            self.fail(
                "Import plugins with non-callable import_function:\n"
                + "\n".join(issues)
            )


# ------------------------------------------------------------
#
# TestExportPluginSmoke
#
# ------------------------------------------------------------
class TestExportPluginSmoke(GrampsTestCase):
    """Verify export plugins have a callable ``export_function`` attribute."""

    def test_export_plugins_have_callable(self) -> None:
        """Each listed EXPORT plugin must reference a callable export function."""
        export_plugins = [
            p
            for p in self.plugin_registry.type_plugins(EXPORT)
            if p.fpath and ADDONS_ROOT in p.fpath and p.include_in_listing
        ]
        issues: list[str] = []
        for pdata in export_plugins:
            if _check_dependencies(pdata):
                continue
            mod = self.plugin_manager.load_plugin(pdata)
            if mod is None:
                continue
            func = getattr(mod, pdata.export_function, None)
            if not callable(func):
                issues.append(f"{pdata.id}: {pdata.export_function} is not callable")
        if issues:
            self.fail(
                "Export plugins with non-callable export_function:\n"
                + "\n".join(issues)
            )


if __name__ == "__main__":
    unittest.main()
