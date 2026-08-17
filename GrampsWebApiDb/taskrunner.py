#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2026 David Straub
# Copyright (C) 2026      Douglas S. Blank <doug.blank@gmail.com>
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
Two task runners, ported from the GrampsWebSync addon's session.py/
adapters.py (same repo, same license -- credit to David Straub for the
original TaskRunner protocol and both implementations below). Re-added here
(rather than importing GrampsWebSync directly) so this addon has no runtime
dependency on another addon being installed -- the same reasoning
webapi_client.py's own module docstring gives for vendoring rather than
importing.

grampswebapidb.py used to keep the GTK main thread responsive during a
blocking network call by re-entering the main loop mid-operation
(_pump_main_loop()/_guarded_pump(), see that module's docstring for the
history). That reentrancy caused two separate production crashes: switching
Family Trees while a pump-driven sync was suspended mid-operation resumed
against an already-closed sqlite connection, and an unrelated GTK
callback's exception, dispatched from a pump, propagated up through this
addon's own call stack and crashed the whole application. Both were
patched defensively, but the root cause is the reentrancy itself, not
either specific symptom.

GLibTaskRunner and IoRunner replace that: network I/O moves onto a real
worker thread (IoRunner) so the main thread is never blocked waiting on it,
and DB-touching work stays on the main thread (GLibTaskRunner) since the
sqlite backend is usable only from the thread that created the connection
(no check_same_thread=False). Nothing in grampswebapidb.py needs to
re-enter the main loop anymore -- see that module's docstring for the one
remaining exception (load()'s bootstrap sync).
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, Protocol

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import GLib


class TaskRunner(Protocol):
    """Runs a potentially slow callable and reports the outcome back."""

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None: ...

    def post(self, func: Callable[[], None]) -> None: ...


def _post_to_main_loop(func: Callable[[], None]) -> None:
    """Schedule ``func`` to run once on the GTK main loop."""

    def once() -> bool:
        func()
        return False

    GLib.idle_add(once)


class GLibTaskRunner:
    """Defers a task to the GTK main loop.

    For steps that touch a Gramps database. Those must not run on a worker
    thread: the sqlite backend passes no ``check_same_thread=False`` and
    shares one cursor, so a connection is usable only from the thread that
    created it.

    :func:`GLib.idle_add` keeps the work on the main loop while still
    letting the caller return immediately.
    """

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Schedule ``func`` on the main loop and dispatch the outcome there."""

        def once() -> bool:
            try:
                result = func()
            except BaseException as exc:  # noqa: BLE001 -- reported, not swallowed
                on_error(exc)
            else:
                on_success(result)
            return False  # run once

        GLib.idle_add(once)

    def post(self, func: Callable[[], None]) -> None:
        """Run ``func`` on the main loop."""
        _post_to_main_loop(func)


class IoRunner:
    """Runs a task on a worker thread, dispatching the outcome on the main loop.

    For steps that only do network I/O (webapi_client calls) -- never for
    anything that reads or writes ``self.dbapi``. Network waits are where a
    sync/push spends most of its wall-clock time and the only place it can
    block indefinitely, so moving them off the main loop is what keeps the
    window responsive without needing to re-enter the main loop to fake it.
    Callbacks are marshalled back through :func:`GLib.idle_add`, so
    listeners still run on the thread that owns GTK.
    """

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Run ``func`` on a worker thread; call back on the main loop."""

        def work() -> None:
            try:
                result = func()
            except BaseException as exc:  # noqa: BLE001
                # Handed straight on: `except ... as exc` unbinds the name
                # when the block exits, and the callback runs later than that.
                self._dispatch(on_error, exc)
            else:
                self._dispatch(on_success, result)

        # daemon=True: a worker abandoned by close() (tree closed while a
        # push/sync is in flight) finishes quietly in the background and
        # does not block process exit.
        threading.Thread(target=work, daemon=True, name="grampswebapidb-io").start()

    @staticmethod
    def _dispatch(callback: Callable[[Any], None], value: Any) -> None:
        _post_to_main_loop(lambda: callback(value))

    def post(self, func: Callable[[], None]) -> None:
        """Run ``func`` on the main loop."""
        _post_to_main_loop(func)
