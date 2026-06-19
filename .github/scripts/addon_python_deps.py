#!/usr/bin/env python3
"""Single source of truth for addon *Python* dependencies (``requires_mod``).

Sibling to ``addon_system_deps.py`` (which covers the *system* deps —
``requires_gi`` typelibs and ``requires_exe`` executables). This module covers
the third dependency kind a Gramps addon declares in its ``.gpr.py``:

* ``requires_mod`` — importable Python module names (e.g. ``["psycopg2"]``,
  ``["life_line_chart", "svgwrite"]``). pip-installable.

ci.yml previously inlined an *identical* ``requires_mod`` derivation heredoc in
three jobs (``unit-test-linux``, ``unit-test-windows``, ``integration-test``)
to build the install union, plus a near-identical ``find_spec`` validator
heredoc in each. That copy-paste is the drift this module removes: the
``.gpr.py`` files stay the single source of truth and every job derives the
list from one place. A one-line change is now a one-site edit.

Self-contained on purpose: pure stdlib, no Gramps import and no third-party
import, so it runs at image-build time before Gramps is installed and on the
bare Windows conda runner. It does NOT depend on any external project.

Scanning mirrors ``addon_system_deps.py`` deliberately: a regex finds each
``requires_mod = [...]`` assignment and ``ast.literal_eval`` parses the
bracketed list (no executing the ``.gpr.py``). Every real ``requires_mod`` in
addons-source is a flat list of string literals, so a literal-eval parse covers
them all; a non-literal or unreadable declaration is skipped tolerantly (with a
note to stderr) rather than aborting the batch — mirroring the old inline
behaviour.

``requires_mod`` is the *importable module* name Gramps verifies at runtime via
``importlib.util.find_spec`` (``gramps/gen/utils/requirements.py``
``Requirements.check_mod``). ``pip install`` wants the *distribution* name,
which differs for a few packages, so the install union maps the known
import→distribution cases (``PIL`` → ``Pillow``) via
``_IMPORT_TO_DISTRIBUTION``. The map is INSTALL-ONLY: ``--check-resolves``
validates the *raw* declared import name, exactly as Gramps does, so an addon
that declares the PyPI distribution name by mistake (``requires_mod=["Pillow"]``
when the import name is ``"PIL"``) is still caught.

CLI::

    addon_python_deps.py --install-list ROOT     # space-separated sorted union
    addon_python_deps.py --check-resolves ROOT   # fail if a declared import name
                                                 # pip-installs but does not import
"""

from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import sys

# Matches a single-line ``requires_mod = ["a", "b"]`` assignment — the same
# shape addon_system_deps.py's _GI_RE/_EXE_RE assume, and the only shape that
# occurs in addons-source.
_MOD_RE = re.compile(r"requires_mod\s*=\s*(\[[^\]]*\])")

# ``requires_mod`` holds the *importable module* name (declare "PIL", the import
# name, NOT "Pillow", the PyPI distribution — Gramps verifies it with
# ``importlib.util.find_spec``). But ``pip install`` wants the *distribution*
# name, which differs for some packages, so installing the raw import name fails
# (``pip install PIL`` → no such distribution; the package is ``Pillow``). Map
# the known import→distribution cases so the derived install list resolves on
# PyPI. Addons stay correct (import name); only the install side translates.
#
# Kept in step with Gramps' own install-time table, ``_IMPORT_TO_PYPI`` in
# ``gramps/gen/utils/pypi.py`` (gramps PR #2308) — the authority Gramps will use
# to install ``requires_mod`` deps in frozen/Flatpak/pip-less environments. The
# entries below mirror that table so an addon declaring any of these import names
# installs the same distribution in CI as Gramps does at runtime. Once #2308
# merges, single-source this from that module rather than hand-mirroring it.
_IMPORT_TO_DISTRIBUTION = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "dateutil": "python-dateutil",
    "bs4": "beautifulsoup4",
    "serial": "pyserial",
    "usb": "pyusb",
    "nacl": "PyNaCl",
    "Crypto": "pycryptodome",
    "OpenSSL": "pyOpenSSL",
    "wx": "wxPython",
}


