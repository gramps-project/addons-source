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

"""End-to-end sync runs against an in-process fake Gramps Web server."""

from __future__ import annotations

import os
import unittest

from const import (
    C_ADD_LOC,
    C_ADD_REM,
    C_DEL_LOC,
    C_DEL_REM,
    C_UPD_BOTH,
    C_UPD_LOC,
    C_UPD_REM,
    MODE_BIDIRECTIONAL,
    MODE_RESET_TO_LOCAL,
    MODE_RESET_TO_REMOTE,
)
from session import (
    STATUS_COMPARING,
    STATUS_FETCHING,
    STATUS_LOCAL_APPLIED,
    State,
)

from .scenario import (
    DEFAULT_URL as URL,
    DEFAULT_USERNAME as USERNAME,
    T0,
    T2,
    T3,
    SyncScenario,
)


class SyncFlowTestCase(unittest.TestCase):
    """Base class providing a seeded, shared two-tree scenario."""

    def make_scenario(self, **kwargs) -> SyncScenario:
        """Return a shared scenario with two people, registered for teardown."""
        scenario = SyncScenario(**kwargs)
        self.addCleanup(scenario.close)
        scenario.seed_person("I0001", surname="Doe", changed_at=T0)
        scenario.seed_person("I0002", surname="Roe", changed_at=T0)
        scenario.share()
        return scenario


class InSyncTest(SyncFlowTestCase):
    """Two identical trees."""

    def test_identical_trees_report_no_changes(self) -> None:
        """A tree exported and reimported must diff as unchanged."""
        scenario = self.make_scenario()
        result = scenario.run()
        self.assertEqual(result.session.changes, [])
        self.assertIs(result.final_state, State.DONE)

    def test_confirmation_stage_is_skipped(self) -> None:
        """With nothing to confirm, the flow bypasses the review pane."""
        scenario = self.make_scenario()
        result = scenario.run()
        self.assertNotIn(State.REVIEW, result.states)
        self.assertNotIn(State.APPLYING, result.states)

    def test_nothing_is_sent_to_the_server(self) -> None:
        """An in-sync run must not post a transaction."""
        scenario = self.make_scenario()
        scenario.run()
        self.assertEqual(scenario.server.committed, [])

    def test_a_run_with_nothing_to_do_goes_straight_to_the_result(self) -> None:
        """No pane may be shown with nothing on it but an Apply button."""
        scenario = self.make_scenario()
        result = scenario.run()
        self.assertNotIn(State.REVIEW, result.states)
        self.assertEqual(
            result.states, [State.CONNECTING, State.COMPARING, State.DONE]
        )


