#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 Douglas S. Blank <doug.blank@gmail.com>
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
Unit tests for grampswebapidb.WebApiDB: the sync/write-through logic.

WebApiDB subclasses the stock SQLite DBAPI backend, but these tests never
open a real database file -- SQLite's own commit_*/remove_* methods and
transaction machinery are stubbed out (WebApiDB.__new__() plus per-test
attribute overrides), the same pattern SharedPostgreSQL/tests/
test_initialize.py uses to test _create_settings() without a real Postgres
connection. This isolates exactly the logic this addon adds:

  - transaction_to_json(): local DbTxn -> flat change-list payload
  - _apply_change(): one server change -> a commit_*/remove_* call
  - _sync_from_server(): pagination + sync_last_time bookkeeping
  - transaction_commit(): push-after-commit, ordering, and error swallowing

Run with::

    python3 -m unittest GrampsWebApiDb.tests.test_grampswebapidb -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import copy
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from unittest import mock

# -------------------------------------------------------------------------
#
# Make the addon importable the way Gramps loads it: its own directory on
# sys.path (grampswebapidb.py does a bare ``from webapi_client import
# WebApiHandler`` -- see CLAUDE.md Testing conventions).
#
# -------------------------------------------------------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import gramps
except ImportError as _err:
    raise unittest.SkipTest("gramps package not available: %s" % _err)

from gramps.gen.db import DbTxn
from gramps.gen.db.dbconst import REFERENCE_KEY, TXNADD, TXNDEL, TXNUPD
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Attribute, Person, Tag
from gramps.gen.lib.json_utils import data_to_object, object_to_data, remove_object

from GrampsWebApiDb import grampswebapidb
from GrampsWebApiDb.grampswebapidb import (
    WebApiDB,
    WebApiPushConflict,
    transaction_to_json,
)

# grampswebapidb.py imports webapi_client with a bare `from webapi_client
# import ...` (see CLAUDE.md Testing conventions -- this addon has no
# __init__.py, so Gramps and tests alike add its own directory to
# sys.path). That makes "webapi_client" and "GrampsWebApiDb.webapi_client"
# two distinct sys.modules entries for the same file, so an exception
# class must come from whichever import path the code under test actually
# uses -- grampswebapidb.WebApiPushConflict here, not a fresh
# `from GrampsWebApiDb.webapi_client import WebApiPushConflict`, or
# `except WebApiPushConflict` in transaction_commit() won't match it.


# -------------------------------------------------------------------------
#
# Test helpers
#
# -------------------------------------------------------------------------
def person_data(handle="H1", gramps_id="I0001"):
    """A real Person's data-dict, the shape new_data/old_data actually take."""
    person = Person()
    person.set_handle(handle)
    person.set_gramps_id(gramps_id)
    return object_to_data(person)


class FakeTransaction:
    """Duck-types the bit of DbTxn that transaction_to_json() reads:
    get_recnos()/get_record(). Avoids needing a real commitdb/pickle round
    trip just to test the flattening logic."""

    def __init__(self, records):
        # records: list of (key, action, handle, old_data, new_data)
        self._records = records

    def get_recnos(self, reverse=False):
        idx = range(len(self._records))
        return reversed(idx) if reverse else idx

    def get_record(self, recno):
        return self._records[recno]


def new_instance():
    """A WebApiDB that never touched a real SQLite file or server."""
    return WebApiDB.__new__(WebApiDB)


# -------------------------------------------------------------------------
#
# TestTransactionToJson
#
# -------------------------------------------------------------------------
class TestTransactionToJson(unittest.TestCase):
    def test_add_record_shape(self):
        new_data = person_data()
        trans = FakeTransaction([(0, TXNADD, "H1", None, new_data)])  # PERSON_KEY
        out = transaction_to_json(trans)
        self.assertEqual(len(out), 1)
        entry = out[0]
        self.assertEqual(entry["type"], "add")
        self.assertEqual(entry["handle"], "H1")
        self.assertEqual(entry["_class"], "Person")
        self.assertIsNone(entry["old"])
        self.assertNotIn("_object", entry["new"])

    def test_update_record_carries_old_and_new(self):
        old_data = person_data(gramps_id="I0001")
        new_data = person_data(gramps_id="I0002")
        trans = FakeTransaction([(0, TXNUPD, "H1", old_data, new_data)])
        out = transaction_to_json(trans)
        self.assertEqual(out[0]["type"], "update")
        self.assertNotIn("_object", out[0]["old"])
        self.assertNotIn("_object", out[0]["new"])

    def test_delete_record_has_no_new_data(self):
        old_data = person_data()
        trans = FakeTransaction([(0, TXNDEL, "H1", old_data, None)])
        out = transaction_to_json(trans)
        self.assertEqual(out[0]["type"], "delete")
        self.assertIsNone(out[0]["new"])
        self.assertIsNotNone(out[0]["old"])

    def test_reference_type_record_is_skipped(self):
        # REFERENCE_KEY has no entry in KEY_TO_CLASS_MAP -- see dbconst.py.
        trans = FakeTransaction([(REFERENCE_KEY, TXNADD, "H1", None, {})])
        self.assertEqual(transaction_to_json(trans), [])

    def test_multiple_records_preserve_order(self):
        trans = FakeTransaction(
            [
                (0, TXNADD, "H1", None, person_data("H1")),
                (0, TXNUPD, "H2", person_data("H2"), person_data("H2", "I0002")),
            ]
        )
        out = transaction_to_json(trans)
        self.assertEqual([e["handle"] for e in out], ["H1", "H2"])


