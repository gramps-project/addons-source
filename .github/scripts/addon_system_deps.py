#!/usr/bin/env python3
"""Single source of truth for addon *system* dependencies in CI.

Addons declare three dependency kinds in their ``.gpr.py``:

* ``requires_mod`` — importable Python modules. pip-installable; ci.yml
  auto-derives these from the ``.gpr.py`` files. Most ship a plain wheel and need
  nothing more, but a few have no wheel on a CI platform and build from / link
  against a system library — ``pygraphviz`` (graphviz), ``psycopg2`` / ``psycopg``
  (libpq). Those need a system package before the pip step can satisfy them,
  mapped in ``MOD_BUILD_PACKAGES`` below.
* ``requires_gi`` — GObject-introspection typelibs (e.g. ``GooCanvas``).
* ``requires_exe`` — system executables (e.g. ``dot`` from graphviz).

All three system kinds above (the GI typelibs, the executables, and the
source-built ``requires_mod`` system packages) are not pip-installable as named,
are named differently per platform, and Gramps' own ``Requirements`` only
*checks* ``requires_mod`` (never installs its system side). This module maps each
declared ``requires_gi`` namespace / ``requires_exe`` name / source-built
``requires_mod`` to its package on each CI platform and scans the addons for what
they declare, so ci.yml derives the install list from one place instead of a
hand-kept list.

Platform availability is asymmetric and encoded here: the GTK 3 addon libs
(goocanvas, osm-gps-map, gexiv2) exist on Debian/apt but **not on conda-forge**,
so the conda (Windows) lane cannot install them — addons needing them skip there
by necessity. A ``conda`` value of ``None`` records that.

Pure stdlib so it runs anywhere in CI without bootstrapping.

CLI::

    addon_system_deps.py --platform apt          # space-separated install list
    addon_system_deps.py --platform conda        #   (only packages available there)
    addon_system_deps.py --unmapped .            # declared GI/exe/mod with no map entry; exit 1 if any
"""

# ------------------------
# Python modules
# ------------------------
from __future__ import annotations

import argparse
import ast
import glob
import os
import re
import sys

# ---------------------------------------------------------------------------
# The map. Keys are what addons declare; values give the package per platform.
# A None value means "no package provides this on that platform" (so it is not
# installed there and an addon needing it is expected to skip).
# ---------------------------------------------------------------------------

# requires_gi namespace -> package providing the typelib, per platform.
GI_PACKAGES: dict[str, dict[str, str | None]] = {
    "GExiv2": {"apt": "gir1.2-gexiv2-0.10", "conda": None},
    "GooCanvas": {"apt": "gir1.2-goocanvas-2.0", "conda": None},
    "OsmGpsMap": {"apt": "gir1.2-osmgpsmap-1.0", "conda": None},
    # PlaceCoordinateGramplet declares GeocodeGlib 1.0, but modern distros ship
    # only the 2.0 typelib and conda-forge ships none; the addon has no tests.
    # Recorded so the drift-guard recognises the namespace; not installed.
    "GeocodeGlib": {"apt": None, "conda": None},
}

# requires_exe executable -> package providing it, per platform.
EXE_PACKAGES: dict[str, dict[str, str | None]] = {
    "dot": {"apt": "graphviz", "conda": "graphviz"},
}

# Source-built / system-library requires_mod -> the package that makes the
# module installable+importable, per platform. A requires_mod belongs here ONLY
# when a plain ``pip install <mod>`` cannot satisfy it by itself on a CI platform:
#   * apt — no wheel, so pip compiles the C extension from source against a -dev
#     header (``pygraphviz`` -> libgraphviz-dev; ``psycopg2`` -> libpq-dev), or the
#     pure-Python build links a system shared library at import time (``psycopg`` /
#     psycopg3 -> libpq, provided by libpq-dev). The generic compiler toolchain
#     (gcc, python3-dev, pkg-config) those source builds need stays in the CI
#     image (.github/docker/gramps-ci/Dockerfile no longer purges it).
#   * conda — conda-forge ships the whole binding prebuilt, so the value is the
#     module's own conda-forge package; the conda lane ``mamba install``s it and
#     the later pip step finds it already satisfied. Verified present on
#     conda-forge win-64: pygraphviz, psycopg2, psycopg.
# Both platforms must PROVISION the dep or fail the install step honestly — a
# value the platform cannot resolve aborts the job (apt-get install / mamba
# install) rather than letting ci.yml's "|| echo … (continuing)" swallow a failed
# build into a silently-degraded green. A genuinely unprovisionable module would
# be a None, but pygraphviz/psycopg2/psycopg are available on both apt and
# conda-forge.
MOD_BUILD_PACKAGES: dict[str, dict[str, str | None]] = {
    "pygraphviz": {"apt": "libgraphviz-dev", "conda": "pygraphviz"},
    "psycopg2": {"apt": "libpq-dev", "conda": "psycopg2"},
    "psycopg": {"apt": "libpq-dev", "conda": "psycopg"},  # psycopg3
}

# requires_mod that ship a plain pip wheel needing no system package on any CI
# platform. Listed explicitly so the drift guard can tell a wheel-only module
# (nothing to map) from a source-built one that was forgotten: every declared
# requires_mod must be classified as exactly one of WHEEL_ONLY_MODS or
# MOD_BUILD_PACKAGES, else a newly-added source-built dep could silently lose
# coverage again (the build-toolchain gap this module closes). ``--unmapped``
# fails CI on any requires_mod that is in neither set.
WHEEL_ONLY_MODS: frozenset[str] = frozenset(
    {
        "PIL",  # EditExifMetadata — Pillow ships binary wheels on every CI
        # platform; declared by import name, addon_python_deps maps
        # PIL→Pillow on the install side
        "boto3",  # S3MediaUploader — pure-Python AWS SDK wheel
        "dbf",  # TMGimporter — pure-Python wheel
        "life_line_chart",  # LifeLineChartView — pure-Python wheel
        "litellm",  # ChatWithTree / GrampsChat — pure-Python wheel
        "networkx",  # NetworkChart — pure-Python wheel
        "pymongo",  # MongoDB — ships binary wheels on every CI platform
        "svgwrite",  # LifeLineChartView — pure-Python wheel
    }
)

