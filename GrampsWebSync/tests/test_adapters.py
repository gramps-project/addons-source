# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       David Straub
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

"""Tests for the production ports in :mod:`adapters`.

Drives a real :class:`GLib.MainLoop`; no widgets are built, so no display is
needed.
"""

from __future__ import annotations

import threading
import unittest

from adapters import GLibTaskRunner, IoRunner
from gi.repository import GLib

#: Milliseconds before an unresponsive loop is torn down.
TIMEOUT_MS = 5000


def run_task(func, runner=None):
    """Run ``func`` through a runner and return the outcome.

    :param func: The task to schedule.
    :param runner: The runner to use. Defaults to :class:`GLibTaskRunner`.
    :returns: Dict with ``result`` or ``error``, ``thread`` and
        ``callback_thread``.
    """
    outcome: dict = {}
    loop = GLib.MainLoop()

    def on_success(result):
        outcome["result"] = result
        outcome["callback_thread"] = threading.current_thread()
        loop.quit()

    def on_error(exc):
        outcome["error"] = exc
        outcome["callback_thread"] = threading.current_thread()
        loop.quit()

    def wrapped():
        outcome["thread"] = threading.current_thread()
        return func()

    (runner or GLibTaskRunner()).run(wrapped, on_success, on_error)
    GLib.timeout_add(TIMEOUT_MS, loop.quit)
    loop.run()
    return outcome


class GLibTaskRunnerTest(unittest.TestCase):
    """The runner must keep work on the thread that owns GTK."""

    def test_task_runs_on_the_calling_thread(self) -> None:
        """Steps drive Gramps progress through the GUI ``User``, which touches
        widgets. Running them on a worker thread segfaults inside ``diff_dbs``,
        so the runner must not spawn one."""
        outcome = run_task(lambda: "done")
        self.assertEqual(outcome.get("result"), "done")
        self.assertIs(outcome["thread"], threading.current_thread())

    def test_success_callback_receives_the_return_value(self) -> None:
        self.assertEqual(run_task(lambda: 42).get("result"), 42)

    def test_failure_is_reported_to_the_error_callback(self) -> None:
        def boom():
            raise ValueError("boom")

        outcome = run_task(boom)
        self.assertNotIn("result", outcome)
        self.assertIsInstance(outcome.get("error"), ValueError)

    def test_task_is_run_exactly_once(self) -> None:
        """The idle source must remove itself, or it repeats forever."""
        calls = []
        run_task(lambda: calls.append(1))
        self.assertEqual(len(calls), 1)


class IoRunnerTest(unittest.TestCase):
    """Network steps leave the main loop, but their callbacks come back to it."""

    def test_task_runs_off_the_calling_thread(self) -> None:
        """This is what keeps the window responsive while a request is in
        flight, and what makes Cancel work at all."""
        outcome = run_task(lambda: "done", runner=IoRunner())
        self.assertEqual(outcome.get("result"), "done")
        self.assertIsNot(outcome["thread"], threading.current_thread())

    def test_callback_returns_to_the_main_loop(self) -> None:
        """Listeners draw widgets, so they must not run on the worker."""
        outcome = run_task(lambda: "done", runner=IoRunner())
        self.assertIs(outcome["callback_thread"], threading.current_thread())

    def test_failure_is_reported_to_the_error_callback(self) -> None:
        def boom():
            raise ValueError("boom")

        outcome = run_task(boom, runner=IoRunner())
        self.assertNotIn("result", outcome)
        self.assertIsInstance(outcome.get("error"), ValueError)

    def test_post_runs_on_the_main_loop(self) -> None:
        """Progress raised inside a network step is marshalled through this."""
        seen: dict = {}
        loop = GLib.MainLoop()

        def note():
            seen["thread"] = threading.current_thread()
            loop.quit()

        threading.Thread(target=lambda: IoRunner().post(note)).start()
        GLib.timeout_add(TIMEOUT_MS, loop.quit)
        loop.run()
        self.assertIs(seen.get("thread"), threading.current_thread())


if __name__ == "__main__":
    unittest.main()
