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
Exercise Gramps' *own* addon dependency-loading mechanism over the tree.

Where ``test_plugin_registration.py`` checks a plugin's environment
dependencies (``requires_mod`` / ``requires_gi`` / ``requires_exe``), this
module checks the **inter-addon** ``depends_on`` mechanism — the part of
``BasePluginManager.reg_plugins`` that topologically sorts plugins by
``depends_on`` and loads each dependency *before* the addons that import it, so
the dependency is already in ``sys.modules`` when the dependent's top-level
``import`` runs (``import_plugin`` adds a plugin's directory to ``sys.path``
only for the duration of its own import, then pops it — see
``gramps/gen/plug/_manager.py``).

The metadata is read from the real ``PluginRegister`` booted by
:class:`GrampsTestCase`, but the load itself is driven **in isolation**: a
booted, whole-tree registry has every dependency cached in ``sys.modules``, so
loading a dependent in-process succeeds regardless of whether it declared the
dependency — it cannot tell a correct declaration from a missing one. The
isolated subprocess removes that masking: it puts *only* the addon's own
directory (plus its declared dependencies') on ``sys.path``, so the declared
``depends_on`` is the only thing that can satisfy a load-time sibling import.
"""

# ------------------------
# Python modules
# ------------------------
import logging
import os
import re
import subprocess
import sys
import textwrap
import unittest
from typing import Any

# ------------------------
# Gramps specific
# ------------------------
from tests.gramps_test_env import GrampsTestCase
from tests.test_plugin_registration import _get_addon_plugins

LOG = logging.getLogger(__name__)


# ------------------------
# Isolated-load subprocess
# ------------------------
_LOADER = textwrap.dedent(
    """
    import sys, importlib, traceback
    # Strip the implicit "" / "." CWD entries so PEP 420 namespace packages
    # cannot let a sibling addon import as an empty package from the CWD —
    # that would silently defeat the isolation.
    sys.path[:] = [p for p in sys.path if p not in ("", ".")]
    # Pin the GI versions Gramps' launcher pins, so a version-sensitive
    # top-level ``from gi.repository import X`` in an addon does not fail on
    # an ambiguous default. This matches the addon's runtime, it is not
    # Gramps' loader.
    try:
        import gi
        # Gdk before Gtk: an addon whose top-level import lists Gdk first
        # would otherwise load Gdk at the system default (e.g. 4.0) and then
        # clash when Gtk 3.0 pulls in Gdk 3.0.
        for ns, ver in (("Gdk", "3.0"), ("Gtk", "3.0"), ("PangoCairo", "1.0")):
            try:
                gi.require_version(ns, ver)
            except (ValueError, AttributeError):
                pass
    except ImportError:
        pass
    # base_dirs holds Gramps itself (a non-addon path): the child runs under
    # -I so PYTHONPATH is ignored, and a run-from-source Gramps would
    # otherwise be unimportable. addon-from-addon isolation is unaffected.
    sys.path[:0] = [{target_dir!r}] + list({dep_dirs!r}) + list({base_dirs!r})
    try:
        importlib.import_module({module!r})
    except BaseException:
        traceback.print_exc()
        sys.exit(2)
    sys.exit(0)
    """
)


def _isolated_load(
    target_dir: str,
    dep_dirs: list[str],
    base_dirs: list[str],
    module: str,
    timeout: int = 60,
) -> tuple[int, str]:
    """Import ``module`` in a subprocess whose ``sys.path`` is tightly scoped.

    Only ``target_dir`` (the addon), ``dep_dirs`` (its declared dependencies)
    and ``base_dirs`` (Gramps itself) are added — no other addon directory —
    so a load-time sibling import can only be satisfied by a declared
    dependency. Runs under ``-I`` from a neutral CWD with ``PYTHONPATH``
    stripped, so neither environment nor working directory can leak paths in.

    :returns: ``(returncode, stderr)``; returncode ``0`` = imported,
              ``2`` = import failed, ``-1`` = timed out.
    """
    code = _LOADER.format(
        target_dir=target_dir, dep_dirs=dep_dirs, base_dirs=base_dirs, module=module
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env=env,
        )
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    return proc.returncode, proc.stderr


def _gramps_root() -> str:
    """Return the directory that must be on ``sys.path`` to ``import gramps``."""
    import gramps

    return os.path.dirname(os.path.dirname(os.path.abspath(gramps.__file__)))


def _missing_modules(stderr: str) -> set[str]:
    """Return the top-level module names ``stderr`` reports as unimportable."""
    return {m.split(".")[0] for m in re.findall(r"No module named ['\"]([^'\"]+)", stderr)}


# ------------------------------------------------------------
#
# TestAddonDependencyLoading
#
# ------------------------------------------------------------
class TestAddonDependencyLoading(GrampsTestCase):
    """Drive Gramps' ``depends_on`` resolver over the addons in this tree."""

    def _addons_with_depends(self) -> list[Any]:
        """Return registered addon plugins that declare a non-empty ``depends_on``.

        :returns: List of :class:`PluginData` whose ``depends_on`` is truthy.
        """
        return [
            pdata
            for pdata in _get_addon_plugins(self.plugin_registry)
            if pdata.depends_on
        ]

    def test_declared_dependencies_resolve_to_registered_plugins(self) -> None:
        """Every ``depends_on`` id must name a plugin Gramps actually registered.

        This is the precondition the loader's topological sort relies on: an id
        with no matching registered plugin never enters ``plugins_sorted``, so
        the dependent is reported under "Cannot resolve …" and is left unloaded.
        """
        unresolved: list[str] = []
        for pdata in self._addons_with_depends():
            for dep_id in pdata.depends_on:
                if self.plugin_registry.get_plugin(dep_id) is None:
                    unresolved.append(f"{pdata.id} -> {dep_id}")
        if unresolved:
            self.fail(
                "Addons declaring depends_on ids that are not registered "
                "(the Gramps loader cannot satisfy these):\n  "
                + "\n  ".join(sorted(unresolved))
            )

    def test_dependency_graph_is_acyclic(self) -> None:
        """The addon ``depends_on`` graph must be acyclic.

        Gramps' resolver bounds its passes by the plugin count and gives up
        on the remainder; a cycle therefore silently leaves every plugin in it
        unloaded. Walk the graph and fail loudly on any cycle instead.
        """
        edges: dict[str, list[str]] = {}
        for pdata in self._addons_with_depends():
            edges[pdata.id] = [
                dep
                for dep in pdata.depends_on
                if self.plugin_registry.get_plugin(dep) is not None
            ]

        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = {}

        def visit(node: str, trail: list[str]) -> list[str] | None:
            color[node] = GREY
            for nxt in edges.get(node, []):
                if color.get(nxt, WHITE) == GREY:
                    return trail + [node, nxt]  # back-edge: cycle found
                if color.get(nxt, WHITE) == WHITE:
                    cycle = visit(nxt, trail + [node])
                    if cycle:
                        return cycle
            color[node] = BLACK
            return None

        for start in edges:
            if color.get(start, WHITE) == WHITE:
                cycle = visit(start, [])
                if cycle:
                    self.fail("Cyclic addon depends_on chain: " + " -> ".join(cycle))

    def _addon_module_names(self) -> set[str]:
        """Return the module name of every addon plugin in the tree.

        Used to tell a *sibling-addon* import failure (a real dependency
        finding) apart from an environmental one (a missing pip module, a GI
        version clash, no display).
        """
        return {
            pdata.mod_name
            for pdata in _get_addon_plugins(self.plugin_registry)
            if pdata.mod_name
        }

    def test_declared_dependencies_are_load_bearing(self) -> None:
        """A declared dependency must actually make its dependent importable.

        For each addon that declares ``depends_on``, import its module twice in
        isolation (see :func:`_isolated_load`):

        * **with** its declared dependency directories on ``sys.path`` — if the
          import fails *because a sibling addon module is missing*, the
          declared ``depends_on`` is insufficient (an undeclared or unsatisfied
          sibling dependency — the Mantis 13707 class) and the test fails. A
          failure for any other reason (a missing pip module, a GI version
          clash, no display) is environmental, logged, and not gated — the same
          stance ``test_plugin_registration`` takes on load failures.
        * **without** them — used to confirm the dependency is genuinely needed
          at load time. A dependent that still imports without its declared
          dependency is importing it lazily (or over-declares); that is noted,
          not failed, since the loader tolerates it.

        To stay honest about the anti-pattern the whole suite guards against
        ("a silent skip must not read as a pass"), at least one dependent must
        demonstrate a real load-time dependency — otherwise this test is
        exercising nothing and fails.
        """
        dependents = self._addons_with_depends()
        if not dependents:
            self.skipTest("no addon declares depends_on in this tree")

        base_dirs = [_gramps_root()]
        addon_modules = self._addon_module_names()
        insufficient: list[str] = []  # declared deps do NOT satisfy a sibling import
        load_bearing = 0  # dependents whose dependency is provably needed at load
        for pdata in dependents:
            dep_dirs: list[str] = []
            dep_modules: set[str] = set()
            for dep_id in pdata.depends_on:
                dep = self.plugin_registry.get_plugin(dep_id)
                if dep is None:
                    continue  # resolvability is the other test's finding
                dep_dirs.append(dep.fpath)
                dep_modules.add(dep.mod_name)

            rc_with, err_with = _isolated_load(
                pdata.fpath, dep_dirs, base_dirs, pdata.mod_name
            )
            if rc_with != 0:
                # Only a *sibling addon* left unimportable is our finding;
                # everything else (GI clash, missing pip dep, display) is
                # environmental and non-gating.
                unmet = (_missing_modules(err_with) & addon_modules) - {pdata.mod_name}
                if unmet:
                    insufficient.append(
                        f"{pdata.id}: declared depends_on {pdata.depends_on} does "
                        f"not satisfy sibling import(s) {sorted(unmet)}"
                    )
                else:
                    LOG.info(
                        "%s: isolated load failed for a non-dependency reason "
                        "(environment); cannot verify its depends_on. Tail: %s",
                        pdata.id,
                        (err_with.strip().splitlines() or ["<none>"])[-1],
                    )
                continue

            rc_without, err_without = _isolated_load(
                pdata.fpath, [], base_dirs, pdata.mod_name
            )
            if rc_without != 0 and (_missing_modules(err_without) & dep_modules):
                load_bearing += 1
            elif rc_without == 0:
                LOG.info(
                    "%s imports without its depends_on %s (lazy import or "
                    "over-declared) — not a failure",
                    pdata.id,
                    pdata.depends_on,
                )
            else:
                LOG.info(
                    "%s loads with its depends_on but its without-deps failure "
                    "does not name the dependency; cannot confirm load-bearing",
                    pdata.id,
                )

        if insufficient:
            self.fail(
                "Addons whose declared depends_on does NOT satisfy their "
                "sibling imports (the loader would fail to load these):\n  "
                + "\n  ".join(insufficient)
            )
        self.assertGreater(
            load_bearing,
            0,
            "No addon demonstrated a load-time depends_on: every dependent "
            "imported fine without its declared dependency, so this test "
            "verified nothing about the loading mechanism.",
        )


if __name__ == "__main__":
    unittest.main()
