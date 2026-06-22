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
Integration tests for ``make.py``'s i18n string extraction.

Runs ``make.py <ver> init <Addon>`` as a subprocess against synthetic addon
trees and inspects the generated ``po/template.pot``. Verifies that extraction
reaches NESTED package modules (issue #51 — previously only the addon's
top-level ``*.py`` was scanned), that the addon's own ``tests/`` tree is
excluded, and that a flat addon still references only its top-level files (the
strict no-op invariant for flat addons).
"""

# ------------------------
# Python modules
# ------------------------
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ADDONS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKE_PY = os.path.join(ADDONS_ROOT, "make.py")


def _gramps_env():
    """Return ``(gramps_version_dir, gramps_target_version, env)`` for driving
    make.py, or ``(None, None, None)`` if gramps is not importable.

    ``make.py … init <addon>`` imports ``gramps.gen.plug.make_environment`` from
    ``GRAMPSPATH`` to exec each ``.gpr.py``; we derive GRAMPSPATH from the
    importable gramps so the same test runs against a 6.0 or 6.1 install.
    """
    try:
        import gramps
        import gramps.version
    except Exception:  # gramps not on path → caller skips
        return None, None, None
    major, minor = gramps.version.VERSION_TUPLE[:2]
    env = os.environ.copy()
    env.setdefault(
        "GRAMPSPATH", os.path.dirname(os.path.dirname(gramps.__file__))
    )
    return "gramps%d%d" % (major, minor), "%d.%d" % (major, minor), env


GRAMPS_VERSION, GRAMPS_TARGET, GRAMPS_ENV = _gramps_env()
HAVE_XGETTEXT = shutil.which("xgettext") is not None

# A .gpr.py registering one listable gramplet, so make.py's init "is this addon
# listable?" guard passes. Plain quotes (no _()) — the gpr is not the unit under
# test here; the modules carrying _() strings are.
_GPR = """\
register(GRAMPLET,
    id='{name}',
    name='{name}',
    description='Synthetic test addon',
    version='1.0.0',
    gramps_target_version='{target}',
    status=STABLE,
    fname='{name}.py',
    height=200,
    gramplet='{name}',
    gramplet_title='{name}',
)
"""


@unittest.skipUnless(
    GRAMPS_VERSION and HAVE_XGETTEXT, "needs an importable gramps and xgettext"
)
class I18nExtractionTest(unittest.TestCase):
    """``make.py init`` must extract strings from nested package modules."""

    def setUp(self) -> None:
        self.workdir = tempfile.mkdtemp(prefix="i18n_extract_test_")
        self.src = os.path.join(self.workdir, "addons-source")
        os.makedirs(self.src)
        shutil.copy(MAKE_PY, self.src)

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _write(self, relpath: str, content: str) -> None:
        path = os.path.join(self.src, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(content)

    def _init(self, addon: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "make.py", GRAMPS_VERSION, "init", addon],
            cwd=self.src,
            env=GRAMPS_ENV,
            capture_output=True,
            text=True,
            check=False,
        )

    def _pot(self, addon: str) -> str:
        with open(
            os.path.join(self.src, addon, "po", "template.pot"), encoding="utf-8"
        ) as fp:
            return fp.read()

    @staticmethod
    def _referenced_py(pot: str) -> set:
        """The .py source files referenced by the pot's ``#:`` location lines."""
        files = set()
        for line in pot.splitlines():
            if line.startswith("#:"):
                for tok in line[2:].split():
                    match = re.match(r"(\S+\.py):\d+", tok)
                    if match:
                        files.add(match.group(1))
        return files

    def test_nested_strings_extracted_and_tests_excluded(self) -> None:
        name = "NestedAddon"
        self._write(
            f"{name}/{name}.gpr.py", _GPR.format(name=name, target=GRAMPS_TARGET)
        )
        self._write(f"{name}/{name}.py", 'def f():\n    return _("flat top-level string")\n')
        self._write(f"{name}/pkg/__init__.py", "")
        self._write(
            f"{name}/pkg/nested.py", 'def g():\n    return _("nested package string")\n'
        )
        self._write(f"{name}/tests/__init__.py", "")
        self._write(
            f"{name}/tests/test_x.py",
            'def t():\n    return _("test-only string must not ship")\n',
        )

        result = self._init(name)
        self.assertEqual(
            result.returncode,
            0,
            "make.py init failed\nstdout:\n%s\nstderr:\n%s"
            % (result.stdout, result.stderr),
        )

        pot = self._pot(name)
        self.assertIn("flat top-level string", pot)
        self.assertIn(
            "nested package string",
            pot,
            "issue #51: strings in nested package modules must be extracted",
        )
        self.assertNotIn(
            "test-only string must not ship",
            pot,
            "the addon's own tests/ tree must be excluded from extraction",
        )

        refs = self._referenced_py(pot)
        self.assertIn(f"{name}/pkg/nested.py", refs)
        self.assertTrue(
            all("/tests/" not in r for r in refs),
            "no tests/ file should be referenced; got %r" % (refs,),
        )

    def test_flat_addon_references_only_top_level(self) -> None:
        """Flat addon (no nested package): extraction must be unchanged — only
        top-level .py files are referenced."""
        name = "FlatAddon"
        self._write(
            f"{name}/{name}.gpr.py", _GPR.format(name=name, target=GRAMPS_TARGET)
        )
        self._write(f"{name}/{name}.py", 'def f():\n    return _("flat alpha")\n')
        self._write(f"{name}/extra.py", 'def h():\n    return _("flat beta")\n')

        result = self._init(name)
        self.assertEqual(
            result.returncode,
            0,
            "make.py init failed\nstdout:\n%s\nstderr:\n%s"
            % (result.stdout, result.stderr),
        )

        pot = self._pot(name)
        self.assertIn("flat alpha", pot)
        self.assertIn("flat beta", pot)

        refs = self._referenced_py(pot)
        # Top-level files have exactly one path separator ("FlatAddon/x.py");
        # a nested file would have two. None should be nested.
        self.assertTrue(
            refs and all(r.count("/") == 1 for r in refs),
            "flat addon should reference only top-level files; got %r" % (refs,),
        )


if __name__ == "__main__":
    unittest.main()
