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
against the real authority table wherever gramps >= 6.1 is importable — the
gramps61 CI lanes — and skips elsewhere. Mirror drift can only originate from
a 6.1+ table change, which exactly those lanes catch.

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


# The overlay that makes every ``import gramps...`` raise ImportError, even on
# a machine where the real gramps is importable (None in sys.modules halts the
# import of the top-level package before any submodule is considered).
_NO_GRAMPS = {"gramps": None}


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
        with mock.patch.dict(sys.modules, _NO_GRAMPS):
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
        with mock.patch.dict(sys.modules, _NO_GRAMPS):
            label, check = deps._module_checker()
        self.assertIn("find_spec", label)
        self.assertTrue(check("os"))
        self.assertFalse(check("definitely_not_a_module_xyz"))


class CheckResolvesGate(unittest.TestCase):
    """check_resolves(): probe by distribution name, judge by import name."""

    def _run(self, *, check, pip_ok_for: set[str], recorded: list[list[str]]):
        """Drive check_resolves with one declared mod, ``PIL``, hermetically."""

        def fake_run(argv, **kwargs):
            recorded.append(list(argv))
            rc = 0 if argv[-1] in pip_ok_for else 1
            return types.SimpleNamespace(returncode=rc)

        out = io.StringIO()
        with (
            mock.patch.object(deps, "declared_mods", return_value={"PIL"}),
            mock.patch.object(
                deps, "_distribution_map", return_value={"PIL": "Pillow"}
            ),
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
        rc, out = self._run(
            check=lambda name: True, pip_ok_for={"Pillow"}, recorded=recorded
        )
        self.assertEqual(rc, 0)
        pip_show = [argv for argv in recorded if "show" in argv]
        self.assertTrue(pip_show and pip_show[0][-1] == "Pillow", pip_show)
        self.assertNotIn("~", out)
        self.assertIn("ok PIL", out)

    def test_installed_but_unresolvable_fails(self) -> None:
        recorded: list[list[str]] = []
        rc, out = self._run(
            check=lambda name: False, pip_ok_for={"Pillow"}, recorded=recorded
        )
        self.assertEqual(rc, 1)
        self.assertIn("x  PIL", out)
        self.assertIn("::error::", out)


if __name__ == "__main__":
    unittest.main()