def _gpr_files(root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(root, "*", "*.gpr.py")))


def _declared_mods(text: str, path: str) -> list[str]:
    """The *raw* (un-mapped) ``requires_mod`` import names declared in one
    ``.gpr.py`` body. Tolerant: a non-literal value is skipped with a note to
    stderr, mirroring the old inline behaviour."""
    out: list[str] = []
    for m in _MOD_RE.finditer(text):
        try:
            value = ast.literal_eval(m.group(1))
        except (ValueError, SyntaxError):
            print(
                f"addon_python_deps: skipping non-literal requires_mod "
                f"in {path}: {m.group(1)!r}",
                file=sys.stderr,
            )
            continue
        for mod in value:
            if mod:
                out.append(mod)
    return out


def declared_mods(root: str) -> set[str]:
    """The sorted-by-caller set of *raw* ``requires_mod`` import names declared
    across every addon's ``.gpr.py`` under *root* — the names Gramps verifies
    via ``find_spec`` (NOT the install-mapped distribution names). Unreadable
    files are skipped with a note to stderr."""
    names: set[str] = set()
    for path in _gpr_files(root):
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print(
                f"addon_python_deps: skipping unreadable {path}: {exc}",
                file=sys.stderr,
            )
            continue
        names.update(_declared_mods(text, path))
    return names


def install_list(root: str) -> list[str]:
    """Return the sorted union of ``requires_mod`` across every addon's
    ``.gpr.py`` under *root*, mapped to pip *distribution* names. This is the
    list the ci.yml "Install addon runtime deps" steps pip-install. Best-effort
    and tolerant — a file that cannot be read, or a non-literal value, is
    skipped (not fatal), so the step installs what it can resolve."""
    return sorted(_IMPORT_TO_DISTRIBUTION.get(mod, mod) for mod in declared_mods(root))


def check_resolves(root: str) -> int:
    """Validate that every declared ``requires_mod`` import name which actually
    pip-installed also resolves under ``importlib.util.find_spec`` — the same
    check Gramps' ``Requirements.check_mod`` performs at runtime. The *raw*
    declared name is checked (NOT the install-mapped distribution name), because
    that is what Gramps imports.

    Run this *after* the install union has been pip-installed: a name that pip
    never installed (an exotic system-dep / image gap, not a PR bug) is skipped;
    a name that pip-installed yet still fails ``find_spec`` is a wrong
    declaration (e.g. the PyPI distribution ``"Pillow"`` instead of the import
    name ``"PIL"``) and fails the gate. Returns 1 if any bad name, else 0.
    Preserves the behaviour of the old inline validator heredoc verbatim."""
    import subprocess
    from importlib.util import find_spec

    bad: list[str] = []
    for name in sorted(declared_mods(root)):
        installed = (
            subprocess.run(
                [sys.executable, "-m", "pip", "show", name],
                capture_output=True,
            ).returncode
            == 0
        )
        if not installed:
            print(f"~  {name} (pip-install failed earlier, skipping)")
            continue
        if find_spec(name) is None:
            bad.append(name)
            print(f"x  {name} (pip-installed but find_spec returned None)")
        else:
            print(f"ok {name}")

    if bad:
        print()
        print(f"::error::Wrong requires_mod names: {bad}")
        print("These pip-install but are not importable. requires_mod is")
        print("consumed by gramps' check_mod() via find_spec(), so the")
        print("importable module name is required (e.g. 'PIL', not 'Pillow').")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--install-list",
        metavar="ROOT",
        help="print the sorted, pip-installable union of requires_mod across "
        "ROOT/*/*.gpr.py (import names mapped to distribution names)",
    )
    group.add_argument(
        "--check-resolves",
        metavar="ROOT",
        help="verify every declared requires_mod import name that pip-installed "
        "also resolves under importlib.util.find_spec (Gramps' check_mod); "
        "exit 1 if any installs but does not import",
    )
    args = parser.parse_args(argv)

    if args.install_list is not None:
        print(" ".join(install_list(args.install_list)))
        return 0
    return check_resolves(args.check_resolves)


if __name__ == "__main__":
    sys.exit(main())
