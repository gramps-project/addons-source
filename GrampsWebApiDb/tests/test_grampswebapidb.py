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
from gramps.gen.lib import Person
from gramps.gen.lib.json_utils import object_to_data, remove_object

from GrampsWebApiDb import grampswebapidb
from GrampsWebApiDb.grampswebapidb import WebApiDB, WebApiPushConflict, transaction_to_json

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
        self.metadata = {}
        self.db._get_metadata = lambda key, default=0: self.metadata.get(
            key, default
        )
        self.db._set_metadata = lambda key, value, use_txn=True: self.metadata.__setitem__(
            key, value
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
        self.metadata = {}
        self.db._get_metadata = lambda key, default=0: self.metadata.get(
            key, default
        )
        self.db._set_metadata = lambda key, value, use_txn=True: self.metadata.__setitem__(
            key, value
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

    def test_conflict_triggers_resync_not_raise(self):
        # A WebApiPushConflict means the server rejected the whole batch
        # because something changed server-side since the local mirror's
        # snapshot -- the response is to resync from the server, not to
        # propagate the exception (the local commit already happened).
        trans = FakeTransaction([(0, TXNADD, "H1", None, person_data("H1"))])
        self.db.web_client.push_transaction.side_effect = WebApiPushConflict(
            "Object has changed"
        )
        with mock.patch.object(
            grampswebapidb.SQLite, "transaction_commit"
        ), mock.patch.object(self.db, "_sync_from_server") as resync:
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise
        resync.assert_called_once_with()

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
        ):
            with self.assertLogs(grampswebapidb.LOG, level="WARNING"):
                self.db.transaction_commit(trans)  # must not raise


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


if __name__ == "__main__":
    unittest.main()
