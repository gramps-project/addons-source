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

"""Failure handling, exercised by injecting faults into the fake server."""

from __future__ import annotations

import unittest
from urllib.error import URLError

from session import ErrorKind, State

from .fakes import http_error
from .scenario import (
    DEFAULT_URL as URL,
    DEFAULT_USERNAME as USERNAME,
    T0,
    T2,
    SyncScenario,
)


class LoginFailureTest(unittest.TestCase):
    """Authentication and reachability problems at connect time."""

    def make_scenario(self, **kwargs) -> SyncScenario:
        scenario = SyncScenario(**kwargs)
        self.addCleanup(scenario.close)
        scenario.seed_person("I0001", surname="Doe", changed_at=T0)
        scenario.share()
        return scenario

    def test_http_statuses_map_to_distinct_error_kinds(self) -> None:
        """Each status the server can return is reported as its own kind."""
        cases = [
            (401, ErrorKind.AUTH_FAILED),
            (403, ErrorKind.FORBIDDEN),
            (404, ErrorKind.NOT_FOUND),
            (429, ErrorKind.RATE_LIMITED),
            (503, ErrorKind.TREE_DISABLED),
            (500, ErrorKind.SERVER_ERROR),
        ]
        for code, expected in cases:
            with self.subTest(code=code):
                scenario = self.make_scenario()
                scenario.server.fail_always("get_permissions", http_error(code))
                result = scenario.run()
                self.assertIs(result.final_state, State.LOGIN)
                self.assertIsNotNone(result.login_error)
                self.assertIs(result.login_error.kind, expected)

    def test_login_failure_is_recoverable_not_terminal(self) -> None:
        """A rejected login must not set the terminal error."""
        scenario = self.make_scenario()
        scenario.server.fail_always("get_permissions", http_error(401))
        result = scenario.run()
        self.assertIsNone(result.error)
        self.assertIs(result.final_state, State.LOGIN)

    def test_unreachable_server_reports_a_connection_failure(self) -> None:
        scenario = self.make_scenario()
        scenario.server.fail_always("get_permissions", URLError("no route to host"))
        result = scenario.run()
        self.assertIs(result.login_error.kind, ErrorKind.CONNECTION_FAILED)

    def test_non_api_response_reports_an_invalid_response(self) -> None:
        """Something answered, but it was not the Gramps Web API."""
        scenario = self.make_scenario()
        scenario.server.fail_always("get_permissions", ValueError("not JSON"))
        result = scenario.run()
        self.assertIs(result.login_error.kind, ErrorKind.INVALID_RESPONSE)

    def test_user_without_required_permission_is_refused(self) -> None:
        """Without ViewPrivate the export is partial, so sync must not start."""
        scenario = self.make_scenario(permissions={"ViewObject"})
        result = scenario.run()
        self.assertIs(result.final_state, State.LOGIN)
        self.assertIs(result.login_error.kind, ErrorKind.INSUFFICIENT_PERMISSIONS)

    def test_failed_login_does_not_touch_either_tree(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.server.fail_always("get_permissions", http_error(401))

        scenario.run()

        self.assertEqual(scenario.remote.surname("I0001"), "Doe")
        self.assertEqual(scenario.server.committed, [])


class MidSyncFailureTest(unittest.TestCase):
    """Failures after the connection is established are terminal."""

    def make_scenario(self) -> SyncScenario:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.seed_person("I0001", surname="Doe", changed_at=T0)
        scenario.seed_person("I0002", surname="Roe", changed_at=T0)
        scenario.share()
        return scenario

    def test_export_download_failure_fails_the_run(self) -> None:
        scenario = self.make_scenario()
        scenario.server.fail_always("download_xml", http_error(500))
        result = scenario.run()
        self.assertIs(result.final_state, State.FAILED)
        self.assertIs(result.error.kind, ErrorKind.SERVER_ERROR)

    def test_transaction_conflict_is_reported_as_a_conflict(self) -> None:
        """HTTP 409 means the server rejected the transaction as stale."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.server.fail_always("commit", http_error(409))

        result = scenario.run()

        self.assertIs(result.final_state, State.FAILED)
        self.assertIs(result.error.kind, ErrorKind.CONFLICT)

    def test_expired_token_mid_sync_is_reported_as_auth_failure(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.server.fail_always("commit", http_error(401))
        result = scenario.run()
        self.assertIs(result.error.kind, ErrorKind.AUTH_FAILED)

    def test_failed_run_does_not_record_a_sync_timestamp(self) -> None:
        """Recording it would move the diff cutoff past the unsynced changes."""
        scenario = self.make_scenario()
        scenario.credentials.timestamp = T0
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.server.fail_always("commit", http_error(409))

        scenario.run()

        self.assertEqual(scenario.credentials.get_timestamp(URL, USERNAME), T0)

    def test_local_changes_survive_a_failed_remote_commit(self) -> None:
        """The local half commits before the remote half is even attempted."""
        scenario = self.make_scenario()
        scenario.remote.edit_person("I0002", surname="Neu", changed_at=T2)
        scenario.local.edit_person("I0001", surname="Mueller", changed_at=T2)
        scenario.server.fail_always("commit", http_error(500))

        result = scenario.run()

        self.assertIs(result.final_state, State.FAILED)
        self.assertEqual(scenario.local.surname("I0002"), "Neu")


class CancellationTest(unittest.TestCase):
    """Cancelling must stop work that has been scheduled but not yet run."""

    def make_scenario(self) -> SyncScenario:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.seed_person("I0001", surname="Doe", changed_at=T0)
        scenario.share()
        return scenario

    def test_cancel_before_compare_skips_the_download(self) -> None:
        scenario = self.make_scenario()
        session = scenario.make_session()
        session.begin()
        session.cancel()

        session._fetch_xml()

        self.assertNotIn("download_xml", scenario.server.calls)

    def test_cancel_before_apply_sends_nothing(self) -> None:
        """``cancel`` releases the diff handler, so applying must not proceed."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        session = scenario.make_session()
        session.begin()
        session.submit_credentials("https://example.org/api", "owner", "secret")
        session.cancel()

        session._apply_local()

        self.assertEqual(scenario.server.committed, [])

    def test_cancel_before_transfer_moves_no_files(self) -> None:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.local.add_media("O0001", "photo.jpg", changed_at=T0)
        scenario.share()
        session = scenario.make_session()
        session.begin()
        session.submit_credentials("https://example.org/api", "owner", "secret")
        session.cancel()

        session._transfer(*session._resolve_transfers())

        self.assertEqual(scenario.server.media_files, {})


class MediaFailureTest(unittest.TestCase):
    """One bad media file must not abort the whole transfer."""

    def make_scenario(self) -> SyncScenario:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        return scenario

    def test_failed_download_is_recorded_without_failing_the_run(self) -> None:
        """A single unreadable file is recorded and the run continues."""
        scenario = self.make_scenario()
        first = scenario.local.add_media("O0001", "first.jpg", on_disk=False)
        second = scenario.local.add_media("O0002", "second.jpg", on_disk=False)
        scenario.share()
        # The server holds both files, so nothing needs uploading and this
        # test isolates the download path.
        scenario.server.media_files[first] = b"first bytes"
        scenario.server.media_files[second] = b"second bytes"
        scenario.server.fail_next("download_media_file", http_error(500))

        result = scenario.run()

        self.assertIs(result.final_state, State.DONE)
        self.assertEqual(result.session.downloaded, {"O0001": False, "O0002": True})

    def test_file_missing_on_both_sides_is_reported_once(self) -> None:
        """Neither side can supply such a file, so neither transfer is tried.

        It used to appear in both missing lists, so the download 404d and the
        upload found nothing to send, and the user was told of two errors for
        one file that simply does not exist anywhere.
        """
        scenario = self.make_scenario()
        scenario.local.add_media("O0001", "nowhere.jpg", on_disk=False)
        scenario.share()

        result = scenario.run()

        self.assertIs(result.final_state, State.DONE)
        self.assertIsNone(result.error)
        self.assertEqual([gid for gid, _h in result.session.missing_both], ["O0001"])
        self.assertEqual(result.session.missing_local, [])
        self.assertEqual(result.session.missing_remote, [])
        self.assertEqual(result.session.downloaded, {})
        self.assertEqual(result.session.uploaded, {})

    def test_upload_still_fails_the_run_on_a_server_error(self) -> None:
        """The new guard must not swallow genuine transport failures."""
        scenario = self.make_scenario()
        scenario.local.add_media("O0002", "present.jpg", changed_at=T0)
        scenario.share()
        scenario.server.fail_always("upload_media_file", http_error(500))

        result = scenario.run()

        self.assertIs(result.final_state, State.FAILED)
        self.assertIs(result.error.kind, ErrorKind.SERVER_ERROR)


if __name__ == "__main__":
    unittest.main()