# -------------------------------------------------------------------------
#
# TestApplyChange
#
# -------------------------------------------------------------------------
class TestApplyChange(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.commit_person = mock.MagicMock()
        self.db.remove_person = mock.MagicMock()
        self.trans = object()  # opaque; just forwarded

    def test_unrecognized_obj_class_is_ignored(self):
        change = {"obj_class": "NotAThing", "trans_type": TXNADD, "obj_handle": "H1"}
        applied = self.db._apply_change(change, self.trans)
        self.assertFalse(applied)
        self.db.commit_person.assert_not_called()
        self.db.remove_person.assert_not_called()

    def test_delete_calls_remove(self):
        change = {"obj_class": "Person", "trans_type": TXNDEL, "obj_handle": "H1"}
        applied = self.db._apply_change(change, self.trans)
        self.assertTrue(applied)
        self.db.remove_person.assert_called_once_with("H1", self.trans)
        self.db.commit_person.assert_not_called()

    def test_add_calls_commit_with_reconstructed_object(self):
        new_data = remove_object(person_data("H1", "I0001"))
        change = {
            "obj_class": "Person",
            "trans_type": TXNADD,
            "obj_handle": "H1",
            "new_data": new_data,
        }
        applied = self.db._apply_change(change, self.trans)
        self.assertTrue(applied)
        self.db.commit_person.assert_called_once()
        obj, trans = self.db.commit_person.call_args[0]
        self.assertIsInstance(obj, Person)
        self.assertEqual(obj.get_handle(), "H1")
        self.assertIs(trans, self.trans)

    def test_update_is_also_an_upsert(self):
        new_data = remove_object(person_data("H1", "I0002"))
        change = {
            "obj_class": "Person",
            "trans_type": TXNUPD,
            "obj_handle": "H1",
            "new_data": new_data,
        }
        applied = self.db._apply_change(change, self.trans)
        self.assertTrue(applied)
        self.db.commit_person.assert_called_once()
        self.db.remove_person.assert_not_called()


# -------------------------------------------------------------------------
#
# TestEmitChangeSignals
#
# -------------------------------------------------------------------------
class TestEmitChangeSignals(unittest.TestCase):
    """_emit_change_signals() reproduces the person-add/family-update/...
    signals a normal (non-batch) local commit would have emitted -- see
    _sync_from_server()'s batch=True DbTxn and the module docstring's note
    on why that otherwise leaves already-open views unaware anything
    changed."""

    def setUp(self):
        self.db = new_instance()
        self.db.emit = mock.MagicMock()

    def emitted(self):
        return {call.args[0]: call.args[1][0] for call in self.db.emit.call_args_list}

    def test_add_emits_person_add_with_handle(self):
        self.db._emit_change_signals({("Person", "H1"): TXNADD})
        self.assertEqual(self.emitted(), {"person-add": ["H1"]})

    def test_update_emits_dash_update(self):
        self.db._emit_change_signals({("Family", "F1"): TXNUPD})
        self.assertEqual(self.emitted(), {"family-update": ["F1"]})

    def test_delete_emits_dash_delete(self):
        self.db._emit_change_signals({("Event", "E1"): TXNDEL})
        self.assertEqual(self.emitted(), {"event-delete": ["E1"]})

    def test_unrecognized_obj_class_is_skipped(self):
        self.db._emit_change_signals({("NotAThing", "H1"): TXNADD})
        self.db.emit.assert_not_called()

    def test_same_class_and_trans_type_batched_into_one_call(self):
        self.db._emit_change_signals(
            {("Person", "H1"): TXNUPD, ("Person", "H2"): TXNUPD}
        )
        self.db.emit.assert_called_once()
        name, (handles,) = self.db.emit.call_args[0]
        self.assertEqual(name, "person-update")
        self.assertEqual(set(handles), {"H1", "H2"})

    def test_deletes_and_adds_emitted_before_updates(self):
        # Same ordering as DBAPI.transaction_commit()'s own signal loop.
        self.db._emit_change_signals(
            {("Person", "H1"): TXNUPD, ("Family", "F1"): TXNDEL}
        )
        names = [call.args[0] for call in self.db.emit.call_args_list]
        self.assertEqual(names, ["family-delete", "person-update"])


# -------------------------------------------------------------------------
#
# TestSyncFromServer
#
# -------------------------------------------------------------------------
class FakeDbTxn:
    """Stand-in for gramps.gen.db.DbTxn: a plain context manager, so
    _sync_from_server's pagination/bookkeeping can be tested without a
    real transaction_begin/transaction_commit or get_undodb()."""

    def __init__(self, msg, grampsdb, batch=False):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class TestSyncFromServer(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()
        # _sync_from_server() now emits change signals per page (see
        # TestEmitChangeSignals for that logic in isolation) -- emit()
        # itself needs Callback.__init__'s instance state, which
        # new_instance()'s bare __new__() never runs, so it's stubbed here
        # the same way commit_person/remove_person are stubbed elsewhere.
        self.db.emit = mock.MagicMock()
        self.metadata = {}
        self.db._get_metadata = lambda key, default=0: self.metadata.get(key, default)
        self.db._set_metadata = (
            lambda key, value, use_txn=True: self.metadata.__setitem__(key, value)
        )
        self.patcher = mock.patch.object(grampswebapidb, "DbTxn", FakeDbTxn)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        # Every existing test here predates the empty-changes-marker ->
        # full-resync fallback (see TestFullResyncTrigger below) and uses
        # "changes": [] purely as pagination/timestamp filler, not to
        # exercise that fallback -- stub it out so those tests keep
        # testing what they always tested.
        self.db._full_resync = mock.MagicMock()

    def test_syncing_flag_is_set_during_the_sync_and_cleared_after(self):
        # What stops _pump_main_loop()'s re-entrant timeout ticks from
        # starting a second sync underneath this one.
        seen = []
        self.db.web_client.get_transaction_history.side_effect = lambda **kwargs: (
            seen.append(self.db._syncing),
            ([], 0),
        )[1]
        self.db._sync_from_server()
        self.assertEqual(seen, [True])
        self.assertFalse(self.db._syncing)

    def test_syncing_flag_is_cleared_even_if_the_sync_raises(self):
        self.db.web_client.get_transaction_history.side_effect = OSError("down")
        with self.assertRaises(OSError):
            self.db._sync_from_server()
        self.assertFalse(self.db._syncing)

    def test_main_loop_is_pumped_between_pages(self):
        # A catch-up of any size would otherwise hold the main loop for
        # its whole duration -- long enough for the window manager to
        # offer to force-quit Gramps.
        full_page = [
            {"timestamp": float(i), "changes": []}
            for i in range(grampswebapidb.SYNC_PAGE_SIZE)
        ]
        short_page = [{"timestamp": 999.0, "changes": []}]
        self.db.web_client.get_transaction_history.side_effect = [
            (full_page, len(full_page) + 1),
            (short_page, 1),
        ]
        with mock.patch.object(grampswebapidb, "_pump_main_loop") as pump:
            self.db._sync_from_server()
        # Once after each page, plus once on the way out.
        self.assertEqual(pump.call_count, 3)

    def test_main_loop_is_pumped_even_when_nothing_came_back(self):
        # The routine poll: the loop breaks before its own pump, but the
        # round trip that found nothing still blocked the main loop.
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        with mock.patch.object(grampswebapidb, "_pump_main_loop") as pump:
            self.db._sync_from_server()
        self.assertEqual(pump.call_count, 1)

    def test_stops_after_short_page(self):
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        self.db.web_client.get_transaction_history.return_value = (
            [{"timestamp": 5.0, "changes": [change]}],
            1,
        )
        with mock.patch.object(self.db, "_apply_change", return_value=True) as apply:
            applied = self.db._sync_from_server()
        self.assertEqual(applied, 1)
        apply.assert_called_once_with(change, mock.ANY)
        self.db.web_client.get_transaction_history.assert_called_once()

    def test_pagination_continues_on_full_page(self):
        full_page = [
            {"timestamp": float(i), "changes": []}
            for i in range(grampswebapidb.SYNC_PAGE_SIZE)
        ]
        short_page = [{"timestamp": 999.0, "changes": []}]
        self.db.web_client.get_transaction_history.side_effect = [
            (full_page, len(full_page) + 1),
            (short_page, 1),
        ]
        applied = self.db._sync_from_server()
        self.assertEqual(applied, 0)
        self.assertEqual(self.db.web_client.get_transaction_history.call_count, 2)
        calls = self.db.web_client.get_transaction_history.call_args_list
        self.assertEqual(calls[0].kwargs["page"], 1)
        self.assertEqual(calls[1].kwargs["page"], 2)

    def test_no_transactions_leaves_sync_time_unchanged(self):
        self.metadata["sync_last_time"] = 42.0
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        applied = self.db._sync_from_server()
        self.assertEqual(applied, 0)
        self.assertEqual(self.metadata["sync_last_time"], 42.0)

    def test_sync_last_time_advances_to_max_timestamp_seen(self):
        page = [
            {"timestamp": 10.0, "changes": []},
            {"timestamp": 30.0, "changes": []},
            {"timestamp": 20.0, "changes": []},
        ]
        self.db.web_client.get_transaction_history.return_value = (page, 3)
        self.db._sync_from_server()
        self.assertEqual(self.metadata["sync_last_time"], 30.0)

    def test_unrecognized_changes_are_not_counted(self):
        page = [
            {
                "timestamp": 1.0,
                "changes": [
                    {"obj_class": "Bogus", "trans_type": TXNADD, "obj_handle": "H1"}
                ],
            }
        ]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        applied = self.db._sync_from_server()
        self.assertEqual(applied, 0)

    def test_emits_a_signal_per_applied_change(self):
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        self.db.web_client.get_transaction_history.return_value = (
            [{"timestamp": 5.0, "changes": [change]}],
            1,
        )
        with mock.patch.object(self.db, "_apply_change", return_value=True):
            self.db._sync_from_server()
        self.db.emit.assert_called_once_with("person-add", (["H1"],))

    def test_repeated_changes_to_one_handle_collapse_to_the_last(self):
        # Same handle, updated then deleted within one page/poll -- only
        # the net (delete) signal should fire, not both.
        page = [
            {
                "timestamp": 1.0,
                "changes": [
                    {"obj_class": "Person", "trans_type": TXNUPD, "obj_handle": "H1"}
                ],
            },
            {
                "timestamp": 2.0,
                "changes": [
                    {"obj_class": "Person", "trans_type": TXNDEL, "obj_handle": "H1"}
                ],
            },
        ]
        self.db.web_client.get_transaction_history.return_value = (page, 2)
        with mock.patch.object(self.db, "_apply_change", return_value=True):
            self.db._sync_from_server()
        self.db.emit.assert_called_once_with("person-delete", (["H1"],))

    def test_unrecognized_changes_emit_no_signal(self):
        page = [
            {
                "timestamp": 1.0,
                "changes": [
                    {"obj_class": "Bogus", "trans_type": TXNADD, "obj_handle": "H1"}
                ],
            }
        ]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        self.db._sync_from_server()
        self.db.emit.assert_not_called()

    def test_no_progress_callback_by_default(self):
        # _poll_tick()'s background call relies on this: no callback means
        # no attempt to report progress, so a periodic poll can't raise
        # trying to call None.
        page = [{"timestamp": 1.0, "changes": []}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        self.db._sync_from_server()  # must not raise

    def test_progress_reported_as_percent_of_total(self):
        page = [{"timestamp": 1.0, "changes": []}] * 25
        self.db.web_client.get_transaction_history.return_value = (page, 100)
        progress = mock.MagicMock()
        self.db._sync_from_server(progress_callback=progress)
        progress.assert_called_once_with(25)

    def test_progress_accumulates_and_caps_at_100_across_pages(self):
        full_page = [
            {"timestamp": float(i), "changes": []}
            for i in range(grampswebapidb.SYNC_PAGE_SIZE)
        ]
        short_page = [{"timestamp": 999.0, "changes": []}]
        total = grampswebapidb.SYNC_PAGE_SIZE  # short page pushes seen > total
        self.db.web_client.get_transaction_history.side_effect = [
            (full_page, total),
            (short_page, total),
        ]
        progress = mock.MagicMock()
        self.db._sync_from_server(progress_callback=progress)
        self.assertEqual([call.args[0] for call in progress.call_args_list], [100, 100])

    def test_no_progress_call_when_total_is_zero(self):
        # An empty-history sync (a brand new server-side tree, or nothing
        # new since last sync) has no meaningful denominator to report
        # against -- guards a ZeroDivisionError, not just noise.
        page = [{"timestamp": 1.0, "changes": []}]
        self.db.web_client.get_transaction_history.return_value = (page, 0)
        progress = mock.MagicMock()
        self.db._sync_from_server(progress_callback=progress)
        progress.assert_not_called()

    def test_progress_callback_passed_through_to_full_resync(self):
        page = [{"timestamp": 1.0, "changes": []}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        progress = mock.MagicMock()
        self.db._sync_from_server(progress_callback=progress)
        self.db._full_resync.assert_called_once_with(progress_callback=progress)

    def test_pulling_flag_is_set_during_replay_and_cleared_after(self):
        # _pulling tells transaction_begin() this batch DbTxn is a
        # server-pull replay, not a local bulk edit to reconstruct and push
        # back -- without it, every synced page would be echoed straight
        # back at the server. A leaked True would then silently disable
        # reconciliation for later genuine local batch operations.
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        self.db.web_client.get_transaction_history.return_value = (
            [{"timestamp": 5.0, "changes": [change]}],
            1,
        )
        seen = {}

        def check_flag(change, trans):
            seen["during"] = self.db._pulling
            return True

        with mock.patch.object(self.db, "_apply_change", side_effect=check_flag):
            self.db._sync_from_server()
        self.assertTrue(seen["during"])
        self.assertFalse(self.db._pulling)

    def test_pulling_flag_is_cleared_even_if_replay_raises(self):
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        self.db.web_client.get_transaction_history.return_value = (
            [{"timestamp": 5.0, "changes": [change]}],
            1,
        )
        with mock.patch.object(
            self.db, "_apply_change", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.db._sync_from_server()
        self.assertFalse(self.db._pulling)


# -------------------------------------------------------------------------
#
# TestFullResyncTrigger
#
# A batch=True commit (any bulk import/merge/tool run through
# gramps-web-api) leaves an empty "changes" list on its transaction
# row -- see the module docstring's note on trans.batch guards around
# trans.add(). _sync_from_server() can't replay what was never logged,
# so it falls back to _full_resync() whenever it sees one.
#
# -------------------------------------------------------------------------
class TestFullResyncTrigger(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()
        self.db.emit = mock.MagicMock()  # see TestSyncFromServer.setUp's note
        self.metadata = {}
        self.db._get_metadata = lambda key, default=0: self.metadata.get(key, default)
        self.db._set_metadata = (
            lambda key, value, use_txn=True: self.metadata.__setitem__(key, value)
        )
        self.db._full_resync = mock.MagicMock()
        self.patcher = mock.patch.object(grampswebapidb, "DbTxn", FakeDbTxn)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_empty_changes_transaction_triggers_full_resync(self):
        page = [{"timestamp": 1.0, "changes": []}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        self.db._sync_from_server()
        self.db._full_resync.assert_called_once_with(progress_callback=None)

    def test_normal_transactions_do_not_trigger_full_resync(self):
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        page = [{"timestamp": 1.0, "changes": [change]}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        with mock.patch.object(self.db, "_apply_change", return_value=True):
            self.db._sync_from_server()
        self.db._full_resync.assert_not_called()

    def test_marker_alongside_real_changes_still_applies_the_real_ones(self):
        # A marker transaction doesn't block replaying whatever *is*
        # describable elsewhere in the same page -- only the parts the
        # history feed genuinely has no record of need the fallback.
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        page = [
            {"timestamp": 1.0, "changes": []},
            {"timestamp": 2.0, "changes": [change]},
        ]
        self.db.web_client.get_transaction_history.return_value = (page, 2)
        with mock.patch.object(self.db, "_apply_change", return_value=True):
            applied = self.db._sync_from_server()
        self.assertEqual(applied, 1)
        self.db._full_resync.assert_called_once_with(progress_callback=None)

    def test_marker_still_advances_sync_last_time(self):
        page = [{"timestamp": 42.0, "changes": []}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        self.db._sync_from_server()
        self.assertEqual(self.metadata["sync_last_time"], 42.0)

    def test_short_mirror_triggers_full_resync(self):
        # A server whose tree was populated without gramps-web-api
        # recording history (demo.grampsweb.org: 4668 people, a history
        # holding only the edits made through the API) would otherwise
        # sync to a mirror holding just those, with nothing logged.
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        self.db.web_client.get_object_count.return_value = 26541
        with mock.patch.object(self.db, "get_total", return_value=1):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db._sync_from_server(verify_totals=True)
        self.db._full_resync.assert_called_once_with(progress_callback=None)

    def test_a_replayed_feed_that_still_falls_short_triggers_full_resync(self):
        # The case that made the empty-feed-only version of this check
        # useless: one API edit against a history-less server hands back a
        # transaction and advances the cursor, so the sync looks fine.
        change = {"obj_class": "Person", "trans_type": TXNADD, "obj_handle": "H1"}
        page = [{"timestamp": 1786645046.3, "changes": [change]}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        self.db.web_client.get_object_count.return_value = 26541
        with mock.patch.object(self.db, "_apply_change", return_value=True):
            with mock.patch.object(self.db, "get_total", return_value=1):
                with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                    applied = self.db._sync_from_server(verify_totals=True)
        self.assertEqual(applied, 1)
        self.assertEqual(self.metadata["sync_last_time"], 1786645046.3)
        self.db._full_resync.assert_called_once_with(progress_callback=None)

    def test_matching_totals_do_not_trigger_full_resync(self):
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        self.db.web_client.get_object_count.return_value = 26541
        with mock.patch.object(self.db, "get_total", return_value=26541):
            self.db._sync_from_server(verify_totals=True)
        self.db._full_resync.assert_not_called()

    def test_a_larger_local_total_is_left_alone(self):
        # An extra local object is either about to be pushed or something
        # the export would destroy -- not a shortfall to repair.
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        self.db.web_client.get_object_count.return_value = 10
        with mock.patch.object(self.db, "get_total", return_value=11):
            self.db._sync_from_server(verify_totals=True)
        self.db._full_resync.assert_not_called()

    def test_queued_pushes_suppress_the_total_check(self):
        # Local edits the server hasn't accepted yet: the counts are
        # legitimately out of step, and a rebuild would fight with work
        # still waiting to go the other way. _sync_from_server() drains
        # the queue on the way in, so what's left here is what the flush
        # couldn't place (a 429, a 5xx) -- hence the stubbed flush.
        self.metadata["pending_pushes"] = [{"payload": [], "undo": False}]
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        with mock.patch.object(self.db, "_flush_pending_pushes"), mock.patch.object(
            self.db, "get_total", return_value=0
        ) as get_total:
            self.db._sync_from_server(verify_totals=True)
        self.db._full_resync.assert_not_called()
        get_total.assert_not_called()
        self.db.web_client.get_object_count.assert_not_called()

    def test_poll_syncs_do_not_check_totals(self):
        # Only load() asks for the check -- a rebuild must never land in
        # the middle of a working session, and the poll shouldn't spend a
        # request per tick to find that out.
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        with mock.patch.object(self.db, "get_total", return_value=0) as get_total:
            self.db._sync_from_server()
        self.db._full_resync.assert_not_called()
        get_total.assert_not_called()
        self.db.web_client.get_object_count.assert_not_called()

    def test_total_check_forwards_the_progress_callback(self):
        callback = mock.MagicMock()
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        self.db.web_client.get_object_count.return_value = 1
        with mock.patch.object(self.db, "get_total", return_value=0):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db._sync_from_server(
                    progress_callback=callback, verify_totals=True
                )
        self.db._full_resync.assert_called_once_with(progress_callback=callback)


# -------------------------------------------------------------------------
#
# TestFullResync
#
# -------------------------------------------------------------------------
class TestFullResync(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()
        self.db.web_client.download_export.return_value = b"fake gramps xml bytes"
        self.db.emit = mock.MagicMock()  # see TestSyncFromServer.setUp's note
        # _full_resync() reports the rebuilt total at DEBUG; there's no
        # real dbapi connection behind these stubs to count.
        self.db.get_total = mock.MagicMock(return_value=0)
        self.db._set_metadata = mock.MagicMock()
        self.patcher = mock.patch.object(grampswebapidb, "DbTxn", FakeDbTxn)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_downloads_export_wipes_and_reimports(self):
        # get_<name>_handles/remove_<name> for every primary type, plus
        # importData itself, are all faked out -- this test is only
        # confirming the wiring (download -> wipe every type -> import
        # the downloaded file -> clean up the temp file), not any real
        # Gramps object storage.
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=["H1"]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())

        captured_path = {}

        def fake_import_data(database, filename, user):
            captured_path["path"] = filename
            self.assertTrue(os.path.exists(filename))
            with open(filename, "rb") as f:
                self.assertEqual(f.read(), b"fake gramps xml bytes")

        with mock.patch.object(grampswebapidb, "importData", fake_import_data):
            self.db._full_resync()

        self.db.web_client.download_export.assert_called_once_with(
            on_chunk=self.db._guarded_pump
        )
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            getattr(self.db, f"remove_{name}").assert_called_once_with("H1", mock.ANY)
        # The temp file is cleaned up after import, not left behind.
        self.assertFalse(os.path.exists(captured_path["path"]))
        # A successful reimport can't be described as specific add/update/
        # delete signals, so every view is told to reload wholesale instead
        # -- see request_rebuild() in gramps.gen.db.generic.
        emitted = [call.args[0] for call in self.db.emit.call_args_list]
        self.assertIn("person-rebuild", emitted)
        self.assertIn("family-rebuild", emitted)

    def test_failed_import_does_not_trigger_rebuild(self):
        # request_rebuild() sits after importData() in _full_resync(), not
        # in a finally -- a reimport that raised partway through left the
        # mirror in an unknown state, which is not something to tell every
        # view "reload, this is now correct" about.
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())

        def failing_import_data(database, filename, user):
            raise RuntimeError("boom")

        with mock.patch.object(grampswebapidb, "importData", failing_import_data):
            with self.assertRaises(RuntimeError):
                self.db._full_resync()

        self.db.emit.assert_not_called()

    def test_pulling_flag_is_set_during_the_rebuild_and_cleared_after(self):
        # _pulling suppresses the batch-commit reconciliation that would
        # otherwise try to push this whole wipe-and-reimport back at the
        # server as if it were a local bulk edit. It has to stay set across
        # importData() (which opens its own batch DbTxn internally), and it
        # has to be cleared afterwards -- a leaked True would silently
        # disable reconciliation for every later local batch operation in
        # the session.
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())
        seen = {}

        def check_flag(database, filename, user):
            seen["during_import"] = self.db._pulling

        with mock.patch.object(grampswebapidb, "importData", check_flag):
            self.db._full_resync()
        self.assertTrue(seen["during_import"])
        self.assertFalse(self.db._pulling)

    def test_pulling_flag_is_cleared_even_if_the_reimport_raises(self):
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())

        def failing_import_data(database, filename, user):
            raise RuntimeError("boom")

        with mock.patch.object(grampswebapidb, "importData", failing_import_data):
            with self.assertRaises(RuntimeError):
                self.db._full_resync()
        self.assertFalse(self.db._pulling)

    def test_no_progress_callback_by_default(self):
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())
        with mock.patch.object(grampswebapidb, "importData"):
            self.db._full_resync()  # must not raise

    def test_progress_bookends_the_download_and_reimport(self):
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())
        progress = mock.MagicMock()
        with mock.patch.object(grampswebapidb, "importData"):
            self.db._full_resync(progress_callback=progress)
        self.assertEqual([call.args[0] for call in progress.call_args_list], [0, 100])

    def test_progress_not_completed_if_import_fails(self):
        # The 100% marker means "the rebuild finished" -- a failed reimport
        # must not claim that, same reasoning as request_rebuild() above.
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())

        def failing_import_data(database, filename, user):
            raise RuntimeError("boom")

        progress = mock.MagicMock()
        with mock.patch.object(grampswebapidb, "importData", failing_import_data):
            with self.assertRaises(RuntimeError):
                self.db._full_resync(progress_callback=progress)
        progress.assert_called_once_with(0)

    def test_advances_sync_last_time_past_the_stuck_cursor(self):
        # A totals-shortfall rebuild (_mirror_is_short_of_the_server()) can
        # be triggered by a history feed whose very first page came back
        # empty, which leaves sync_last_time at whatever it started as (0
        # for a brand new mirror) instead of anywhere near "now". Left
        # alone, _push_payload()'s "resync from the server, then retry"
        # conflict recovery reuses that same stuck cursor and so can never
        # actually pick up what changed -- see the module's _full_resync()
        # docstring. Confirm the rebuild now leaves a fresh, roughly-"now"
        # cursor behind instead.
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())
        before = time.time()
        with mock.patch.object(grampswebapidb, "importData"):
            self.db._full_resync()
        after = time.time()
        self.db._set_metadata.assert_called_once_with("sync_last_time", mock.ANY)
        cutoff = self.db._set_metadata.call_args.args[1]
        self.assertGreaterEqual(cutoff, before)
        self.assertLessEqual(cutoff, after)

    def test_does_not_advance_sync_last_time_if_the_reimport_raises(self):
        # A rebuild that failed partway through left the mirror in an
        # unknown state (same reasoning as test_failed_import_does_not_
        # trigger_rebuild() above) -- advancing the cursor anyway would
        # tell the next sync "everything up to here is accounted for" for
        # a mirror that plainly isn't.
        for key, name in grampswebapidb.KEY_TO_NAME_MAP.items():
            if key not in grampswebapidb.CLASS_TO_KEY_MAP.values():
                continue
            setattr(self.db, f"get_{name}_handles", mock.MagicMock(return_value=[]))
            setattr(self.db, f"remove_{name}", mock.MagicMock())

        def failing_import_data(database, filename, user):
            raise RuntimeError("boom")

        with mock.patch.object(grampswebapidb, "importData", failing_import_data):
            with self.assertRaises(RuntimeError):
                self.db._full_resync()
        self.db._set_metadata.assert_not_called()


# -------------------------------------------------------------------------
#
# TestTransactionCommit
#
# -------------------------------------------------------------------------
class TestTransactionCommit(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()
        # A push that fails for a connectivity reason now persists the
        # payload via _set_metadata() for later retry (see
        # TestPendingPushQueue), so even the plain push tests here need
        # somewhere for that to land.
        self.metadata = {}
        self.db._get_metadata = lambda key, default=0: self.metadata.get(key, default)
        self.db._set_metadata = (
            lambda key, value, use_txn=True: self.metadata.__setitem__(key, value)
        )

    def test_no_local_changes_does_not_push(self):
        trans = FakeTransaction([])
        with mock.patch.object(grampswebapidb.SQLite, "transaction_commit"):
            self.db.transaction_commit(trans)
        self.db.web_client.push_transaction.assert_not_called()

    def test_local_changes_are_pushed(self):
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        with mock.patch.object(grampswebapidb.SQLite, "transaction_commit"):
            self.db.transaction_commit(trans)
        self.db.web_client.push_transaction.assert_called_once()
        payload = self.db.web_client.push_transaction.call_args[0][0]
        self.assertEqual(payload[0]["handle"], "H1")

    def test_payload_built_before_super_clears_records(self):
        # The base class's transaction_commit() clears the transaction's
        # records as its last step -- see the module docstring's "must run
        # before super()" note. Simulate that by having the (mocked) super
        # call wipe the fake transaction, and confirm the push still saw
        # the pre-clear data.
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])

        def clear_records(transaction):
            transaction._records = []

        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit", side_effect=clear_records
        ):
            self.db.transaction_commit(trans)
        payload = self.db.web_client.push_transaction.call_args[0][0]
        self.assertEqual(len(payload), 1)

    def test_push_failure_is_logged_not_raised(self):
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = HTTPError(
            "https://example.com/api/transactions/", 500, "boom", None, None
        )
        with mock.patch.object(grampswebapidb.SQLite, "transaction_commit"):
            with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
                self.db.transaction_commit(trans)  # must not raise

    def test_push_swallows_database_closed_mid_push(self):
        # The tree was closed (or switched away from) while push_transaction()'s
        # on_wait=self._guarded_pump had handed the main loop back -- see
        # TestGuardedPump. Not a failure: nothing left to push to.
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = grampswebapidb._DatabaseClosed
        with mock.patch.object(grampswebapidb.SQLite, "transaction_commit"):
            self.db.transaction_commit(trans)  # must not raise, must not log

    def test_conflict_triggers_resync_then_retry(self):
        # A WebApiPushConflict means the server rejected the whole batch
        # because something changed server-side since the local mirror's
        # snapshot -- the response is to do a full resync from the server
        # and then retry the local edit on top of that fresh data (see
        # _retry_after_conflict()), not to propagate the exception (the
        # local commit already happened).
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(
            self.db, "_resync_after_conflict"
        ) as resync, mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise
        # A full resync, not the incremental history feed or a totals
        # check -- neither can see a content-only change to an
        # already-known, bulk-imported object -- see the module
        # docstring and _resync_after_conflict().
        resync.assert_called_once_with()
        retry.assert_called_once_with(mock.ANY)
        payload = retry.call_args[0][0]
        self.assertEqual(payload[0]["handle"], "H1")

    def test_conflict_resync_failure_is_also_swallowed(self):
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(
            self.db,
            "_resync_after_conflict",
            side_effect=HTTPError(
                "https://example.com/api/exporters/gramps/file",
                500,
                "boom",
                None,
                None,
            ),
        ), mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise
        # A failed resync means the mirror still doesn't reflect the
        # server, so retrying the edit on top of it would be pointless.
        retry.assert_not_called()

    def test_retry_failure_is_queued_not_dropped(self):
        # A failure inside _retry_after_conflict() itself (its DbTxn body
        # never finished, so nothing committed locally -- see
        # _push_payload()'s handling of this) is a plain connectivity-
        # shaped problem, not a conflict, so the payload is queued for
        # later like any other push that couldn't be delivered (see
        # TestPendingPushQueue), not dropped.
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(self.db, "_resync_after_conflict"), mock.patch.object(
            self.db,
            "_retry_after_conflict",
            side_effect=OSError("network down"),
        ):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise
        self.assertEqual(len(self.metadata["pending_pushes"]), 1)
        self.assertEqual(
            self.metadata["pending_pushes"][0]["payload"][0]["handle"], "H1"
        )

    def test_conflict_resync_database_closed_is_also_swallowed(self):
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(
            self.db,
            "_resync_after_conflict",
            side_effect=grampswebapidb._DatabaseClosed,
        ), mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            self.db.transaction_commit(trans)  # must not raise, must not log
        retry.assert_not_called()

    def test_repeated_conflict_on_a_retry_is_not_retried_again(self):
        # is_retry=True marks a push that is itself _retry_after_conflict()'s
        # replay -- a second conflict on that replay must not recurse into
        # another retry, or a genuinely hot object could retry forever.
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(
            self.db, "_resync_after_conflict"
        ) as resync, mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db._push_payload(
                    transaction_to_json(trans), is_retry=True
                )  # must not raise
        resync.assert_called_once_with()
        retry.assert_not_called()

    def test_undo_conflict_is_not_retried(self):
        # Retrying an undo/redo against data that changed underneath it is
        # a murkier case (are we replaying the reversal, or the original
        # edit?) than retrying a plain commit -- see the module docstring.
        # Left as resync-and-drop, same as before this feature existed.
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(
            self.db, "_resync_after_conflict"
        ) as resync, mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db._push_payload(transaction_to_json(trans), undo=True)
        resync.assert_called_once_with()
        retry.assert_not_called()


# -------------------------------------------------------------------------
#
# TestResyncAfterConflict
#
# _resync_after_conflict() wraps _full_resync() -- not the incremental
# _sync_from_server() -- with the same _syncing bookkeeping
# _sync_from_server() and _sync_media_files() do around their own bodies,
# so a poll tick landing mid-resync skips its turn instead of starting a
# second sync underneath this one. See the module docstring and this
# method's own docstring for why a full resync, not the cheaper
# incremental feed or a totals check, is what a conflict retry needs.
#
# -------------------------------------------------------------------------
class TestResyncAfterConflict(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db._full_resync = mock.MagicMock()

    def test_delegates_to_full_resync(self):
        self.db._resync_after_conflict()
        self.db._full_resync.assert_called_once_with()

    def test_syncing_flag_is_set_during_and_cleared_after(self):
        seen = []
        self.db._full_resync.side_effect = lambda: seen.append(self.db._syncing)
        self.db._resync_after_conflict()
        self.assertEqual(seen, [True])
        self.assertFalse(self.db._syncing)

    def test_syncing_flag_is_cleared_even_if_the_resync_raises(self):
        self.db._full_resync.side_effect = OSError("down")
        with self.assertRaises(OSError):
            self.db._resync_after_conflict()
        self.assertFalse(self.db._syncing)


# -------------------------------------------------------------------------
#
# TestRetryAfterConflict
#
# -------------------------------------------------------------------------
class TestRetryAfterConflict(unittest.TestCase):
    """_retry_after_conflict() replays each payload entry as a fresh
    commit_<type>()/remove_<type>() call on top of the mirror _push_payload()
    just resynced -- see the module docstring's write-through section.
    DbTxn itself is stubbed out (a bare context-manager stand-in) so this
    isolates just the replay logic, the same way TestApplyChange isolates
    _apply_change() from a real transaction. _merge_or_overwrite() itself
    is covered separately by TestMergeOrOverwrite, so here it's mocked out
    to just confirm it's consulted (and with what) when the handle still
    exists after the resync."""

    def setUp(self):
        self.db = new_instance()
        self.db.commit_person = mock.MagicMock()
        self.db.remove_person = mock.MagicMock()
        self.db.has_person_handle = mock.MagicMock()
        self.db.get_person_from_handle = mock.MagicMock()
        self.db.web_client = mock.MagicMock()
        dbtxn_patch = mock.patch.object(grampswebapidb, "DbTxn")
        mock_dbtxn_class = dbtxn_patch.start()
        mock_dbtxn_class.return_value.__enter__.return_value = "TRANS"
        self.addCleanup(dbtxn_patch.stop)

    def test_add_to_a_handle_that_does_not_exist_is_committed_as_is(self):
        # A true add (or an update whose object was deleted server-side in
        # the same window) has nothing to merge into.
        self.db.has_person_handle.return_value = False
        new_data = remove_object(person_data("H1", "I0001"))
        payload = [
            {
                "type": "add",
                "handle": "H1",
                "_class": "Person",
                "old": None,
                "new": new_data,
            }
        ]
        self.db._retry_after_conflict(payload)
        self.db.get_person_from_handle.assert_not_called()
        self.db.commit_person.assert_called_once()
        obj, trans = self.db.commit_person.call_args[0]
        self.assertIsInstance(obj, Person)
        self.assertEqual(obj.get_handle(), "H1")
        self.assertEqual(trans, "TRANS")

    def test_update_of_a_still_present_handle_is_merged_with_the_current_object(self):
        self.db.has_person_handle.return_value = True
        current = Person()
        current.set_handle("H1")
        self.db.get_person_from_handle.return_value = current
        new_data = remove_object(person_data("H1", "I0002"))
        payload = [
            {
                "type": "update",
                "handle": "H1",
                "_class": "Person",
                "old": None,
                "new": new_data,
            }
        ]
        with mock.patch.object(grampswebapidb, "_merge_or_overwrite") as merge_fn:
            merge_fn.return_value = "MERGED"
            self.db._retry_after_conflict(payload)
        merge_current, merge_local = merge_fn.call_args[0]
        self.assertIs(merge_current, current)
        self.assertIsInstance(merge_local, Person)
        self.assertEqual(merge_local.get_gramps_id(), "I0002")
        self.db.commit_person.assert_called_once_with("MERGED", "TRANS")

    def test_delete_removes_if_handle_still_present(self):
        self.db.has_person_handle.return_value = True
        payload = [
            {
                "type": "delete",
                "handle": "H1",
                "_class": "Person",
                "old": remove_object(person_data("H1")),
                "new": None,
            }
        ]
        self.db._retry_after_conflict(payload)
        self.db.remove_person.assert_called_once_with("H1", "TRANS")

    def test_delete_is_skipped_if_handle_already_gone(self):
        # The conflicting server-side change may have been a delete of the
        # same object -- nothing left to remove a second time.
        self.db.has_person_handle.return_value = False
        payload = [
            {
                "type": "delete",
                "handle": "H1",
                "_class": "Person",
                "old": remove_object(person_data("H1")),
                "new": None,
            }
        ]
        self.db._retry_after_conflict(payload)
        self.db.remove_person.assert_not_called()

    def test_unrecognized_class_is_skipped(self):
        payload = [
            {
                "type": "update",
                "handle": "H1",
                "_class": "NotAThing",
                "old": None,
                "new": {},
            }
        ]
        self.db._retry_after_conflict(payload)  # must not raise
        self.db.commit_person.assert_not_called()
        self.db.has_person_handle.assert_not_called()

    def test_retrying_flag_set_during_replay_and_cleared_after(self):
        self.db.has_person_handle.return_value = False
        seen = {}

        def check_flag(obj, trans):
            seen["during"] = self.db._retrying

        self.db.commit_person.side_effect = check_flag
        new_data = remove_object(person_data("H1"))
        payload = [
            {
                "type": "update",
                "handle": "H1",
                "_class": "Person",
                "old": None,
                "new": new_data,
            }
        ]
        self.db._retry_after_conflict(payload)
        self.assertTrue(seen["during"])
        self.assertFalse(self.db._retrying)

    def test_retrying_flag_cleared_even_if_commit_raises(self):
        self.db.has_person_handle.return_value = False
        self.db.commit_person.side_effect = RuntimeError("boom")
        new_data = remove_object(person_data("H1"))
        payload = [
            {
                "type": "update",
                "handle": "H1",
                "_class": "Person",
                "old": None,
                "new": new_data,
            }
        ]
        with self.assertRaises(RuntimeError):
            self.db._retry_after_conflict(payload)
        self.assertFalse(self.db._retrying)


# -------------------------------------------------------------------------
#
# TestConflictRetryAgainstARealDatabase
#
# Every test above stubs out commit_person/has_person_handle/get_person_
# from_handle as independent mocks, which cannot catch a bug where
# _resync_after_conflict()'s write and the later merge step's read of
# "the current object" disagree -- exactly the shape of bug this fix was
# written for: an earlier version fetched fresh server data with a direct
# GET /<type>/<handle> and fed it straight to data_to_object(), which
# raises KeyError on that endpoint's shape (see _resync_after_conflict()'s
# docstring) -- caught by the broad _CONNECTION_ERRORS handler around it
# and misreported as a connectivity problem, so the payload got queued,
# retried, failed identically, and was silently dropped. This class runs
# against a real (temp-directory) SQLite-backed database and real DbTxn/
# transaction_commit machinery, with only the network layer (web_client)
# mocked, so it actually exercises that interaction end to end -- and
# _full_resync() itself runs for real against a fake XML export, the same
# way _resync_after_conflict() invokes it in production.
#
# -------------------------------------------------------------------------
class TestConflictRetryAgainstARealDatabase(unittest.TestCase):
    def setUp(self):
        tmpdir = tempfile.mkdtemp(prefix="grampswebapidb_test_")
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        db = make_database("sqlite")
        db.load(tmpdir)
        with DbTxn("seed", db) as trans:
            person = Person()
            person.set_gramps_id("I0001")
            db.add_person(person, trans)
            self.handle = person.handle
        # Reclassify the real, already-initialized SQLite-backed db as a
        # WebApiDB, rather than going through its network-dependent
        # load() -- this addon has no per-tree settings.ini (see the
        # module docstring), so nothing else ties identity to a server,
        # and this is the minimal way to run its push/retry logic against
        # a real DBAPI backend.
        db.__class__ = WebApiDB
        db.web_client = mock.MagicMock()
        db._syncing = False
        db._retrying = False
        db._pulling = False
        db._get_metadata = lambda key, default=0: default
        db._set_metadata = lambda key, value, use_txn=True: None
        db.web_client.get_transaction_history.return_value = ([], 0)
        db.web_client.get_object_count.return_value = 1
        db.web_client.supports_background_transactions.return_value = False
        self.db = db
        self.addCleanup(self.db.close)

    def _make_server_fresh(self):
        """The server's true current state for self.handle, diverged from
        the local mirror's stale copy (private=False -> True) via a route
        this addon's history feed cannot see -- see
        _resync_after_conflict()'s docstring."""
        server_fresh = copy.deepcopy(
            remove_object(object_to_data(self.db.get_person_from_handle(self.handle)))
        )
        server_fresh["private"] = True
        return server_fresh

    def _stub_full_resync_to(self, server_fresh):
        """Patch _full_resync() to commit server_fresh into local storage
        via a real, batch=True/_pulling=True DbTxn -- standing in for
        what a real resync does (download and reimport a full XML
        export), without actually needing one here. What matters for
        these tests is the local write _resync_after_conflict() relies
        on, not how a real resync produces it."""

        def fake_full_resync():
            self.db._pulling = True
            try:
                with DbTxn("fake resync", self.db, batch=True) as trans:
                    self.db.commit_person(data_to_object(server_fresh), trans)
            finally:
                self.db._pulling = False

        return mock.patch.object(self.db, "_full_resync", side_effect=fake_full_resync)

    def _push_conflicts_once_then_succeeds(self):
        calls = []

        def fake_push(payload, undo=False, background=False, on_wait=None):
            calls.append(copy.deepcopy(payload))
            if len(calls) == 1:
                raise WebApiPushConflict("Object has changed")

        self.db.web_client.push_transaction.side_effect = fake_push
        return calls

    def _add_an_attribute(self):
        with DbTxn("edit", self.db) as trans:
            person = self.db.get_person_from_handle(self.handle)
            attr = Attribute()
            attr.set_type("Occupation")
            attr.set_value("Tester")
            person.add_attribute(attr)
            self.db.commit_person(person, trans)

    def test_retry_pushes_the_resynced_object_as_old_not_the_stale_mirror(self):
        stale_local = remove_object(
            object_to_data(self.db.get_person_from_handle(self.handle))
        )
        server_fresh = self._make_server_fresh()
        calls = self._push_conflicts_once_then_succeeds()

        with self._stub_full_resync_to(server_fresh):
            self._add_an_attribute()

        self.assertEqual(len(calls), 2)
        # The original push sent the stale local snapshot -- that's what
        # the server rejected.
        self.assertEqual(calls[0][0]["old"], stale_local)
        # The retry must send the *resynced* server state as "old", not
        # the same stale value again -- otherwise it is guaranteed to
        # conflict identically and the edit is dropped for good (see
        # _push_payload()'s "give up after a repeated conflict" branch).
        self.assertEqual(calls[1][0]["old"], server_fresh)
        # "new" is the merge of that fresh state with the local edit's
        # actual intent, not a blind overwrite of either side.
        self.assertTrue(calls[1][0]["new"]["private"])
        self.assertTrue(
            any(a["value"] == "Tester" for a in calls[1][0]["new"]["attribute_list"])
        )

    def test_conflict_resolves_without_being_dropped(self):
        # Same setup, phrased as an outcome: the local mirror ends up
        # holding the merged result, and the edit was not dropped after
        # only its first, correctly-rejected attempt.
        calls = self._push_conflicts_once_then_succeeds()

        with self._stub_full_resync_to(self._make_server_fresh()):
            self._add_an_attribute()

        self.assertEqual(len(calls), 2)
        final = self.db.get_person_from_handle(self.handle)
        self.assertTrue(final.get_privacy())
        self.assertEqual(len(final.get_attribute_list()), 1)


# -------------------------------------------------------------------------
#
# TestMergeOrOverwrite
#
# -------------------------------------------------------------------------
class TestMergeOrOverwrite(unittest.TestCase):
    """_merge_or_overwrite() ports GrampsWebSync's diffhandler.py A_MRG_REM
    handling: combine two edits of the same object via the object's own
    merge() -- the same list-unioning logic behind Gramps' Merge People/
    Family/... tools -- rather than letting one edit silently clobber the
    other. Uses real Person/Tag objects rather than mocks, since the whole
    point is exercising Gramps' own merge() implementation."""

    def test_list_valued_fields_from_both_sides_are_unioned(self):
        current = Person()
        current.set_handle("H1")
        current.set_gramps_id("I0001")
        current.add_note("N-remote")

        local = Person()
        local.set_handle("H1")
        local.set_gramps_id("I0002")
        local.add_note("N-local")

        merged = grampswebapidb._merge_or_overwrite(current, local)
        self.assertEqual(set(merged.get_note_list()), {"N-remote", "N-local"})

    def test_current_object_is_not_mutated(self):
        current = Person()
        current.set_handle("H1")
        current.add_note("N-remote")
        local = Person()
        local.set_handle("H1")
        local.add_note("N-local")

        grampswebapidb._merge_or_overwrite(current, local)
        self.assertEqual(current.get_note_list(), ["N-remote"])

    def test_local_obj_gramps_id_is_cleared_before_merging(self):
        # merge() tags on a "Merged Gramps ID" attribute if the acquisition
        # has a gramps_id -- appropriate for absorbing a second, separate
        # object (Gramps' Merge People tool), but this is one object edited
        # twice, not two objects becoming one, so that attribute must not
        # appear, and local's own gramps_id object must be untouched.
        current = Person()
        current.set_handle("H1")
        local = Person()
        local.set_handle("H1")
        local.set_gramps_id("I0002")

        merged = grampswebapidb._merge_or_overwrite(current, local)
        self.assertEqual(merged.get_attribute_list(), [])
        self.assertEqual(local.get_gramps_id(), "I0002")

    def test_type_without_a_real_merge_falls_back_to_local_obj(self):
        # Tag only inherits BaseObject's no-op merge() -- "merging" into it
        # would silently keep current's content and drop the local edit.
        current = Tag()
        current.set_handle("H1")
        current.set_name("Remote name")
        local = Tag()
        local.set_handle("H1")
        local.set_name("Local name")

        result = grampswebapidb._merge_or_overwrite(current, local)
        self.assertIs(result, local)


# -------------------------------------------------------------------------
#
# TestUndoRedo
#
# -------------------------------------------------------------------------
class TestUndoRedo(unittest.TestCase):
    """undo()/redo() peek the relevant DbTxn off DbGenericUndo's queue,
    turn it back into a change-list payload, and push it -- undo via
    push_transaction(..., undo=True) (server reverses it), redo via a
    plain push (same as an ordinary commit). Both delegate to
    _push_payload(), whose conflict/error handling is already covered by
    TestTransactionCommit, so these just confirm the wiring: the right
    payload, the right undo flag, and the peek-before-super ordering."""

    def setUp(self):
        self.db = new_instance()
        self.db.undodb = mock.MagicMock()

    def test_undo_pushes_with_undo_flag(self):
        txn = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.undodb.undo_count = 1
        self.db.undodb.undoq = [txn]
        self.db.undodb.undo.return_value = True
        with mock.patch.object(self.db, "_push_payload") as push:
            result = self.db.undo()
        self.assertTrue(result)
        push.assert_called_once()
        payload = push.call_args[0][0]
        self.assertEqual(payload[0]["handle"], "H1")
        self.assertEqual(push.call_args.kwargs, {"undo": True})

    def test_redo_pushes_without_undo_flag(self):
        txn = FakeTransaction([(0, TXNDEL, "H1", person_data("H1"), None)])
        self.db.undodb.redo_count = 1
        self.db.undodb.redoq = [txn]
        self.db.undodb.redo.return_value = True
        with mock.patch.object(self.db, "_push_payload") as push:
            result = self.db.redo()
        self.assertTrue(result)
        payload = push.call_args[0][0]
        self.assertEqual(payload[0]["handle"], "H1")
        self.assertEqual(push.call_args.kwargs, {})

    def test_no_push_when_nothing_to_undo(self):
        self.db.undodb.undo_count = 0
        self.db.undodb.undo.return_value = False
        with mock.patch.object(self.db, "_push_payload") as push:
            result = self.db.undo()
        self.assertFalse(result)
        push.assert_not_called()

    def test_no_push_when_nothing_to_redo(self):
        self.db.undodb.redo_count = 0
        self.db.undodb.redo.return_value = False
        with mock.patch.object(self.db, "_push_payload") as push:
            result = self.db.redo()
        self.assertFalse(result)
        push.assert_not_called()

    def test_undo_not_pushed_if_super_reports_nothing_undone(self):
        # undo_count > 0 doesn't guarantee _undo() actually ran (e.g. a
        # readonly db -- see DbUndo.undo()); only a truthy result pushes.
        txn = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.undodb.undo_count = 1
        self.db.undodb.undoq = [txn]
        self.db.undodb.undo.return_value = False
        with mock.patch.object(self.db, "_push_payload") as push:
            result = self.db.undo()
        self.assertFalse(result)
        push.assert_not_called()

    def test_transaction_grabbed_before_super_pops_the_queue(self):
        # WebApiDB.undo() must read undoq[-1] before delegating to
        # super().undo() (-> DbGenericUndo._undo(), which pops it) -- grab
        # it too late and the payload would be built from the wrong (or a
        # missing) transaction.
        txn = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.undodb.undo_count = 1
        self.db.undodb.undoq = [txn]

        def pop_on_undo(update_history):
            self.db.undodb.undoq.pop()
            return True

        self.db.undodb.undo.side_effect = pop_on_undo
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db.undo()
        payload = push.call_args[0][0]
        self.assertEqual(payload[0]["handle"], "H1")


# -------------------------------------------------------------------------
#
# TestMisc
#
# -------------------------------------------------------------------------
class TestMisc(unittest.TestCase):
    def test_requires_login_is_false(self):
        self.assertFalse(new_instance().requires_login())

    def test_initialize_wraps_connection_errors(self):
        db = new_instance()
        with mock.patch.object(
            grampswebapidb.WebApiHandler,
            "from_env",
            side_effect=ValueError("GRAMPS_WEB_API_KEY is not set"),
        ):
            with self.assertRaises(DbConnectionError):
                db._initialize("/tmp/some-tree", None, None)

    def test_initialize_stores_web_client_and_calls_super(self):
        db = new_instance()
        sentinel_client = mock.MagicMock()
        with mock.patch.object(
            grampswebapidb.WebApiHandler, "from_env", return_value=sentinel_client
        ), mock.patch.object(grampswebapidb.SQLite, "_initialize") as super_init:
            db._initialize("/tmp/some-tree", "user", "pw")
        self.assertIs(db.web_client, sentinel_client)
        super_init.assert_called_once_with("/tmp/some-tree", "user", "pw")


# -------------------------------------------------------------------------
#
# TestDescribeConnectionError
#
# _get_json()/_get_binary() re-raise a non-401/429 HTTPError as-is, which
# throws its response body away -- so, absent _http_error_detail(), a
# validation failure the server explained in detail (a raw 422 from
# FastAPI's own request validation, before gramps-web-api's route handler
# even runs) would reach the user as nothing but "HTTP Error 422:
# Unprocessable Entity". See _describe_connection_error()'s docstring.
#
# -------------------------------------------------------------------------
class TestDescribeConnectionError(unittest.TestCase):
    @staticmethod
    def _http_error(code, body=None):
        fp = io.BytesIO(json.dumps(body).encode()) if body is not None else None
        return HTTPError("https://example.com/api/transactions/", code, "x", None, fp)

    def test_403_names_the_permission_problem_instead_of_the_raw_status(self):
        message = grampswebapidb._describe_connection_error(self._http_error(403))
        self.assertIn("GRAMPS_WEB_API_KEY", message)
        self.assertNotIn("HTTP Error 403", message)

    def test_422_appends_fastapi_detail(self):
        err = self._http_error(422, {"detail": [{"msg": "value is not a valid float"}]})
        message = grampswebapidb._describe_connection_error(err)
        self.assertIn("HTTP Error 422", message)
        self.assertIn("value is not a valid float", message)

    def test_appends_the_apps_own_error_message_shape_too(self):
        err = self._http_error(400, {"error": {"message": "Object has changed"}})
        message = grampswebapidb._describe_connection_error(err)
        self.assertIn("Object has changed", message)

    def test_appends_flask_jwt_extendeds_msg_shape_too(self):
        # What POST /token/refresh/ actually answers with when the stored
        # refresh token is expired, revoked, or otherwise rejected.
        err = self._http_error(422, {"msg": "Signature verification failed"})
        message = grampswebapidb._describe_connection_error(err)
        self.assertIn("Signature verification failed", message)

    def test_no_body_falls_back_to_the_bare_status(self):
        message = grampswebapidb._describe_connection_error(self._http_error(500))
        self.assertEqual(message, str(self._http_error(500)))

    def test_unparseable_body_falls_back_to_the_bare_status(self):
        err = HTTPError(
            "https://example.com/api/transactions/",
            422,
            "x",
            None,
            io.BytesIO(b"not json"),
        )
        message = grampswebapidb._describe_connection_error(err)
        self.assertEqual(message, str(err))

    def test_non_http_error_just_stringifies(self):
        message = grampswebapidb._describe_connection_error(ValueError("boom"))
        self.assertEqual(message, "boom")


# -------------------------------------------------------------------------
#
# TestCheckIdentity
#
# Nothing but a Family Tree's own name ties its local mirror to one
# particular GRAMPS_WEB_API_KEY account (see the module docstring) --
# _check_identity() requires that name to be "<username>@<host>" for
# whoever the current key authenticates as, so pointing the key at a
# different account while reopening the same tree fails loudly at load()
# instead of quietly mixing that account's data into the old mirror.
#
# -------------------------------------------------------------------------
class TestCheckIdentity(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db._directory = "/tmp/some-tree"
        self.db.web_client = mock.MagicMock()
        self.db.web_client.get_identity.return_value = "dblank@hadaly.duckdns.org"

    def test_matching_name_passes(self):
        self.db.get_dbname = mock.MagicMock(return_value="dblank@hadaly.duckdns.org")
        self.db._check_identity()  # must not raise

    def test_name_sanitized_the_same_way_dbman_does_still_passes(self):
        # gramps.gui.dbman's Family Tree Manager replaces "." (among other
        # characters) with "_" in any name typed through its rename UI, so
        # a hostname's dots can never actually reach name.txt -- the check
        # must accept the sanitized form as a match, not just the literal
        # "<username>@<host>" string.
        self.db.get_dbname = mock.MagicMock(return_value="dblank@hadaly_duckdns_org")
        self.db._check_identity()  # must not raise

    def test_mismatched_name_raises(self):
        self.db.get_dbname = mock.MagicMock(return_value="Gramps Web API DB")
        with self.assertRaises(DbConnectionError):
            self.db._check_identity()

    def test_mismatch_error_names_the_typeable_form(self):
        self.db.get_dbname = mock.MagicMock(return_value="Gramps Web API DB")
        with self.assertRaises(DbConnectionError) as ctx:
            self.db._check_identity()
        self.assertIn("dblank@hadaly_duckdns_org", str(ctx.exception))

    def test_connection_error_resolving_identity_is_wrapped(self):
        self.db.get_dbname = mock.MagicMock(return_value="dblank@hadaly.duckdns.org")
        self.db.web_client.get_identity.side_effect = HTTPError(
            "https://example.com/api/users/-/", 500, "boom", None, None
        )
        with self.assertRaises(DbConnectionError):
            self.db._check_identity()


# -------------------------------------------------------------------------
#
# TestCheckPermissions
#
# The server gates GET /transactions/history/ behind ViewPrivate and POST
# /transactions/ behind AddObject+EditObject+DeleteObject together. Checked
# up front at load() so a missing one is named explicitly rather than
# surfacing later as a bare 403 -- or, for the ViewPrivate export path, as
# a silently privacy-filtered resync. See the module docstring.
#
# -------------------------------------------------------------------------
class TestCheckPermissions(unittest.TestCase):
    ALL_PERMS = ["ViewPrivate", "AddObject", "EditObject", "DeleteObject"]

    def setUp(self):
        self.db = new_instance()
        self.db._directory = "/tmp/tree"
        self.db.web_client = mock.MagicMock()

    def _grant(self, *perms):
        self.db.web_client.get_permissions.return_value = list(perms)

    def test_editor_role_permissions_pass(self):
        self._grant(*self.ALL_PERMS)
        self.db._check_permissions()  # must not raise

    def test_extra_permissions_are_fine(self):
        # An Owner/Admin has a superset; only the required ones matter.
        self._grant(*self.ALL_PERMS, "AddUser", "ImportFile")
        self.db._check_permissions()  # must not raise

    def test_missing_view_private_raises(self):
        self._grant("AddObject", "EditObject", "DeleteObject")
        with self.assertRaises(DbConnectionError) as ctx:
            self.db._check_permissions()
        self.assertIn("ViewPrivate", str(ctx.exception))

    def test_missing_one_write_permission_raises(self):
        # has_permissions() server-side fails if *any* of the three are
        # missing, so a Contributor (AddObject only) cannot push at all.
        self._grant("ViewPrivate", "AddObject")
        with self.assertRaises(DbConnectionError) as ctx:
            self.db._check_permissions()
        message = str(ctx.exception)
        self.assertIn("EditObject", message)
        self.assertIn("DeleteObject", message)
        self.assertNotIn("AddObject", message.replace("EditObject", ""))

    def test_error_names_the_role_to_ask_for(self):
        self._grant()
        with self.assertRaises(DbConnectionError) as ctx:
            self.db._check_permissions()
        self.assertIn("Editor", str(ctx.exception))

    def test_read_only_tree_does_not_need_write_permissions(self):
        # A tree opened read-only never pushes, so a Member-level account
        # (ViewPrivate but no write permissions) is enough for it.
        self._grant("ViewPrivate")
        self.db._check_permissions(writable=False)  # must not raise

    def test_read_only_tree_still_needs_view_private(self):
        self._grant("AddObject", "EditObject", "DeleteObject")
        with self.assertRaises(DbConnectionError):
            self.db._check_permissions(writable=False)

    def test_connection_error_fetching_permissions_is_wrapped(self):
        self.db.web_client.get_permissions.side_effect = HTTPError(
            "https://example.com/api/token/refresh/", 500, "boom", None, None
        )
        with self.assertRaises(DbConnectionError):
            self.db._check_permissions()

    def test_load_checks_permissions_for_a_writable_tree(self):
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions") as check, mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ), mock.patch.object(
            self.db, "_sync_media_files"
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            self.db.load("some/path")
        check.assert_called_once_with(writable=True)

    def test_load_in_read_only_mode_checks_read_permissions_only(self):
        # DbGeneric.load()'s signature is (directory, callback, mode, ...) --
        # cli/grampscli.py passes mode positionally.
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions") as check, mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ), mock.patch.object(
            self.db, "_sync_media_files"
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            self.db.load("some/path", None, "r")
        check.assert_called_once_with(writable=False)

    def test_load_reads_mode_from_a_keyword_too(self):
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions") as check, mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ), mock.patch.object(
            self.db, "_sync_media_files"
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            self.db.load("some/path", mode="r")
        check.assert_called_once_with(writable=False)


# -------------------------------------------------------------------------
#
# TestCheckServerVersion
#
# A server running Gramps < 6.0 serializes its transaction history in a
# shape data_to_object() can't read, which would otherwise surface as a
# bare KeyError mid-sync. See the module docstring.
#
# -------------------------------------------------------------------------
class TestCheckServerVersion(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db._directory = "/tmp/tree"
        self.db.web_client = mock.MagicMock()

    def test_supported_version_passes(self):
        self.db.web_client.get_gramps_version.return_value = "6.0.1"
        self.db._check_server_version()  # must not raise

    def test_newer_version_passes(self):
        self.db.web_client.get_gramps_version.return_value = "6.1.0"
        self.db._check_server_version()  # must not raise

    def test_too_old_raises_naming_both_versions(self):
        self.db.web_client.get_gramps_version.return_value = "5.2.3"
        with self.assertRaises(DbConnectionError) as ctx:
            self.db._check_server_version()
        message = str(ctx.exception)
        self.assertIn("5.2.3", message)
        self.assertIn("6.0", message)

    def test_unknown_version_is_allowed_through(self):
        # Better to try and let the KeyError path catch a genuinely
        # incompatible server than to block on a guess.
        self.db.web_client.get_gramps_version.return_value = None
        self.db._check_server_version()  # must not raise

    def test_unparseable_version_is_allowed_through(self):
        self.db.web_client.get_gramps_version.return_value = "some-dev-build"
        self.db._check_server_version()  # must not raise

    def test_connection_error_is_wrapped(self):
        self.db.web_client.get_gramps_version.side_effect = HTTPError(
            "https://example.com/api/metadata/", 500, "boom", None, None
        )
        with self.assertRaises(DbConnectionError):
            self.db._check_server_version()


# -------------------------------------------------------------------------
#
# TestUseBackgroundPush
#
# -------------------------------------------------------------------------
class TestUseBackgroundPush(unittest.TestCase):
    """Only a large payload on a capable server goes through the server's
    background task queue -- see BACKGROUND_PUSH_THRESHOLD."""

    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()

    def _payload(self, size):
        return [{"type": "add", "handle": "H%d" % i} for i in range(size)]

    def test_small_payload_is_synchronous_without_asking_the_server(self):
        self.db.web_client.supports_background_transactions.return_value = True
        self.assertFalse(self.db._use_background_push(self._payload(1)))
        self.db.web_client.supports_background_transactions.assert_not_called()

    def test_large_payload_on_a_capable_server_goes_background(self):
        self.db.web_client.supports_background_transactions.return_value = True
        payload = self._payload(grampswebapidb.BACKGROUND_PUSH_THRESHOLD)
        self.assertTrue(self.db._use_background_push(payload))

    def test_large_payload_on_an_old_server_stays_synchronous(self):
        self.db.web_client.supports_background_transactions.return_value = False
        payload = self._payload(grampswebapidb.BACKGROUND_PUSH_THRESHOLD)
        self.assertFalse(self.db._use_background_push(payload))

    def test_failure_asking_falls_back_to_synchronous(self):
        # Not worth failing the push over -- the synchronous path works
        # against every server version.
        self.db.web_client.supports_background_transactions.side_effect = OSError(
            "metadata unreachable"
        )
        payload = self._payload(grampswebapidb.BACKGROUND_PUSH_THRESHOLD)
        self.assertFalse(self.db._use_background_push(payload))

    def test_push_payload_passes_the_flag_through(self):
        self.db._get_metadata = lambda key, default=0: default
        self.db._set_metadata = lambda key, value, use_txn=True: None
        self.db.web_client.supports_background_transactions.return_value = True
        payload = self._payload(grampswebapidb.BACKGROUND_PUSH_THRESHOLD)
        self.db._push_payload(payload)
        self.assertTrue(
            self.db.web_client.push_transaction.call_args.kwargs["background"]
        )


# -------------------------------------------------------------------------
#
# TestIsRetryablePushError
#
# -------------------------------------------------------------------------
class TestIsRetryablePushError(unittest.TestCase):
    """A 4xx other than 429 is the server's settled answer and must not be
    queued for retry -- see _is_retryable_push_error()."""

    def _http(self, code):
        return HTTPError("https://example.com/api/transactions/", code, "x", None, None)

    def test_403_is_not_retryable(self):
        self.assertFalse(grampswebapidb._is_retryable_push_error(self._http(403)))

    def test_400_is_not_retryable(self):
        self.assertFalse(grampswebapidb._is_retryable_push_error(self._http(400)))

    def test_404_is_not_retryable(self):
        self.assertFalse(grampswebapidb._is_retryable_push_error(self._http(404)))

    def test_429_is_retryable(self):
        self.assertTrue(grampswebapidb._is_retryable_push_error(self._http(429)))

    def test_500_is_retryable(self):
        self.assertTrue(grampswebapidb._is_retryable_push_error(self._http(500)))

    def test_network_errors_are_retryable(self):
        self.assertTrue(grampswebapidb._is_retryable_push_error(OSError("down")))
        self.assertTrue(
            grampswebapidb._is_retryable_push_error(URLError("no route to host"))
        )


# -------------------------------------------------------------------------
#
# TestPolling
#
# load() schedules a GLib.timeout_add_seconds() tick that re-syncs for as
# long as the database stays open (see the module docstring's polling
# section); close() must cancel it so a closed database doesn't keep
# polling on a connection that's going away.
#
# -------------------------------------------------------------------------
class TestPolling(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()

    def test_load_syncs_and_schedules_polling(self):
        with mock.patch.object(
            grampswebapidb.SQLite, "load"
        ) as super_load, mock.patch.object(
            self.db, "_check_identity"
        ) as check_identity, mock.patch.object(
            self.db, "_check_permissions"
        ), mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ) as sync, mock.patch.object(
            self.db, "_sync_media_files"
        ) as sync_media, mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds", side_effect=[42, 43]
        ) as timeout_add:
            self.db.load("some/path")
        super_load.assert_called_once_with("some/path")
        check_identity.assert_called_once_with()
        sync.assert_called_once_with(progress_callback=None, verify_totals=True)
        sync_media.assert_called_once_with()
        timeout_add.assert_has_calls(
            [
                mock.call(grampswebapidb.POLL_INTERVAL_SECONDS, self.db._poll_tick),
                mock.call(
                    grampswebapidb.MEDIA_POLL_INTERVAL_SECONDS,
                    self.db._media_poll_tick,
                ),
            ]
        )
        self.assertEqual(self.db._poll_source_id, 42)
        self.assertEqual(self.db._media_poll_source_id, 43)

    def test_load_forwards_positional_callback_to_sync(self):
        # DbGeneric.load()'s own signature is (directory, callback=None,
        # mode=..., ...) -- cli/grampscli.py calls it positionally
        # (db.load(filename, self._pulse_progress, mode, ...)), so load()
        # must recognize the callback there too, not just as a kwarg.
        my_callback = mock.MagicMock()
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions"), mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ) as sync, mock.patch.object(
            self.db, "_sync_media_files"
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            self.db.load("some/path", my_callback, "w")
        sync.assert_called_once_with(progress_callback=my_callback, verify_totals=True)

    def test_load_forwards_keyword_callback_to_sync(self):
        my_callback = mock.MagicMock()
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions"), mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ) as sync, mock.patch.object(
            self.db, "_sync_media_files"
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            self.db.load("some/path", callback=my_callback)
        sync.assert_called_once_with(progress_callback=my_callback, verify_totals=True)

    def test_load_media_sync_failure_does_not_block_load(self):
        # Unlike a _sync_from_server() failure (which load() re-raises as
        # DbConnectionError), a failed initial media sync is logged and
        # swallowed -- the record mirror is already usable, so opening the
        # tree should still succeed.
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions"), mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ), mock.patch.object(
            self.db, "_sync_media_files", side_effect=OSError("network down")
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
                self.db.load("some/path")  # must not raise
        # That traceback is this outage's one loud report -- the media
        # poll should stay quiet rather than repeat it 300 seconds later.
        self.assertEqual(self.db._media_poll_failures, 1)

    def test_load_resets_poll_backoff_state(self):
        # Class-attribute defaults, so an instance reused across a
        # close()/load() must not start out backed off from the previous
        # tree's outage.
        self.db._poll_failures = 4
        self.db._media_poll_failures = 4
        self.db._poll_interval = grampswebapidb.POLL_BACKOFF_MAX_SECONDS
        with mock.patch.object(grampswebapidb.SQLite, "load"), mock.patch.object(
            self.db, "_check_identity"
        ), mock.patch.object(self.db, "_check_permissions"), mock.patch.object(
            self.db, "_check_server_version"
        ), mock.patch.object(
            self.db, "_sync_from_server"
        ), mock.patch.object(
            self.db, "_sync_media_files"
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds"
        ):
            self.db.load("some/path")
        self.assertEqual(self.db._poll_failures, 0)
        self.assertEqual(self.db._media_poll_failures, 0)
        self.assertEqual(self.db._poll_interval, grampswebapidb.POLL_INTERVAL_SECONDS)

    def test_close_cancels_pending_poll(self):
        self.db._poll_source_id = 42
        self.db._media_poll_source_id = 43
        with mock.patch.object(
            grampswebapidb.SQLite, "close"
        ) as super_close, mock.patch.object(
            grampswebapidb.GLib, "source_remove"
        ) as source_remove:
            self.db.close()
        source_remove.assert_has_calls([mock.call(42), mock.call(43)])
        self.assertIsNone(self.db._poll_source_id)
        self.assertIsNone(self.db._media_poll_source_id)
        super_close.assert_called_once_with()
        self.assertTrue(self.db._closed)

    def test_close_without_a_poll_scheduled_is_a_no_op(self):
        # e.g. close() called after a failed load(), before the timeouts
        # were ever scheduled.
        with mock.patch.object(
            grampswebapidb.SQLite, "close"
        ) as super_close, mock.patch.object(
            grampswebapidb.GLib, "source_remove"
        ) as source_remove:
            self.db.close()
        source_remove.assert_not_called()
        super_close.assert_called_once_with()
        self.assertTrue(self.db._closed)

    def test_poll_tick_syncs_and_keeps_repeating(self):
        with mock.patch.object(self.db, "_sync_from_server") as sync:
            result = self.db._poll_tick()
        sync.assert_called_once_with()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)

    def test_poll_tick_does_not_start_a_sync_underneath_a_running_one(self):
        # _pump_main_loop() hands the main loop back part-way through a
        # sync, which is when this timeout can fire re-entrantly.
        self.db._syncing = True
        with mock.patch.object(self.db, "_sync_from_server") as sync:
            result = self.db._poll_tick()
        sync.assert_not_called()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)

    def test_media_poll_tick_does_not_start_a_sync_underneath_a_running_one(self):
        self.db._syncing = True
        with mock.patch.object(self.db, "_sync_media_files") as sync_media:
            result = self.db._media_poll_tick()
        sync_media.assert_not_called()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)

    def test_poll_tick_swallows_connection_errors_and_keeps_polling(self):
        # The failing tick reschedules itself at a longer interval, so it
        # reports SOURCE_REMOVE for the *old* source while the replacement
        # keeps the poll alive.
        self.db._poll_interval = grampswebapidb.POLL_INTERVAL_SECONDS
        with mock.patch.object(
            self.db, "_sync_from_server", side_effect=OSError("network down")
        ), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds", return_value=99
        ) as timeout_add:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                result = self.db._poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_REMOVE)
        timeout_add.assert_called_once_with(
            grampswebapidb.POLL_INTERVAL_SECONDS * 2, self.db._poll_tick
        )
        self.assertEqual(self.db._poll_source_id, 99)
        self.assertEqual(
            self.db._poll_interval, grampswebapidb.POLL_INTERVAL_SECONDS * 2
        )
        self.assertEqual(self.db._poll_failures, 1)

    def test_poll_tick_reports_a_lasting_outage_only_once(self):
        # A server that stays down must not log a warning (let alone a
        # traceback) on every tick for the whole outage.
        with mock.patch.object(
            self.db, "_sync_from_server", side_effect=OSError("network down")
        ), mock.patch.object(grampswebapidb.GLib, "timeout_add_seconds"):
            with self.assertLogs(grampswebapidb.LOG, level="DEBUG") as logs:
                for _unused in range(5):
                    self.db._poll_tick()
        warnings = [rec for rec in logs.records if rec.levelname == "WARNING"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(self.db._poll_failures, 5)

    def test_poll_tick_backs_off_to_the_cap_and_stops_rescheduling(self):
        with mock.patch.object(
            self.db, "_sync_from_server", side_effect=OSError("network down")
        ), mock.patch.object(grampswebapidb.GLib, "timeout_add_seconds") as timeout_add:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                for _unused in range(20):
                    result = self.db._poll_tick()
        self.assertEqual(
            self.db._poll_interval, grampswebapidb.POLL_BACKOFF_MAX_SECONDS
        )
        # Every reschedule doubles the interval, so once the cap is
        # reached the timer is left alone rather than churned each tick.
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)
        intervals = [call.args[0] for call in timeout_add.call_args_list]
        self.assertEqual(intervals, sorted(intervals))
        self.assertLessEqual(intervals[-1], grampswebapidb.POLL_BACKOFF_MAX_SECONDS)

    def test_poll_tick_restores_the_normal_interval_after_recovery(self):
        self.db._poll_failures = 3
        self.db._poll_interval = grampswebapidb.POLL_BACKOFF_MAX_SECONDS
        with mock.patch.object(self.db, "_sync_from_server"), mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds", return_value=7
        ) as timeout_add:
            with self.assertLogs(grampswebapidb.LOG, level="INFO"):
                result = self.db._poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_REMOVE)
        timeout_add.assert_called_once_with(
            grampswebapidb.POLL_INTERVAL_SECONDS, self.db._poll_tick
        )
        self.assertEqual(self.db._poll_source_id, 7)
        self.assertEqual(self.db._poll_interval, grampswebapidb.POLL_INTERVAL_SECONDS)
        self.assertEqual(self.db._poll_failures, 0)

    def test_media_poll_tick_syncs_and_keeps_repeating(self):
        with mock.patch.object(self.db, "_sync_media_files") as sync_media:
            result = self.db._media_poll_tick()
        sync_media.assert_called_once_with()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)

    def test_media_poll_tick_swallows_connection_errors_and_keeps_repeating(self):
        with mock.patch.object(
            self.db, "_sync_media_files", side_effect=OSError("network down")
        ):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                result = self.db._media_poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)
        self.assertEqual(self.db._media_poll_failures, 1)

    def test_media_poll_tick_reports_a_lasting_outage_only_once(self):
        with mock.patch.object(
            self.db, "_sync_media_files", side_effect=OSError("network down")
        ):
            with self.assertLogs(grampswebapidb.LOG, level="DEBUG") as logs:
                for _unused in range(4):
                    result = self.db._media_poll_tick()
        warnings = [rec for rec in logs.records if rec.levelname == "WARNING"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)
        self.assertEqual(self.db._media_poll_failures, 4)

    def test_media_poll_tick_notes_recovery(self):
        self.db._media_poll_failures = 2
        with mock.patch.object(self.db, "_sync_media_files"):
            with self.assertLogs(grampswebapidb.LOG, level="INFO"):
                result = self.db._media_poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)
        self.assertEqual(self.db._media_poll_failures, 0)

    def test_poll_tick_stops_quietly_when_the_tree_closed_mid_sync(self):
        # The user switching (or closing) this Family Tree while
        # _guarded_pump() had handed the main loop back mid-sync -- see
        # TestGuardedPump. Not a failure: no WARNING, and the timer must
        # not reschedule itself (close() already removed its GLib source).
        with mock.patch.object(
            self.db, "_sync_from_server", side_effect=grampswebapidb._DatabaseClosed
        ):
            result = self.db._poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_REMOVE)
        self.assertEqual(self.db._poll_failures, 0)

    def test_media_poll_tick_stops_quietly_when_the_tree_closed_mid_sync(self):
        with mock.patch.object(
            self.db, "_sync_media_files", side_effect=grampswebapidb._DatabaseClosed
        ):
            result = self.db._media_poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_REMOVE)
        self.assertEqual(self.db._media_poll_failures, 0)


