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

"""Source-built addon deps must be provisioned in CI — never a silent skip.

Regression test for the build-toolchain coverage gap (addons-source PR #820):
the CI image purged the build toolchain (gcc/python3-dev/pkg-config) after the
Gramps install, and the system packages a source-built ``requires_mod`` needs
were not provisioned on either lane. So ``pip install pygraphviz`` / ``psycopg2``
/ ``psycopg`` failed at CI runtime, the failure was swallowed by the install
step's ``|| echo … (continuing)``, and the affected addon's coverage degraded
while the job stayed green — silent coverage loss reported as success.

The fix restores the invariant *declared addon dependencies are honestly
satisfied or honestly skipped* over the WHOLE category of source-built
``requires_mod``, on BOTH CI lanes:

* apt — every source-built ``requires_mod`` has its ``-dev`` / libpq package in
  the single-source map (``addon_system_deps.MOD_BUILD_PACKAGES``), and the
  compiler toolchain stays in the CI image
  (``.github/docker/gramps-ci/Dockerfile`` no longer purges it), so pip builds /
  links the extension.
* conda — the same modules map to their prebuilt conda-forge package, so the
  Windows lane installs them (``mamba install``) instead of silently skipping;
  the conda side is NOT ``None``.

It also closes the category over *future* additions: every declared
``requires_mod`` must be classified (wheel-only or source-built), and the
``--unmapped`` drift guard fails CI on any module that is neither — so a
newly-added source-built dep cannot quietly reopen the gap.

Why this lives in ``tests/`` and not ``.github/scripts/tests/``: the C4
red→green runner derives the unittest module name from the test path
(``path.replace('/', '.')``); a ``.github/``-rooted path yields a leading-dot
module name that ``python3 -m unittest`` rejects. ``tests/`` is the repo's real
test package (alongside ``test_plugin_load_gate.py``), so the module name is
importable. Pure stdlib / no ``gi`` / no ``gramps.gui`` imports — it runs under
the headless runner. It exercises the production derivation path (the same
``packages()`` / ``unmapped()`` / CLI that ci.yml calls), not a copy of it.
"""

# ------------------------
# Python modules
# ------------------------
from __future__ import annotations

import ast
import glob
import io
import os
import re
import sys
import unittest
from contextlib import redirect_stdout

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)  # repo root (tests/ lives directly under it)
_SCRIPTS = os.path.join(_REPO_ROOT, ".github", "scripts")
_DOCKERFILE = os.path.join(_REPO_ROOT, ".github", "docker", "gramps-ci", "Dockerfile")

sys.path.insert(0, _SCRIPTS)
import addon_system_deps as deps  # noqa: E402

# The requires_mod that are built from / linked against a system package in CI
# (no plain pip wheel that imports unaided on at least one lane). Kept here as the
# test's own statement of the category, independent of the production map, so a
# regression that drops an entry from MOD_BUILD_PACKAGES is caught rather than
# mirrored. ``psycopg`` (psycopg3, PostgreSQLEnhanced) is included alongside
# ``psycopg2``/``pygraphviz`` — its pure-Python build still needs libpq at import.
_SOURCE_BUILT_MODS = ("pygraphviz", "psycopg2", "psycopg")

_REQUIRES_MOD_RE = re.compile(r"requires_mod\s*=\s*(\[[^\]]*\])")


def _declared_requires_mod() -> set[str]:
    """Union of requires_mod across every .gpr.py in the repo (as ci.yml derives)."""
    mods: set[str] = set()
    for path in glob.glob(os.path.join(_REPO_ROOT, "*", "*.gpr.py")):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        for match in _REQUIRES_MOD_RE.finditer(text):
            try:
                mods.update(ast.literal_eval(match.group(1)))
            except (ValueError, SyntaxError):
                pass
    return mods


