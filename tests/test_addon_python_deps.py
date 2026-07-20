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

"""The requires_mod machinery must track Gramps' own (gramps PR #2308).

gramps 6.1 ships an install-time authority for addon Python deps:
``gramps/gen/utils/pypi.py`` with the import→distribution table
``_IMPORT_TO_PYPI``, and a ``Requirements.check_mod`` that really imports the
module after ``find_spec`` (merged as 7f94428b13; not backported to 6.0).
``addon_python_deps.py`` accounts for both at lookup time:

* ``_distribution_map()`` prefers the installed gramps' ``_IMPORT_TO_PYPI``
  over the local ``_IMPORT_TO_DISTRIBUTION`` fallback mirror, so 6.1+ lanes
  install exactly what Gramps' own installer would — including entries added
  upstream after this file was written.
* ``_module_checker()`` delegates ``--check-resolves`` to the installed
  gramps' ``Requirements().check_mod``, so the gate is find_spec-only on 6.0
  and find_spec-plus-real-import on 6.1+, per lane, automatically.
* the pip-installed-ness probe uses the *mapped distribution* name — ``pip
  show PIL`` fails even with Pillow installed, so probing the raw import name
  silently skipped exactly the declarations the mapping machinery exists for.

These tests pin the two seams and the probe fix hermetically (fake gramps
module trees injected via ``mock.patch.dict(sys.modules, ...)``; no network,
no real gramps needed), plus one sync-guard that compares the fallback mirror
against the real authority table wherever gramps >= 6.1 is importable.

NOTE on the sync-guard's reach: it is LATENT until these workflows land on
``maintenance/gramps61``. Today no CI lane imports a gramps that ships
``gramps.gen.utils.pypi`` — the gramps60 image predates it, and the conda
Windows lane pins 6.0.x — so every lane skips the guard; it self-activates
when the pipeline reaches the 6.1 branch. Keep it: the cost is one skipped
test until then, and it is the only place a mirror-vs-authority drift is
caught once 6.1 arrives.

Import guards use ``except (Exception, SystemExit)`` throughout: a
half-installed gramps (raw source checkout on sys.path) raises ``SystemExit``
from ResourcePath at import, not ImportError.
"""

# ------------------------
# Python modules
# ------------------------
from __future__ import annotations

import io
import os
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)  # repo root (tests/ lives directly under it)
_SCRIPTS = os.path.join(_REPO_ROOT, ".github", "scripts")

sys.path.insert(0, _SCRIPTS)
import addon_python_deps as deps  # noqa: E402


def _fake_gramps_tree(**leaves: types.ModuleType) -> dict[str, types.ModuleType]:
    """A sys.modules overlay for ``gramps.gen.utils`` plus the given leaves.

    ``leaves`` maps a leaf module name (``pypi``, ``requirements``) to a fake
    module; the returned dict contains the full parent chain with attributes
    linked, ready for ``mock.patch.dict(sys.modules, ...)``.
    """
    gramps = types.ModuleType("gramps")
    gen = types.ModuleType("gramps.gen")
    utils = types.ModuleType("gramps.gen.utils")
    gramps.gen = gen
    gen.utils = utils
    tree = {"gramps": gramps, "gramps.gen": gen, "gramps.gen.utils": utils}
    for name, module in leaves.items():
        setattr(utils, name, module)
        tree[f"gramps.gen.utils.{name}"] = module
    return tree


def _no_gramps_overlay() -> dict[str, None]:
    """A sys.modules overlay under which every ``import gramps...`` fails.

    A top-level ``{"gramps": None}`` alone is NOT enough: ``from
    gramps.gen.utils.requirements import Requirements`` short-circuits on a
    cached ``sys.modules['gramps.gen.utils.requirements']`` and never consults
    the None-ed parent. And a cached submodule is the norm on CI — unittest
    discovery imports ``test_plugin_registration``, which imports
    ``gramps.gen.utils.requirements`` at module level, before these tests run.
    So None-out the top-level name AND every already-cached ``gramps.*`` key;
    that restores the ImportError the fallback branches must see.
    """
    overlay: dict[str, None] = {"gramps": None}
    for name in list(sys.modules):
        if name == "gramps" or name.startswith("gramps."):
            overlay[name] = None
    return overlay


