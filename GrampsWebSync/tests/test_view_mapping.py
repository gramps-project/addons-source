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

import grampswebsync
from grampswebsync import PAGE_FOR_STATE, error_message
from session import ErrorKind, State


class PageMappingTest(unittest.TestCase):
    """Every flow state must correspond to a page the assistant owns."""

    def test_every_state_maps_to_a_page(self) -> None:
        self.assertEqual(set(PAGE_FOR_STATE), set(State))

    def test_page_indices_match_the_assistant_page_order(self) -> None:
        """Indices must be the contiguous range the pages are appended in.

        The assistant addresses pages positionally, so a gap or an off-by-one
        here sends the user to the wrong page rather than failing loudly.
        """
        self.assertEqual(sorted(set(PAGE_FOR_STATE.values())), list(range(8)))

    def test_terminal_states_share_the_conclusion_page(self) -> None:
        """Success and failure are both reported on the last page."""
        self.assertEqual(
            PAGE_FOR_STATE[State.DONE], PAGE_FOR_STATE[State.FAILED]
        )
        self.assertEqual(PAGE_FOR_STATE[State.DONE], grampswebsync.PAGE_CONCLUSION)


class ErrorMessageTest(unittest.TestCase):
    """Every error the session can record must render as something readable."""

    def test_every_error_kind_has_a_message(self) -> None:
        """An unmapped kind would surface to the user as an empty dialog."""
        for kind in ErrorKind:
            with self.subTest(kind=kind.name):
                message = error_message(kind, "42")
                self.assertTrue(message.strip(), f"{kind.name} rendered empty")

    def test_detail_is_included_where_it_carries_information(self) -> None:
        """Status codes must reach the user for the otherwise-opaque kinds."""
        self.assertIn("42", error_message(ErrorKind.SERVER_ERROR, "42"))
        self.assertIn("boom", error_message(ErrorKind.UNEXPECTED, "boom"))


if __name__ == "__main__":
    unittest.main()
