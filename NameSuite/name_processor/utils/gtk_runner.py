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

from collections.abc import Generator, Callable

from gi.repository import GLib


def run_in_idle_loop(
    generator: Generator[None, None, object | None],
    on_complete: Callable[[object | None], None] | None = None,
) -> GLib.Source:
    """
    Executes a chunked generator in the GTK idle loop to prevent UI freezing.

    :param generator: A generator yielding control periodically.
    :param on_complete: Callback executed with the generator's final return value.
    """

    def process_chunk() -> bool:
        try:
            next(generator)
            return True  # Tell GTK to keep calling this when idle
        except StopIteration as e:
            # Generator finished naturally
            if on_complete:
                on_complete(e.value)
            return False  # Stop the idle loop
        except Exception as e:
            # Log or handle unexpected DB/Processing errors
            print(f"Background task failed: {e}")
            return False

    return GLib.idle_add(process_chunk)