PLATFORMS = ("apt", "conda")


# ------------------------------------------------------------
#
# scanning
#
# ------------------------------------------------------------
_GI_RE = re.compile(r"requires_gi\s*=\s*(\[[^\]]*\])")
_EXE_RE = re.compile(r"requires_exe\s*=\s*(\[[^\]]*\])")
_MOD_RE = re.compile(r"requires_mod\s*=\s*(\[[^\]]*\])")


def _gpr_files(root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(root, "*", "*.gpr.py")))


def _literal(src: str):
    try:
        return ast.literal_eval(src)
    except (ValueError, SyntaxError):
        return []


def _scan(root: str, pattern: re.Pattern, first_of_tuple: bool) -> set[str]:
    found: set[str] = set()
    for path in _gpr_files(root):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for match in pattern.finditer(text):
            for entry in _literal(match.group(1)):
                if first_of_tuple and isinstance(entry, (tuple, list)):
                    entry = entry[0] if entry else None
                if not entry:
                    continue
                if not isinstance(entry, str):
                    # A non-str entry (e.g. requires_mod=[("psycopg2", ">=2")],
                    # or a nested list) would be unhashable for .add() or crash a
                    # later sorted()/lookup — skip it tolerantly with a note.
                    print(
                        f"addon_system_deps: skipping non-string requires_* "
                        f"entry in {path}: {entry!r}",
                        file=sys.stderr,
                    )
                    continue
                found.add(entry)
    return found


def scan_gi_namespaces(root: str) -> set[str]:
    return _scan(root, _GI_RE, first_of_tuple=True)


def scan_executables(root: str) -> set[str]:
    return _scan(root, _EXE_RE, first_of_tuple=False)


def scan_modules(root: str) -> set[str]:
    return _scan(root, _MOD_RE, first_of_tuple=False)


def addon_requirements(addon_dir: str) -> tuple[set[str], set[str]]:
    """Return (gi_namespaces, executables) declared by a single addon dir."""
    gi: set[str] = set()
    exe: set[str] = set()
    for path in sorted(glob.glob(os.path.join(addon_dir, "*.gpr.py"))):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for match in _GI_RE.finditer(text):
            for entry in _literal(match.group(1)):
                ns = entry[0] if isinstance(entry, (tuple, list)) else entry
                if isinstance(ns, str) and ns:
                    gi.add(ns)
        for match in _EXE_RE.finditer(text):
            for entry in _literal(match.group(1)):
                if isinstance(entry, str) and entry:
                    exe.add(entry)
    return gi, exe


# ------------------------------------------------------------
#
# derivation
#
# ------------------------------------------------------------
def packages(platform: str) -> list[str]:
    """All install-by-name packages available for a platform (full mapped set)."""
    pkgs: list[str] = []
    for table in (GI_PACKAGES, EXE_PACKAGES, MOD_BUILD_PACKAGES):
        for entry in table.values():
            pkg = entry.get(platform)
            if pkg:
                pkgs.append(pkg)
    return sorted(set(pkgs))


def unmapped(root: str) -> tuple[set[str], set[str], set[str]]:
    """Declared deps with no entry in the maps at all (drift).

    The third element is every declared ``requires_mod`` classified as *neither*
    a wheel-only module nor a source-built one — an unclassified module that, if
    it turns out to need a system package, would silently lose coverage. CI fails
    on it so a human must classify it (add to ``WHEEL_ONLY_MODS`` or
    ``MOD_BUILD_PACKAGES``).
    """
    return (
        scan_gi_namespaces(root) - set(GI_PACKAGES),
        scan_executables(root) - set(EXE_PACKAGES),
        scan_modules(root) - WHEEL_ONLY_MODS - set(MOD_BUILD_PACKAGES),
    )


def addon_satisfiable_on(addon_dir: str, platform: str) -> bool:
    """
    True if every system dep the addon declares has a package on this platform.

    Used by the test runner to tell an *expected* platform skip (a declared dep
    that simply is not packaged here, e.g. goocanvas on conda) from a suspicious
    all-skip that should fail.
    """
    gi, exe = addon_requirements(addon_dir)
    for ns in gi:
        entry = GI_PACKAGES.get(ns)
        if entry is None or entry.get(platform) is None:
            return False
    for name in exe:
        entry = EXE_PACKAGES.get(name)
        if entry is None or entry.get(platform) is None:
            return False
    return True


# ------------------------------------------------------------
#
# CLI
#
# ------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=PLATFORMS)
    parser.add_argument(
        "--unmapped",
        metavar="ROOT",
        help="print declared GI/exe/mod deps with no map entry; exit 1 if any",
    )
    args = parser.parse_args(argv)

    if args.unmapped is not None:
        gi, exe, mod = unmapped(args.unmapped)
        for ns in sorted(gi):
            print(f"gi:{ns}")
        for name in sorted(exe):
            print(f"exe:{name}")
        for name in sorted(mod):
            print(f"mod:{name}")
        return 1 if (gi or exe or mod) else 0

    if args.platform:
        print(" ".join(packages(args.platform)))
        return 0

    parser.error("nothing to do: pass --platform or --unmapped")
    return 2


if __name__ == "__main__":
    sys.exit(main())