class BidirectionalSyncTest(SyncFlowTestCase):
    """Changes made on one side only, propagating to the other."""

    def test_local_edit_reaches_the_server(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        result = scenario.run()
        self.assertEqual(result.change_ids(C_UPD_LOC), {"I0001"})
        self.assertEqual(scenario.remote.surname("I0001"), "Müller")

    def test_remote_edit_reaches_the_local_tree(self) -> None:
        scenario = self.make_scenario()
        scenario.remote.edit_person("I0001", surname="Mueller", changed_at=T2)
        result = scenario.run()
        self.assertEqual(result.change_ids(C_UPD_REM), {"I0001"})
        self.assertEqual(scenario.local.surname("I0001"), "Mueller")

    def test_local_addition_reaches_the_server(self) -> None:
        scenario = self.make_scenario()
        scenario.local.add_person("I9001", surname="Neu", changed_at=T2)
        result = scenario.run()
        self.assertEqual(result.change_ids(C_ADD_LOC), {"I9001"})
        self.assertIn("I9001", scenario.remote.person_ids())

    def test_remote_addition_reaches_the_local_tree(self) -> None:
        scenario = self.make_scenario()
        scenario.remote.add_person("I9002", surname="Neuer", changed_at=T2)
        result = scenario.run()
        self.assertEqual(result.change_ids(C_ADD_REM), {"I9002"})
        self.assertIn("I9002", scenario.local.person_ids())

    def test_local_deletion_reaches_the_server(self) -> None:
        scenario = self.make_scenario()
        scenario.local.delete_person("I0002")
        result = scenario.run()
        self.assertEqual(result.change_ids(C_DEL_LOC), {"I0002"})
        self.assertNotIn("I0002", scenario.remote.person_ids())

    def test_remote_deletion_reaches_the_local_tree(self) -> None:
        scenario = self.make_scenario()
        scenario.remote.delete_person("I0002")
        result = scenario.run()
        self.assertEqual(result.change_ids(C_DEL_REM), {"I0002"})
        self.assertNotIn("I0002", scenario.local.person_ids())

    def test_edits_on_both_sides_are_flagged_as_simultaneous(self) -> None:
        """Competing edits to one object are reported as simultaneous."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.remote.edit_person("I0001", surname="Mueller", changed_at=T3)
        result = scenario.run()
        self.assertEqual(result.change_ids(C_UPD_BOTH), {"I0001"})

    def test_independent_changes_on_both_sides_both_propagate(self) -> None:
        """Each side's change lands on the other in a single run."""
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.remote.add_person("I9003", surname="Neu", changed_at=T2)
        scenario.run()
        self.assertEqual(scenario.remote.surname("I0001"), "Müller")
        self.assertIn("I9003", scenario.local.person_ids())


class SyncModeTest(SyncFlowTestCase):
    """The four sync modes resolve the same divergence differently."""

    def diverged(self) -> SyncScenario:
        """Return a scenario where each side added a distinct person."""
        scenario = self.make_scenario()
        scenario.local.add_person("I9100", surname="LocalOnly", changed_at=T2)
        scenario.remote.add_person("I9200", surname="RemoteOnly", changed_at=T2)
        return scenario

    def test_bidirectional_keeps_both_additions(self) -> None:
        scenario = self.diverged()
        scenario.run(mode=MODE_BIDIRECTIONAL)
        for side in (scenario.local, scenario.remote):
            self.assertIn("I9100", side.person_ids())
            self.assertIn("I9200", side.person_ids())

    def test_reset_to_local_makes_the_server_match_the_local_tree(self) -> None:
        scenario = self.diverged()
        scenario.run(mode=MODE_RESET_TO_LOCAL)
        self.assertIn("I9100", scenario.remote.person_ids())
        self.assertNotIn("I9200", scenario.remote.person_ids())
        self.assertNotIn("I9200", scenario.local.person_ids())

    def test_reset_to_remote_makes_the_local_tree_match_the_server(self) -> None:
        scenario = self.diverged()
        scenario.run(mode=MODE_RESET_TO_REMOTE)
        self.assertIn("I9200", scenario.local.person_ids())
        self.assertNotIn("I9100", scenario.local.person_ids())
        self.assertNotIn("I9100", scenario.remote.person_ids())

    def test_an_unknown_mode_is_rejected(self) -> None:
        """Modes are a closed set; an unknown one must not sync silently."""
        scenario = self.make_scenario()
        scenario.local.delete_person("I0002")
        result = scenario.run(mode=99)
        self.assertIs(result.final_state, State.FAILED)


class MediaFileTest(SyncFlowTestCase):
    """Media files, which sync separately from object data."""

    def test_file_missing_locally_is_downloaded(self) -> None:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        handle = scenario.local.add_media(
            "O0001", "photo.jpg", changed_at=T0, on_disk=False
        )
        scenario.share()
        scenario.server.media_files[handle] = b"server image bytes"

        result = scenario.run()

        self.assertIs(result.final_state, State.DONE)
        self.assertEqual(result.session.downloaded, {"O0001": True})
        media = scenario.db1.get_media_from_handle(handle)
        local_path = os.path.join(scenario.local_media_dir, media.get_path())
        self.assertTrue(os.path.exists(local_path))
        with open(local_path, "rb") as fobj:
            self.assertEqual(fobj.read(), b"server image bytes")

    def test_file_missing_remotely_is_uploaded(self) -> None:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        handle = scenario.local.add_media(
            "O0002", "portrait.jpg", content=b"local bytes", changed_at=T0
        )
        scenario.share()
        self.assertNotIn(handle, scenario.server.media_files)

        result = scenario.run()

        self.assertEqual(result.session.uploaded, {"O0002": True})
        self.assertEqual(scenario.server.media_files[handle], b"local bytes")

    def test_the_review_knows_what_will_be_transferred(self) -> None:
        """The media scan runs before the review, not after the apply, so the
        checkbox can state the counts rather than promising the unknown."""
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.local.add_media("O0010", "up.jpg", changed_at=T0)
        scenario.share()

        session = scenario.make_session()
        session.submit_credentials(URL, USERNAME, "secret")

        self.assertIs(session.state, State.REVIEW)
        self.assertEqual([gid for gid, _h in session.missing_remote], ["O0010"])

    def test_media_arriving_with_the_sync_is_still_transferred(self) -> None:
        """A media object added by the sync has no file on the receiving side,
        which the scan taken before the review cannot have seen."""
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.share()
        handle = scenario.remote.add_media("O0011", "new.jpg", changed_at=T2)
        scenario.server.media_files[handle] = b"server image bytes"

        result = scenario.run()

        self.assertIs(result.final_state, State.DONE)
        self.assertEqual(result.session.downloaded, {"O0011": True})
        media = scenario.db1.get_media_from_handle(handle)
        local_path = os.path.join(scenario.local_media_dir, media.get_path())
        with open(local_path, "rb") as fobj:
            self.assertEqual(fobj.read(), b"server image bytes")

    def test_a_run_touching_no_media_object_scans_only_once(self) -> None:
        """The second scan exists for the case above; making every run pay for
        it would be a round trip for nothing."""
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.seed_person("I0001", surname="Doe", changed_at=T0)
        scenario.share()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)

        scenario.run()

        self.assertEqual(scenario.server.calls.count("get_missing_files"), 1)

    def test_transfer_stage_is_skipped_when_all_files_are_present(self) -> None:
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        handle = scenario.local.add_media("O0003", "ok.jpg", changed_at=T0)
        scenario.share()
        scenario.server.media_files[handle] = b"fake image bytes"

        result = scenario.run()

        self.assertNotIn(State.TRANSFERRING, result.states)
        self.assertIs(result.final_state, State.DONE)

    def test_leaving_the_review_unanswered_transfers_nothing(self) -> None:
        """Until the user confirms, the run must neither advance nor fail."""
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.local.add_media("O0004", "skipped.jpg", changed_at=T0)
        scenario.share()

        result = scenario.run(confirm=False)

        self.assertIs(result.final_state, State.REVIEW)
        self.assertEqual(scenario.server.media_files, {})

    def test_unchecking_the_media_box_skips_the_transfer(self) -> None:
        """The box is the only control over media now that the second
        confirmation page is gone, so it has to actually govern."""
        scenario = SyncScenario()
        self.addCleanup(scenario.close)
        scenario.local.add_media("O0005", "declined.jpg", changed_at=T0)
        scenario.share()

        result = scenario.run(transfer_media=False)

        self.assertIs(result.final_state, State.DONE)
        self.assertNotIn(State.TRANSFERRING, result.states)
        self.assertEqual(scenario.server.media_files, {})


