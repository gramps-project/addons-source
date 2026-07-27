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

"""Unit tests for :func:`session.next_state`."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from session import ErrorKind, State, SyncError, next_state


def fake_session(
    error: SyncError | None = None,
    changes: list | None = None,
    has_missing_files: bool = False,
) -> SimpleNamespace:
    """Build a stand-in exposing the attributes :func:`next_state` reads.

    :param error: A terminal error, if any.
    :param changes: The pending change list.
    :param has_missing_files: Whether media files are missing on either side.
    :returns: The stand-in session.
    """
    return SimpleNamespace(
        error=error,
        changes=changes if changes is not None else [],
        has_missing_files=has_missing_files,
    )


class NextStateTest(unittest.TestCase):
    """The happy-path chain and its two conditional skips."""

    def test_linear_path_with_changes_and_files(self) -> None:
        """With both changes and missing files, every state is visited."""
        session = fake_session(changes=["a change"], has_missing_files=True)
        expected = [
            (State.INTRO, State.LOGIN),
            (State.LOGIN, State.COMPARING),
            (State.COMPARING, State.REVIEW_CHANGES),
            (State.REVIEW_CHANGES, State.APPLYING),
            (State.APPLYING, State.REVIEW_FILES),
            (State.REVIEW_FILES, State.TRANSFERRING),
            (State.TRANSFERRING, State.DONE),
        ]
        for state, following in expected:
            with self.subTest(state=state.name):
                self.assertIs(next_state(state, session), following)

    def test_no_changes_but_missing_files_goes_to_the_media_stage(self) -> None:
        session = fake_session(changes=[], has_missing_files=True)
        self.assertIs(next_state(State.COMPARING, session), State.REVIEW_FILES)

    def test_nothing_to_do_at_all_ends_the_run(self) -> None:
        """Fully in sync: no confirmation page of any kind is shown."""
        session = fake_session(changes=[], has_missing_files=False)
        self.assertIs(next_state(State.COMPARING, session), State.DONE)

    def test_applying_with_no_missing_files_ends_the_run(self) -> None:
        """The media page is skipped rather than shown with empty lists."""
        session = fake_session(changes=["a change"], has_missing_files=False)
        self.assertIs(next_state(State.APPLYING, session), State.DONE)

    def test_changes_present_requires_confirmation(self) -> None:
        """Any pending change must be confirmed before it is applied."""
        session = fake_session(changes=["a change"])
        self.assertIs(next_state(State.COMPARING, session), State.REVIEW_CHANGES)

    def test_no_missing_files_skips_transfer(self) -> None:
        """With all media present on both sides, the run ends after review."""
        session = fake_session(has_missing_files=False)
        self.assertIs(next_state(State.REVIEW_FILES, session), State.DONE)

    def test_missing_files_requires_transfer(self) -> None:
        """Missing media on either side means a transfer stage."""
        session = fake_session(has_missing_files=True)
        self.assertIs(next_state(State.REVIEW_FILES, session), State.TRANSFERRING)


class ErrorShortCircuitTest(unittest.TestCase):
    """A recorded error overrides the flow from wherever it happened."""

    def test_error_from_any_state_goes_to_failed(self) -> None:
        """Every non-terminal state jumps to FAILED once an error is set."""
        session = fake_session(
            error=SyncError(ErrorKind.CONFLICT), changes=["a change"]
        )
        for state in State:
            if state in (State.DONE, State.FAILED):
                continue
            with self.subTest(state=state.name):
                self.assertIs(next_state(state, session), State.FAILED)

    def test_error_outranks_the_skip_conditions(self) -> None:
        """The error check runs before any branch that might route elsewhere."""
        session = fake_session(error=SyncError(ErrorKind.AUTH_FAILED), changes=[])
        self.assertIs(next_state(State.COMPARING, session), State.FAILED)


class TerminalStateTest(unittest.TestCase):
    """Terminal states do not advance on their own."""

    def test_done_is_terminal(self) -> None:
        self.assertIs(next_state(State.DONE, fake_session()), State.DONE)

    def test_failed_is_terminal(self) -> None:
        session = fake_session(error=SyncError(ErrorKind.UNEXPECTED))
        self.assertIs(next_state(State.FAILED, session), State.FAILED)


if __name__ == "__main__":
    unittest.main()
