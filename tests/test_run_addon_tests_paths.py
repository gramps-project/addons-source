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
RUN_ADDON_TESTS = os.path.join(
    ADDONS_ROOT, ".github", "scripts", "run_addon_tests.py"
)


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
        self._write(
            "tests/gramps_test_env.py", 'SENTINEL = "repo-root-shared-env"\n'
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, relpath: str, content: str) -> None:
        path = os.path.join(self.root, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(content)

    def _run(self, modname: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = "."  # repo root on sys.path, as ci.yml sets it
        return subprocess.run(
            [
                sys.executable,
                RUN_ADDON_TESTS,
                "--platform",
                "apt",
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
            "from synthlib import VALUE\n"            # per-addon import root
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


if __name__ == "__main__":
    unittest.main()
