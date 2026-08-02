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

"""Checks that the GTK view's lookup tables cover the session's enums.

Constructs no widgets, so no display is needed.
"""

from __future__ import annotations

import unittest

from grampswebsync import (
    PANE_CONNECT,
    PANE_FOR_STATE,
    PANE_RESULT,
    PANE_REVIEW,
    PANE_WORKING,
)
from session import State, WORKING_STATES


class PaneMappingTest(unittest.TestCase):
    """Every flow state must correspond to a pane the stack owns."""

    def test_every_state_maps_to_a_pane(self) -> None:
        self.assertEqual(set(PANE_FOR_STATE), set(State))

    def test_only_the_four_panes_are_named(self) -> None:
        """A typo in a pane name would leave the stack showing the wrong child."""
        self.assertEqual(
            set(PANE_FOR_STATE.values()),
            {PANE_CONNECT, PANE_WORKING, PANE_REVIEW, PANE_RESULT},
        )

    def test_terminal_states_share_the_result_pane(self) -> None:
        """Success and failure are both reported in the same place."""
        self.assertEqual(PANE_FOR_STATE[State.DONE], PANE_RESULT)
        self.assertEqual(PANE_FOR_STATE[State.FAILED], PANE_RESULT)

    def test_every_working_state_shows_the_working_pane(self) -> None:
        """The phase list is indexed by this tuple, so the two must agree."""
        for state in WORKING_STATES:
            with self.subTest(state=state.name):
                self.assertEqual(PANE_FOR_STATE[state], PANE_WORKING)

    def test_working_states_are_the_ones_that_run_unattended(self) -> None:
        """Anything else waits for the user, and must not join the phase list."""
        waiting = {State.CONNECT, State.REVIEW, State.DONE, State.FAILED}
        self.assertEqual(set(WORKING_STATES), set(State) - waiting)


if __name__ == "__main__":
    unittest.main()
