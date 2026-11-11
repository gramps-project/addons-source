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
Tests for the undeclared-``depends_on`` detector (Mantis 13707 class).

The detector *logic* lives in :mod:`tests.addon_dependencies` (an
import-light module, no ``gi`` / ``gramps.gui``); this file drives it:

* :class:`TestIsolatedLoadParallelism` proves the runtime fix (review
  finding R-F): :func:`run_isolated_loads` runs the per-module loads
  concurrently, not serially. It injects a sleeping stub loader so the
  speed-up is measured deterministically without spawning subprocesses.
* :class:`TestAddonDependencies` is the real full-tree scan. It is heavy
  (one isolated-load subprocess per registered module) and needs the
  Gramps runtime importable, so it runs only when the CI detector job
  sets ``RUN_ADDON_DEP_SCAN=1``; the default ``unittest`` run skips it.
"""

import logging
import os
import time
import unittest

from tests.addon_dependencies import (
    ADDONS_ROOT,
    LoadTask,
    build_load_tasks,
    run_isolated_loads,
    _index_addons,
)

LOG = logging.getLogger(__name__)

# Allow the speed-up assertions a generous margin: even on a loaded CI
# runner the parallel run must beat the serial wall-clock by a wide gap,
# while a truly serial implementation cannot.
_PARALLEL_TASKS = 8
_PER_LOAD_DELAY = 0.25  # seconds the stub loader sleeps per task


def _sleeping_loader(delay: float, rc: int = 0, err: str = ""):
    """Return a load_fn stub that sleeps ``delay`` then reports ``(rc, err)``."""

    def _load(target_dir, dep_dirs, module, timeout=30):
        time.sleep(delay)
        return rc, err

    return _load


class TestIsolatedLoadParallelism(unittest.TestCase):
    """The isolated loads run concurrently, not serially (finding R-F)."""

    @staticmethod
    def _tasks(n):
        return [
            LoadTask(
                pid=f"p{i}",
                module=f"m{i}",
                target_dir="/nonexistent",
                dep_dirs=[],
                declared_modules=set(),
                requires_mod=set(),
            )
            for i in range(n)
        ]

    def test_loads_run_in_parallel(self):
        """``n`` slow loads across ``n`` workers finish in ~one delay, not n.

        A serial loop would take ``n * delay``; the thread pool must
        finish in well under half that. With n=8 and delay=0.25s the
        serial floor is 2.0s and the parallel run is ~0.25s — the 1.0s
        threshold cannot be met by serial execution.
        """
        tasks = self._tasks(_PARALLEL_TASKS)
        load_fn = _sleeping_loader(_PER_LOAD_DELAY)

        start = time.monotonic()
        counts, findings_a, findings_c = run_isolated_loads(
            tasks, set(), max_workers=_PARALLEL_TASKS, load_fn=load_fn
        )
        elapsed = time.monotonic() - start

        self.assertEqual(counts["pass"], _PARALLEL_TASKS)
        self.assertEqual(findings_a, [])
        self.assertEqual(findings_c, [])

        serial_floor = _PARALLEL_TASKS * _PER_LOAD_DELAY
        self.assertLess(
            elapsed,
            serial_floor * 0.5,
            f"isolated loads did not run in parallel: {elapsed:.2f}s elapsed "
            f"for {_PARALLEL_TASKS} loads (serial floor {serial_floor:.2f}s)",
        )

    def test_results_classified_in_task_order(self):
        """Concurrency must not disturb deterministic, ordered classification.

        Tasks finish out of completion order (decreasing sleeps), but the
        findings list must follow task order and the failure must bucket
        as (a) — an undeclared sibling-addon import.
        """
        n = 4
        tasks = self._tasks(n)
        all_modules = {"sibling"}

        def load_fn(target_dir, dep_dirs, module, timeout=30):
            # Earlier tasks sleep longer, so completion order is reversed.
            time.sleep((n - int(module[1:])) * 0.02)
            if module == "m0":
                return 2, "ModuleNotFoundError: No module named 'sibling'"
            return 0, ""

        counts, findings_a, findings_c = run_isolated_loads(
            tasks, all_modules, max_workers=n, load_fn=load_fn
        )

        self.assertEqual(counts["pass"], n - 1)
        self.assertEqual(counts["a"], 1)
        self.assertEqual(len(findings_a), 1)
        self.assertIn("p0 (module m0)", findings_a[0])
        self.assertIn("sibling", findings_a[0])

    def test_empty_task_list_is_noop(self):
        counts, findings_a, findings_c = run_isolated_loads([], set())
        self.assertEqual(counts, {"pass": 0, "a": 0, "b": 0, "c": 0})
        self.assertEqual(findings_a, [])
        self.assertEqual(findings_c, [])


class TestAddonDependencies(unittest.TestCase):
    """Fail when any addon imports a sibling addon it does not declare.

    Full-tree scan — heavy (one isolated-load subprocess per registered
    module) and requires the Gramps runtime importable. Run by the CI
    detector job (which sets ``RUN_ADDON_DEP_SCAN=1`` and times the
    wall-clock); skipped in a plain ``unittest`` run.
    """

    @unittest.skipUnless(
        os.environ.get("RUN_ADDON_DEP_SCAN") == "1",
        "full-tree addon-dependency scan — set RUN_ADDON_DEP_SCAN=1 "
        "(CI detector job) to run",
    )
    def test_no_undeclared_addon_dependencies(self):
        """Every addon's registered modules must import in isolation, given
        only the directories of its declared ``depends_on``.

        A failure that names a sibling-addon module not listed in
        ``depends_on`` is a finding (the #13707 class). A failure that
        names a declared ``requires_mod`` is the environment, not the
        declaration. Anything else is logged separately.
        """
        id_to_addon, all_modules, skipped_gpr = _index_addons(ADDONS_ROOT)
        self.assertGreater(len(id_to_addon), 0, "No addons found — index is empty")

        tasks = build_load_tasks(id_to_addon)
        counts, findings_a, findings_c = run_isolated_loads(tasks, all_modules)

        LOG.info(
            "Indexed %d plugins; load pass=%d, bucket a=%d, b=%d, c=%d; "
            "gpr exec skipped=%d",
            len(id_to_addon),
            counts["pass"],
            counts["a"],
            counts["b"],
            counts["c"],
            len(skipped_gpr),
        )
        if skipped_gpr:
            LOG.warning(
                "%d .gpr.py file(s) failed exec-shim and were skipped:\n%s",
                len(skipped_gpr),
                "\n".join(f"  {p}: {e}" for p, e in skipped_gpr),
            )
        if findings_c:
            LOG.warning(
                "%d addon(s) failed isolated load for non-dependency reasons "
                "(NOT a finding — environment / GUI-state / import-time side "
                "effects):\n%s",
                len(findings_c),
                "\n".join(findings_c),
            )

        if findings_a:
            self.fail(
                "Found %d addon(s) that import a sibling addon without "
                "declaring it in depends_on:\n%s"
                % (len(findings_a), "\n".join(findings_a))
            )


if __name__ == "__main__":
    unittest.main()
