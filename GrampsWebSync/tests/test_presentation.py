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

"""Unit tests for :mod:`presentation`, the interface's non-GTK half.

Constructs no widgets, so no display is needed.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import presentation
from adapters import KeyringUnavailable
from const import (
    A_ADD_LOC,
    A_ADD_REM,
    A_DEL_LOC,
    A_DEL_REM,
    A_MRG_REM,
    A_UPD_REM,
    MIN_API_VERSION_TEXT,
)
from gramps.gen.lib import Name, Person, Surname, Tag
from presentation import (
    LOCAL,
    REMOTE,
    VERB_ADD,
    VERB_MERGE,
    VERB_UPDATE,
    build_review,
    context_lines,
    deletion_warning,
    describe_object,
    error_message,
    format_last_synced,
    is_insecure,
    keyring_message,
    object_id,
    outcome_summary,
    sanitize_url,
)
from session import ErrorKind, State


def person(gramps_id: str, first: str = "John", last: str = "Smith") -> Person:
    """Build a person carrying a primary name, for description tests."""
    obj = Person()
    obj.set_gramps_id(gramps_id)
    name = Name()
    name.set_first_name(first)
    surname = Surname()
    surname.set_surname(last)
    name.add_surname(surname)
    obj.set_primary_name(name)
    return obj


def action(kind: str, obj=None, obj2=None, obj_type: str = "Person"):
    """Build one action tuple in the shape :func:`build_review` consumes."""
    return (kind, "handle", obj_type, obj, obj2)


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

    def test_a_failed_server_task_reports_what_the_server_said(self) -> None:
        """This used to render a stringified status dict plus advice to check
        the connection, which was neither true nor actionable."""
        message = error_message(ErrorKind.SERVER_TASK_FAILED, "disk full")
        self.assertIn("disk full", message)
        self.assertNotIn("connection", message.lower())

    def test_an_outdated_server_is_told_both_versions(self) -> None:
        message = error_message(ErrorKind.SERVER_TOO_OLD, "2.4.1")
        self.assertIn("2.4.1", message)
        self.assertIn(MIN_API_VERSION_TEXT, message)

    def test_the_two_version_bounds_advise_opposite_remedies(self) -> None:
        """Too old means update the server. Too new means move to a newer
        Gramps: an API major pairs with a Gramps release line, so no build of
        this addon will ever speak the next one. Sending someone after the
        wrong one has them hunting for something that does not exist."""
        too_old = error_message(ErrorKind.SERVER_TOO_OLD, "1.0.0")
        too_new = error_message(ErrorKind.SERVER_TOO_NEW, "9.0.0")
        self.assertIn("update the server", too_old.lower())
        self.assertIn("newer version of gramps", too_new.lower())
        self.assertNotIn("update the server", too_new.lower())
        self.assertNotIn("update the addon", too_new.lower())

    def test_the_version_found_is_named_at_both_ends(self) -> None:
        self.assertIn("1.0.0", error_message(ErrorKind.SERVER_TOO_OLD, "1.0.0"))
        self.assertIn("9.0.0", error_message(ErrorKind.SERVER_TOO_NEW, "9.0.0"))

    def test_a_server_reporting_no_version_still_gets_a_message(self) -> None:
        """The detail is empty in that case, so the general branch must cope."""
        message = error_message(ErrorKind.SERVER_TOO_OLD)
        self.assertTrue(message.strip())
        self.assertIn(MIN_API_VERSION_TEXT, message)


class KeyringMessageTest(unittest.TestCase):
    """An unusable keyring is reported, and under snap it is fixable."""

    def test_the_snap_command_is_included_when_there_is_one(self) -> None:
        problem = KeyringUnavailable(
            "denied", snap_command="snap connect gramps:password-manager-service"
        )
        self.assertIn("snap connect gramps", keyring_message(problem))

    def test_elsewhere_the_message_says_what_to_expect_instead(self) -> None:
        message = keyring_message(KeyringUnavailable("no backend"))
        self.assertNotIn("snap", message.lower())
        self.assertTrue(message.strip())


class UrlTest(unittest.TestCase):
    """Completing and judging what the user typed into the URL entry."""

    def test_a_bare_host_gets_https(self) -> None:
        self.assertEqual(
            sanitize_url("example.org/api"), "https://example.org/api"
        )

    def test_surrounding_whitespace_is_dropped(self) -> None:
        self.assertEqual(sanitize_url("  example.org  "), "https://example.org")

    def test_an_explicit_scheme_is_left_alone(self) -> None:
        """Including http: the user is warned, not overruled."""
        self.assertEqual(sanitize_url("http://localhost:5000"), "http://localhost:5000")
        self.assertEqual(sanitize_url("https://example.org"), "https://example.org")

    def test_an_empty_entry_stays_empty(self) -> None:
        """Otherwise the entry would fill itself in with a bare scheme."""
        self.assertEqual(sanitize_url("   "), "")

    def test_only_http_counts_as_insecure(self) -> None:
        self.assertTrue(is_insecure("http://example.org"))
        self.assertFalse(is_insecure("https://example.org"))
        self.assertFalse(is_insecure("example.org"))


class DescribeObjectTest(unittest.TestCase):
    """Rows say what an object is, not only that one exists."""

    def test_a_person_is_described_by_name(self) -> None:
        name = describe_object(person("I0001"), "Person")
        self.assertIn("Smith", name)
        self.assertIn("John", name)

    def test_a_tag_is_described_by_its_name_and_has_no_id(self) -> None:
        """Tags carry no Gramps ID, so the ID column must stay empty for them."""
        tag = Tag()
        tag.set_name("Needs sources")
        self.assertEqual(describe_object(tag, "Tag"), "Needs sources")
        self.assertEqual(object_id(tag, "Tag"), "")

    def test_a_class_needing_a_database_degrades_rather_than_raising(self) -> None:
        """Objects only the remote tree has may arrive without one."""
        self.assertEqual(describe_object(Person(), "Family"), "")

    def test_a_missing_object_is_not_an_error(self) -> None:
        self.assertEqual(describe_object(None, "Person"), "")


class ReviewModelTest(unittest.TestCase):
    """Actions are grouped by the database they change, not by what differs."""

    def test_actions_are_filed_under_their_destination(self) -> None:
        model = build_review(
            [
                action(A_ADD_LOC, obj2=person("I0001")),
                action(A_UPD_REM, obj=person("I0002")),
            ]
        )
        self.assertEqual([d.where for d in model.destinations], [LOCAL, REMOTE])
        self.assertEqual(model.destinations[0].groups[0].verb, VERB_ADD)
        self.assertEqual(model.destinations[1].groups[0].verb, VERB_UPDATE)

    def test_a_merge_appears_under_both_destinations(self) -> None:
        """It writes the combined object to each, so reporting it once would
        understate what happens to one of the trees."""
        model = build_review([action(A_MRG_REM, obj=person("I0001"))])
        self.assertEqual([d.where for d in model.destinations], [LOCAL, REMOTE])
        for destination in model.destinations:
            self.assertEqual(destination.groups[0].verb, VERB_MERGE)
            self.assertEqual(destination.count, 1)

    def test_a_destination_nothing_happens_to_is_left_out(self) -> None:
        model = build_review([action(A_ADD_REM, obj=person("I0001"))])
        self.assertEqual([d.where for d in model.destinations], [REMOTE])

    def test_deletions_are_counted_per_side(self) -> None:
        model = build_review(
            [
                action(A_DEL_LOC, obj2=person("I0001")),
                action(A_DEL_REM, obj=person("I0002")),
                action(A_DEL_REM, obj=person("I0003")),
            ]
        )
        self.assertEqual(model.local_deletions, 1)
        self.assertEqual(model.remote_deletions, 2)
        self.assertTrue(model.deletes)

    def test_rows_are_sorted_so_the_list_does_not_reshuffle(self) -> None:
        """The actions arrive in dictionary order, which is not stable enough
        to show the same user the same list twice."""
        model = build_review(
            [
                action(A_ADD_REM, obj=person("I0003", last="Zeta")),
                action(A_ADD_REM, obj=person("I0001", last="Alpha")),
                action(A_ADD_REM, obj=person("I0002", last="Mu")),
            ]
        )
        names = [row.name for row in model.destinations[0].groups[0].rows]
        self.assertEqual(names, sorted(names))

    def test_an_unknown_action_is_skipped_rather_than_crashing_the_pane(self) -> None:
        model = build_review([action("no_such_action", obj=person("I0001"))])
        self.assertEqual(model.destinations, ())

    def test_no_actions_produce_an_empty_model(self) -> None:
        model = build_review([])
        self.assertEqual(model.destinations, ())
        self.assertFalse(model.deletes)


class DeletionWarningTest(unittest.TestCase):
    """What will be removed is stated before it happens."""

    def test_nothing_deleted_means_no_warning(self) -> None:
        model = build_review([action(A_ADD_REM, obj=person("I0001"))])
        self.assertEqual(deletion_warning(model), "")

    def test_both_sides_are_named_when_both_lose_objects(self) -> None:
        model = build_review(
            [
                action(A_DEL_LOC, obj2=person("I0001")),
                action(A_DEL_REM, obj=person("I0002")),
            ]
        )
        warning = deletion_warning(model)
        self.assertIn("computer", warning)
        self.assertIn("server", warning)

    def test_a_bidirectional_run_that_deletes_is_warned_about_too(self) -> None:
        """The warning is derived from the actions, not from the mode, because
        propagating a deletion destroys data just as surely as a reset does."""
        model = build_review([action(A_DEL_REM, obj=person("I0001"))])
        self.assertTrue(deletion_warning(model))


class OutcomeSummaryTest(unittest.TestCase):
    """The final report covers both databases and the media files."""

    @staticmethod
    def session(**kwargs):
        """Build a stand-in exposing what :func:`outcome_summary` reads."""
        defaults = {
            "actions": [],
            "downloaded": {},
            "uploaded": {},
            "missing_both": [],
            "error": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_object_changes_are_reported_not_only_media(self) -> None:
        """A run applying hundreds of changes and no media used to report
        "Media files are in sync." and nothing else."""
        summary = outcome_summary(self.session(actions=[1, 2, 3]))
        self.assertIn("3", summary)

    def test_an_untouched_pair_of_trees_says_so(self) -> None:
        """The commonest outcome of all, and the one that used to be described
        purely in terms of media files."""
        summary = outcome_summary(self.session())
        self.assertIn("trees", summary.lower())

    def test_the_trees_are_reported_before_the_media(self) -> None:
        """Whatever else happened, the databases are what the user came for."""
        summary = outcome_summary(self.session())
        self.assertLess(
            summary.lower().index("trees"), summary.lower().index("media")
        )

    def test_a_media_only_run_still_reports_the_trees(self) -> None:
        summary = outcome_summary(self.session(uploaded={"O1": True}))
        self.assertIn("trees", summary.lower())
        self.assertIn("1", summary)

    def test_partial_progress_survives_a_failure(self) -> None:
        """A connection lost after two of three uploads must still report the
        two, rather than showing the error alone."""
        summary = outcome_summary(
            self.session(
                error=object(),
                uploaded={"O1": True, "O2": True, "O3": False},
            )
        )
        self.assertIn("2", summary)
        self.assertIn("1", summary)

    def test_files_missing_on_both_sides_are_called_out(self) -> None:
        summary = outcome_summary(self.session(missing_both=[("O1", "h1")]))
        self.assertIn("both", summary.lower())

    def test_a_failure_does_not_claim_media_are_in_sync(self) -> None:
        """Nothing was checked, so asserting it would be a guess."""
        summary = outcome_summary(self.session(error=object()))
        self.assertNotIn("in sync", summary)


class ContextLinesTest(unittest.TestCase):
    """The strip has to answer "which tree am I about to write to?"."""

    def test_the_tree_name_becomes_the_heading_once_known(self) -> None:
        """It is the only thing that distinguishes two trees on a hosted
        deployment, where the address is shared and only the account differs."""
        title, subtitle = context_lines(
            "https://hub.example/api", "alice", "Smith Family", "Last synced today"
        )
        self.assertEqual(title, "Smith Family")
        self.assertIn("alice", subtitle)
        self.assertIn("hub.example", subtitle)
        self.assertIn("Last synced today", subtitle)

    def test_before_connecting_the_account_leads(self) -> None:
        """The server has not said what it calls its tree yet."""
        title, subtitle = context_lines(
            "https://hub.example/api", "alice", "", "Never synced"
        )
        self.assertIn("alice", title)
        self.assertIn("hub.example", title)
        self.assertEqual(subtitle, "Never synced")

    def test_a_named_tree_never_synced_still_says_where_it_is(self) -> None:
        title, subtitle = context_lines(
            "https://hub.example/api", "alice", "Smith Family", ""
        )
        self.assertEqual(title, "Smith Family")
        self.assertIn("alice", subtitle)

    def test_nothing_configured_says_so(self) -> None:
        title, subtitle = context_lines("", "", "", "Never synced")
        self.assertTrue(title.strip())
        self.assertEqual(subtitle, "")

    def test_a_half_configured_server_is_not_presented_as_real(self) -> None:
        self.assertEqual(
            context_lines("https://hub.example/api", ""), context_lines("", "")
        )


class LastSyncedTest(unittest.TestCase):
    """The context strip says how current the baseline is."""

    def test_never_synced_is_said_plainly(self) -> None:
        self.assertTrue(format_last_synced(0).strip())

    def test_recent_and_distant_syncs_read_differently(self) -> None:
        now = 1_700_000_000.0
        recent = format_last_synced(now - 120, now)
        older = format_last_synced(now - 3 * 3600, now)
        self.assertNotEqual(recent, older)
        self.assertIn("2", recent)
        self.assertIn("3", older)

    def test_a_baseline_in_the_future_does_not_produce_nonsense(self) -> None:
        """Clock skew between the two machines is entirely possible."""
        now = 1_700_000_000.0
        self.assertTrue(format_last_synced(now + 5000, now).strip())


class PhaseLabelTest(unittest.TestCase):
    """Every phase the working pane lists must have a name."""

    def test_each_working_state_is_named(self) -> None:
        from session import WORKING_STATES

        for state in WORKING_STATES:
            with self.subTest(state=state.name):
                self.assertTrue(presentation.state_label(state).strip())

    def test_a_state_that_is_not_a_phase_has_no_label(self) -> None:
        self.assertEqual(presentation.state_label(State.REVIEW), "")


if __name__ == "__main__":
    unittest.main()
