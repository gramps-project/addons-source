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
Test doubles for taskrunner.TaskRunner. InlineTaskRunner is ported from the
GrampsWebSync addon's tests/fakes.py (same repo, same license -- credit to
David Straub for the original).
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
from collections.abc import Callable
from typing import Any


class InlineTaskRunner:
    """Runs each task synchronously on the calling thread.

    By the time ``run`` returns, the step and its completion callback have
    both finished. Standing in for both ``self.runner`` and
    ``self.io_runner`` keeps a test single-threaded and its assertions
    deterministic: an async chain built from ``..._async()`` methods
    resolves entirely within the one call that kicks it off, with no real
    thread and no real GLib main loop involved.
    """

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Execute ``func`` and dispatch to the appropriate callback."""
        try:
            result = func()
        except BaseException as exc:  # noqa: BLE001 -- mirrors the real runner
            on_error(exc)
        else:
            on_success(result)

    def post(self, func: Callable[[], None]) -> None:
        """Run ``func`` immediately; there is no other thread to marshal from."""
        func()