# -------------------------------------------------------------------------
#
# TestGuardedPump
#
# _guarded_pump() is what every _pump_main_loop() call inside WebApiDB
# goes through instead of the bare function -- see the module docstring's
# "Keeping the GUI alive" section. Regression coverage for the crash a PR
# tester hit: switching Family Trees while a poll-driven sync was
# suspended mid-_pump_main_loop() resumed against an already-closed
# sqlite connection (sqlite3.ProgrammingError: Cannot operate on a closed
# database).
#
# -------------------------------------------------------------------------
class TestGuardedPump(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()

    def test_pumps_and_returns_when_still_open(self):
        with mock.patch.object(grampswebapidb, "_pump_main_loop") as pump:
            self.db._guarded_pump()  # must not raise
        pump.assert_called_once_with()

    def test_raises_database_closed_if_close_ran_during_the_pump(self):
        def fake_pump():
            # Simulates close() running from a GTK event dispatched while
            # this pump had control -- see close()'s own _closed = True.
            self.db._closed = True

        with mock.patch.object(
            grampswebapidb, "_pump_main_loop", side_effect=fake_pump
        ):
            with self.assertRaises(grampswebapidb._DatabaseClosed):
                self.db._guarded_pump()


# -------------------------------------------------------------------------
#
# TestSyncMediaFiles
#
# _sync_media_files() and its helpers: the file-transfer half of keeping
# the mirror in sync, ported from GrampsWebSync's media-file-sync wizard
# step (grampswebsync.py/webapihandler.py, credit David Straub).
#
# -------------------------------------------------------------------------
class FakeMedia:
    """Duck-types the bit of a Media object these helpers read."""

    def __init__(self, handle, path, gramps_id="O0001"):
        self.handle = handle
        self._path = path
        self.gramps_id = gramps_id

    def get_path(self):
        return self._path


class TestMissingLocalMediaHandles(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()

    def test_returns_handles_whose_file_is_missing(self):
        present = FakeMedia("H1", "present.jpg")
        missing = FakeMedia("H2", "missing.jpg")
        with mock.patch.object(
            self.db, "iter_media", return_value=[present, missing]
        ), mock.patch.object(
            grampswebapidb,
            "media_path_full",
            side_effect=lambda db, path: "/tree/" + path,
        ), mock.patch.object(
            grampswebapidb.os.path, "exists", side_effect=lambda p: "present" in p
        ):
            handles = self.db._missing_local_media_handles()
        self.assertEqual(handles, ["H2"])

    def test_no_media_objects_returns_empty_list(self):
        with mock.patch.object(self.db, "iter_media", return_value=[]):
            self.assertEqual(self.db._missing_local_media_handles(), [])


class TestMissingRemoteMediaHandles(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()

    def test_extracts_handles_from_server_response(self):
        self.db.web_client = mock.MagicMock()
        self.db.web_client.get_missing_files.return_value = [
            {"handle": "H1", "gramps_id": "O0001"},
            {"handle": "H2", "gramps_id": "O0002"},
        ]
        self.assertEqual(self.db._missing_remote_media_handles(), ["H1", "H2"])

    def test_empty_server_response(self):
        self.db.web_client = mock.MagicMock()
        self.db.web_client.get_missing_files.return_value = []
        self.assertEqual(self.db._missing_remote_media_handles(), [])


class TestDownloadOneMediaFile(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()

    def test_downloads_and_returns_true(self):
        media = FakeMedia("H1", "photo.jpg")
        with mock.patch.object(
            self.db, "get_media_from_handle", return_value=media
        ), mock.patch.object(
            grampswebapidb, "media_path_full", return_value="/tree/photo.jpg"
        ):
            result = self.db._download_one_media_file("H1")
        self.assertTrue(result)
        self.db.web_client.download_media_file.assert_called_once_with(
            "H1", "/tree/photo.jpg"
        )

    def test_missing_local_object_returns_false(self):
        with mock.patch.object(
            self.db,
            "get_media_from_handle",
            side_effect=grampswebapidb.HandleError("H1"),
        ):
            result = self.db._download_one_media_file("H1")
        self.assertFalse(result)
        self.db.web_client.download_media_file.assert_not_called()

    def test_connection_error_is_logged_and_returns_false(self):
        media = FakeMedia("H1", "photo.jpg")
        self.db.web_client.download_media_file.side_effect = OSError("network down")
        with mock.patch.object(
            self.db, "get_media_from_handle", return_value=media
        ), mock.patch.object(
            grampswebapidb, "media_path_full", return_value="/tree/photo.jpg"
        ):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                result = self.db._download_one_media_file("H1")
        self.assertFalse(result)


class TestUploadOneMediaFile(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()

    def test_uploads_and_returns_true(self):
        media = FakeMedia("H1", "photo.jpg")
        self.db.web_client.upload_media_file.return_value = True
        with mock.patch.object(
            self.db, "get_media_from_handle", return_value=media
        ), mock.patch.object(
            grampswebapidb, "media_path_full", return_value="/tree/photo.jpg"
        ), mock.patch.object(
            grampswebapidb.os.path, "exists", return_value=True
        ):
            result = self.db._upload_one_media_file("H1")
        self.assertTrue(result)
        self.db.web_client.upload_media_file.assert_called_once_with(
            "H1", "/tree/photo.jpg"
        )

    def test_conflict_response_returns_false(self):
        # WebApiHandler.upload_media_file() itself returns False on a 409
        # (someone else already uploaded a file for this object) rather
        # than raising -- propagated here as-is.
        media = FakeMedia("H1", "photo.jpg")
        self.db.web_client.upload_media_file.return_value = False
        with mock.patch.object(
            self.db, "get_media_from_handle", return_value=media
        ), mock.patch.object(
            grampswebapidb, "media_path_full", return_value="/tree/photo.jpg"
        ), mock.patch.object(
            grampswebapidb.os.path, "exists", return_value=True
        ):
            result = self.db._upload_one_media_file("H1")
        self.assertFalse(result)

    def test_missing_local_object_returns_false(self):
        with mock.patch.object(
            self.db,
            "get_media_from_handle",
            side_effect=grampswebapidb.HandleError("H1"),
        ):
            result = self.db._upload_one_media_file("H1")
        self.assertFalse(result)
        self.db.web_client.upload_media_file.assert_not_called()

    def test_file_not_on_disk_returns_false_without_uploading(self):
        media = FakeMedia("H1", "photo.jpg")
        with mock.patch.object(
            self.db, "get_media_from_handle", return_value=media
        ), mock.patch.object(
            grampswebapidb, "media_path_full", return_value="/tree/photo.jpg"
        ), mock.patch.object(
            grampswebapidb.os.path, "exists", return_value=False
        ):
            result = self.db._upload_one_media_file("H1")
        self.assertFalse(result)
        self.db.web_client.upload_media_file.assert_not_called()

    def test_connection_error_is_logged_and_returns_false(self):
        media = FakeMedia("H1", "photo.jpg")
        self.db.web_client.upload_media_file.side_effect = OSError("network down")
        with mock.patch.object(
            self.db, "get_media_from_handle", return_value=media
        ), mock.patch.object(
            grampswebapidb, "media_path_full", return_value="/tree/photo.jpg"
        ), mock.patch.object(
            grampswebapidb.os.path, "exists", return_value=True
        ):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                result = self.db._upload_one_media_file("H1")
        self.assertFalse(result)


class TestSyncMediaFiles(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()

    def test_downloads_missing_local_then_uploads_missing_remote(self):
        with mock.patch.object(
            self.db, "_missing_local_media_handles", return_value=["H1", "H2"]
        ), mock.patch.object(
            self.db, "_missing_remote_media_handles", return_value=["H3"]
        ), mock.patch.object(
            self.db, "_download_one_media_file", return_value=True
        ) as download, mock.patch.object(
            self.db, "_upload_one_media_file", return_value=True
        ) as upload:
            result = self.db._sync_media_files()
        download.assert_has_calls([mock.call("H1"), mock.call("H2")])
        upload.assert_called_once_with("H3")
        self.assertEqual(result, (2, 1))

    def test_main_loop_is_pumped_per_file_and_syncing_flag_is_managed(self):
        # Each transfer is its own blocking round trip, and a first sync
        # of a tree with media runs hundreds back to back.
        seen = []
        with mock.patch.object(
            self.db, "_missing_local_media_handles", return_value=["H1", "H2"]
        ), mock.patch.object(
            self.db, "_missing_remote_media_handles", return_value=["H3"]
        ), mock.patch.object(
            self.db,
            "_download_one_media_file",
            side_effect=lambda handle: seen.append(self.db._syncing) or True,
        ), mock.patch.object(
            self.db, "_upload_one_media_file", return_value=True
        ), mock.patch.object(
            grampswebapidb, "_pump_main_loop"
        ) as pump:
            self.db._sync_media_files()
        self.assertEqual(pump.call_count, 3)
        self.assertEqual(seen, [True, True])
        self.assertFalse(self.db._syncing)

    def test_counts_only_successful_transfers(self):
        with mock.patch.object(
            self.db, "_missing_local_media_handles", return_value=["H1", "H2"]
        ), mock.patch.object(
            self.db, "_missing_remote_media_handles", return_value=[]
        ), mock.patch.object(
            self.db, "_download_one_media_file", side_effect=[True, False]
        ):
            result = self.db._sync_media_files()
        self.assertEqual(result, (1, 0))

    def test_nothing_missing_is_a_no_op(self):
        with mock.patch.object(
            self.db, "_missing_local_media_handles", return_value=[]
        ), mock.patch.object(self.db, "_missing_remote_media_handles", return_value=[]):
            result = self.db._sync_media_files()
        self.assertEqual(result, (0, 0))


# -------------------------------------------------------------------------
#
# TestBatchCommitReconciliation
#
# A local batch=True transaction (a bulk import, or a stock Tool like
# Check and Repair Database) records nothing per-object -- DBAPI skips
# trans.add() for a batch commit -- so transaction_to_json() sees an
# empty payload and nothing would ever be pushed. transaction_begin()
# snapshots every primary object's full current data up front
# (_snapshot_all_objects()) and transaction_commit() diffs a fresh
# snapshot against it after, reconstructing the change list -- not just
# which handles exist, and not a .change-vs-start_time timestamp guess
# (an earlier version compared timestamps instead of content and, for
# that and two other reasons, could silently miss changes, push a false
# "old" a real server always rejects as a conflict, or drop deletes
# outright -- see the module docstring and _reconcile_batch_commit()'s
# own docstring for the full account; GrampsWebApiDb/tests/
# test_reconcile_batch_commit_real_db.py exercises all of that against a
# real database).
#
# -------------------------------------------------------------------------
class FakeBatchTxn:
    """Duck-types the DbTxn attributes the batch-reconciliation path
    reads: .batch, .start_time, and whatever attribute transaction_begin()
    stashes its snapshot in. get_recnos() returns nothing, matching a real
    batch transaction's empty undo log."""

    def __init__(self, batch=True, start_time=100.0):
        self.batch = batch
        self.start_time = start_time

    def get_recnos(self, reverse=False):
        return []

    def get_record(self, recno):  # pragma: no cover - never reached
        raise AssertionError("a batch transaction records nothing")


def raw_person_data(handle, change=100.0, **extra):
    """A minimal json_utils-shaped dict standing in for what
    _get_raw_data()/_iter_raw_data() returns for a Person.
    _reconcile_batch_commit() only ever diffs and forwards these as
    plain dicts (via diff_items()) -- it never turns them back into
    real objects -- so a real Person is not needed to test it."""
    data = {"handle": handle, "change": change, "gramps_id": "I" + handle}
    data.update(extra)
    return data


def stub_iter_raw_data(db, data_by_class):
    """data_by_class: {obj_class: {handle: raw_data_dict}}. Stubs
    _iter_raw_data() -- the bulk per-type read _snapshot_all_objects()
    uses -- so _reconcile_batch_commit()/_snapshot_all_objects() can be
    exercised without a real database."""

    def fake_iter_raw_data(key):
        obj_class = grampswebapidb.KEY_TO_CLASS_MAP[key]
        return list(data_by_class.get(obj_class, {}).items())

    db._iter_raw_data = mock.MagicMock(side_effect=fake_iter_raw_data)


class TestTransactionBeginSnapshot(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()

    def test_local_batch_transaction_gets_a_full_object_snapshot(self):
        stub_iter_raw_data(self.db, {"Person": {"H1": raw_person_data("H1")}})
        trans = FakeBatchTxn(batch=True)
        with mock.patch.object(grampswebapidb.SQLite, "transaction_begin"):
            self.db.transaction_begin(trans)
        self.assertEqual(
            trans._webapidb_before, {("Person", "H1"): raw_person_data("H1")}
        )

    def test_non_batch_transaction_gets_no_snapshot(self):
        # An ordinary edit is recorded per-object by DBAPI, so
        # transaction_to_json() sees it and none of this is needed.
        trans = FakeBatchTxn(batch=False)
        with mock.patch.object(grampswebapidb.SQLite, "transaction_begin"):
            self.db.transaction_begin(trans)
        self.assertFalse(hasattr(trans, "_webapidb_before"))

    def test_pull_side_batch_transaction_gets_no_snapshot(self):
        # _sync_from_server()'s own replay is a batch transaction too, but
        # pushing it back to the server would echo the server's own changes
        # straight back at it.
        self.db._pulling = True
        trans = FakeBatchTxn(batch=True)
        with mock.patch.object(grampswebapidb.SQLite, "transaction_begin"):
            self.db.transaction_begin(trans)
        self.assertFalse(hasattr(trans, "_webapidb_before"))


class TestReconcileBatchCommit(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()

    def test_added_handle_becomes_an_add_with_no_old_data(self):
        stub_iter_raw_data(
            self.db,
            {"Person": {"H1": raw_person_data("H1"), "H2": raw_person_data("H2")}},
        )
        before = {("Person", "H1"): raw_person_data("H1")}
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit(before)
        entries = push.call_args[0][0]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "add")
        self.assertEqual(entries[0]["handle"], "H2")
        self.assertEqual(entries[0]["_class"], "Person")
        self.assertIsNone(entries[0]["old"])
        self.assertEqual(entries[0]["new"], raw_person_data("H2"))

    def test_removed_handle_becomes_a_delete_carrying_its_last_known_data(self):
        stub_iter_raw_data(self.db, {"Person": {}})
        before = {("Person", "H1"): raw_person_data("H1")}
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit(before)
        entries = push.call_args[0][0]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "delete")
        self.assertEqual(entries[0]["handle"], "H1")
        self.assertIsNone(entries[0]["new"])
        # Bug fixed: an earlier version replayed deletes through
        # _retry_after_conflict()'s has_handle() guard, which (correct
        # for an actual conflict retry) silently no-ops here since the
        # object is legitimately already gone -- dropping every
        # reconciled delete. This builds the entry directly instead.
        self.assertEqual(entries[0]["old"], raw_person_data("H1"))

    def test_surviving_handle_with_real_content_change_becomes_an_update(self):
        stub_iter_raw_data(
            self.db,
            {"Person": {"H1": raw_person_data("H1", change=200.0, gramps_id="I0002")}},
        )
        before = {
            ("Person", "H1"): raw_person_data("H1", change=100.0, gramps_id="I0001")
        }
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit(before)
        entries = push.call_args[0][0]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "update")
        # Bug fixed: an earlier version replayed this through
        # _retry_after_conflict(), which re-commits whatever local
        # storage holds *now* -- by reconciliation time, already the
        # batch's own result -- so "old" ended up matching "new"
        # instead of genuinely reflecting the pre-batch state a real
        # server needs to compare against.
        self.assertEqual(entries[0]["old"]["gramps_id"], "I0001")
        self.assertEqual(entries[0]["new"]["gramps_id"], "I0002")

    def test_update_within_the_same_wall_clock_second_as_batch_start_is_still_detected(
        self,
    ):
        # Bug fixed: an earlier version compared .change (int) against
        # the transaction's own start_time (a float), so any edit
        # landing in the same wall-clock second as start_time -- the
        # common case for a fast local tool -- was silently missed.
        # This version diffs content, not timestamps, so it isn't
        # fooled by two events sharing a second.
        stub_iter_raw_data(
            self.db,
            {"Person": {"H1": raw_person_data("H1", change=100.0, private=True)}},
        )
        before = {("Person", "H1"): raw_person_data("H1", change=100.0, private=False)}
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit(before)
        entries = push.call_args[0][0]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "update")

    def test_resave_with_only_the_change_timestamp_different_is_not_pushed(self):
        # diff_items() -- the same function gramps-web-api's own
        # old_unchanged() conflict check uses server-side -- ignores
        # "change", so a resave that touched nothing else must not be
        # reported as an update.
        stub_iter_raw_data(
            self.db, {"Person": {"H1": raw_person_data("H1", change=999.0)}}
        )
        before = {("Person", "H1"): raw_person_data("H1", change=100.0)}
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit(before)
        push.assert_not_called()

    def test_untouched_handle_is_skipped(self):
        # A bulk tool that rewrote 3 of 10000 objects must push 3, not
        # 10000.
        data = raw_person_data("H1")
        stub_iter_raw_data(self.db, {"Person": {"H1": data}})
        before = {("Person", "H1"): data}
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit(before)
        push.assert_not_called()

    def test_nothing_changed_pushes_nothing(self):
        stub_iter_raw_data(self.db, {})
        with mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit({})
        push.assert_not_called()

    def test_pushes_directly_not_via_retry_after_conflict(self):
        # Bug fixed: an earlier version routed every reconstructed entry
        # through _retry_after_conflict(), whose replay reads local
        # storage at commit time -- already the batch's own result by
        # then, not the pre-batch state a real server needs. This
        # builds the correct payload directly and pushes it the normal
        # way, so _retry_after_conflict() is only ever reached (via
        # _push_payload()'s own conflict handling) if the push actually
        # conflicts.
        stub_iter_raw_data(self.db, {"Person": {"H1": raw_person_data("H1")}})
        with mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as replay, mock.patch.object(self.db, "_push_payload") as push:
            self.db._reconcile_batch_commit({})
        push.assert_called_once()
        replay.assert_not_called()

    def test_transaction_commit_routes_a_snapshotted_batch_to_reconcile(self):
        trans = FakeBatchTxn(batch=True, start_time=100.0)
        trans._webapidb_before = {("Person", "H1"): raw_person_data("H1")}
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(self.db, "_reconcile_batch_commit") as reconcile:
            self.db.transaction_commit(trans)
        reconcile.assert_called_once_with({("Person", "H1"): raw_person_data("H1")})
        # ...and does NOT also take the ordinary push path, which would
        # push an empty payload.
        self.db.web_client.push_transaction.assert_not_called()


# -------------------------------------------------------------------------
#
# TestPendingPushQueue
#
# A push that fails for a connectivity reason (rather than a conflict) is
# persisted and retried later, so an edit made while offline still
# reaches the server. See the module docstring.
#
# -------------------------------------------------------------------------
class TestPendingPushQueue(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()
        self.metadata = {}
        self.db._get_metadata = lambda key, default=0: self.metadata.get(key, default)
        self.db._set_metadata = (
            lambda key, value, use_txn=True: self.metadata.__setitem__(key, value)
        )

    def _payload(self, handle="H1"):
        return [{"type": "add", "handle": handle, "_class": "Person"}]

    def test_connection_failure_queues_the_payload(self):
        self.db.web_client.push_transaction.side_effect = HTTPError(
            "https://example.com/api/transactions/", 500, "boom", None, None
        )
        with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
            self.db._push_payload(self._payload())
        queued = self.metadata["pending_pushes"]
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["payload"], self._payload())
        self.assertFalse(queued[0]["undo"])

    def test_undo_flag_is_preserved_in_the_queue(self):
        self.db.web_client.push_transaction.side_effect = OSError("network down")
        with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
            self.db._push_payload(self._payload(), undo=True)
        self.assertTrue(self.metadata["pending_pushes"][0]["undo"])

    def test_successful_push_queues_nothing(self):
        self.db._push_payload(self._payload())
        self.assertNotIn("pending_pushes", self.metadata)

    def test_conflict_does_not_queue(self):
        # A conflict is handled by resync-and-retry, not by queueing --
        # queueing it too would push the same edit twice.
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(self.db, "_resync_after_conflict"), mock.patch.object(
            self.db, "_retry_after_conflict"
        ):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db._push_payload(self._payload())
        self.assertNotIn("pending_pushes", self.metadata)

    def test_flush_sends_queued_pushes_in_order_and_clears_them(self):
        self.metadata["pending_pushes"] = [
            {"payload": self._payload("H1"), "undo": False},
            {"payload": self._payload("H2"), "undo": False},
        ]
        with self.assertLogs(grampswebapidb.LOG, level="INFO"):
            self.db._flush_pending_pushes()
        sent = [
            c[0][0][0]["handle"]
            for c in self.db.web_client.push_transaction.call_args_list
        ]
        self.assertEqual(sent, ["H1", "H2"])
        self.assertEqual(self.metadata["pending_pushes"], [])

    def test_flush_stops_at_the_first_still_undeliverable_entry(self):
        # Order matters: a later edit may depend on an earlier one (a
        # Family referencing a Person), so a stuck entry must block the
        # rest rather than letting them jump the queue.
        self.metadata["pending_pushes"] = [
            {"payload": self._payload("H1"), "undo": False},
            {"payload": self._payload("H2"), "undo": False},
        ]
        self.db.web_client.push_transaction.side_effect = OSError("still down")
        with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
            self.db._flush_pending_pushes()
        self.assertEqual(self.db.web_client.push_transaction.call_count, 1)
        self.assertEqual(len(self.metadata["pending_pushes"]), 2)

    def test_flush_drops_a_queued_push_that_now_conflicts(self):
        # A queued payload's "old" snapshot is stale by definition, so the
        # resync-and-merge path can't be applied to it -- dropping it is
        # the honest outcome, loudly logged.
        self.metadata["pending_pushes"] = [
            {"payload": self._payload("H1"), "undo": False},
            {"payload": self._payload("H2"), "undo": False},
        ]
        self.db.web_client.push_transaction.side_effect = [
            WebApiPushConflict("Object has changed"),
            None,
        ]
        with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
            self.db._flush_pending_pushes()
        # The conflicting entry is dropped, but the one behind it still goes.
        self.assertEqual(self.db.web_client.push_transaction.call_count, 2)
        self.assertEqual(self.metadata["pending_pushes"], [])

    def test_empty_queue_makes_no_requests(self):
        self.db._flush_pending_pushes()
        self.db.web_client.push_transaction.assert_not_called()

    def test_queue_is_capped_dropping_the_oldest(self):
        self.metadata["pending_pushes"] = [
            {"payload": self._payload("H%d" % i), "undo": False}
            for i in range(grampswebapidb.MAX_PENDING_PUSHES)
        ]
        self.db.web_client.push_transaction.side_effect = OSError("network down")
        with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
            self.db._push_payload(self._payload("NEW"))
        queued = self.metadata["pending_pushes"]
        self.assertEqual(len(queued), grampswebapidb.MAX_PENDING_PUSHES)
        # Oldest dropped, newest kept.
        self.assertEqual(queued[0]["payload"][0]["handle"], "H1")
        self.assertEqual(queued[-1]["payload"][0]["handle"], "NEW")

    def test_permanent_rejection_is_not_queued(self):
        # A 403 (the account lacks write permissions) will answer the same
        # way forever -- queueing it would retry on every poll and
        # eventually evict genuinely retryable work from the capped queue.
        self.db.web_client.push_transaction.side_effect = HTTPError(
            "https://example.com/api/transactions/", 403, "Forbidden", None, None
        )
        with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
            self.db._push_payload(self._payload())
        self.assertNotIn("pending_pushes", self.metadata)

    def test_rate_limit_is_still_queued(self):
        # 429 is "try again shortly", not a refusal.
        self.db.web_client.push_transaction.side_effect = HTTPError(
            "https://example.com/api/transactions/", 429, "Too Many", None, None
        )
        with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
            self.db._push_payload(self._payload())
        self.assertEqual(len(self.metadata["pending_pushes"]), 1)

    def test_flush_drops_a_permanently_rejected_entry_and_continues(self):
        self.metadata["pending_pushes"] = [
            {"payload": self._payload("H1"), "undo": False},
            {"payload": self._payload("H2"), "undo": False},
        ]
        self.db.web_client.push_transaction.side_effect = [
            HTTPError(
                "https://example.com/api/transactions/", 403, "Forbidden", None, None
            ),
            None,
        ]
        with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
            self.db._flush_pending_pushes()
        # The rejected entry is dropped rather than blocking the queue
        # forever -- permissions may have changed since it was queued.
        self.assertEqual(self.db.web_client.push_transaction.call_count, 2)
        self.assertEqual(self.metadata["pending_pushes"], [])

    def test_sync_from_server_flushes_the_queue_first(self):
        # The queue is retried on every poll tick, not just at load().
        self.db.emit = mock.MagicMock()
        self.db.web_client.get_transaction_history.return_value = ([], 0)
        with mock.patch.object(self.db, "_flush_pending_pushes") as flush:
            self.db._sync_from_server()
        flush.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