class GrampsTableSync(unittest.TestCase):
    """The fallback mirror must equal Gramps' authority table (gramps >= 6.1)."""

    def test_local_mirror_matches_gramps_table(self) -> None:
        try:
            from gramps.gen.utils import pypi
        except (Exception, SystemExit):
            self.skipTest(
                "gramps.gen.utils.pypi not importable — the sync-guard gates "
                "on gramps >= 6.1 lanes; the mirror is inert here"
            )
        # A loud failure on rename: at runtime getattr degrades safely to the
        # mirror, so THIS assertion is the only place an upstream rename of
        # _IMPORT_TO_PYPI surfaces.
        self.assertTrue(
            hasattr(pypi, "_IMPORT_TO_PYPI"),
            "gramps.gen.utils.pypi no longer exposes _IMPORT_TO_PYPI — "
            "update _distribution_map() and this mirror sync-guard",
        )
        self.assertEqual(
            dict(pypi._IMPORT_TO_PYPI),
            deps._IMPORT_TO_DISTRIBUTION,
            "_IMPORT_TO_DISTRIBUTION has drifted from gramps' "
            "_IMPORT_TO_PYPI — re-sync the fallback mirror in "
            ".github/scripts/addon_python_deps.py",
        )


class DistributionMapSeam(unittest.TestCase):
    """_distribution_map(): authority when present, mirror otherwise."""

    def test_prefers_gramps_table(self) -> None:
        fake_pypi = types.ModuleType("gramps.gen.utils.pypi")
        fake_pypi._IMPORT_TO_PYPI = {"PIL": "Pillow", "fake_mod": "fake-dist"}
        with mock.patch.dict(sys.modules, _fake_gramps_tree(pypi=fake_pypi)):
            table = deps._distribution_map()
        self.assertEqual(table["fake_mod"], "fake-dist")
        self.assertEqual(table["PIL"], "Pillow")

    def test_falls_back_without_gramps(self) -> None:
        # Seed a cached gramps.gen.utils.pypi FIRST (as the integration lane's
        # discovery would leave gramps submodules cached), then apply the
        # overlay on top: the fallback must still fire, proving the overlay
        # defeats a pre-cached submodule and not merely an absent gramps.
        fake_pypi = types.ModuleType("gramps.gen.utils.pypi")
        fake_pypi._IMPORT_TO_PYPI = {"PIL": "Pillow", "seeded": "seeded-dist"}
        with mock.patch.dict(sys.modules, _fake_gramps_tree(pypi=fake_pypi)):
            with mock.patch.dict(sys.modules, _no_gramps_overlay()):
                table = deps._distribution_map()
        self.assertEqual(table, deps._IMPORT_TO_DISTRIBUTION)

    def test_falls_back_when_table_attr_missing(self) -> None:
        # Pins the safe-degradation path an upstream rename would take.
        fake_pypi = types.ModuleType("gramps.gen.utils.pypi")
        with mock.patch.dict(sys.modules, _fake_gramps_tree(pypi=fake_pypi)):
            table = deps._distribution_map()
        self.assertEqual(table, deps._IMPORT_TO_DISTRIBUTION)


class ModuleCheckerSeam(unittest.TestCase):
    """_module_checker(): Gramps' own gate when present, find_spec otherwise."""

    def test_delegates_to_gramps_check_mod(self) -> None:
        calls: list[str] = []

        class _FakeRequirements:
            def check_mod(self, name: str) -> bool:
                calls.append(name)
                return name == "good_mod"

        fake_req = types.ModuleType("gramps.gen.utils.requirements")
        fake_req.Requirements = _FakeRequirements
        with mock.patch.dict(sys.modules, _fake_gramps_tree(requirements=fake_req)):
            label, check = deps._module_checker()
            self.assertIn("check_mod", label)
            self.assertTrue(check("good_mod"))
            self.assertFalse(check("bad_mod"))
        self.assertEqual(calls, ["good_mod", "bad_mod"])

    def test_stdlib_fallback(self) -> None:
        # Seed a cached gramps.gen.utils.requirements FIRST (exactly what
        # unittest discovery of test_plugin_registration leaves behind on the
        # integration lane), then overlay: the checker must STILL fall back to
        # find_spec. Without the full-tree overlay this false-red'd — the
        # delegated path was taken because the submodule was already cached.
        fake_req = types.ModuleType("gramps.gen.utils.requirements")

        class _FakeRequirements:
            def check_mod(self, name: str) -> bool:  # pragma: no cover
                return True

        fake_req.Requirements = _FakeRequirements
        with mock.patch.dict(sys.modules, _fake_gramps_tree(requirements=fake_req)):
            with mock.patch.dict(sys.modules, _no_gramps_overlay()):
                label, check = deps._module_checker()
                self.assertIn("find_spec", label)
                self.assertTrue(check("os"))
                self.assertFalse(check("definitely_not_a_module_xyz"))


