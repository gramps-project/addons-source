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
Real-database integration tests for WebApiDB._reconcile_batch_commit() --
the mechanism that is supposed to notice when a *local* batch=True
operation (a real Gramps Import, or a stock Tool like Check and Repair
Database, Media Manager, Reorder Gramps IDs, ...) added, changed, or
removed something, and push that to the server -- see the module
docstring's "Not every local batch=True commit is a pull-side replay"
section and _reconcile_batch_commit()'s own docstring.

Why this file exists, separately
---------------------------------
Every test in test_grampswebapidb.py's TestReconcileBatchCommit class
stubs out _iter_raw_data() and DbTxn itself, isolating the diff logic
from real commit/push machinery -- appropriate for a fast unit suite,
but exactly the isolation that let a previous fix to a neighboring
mechanism (conflict-retry) ship broken for two review rounds: see
commit 8e21ed72d, and TestConflictRetryAgainstARealDatabase in
test_grampswebapidb.py, which was written for the same reason. This
file runs a real ImportXml import and real batch=True DbTxns against a
real DBAPI-backed SQLite database (WebApiDB.__class__ reclassification,
same trick), with only the network layer (web_client) mocked, and
checks what actually gets pushed.

What it found (now fixed)
--------------------------
This file originally documented three independent bugs in
_reconcile_batch_commit(), none caught by the mocked unit tests, each
individually sufficient to make it fail to sync real local batch
changes to a real server -- every test below currently passes because
all three are fixed (_reconcile_batch_commit() and
_snapshot_all_objects() in grampswebapidb.py; see their docstrings for
the current design). Left here, unmodified, as the regression tests
that prove it and guard against it breaking again:

1. Timestamp precision (test_update_within_the_same_wall_clock_second_
   as_batch_start_is_not_silently_missed): the old implementation only
   treated a surviving handle as changed if
   ``get_obj(handle).change >= start_time``. ``.change`` is an int
   (whole seconds); ``start_time`` is a raw ``time.time()`` float. Any
   real edit that landed within the same wall-clock second the batch
   transaction began in -- the common case for a fast local tool --
   compared a truncated-down int against a float with a nonzero
   fractional part and silently failed the check. The change was never
   even attempted, let alone pushed: no entry, no log line, nothing.
   Fixed by comparing actual before/after content
   (gramps.gen.merge.diff.diff_items()) instead of timestamps at all.

