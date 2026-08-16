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
stubs out the handle accessors and DbTxn itself, isolating the diff
logic from real commit/push machinery -- appropriate for a fast unit
suite, but exactly the isolation that let a previous fix to a
neighboring mechanism (conflict-retry) ship broken for two review
rounds: see commit 8e21ed72d, and TestConflictRetryAgainstARealDatabase
in test_grampswebapidb.py, which was written for the same reason. This
file runs a real ImportXml import and real batch=True DbTxns against a
real DBAPI-backed SQLite database (WebApiDB.__class__ reclassification,
same trick), with only the network layer (web_client) mocked, and
checks what actually gets pushed.

What it found
--------------
Three independent bugs, none caught by the mocked unit tests, each
individually sufficient to make _reconcile_batch_commit() fail to
sync real local batch changes to a real server:

1. Timestamp precision (test_update_within_the_same_wall_clock_second_
   as_batch_start_is_not_silently_missed): _reconcile_batch_commit()
   only treats a surviving handle as changed if
   ``get_obj(handle).change >= start_time``. ``.change`` is an int
   (whole seconds); ``start_time`` is a raw ``time.time()`` float. Any
   real edit that lands within the same wall-clock second the batch
   transaction began in -- the common case for a fast local tool --
   compares a truncated-down int against a float with a nonzero
   fractional part and silently fails the check. The change is never
   even attempted, let alone pushed: no entry, no log line, nothing.

2. Stale "old" snapshot (test_real_import_add_is_pushed_as_an_add_not_
   a_false_conflict, test_real_batch_update_pushes_the_pre_batch_state_
   as_old): by the time _reconcile_batch_commit() runs, the real batch
   operation has already written its result to local storage for real.
   _retry_after_conflict()'s replay then re-commits that *already-
   current* local state as a "fresh" edit, so DBAPI's own "old"
   snapshot (_commit_base()'s _get_raw_data(), read from local storage
   at commit time) captures the *post-batch* content, not what the
   server last actually saw. For a brand-new object this means "type":
   "update" with a non-None "old" instead of "type": "add" with "old":
   None; for a changed object it means "old" that already matches
   "new". Either way, a real server's own old-data check (gramps_webapi/
   api/tasks.py's old_unchanged(), confirmed by reading that source)
   compares this against what it actually holds and calls it a
   conflict -- even though nothing server-side changed at all.
   _push_payload() then does a full resync, and because this push
   already has is_retry=True (_retry_after_conflict() sets
   self._retrying for its own DbTxn, and _reconcile_batch_commit()
   goes through that same method), it gives up rather than retrying
   again -- so the entire reconstructed batch (every add and update in
   it, bundled into one push -- see the module docstring on
   WebApiPushConflict) is silently dropped, logged only as a WARNING.

3. Deletes swallowed (test_real_batch_delete_is_pushed_not_swallowed):
   _retry_after_conflict()'s delete handling is
   ``if has_handle(handle): remove(...)`` -- correct for its original
   use (a conflict retry, where "already gone" means someone else beat
   us to the delete, nothing to do). But by the time
   _reconcile_batch_commit() replays a *real* local delete, the object
   is *legitimately* already gone (the real batch operation removed it
   for real). has_handle() is therefore already False, the guard skips
   the remove() call entirely, nothing is recorded in the replay's own
   DbTxn, and the delete is never pushed to the server at all -- no
   entry, no log line, nothing.

None of these are fixed here. This file exists to pin down exactly what
is broken, with reproducible real-database evidence, before deciding
how to fix it -- see the commit/PR discussion this file was written
alongside.

Not wired into the addon's normal fast test run (this repo has no CI --
see CLAUDE.md); explicit invocation only::

    python3 -m unittest GrampsWebApiDb.tests.test_reconcile_batch_commit_real_db -v

Kept for future regression testing of this path once it's fixed --
every "current, buggy" test below asserts the *correct* behavior, so it
will start passing (and should stay passing) once the underlying bug it
documents is fixed, with no test changes needed.
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
from gramps.gen.lib import Person
from gramps.gen.lib.json_utils import object_to_data, remove_object
from gramps.gen.user import User
from gramps.plugins.importer.importxml import importData

from GrampsWebApiDb.grampswebapidb import WebApiDB

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


if __name__ == "__main__":
    unittest.main()
