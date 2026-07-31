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

"""Recovering from a failed run, and refusing to commit a stale comparison."""

from __future__ import annotations

import unittest

from const import MODE_BIDIRECTIONAL
from gramps.gen.db import DbTxn
from session import ErrorKind, State, Step, SyncSession

from .fakes import http_error
from .scenario import (
    DEFAULT_URL as URL,
    DEFAULT_USERNAME as USERNAME,
    T0,
    T2,
    SyncScenario,
)


class RecoveryTestCase(unittest.TestCase):
    """Drives a session by hand, so a run can be interrupted mid-flow."""

    def make_scenario(self) -> SyncScenario:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.seed_person("I0001", surname="Doe", changed_at=T0)
        scenario.seed_person("I0002", surname="Roe", changed_at=T0)
        scenario.share()
        return scenario

    def connect(self, scenario: SyncScenario) -> SyncSession:
        """Return a session that has connected and compared."""
        session = scenario.make_session()
        session.begin()
        session.submit_credentials(URL, USERNAME, "secret")
        return session


class RetryTest(RecoveryTestCase):
    """A failed run resumes where it stopped rather than starting over."""

    def test_no_retry_is_offered_without_a_failure(self) -> None:
        scenario = self.make_scenario()
        session = self.connect(scenario)
        self.assertFalse(session.can_retry)

    def test_a_failed_push_can_be_retried(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        scenario.server.fail_next("commit", http_error(500))
        session = self.connect(scenario)

        session.confirm_changes(MODE_BIDIRECTIONAL)
        self.assertIs(session.state, State.FAILED)
        self.assertIs(session.failed_in, Step.PUSH_REMOTE)

        session.retry()

        self.assertIsNone(session.error)
        self.assertEqual(scenario.remote.surname("I0001"), "Mueller")

    def test_retrying_a_push_does_not_re_apply_the_local_half(self) -> None:
        """Resuming at the failed step is the whole point of tracking it."""
        scenario = self.make_scenario()
        scenario.remote.edit_person("I0002", surname="Neu", changed_at=T2)
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        scenario.server.fail_next("commit", http_error(500))
        session = self.connect(scenario)

        session.confirm_changes(MODE_BIDIRECTIONAL)
        session.retry()

        # One payload reached the server: the retry re-sent, it did not stack a
        # second local transaction on top of the first.
        self.assertEqual(len(scenario.server.committed), 1)
        self.assertEqual(scenario.local.surname("I0002"), "Neu")

    def test_retrying_a_push_does_not_download_the_tree_again(self) -> None:
        """The remote database is kept open precisely so this is cheap."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        scenario.server.fail_next("commit", http_error(500))
        session = self.connect(scenario)

        session.confirm_changes(MODE_BIDIRECTIONAL)
        session.retry()

        self.assertEqual(scenario.server.calls.count("download_xml"), 1)

    def test_a_failed_download_is_retried_from_the_start(self) -> None:
        scenario = self.make_scenario()
        scenario.server.fail_next("download_xml", http_error(500))
        session = scenario.make_session()
        session.begin()
        session.submit_credentials(URL, USERNAME, "secret")

        self.assertIs(session.state, State.FAILED)
        self.assertIs(session.failed_in, Step.FETCH)

        session.retry()

        self.assertIsNone(session.error)
        self.assertEqual(scenario.server.calls.count("download_xml"), 2)

    def test_a_failed_transfer_resumes_with_the_remaining_files(self) -> None:
        """Files already moved are not sent twice."""
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.local.add_media("O0001", "one.jpg", changed_at=T0)
        scenario.local.add_media("O0002", "two.jpg", changed_at=T0)
        scenario.share()
        session = self.connect(scenario)
        self.assertIs(session.state, State.REVIEW_FILES)

        scenario.server.fail_next("upload_media_file", http_error(500))
        session.confirm_files()
        self.assertIs(session.state, State.FAILED)

        session.retry()

        self.assertIs(session.state, State.DONE)
        self.assertEqual(session.uploaded, {"O0001": True, "O0002": True})
        self.assertEqual(len(scenario.server.media_files), 2)

    def test_retry_without_a_recorded_step_does_nothing(self) -> None:
        scenario = self.make_scenario()
        session = self.connect(scenario)
        session.failed_in = None
        session.retry()  # must not raise
        self.assertIsNone(session.error)


class StaleComparisonTest(RecoveryTestCase):
    """Edits made while the review page is open must not be overwritten.

    The comparison captures object snapshots and the tool does not block the
    main window, so the user can keep editing. Committing those snapshots would
    silently discard whatever they did in the meantime.
    """

    def test_an_edit_during_review_stops_the_commit(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        session = self.connect(scenario)
        self.assertIs(session.state, State.REVIEW_CHANGES)

        scenario.local.edit_person("I0001", surname="Later", changed_at=T2 + 10)
        session.confirm_changes(MODE_BIDIRECTIONAL)

        self.assertIs(session.state, State.FAILED)
        self.assertIs(session.error.kind, ErrorKind.STALE_LOCAL_DATA)

    def test_nothing_is_sent_when_the_comparison_is_stale(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        session = self.connect(scenario)

        scenario.local.edit_person("I0001", surname="Later", changed_at=T2 + 10)
        session.confirm_changes(MODE_BIDIRECTIONAL)

        self.assertEqual(scenario.server.committed, [])
        self.assertEqual(scenario.local.surname("I0001"), "Later")

    def test_a_deletion_during_review_is_caught(self) -> None:
        """A delete is as destructive as an edit and must be caught too."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        session = self.connect(scenario)

        scenario.local.delete_person("I0001")
        session.confirm_changes(MODE_BIDIRECTIONAL)

        self.assertIs(session.error.kind, ErrorKind.STALE_LOCAL_DATA)

    def test_an_object_appearing_locally_is_caught(self) -> None:
        """The action was 'add here', which now would collide with real data."""
        scenario = self.make_scenario()
        scenario.remote.add_person("I0003", surname="Nieuw", changed_at=T2)
        session = self.connect(scenario)
        self.assertIs(session.state, State.REVIEW_CHANGES)

        person = scenario.remote.person("I0003")
        with DbTxn("local add", scenario.db1) as trans:
            scenario.db1.add_person(person, trans)

        session.confirm_changes(MODE_BIDIRECTIONAL)

        self.assertIs(session.error.kind, ErrorKind.STALE_LOCAL_DATA)

    def test_retry_after_a_stale_comparison_compares_again(self) -> None:
        """The snapshots are worthless, so resuming the commit is not an option."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        session = self.connect(scenario)

        scenario.local.edit_person("I0001", surname="Later", changed_at=T2 + 10)
        session.confirm_changes(MODE_BIDIRECTIONAL)
        self.assertIs(session.failed_in, Step.DIFF)

        session.retry()

        self.assertEqual(scenario.server.calls.count("download_xml"), 2)
        self.assertIsNone(session.error)

    def test_an_untouched_tree_commits_normally(self) -> None:
        """The guard must not fire on a run where nothing changed underneath."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        session = self.connect(scenario)

        session.confirm_changes(MODE_BIDIRECTIONAL)

        self.assertIsNone(session.error)
        self.assertEqual(scenario.remote.surname("I0001"), "Mueller")


if __name__ == "__main__":
    unittest.main()