class TimestampTest(SyncFlowTestCase):
    """The last-sync timestamp, which drives every later diff."""

    def test_successful_run_records_the_sync_time(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        scenario.clock.time = 1_700_000_500.0

        scenario.run()

        self.assertEqual(scenario.credentials.get_timestamp(URL, USERNAME), 1_700_000_500.0)

    def test_in_sync_run_also_records_the_sync_time(self) -> None:
        """Finding no differences still counts as a successful sync."""
        scenario = self.make_scenario()
        scenario.clock.time = 1_700_000_900.0

        scenario.run()

        self.assertEqual(
            scenario.credentials.get_timestamp(URL, USERNAME), 1_700_000_900.0
        )

    def test_each_server_keeps_its_own_baseline(self) -> None:
        """Syncing elsewhere must not disturb this server's baseline.

        The baseline used to be a single value that a changed URL reset, so
        alternating between two servers discarded it every time and made every
        run after a switch a full "modified in both" comparison.
        """
        scenario = self.make_scenario()
        scenario.credentials.timestamps[(URL, USERNAME)] = T3
        scenario.run(url="https://elsewhere.example/api")
        self.assertEqual(scenario.credentials.get_timestamp(URL, USERNAME), T3)


class ProgressTest(SyncFlowTestCase):
    """Progress and status reporting reach the listener."""

    def test_applying_changes_reports_api_progress(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        result = scenario.run()
        api_progress = [f for kind, f in result.progress if kind == "api"]
        self.assertTrue(api_progress)
        self.assertEqual(api_progress[-1], 1.0)

    def test_comparison_reports_fetching_then_comparing(self) -> None:
        scenario = self.make_scenario()
        result = scenario.run()
        self.assertEqual(
            [s for s in result.statuses if s in (STATUS_FETCHING, STATUS_COMPARING)],
            [STATUS_FETCHING, STATUS_COMPARING],
        )

    def test_local_commit_is_reported(self) -> None:
        scenario = self.make_scenario()
        scenario.remote.edit_person("I0001", surname="Mueller", changed_at=T2)
        result = scenario.run()
        self.assertIn(STATUS_LOCAL_APPLIED, result.statuses)

    def test_remote_only_changes_do_not_report_a_local_commit(self) -> None:
        scenario = self.make_scenario()
        scenario.local.edit_person("I0001", surname="Müller", changed_at=T2)
        result = scenario.run()
        self.assertNotIn(STATUS_LOCAL_APPLIED, result.statuses)


if __name__ == "__main__":
    unittest.main()