class SourceBuiltModBuildDeps(unittest.TestCase):
    """The install list must carry every source-built requires_mod, per lane."""

    def test_known_source_built_mods_are_declared_by_some_addon(self):
        # Grounds the rest of the suite in real declarations: if these addons ever
        # drop the dep this test would otherwise pass vacuously.
        declared = _declared_requires_mod()
        for mod in _SOURCE_BUILT_MODS:
            self.assertIn(
                mod,
                declared,
                f"expected some addon's .gpr.py to declare requires_mod={mod!r}",
            )

    def test_packages_apt_includes_build_headers(self):
        apt = deps.packages("apt")
        for mod in _SOURCE_BUILT_MODS:
            pkg = deps.MOD_BUILD_PACKAGES.get(mod, {}).get("apt")
            self.assertIsNotNone(
                pkg,
                f"source-built requires_mod {mod!r} has no apt package in "
                "MOD_BUILD_PACKAGES — its CI pip build/import will fail for a "
                "missing header/library",
            )
            self.assertIn(
                pkg,
                apt,
                f"{pkg!r} (system package for {mod!r}) missing from packages('apt'); "
                "ci.yml would not install it and the source build would be silently skipped",
            )

    def test_packages_conda_provisions_source_built_mods(self):
        # The conda (Windows) lane provisions its own deps and must mirror apt:
        # pygraphviz/psycopg2/psycopg ship prebuilt on conda-forge, so the conda
        # side is the module's own conda-forge package — NEVER None (the
        # silent-skip the invariant forbids over the whole category).
        conda = deps.packages("conda")
        for mod in _SOURCE_BUILT_MODS:
            pkg = deps.MOD_BUILD_PACKAGES.get(mod, {}).get("conda")
            self.assertIsNotNone(
                pkg,
                f"source-built requires_mod {mod!r} maps to conda=None — the conda "
                "lane would not install it and the failed pip build would be "
                "swallowed into a silently-degraded green. It is on conda-forge; map it.",
            )
            self.assertIn(
                pkg,
                conda,
                f"{pkg!r} (conda package for {mod!r}) missing from packages('conda'); "
                "the Windows lane would skip the addon's suite instead of running it",
            )

    def test_cli_apt_emits_build_headers(self):
        # Exercise the exact production entry point ci.yml calls:
        #   pkgs=$(python3 addon_system_deps.py --platform apt)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = deps.main(["--platform", "apt"])
        self.assertEqual(rc, 0)
        emitted = buf.getvalue().split()
        self.assertIn("libgraphviz-dev", emitted)
        self.assertIn("libpq-dev", emitted)

    def test_cli_conda_emits_source_built_mods(self):
        # The conda step calls: pkgs=$(python addon_system_deps.py --platform conda)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = deps.main(["--platform", "conda"])
        self.assertEqual(rc, 0)
        emitted = buf.getvalue().split()
        for mod in _SOURCE_BUILT_MODS:
            self.assertIn(
                mod,
                emitted,
                f"conda --platform output is missing {mod!r}; the Windows lane "
                "would not install it",
            )

    def test_every_declared_source_built_mod_is_provisioned_on_both_lanes(self):
        # Category guard: any source-built requires_mod an addon declares must be
        # mapped AND surfaced on BOTH lanes, so a newly added one cannot silently
        # lose coverage on apt or on conda.
        apt = set(deps.packages("apt"))
        conda = set(deps.packages("conda"))
        for mod in _declared_requires_mod() & set(_SOURCE_BUILT_MODS):
            entry = deps.MOD_BUILD_PACKAGES[mod]
            for platform, available in (("apt", apt), ("conda", conda)):
                pkg = entry.get(platform)
                self.assertIsNotNone(
                    pkg,
                    f"{mod!r} maps to {platform}=None — silent skip on {platform}",
                )
                self.assertIn(pkg, available)


class RequiresModCategoryIsComplete(unittest.TestCase):
    """Every declared requires_mod must be classified — no silent new gap."""

    def test_every_declared_requires_mod_is_classified(self):
        # The heart of C5(b): each declared requires_mod is EITHER a known
        # wheel-only module OR a mapped source-built one. An unclassified module
        # is exactly how a future source-built dep would silently lose coverage.
        classified = set(deps.WHEEL_ONLY_MODS) | set(deps.MOD_BUILD_PACKAGES)
        for mod in _declared_requires_mod():
            self.assertIn(
                mod,
                classified,
                f"requires_mod {mod!r} is in neither WHEEL_ONLY_MODS nor "
                "MOD_BUILD_PACKAGES — classify it (a source-built one needs a "
                "system-package mapping or its CI coverage silently degrades)",
            )

    def test_unmapped_reports_no_mod_drift(self):
        # Drive the production drift guard ci.yml's "Validate addon system deps
        # are mapped" step runs (python3 addon_system_deps.py --unmapped .). It
        # must report no unmapped requires_mod for the current addon set.
        _gi, _exe, mod = deps.unmapped(_REPO_ROOT)
        self.assertEqual(
            mod,
            set(),
            f"--unmapped reports unclassified requires_mod {sorted(mod)!r}; "
            "ci.yml's mapping gate would fail. Classify each as wheel-only or "
            "source-built.",
        )

    def test_unmapped_cli_exit_zero(self):
        # The full CLI the validate step invokes must exit 0 (no drift) today.
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = deps.main(["--unmapped", _REPO_ROOT])
        self.assertEqual(
            rc,
            0,
            "addon_system_deps.py --unmapped exits non-zero — an addon declares a "
            f"GI/exe/mod dep with no mapping:\n{buf.getvalue()}",
        )


class CiImageKeepsBuildToolchain(unittest.TestCase):
    """The image must keep the compiler toolchain the apt builds use."""

    @classmethod
    def setUpClass(cls):
        with open(_DOCKERFILE, encoding="utf-8") as fh:
            cls.lines = [
                ln
                for ln in fh.read().splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")
            ]

    def test_toolchain_not_purged(self):
        # The defect was a `RUN apt-get purge -y gcc python3-dev pkg-config` after
        # the Gramps install, removing the compiler before CI-runtime source
        # builds of requires_mod run.
        for line in self.lines:
            if "apt-get purge" in line or "apt-get remove" in line:
                for tool in ("gcc", "pkg-config", "python3-dev"):
                    self.assertNotIn(
                        tool,
                        line,
                        f"Dockerfile purges build toolchain ({tool!r}) — "
                        "CI-runtime source builds of requires_mod will have no compiler:\n"
                        f"    {line.strip()}",
                    )

    def test_toolchain_is_installed(self):
        text = "\n".join(self.lines)
        for tool in ("gcc", "pkg-config"):
            self.assertIn(
                tool,
                text,
                f"Dockerfile no longer installs {tool!r}; source-built requires_mod "
                "cannot compile in CI",
            )


if __name__ == "__main__":
    unittest.main()
