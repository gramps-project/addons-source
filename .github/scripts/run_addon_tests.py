#!/usr/bin/env python3
"""Run per-addon unit tests with a GI bootstrap, a timeout, and honest skips.

Replaces a bare ``python -m unittest <modules>`` in CI. It does three things
plain unittest does not:

1. **GI version bootstrap.** Before any test imports a ``gramps.gui`` module, it
   calls ``gi.require_version`` for Pango/PangoCairo/Gtk — the set the Gramps
   GUI launcher (``gramps/gui/grampsgui.py``) pins at startup. A direct test
   import never runs that launcher, so without this the first
   ``from gi.repository import Gtk`` (in gramps core) warns and risks the wrong
   GTK on a host where GTK 4 is the default.

2. **A per-module timeout.** Each module runs in its own subprocess with a wall
   clock. A test that hangs (e.g. a DB import that blocks on a platform) would
   otherwise hang the whole CI job indefinitely — neither plain unittest nor
   xmlrunner has a timeout. A module that exceeds the limit is killed and
   reported as a FAILURE, so the job stays bounded and names the culprit.

3. **Honest skip accounting.** unittest exits 0 when every test SKIPS, so a
   wholly-skipped module reads as a pass. This runner FAILS such a module —
   UNLESS the addon's declared system deps are unavailable on this platform
   (e.g. goocanvas/osm-gps-map are not on conda-forge), in which case the skip
   is expected and tolerated (the map lives in ``addon_system_deps.py``).

Usage::

    run_addon_tests.py --platform apt   Addon.tests.test_x  Other.tests.test_y
    run_addon_tests.py --platform conda Addon.tests.test_x

Exit code is non-zero if any module is a hard failure (test failure/error,
timeout, or an unexpected all-skip on a platform where the addon's deps are
available).
"""

# ------------------------
# Python modules
# ------------------------
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addon_system_deps as deps  # noqa: E402

# Per-module wall clock. Generous enough for a legitimate DB-backed suite, small
# enough that a hung test is caught promptly instead of running to the job cap.
# Overridable via env for tuning/testing.
MODULE_TIMEOUT_S = int(os.environ.get("RUN_ADDON_TESTS_TIMEOUT", "300"))

# Markers the worker prints so the parent can read the outcome without needing
# xmlrunner (820's env has only stdlib unittest).
_OK = "__RESULT__ ok"
_LOADERROR = "__RESULT__ loaderror"


def _bootstrap_gi() -> None:
    """Pin the GI versions the Gramps GUI launcher pins, before tests import."""
    try:
        import gi
    except ImportError:
        return
    for namespace, version in (("Pango", "1.0"), ("PangoCairo", "1.0"), ("Gtk", "3.0")):
        try:
            gi.require_version(namespace, version)
        except (ValueError, AttributeError):
            pass


# ------------------------------------------------------------
#
# worker: runs ONE module in this (sub)process
#
# ------------------------------------------------------------
def _run_worker(modname: str, root: str = ".") -> int:
    """Run a single module; print a machine-readable result line; exit 0.

    The parent classifies pass/fail from the printed counts and its own platform
    knowledge, so the worker always exits 0 (a non-zero exit would be
    indistinguishable from an interpreter crash).
    """
    _bootstrap_gi()
    # Put the addon's own directory on sys.path, mirroring how Gramps' plugin
    # loader (gramps/gen/plug/_manager.py) inserts the addon dir before importing
    # a plugin. APPEND (not prepend) so the repo-root shared `tests` environment
    # still takes precedence: this lets a nested-package addon's top-level
    # imports (e.g. ``from name_processor… import``) resolve without shadowing
    # the shared Gramps-emulation test env. The module is still loaded by its
    # full dotted name from the repo root, so package-relative imports keep
    # working too.
    addon = modname.split(".", 1)[0]
    addon_dir = os.path.join(root, addon)
    if addon_dir not in sys.path:
        sys.path.append(addon_dir)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(modname)
    except Exception as exc:  # import-time failure
        print(f"{_LOADERROR} {exc!r}", flush=True)
        return 0
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    broke = len(result.failures) + len(result.errors)
    print(
        f"{_OK} tests={result.testsRun} skipped={len(result.skipped)} broke={broke}",
        flush=True,
    )
    return 0


# ------------------------------------------------------------
#
# parent: spawns a timed worker per module and classifies the outcome
#
# ------------------------------------------------------------
def _classify(modname: str, platform: str, root: str) -> tuple[bool, str]:
    """Run one module in a timed subprocess. Return (is_hard_failure, summary)."""
    addon = modname.split(".", 1)[0]
    satisfiable = deps.addon_satisfiable_on(os.path.join(root, addon), platform)

    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--worker", modname, "--root", root],
        stdout=subprocess.PIPE,
        stderr=None,  # stream the test output straight to the CI log
        text=True,
    )
    try:
        # communicate() enforces the wall clock and reaps the process.
        stdout, _ = proc.communicate(timeout=MODULE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return True, f"  FAIL  {modname} — timed out after {MODULE_TIMEOUT_S}s (hung)"

    out_lines = stdout.splitlines()
    for line in out_lines:  # echo the worker's result marker into the log
        print(line)

    result_line = next(
        (ln for ln in reversed(out_lines) if ln.startswith("__RESULT__")), ""
    )

    if result_line.startswith(_LOADERROR):
        if satisfiable:
            return True, f"  FAIL  {modname} — load error"
        return False, (
            f"  skip  {modname} — not loadable on {platform} "
            f"(addon system deps unavailable here)"
        )

    if not result_line.startswith(_OK):
        return True, f"  FAIL  {modname} — no result (worker crashed)"

    fields = dict(tok.split("=", 1) for tok in result_line.split()[2:] if "=" in tok)
    ran = int(fields.get("tests", 0))
    skipped = int(fields.get("skipped", 0))
    broke = int(fields.get("broke", 0))

    if broke:
        return True, f"  FAIL  {modname} — {broke} failed/errored"
    if ran > 0 and skipped == ran:
        if satisfiable:
            return True, (
                f"  FAIL  {modname} — all {ran} tests skipped "
                f"(degraded coverage; deps ARE available on {platform})"
            )
        return False, (
            f"  skip  {modname} — all {ran} skipped, expected "
            f"(addon system deps unavailable on {platform})"
        )
    if skipped:
        return False, f"  ok    {modname} — {ran} tests, {skipped} skipped"
    return False, f"  ok    {modname} — {ran} tests"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=deps.PLATFORMS)
    parser.add_argument(
        "--root",
        default=".",
        help="addons-source root holding the <Addon>/ dirs (default: cwd)",
    )
    parser.add_argument(
        "--worker",
        metavar="MODULE",
        help="internal: run this single module and print its result line",
    )
    parser.add_argument("modules", nargs="*", help="dotted test modules to run")
    args = parser.parse_args(argv)

    if args.worker:
        return _run_worker(args.worker, args.root)

    if not args.platform:
        parser.error("--platform is required in parent mode")
    if not args.modules:
        print("No per-addon unit test modules found")
        return 0

    hard_failures: list[str] = []
    summary: list[str] = []
    for modname in args.modules:
        failed, line = _classify(modname, args.platform, args.root)
        summary.append(line)
        if failed:
            hard_failures.append(modname)

    print("\n=== addon test summary ===")
    for line in summary:
        print(line)

    if hard_failures:
        print(f"\n{len(hard_failures)} module(s) failed: {hard_failures}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
