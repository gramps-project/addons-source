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

``requires_mod`` is the *importable module* name Gramps verifies at runtime
(``gramps/gen/utils/requirements.py`` ``Requirements.check_mod`` — bare
``find_spec`` on gramps 6.0; ``find_spec`` plus a real import on 6.1+, gramps
PR #2308). ``pip install`` wants the *distribution* name, which differs for a
few packages, so the install union maps the known import→distribution cases
(``PIL`` → ``Pillow``) — single-sourced from Gramps' own ``_IMPORT_TO_PYPI``
table when the installed gramps ships one (6.1+), with the local
``_IMPORT_TO_DISTRIBUTION`` mirror as fallback. The map is INSTALL-ONLY:
``--check-resolves`` validates the *raw* declared import name, exactly as
Gramps does, so an addon that declares the PyPI distribution name by mistake
(``requires_mod=["Pillow"]`` when the import name is ``"PIL"``) is still
caught.

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
from collections.abc import Callable

# Sibling module in the same directory: the wheel-only vs source-built
# classification of every declared requires_mod. Running this file by path
# already puts its dir on sys.path[0]; the insert also covers being imported
# (the tests, and any embedding). Pure stdlib either way — no gramps import.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from addon_system_deps import WHEEL_ONLY_MODS  # noqa: E402

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
# FALLBACK MIRROR of Gramps' own install-time table, ``_IMPORT_TO_PYPI`` in
# ``gramps/gen/utils/pypi.py`` (gramps PR #2308, merged into gramps 6.1 as
# 7f94428b13; not on 6.0) — the authority Gramps uses to install
# ``requires_mod`` deps in frozen/Flatpak/pip-less environments. At lookup time
# ``_distribution_map()`` prefers that table from the installed gramps, so on
# 6.1+ lanes new upstream entries take effect without touching this file; this
# mirror serves lanes where gramps is absent or predates 6.1 (the gramps60
# image, the conda-forge 6.0.x Windows lane, bare runners). The sync-guard test
# ``tests/test_addon_python_deps.py::GrampsTableSync`` pins mirror == authority
# wherever the authority is importable.
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


def _distribution_map() -> dict[str, str]:
    """The import→distribution table, preferring the authority over the mirror.

    The installed Gramps (6.1+) ships the authoritative table,
    ``_IMPORT_TO_PYPI`` in ``gramps/gen/utils/pypi.py``; read it so CI installs
    exactly the distribution Gramps' own installer would. Fall back to the
    local ``_IMPORT_TO_DISTRIBUTION`` mirror when gramps is absent (image
    build, bare runner) or predates 6.1. The table dict is read directly rather
    than calling ``resolve_pypi_name()``: same data, but without one
    ``LOG.warning`` per translated name in every CI step — and that warning
    advises declaring the PyPI name, the opposite of the import-name contract
    ``--check-resolves`` enforces.

    A half-installed gramps can raise ``SystemExit`` at import (ResourcePath
    aborts when its resources are missing), so the guard is broader than
    ``ImportError``.
    """
    try:
        from gramps.gen.utils import pypi as _gramps_pypi
    except (Exception, SystemExit):
        return _IMPORT_TO_DISTRIBUTION
    table = getattr(_gramps_pypi, "_IMPORT_TO_PYPI", None)
    return dict(table) if table else _IMPORT_TO_DISTRIBUTION


def _module_checker() -> tuple[str, Callable[[str], bool]]:
    """A ``(label, check)`` pair implementing Gramps' requires_mod gate.

    Delegates to the installed gramps' ``Requirements().check_mod`` so the
    gate matches whichever series this lane ships: bare ``find_spec`` on 6.0,
    ``find_spec`` plus a real import on 6.1+ (gramps PR #2308). The stdlib
    ``find_spec`` fallback only applies where gramps is not importable (a dev
    box, never a CI lane) and deliberately stays find_spec-only: the gate
    exists to catch *declaration* bugs, and really importing every declared
    mod on an arbitrary machine is slow and side-effectful.
    """
    try:
        from gramps.gen.utils.requirements import Requirements
    except (Exception, SystemExit):
        from importlib.util import find_spec

        return (
            "stdlib find_spec (gramps not importable)",
            lambda name: find_spec(name) is not None,
        )
    return "gramps Requirements().check_mod", Requirements().check_mod


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
    table = _distribution_map()
    return sorted(table.get(mod, mod) for mod in declared_mods(root))


def check_resolves(root: str) -> int:
    """Validate that every declared ``requires_mod`` import name which actually
    pip-installed also passes Gramps' own dependency gate,
    ``Requirements().check_mod`` — bare ``find_spec`` on gramps 6.0,
    ``find_spec`` plus a real import on 6.1+ (gramps PR #2308) — so the gate
    matches whichever series this lane ships. The *raw* declared name is
    checked (NOT the install-mapped distribution name), because that is what
    Gramps imports; installed-ness however is probed with the *mapped*
    distribution name, because that is the only name pip knows (``pip show
    PIL`` fails even with Pillow installed).

    Run this *after* the install union has been pip-installed. A name whose
    distribution pip never installed is judged by its category: a **wheel-only**
    module (``WHEEL_ONLY_MODS``) ships a pure/binary wheel that installs on
    every CI platform, so a miss is a real provisioning regression and FAILS
    the gate; a **source-built** module (``MOD_BUILD_PACKAGES``, e.g. pygraphviz
    / psycopg2) can legitimately miss on an image/system gap and stays an
    advisory skip. A name that pip-installed yet still fails the gate is a wrong
    declaration (e.g. the PyPI distribution ``"Pillow"`` instead of the import
    name ``"PIL"``) — or, on 6.1+, a module that installs but cannot import —
    and fails the run. Returns 1 if any bad or missing-wheel name, else 0."""
    import subprocess

    label, check = _module_checker()
    print(f"dep gate: {label}")
    table = _distribution_map()
    bad: list[str] = []
    missing_wheels: list[str] = []
    for name in sorted(declared_mods(root)):
        dist = table.get(name, name)
        installed = (
            subprocess.run(
                [sys.executable, "-m", "pip", "show", dist],
                capture_output=True,
            ).returncode
            == 0
        )
        if not installed:
            if name in WHEEL_ONLY_MODS:
                missing_wheels.append(name)
                print(f"x  {name} (wheel-only, but pip never installed {dist})")
            else:
                print(
                    f"~  {name} (pip never installed {dist}, skipping — "
                    "source-built/system-dep)"
                )
            continue
        if not check(name):
            bad.append(name)
            print(f"x  {name} (installed as {dist} but fails Gramps' dep gate)")
        else:
            print(f"ok {name}")

    if bad:
        print()
        print(f"::error::Wrong requires_mod names: {bad}")
        print("These pip-install but are not importable. requires_mod is")
        print("consumed by gramps' check_mod() — find_spec, plus a real import")
        print("on gramps 6.1+ — so the importable module name is required")
        print("(e.g. 'PIL', not 'Pillow').")
    if missing_wheels:
        print()
        print(f"::error::Wheel-only requires_mod never pip-installed: {missing_wheels}")
        print("These declare a pure/binary wheel that installs on every CI")
        print("platform, so a failed install is a provisioning regression, not")
        print("an environment gap — investigate the install step's output above.")
    return 1 if (bad or missing_wheels) else 0


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
        "also passes Gramps' dep gate (Requirements().check_mod when gramps is "
        "importable, stdlib find_spec otherwise); exit 1 if any installs but "
        "does not import",
    )
    args = parser.parse_args(argv)

    if args.install_list is not None:
        print(" ".join(install_list(args.install_list)))
        return 0
    return check_resolves(args.check_resolves)


if __name__ == "__main__":
    sys.exit(main())
