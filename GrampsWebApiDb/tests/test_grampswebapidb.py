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
import os
import sys
import unittest
from urllib.error import HTTPError
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

from gramps.gen.db.dbconst import REFERENCE_KEY, TXNADD, TXNDEL, TXNUPD
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.lib import Person, Tag
from gramps.gen.lib.json_utils import object_to_data, remove_object

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
        self.db._full_resync.assert_called_once_with()

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
        self.db._full_resync.assert_called_once_with()

    def test_marker_still_advances_sync_last_time(self):
        page = [{"timestamp": 42.0, "changes": []}]
        self.db.web_client.get_transaction_history.return_value = (page, 1)
        self.db._sync_from_server()
        self.assertEqual(self.metadata["sync_last_time"], 42.0)


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

        self.db.web_client.download_export.assert_called_once_with()
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


# -------------------------------------------------------------------------
#
# TestTransactionCommit
#
# -------------------------------------------------------------------------
class TestTransactionCommit(unittest.TestCase):
    def setUp(self):
        self.db = new_instance()
        self.db.web_client = mock.MagicMock()

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

    def test_conflict_triggers_resync_then_retry(self):
        # A WebApiPushConflict means the server rejected the whole batch
        # because something changed server-side since the local mirror's
        # snapshot -- the response is to resync from the server and then
        # retry the local edit on top of that fresh data (see
        # _retry_after_conflict()), not to propagate the exception (the
        # local commit already happened).
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(self.db, "_sync_from_server") as resync, mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise
        resync.assert_called_once_with()
        retry.assert_called_once()
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
            "_sync_from_server",
            side_effect=HTTPError(
                "https://example.com/api/transactions/history/", 500, "boom", None, None
            ),
        ), mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise
        # A failed resync means the mirror still doesn't reflect the
        # server, so retrying the edit on top of it would be pointless.
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
        ), mock.patch.object(self.db, "_sync_from_server") as resync, mock.patch.object(
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
        ), mock.patch.object(self.db, "_sync_from_server") as resync, mock.patch.object(
            self.db, "_retry_after_conflict"
        ) as retry:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db._push_payload(transaction_to_json(trans), undo=True)
        resync.assert_called_once_with()
        retry.assert_not_called()


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
            self.db, "_sync_from_server"
        ) as sync, mock.patch.object(
            grampswebapidb.GLib, "timeout_add_seconds", return_value=42
        ) as timeout_add:
            self.db.load("some/path")
        super_load.assert_called_once_with("some/path")
        sync.assert_called_once_with()
        timeout_add.assert_called_once_with(
            grampswebapidb.POLL_INTERVAL_SECONDS, self.db._poll_tick
        )
        self.assertEqual(self.db._poll_source_id, 42)

    def test_close_cancels_pending_poll(self):
        self.db._poll_source_id = 42
        with mock.patch.object(
            grampswebapidb.SQLite, "close"
        ) as super_close, mock.patch.object(
            grampswebapidb.GLib, "source_remove"
        ) as source_remove:
            self.db.close()
        source_remove.assert_called_once_with(42)
        self.assertIsNone(self.db._poll_source_id)
        super_close.assert_called_once_with()

    def test_close_without_a_poll_scheduled_is_a_no_op(self):
        # e.g. close() called after a failed load(), before the timeout
        # was ever scheduled.
        with mock.patch.object(
            grampswebapidb.SQLite, "close"
        ) as super_close, mock.patch.object(
            grampswebapidb.GLib, "source_remove"
        ) as source_remove:
            self.db.close()
        source_remove.assert_not_called()
        super_close.assert_called_once_with()

    def test_poll_tick_syncs_and_keeps_repeating(self):
        with mock.patch.object(self.db, "_sync_from_server") as sync:
            result = self.db._poll_tick()
        sync.assert_called_once_with()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)

    def test_poll_tick_swallows_connection_errors_and_keeps_repeating(self):
        with mock.patch.object(
            self.db, "_sync_from_server", side_effect=OSError("network down")
        ):
            with self.assertLogs(grampswebapidb.LOG, level="ERROR"):
                result = self.db._poll_tick()
        self.assertEqual(result, grampswebapidb.GLib.SOURCE_CONTINUE)


if __name__ == "__main__":
    unittest.main()