2. Stale "old" snapshot (test_real_import_add_is_pushed_as_an_add_not_
   a_false_conflict, test_real_batch_update_pushes_the_pre_batch_state_
   as_old): by the time _reconcile_batch_commit() ran, the real batch
   operation had already written its result to local storage for real.
   The old implementation's replay (via _retry_after_conflict()) then
   re-committed that *already-current* local state as a "fresh" edit,
   so DBAPI's own "old" snapshot (_commit_base()'s _get_raw_data(),
   read from local storage at commit time) captured the *post-batch*
   content, not what the server last actually saw. For a brand-new
   object this meant "type": "update" with a non-None "old" instead of
   "type": "add" with "old": None; for a changed object it meant "old"
   that already matched "new". Either way, a real server's own old-
   data check (gramps_webapi/api/tasks.py's old_unchanged(), confirmed
   by reading that source) compared this against what it actually held
   and called it a conflict -- even though nothing server-side changed
   at all -- and because that push already had is_retry=True, it gave
   up rather than retrying, silently dropping the entire reconstructed
   batch. Fixed by capturing the true pre-transaction data up front
   (transaction_begin()'s _snapshot_all_objects() call) and building
   the payload's "old" from that, instead of from local storage at
   replay time.

3. Deletes swallowed (test_real_batch_delete_is_pushed_not_swallowed):
   _retry_after_conflict()'s delete handling is
   ``if has_handle(handle): remove(...)`` -- correct for its original
   use (a conflict retry, where "already gone" means someone else beat
   us to the delete, nothing to do). But by the time the old
   _reconcile_batch_commit() replayed a *real* local delete through it,
   the object was *legitimately* already gone (the real batch operation
   removed it for real), so has_handle() was already False, the guard
   skipped the remove() call entirely, and the delete never reached the
   server. Fixed by building the delete entry directly from the pre-
   transaction snapshot instead of replaying it through
   _retry_after_conflict() at all -- that method is now only reached
   (via _push_payload()'s own conflict handling) if a reconciliation
   push itself genuinely conflicts, the same as any other edit.

Not wired into the addon's normal fast test run (this repo has no CI --
see CLAUDE.md); explicit invocation only::

    python3 -m unittest GrampsWebApiDb.tests.test_reconcile_batch_commit_real_db -v
"""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
import copy
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

# -------------------------------------------------------------------------
#
# Make the addon importable the way Gramps loads it -- see
# test_grampswebapidb.py's comment on the same hack.
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
from gramps.gen.db.utils import make_database
from gramps.gen.lib import Note, Person, Tag
from gramps.gen.lib.json_utils import data_to_object, object_to_data, remove_object
from gramps.gen.user import User
from gramps.plugins.importer.importxml import importData

from GrampsWebApiDb.grampswebapidb import WebApiDB, WebApiPushConflict

#: A minimal, valid Gramps XML document holding one person -- enough for
#: a real ImportXml run. ImportXml strips a leading "_" off the XML
#: handle attribute (confirmed empirically: "_h...1" in the XML becomes
#: local handle "h...1"), so callers pass the XML-side spelling and read
#: back whatever ImportXml actually assigned via get_person_handles().
PERSON_XML = """<?xml version="1.0" encoding="UTF-8"?>
<database xmlns="http://gramps-project.org/xml/1.7.1/">
  <header><created date="2024-01-01" version="6.0.0"/></header>
  <people>
    <person handle="_{handle}" id="{gramps_id}">
      <gender>U</gender>
    </person>
  </people>
</database>
"""


# -------------------------------------------------------------------------
#
# TestReconcileBatchCommitAgainstARealDatabase
#
# -------------------------------------------------------------------------
class TestReconcileBatchCommitAgainstARealDatabase(unittest.TestCase):
    def setUp(self):
        tmpdir = tempfile.mkdtemp(prefix="grampswebapidb_reconcile_test_")
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        self.tmpdir = tmpdir
        db = make_database("sqlite")
        db.load(tmpdir)
        # Same reclassification trick as TestConflictRetryAgainstARealDatabase
        # in test_grampswebapidb.py -- a real, already-initialized DBAPI
        # backend, without going through WebApiDB's network-dependent load().
        db.__class__ = WebApiDB
        db.web_client = mock.MagicMock()
        db._syncing = False
        db._retrying = False
        db._pulling = False
        db._get_metadata = lambda key, default=0: default
        db._set_metadata = lambda key, value, use_txn=True: None
        self.db = db
        self.addCleanup(self.db.close)
        self.pushes = []

        def fake_push(payload, undo=False, background=False, on_wait=None):
            self.pushes.append(copy.deepcopy(payload))

        self.db.web_client.push_transaction.side_effect = fake_push

    def _seed_person(self, privacy=False):
        """Add a person via a plain (non-batch) commit -- standing in for
        an object already synced with the server, the same way a fresh
        WebApiDB mirror would hold it. Its own push is not what these
        tests are about, so the recorder is cleared afterward."""
        with DbTxn("seed", self.db) as trans:
            person = Person()
            person.set_gramps_id("I0001")
            person.set_privacy(privacy)
            self.db.add_person(person, trans)
            handle = person.handle
        self.pushes.clear()
        return handle

    def _import_xml(self, xml_text, filename="import.gramps"):
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w") as f:
            f.write(xml_text)
        importData(self.db, path, User())

    # -- Bug 1: timestamp precision -------------------------------------

    def test_update_within_the_same_wall_clock_second_as_batch_start_is_not_silently_missed(
        self,
    ):
        # A real external batch tool (Check and Repair Database, Media
        # Manager, ...) modifying an existing object typically finishes
        # within the same wall-clock second it started in -- this must
        # still be detected and pushed, not silently skipped because
        # get_obj(handle).change (whole seconds) happens to compare less
        # than transaction.start_time (a time.time() float).
        handle = self._seed_person()
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            person = self.db.get_person_from_handle(handle)
            person.set_privacy(True)
            self.db.commit_person(person, trans)
        self.assertEqual(
            len(self.pushes),
            1,
            "a same-second local edit made by a real batch tool must "
            "still be reconciled and pushed",
        )

    # -- Bug 2: stale "old" snapshot -------------------------------------

    def test_real_import_add_is_pushed_as_an_add_not_a_false_conflict(self):
        # A real ImportXml run (its own batch=True DbTxn, opened
        # internally -- not by this addon) adding a brand-new person must
        # be reconstructed as an "add" with "old": None, the same as any
        # other first-time local add -- not "update" with the object's
        # own just-committed data as "old", which a real server (which
        # has never seen this handle) always rejects as a conflict.
        self._import_xml(
            PERSON_XML.format(handle="h" + "0" * 19 + "1", gramps_id="I0001")
        )
        self.assertEqual(len(self.pushes), 1)
        entry = self.pushes[0][0]
        self.assertEqual(entry["type"], "add")
        self.assertIsNone(entry["old"])

    def test_real_batch_update_pushes_the_pre_batch_state_as_old(self):
        # A real external batch tool modifying an existing, already-
        # synced object must push "old" as what was last known-synced
        # (pre-batch) -- what the server actually still has -- not what
        # the batch tool just wrote locally, or a real server's
        # old-data check rejects it as a conflict even though nothing
        # server-side changed.
        handle = self._seed_person(privacy=False)
        pre_batch = remove_object(
            object_to_data(self.db.get_person_from_handle(handle))
        )
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            # Sidesteps bug 1 (already covered by its own test above) so
            # this test isolates bug 2 only.
            trans.start_time -= 10
            person = self.db.get_person_from_handle(handle)
            person.set_privacy(True)
            self.db.commit_person(person, trans)
        self.assertEqual(len(self.pushes), 1)
        entry = self.pushes[0][0]
        self.assertEqual(entry["type"], "update")
        self.assertEqual(entry["old"], pre_batch)
        self.assertTrue(entry["new"]["private"])

    # -- Bug 3: deletes swallowed -----------------------------------------

    def test_real_batch_delete_is_pushed_not_swallowed(self):
        # A real external batch tool removing an existing object inside
        # its own batch=True DbTxn must still reach the server as a
        # "delete" entry -- _retry_after_conflict()'s has_handle() guard
        # (correct for an actual conflict retry, where "already gone"
        # means someone else's delete beat ours) must not also treat a
        # delete this addon's own reconciliation is replaying as
        # "nothing to do", just because the real batch delete already
        # removed it locally by the time the replay runs.
        handle = self._seed_person()
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            trans.start_time -= 10  # isolate from bug 1, as above
            self.db.remove_person(handle, trans)
        self.assertFalse(self.db.has_person_handle(handle))
        self.assertEqual(len(self.pushes), 1)
        entry = self.pushes[0][0]
        self.assertEqual(entry["type"], "delete")
        self.assertEqual(entry["handle"], handle)

    # -- Sanity: untouched objects are left alone -------------------------

    def test_objects_the_batch_did_not_touch_are_not_pushed(self):
        untouched = self._seed_person()
        handle = self._seed_person()
        # Backdating start_time by as much as the bug-2/3 tests above do
        # (10s) would also pull it before *untouched*'s own .change,
        # making it look touched too -- that's bug 1 again, just aimed
        # at the wrong object. A 2s real sleep plus a 1s backdate keeps
        # comfortable margin on both sides: well after untouched/handle's
        # original .change, and well before the edit's own -- isolating
        # this test from bug 1 without reintroducing a false positive.
        time.sleep(2)
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            trans.start_time -= 1
            person = self.db.get_person_from_handle(handle)
            person.set_privacy(True)
            self.db.commit_person(person, trans)
        self.assertEqual(len(self.pushes), 1)
        touched_handles = {e["handle"] for e in self.pushes[0]}
        self.assertEqual(touched_handles, {handle})
        self.assertNotIn(untouched, touched_handles)

    # -- Additional edge cases -------------------------------------------

    def test_a_resave_with_no_real_change_is_not_pushed(self):
        # Some tools (Check and Repair among them) re-commit an object
        # even when nothing about it actually needed fixing. That must
        # not be reported as an update -- diff_items() ignores "change"
        # (the timestamp _commit_base() bumps on every commit,
        # unconditionally), the same as gramps-web-api's own
        # old_unchanged() conflict check does server-side.
        handle = self._seed_person()
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            person = self.db.get_person_from_handle(handle)
            self.db.commit_person(person, trans)
        self.assertEqual(len(self.pushes), 0)

    def test_multiple_object_types_in_one_batch_are_all_reconciled(self):
        # _reconcile_batch_commit() walks every entry in CLASS_TO_KEY_MAP,
        # not just Person -- a real batch tool touching several object
        # types at once (e.g. Check and Repair fixing both people and
        # tags) must have all of them reconciled together in one push.
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            person = Person()
            person.set_gramps_id("I0002")
            self.db.add_person(person, trans)
            tag = Tag()
            tag.set_name("A Tag")
            self.db.add_tag(tag, trans)
        self.assertEqual(len(self.pushes), 1)
        entries = {(e["_class"], e["type"]) for e in self.pushes[0]}
        self.assertEqual(entries, {("Person", "add"), ("Tag", "add")})

    def test_add_update_and_delete_together_in_one_batch_are_all_reconciled(self):
        keep = self._seed_person()
        gone = self._seed_person()
        pre_batch_keep = remove_object(
            object_to_data(self.db.get_person_from_handle(keep))
        )
        with DbTxn("simulated batch tool", self.db, batch=True) as trans:
            new_person = Person()
            new_person.set_gramps_id("I0099")
            self.db.add_person(new_person, trans)
            added = new_person.handle

            person = self.db.get_person_from_handle(keep)
            person.set_privacy(True)
            self.db.commit_person(person, trans)

            self.db.remove_person(gone, trans)

        self.assertEqual(len(self.pushes), 1)
        by_handle = {e["handle"]: e for e in self.pushes[0]}
        self.assertEqual(set(by_handle), {added, keep, gone})
        self.assertEqual(by_handle[added]["type"], "add")
        self.assertIsNone(by_handle[added]["old"])
        self.assertEqual(by_handle[keep]["type"], "update")
        self.assertEqual(by_handle[keep]["old"], pre_batch_keep)
        self.assertTrue(by_handle[keep]["new"]["private"])
        self.assertEqual(by_handle[gone]["type"], "delete")
        self.assertIsNone(by_handle[gone]["new"])

    def test_a_genuine_conflict_on_the_reconciliation_push_recovers_via_full_resync(
        self,
    ):
        # If the server's own copy of a touched object really did change
        # in the narrow window between this addon's before-snapshot and
        # the reconciliation push actually going out, the push must get
        # the same recovery any other edit's conflict gets (full resync,
        # then a retry) -- not a special case, and not silently dropped.
        handle = self._seed_person(privacy=False)
        server_fresh = copy.deepcopy(
            remove_object(object_to_data(self.db.get_person_from_handle(handle)))
        )
        server_fresh["private"] = True  # changed server-side, unknown to us

        calls = []

        def fake_push(payload, undo=False, background=False, on_wait=None):
            calls.append(copy.deepcopy(payload))
            if len(calls) == 1:
                raise WebApiPushConflict("Object has changed")

        self.db.web_client.push_transaction.side_effect = fake_push

        def fake_full_resync():
            self.db._pulling = True
            try:
                with DbTxn("fake resync", self.db, batch=True) as trans:
                    self.db.commit_person(data_to_object(server_fresh), trans)
            finally:
                self.db._pulling = False

        with mock.patch.object(self.db, "_full_resync", side_effect=fake_full_resync):
            with DbTxn("simulated batch tool", self.db, batch=True) as trans:
                person = self.db.get_person_from_handle(handle)
                # A list-valued field, not a scalar one: _merge_or_
                # overwrite()'s merge() only unions list fields, so this
                # is what actually verifies the local edit survives
                # alongside the server's own (scalar) change, rather than
                # one silently overwriting the other -- see that
                # function's own docstring on the scalar-field caveat.
                note = Note()
                note.set_handle("N-local")
                self.db.add_note(note, trans)
                person.add_note("N-local")
                self.db.commit_person(person, trans)

        self.assertEqual(len(calls), 2)
        final = self.db.get_person_from_handle(handle)
        # Server's concurrent change survived...
        self.assertTrue(final.get_privacy())
        # ...and so did the local batch's own edit.
        self.assertIn("N-local", final.get_note_list())


if __name__ == "__main__":
    unittest.main()
