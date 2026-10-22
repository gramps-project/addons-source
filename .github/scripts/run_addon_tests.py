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
   reported as a FAILURE, so the job stays bounded and names the culprit. The
   worker runs in its own process group (POSIX) so the timeout reaps any
   children it spawned, not just the worker — otherwise a hung grandchild
   holding the stdout pipe defeats the timeout.

3. **Honest skip accounting.** unittest exits 0 when every test SKIPS, and also
   when a module collects ZERO tests — both read as a pass. This runner FAILS a
   wholly-skipped or zero-test module, UNLESS the addon's declared system deps
   are unavailable on this platform (e.g. goocanvas/osm-gps-map are not on
   conda-forge), in which case the skip is expected and tolerated (the map
   lives in ``addon_system_deps.py``). A module that fails to LOAD is excused as
   a platform skip only when the failure is dependency-shaped (ImportError, or
   gi's absent-typelib ValueError); a SyntaxError or a bug in the addon's own
   import-time code is a real defect and always FAILS, on every platform. A
   module that raises ``SkipTest`` at import is opting out explicitly and is
   always honoured as a skip.

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
import importlib
import os
import re
import signal
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addon_system_deps as deps  # noqa: E402


def _module_timeout() -> int:
    """Per-module wall clock (seconds). Generous enough for a legitimate
    DB-backed suite, small enough that a hung test is caught promptly instead of
    running to the job cap. Overridable via ``RUN_ADDON_TESTS_TIMEOUT``; a
    non-integer value is ignored with a note rather than crashing the runner."""
    raw = os.environ.get("RUN_ADDON_TESTS_TIMEOUT", "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            print(
                f"run_addon_tests: ignoring non-integer "
                f"RUN_ADDON_TESTS_TIMEOUT={raw!r}; using default 300",
                file=sys.stderr,
            )
    return 300


MODULE_TIMEOUT_S = _module_timeout()

# Markers the worker prints so the parent can read the outcome without needing
# xmlrunner (820's env has only stdlib unittest).
_OK = "__RESULT__ ok"
_LOADERROR = "__RESULT__ loaderror"


def _terminal_exc_name(text: str) -> str | None:
    """The exception class name on the last ``Type: message`` line of a
    traceback string (``ModuleNotFoundError``, ``SyntaxError``, ``SkipTest``…),
    or None. Scans from the end, so the first match is the terminal line."""
    for line in reversed(text.strip().splitlines()):
        m = re.match(r"^([A-Za-z_][\w.]*)\s*:", line.strip())
        if m:
            return m.group(1).rsplit(".", 1)[-1]
    return None


def _is_skip_request(exc: BaseException) -> bool:
    """Whether a module opted out at import time via ``raise SkipTest(...)``.

    A module-level SkipTest is an explicit, deliberate opt-out (the addon's own
    guard for "this needs a display / PyGObject / a backend I don't have"), so it
    is honoured as a skip on every platform — never a failure, and never
    dependent on the addon's declared system deps."""
    if isinstance(exc, unittest.SkipTest):
        return True
    # unittest's loader may wrap it (see _dep_shaped) — check the terminal type.
    return isinstance(exc, ImportError) and _terminal_exc_name(str(exc)) == "SkipTest"


def _dep_shaped(exc: BaseException) -> bool:
    """Whether a module load failure is a missing-dependency shape.

    Only these may be excused as an expected platform skip when the addon's
    declared deps are unavailable: a missing module (ImportError /
    ModuleNotFoundError), or the ``ValueError`` ``gi.require_version`` raises for
    an absent typelib (``Namespace X not available``). A SyntaxError or a bug in
    the addon's own import-time code is a real defect and must never be excused.

    Complication: ``unittest``'s loader wraps EVERY import-time exception —
    including SyntaxError — into an ``ImportError`` whose message embeds the
    original traceback (``Failed to import test module: …``). So for that
    wrapper we cannot go by type; inspect the terminal exception in the embedded
    traceback instead.
    """
    if isinstance(exc, ValueError):
        return "not available" in str(exc)
    if isinstance(exc, ImportError):
        msg = str(exc)
        if "Failed to import test module" in msg:
            terminal = _terminal_exc_name(msg)
            # Unknown terminal → treat as dep (tolerant: a missing dep is the
            # common case and we would rather skip than falsely fail).
            return terminal in (None, "ImportError", "ModuleNotFoundError")
        return True  # a bare ImportError (not the loader wrapper)
    return False


def _load_kind(exc: BaseException) -> str:
    """Classify a module load failure: skip | dep | other."""
    if _is_skip_request(exc):
        return "skip"
    return "dep" if _dep_shaped(exc) else "other"


def _load_failure_exception(suite: unittest.TestSuite):
    """The exception behind a deferred import failure, or None.

    ``loadTestsFromName`` wraps a module that fails to import in a
    ``unittest.loader._FailedTest`` placeholder carrying the original exception
    in ``_exception``. Walk the suite for one and return that exception, so the
    caller can classify the failure instead of running a placeholder that errors
    anonymously. Private-API tolerant: if the internals ever change, return None
    and let the suite run (the pre-taxonomy behaviour)."""
    try:
        from unittest.loader import _FailedTest
    except Exception:
        return None

    def _walk(test):
        if isinstance(test, unittest.TestSuite):
            for child in test:
                found = _walk(child)
                if found is not None:
                    return found
            return None
        if isinstance(test, _FailedTest):
            return getattr(test, "_exception", None) or ImportError(
                "module failed to load"
            )
        return None

    return _walk(suite)


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
    # Resolve the addon PACKAGE (its directory, from the repo root) before the
    # addon dir joins sys.path. Many addons ship a top-level module named after
    # the addon itself (<Addon>/<Addon>.py); the moment <Addon>/ is on sys.path
    # that regular module wins the bare name <Addon> over the namespace package,
    # and the dotted test name <Addon>.tests.test_x then dies with "module
    # '<Addon>' has no attribute 'tests'". Importing the package first pins it in
    # sys.modules so the dotted load resolves, while the addon dir added below
    # still serves the tests' bare sibling imports (e.g. `from models import …`).
    try:
        importlib.import_module(addon)
    except Exception:
        # Not importable as a package (single-file addon, or its __init__ needs
        # deps): leave it; the dotted load below reports the real failure.
        pass
    if addon_dir not in sys.path:
        sys.path.append(addon_dir)
    # Load via unittest (NOT a bare import_module probe): an addon whose
    # top-level module shares the addon's directory name (e.g.
    # CalculateEstimatedDates/CalculateEstimatedDates.py) is shadowed by
    # addon_dir being on sys.path, which breaks a dotted import_module but not
    # unittest's own resolution. A load failure surfaces two ways depending on
    # the Python version and error kind — loadTestsFromName may RAISE it, or
    # defer it into a _FailedTest placeholder that errors only when run (so the
    # parent would otherwise see an anonymous `broke=1` with the shape lost).
    # Handle both, and classify the real exception (dependency-shaped vs a code
    # bug) either way.
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(modname)
    except Exception as exc:  # raised import-time failure
        kind = _load_kind(exc)
        print(f"{_LOADERROR} kind={kind} {exc!r}", flush=True)
        return 0
    load_exc = _load_failure_exception(suite)  # deferred (_FailedTest) failure
    if load_exc is not None:
        kind = _load_kind(load_exc)
        print(f"{_LOADERROR} kind={kind} {load_exc!r}", flush=True)
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
        [
            sys.executable,
            os.path.abspath(__file__),
            "--worker",
            modname,
            "--root",
            root,
        ],
        stdout=subprocess.PIPE,
        stderr=None,  # stream the test output straight to the CI log
        text=True,
        # Own process group so a timeout can reap the worker AND any children it
        # spawned. Without this, proc.kill() kills only the worker and the
        # follow-up communicate() blocks until a grandchild that inherited the
        # stdout pipe exits — a hung grandchild defeats the timeout entirely.
        start_new_session=(os.name == "posix"),  # setsid; raises on Windows
    )
    try:
        # communicate() enforces the wall clock and reaps the process.
        stdout, _ = proc.communicate(timeout=MODULE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # group id == worker pid
            except (ProcessLookupError, PermissionError):
                proc.kill()
        else:
            proc.kill()
        try:
            # Bounded: a surviving grandchild holding the stdout pipe must not
            # hang the run a second time.
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return True, f"  FAIL  {modname} — timed out after {MODULE_TIMEOUT_S}s (hung)"

    out_lines = stdout.splitlines()
    for line in out_lines:  # echo the worker's result marker into the log
        print(line)

    result_line = next(
        (ln for ln in reversed(out_lines) if ln.startswith("__RESULT__")), ""
    )

    if result_line.startswith(_LOADERROR):
        kind_m = re.search(r"\bkind=(\w+)", result_line)
        kind = kind_m.group(1) if kind_m else ""
        if kind == "skip":
            # The module raised SkipTest at import: an explicit opt-out, honoured
            # on every platform regardless of declared-dep satisfiability.
            return False, f"  skip  {modname} — module opted out (SkipTest at import)"
        dep_shaped = kind == "dep"
        if not dep_shaped:
            # A non-dependency load failure (SyntaxError, a bug in the addon's
            # import-time code) is a real defect on every platform — never
            # excusable as a "deps unavailable here" skip.
            return True, (
                f"  FAIL  {modname} — load error (not dependency-shaped; "
                "a code bug, not a platform skip)"
            )
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
    if ran == 0 and skipped == 0:
        # The module loaded but collected NOTHING (a class not subclassing
        # TestCase, a mistyped method name, a refactor that broke collection).
        # unittest exits 0 on this, so it would read as green — fail it. Note
        # the skipped==0 guard: a class-level skip (setUpClass raising SkipTest)
        # reports tests=0 with skips recorded, and that is a skipped module, not
        # an empty one — it falls through to the all-skipped rule below.
        return True, (
            f"  FAIL  {modname} — module loaded but collected zero tests "
            "(empty or misnamed test module reads as green)"
        )
    if skipped >= ran:
        # Everything skipped — including the ran==0/skipped>0 class-level case.
        total = max(ran, skipped)
        if satisfiable:
            return True, (
                f"  FAIL  {modname} — all {total} test(s) skipped "
                f"(degraded coverage; deps ARE available on {platform})"
            )
        return False, (
            f"  skip  {modname} — all {total} skipped, expected "
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
