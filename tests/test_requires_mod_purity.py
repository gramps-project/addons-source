#
# Gramps addons
#
# Copyright (C) 2025  Gramps Development Team
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Verify that every ``requires_mod`` entry in addon .gpr.py files is a
pure-Python package.

Gramps is distributed as a self-contained bundle on Windows (AIO) and
macOS (.app).  In those builds ``sys.executable`` is the Gramps launcher
binary, not a Python interpreter, so pip must run in-process via
``runpy``.  Compiled extensions (.so / .pyd) installed this way often
fail to load because the bundle does not carry their native library
dependencies.  Only pure-Python packages are safe to declare in
``requires_mod``.

This test finds every ``requires_mod=[...]`` declaration in the repo,
and for each module that is actually installed on the current machine it
checks whether that module contains compiled extension files.  A compiled
module causes the test to fail so addon authors are alerted during CI.

Modules that are not installed are skipped (we cannot inspect them).
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import ast
import importlib.util
import os
import unittest

# -------------------------------------------------------------------------
#
# Helpers
#
# -------------------------------------------------------------------------

ADDONS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_COMPILED_SUFFIXES = (".so", ".pyd")


def _has_compiled_files(directory: str) -> bool:
    """Return True if *directory* contains any compiled extension files."""
    for _root, _dirs, files in os.walk(directory):
        for fname in files:
            if fname.endswith(_COMPILED_SUFFIXES):
                return True
    return False


def _is_compiled_module(module_name: str) -> bool | None:
    """
    Return True if the named module contains compiled extensions,
    False if it is pure Python, or None if it is not installed.
    """
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return None

    # Single-file module (e.g. a plain .py or a .so)
    if spec.origin:
        if spec.origin.endswith(_COMPILED_SUFFIXES):
            return True

    # Package: check all files in the package directory
    if spec.submodule_search_locations:
        for location in spec.submodule_search_locations:
            if os.path.isdir(location) and _has_compiled_files(location):
                return True

    return False


def _collect_requires_mod() -> dict[str, list[str]]:
    """
    Walk every .gpr.py file in the repo and return a mapping of
    ``addon_name -> [module, ...]`` for all ``requires_mod`` declarations.
    """
    result: dict[str, list[str]] = {}
    for entry in sorted(os.listdir(ADDONS_ROOT)):
        addon_dir = os.path.join(ADDONS_ROOT, entry)
        if not os.path.isdir(addon_dir):
            continue
        for fname in os.listdir(addon_dir):
            if not fname.endswith(".gpr.py"):
                continue
            gpr_path = os.path.join(addon_dir, fname)
            try:
                with open(gpr_path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=gpr_path)
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg != "requires_mod":
                        continue
                    if not isinstance(kw.value, ast.List):
                        continue
                    modules = [
                        elt.value
                        for elt in kw.value.elts
                        if isinstance(elt, ast.Constant)
                        and isinstance(elt.value, str)
                    ]
                    if modules:
                        result.setdefault(entry, []).extend(modules)
    return result


# -------------------------------------------------------------------------
#
# RequiresModPurityTest
#
# -------------------------------------------------------------------------
class RequiresModPurityTest(unittest.TestCase):
    """Ensure requires_mod entries do not reference compiled extension packages."""

    def test_no_compiled_extensions(self):
        """
        Every installed requires_mod module must be pure Python.

        Compiled extensions (.so / .pyd) will fail to load inside a
        bundled Gramps app if their native library dependencies are not
        present in the bundle.  Only pure-Python packages are safe.
        """
        failures = []
        skipped = []
        for addon, modules in _collect_requires_mod().items():
            for module in modules:
                compiled = _is_compiled_module(module)
                if compiled is None:
                    skipped.append(f"{addon}: {module} (not installed, skipped)")
                elif compiled:
                    failures.append(
                        f"{addon}: '{module}' contains compiled extensions"
                        " and will not work in bundled Gramps builds"
                    )

        if skipped:
            print(
                "\nSkipped (not installed):\n"
                + "\n".join(f"  {s}" for s in skipped)
            )

        if failures:
            self.fail(
                "The following requires_mod entries contain compiled extensions.\n"
                "Only pure-Python packages are safe in bundled Gramps (Mac .app"
                " / Windows AIO).\n"
                "Consider removing the dependency, replacing it with a pure-Python"
                " alternative, or documenting that this addon does not support"
                " bundled builds.\n\n"
                + "\n".join(f"  {f}" for f in failures)
            )


# -------------------------------------------------------------------------
#
# main
#
# -------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main()
