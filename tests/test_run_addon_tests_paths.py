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
Tests for ``run_addon_tests.py``'s per-addon import root (issue #52).

The runner appends each addon's own directory to ``sys.path`` before loading
its tests, mirroring how Gramps' plugin loader puts the addon dir on the path.
This lets an addon's tests import the addon's top-level modules
(``from <addonlib> import …``) — including a nested-package addon whose test
modules live under ``<Addon>/tests/<subpkg>/`` — while the repo-root shared
``tests`` environment still wins (APPEND, not prepend).

Driven via subprocess against synthetic addon trees in a temp dir, so no gramps
install is needed.
"""

# ------------------------
# Python modules
# ------------------------
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


ADDONS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ADDON_TESTS = os.path.join(ADDONS_ROOT, ".github", "scripts", "run_addon_tests.py")


@unittest.skipUnless(
    os.path.isfile(RUN_ADDON_TESTS), "run_addon_tests.py not present on this branch"
)
class RunAddonTestsPathsTest(unittest.TestCase):
    """The runner must load nested- and flat-package addon tests by adding the
    addon dir to sys.path, without shadowing the shared repo-root tests env."""

    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="run_addon_tests_paths_")
        # Stand-in for the repo-root shared Gramps-emulation env (PR 950):
        # a top-level `tests` package the addon tests may import.
        self._write("tests/__init__.py", "")
        self._write("tests/gramps_test_env.py", 'SENTINEL = "repo-root-shared-env"\n')

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, relpath: str, content: str) -> None:
        path = os.path.join(self.root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(content)

    def _run(
        self,
        modname: str,
        platform: str = "apt",
        extra_env: dict | None = None,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = "."  # repo root on sys.path, as ci.yml sets it
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [
                sys.executable,
                RUN_ADDON_TESTS,
                "--platform",
                platform,
                "--root",
                self.root,
                modname,
            ],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_nested_package_addon_loads(self) -> None:
        """A nested-package addon: test module under tests/<subpkg>/, importing
        the addon's top-level lib AND the shared repo-root tests env."""
        # Namespace-package top (no SynthAddon/__init__.py); top-level lib module.
        self._write("SynthAddon/synthlib.py", "VALUE = 42\n")
        self._write("SynthAddon/tests/__init__.py", "")
        self._write("SynthAddon/tests/sub/__init__.py", "")
        self._write(
            "SynthAddon/tests/sub/test_nested.py",
            "import unittest\n"
            "from synthlib import VALUE\n"  # per-addon import root
            "from tests.gramps_test_env import SENTINEL\n"  # shared env not shadowed
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_addon_lib(self):\n"
            "        self.assertEqual(VALUE, 42)\n"
            "    def test_shared_env(self):\n"
            '        self.assertEqual(SENTINEL, "repo-root-shared-env")\n',
        )

        result = self._run("SynthAddon.tests.sub.test_nested")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, "runner failed:\n%s" % out)
        self.assertIn("ok    SynthAddon.tests.sub.test_nested", result.stdout, out)

    def test_flat_model_b_addon_loads(self) -> None:
        """A flat addon whose test imports a top-level addon module
        (WebSearch-style) — currently broken without the per-addon import root."""
        self._write("FlatAddon/flatlib.py", "FLAT = 7\n")
        self._write("FlatAddon/tests/__init__.py", "")
        self._write(
            "FlatAddon/tests/test_flat.py",
            "import unittest\n"
            "from flatlib import FLAT\n"
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_flat(self):\n"
            "        self.assertEqual(FLAT, 7)\n",
        )

        result = self._run("FlatAddon.tests.test_flat")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, "runner failed:\n%s" % out)
        self.assertIn("ok    FlatAddon.tests.test_flat", result.stdout, out)

    # ------------------------------------------------------------------
    # Outcome classification (load-failure taxonomy, zero-test, timeout,
    # tolerant timeout env) — adversarial-review findings F1-F4/F10.
    # GooCanvas is apt-provisioned but conda:None (addon_system_deps.GI_PACKAGES),
    # so a `requires_gi=[("GooCanvas","2.0")]` addon is unsatisfiable on conda
    # and satisfiable on apt — the lever these tests use.
    # ------------------------------------------------------------------
    def _write_gi_addon(self, addon: str, test_body: str) -> None:
        self._write(
            f"{addon}/{addon.lower()}.gpr.py",
            f'register(GRAMPLET, id="{addon}", requires_gi=[("GooCanvas", "2.0")])\n',
        )
        self._write(f"{addon}/tests/__init__.py", "")
        self._write(f"{addon}/tests/test_x.py", test_body)

    def test_syntax_error_fails_even_on_unsatisfiable_platform(self) -> None:
        # A SyntaxError is a code bug, never a dependency shape — it must FAIL
        # even where the addon's declared GI dep is unavailable (conda).
        self._write_gi_addon("GiSyntax", "def broken(:\n    pass\n")
        result = self._run("GiSyntax.tests.test_x", platform="conda")
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, out)
        self.assertIn("not dependency-shaped", out)

    def test_dep_import_error_skips_on_unsatisfiable_platform(self) -> None:
        # A dependency-shaped load failure (ImportError) where the addon's deps
        # are unavailable is an expected platform skip.
        self._write_gi_addon(
            "GiDepSkip", "import definitely_not_installed_xyz  # noqa\n"
        )
        result = self._run("GiDepSkip.tests.test_x", platform="conda")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("skip", result.stdout)

    def test_dep_import_error_fails_on_satisfiable_platform(self) -> None:
        # The same ImportError where the addon declares no unsatisfiable dep
        # (satisfiable on apt) is a real failure, not a skip.
        self._write(
            "PlainAddon/plainaddon.gpr.py", 'register(GRAMPLET, id="PlainAddon")\n'
        )
        self._write("PlainAddon/tests/__init__.py", "")
        self._write(
            "PlainAddon/tests/test_x.py",
            "import definitely_not_installed_xyz  # noqa\n",
        )
        result = self._run("PlainAddon.tests.test_x", platform="apt")
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, out)

    def test_zero_collected_tests_fails(self) -> None:
        # A module that loads but collects no tests reads as green under plain
        # unittest; the runner must fail it.
        self._write(
            "EmptyAddon/emptyaddon.gpr.py", 'register(GRAMPLET, id="EmptyAddon")\n'
        )
        self._write("EmptyAddon/tests/__init__.py", "")
        self._write(
            "EmptyAddon/tests/test_x.py",
            "class NotATestCase:\n    def test_nope(self):\n        pass\n",
        )
        result = self._run("EmptyAddon.tests.test_x", platform="apt")
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, out)
        self.assertIn("zero tests", out)

    def test_non_integer_timeout_env_is_tolerated(self) -> None:
        # A non-integer RUN_ADDON_TESTS_TIMEOUT must not crash the runner.
        self._write("OkAddon/okaddon.gpr.py", 'register(GRAMPLET, id="OkAddon")\n')
        self._write("OkAddon/tests/__init__.py", "")
        self._write(
            "OkAddon/tests/test_x.py",
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertTrue(True)\n",
        )
        result = self._run(
            "OkAddon.tests.test_x",
            platform="apt",
            extra_env={"RUN_ADDON_TESTS_TIMEOUT": "soon"},
        )
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("ignoring non-integer", result.stderr)

    def test_same_named_addon_module_does_not_shadow_package(self) -> None:
        # Regression: many addons ship <Addon>/<Addon>.py. Once <Addon>/ is on
        # sys.path (for the tests' bare sibling imports) that regular module wins
        # the bare name over the namespace-package directory, and the dotted test
        # name <Addon>.tests.test_x died with "module '<Addon>' has no attribute
        # 'tests'" — 11 real addons failed this way on CI.
        self._write("ShadowAddon/shadowaddon.gpr.py", 'register(GRAMPLET, id="s")\n')
        self._write("ShadowAddon/ShadowAddon.py", "MAIN = 'addon main module'\n")
        self._write("ShadowAddon/sibling.py", "SIB = 5\n")
        self._write("ShadowAddon/tests/__init__.py", "")
        self._write(
            "ShadowAddon/tests/test_x.py",
            "import unittest\n"
            "from sibling import SIB\n"  # bare sibling import needs addon dir
            "\n"
            "class T(unittest.TestCase):\n"
            "    def test_sibling(self):\n"
            "        self.assertEqual(SIB, 5)\n",
        )
        result = self._run("ShadowAddon.tests.test_x", platform="apt")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("ok    ShadowAddon.tests.test_x", result.stdout, out)

    def test_module_level_skiptest_is_honored(self) -> None:
        # A module that raises SkipTest at import is explicitly opting out (the
        # addon's own "needs a display / PyGObject" guard) — honour it as a skip
        # on every platform, never a failure.
        self._write("SkipAddon/skipaddon.gpr.py", 'register(GRAMPLET, id="s")\n')
        self._write("SkipAddon/tests/__init__.py", "")
        self._write(
            "SkipAddon/tests/test_x.py",
            "import unittest\nraise unittest.SkipTest('no display here')\n",
        )
        result = self._run("SkipAddon.tests.test_x", platform="apt")
        out = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, out)
        self.assertIn("opted out", out)

    @unittest.skipUnless(os.name == "posix", "process-group kill is POSIX-only")
    def test_timeout_reaps_grandchild_holding_stdout(self) -> None:
        # A test that spawns a long-lived child inheriting the worker's stdout
        # must not defeat the timeout: the whole process group is reaped and the
        # follow-up communicate() is bounded, so the runner returns promptly.
        import time

        self._write(
            "HangAddon/hangaddon.gpr.py", 'register(GRAMPLET, id="HangAddon")\n'
        )
        self._write("HangAddon/tests/__init__.py", "")
        self._write(
            "HangAddon/tests/test_x.py",
            "import subprocess, sys, time, unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_hang(self):\n"
            # child inherits stdout (the worker's pipe); then the test blocks
            "        subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            "        time.sleep(120)\n",
        )
        start = time.monotonic()
        result = self._run(
            "HangAddon.tests.test_x",
            platform="apt",
            extra_env={"RUN_ADDON_TESTS_TIMEOUT": "3"},
        )
        elapsed = time.monotonic() - start
        out = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, out)
        self.assertIn("timed out", out)
        self.assertLess(elapsed, 45, f"timeout not bounded (took {elapsed:.1f}s)")


if __name__ == "__main__":
    unittest.main()
