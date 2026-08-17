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


class FakeHandleDb:
    """Minimal stand-in for the ``db`` argument grampswebapidb.py's
    _prune_dangling_references() (called from _merge_or_overwrite()) uses
    to check whether a Tag/Note/Citation handle still exists: answers
    has_tag_handle()/has_note_handle()/has_citation_handle() from a
    settable set of "known" handles.

    Defaults to reporting every handle as known (``known_handles=None``),
    so a test that isn't exercising the pruning itself can pass one
    without also having to enumerate every handle its test objects use.
    """

    def __init__(self, known_handles=None):
        self.known_handles = known_handles

    def _has_handle(self, handle):
        return True if self.known_handles is None else handle in self.known_handles

    has_tag_handle = _has_handle
    has_note_handle = _has_handle
    has_citation_handle = _has_handle
