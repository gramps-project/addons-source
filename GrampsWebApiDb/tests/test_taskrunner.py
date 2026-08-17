#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Douglas S. Blank <doug.blank@gmail.com>
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
Unit tests for taskrunner.GLibTaskRunner/IoRunner and
tests.fakes.InlineTaskRunner.

Uses a real (but GUI-less) GLib.MainContext to prove GLibTaskRunner/
IoRunner actually dispatch the way their docstrings claim -- the only place
in this addon's test suite that drives a real main loop or a real thread,
since every other test swaps in InlineTaskRunner. See grampswebapidb.py's
module docstring for why this addon needs both.

Run with::

    python3 -m unittest GrampsWebApiDb.tests.test_taskrunner -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import os
import sys
import threading
import unittest

# -------------------------------------------------------------------------
#
# Make the addon importable the way Gramps loads it: its own directory on
# sys.path (grampswebapidb.py/webapi_client.py use bare, not package-
# relative, imports of each other -- see CLAUDE.md Testing conventions).
#
# -------------------------------------------------------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib
except ImportError as _err:
    raise unittest.SkipTest("PyGObject not available: %s" % _err)

from GrampsWebApiDb.taskrunner import GLibTaskRunner, IoRunner
from GrampsWebApiDb.tests.fakes import InlineTaskRunner


def _pump_until(predicate, timeout=5.0):
    """Iterate the default GLib main context until predicate() is true.

    Test-only helper: a bounded stand-in for a real GTK main loop, the same
    shape as grampswebapidb.py's own _run_async_to_completion() wait-adapter
    but with a hard timeout so a broken runner fails the test instead of
    hanging it forever.
    """
    import time as _time

    context = GLib.MainContext.default()
    deadline = _time.monotonic() + timeout
    while not predicate():
        if _time.monotonic() > deadline:
            raise AssertionError(
                "timed out waiting for the main loop to deliver a result"
            )
        context.iteration(True)


class TestGLibTaskRunner(unittest.TestCase):
    def test_success_runs_func_on_the_main_loop_and_calls_on_success(self):
        main_thread = threading.current_thread()
        seen = {}

        def func():
            seen["thread"] = threading.current_thread()
            return 42

        def on_success(result):
            seen["success"] = result

        def on_error(exc):
            seen["error"] = exc

        GLibTaskRunner().run(func, on_success, on_error)
        _pump_until(lambda: "success" in seen or "error" in seen)

        self.assertEqual(seen.get("success"), 42)
        self.assertNotIn("error", seen)
        self.assertIs(seen["thread"], main_thread)

    def test_exception_is_reported_to_on_error_not_raised(self):
        seen = {}
        boom = RuntimeError("boom")

        def func():
            raise boom

        GLibTaskRunner().run(
            func,
            on_success=lambda result: seen.__setitem__("success", result),
            on_error=lambda exc: seen.__setitem__("error", exc),
        )
        _pump_until(lambda: "success" in seen or "error" in seen)

        self.assertNotIn("success", seen)
        self.assertIs(seen.get("error"), boom)

    def test_post_runs_func_on_the_main_loop(self):
        main_thread = threading.current_thread()
        seen = {}

        GLibTaskRunner().post(
            lambda: seen.__setitem__("thread", threading.current_thread())
        )
        _pump_until(lambda: "thread" in seen)

        self.assertIs(seen["thread"], main_thread)


class TestIoRunner(unittest.TestCase):
    def test_func_runs_on_a_different_thread_than_the_caller(self):
        caller_thread = threading.current_thread()
        seen = {}

        def func():
            seen["thread"] = threading.current_thread()
            return "ok"

        IoRunner().run(
            func,
            on_success=lambda result: seen.__setitem__("success", result),
            on_error=lambda exc: seen.__setitem__("error", exc),
        )
        _pump_until(lambda: "success" in seen or "error" in seen)

        self.assertEqual(seen.get("success"), "ok")
        self.assertIsNot(seen["thread"], caller_thread)

    def test_on_success_is_dispatched_back_on_the_main_thread(self):
        main_thread = threading.current_thread()
        seen = {}

        IoRunner().run(
            lambda: None,
            on_success=lambda _: seen.__setitem__("thread", threading.current_thread()),
            on_error=lambda exc: seen.__setitem__("error", exc),
        )
        _pump_until(lambda: "thread" in seen or "error" in seen)

        self.assertNotIn("error", seen)
        self.assertIs(seen["thread"], main_thread)

    def test_exception_is_marshalled_to_on_error_on_the_main_thread(self):
        main_thread = threading.current_thread()
        seen = {}
        boom = RuntimeError("boom")

        def func():
            raise boom

        IoRunner().run(
            func,
            on_success=lambda result: seen.__setitem__("success", result),
            on_error=lambda exc: seen.update(
                error=exc, thread=threading.current_thread()
            ),
        )
        _pump_until(lambda: "error" in seen)

        self.assertNotIn("success", seen)
        self.assertIs(seen["error"], boom)
        self.assertIs(seen["thread"], main_thread)

    def test_post_runs_func_on_the_main_thread(self):
        main_thread = threading.current_thread()
        seen = {}

        IoRunner().post(lambda: seen.__setitem__("thread", threading.current_thread()))
        _pump_until(lambda: "thread" in seen)

        self.assertIs(seen["thread"], main_thread)


class TestInlineTaskRunner(unittest.TestCase):
    def test_run_success_calls_on_success_synchronously(self):
        seen = {}
        InlineTaskRunner().run(
            lambda: 7,
            on_success=lambda result: seen.__setitem__("success", result),
            on_error=lambda exc: seen.__setitem__("error", exc),
        )
        self.assertEqual(seen, {"success": 7})

    def test_run_error_calls_on_error_synchronously(self):
        seen = {}
        boom = RuntimeError("boom")

        def func():
            raise boom

        InlineTaskRunner().run(
            func,
            on_success=lambda result: seen.__setitem__("success", result),
            on_error=lambda exc: seen.__setitem__("error", exc),
        )
        self.assertEqual(seen, {"error": boom})

    def test_post_runs_immediately(self):
        seen = []
        InlineTaskRunner().post(lambda: seen.append(1))
        self.assertEqual(seen, [1])


if __name__ == "__main__":
    unittest.main()
