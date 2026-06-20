#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import TypeVar


T = TypeVar("T")


class SynchronousTaskRunner:
    """Synchronous implementation of BackgroundTaskRunner for testing."""

    def run_chunked(
        self,
        generator: Generator[None, None, T],
        on_complete: Callable[[T | None], None] | None = None,
    ) -> None:
        """
        Execute a generator synchronously to completion.

        This is intended for use in tests where we want deterministic
        behavior without the GTK main loop.

        Args:
            generator: A generator yielding control periodically.
            on_complete: Callback executed with the generator's final return value.
        """
        try:
            # Consume the entire generator
            while True:
                next(generator)
        except StopIteration as e:
            # Generator finished naturally
            if on_complete:
                on_complete(e.value)
        except Exception as e:
            # Propagate exceptions in tests (don't swallow them)
            raise RuntimeError(f"Synchronous task failed: {e}") from e