class CheckResolvesGate(unittest.TestCase):
    """check_resolves(): probe by distribution name, judge by import name."""

    def _run(
        self,
        *,
        check,
        pip_ok_for: set[str],
        recorded: list[list[str]],
        declared: set[str] | None = None,
        dist_map: dict[str, str] | None = None,
    ):
        """Drive check_resolves hermetically.

        Defaults to one declared mod, ``PIL`` → ``Pillow``. Pass ``declared`` /
        ``dist_map`` to exercise the wheel-only vs source-built branches against
        the REAL classification sets (WHEEL_ONLY_MODS is not mocked).
        """
        declared = {"PIL"} if declared is None else declared
        dist_map = {"PIL": "Pillow"} if dist_map is None else dist_map

        def fake_run(argv, **kwargs):
            recorded.append(list(argv))
            rc = 0 if argv[-1] in pip_ok_for else 1
            return types.SimpleNamespace(returncode=rc)

        out = io.StringIO()
        with (
            mock.patch.object(deps, "declared_mods", return_value=declared),
            mock.patch.object(deps, "_distribution_map", return_value=dist_map),
            mock.patch.object(
                deps, "_module_checker", return_value=("test gate", check)
            ),
            mock.patch("subprocess.run", side_effect=fake_run),
            redirect_stdout(out),
        ):
            rc = deps.check_resolves(".")
        return rc, out.getvalue()

    def test_probe_uses_distribution_name(self) -> None:
        # Regression: `pip show PIL` fails even with Pillow installed, so the
        # old raw-name probe skipped ("~") the one declaration the mapping
        # machinery exists for — never validating it.
        recorded: list[list[str]] = []
        checked: list[str] = []

        def check(name: str) -> bool:
            checked.append(name)
            return True

        rc, out = self._run(check=check, pip_ok_for={"Pillow"}, recorded=recorded)
        self.assertEqual(rc, 0)
        pip_show = [argv for argv in recorded if "show" in argv]
        self.assertTrue(pip_show and pip_show[0][-1] == "Pillow", pip_show)
        self.assertNotIn("~", out)
        self.assertIn("ok PIL", out)
        # The gate must JUDGE the raw import name, never the distribution name —
        # gramps' check_mod("Pillow") would wrongly fail a correct requires_mod
        # =["PIL"]. (Kills the M1b mutant that passed `dist` to the checker.)
        self.assertEqual(checked, ["PIL"])

    def test_installed_but_unresolvable_fails(self) -> None:
        recorded: list[list[str]] = []
        checked: list[str] = []

        def check(name: str) -> bool:
            checked.append(name)
            return False

        rc, out = self._run(check=check, pip_ok_for={"Pillow"}, recorded=recorded)
        self.assertEqual(rc, 1)
        self.assertIn("x  PIL", out)
        self.assertIn("::error::", out)
        self.assertEqual(checked, ["PIL"])

    def test_wheel_only_never_installed_fails(self) -> None:
        # A wheel-only dep (PIL is in the real WHEEL_ONLY_MODS) that pip never
        # installed is a provisioning regression, not an environment gap: the
        # gate must FAIL, and must not even consult the dep checker.
        self.assertIn("PIL", deps.WHEEL_ONLY_MODS)  # guard the fixture premise
        recorded: list[list[str]] = []
        checked: list[str] = []

        def check(name: str) -> bool:
            checked.append(name)
            return True

        rc, out = self._run(
            check=check, pip_ok_for=set(), recorded=recorded
        )  # nothing installs
        self.assertEqual(rc, 1)
        self.assertIn("wheel-only", out)
        self.assertIn("::error::Wheel-only", out)
        self.assertEqual(
            checked, [], "a never-installed wheel must not be gate-checked"
        )

    def test_source_built_never_installed_stays_advisory(self) -> None:
        # A source-built dep (pygraphviz is in the real MOD_BUILD_PACKAGES, not
        # WHEEL_ONLY_MODS) may legitimately miss on an image/system gap: advisory
        # skip, rc 0.
        self.assertNotIn("pygraphviz", deps.WHEEL_ONLY_MODS)  # guard the premise
        recorded: list[list[str]] = []
        rc, out = self._run(
            check=lambda name: True,
            pip_ok_for=set(),
            recorded=recorded,
            declared={"pygraphviz"},
            dist_map={},
        )
        self.assertEqual(rc, 0)
        self.assertIn("~  pygraphviz", out)


if __name__ == "__main__":
    unittest.main()
