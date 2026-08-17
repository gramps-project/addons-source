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
Database backend that mirrors a Gramps Web API server locally.

Design
------
This subclasses the stock SQLite DBAPI backend rather than DbReadBase /
DbWriteBase directly. DbGeneric (gramps.gen.db.generic) already implements
every get_*_from_handle / iter_* / get_number_of_* method generically on
top of a small Connection-like object (execute/fetchone/fetchall/commit/
table_exists/...) -- see SQLite in gramps/plugins/db/dbapi/sqlite.py. So
reads only need a local, fast, complete SQLite mirror; nothing above the
Connection layer needs reimplementing.

The mirror is kept current via GET /api/transactions/history/?after=<ts>,
the same per-object transaction log gramps-web-api's own undo system uses
(gramps_webapi/undodb.py's DbUndoSQLWeb.get_transactions()). Confirmed
against a live server: each entry is a *transaction* dict with a nested
"changes" list, each change carrying obj_class ("Person", "Family", ...),
trans_type (TXNADD=0/TXNUPD=1/TXNDEL=2), obj_handle, and -- when the
"new" query param is set -- new_data, a "_class"-tagged dict in the same
shape gramps.gen.lib.json_utils.data_to_object() reconstructs objects
from (it's literally what the server's own object_to_data(obj) produced
when the change was committed). So syncing is: remember the timestamp of
the last transaction applied, ask for everything after it, and for each
change either data_to_object(new_data) + commit_<type>() (add and update
both being upserts, no need to distinguish) or remove_<type>() for a
delete.

This "_class"-tagged new_data shape is only produced by gramps-web-api
servers running against Gramps >= 6.0; a server still on Gramps 5.2 (e.g.
gramps-web-api itself untouched) serializes objects differently (no
"_class"/"value"/"string" triplet on GrampsType-derived fields), and
data_to_object() raises KeyError on it. Confirmed against a live gramps52
server: read-only endpoints (auth, /trees/, /people/ counts, etc.) work
fine, but _sync_from_server_async() cannot deserialize its transaction history.

Credentials come from a single environment variable, GRAMPS_WEB_API_KEY
(see webapi_client.py for its "<REFRESH_TOKEN>*<BASE64URL(URL)>" shape and
the tradeoffs of using a refresh token here rather than a real scoped
personal-access-token). There is deliberately no per-tree settings.ini and
no login dialog: the same env var also works as a bare SDK credential
(WebApiHandler.from_env()) for scripts that talk to the server directly,
without going through Gramps at all -- one credential, two consumers.

Because of that, nothing but the Family Tree's own name ties its local
mirror to one particular server account. _check_identity_async() requires that
name to be "<username>@<host>" (modulo Gramps' own filename-safe-character
substitution on tree names, e.g. dots -> underscores -- see
_FAMILY_TREE_NAME_UNSAFE_CHARS) for whoever GRAMPS_WEB_API_KEY currently
authenticates as, checked on every load() -- so pointing the env var at a
different account while reopening the same Family Tree fails loudly
instead of quietly mixing that account's data into the old mirror.

Write-through (local edits pushed back to the server) hooks
transaction_commit() rather than the individual commit_person/
commit_family/... methods: DbTxn.__exit__ calls self.db.transaction_commit
(gramps/gen/db/txn.py) exactly once per completed local transaction, and
DbTxn already accumulates every add/update/delete in that transaction via
its own get_recnos()/get_record() -- transaction_to_json() below turns
that into the flat {type, handle, _class, old, new} list POST
/transactions/ expects (confirmed against base.py's own POST /people/
handler, which builds its response the same way). This must run *before*
super().transaction_commit(), since DBAPI.transaction_commit() clears the
transaction's records as its last step.

The other place a DbTxn gets used is _sync_from_server_async() itself, applying
server-pulled changes -- that uses batch=True, and DBAPI._commit_base()
skips trans.add() entirely for batch transactions (see dbapi.py), so
transaction_to_json() naturally sees nothing there and no push happens.
No separate "am I currently syncing" flag is needed to stop synced
changes from being echoed straight back to the server.

_sync_from_server_async() can only replay what the history feed actually
logged, and a batch=True commit -- any bulk import, merge, or tool run
through gramps-web-api, not just a one-off -- logs nothing per-object:
DBAPI's own commit_*/remove_* methods guard their trans.add() undo-log
call with `if not trans.batch`, so a batch transaction leaves behind an
empty-changes marker (a real Transaction row, but with no Change rows)
instead of the usual per-object entries. Confirmed live: bulk-importing
example.gramps produced exactly one such marker, and the 2157 people it
added were otherwise invisible to this addon's sync no matter how often
it resynced, because the transaction history itself never recorded
them. _sync_from_server_async() treats an empty-changes transaction as a
signal that its history-replay approach cannot describe what happened,
and falls back to _full_resync_async() -- downloading the server's current
full Gramps XML export and reimporting it into a wiped local mirror,
the only way to recover completeness when the incremental feed has a
blind spot by construction.

An empty-changes marker is not the only shape that blind spot takes: a
server whose tree was populated without gramps-web-api recording any
history at all (a server-side import straight into the database, a
restored dump, a truncated history table) has no history to describe
what it holds -- https://demo.grampsweb.org is exactly that, 4668 people
against a history that was empty until someone edited it through the
API. Replaying such a feed produces a mirror holding only the few edits
the history does know about, with nothing to distinguish that from a
correct sync. load() therefore checks the mirror's own object total
against the server's after each sync (_mirror_is_short_of_the_server_async(),
via _sync_from_server_async()'s verify_totals) and routes a shortfall to the
same _full_resync_async(). Comparing totals rather than watching for an empty
feed is what makes the case detectable: one API edit against such a
server is enough for the feed to hand back a transaction and for the
sync to look like it worked.

Pushes go out without force=1, so the server compares each item's "old"
snapshot against its own current data and rejects the whole batch with
WebApiPushConflict (see webapi_client.push_transaction()) if anything
changed server-side since the local mirror last synced -- a real, if
coarse, optimistic-concurrency check: the whole push either applies or
none of it does, with no indication of which item conflicted.

The incremental history feed can't be trusted to explain a conflict, and
this is not a one-server edge case: gramps-web-api's bulk-import path
(POST /importers/<ext>/file -- GEDCOM, Gramps XML, CSV, ...) runs the
same batch=True import machinery a local Gramps client's own Import menu
action would, which never touches its transaction-history table at all
(DBAPI's own _commit_base() only calls trans.add() when `not
trans.batch`) -- ordinary server administration for any real
installation, not a quirk of any particular one. So the incremental
history feed can be blind to an object's true current state from the
moment it was imported, indefinitely -- and a totals comparison
(_mirror_is_short_of_the_server_async(), the verify_totals check load() and
_sync_from_server_async() use elsewhere) can't catch this either, since the
object count doesn't change when an already-known object's content
changes server-side, only when objects are added or removed.

A per-object fix was tried and doesn't work: gramps-web-api's REST
single-object endpoints (GET /<type>/<handle>) serialize with
GrampsJSONEncoder.extract_object() (gramps_webapi/api/resources/
emit.py) -- a walk of the object's own __dict__/properties for the
frontend's display schema, with no "_class" tag on GrampsType-derived
fields -- not the gramps.gen.lib.json_utils shape data_to_object()
needs to reconstruct a Gramps object; feeding it that shape raises
KeyError. Only two things produce the compatible shape: the
transaction-history feed's new_data, and a raw Gramps XML export (see
_full_resync_async()). So on a conflict, _push_payload_async() below does a full
resync (_resync_after_conflict_async(), reusing _full_resync_async()) -- expensive,
but the only server round-trip that reliably brings the local mirror
back to the server's true current state for whatever this push touched
-- and then, for a plain commit (not an undo/redo -- see
_retry_after_conflict()), replays the intended *new* state as a fresh
local edit via commit_<type>()/remove_<type>(). That fresh edit goes
through the normal transaction_commit() -> _start_push() path again
with is_retry=True, so it now carries an "old" snapshot matching the
just-resynced mirror, and will only be rejected a second time if
something changes server-side in the brief window since the resync ran
-- in which case it is logged and dropped rather than retried again, to
avoid retrying forever against a genuinely hot object.

A Gramps XML export isn't perfectly round-trip-faithful either, though:
it has no element for Person.birth_ref_index/death_ref_index (see
exportxml.py's write_person()), so ImportXml recomputes both from
document order on the way back in instead of preserving them -- wrong
whenever the true index was -1 despite a BIRTH/DEATH-type event ref
existing, or pointed at something other than the first such ref. Since
diff_items() (the same function old_unchanged() uses server-side) treats
those two fields as ordinary content, a Person whose true index doesn't
match that heuristic would otherwise disagree with the server after
every single resync, forever, for reasons unrelated to anything actually
edited. _snapshot_birth_death_indices()/_restore_birth_death_indices()
carry the pre-resync value back across the reimport for any Person whose
event_ref_list didn't itself change, closing that gap.

For an add/update whose object still exists server-side (i.e. the
conflicting edit changed the same object rather than deleting it),
_merge_or_overwrite() below combines the two edits with the object's own
merge() -- the same list-unioning logic behind Gramps' Merge People/
Family/... tools (ported from GrampsWebSync's diffhandler.py, credit
David Straub, same license) -- rather than letting the retry blindly
clobber whatever the other side changed. merge(current, acquisition) is
called as current.merge(acquisition) with current the server's post-
resync copy and acquisition the local edit, so a *list*-valued field
(notes, citations, media, urls, event/family refs, tags, ...) is
unioned -- both sides' items survive -- and any other field merge()
doesn't specially handle is simply left as current's own value, with
acquisition's silently discarded (confirmed empirically:
merge(FEMALE-current, MALE-local) keeps FEMALE) -- the *opposite* of
"local overwrites remote". Two fields do get their own special-cased
merge instead of either of those: privacy is OR'd
(PrivacyBase._merge_privacy(): ``self.private = self.private or
other.private``, so the merged object is private if either side marked
it private -- confirmed the same way), and Person.merge() keeps
current's own primary name but demotes acquisition's into current's
alternate_names list rather than discarding it. Real field-level
conflict *resolution* for the plain-scalar case (diff, prompt the user)
is still out of scope. If the push fails for a non-conflict reason
(network error, auth failure), the local commit has already happened and
is not rolled back -- the local mirror just drifts from the server until
the next successful push or read sync.

Not every local batch=True commit is a pull-side replay, though: the same
trans.batch guard that makes _sync_from_server_async()'s own replay silent to
transaction_to_json() applies equally to *local* bulk operations run
against this open tree from outside this file entirely -- ImportXml/
ImportGedcom/ImportCsv/..., and stock Tools like Check and Repair
Database, Media Manager, Extract Information from Names, Rename Event
Types, Reorder Gramps IDs, and Sort Events all open their own DbTxn with
batch=True for performance. Left alone, any of those would apply locally
and never reach the server: transaction_commit() would see the same empty
transaction_to_json() payload it correctly sees for _sync_from_server_async()'s
own pull-side batch replay, with nothing in the payload itself to tell the
two apart. transaction_begin() (called by DbTxn.__enter__, so before the
batch operation's body runs) tells them apart with a _pulling flag set
only around _sync_from_server_async()'s own batch DbTxns (including the ones
_full_resync_async() opens) -- everywhere else, a batch=True transaction gets a
full snapshot of every primary object's current data stashed on the
transaction itself (_snapshot_all_objects()), not just which handles
exist. transaction_commit() diffs that snapshot against a fresh one taken
right after the commit (_reconcile_batch_commit()) to reconstruct what
changed: a handle that appeared is an add ("old": None); one that
disappeared is a delete ("old" the pre-transaction data); one that
persisted is an update only if its content actually differs, compared
with gramps.gen.merge.diff.diff_items() -- the same function gramps-web-
api's own old_unchanged() conflict check uses server-side, so this
addon's "did it change" agrees with the server's. (An earlier version of
this used handle presence plus a `.change`-timestamp comparison instead
of a real content diff, and replayed each reconstructed entry through
_retry_after_conflict() to pick up an "old" snapshot -- three separate
bugs followed from that: `.change` (whole seconds) compared against the
transaction's own start_time (a sub-second float) silently missed any
edit landing in the same wall-clock second the batch began in, which is
the common case; replaying against local storage that by then already
held the batch's own result sent the object's *post*-batch content as
"old" instead of what the server last actually saw, which a real
server's own old-data check always reads as a conflict; and replaying a
delete against storage where the object was already legitimately gone
did nothing at all. Building the payload directly from the two
snapshots, with real "old" data captured before anything ran, avoids
all three.) The reconstructed payload goes out through the normal
transaction_commit() -> _start_push() path, with the same conflict
handling (full resync, then _retry_after_conflict()) any other edit
gets, for the rare case something else changed the same object in the
meantime. Reading (and briefly holding in memory) two full copies of
every primary object's data per batch commit is a real cost, but
_snapshot_all_objects() keeps it to O(types) bulk queries rather than
O(handles) individual ones, and correctness here is worth more than the
memory -- the same trade _full_resync_async() already makes for the
equivalent pull-side blind spot.

A second, previously-unhandled kind of silent drift: when a push's own
HTTP call fails for a plain connectivity reason (network down, server
unreachable -- not a conflict), the local commit has already happened and
is never rolled back, but until now nothing remembered that the push
still needed to go out -- "the next successful push or read sync" above
was aspirational, not implemented. _push_payload_async() now persists such a
payload (via _set_metadata(), the same mechanism sync_last_time already
uses, so it survives close()/reopen) to a "pending_pushes" queue instead
of just logging and forgetting it. _flush_pending_pushes_async(), called at the
top of every _sync_from_server_async() (both the load()-time call and every
poll tick), retries the queue in order and stops at the first entry that
still can't be delivered, rather than skipping ahead -- so a later,
causally-dependent edit (e.g. a Family added after the Person it
references) can never reach the server ahead of an earlier one still
stuck behind a connectivity failure.

Not every push failure is worth queueing, though: a 4xx other than 429 is
the server's considered answer about the request itself and will not
change on replay, so _is_retryable_push_error() sends those straight to a
loud log instead -- queueing one would retry it on every poll forever and
eventually evict genuinely retryable work from the capped queue.

The most likely such rejection is a permissions one, and _check_
permissions() heads it off at load() rather than letting every subsequent
edit fail: gramps-web-api gates POST /transactions/ behind all three of
AddObject/EditObject/DeleteObject at once (transactions.py's
require_permissions(); has_permissions() fails if any are missing), and
gates GET /transactions/history/ behind ViewPrivate. ViewPrivate is the
one whose absence would otherwise be *silent* rather than merely fatal:
the history feed 403s loudly without it, but GET /exporters/gramps/file
does not refuse the request at all -- it passes
view_private=has_permissions({PERM_VIEW_PRIVATE}) into the export task
(exporters.py), so an under-privileged caller gets a privacy-filtered
export, which _full_resync_async() would then import over a wiped local mirror,
quietly dropping every private record from the mirror. Checking the
permission set up front costs no extra round trip (gramps-web-api puts it
in the access token's own claims, so get_permissions() just decodes the
JWT already in hand) and names exactly what is missing. A tree opened
read-only (DBMODE_R) never pushes, so it is held to the read permission
only.

GET /metadata/ (cached per handler; needs no special permission) supplies
the two versions the addon reasons about. The server's *Gramps* version
gates compatibility outright: _check_server_version_async() refuses at load()
below MIN_SERVER_GRAMPS_VERSION, since anything older serializes its
transaction history in the pre-6.0 shape and would otherwise fail much
later as a bare KeyError out of data_to_object() mid-sync. It is
deliberately lenient about a server that reports no parseable version at
all -- better to try than to block on a guess.

The server's *gramps-web-api* version gates one optimization: from 2.7,
POST /transactions/ accepts ?background=1, queueing the work and
answering 202 immediately instead of holding the connection open while it
processes. _push_payload_async() uses that only for payloads at or above
BACKGROUND_PUSH_THRESHOLD, where server-side processing could plausibly
outlast webapi_client.TIMEOUT and drop the connection mid-write -- most of
all the single large payload _reconcile_batch_commit() builds after a bulk
import. Everything smaller stays synchronous, which is simpler and keeps
the crisp "400 means conflict" semantics. Two asymmetries make the
backgrounded path trickier than just adding a query parameter, both
absorbed inside push_transaction() so callers see identical behavior
either way: the server only really backgrounds the work if it has a Celery
queue configured (otherwise it runs inline and answers 200, so 202 means
"poll GET /tasks/<id>" and 200 means "already done"), and on that inline
path a conflict comes back as HTTP 500 rather than 400, because run_task()
catches process_transactions()'s ValueError and re-aborts it (see
gramps_webapi/api/tasks.py). Both 400 and 500 are therefore checked for
the "Object has changed" sentinel, and a failed background task is
inspected for it too -- otherwise a conflict on that path would read as a
transient server error and be queued for retry forever.

The mirror stays current while the tree is open, not just at load() time:
load() also schedules a GLib.timeout_add_seconds() tick (POLL_INTERVAL_SECONDS)
that re-runs _sync_from_server_async() for as long as the database stays
open -- the same timestamp-cursor poll gramps-connect's browser client uses
against this same endpoint (see gramps-connect's store/historyPoll.ts), so a
change made from any other client shows up here without closing and
reopening the tree. Its network legs run on a worker thread (see "Keeping
the GUI alive" below), so a poll's round trip no longer costs the window a
UI pause the way it once did. close() cancels the pending timeout so a
closed database doesn't keep polling.

A server that stops answering does not interrupt the session: the poll
reports the outage once, backs off towards POLL_BACKOFF_MAX_SECONDS while
it lasts, and picks the mirror up again from the persisted sync cursor on
the first tick that succeeds -- meanwhile local edits go on working
against the mirror and queue for push (see _queue_pending_push()). See
_poll_tick() and _record_poll_failure().

Keeping the GUI alive
---------------------
Every network round trip this addon makes runs on a worker thread
(taskrunner.py's IoRunner), never on the GTK main thread -- so nothing here
can hold the window unresponsive the way blocking network I/O on the main
thread would, and there is nothing to interleave with the main loop's own
event processing while a sync, push, or resync is in flight. Everything
that touches self.dbapi (a commit, a DbTxn, importData()'s reimport) stays
on the main thread instead, dispatched via GLibTaskRunner -- the sqlite
backend binds a connection to its creating thread, so a DB step can never
run anywhere else. Each such step is written as one method call that
starts, runs to completion, and returns, with the *next* step (on either
runner) scheduled only once it has -- see _push_payload_async(),
_full_resync_async(), _sync_from_server_async()/_sync_page(), and
_sync_media_files_async() for the actual chains.

This wasn't always true: earlier versions of this addon ran all of that
network work synchronously on the GTK main thread and periodically called
_pump_main_loop() (still present, now with exactly one caller --
_run_async_to_completion(), see below) to hand the loop back its turn
mid-operation, the same tactic viewmanager.py's own autobackup timer uses.
That reentrancy caused two separate crashes in the field: switching Family
Trees while a pump-driven sync was suspended mid-operation resumed against
an already-closed self.dbapi (sqlite3.ProgrammingError), and a HandleError
raised by an unrelated view's redraw, dispatched from a pending GTK
callback during a pump, propagated straight up through an otherwise-
successful WebApiPushConflict recovery and crashed the whole application.
Both are structurally impossible now: there is no reentrant pump inside
any of the chains above for another GTK event to interleave with, and
close() can only ever run strictly before or strictly after one of these
main-thread steps, never during one.

A callback scheduled on a worker thread can still find, by the time it's
delivered back to the main thread, that close() ran while it was in
flight -- switching Family Trees or quitting Gramps is a perfectly
ordinary GTK event, unrelated to whatever network call happens to be
outstanding. self._run_id, a generation counter close() bumps before
anything else it does, and self._guarded() (a decorator-like wrapper
applied to a step's on_success/on_error before handing it to a runner)
together replace what _DatabaseClosed/_guarded_pump()/self._closed used to
do for the old pump-based reentrancy: a self._guarded()-wrapped callback
whose captured run_id no longer matches self._run_id is silently dropped
rather than run, instead of raising an exception for some caller further
up a call stack to catch. Some DB-touching steps (_full_resync_async()'s
rebuild(), _after_conflict_resync()'s run_retry()) go further and re-check
self._run_id themselves as their very first action, before touching
self.dbapi at all -- needed wherever a step is scheduled from inside a
callback that already ran (so self._guarded() has already let it through
once) rather than scheduled directly by the top-level caller that claimed
self._syncing; see either method's own comments for the narrow scheduling
gap this closes.

self._syncing is the single-flight gate stopping two such chains from
running concurrently and landing overlapping DB-apply callbacks against
the same local mirror: the true top-level entry point for a given
operation (_start_push(), _poll_tick(), _media_poll_tick(), load()'s
wait-adapter) claims it before anything touches the network, and only
_finish_async_op() -- wrapping that operation's real completion, including
any conflict-recovery detour a push takes through a full resync and retry
-- releases it, once the whole chain has actually finished, not merely
started. A push arriving while self._syncing is already held is queued
(_queue_pending_push()) rather than raced against whatever is in flight;
_finish_async_op() attempts one flush of that queue before releasing the
flag, so a deferred push goes out as soon as the chain that pre-empted it
finishes rather than waiting for the next poll tick.

load() is the one entry point that still needs a synchronous answer:
Gramps core's own DbGeneric.load() contract requires the tree to be ready
by the time it returns, unlike every other entry point in this file, which
starts a chain and returns immediately. _run_async_to_completion() bridges
that gap -- the *only* remaining caller of _guarded_pump()/
_pump_main_loop() -- by driving one of the async chains above to
completion synchronously: pumping the main loop (so the worker-thread
dispatch that chain depends on can actually be delivered), but never
touching self.dbapi itself while doing so, and never reentering any of
this addon's own DB-touching steps. See that method's own docstring.

Tracing a session
-----------------
Most of what this addon does is invisible from the Gramps UI: a sync that
finds nothing, a push that succeeded, a mirror quietly short of the
server. Both this module and webapi_client.py log to ".grampswebapidb",
so::

    gramps -d .grampswebapidb

turns on a DEBUG trace of exactly that (argparser.py's -d hands the name
to logging.getLogger().setLevel()). It is deliberately per-operation
rather than per-object: one line per HTTP request (method, path, status,
round-trip time -- WebApiHandler._open()), one per sync page and one per
sync (changes applied/skipped, cursor, elapsed), plus load, push, queue
depth, media transfer counts, and the local-vs-server totals compared at
load. Nothing logs object data or credentials, and replaying a busy feed
costs a fixed handful of lines rather than one per change.

A second, independent timeout (MEDIA_POLL_INTERVAL_SECONDS, coarser than
POLL_INTERVAL_SECONDS) drives _sync_media_files_async(): downloading media files
that exist as Media-object records in the mirror but not on local disk,
and uploading local media files the server doesn't have yet. This is
ported from GrampsWebSync's own media-file-sync step (grampswebsync.py's
file_confirmation/file_progress wizard pages, webapihandler.py's
get_missing_files()/download_media_file()/upload_media_file() -- same
repo, same license, credit David Straub), but runs unattended on its own
timer here instead of as an explicit user-driven wizard step with its own
progress UI. It is a separate, coarser timer rather than piggybacking on
_poll_tick() because, unlike the record-history feed, there is no cheap
"what changed since last time" signal for file presence -- every pass
re-checks every local Media object's file with os.path.exists() and
re-asks the server's own GET /media/?filemissing=1 endpoint, and anything
found missing is then transferred in full.

_sync_from_server_async()'s replay runs inside a batch=True DbTxn deliberately
(see the write-through section below for why), but that has a side effect
beyond suppressing trans.add(): DBAPI.transaction_commit() only emits its
person-add/family-update/event-delete/... signals `if not transaction.batch`
(see dbapi.py), so a batch replay is otherwise invisible to every
already-open GTK view -- the local mirror would update on disk with nothing
on screen changing. _emit_change_signals() reproduces just that signal half
by hand, once per synced page, using the exact same
KEY_TO_NAME_MAP[key] + {"add"/"update"/"delete"} signal names DBAPI itself
emits for a normal (non-batch) local edit -- so every view refreshes exactly
the way it already knows how to for a local change, with no new view-side
code needed. Collapsed to one signal per (obj_class, handle) -- the net
effect across everything applied in that page, so e.g. an update
immediately followed by a delete of the same object only fires the delete
signal, not both.

A _full_resync_async() (see below) is the one path that doesn't go through
_emit_change_signals(): a full wipe-and-reimport is exactly the "too much
changed to describe incrementally" case DbGeneric's own request_rebuild()
exists for (it emits a single <type>-rebuild signal per object type,
telling every view to reload wholesale rather than replay a specific
add/update/delete) -- so _full_resync_async() calls that once after a successful
reimport instead.

Undo/redo integration hooks undo()/redo() the same way transaction_commit()
hooks commits: Gramps core's own DbGenericUndo._undo()/_redo()
(gramps/gen/db/generic.py) revert the local mirror directly via low-level
_txn_begin()/undo_data()/_txn_commit() calls that never go through
transaction_commit(), so without this override a local Undo/Redo would
silently desync the server -- worse than a push conflict, since nothing
would even be logged. The fix reuses transaction_to_json() on the DbTxn
DbGenericUndo already stores in its undo/redo queues (the same object
transaction_commit() turned into a payload the first time), then pushes
it again: undo() sends it to POST /transactions/?undo=1, where the server
reverses it itself (swaps old/new, add<->delete -- see
gramps_webapi/api/resources/util.py's reverse_transaction()); redo() just
pushes the original forward payload again, no different from a fresh
commit. Both go through the same conflict-detection/resync path as a
normal commit. Gramps' own undo history is in-memory/per-session, not
persisted, so this only ever matters within a single running session.
"""

import inspect
import json
import logging
import os
import re
from copy import deepcopy
from tempfile import NamedTemporaryFile
from time import monotonic, time
from urllib.error import HTTPError, URLError

from gi.repository import GLib

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.constfunc import has_display
from gramps.gen.db import DbTxn
from gramps.gen.db.dbconst import (
    CLASS_TO_KEY_MAP,
    DBMODE_W,
    KEY_TO_CLASS_MAP,
    KEY_TO_NAME_MAP,
    TXNADD,
    TXNDEL,
    TXNUPD,
)
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.errors import HandleError
from gramps.gen.lib.baseobj import BaseObject
from gramps.gen.lib.json_utils import data_to_object, remove_object
from gramps.gen.merge.diff import diff_items
from gramps.gen.user import User
from gramps.gen.utils.file import media_path_full
from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.plugins.importer.importxml import importData

from taskrunner import GLibTaskRunner, IoRunner
from webapi_client import WebApiHandler, WebApiPushConflict, parse_version

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
LOG = logging.getLogger(".grampswebapidb")

#: How many transactions to request per page while syncing.
SYNC_PAGE_SIZE = 100

#: How often (seconds) load() re-polls the server for as long as the
#: database stays open -- see the module docstring's note on why this runs
#: synchronously on the GTK main thread rather than a background timer.
POLL_INTERVAL_SECONDS = 10

#: How often (seconds) load() and the ongoing poll re-scan for media files
#: missing locally or on the server -- see _sync_media_files(). Coarser
#: than POLL_INTERVAL_SECONDS: unlike a record-history page fetch, a scan
#: touches every local Media object's file on disk (os.path.exists()) and
#: hits a separate server endpoint, and anything found missing is then
#: transferred in full -- not worth doing on every 10-second record-sync
#: tick.
MEDIA_POLL_INTERVAL_SECONDS = 300

#: Ceiling (seconds) on the record poll's backoff while the server is
#: unreachable -- see _poll_tick(). Every consecutive failure doubles the
#: interval from POLL_INTERVAL_SECONDS up to this cap, and the first
#: success resets it. A server that is down (or a laptop that is off the
#: network) stays down for minutes or hours, not seconds, and each futile
#: tick costs a blocking round trip on the GTK main thread -- including
#: webapi_client's own one-shot retry sleep -- so retrying every 10
#: seconds for the whole outage buys nothing and stutters the UI. The cap
#: is deliberately no larger than MEDIA_POLL_INTERVAL_SECONDS: once the
#: server comes back, the mirror should catch up within a poll or two,
#: not stay stale for an hour.
POLL_BACKOFF_MAX_SECONDS = 300

#: Cap on the persisted pending-push queue (see _queue_pending_push()).
#: A queue this long means the server has been unreachable across a great
#: many local edits; keeping every one of them forever would grow the
#: metadata row without bound, so the oldest are dropped with a loud log
#: rather than silently.
MAX_PENDING_PUSHES = 1000

#: Net change count at or below which _full_resync_async()/
#: _bootstrap_full_resync() describe a reimport with granular per-object
#: signals (_emit_change_signals(), reusing _reconcile_batch_commit()'s
#: own before/after diff via _diff_snapshots()) instead of request_rebuild().
#: See those methods' own comments: a resync recovering from a push
#: conflict or repairing a mirror the history feed lost track of touches a
#: small number of objects against an otherwise-already-correct mirror, so
#: a precise diff is both cheap and far less disruptive than telling every
#: view to reload wholesale -- most importantly, gui/displaystate.py's
#: History.history_changed() only resets Active Person on an actual
#: <type>-rebuild signal, so a small, targeted diff leaves Active Person
#: alone unless the active object itself was one of the handles that
#: genuinely changed. Above this threshold (a bootstrap resync against an
#: empty mirror, or a mirror repair that's badly fallen behind), the diff
#: itself is legitimately "everything," where one rebuild signal per type
#: is cheaper for every view than replaying that many individual add
#: signals -- so request_rebuild() stays the right tool there.
GRANULAR_REBUILD_MAX_CHANGES = 500

#: Server-side permission names (gramps-web-api's auth/const.py) this
#: addon depends on, checked at load() by _check_permissions_async().
#:
#: ViewPrivate is required to read at all: GET /transactions/history/
#: calls require_permissions([PERM_VIEW_PRIVATE]) outright (see
#: gramps_webapi/api/resources/history.py), so the whole incremental sync
#: 403s without it. It matters just as much for _full_resync()'s fallback,
#: which fails *silently* rather than loudly instead: GET /exporters/
#: gramps/file doesn't refuse the request, it passes
#: view_private=has_permissions({PERM_VIEW_PRIVATE}) into the export task
#: (exporters.py), so a caller lacking it gets a privacy-filtered export
#: -- which _full_resync() would then import over a wiped local mirror,
#: quietly dropping every private record from the mirror.
_PERM_VIEW_PRIVATE = "ViewPrivate"

#: POST /transactions/ requires all three of these together
#: (transactions.py's require_permissions([PERM_ADD_OBJ, PERM_EDIT_OBJ,
#: PERM_DEL_OBJ]) -- has_permissions() fails if *any* are missing), so
#: write-through needs all three or no local edit can ever be pushed.
#: PUT /media/<handle>/file additionally needs EditObject, already
#: included here.
_WRITE_PERMISSIONS = ("AddObject", "EditObject", "DeleteObject")

#: Together: the permission set of gramps-web-api's "Editor" role, the
#: least-privileged built-in role that can run this addon read-write.
_REQUIRED_ROLE_NAME = "Editor"

#: Oldest Gramps version a *server* can run and still produce the
#: "_class"-tagged transaction-history serialization data_to_object()
#: understands -- see the module docstring's note on gramps52 servers.
#: Checked at load() by _check_server_version_async() so an incompatible server
#: says so, instead of failing later as a bare KeyError mid-sync.
MIN_SERVER_GRAMPS_VERSION = (6, 0)

#: Payload size (number of change entries) at or above which a push is
#: sent with ?background=1 where the server supports it -- see
#: _push_payload(). Small pushes stay synchronous: that is the
#: overwhelmingly common case (one interactive edit), it keeps the crisp
#: 400-means-conflict semantics, and it avoids a pointless extra
#: round trip to the task endpoint. The threshold exists for the genuinely
#: large payload -- above all the one _reconcile_batch_commit() builds
#: after a bulk import -- where server-side processing can plausibly
#: outlast webapi_client.TIMEOUT and the connection would drop mid-write.
BACKGROUND_PUSH_THRESHOLD = 100

#: Failure modes from WebApiHandler.from_env()/push_transaction(): a
#: malformed/missing key (ValueError), a bad server response shape
#: (KeyError/JSONDecodeError, the latter a ValueError subclass), or the
#: server being unreachable (HTTPError/URLError/OSError -- socket.timeout
#: is an OSError subclass).
_CONNECTION_ERRORS = (ValueError, KeyError, HTTPError, URLError, OSError)


class _DatabaseClosed(Exception):
    """Raised by WebApiDB._guarded_pump() when close() ran while a
    pump-driven sync/push was suspended -- see the module docstring's
    "Keeping the GUI alive" section. Deliberately not one of the
    _CONNECTION_ERRORS: it isn't a connectivity problem, and turning it
    into a DbConnectionError would show the user a scary message about a
    tree they've already left."""


def _pump_main_loop():
    """Dispatch the main loop's next source, blocking until one is ready
    rather than busy-spinning.

    _run_async_to_completion()'s own wait loop calls this over and over
    until the chain it's waiting on finishes. An earlier version of this
    function checked context.pending() and looped calling
    context.iteration(False) only while something was already queued --
    which means, the instant nothing is pending (the common case while
    waiting on a worker thread doing real I/O), that outer wait loop
    spun as fast as Python and the GIL would allow, pinning a CPU core
    for the whole wait. Confirmed live (2026-08-17) that this made both
    the window's own responsiveness and the actual worker-thread transfer
    it was waiting on noticeably worse -- a tight Python loop reacquiring
    the GIL on every spin leaves less of it for the thread doing the
    actual work. context.iteration(True) blocks efficiently (via the
    platform's own poll/select under the hood) until a source is ready --
    including the GLib.idle_add() callback a worker thread's result
    arrives through -- then dispatches exactly that one, the same
    at-most-one-source-per-call contract the old loop had.

    Every network round trip this addon makes runs synchronously on the
    GTK main thread (see the module docstring's polling section), so a
    long one -- a full-export download, a page-by-page catch-up, a media
    transfer, a backgrounded push being waited on -- is time the main
    loop spends inside this addon rather than answering. The window
    manager reads that as a hung application and offers to force-quit it,
    and the window itself stops redrawing (no progress bar movement, no
    repaint after an overlapping window moves away).

    Calling this at the boundaries of those operations gives the loop its
    turn: pending redraws, the progress bar Gramps is already driving via
    load()'s callback, and the window manager's own ping all get handled,
    and the application stays live.

    Goes through GLib's default main context rather than Gtk.main_
    iteration() so this module stays importable without a display: it is
    a DATABASE plugin, loadable from the CLI, where pulling in gramps.gui
    (or Gtk) has no business being a requirement. GTK drives that very
    context, so the effect under the GUI is the same.

    The obvious hazard of pumping a main loop mid-operation is
    re-entrancy -- our own POLL_INTERVAL_SECONDS timeout coming round
    while a sync is in flight. _poll_tick()/_media_poll_tick() check
    _syncing for exactly that and skip their turn.

    A second, subtler hazard: whatever pending source this dispatches --
    a redraw, an idle callback a view scheduled off one of our own
    request_rebuild()/commit signals, an unrelated timer -- runs
    arbitrary code this addon does not own and cannot make correct.
    Gramps' own Callback.emit() already treats a connected handler's
    exception as that handler's problem (log and move on, never let it
    abort the emit()); GLib.MainContext.iteration() has no such
    protection built in, so left unguarded, a bug in some completely
    unrelated bit of GUI code reached this way can propagate up through
    this addon's sync/push machinery and take the whole application down
    with it -- confirmed in the field as a HandleError raised from a
    PeopleView redraw during _full_resync()'s post-reimport pump,
    surfacing (and killing Gramps) from inside a WebApiPushConflict
    handler that had otherwise recovered correctly. Catching and logging
    here, matching Callback.emit()'s own posture, keeps that class of bug
    a cosmetic GUI glitch instead of a lost edit and a crashed app.
    """
    context = GLib.MainContext.default()
    try:
        context.iteration(True)
    except Exception:
        LOG.exception(
            "Unhandled exception from a GTK/GLib callback dispatched "
            "while pumping the main loop mid-sync; continuing rather "
            "than letting it abort the sync/push in progress."
        )


def _http_error_detail(err):
    """Pull the server's own explanation out of an HTTPError's JSON body,
    if it has one.

    _get_json()/_get_binary() re-raise a non-401/429 HTTPError as-is,
    which throws away its response body -- so a bare "HTTP Error 422:
    Unprocessable Entity" reaches the user with no hint which request
    parameter the server actually objected to. FastAPI's own automatic
    validation errors (a raw 422, before the request even reaches
    gramps-web-api's route handler) put that under "detail"; the app's
    own domain errors (see webapi_client._raise_for_push_conflict(),
    _task_error_message()) use {"error": {"message": ...}} instead;
    flask-jwt-extended's own error handlers -- what actually answers a
    rejected POST /token/refresh/ (expired, revoked, or otherwise invalid
    refresh token) -- use a third shape, {"msg": ...}. Try all three; give
    up quietly (None) if the body isn't JSON at all, or has already been
    read by something else.
    """
    try:
        body = json.loads(err.read())
    except (ValueError, OSError, AttributeError):
        return None
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    if detail:
        return str(detail)
    error = body.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    msg = body.get("msg")
    if msg:
        return str(msg)
    return None


def _wrap_progress_callback(callback, text):
    """Adapt a Gramps load()-progress callback (a plain percentage
    function, 0-100) to also carry a descriptive label, for callers that
    accept one: gui/dbloader.py's uistate.pulse_progressbar(value,
    text=None) shows it as "<text>: NN%" on the progress bar dbloader.py
    already displays for the duration of any db.load() call, turning
    that otherwise-blank bar into a real "Syncing with Gramps Web API..."
    indicator during the initial catch-up sync. cli/grampscli.py's own
    callback, _pulse_progress(value), takes only the one positional
    argument -- calling it with a second would raise TypeError -- so the
    signature is inspected once, here, rather than assumed.

    Returns ``callback`` unchanged if it is None or doesn't accept a
    second argument.
    """
    if callback is None:
        return None
    try:
        accepts_text = len(inspect.signature(callback).parameters) >= 2
    except (TypeError, ValueError):
        # Some callables (a bound method of a C extension type, a
        # functools.partial with no introspectable signature, ...) can't
        # be inspected at all -- safest default is the plain percent-only
        # call every caller is guaranteed to accept.
        accepts_text = False
    if not accepts_text:
        return callback
    return lambda value: callback(value, text)


def _import_progress_user(callback):
    """Build the User importData() should see for _full_resync_async()'s
    reimport, using exactly the class and wiring Gramps' own GUI import
    uses -- gui/dbloader.py's DbLoader.do_import():
    ``User(callback=self._pulse_progress, ...)`` -- confirmed, by testing
    it directly against the same large export this addon's own reimport
    was previously freezing on with no progress at all, to report real
    progress throughout a large import without hanging or crashing
    Gramps.

    uistate/dbstate/parent are intentionally omitted: ImportXml's
    GrampsParser never calls begin_progress()/step_progress()/
    end_progress() (only self.update() -> UpdateCallback ->
    user.callback(), see gen/updatecallback.py) -- so the ProgressMeter
    dialog those three would drive, the only thing that would need a
    parent window, is never triggered either way. Only UserBase.callback()
    (inherited unchanged) matters here, and that just calls
    callback(percentage[, text]).

    Falls back to the inert gramps.gen.user.User if there's no display
    (CLI use) or gi/Gtk aren't importable -- gui.user.User pulls in Gtk at
    import time, which this DATABASE plugin must stay usable without.
    """
    if has_display():
        try:
            from gramps.gui.user import User as GuiUser

            return GuiUser(callback=callback)
        except ImportError:
            pass
    return User(callback=callback)


def _describe_connection_error(err):
    """
    Turn a _CONNECTION_ERRORS exception into DbConnectionError's message
    body. A 403 means the account GRAMPS_WEB_API_KEY authenticates as was
    correctly identified but isn't allowed to do this -- worth calling out
    specifically, since the raw HTTPError text ("HTTP Error 403:
    Forbidden") reads like an auth failure rather than a permissions one.

    Anything else that came with a JSON body (see _http_error_detail())
    gets that appended, so a validation failure like a bare 422 names the
    field it rejected instead of just its status code.

    URLError.__str__() wraps its reason in literal angle brackets --
    "<urlopen error [Errno 111] Connection refused>" -- which Gramps'
    own dialog code renders as Pango markup: the "<urlopen ...>" reads
    as an unclosed tag, so the markup parser rejects the whole string
    and the user sees a GTK warning in the log instead of the actual
    error message. Using err.reason directly avoids ever producing that
    wrapper.
    """
    if isinstance(err, HTTPError) and err.code == 403:
        return _(
            "The account authenticating via GRAMPS_WEB_API_KEY does not "
            "have permission on the server for this operation (HTTP 403 "
            "Forbidden). Generate a key for an account with sufficient "
            "permissions, or ask the server administrator to grant this "
            "one access."
        )
    if isinstance(err, HTTPError):
        detail = _http_error_detail(err)
        if detail:
            return "%s\n\n%s" % (err, detail)
        return str(err)
    if isinstance(err, URLError):
        # HTTPError is itself a URLError subclass, so this branch is only
        # reached for a "real" URLError (DNS failure, connection refused,
        # ...) -- an HTTPError always returns above, one way or the other.
        return str(err.reason)
    return str(err)


def _is_retryable_push_error(err):
    """Whether a failed push is worth queueing for a later retry.

    A 4xx is the server's considered answer about *this* request -- 403
    (the account lacks AddObject/EditObject/DeleteObject; see
    _check_permissions_async()), 404, or a 400 that push_transaction() already
    determined isn't a conflict -- and will keep being the answer no
    matter how often it is replayed. Queueing one would retry it on every
    poll forever and, worse, eventually evict genuinely retryable work
    from the capped queue.

    429 is the exception: it is explicitly "try again shortly", not a
    refusal. Everything else (5xx, URLError, socket timeout, a malformed
    response) is transient or unknown, and gets the benefit of the doubt.
    """
    if isinstance(err, HTTPError):
        return err.code == 429 or not 400 <= err.code < 500
    return True


#: Same substitution gramps.gui.dbman's Family Tree Manager applies to
#: whatever a user types renaming a tree (dbman.py's __change_name(): "kill
#: special characters so can use as file name in backup"). A hostname-
#: bearing name can't survive that GUI round-trip with its dots intact, so
#: _check_identity_async() normalizes through this same substitution on both
#: sides before comparing -- see that method.
_FAMILY_TREE_NAME_UNSAFE_CHARS = re.compile(r"[':<>|,;=\"\[\]\.\+\*\/\?\\]")

_TRANS_TYPE_NAME = {TXNADD: "add", TXNUPD: "update", TXNDEL: "delete"}

#: The reverse of _TRANS_TYPE_NAME -- _diff_snapshots() emits "type" as a
#: string (transaction_to_json()'s shape, and what _reconcile_batch_commit()
#: pushes), but _emit_change_signals() takes TXNADD/TXNUPD/TXNDEL. Built
#: from _TRANS_TYPE_NAME rather than duplicated by hand so the two can
#: never drift apart.
_NAME_TO_TRANS_TYPE = {name: code for code, name in _TRANS_TYPE_NAME.items()}

#: Same signal-name suffixes DBAPI.transaction_commit() uses (dbapi.py's
#: own `action` dict) -- see _emit_change_signals().
_TRANS_TYPE_ACTION = {TXNADD: "-add", TXNUPD: "-update", TXNDEL: "-delete"}


def transaction_to_json(transaction):
    """
    Build the flat change-list payload POST /transactions/ expects, from
    a just-committed local DbTxn. Ported from GrampsWebSync's
    webapihandler.transaction_to_json (same repo, same license, credit
    David Straub) instead of imported, for the same no-cross-addon-
    dependency reason as webapi_client.py.
    """
    out = []
    for recno in transaction.get_recnos(reverse=False):
        key, action, handle, old_data, new_data = transaction.get_record(recno)
        obj_cls_name = KEY_TO_CLASS_MAP.get(key)
        if obj_cls_name is None:
            continue  # reference-type record, not a primary object
        out.append(
            {
                "type": _TRANS_TYPE_NAME[action],
                "handle": handle,
                "_class": obj_cls_name,
                "old": None if old_data is None else remove_object(old_data),
                "new": None if new_data is None else remove_object(new_data),
            }
        )
    return out


#: Handle-list attributes merge() unions without any existence check --
#: see _prune_dangling_references() below. TagBase/NoteBase/CitationBase
#: are the only primary-object mixins that hold plain handle lists rather
#: than reference objects of their own (EventRef, ChildRef, ... carry a
#: handle *inside* a child object get_handle_referents() already walks
#: to, so pruning each of these three attributes on every node
#: _iter_referents() yields covers those too).
_DANGLING_REFERENCE_CHECKS = (
    ("tag_list", "has_tag_handle"),
    ("note_list", "has_note_handle"),
    ("citation_list", "has_citation_handle"),
)


def _iter_referents(obj):
    """obj, then every child object get_handle_referents() reaches,
    recursively -- e.g. a Person's EventRef/Attribute/MediaRef/Address
    entries, each of which can carry its own tag_list/note_list/
    citation_list. Same traversal BaseObject.get_referenced_handles_
    recursively() uses, just walking nodes instead of collecting handles.
    """
    yield obj
    for child in obj.get_handle_referents():
        yield from _iter_referents(child)


def _prune_dangling_references(obj, db):
    """Strip any Tag/Note/Citation handle obj (or any nested child object
    -- see _iter_referents()) carries that no longer resolves in db.

    _merge_or_overwrite() below exists specifically to replay a *stale*
    pre-conflict local edit on top of a freshly-resynced object
    (_retry_after_conflict()) -- and merge()'s own list-unioning
    (TagBase._merge_tag_list() and the Note/Citation equivalents,
    gen/lib/{tagbase,notebase,citationbase}.py) has no existence check at
    all. If the push conflict this retry is recovering from was itself
    caused by another client deleting one of those Tag/Note/Citation
    objects, resync correctly drops the reference from the freshly-
    fetched "current" -- but the union then resurrects that now-dangling
    handle straight into the object about to be committed. Confirmed in
    the field (2026-08-17): the very next redraw of the affected row then
    crashed Gramps with an uncaught HandleError (PeopleModel.
    column_tag_color() -> db.get_tag_from_handle()), reproduced exactly
    by replaying this same sequence against a real GTK PersonListModel.

    Applied to whatever _merge_or_overwrite() is about to return, not
    just the merge() branch's output -- the type(current).merge is
    BaseObject.merge fallback (e.g. Tag) returns local_obj outright with
    no merge() call at all to have caught this otherwise.
    """
    for node in _iter_referents(obj):
        for attr, has_handle_name in _DANGLING_REFERENCE_CHECKS:
            handles = getattr(node, attr, None)
            if not handles:
                continue
            has_handle = getattr(db, has_handle_name)
            handles[:] = [h for h in handles if has_handle(h)]


def _event_ref_signature(person):
    """A (handle, role) tuple per entry of person's event_ref_list --
    enough to tell whether the list itself was untouched across a resync
    (see _snapshot_birth_death_indices()), without pulling in the full
    equality check EventRef.is_equivalent() does (citations, notes, ...
    are irrelevant here)."""
    return tuple((ref.ref, ref.role.serialize()) for ref in person.get_event_ref_list())


def _snapshot_birth_death_indices(db):
    """Capture birth_ref_index/death_ref_index (plus an event_ref_list
    signature to tell whether it's still safe to trust that capture
    afterwards) for every Person, keyed by handle -- taken right before
    _full_resync_async()'s rebuild() clears the mirror.

    Gramps XML has no element for either index (confirmed against
    exportxml.py's write_person(): only the event_ref_list itself is
    written) -- ImportXml instead *recomputes* both, unconditionally,
    from document order: the first PRIMARY-role BIRTH/DEATH-type event
    ref becomes the new birth_ref_index/death_ref_index, and a Person
    with no such ref keeps -1 (importxml.py's own GrampsParser,
    ``self.person.get_birth_ref() is None`` guard). That recomputation
    is wrong whenever the true index was already -1 despite a BIRTH/
    DEATH-type ref existing (nothing marks one as "the" birth/death
    among several, or none is marked as primary at all -- both real,
    legal states, common on data imported from outside Gramps) or
    pointed at something other than the first such ref (multiple
    disputed-date events, a later one picked as authoritative). Since
    diff_items() (gen/merge/diff.py) treats birth_ref_index/
    death_ref_index as ordinary content -- unlike "change", there is no
    key-name skip for them -- a Person whose true index doesn't match
    that heuristic silently and permanently disagrees with the server
    after every single resync, so any future edit to that Person's own
    "old" snapshot never matches the server's current data again:
    gramps-web-api's old_unchanged() (api/tasks.py) rejects the push,
    _push_payload_async() resyncs (recomputing the same wrong value
    right back), and the retry conflicts identically -- confirmed via a
    local export/reimport round-trip against a real DBAPI database
    (birth_ref_index went from -1, correct, to 0 purely from the XML
    round trip, with no edit involved).

    _restore_birth_death_indices() undoes the damage for whatever this
    captured, once the reimport is done -- but only for a Person whose
    event_ref_list (see _event_ref_signature()) still matches signature
    for signature afterwards: if it doesn't, something legitimately
    changed that Person server-side and the freshly-recomputed index is
    at least as trustworthy as blindly replaying a now-stale one.
    """
    snapshot = {}
    for handle in db.get_person_handles():
        person = db.get_person_from_handle(handle)
        snapshot[handle] = (
            person.birth_ref_index,
            person.death_ref_index,
            _event_ref_signature(person),
        )
    return snapshot


def _restore_birth_death_indices(db, snapshot, trans):
    """_snapshot_birth_death_indices()'s other half -- see that
    function's docstring. Called under the same self._pulling context
    _full_resync_async()'s rebuild() already holds around the reimport
    itself, so this local-only correction does not get mistaken for an
    edit to push back to the server (see transaction_begin()'s
    self._pulling check). Returns the number of Person objects
    corrected, purely for the caller's own debug log."""
    restored = 0
    for handle, (birth_idx, death_idx, signature) in snapshot.items():
        if not db.has_person_handle(handle):
            continue
        person = db.get_person_from_handle(handle)
        if _event_ref_signature(person) != signature:
            continue
        if person.birth_ref_index == birth_idx and person.death_ref_index == death_idx:
            continue
        person.birth_ref_index = birth_idx
        person.death_ref_index = death_idx
        db.commit_person(person, trans)
        restored += 1
    return restored


def _diff_snapshots(before, after):
    """Diff two {(obj_class, handle): data} snapshots (_snapshot_all_
    objects()'s own shape) into a transaction_to_json()-shaped change
    list: a handle present only in ``after`` is an add ("old": None), one
    present only in ``before`` is a delete ("new": None), and one present
    in both is an update only if its content actually differs -- compared
    with gramps.gen.merge.diff.diff_items(), the exact function gramps-
    web-api's own old_unchanged() conflict check uses server-side
    (gramps_webapi/api/tasks.py, confirmed by reading that source), so
    "did this really change" here agrees with the server's own idea of
    it: both ignore the object's own "change" timestamp, so a resave with
    no other change is correctly not reported at all.

    Shared by _reconcile_batch_commit() (which pushes the result to the
    server -- a local batch=True commit's own changes need to go out) and
    _full_resync_async()/_bootstrap_full_resync() (which only need it to
    decide what to *tell already-open views*, via _emit_change_signals()
    -- what was just pulled *from* the server must never be pushed back).
    """
    entries = []
    for obj_class, handle in after.keys() - before.keys():
        entries.append(
            {
                "type": "add",
                "handle": handle,
                "_class": obj_class,
                "old": None,
                "new": after[(obj_class, handle)],
            }
        )
    for obj_class, handle in before.keys() - after.keys():
        entries.append(
            {
                "type": "delete",
                "handle": handle,
                "_class": obj_class,
                "old": before[(obj_class, handle)],
                "new": None,
            }
        )
    for obj_class, handle in before.keys() & after.keys():
        old_data = before[(obj_class, handle)]
        new_data = after[(obj_class, handle)]
        if diff_items(obj_class, old_data, new_data):
            entries.append(
                {
                    "type": "update",
                    "handle": handle,
                    "_class": obj_class,
                    "old": old_data,
                    "new": new_data,
                }
            )
    return entries


def _merge_or_overwrite(current, local_obj, db):
    """Combine local_obj's content into current via the object's own
    merge() -- the same list-unioning logic behind Gramps' Merge People/
    Family/... tools (ported from GrampsWebSync's diffhandler.py, credit
    David Straub, same license) -- when the type actually implements it.

    Falls back to local_obj outright for a type (e.g. Tag) that only
    inherits BaseObject's no-op merge(): "merging" into a no-op would
    silently keep current's content and discard the local edit entirely,
    which is worse than the plain overwrite this replaces.

    local_obj's gramps_id is cleared before merging so merge() doesn't
    misread it as a real second object being absorbed (which is what
    merge() is for) and tag on a spurious "Merged Gramps ID" attribute --
    this is the same object, edited twice, not two objects becoming one.

    db is required so the result can be checked for dangling references
    before it's returned -- see _prune_dangling_references().
    """
    if type(current).merge is BaseObject.merge:
        result = local_obj
    else:
        merged = deepcopy(current)
        local_copy = deepcopy(local_obj)
        local_copy.gramps_id = None
        merged.merge(local_copy)
        result = merged
    _prune_dangling_references(result, db)
    return result


class WebApiDB(SQLite):
    """
    DBAPI backend whose local SQLite connection is a mirror of a
    Gramps Web API server, kept in sync via the server's transaction
    history endpoint.
    """

    #: Set around _retry_after_conflict()'s own DbTxn so the
    #: transaction_commit() it triggers can tell _push_payload() this push
    #: is itself a conflict retry -- see _push_payload().
    _retrying = False

    #: Set around _sync_from_server()'s own batch=True DbTxns (including
    #: the ones _full_resync() opens) so transaction_begin() can tell them
    #: apart from a batch=True transaction started by anything else (a
    #: bulk import, a Tool) -- see the module docstring and
    #: _reconcile_batch_commit().
    _pulling = False

    #: Set for the duration of any async operation that owns the mirror
    #: -- a record/media sync, or (since the move off reentrant pumping)
    #: a push -- so a second one can't start concurrently and land an
    #: overlapping DB-apply callback. See _start_push()/_finish_async_op().
    _syncing = False

    #: The chain a conflict retry's nested re-push belongs to, stashed by
    #: _after_conflict_resync() so _start_push()'s recursive
    #: (is_retry=True) call can complete *that* chain instead of treating
    #: the retry's own local commit as the finish line -- see both
    #: methods' docstrings and section 2.2.1 of the refactor plan for the
    #: premature-completion bug this exists to prevent.
    _retry_chain_done = None
    _retry_chain_error = None

    #: Bumped by close(), before anything else it does, so a pump-driven
    #: sync/push suspended elsewhere on the call stack can tell (via
    #: _guarded_pump()) that the tree it was working on is gone as soon as
    #: the main loop gives control back. Also what _guarded() (used by the
    #: worker-thread-based ..._async() chains) compares against to drop a
    #: callback belonging to an abandoned chain -- see that method. An
    #: instance can be load()-ed again after close() (Gramps may reuse one
    #: WebApiDB object across Family Trees), so this is a generation
    #: counter rather than a boolean: each close() starts a new generation
    #: instead of leaving a single flag that a fresh load() would have to
    #: remember to clear.
    _run_id = 0

    #: Consecutive failed polls, per timer, and the record poll's current
    #: interval -- the outage state _poll_tick()/_media_poll_tick() use to
    #: log an outage once instead of once per tick, and to back the record
    #: poll off while it lasts. Reset by the first successful sync.
    _poll_failures = 0
    _media_poll_failures = 0
    _poll_interval = POLL_INTERVAL_SECONDS

    def requires_login(self):
        # Credentials come from GRAMPS_WEB_API_KEY, not a login dialog.
        return False

    def _initialize(self, directory, username, password):
        try:
            self.web_client = WebApiHandler.from_env()
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(_describe_connection_error(err), directory) from err
        LOG.debug("client: mirroring %s", self.web_client.url)

        # runner dispatches DB/GUI-touching steps on the main loop;
        # io_runner runs pure network I/O on a worker thread. See
        # taskrunner.py's module docstring for why -- this is what replaces
        # the old _pump_main_loop()/_guarded_pump() reentrancy.
        self.runner = GLibTaskRunner()
        self.io_runner = IoRunner()

        # Local mirror: reuse SQLite's own _initialize for the on-disk
        # cache file, then sync from the server on load().
        super()._initialize(directory, username, password)

    def load(self, *args, **kwargs):
        # callback is Gramps' own load-progress hook -- position 2 in
        # DbGeneric.load()'s signature, or the "callback" kwarg -- the same
        # plain percentage function cli/grampscli.py's _pulse_progress and
        # gui/dbloader.py's real progress-bar wiring already provide.
        # Forwarded to _sync_from_server_async() so a slow initial catch-up
        # (a new mirror, or one that's been offline a while) shows real
        # progress instead of Gramps just looking hung; _poll_tick()'s own
        # background-poll call deliberately leaves this at its None
        # default, since a 10-second background tick shouldn't pop a
        # progress bar.
        callback = kwargs.get("callback")
        if callback is None and len(args) >= 2:
            callback = args[1]
        # Labels the already-visible progress bar dbloader.py shows for
        # the duration of this call ("Syncing with Gramps Web API: NN%")
        # instead of leaving it a bare percentage -- see
        # _wrap_progress_callback()'s own docstring for why this is safe
        # for callers (the CLI's) that don't accept a label at all.
        callback = _wrap_progress_callback(callback, _("Syncing with Gramps Web API"))
        # mode is position 3 in DbGeneric.load()'s signature, defaulting to
        # DBMODE_W -- read the same two ways as callback above. A tree
        # opened read-only never pushes, so it needs no write permissions.
        mode = kwargs.get("mode")
        if mode is None and len(args) >= 3:
            mode = args[2]
        if mode is None:
            mode = DBMODE_W
        LOG.debug(
            "load: %s (mode %s)", args[0] if args else kwargs.get("directory"), mode
        )
        super().load(*args, **kwargs)
        # Each check below makes exactly one network call. Run via
        # _run_async_to_completion() (on io_runner, main loop pumped while
        # waiting) rather than the old synchronous versions directly:
        # confirmed live (2026-08-17) that three back-to-back blocking
        # calls here, with nothing pumping the loop between them, is
        # enough on its own to make the window unresponsive.
        #
        # Each also reports a small, fixed percentage once it succeeds --
        # not a real fraction of anything, just visible proof of progress
        # during a stretch that, before this, reported nothing at all.
        # Reported live (2026-08-17): checks + a full bootstrap resync
        # (see _bootstrap_full_resync() below) can together leave the bar
        # motionless for over ten seconds before the reimport's own real
        # percentages start arriving.
        for check_name, start_chain, percent_after in (
            (
                "identity",
                lambda on_done, on_error: self._check_identity_async(on_done, on_error),
                5,
            ),
            (
                "permissions",
                lambda on_done, on_error: self._check_permissions_async(
                    on_done, on_error, writable=(mode == DBMODE_W)
                ),
                10,
            ),
            (
                "server version",
                lambda on_done, on_error: self._check_server_version_async(
                    on_done, on_error
                ),
                15,
            ),
        ):
            result = self._run_async_to_completion(start_chain)
            if result is None:
                LOG.debug("load: tree closed during %s check; aborting", check_name)
                return
            if callback is not None:
                callback(percent_after)
        # A quick, synchronous, unwrapped check for the totals-shortfall
        # case -- the same condition _mirror_is_short_of_the_server_async()
        # checks, done directly here rather than through the async chain.
        # If the mirror is clearly behind, run the whole resync outside
        # _run_async_to_completion()'s pump loop entirely (see
        # _bootstrap_full_resync()'s own docstring), skipping the wrapped
        # record-sync call below (a bootstrap resync already brings the
        # mirror fully current, same as the async path's effect).
        # Deliberately does not cover the other full-resync trigger (an
        # empty-"changes" marker on an otherwise-adequate feed) -- that
        # still goes through _full_resync_async() via the wrapped path
        # below, same as before this method existed.
        needs_bootstrap_resync = False
        if not self._get_metadata("pending_pushes", default=[]):
            try:
                local_total = self.get_total()
                server_total = self.web_client.get_object_count()
            except _CONNECTION_ERRORS as err:
                raise DbConnectionError(
                    _describe_connection_error(err), self._directory
                ) from err
            needs_bootstrap_resync = server_total > local_total
        # _sync_from_server_async() runs its network legs on a worker
        # thread; _run_async_to_completion() blocks this call (pumping
        # the main loop so that worker thread's result can actually be
        # delivered) until it finishes -- see that method's docstring
        # for why load() still waits synchronously here rather than
        # returning early, unlike everywhere else in this file.
        tree_closed_during_sync = False
        self._syncing = True
        try:
            if needs_bootstrap_resync:
                if callback is not None:
                    callback(20)
                self._bootstrap_full_resync(callback)
            else:
                sync_result = self._run_async_to_completion(
                    lambda on_done, on_error: self._sync_from_server_async(
                        on_done,
                        on_error,
                        progress_callback=callback,
                        verify_totals=True,
                    )
                )
                tree_closed_during_sync = sync_result is None
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(
                _describe_connection_error(err), self._directory
            ) from err
        finally:
            self._syncing = False
        if tree_closed_during_sync:
            # The tree was closed (or switched away from) while this
            # initial sync was still in flight. Nothing left to open;
            # don't schedule polling for it.
            LOG.debug("load: tree closed during initial sync; aborting")
            return
        # Fresh outage state for a freshly opened tree: these are class
        # attributes, so an instance reused across a close()/load() would
        # otherwise start out backed off from the previous tree's outage.
        self._poll_failures = 0
        self._media_poll_failures = 0
        self._poll_interval = POLL_INTERVAL_SECONDS
        # _sync_media_files_async() runs its network legs on a worker
        # thread; _run_async_to_completion() blocks this call (pumping the
        # main loop so that worker thread's result can actually be
        # delivered) until it finishes -- see that method's docstring for
        # why load() still waits synchronously here rather than returning
        # early, unlike everywhere else in this file.
        tree_closed_during_media_sync = False
        self._syncing = True
        try:
            media_result = self._run_async_to_completion(
                lambda on_done, on_error: self._sync_media_files_async(
                    on_done, on_error
                )
            )
            tree_closed_during_media_sync = media_result is None
        except _CONNECTION_ERRORS:
            # Unlike the record sync above, a media-file-sync failure here
            # doesn't block opening the tree: the record mirror is already
            # usable, and missing/un-uploaded media files are recovered on
            # the next successful media poll (or the next load()).
            LOG.exception("Initial media file sync failed; will retry.")
            # Counts as this outage's one loud report, so _media_poll_tick()
            # doesn't immediately say the same thing again 300 seconds later.
            self._media_poll_failures = 1
        finally:
            self._syncing = False
        if tree_closed_during_media_sync:
            LOG.debug("load: tree closed during initial media sync; aborting")
            return
        self._poll_source_id = GLib.timeout_add_seconds(
            POLL_INTERVAL_SECONDS, self._poll_tick
        )
        self._media_poll_source_id = GLib.timeout_add_seconds(
            MEDIA_POLL_INTERVAL_SECONDS, self._media_poll_tick
        )

    def _check_identity_async(self, on_done, on_error):
        """Require this Family Tree's own name to be "<username>@<host>"
        for whoever GRAMPS_WEB_API_KEY currently authenticates as.

        Nothing else ties a local mirror to one particular server account:
        there is no per-tree settings.ini (see the module docstring), and
        _sync_from_server() only ever asks for changes *after* its stored
        sync_last_time -- it has no way to notice the mirror belongs to a
        different account entirely and would just quietly go on mixing old
        and new data. Requiring (and reading back) the account identity in
        the tree's own display name catches that at load time instead, and
        costs nothing extra: get_dbname() just rereads the same name.txt
        Gramps already writes for the Family Tree Manager.

        Both sides are compared after _FAMILY_TREE_NAME_UNSAFE_CHARS's
        substitution, not the raw "<username>@<host>" string: the Family
        Tree Manager's own rename callback silently applies that same
        substitution to anything typed in (dbman.py's __change_name()), so
        a hostname's dots can never actually reach name.txt intact -- an
        exact-string comparison would reject every tree name Gramps itself
        would let you type.

        Runs on io_runner like every other network call in this file:
        confirmed live (2026-08-17, against a real server) that running
        this and the other two load()-time checks synchronously on the
        main thread -- each one a real network round trip with nothing
        pumping the loop in between -- is enough on its own to make the
        window unresponsive, even before reaching any resync work.
        """

        def fetch():
            return self.web_client.get_identity()

        def on_fetched(expected):
            expected_typeable = _FAMILY_TREE_NAME_UNSAFE_CHARS.sub("_", expected)
            actual = self.get_dbname()
            actual_normalized = _FAMILY_TREE_NAME_UNSAFE_CHARS.sub("_", actual)
            if actual_normalized != expected_typeable:
                on_error(
                    DbConnectionError(
                        _(
                            'This Family Tree is named "%(actual)s", but '
                            "GRAMPS_WEB_API_KEY currently authenticates as "
                            '"%(expected)s". Rename this Family Tree to '
                            '"%(expected_typeable)s" (Family Trees -> Manage '
                            "Family Trees) if it's meant to mirror that "
                            "account, or open/create the Family Tree "
                            "already named that -- reusing this one would "
                            "mix its existing local data with the other "
                            "account's."
                        )
                        % {
                            "actual": actual,
                            "expected": expected,
                            "expected_typeable": expected_typeable,
                        },
                        self._directory,
                    )
                )
                return
            on_done(True)

        def on_fetch_error(exc):
            if isinstance(exc, _CONNECTION_ERRORS):
                on_error(
                    DbConnectionError(_describe_connection_error(exc), self._directory)
                )
            else:
                on_error(exc)

        self.io_runner.run(
            fetch, self._guarded(on_fetched), self._guarded(on_fetch_error)
        )

    def _check_permissions_async(self, on_done, on_error, writable=True):
        """Fail at load() if the account GRAMPS_WEB_API_KEY authenticates
        as lacks a server permission this addon depends on, naming exactly
        which -- rather than letting each affected operation fail on its
        own later, in ways that range from a bare 403 to (for the export
        fallback) no error at all. See _PERM_VIEW_PRIVATE's comment for
        what each permission actually gates.

        ``writable`` is False for a tree opened read-only (DBMODE_R), which
        never pushes and so needs only the read permission.

        Costs no extra round trip: gramps-web-api puts the permission list
        in the access token's own claims (token.py's ``claims = {
        "permissions": [...]}``), so get_permissions() just decodes the JWT
        this handler already holds.

        Runs on io_runner for the same reason _check_identity_async() does.
        """
        required = [_PERM_VIEW_PRIVATE]
        if writable:
            required += list(_WRITE_PERMISSIONS)

        def fetch():
            return self.web_client.get_permissions()

        def on_fetched(permissions):
            granted = set(permissions)
            missing = [perm for perm in required if perm not in granted]
            if not missing:
                on_done(True)
                return
            on_error(
                DbConnectionError(
                    _(
                        "The account authenticating via GRAMPS_WEB_API_KEY is "
                        "missing server permission(s) this addon requires: "
                        "%(missing)s. Grant it at least the "
                        '"%(role)s" role on the server (or ask an '
                        "administrator to), then reopen this Family Tree. "
                        "Opening it as-is would leave the local mirror "
                        "silently incomplete or unable to save changes back."
                    )
                    % {"missing": ", ".join(missing), "role": _REQUIRED_ROLE_NAME},
                    self._directory,
                )
            )

        def on_fetch_error(exc):
            if isinstance(exc, _CONNECTION_ERRORS):
                on_error(
                    DbConnectionError(_describe_connection_error(exc), self._directory)
                )
            else:
                on_error(exc)

        self.io_runner.run(
            fetch, self._guarded(on_fetched), self._guarded(on_fetch_error)
        )

    def _check_server_version_async(self, on_done, on_error):
        """Fail at load() if the server runs a Gramps too old to produce
        the transaction-history serialization this addon reads.

        A gramps52-era server answers auth and read-only endpoints
        perfectly well, so nothing fails until _sync_from_server() feeds
        its differently-shaped new_data to data_to_object() and gets a
        bare KeyError -- see the module docstring. Asking GET /metadata/
        up front turns that into a sentence naming both versions.

        Deliberately lenient about *not knowing*: a server that doesn't
        report a Gramps version, or reports one this can't parse, is
        allowed through rather than blocked on a guess. The KeyError path
        still catches a genuinely incompatible one, just less kindly.

        Runs on io_runner for the same reason _check_identity_async() does.
        """

        def fetch():
            return self.web_client.get_gramps_version()

        def on_fetched(reported):
            version = parse_version(reported)
            if version is None or version >= MIN_SERVER_GRAMPS_VERSION:
                on_done(True)
                return
            on_error(
                DbConnectionError(
                    _(
                        "This server runs Gramps %(actual)s, but this addon "
                        "needs a server running Gramps %(required)s or "
                        "newer: older servers serialize their transaction "
                        "history in a format it cannot read. Upgrade the "
                        "Gramps installation behind the Gramps Web API "
                        "server (or ask its administrator to)."
                    )
                    % {
                        "actual": reported,
                        "required": ".".join(
                            str(part) for part in MIN_SERVER_GRAMPS_VERSION
                        ),
                    },
                    self._directory,
                )
            )

        def on_fetch_error(exc):
            if isinstance(exc, _CONNECTION_ERRORS):
                on_error(
                    DbConnectionError(_describe_connection_error(exc), self._directory)
                )
            else:
                on_error(exc)

        self.io_runner.run(
            fetch, self._guarded(on_fetched), self._guarded(on_fetch_error)
        )

    def close(self, *args, **kwargs):
        # Bumped first, before anything else: a sync/push elsewhere on the
        # call stack may be suspended inside _guarded_pump() (waiting to
        # find out whether it's still safe to touch self.dbapi once the
        # main loop hands control back) or, once the ..._async() chains
        # land, inside a worker-thread step whose eventual callback
        # _guarded() must recognize as belonging to an abandoned chain.
        # See _guarded_pump(), _guarded(), and the module docstring's
        # "Keeping the GUI alive" section.
        self._run_id += 1
        # A callback _guarded() drops (or a _guarded_pump() call that
        # raises) never reaches the `finally` blocks that would otherwise
        # clear these -- that unwind only ever happens because something
        # further up the call stack catches it, and after this point
        # nothing does. Reset explicitly so an instance reused for a fresh
        # load() (Gramps may reuse one WebApiDB object across Family
        # Trees) doesn't start out believing an abandoned operation from
        # the previous tree is still in flight.
        self._syncing = False
        self._pulling = False
        self._retrying = False
        # Stop polling a database that's no longer open -- otherwise the
        # next tick would run _sync_from_server() (and touch self.dbapi)
        # against a connection that's about to be (or already) closed.
        poll_source_id = getattr(self, "_poll_source_id", None)
        if poll_source_id is not None:
            GLib.source_remove(poll_source_id)
            self._poll_source_id = None
        media_poll_source_id = getattr(self, "_media_poll_source_id", None)
        if media_poll_source_id is not None:
            GLib.source_remove(media_poll_source_id)
            self._media_poll_source_id = None
        super().close(*args, **kwargs)

    def _guarded(self, callback):
        """Wrap a worker-thread-step callback (an ``on_success``/``on_error``
        handed to ``self.runner.run()``/``self.io_runner.run()``) so it is
        silently dropped if close() ran while that step was in flight,
        instead of resuming and touching a ``self.dbapi`` that is already
        gone.

        Not used yet -- introduced here alongside _run_id so later phases'
        ..._async() methods (see the module docstring) have it ready. The
        async equivalent of _guarded_pump(): where _guarded_pump() raises
        to unwind a still-synchronous call stack, this instead just never
        calls through, since there is no stack left to unwind once the
        step it wraps has already been handed to a worker thread or the
        idle-add queue -- the same posture GrampsWebSync's
        SyncSession._guarded() takes for a run the user has abandoned.
        """
        run_id = self._run_id

        def guarded(value):
            if run_id == self._run_id:
                callback(value)
            else:
                LOG.debug("Dropping a callback from a chain abandoned by close().")

        return guarded

    def _guarded_pump(self):
        """_pump_main_loop(), then raise _DatabaseClosed if that let
        close() run out from under us.

        Every _pump_main_loop() call this class makes goes through here
        instead of the bare function. Without it, a sync/push resumes
        after the pump and immediately crashes trying to touch
        self.dbapi -- the user switching or closing this very Family Tree
        is a perfectly ordinary GTK event, and reentering the main loop
        mid-operation (see the module docstring) is exactly what lets it
        get dispatched underneath a suspended call. Callers that can
        trigger a pump (directly or via webapi_client's on_wait/on_chunk
        hooks) let this propagate up to whichever entry point started
        them -- _poll_tick(), _media_poll_tick(), load(), _push_payload(),
        _flush_pending_pushes() -- which treat it as nothing left to do,
        not a failure.

        Detects this the same way _guarded() does -- comparing _run_id
        before and after -- rather than a boolean _closed flag, since an
        instance can be load()-ed again after close() (see _run_id's own
        docstring); capturing run_id fresh on each call, right before the
        one pump it guards, is exactly the right scope: nothing before
        this call needed protecting (it already ran), and nothing this
        call's caller does after seeing the raised exception touches
        self.dbapi either.
        """
        run_id = self._run_id
        _pump_main_loop()
        if self._run_id != run_id:
            raise _DatabaseClosed()

    def _run_async_to_completion(self, start_chain):
        """Block the calling thread (always the main thread -- this is
        only ever called from load()) until an async chain finishes,
        while still pumping the main loop so the worker-thread dispatch
        that chain depends on can actually be delivered.

        start_chain(on_done, on_error) must kick off exactly one
        ..._async() chain (e.g. ``lambda on_done, on_error:
        self._sync_media_files_async(on_done, on_error)``) and return
        immediately, the same contract every ..._async() method in this
        file follows.

        Raises whatever the chain's on_error received. Returns whatever
        its on_done received -- or None, with nothing raised, if the tree
        was closed while this was waiting (_guarded_pump() propagates
        that as _DatabaseClosed, caught here rather than left to whoever
        called this). load() is the one caller that still needs a
        synchronous answer: Gramps core's DbGeneric.load() contract
        requires the tree to be ready by the time it returns, unlike
        every other entry point in this file (_poll_tick(),
        transaction_commit(), ...), which starts a chain and returns
        immediately -- see the module docstring's "Keeping the GUI alive"
        section for why load() alone keeps this synchronous wait instead
        of also going fully asynchronous.
        """
        box = {}

        def on_done(value=None):
            box["done"] = True
            box["value"] = value

        def on_error(exc):
            box["done"] = True
            box["error"] = exc

        start_chain(on_done, on_error)
        while not box.get("done"):
            try:
                self._guarded_pump()
            except _DatabaseClosed:
                LOG.debug("load: tree closed while waiting on an async chain")
                return None
        if "error" in box:
            raise box["error"]
        return box.get("value")

    def _poll_tick(self):
        """GLib.timeout_add_seconds callback -- see the module docstring's
        polling section. Must return True (GLib.SOURCE_CONTINUE) to keep
        firing.

        Unlike the old synchronous version, always returns
        GLib.SOURCE_CONTINUE immediately: starting
        _sync_from_server_async() can't report success or failure
        synchronously, so the backoff/recovery bookkeeping
        (_on_poll_success()/_on_poll_error(), via _reschedule_poll())
        happens later, from its on_done/on_error. A tree closed mid-sync
        needs no special handling here to stop this timer -- close()
        removes it directly, and _guarded() (wrapping
        _sync_from_server_async()'s callbacks) silently drops one
        belonging to an abandoned chain rather than this method having to
        notice and react.

        An unreachable server is an expected, self-healing condition, not
        a bug in this addon: local edits keep working against the mirror
        and queue up for the next successful push (_queue_pending_push()),
        and the sync cursor is persisted, so the poll only has to survive
        the outage. It is therefore reported once per outage rather than
        once per tick, and the timer backs off while it lasts (see
        _record_poll_failure()) -- a 10-second traceback loop for as long
        as a server stays down buries anything else in the log and makes a
        routine outage look like a crash."""
        if self._syncing:
            # Reached from inside a still-running chain this tick would
            # otherwise start again underneath.
            LOG.debug("poll: a sync is already running; skipping this tick")
            return GLib.SOURCE_CONTINUE
        self._syncing = True
        self._sync_from_server_async(
            on_done=self._finish_async_op(self._on_poll_success),
            on_error=self._finish_async_op(self._on_poll_error),
        )
        return GLib.SOURCE_CONTINUE

    def _on_poll_success(self, applied):
        """_poll_tick()'s on_done -- see that method."""
        if self._poll_failures:
            LOG.info(
                "Sync from server succeeded again after %d failed attempt(s).",
                self._poll_failures,
            )
            self._poll_failures = 0
        self._reschedule_poll(POLL_INTERVAL_SECONDS)

    def _on_poll_error(self, exc):
        """_poll_tick()'s on_error -- see that method."""
        if not isinstance(exc, _CONNECTION_ERRORS):
            # Not a connectivity classification this poll knows how to
            # back off from -- see _on_media_poll_error()'s identical
            # reasoning.
            LOG.error(
                "Unexpected error during periodic sync from server.", exc_info=exc
            )
            return
        self._record_poll_failure(exc)

    def _record_poll_failure(self, err):
        """Handle a failed _poll_tick() sync: report it (once per outage,
        with the detail kept at DEBUG for whoever is diagnosing one) and
        slow the timer down, doubling up to POLL_BACKOFF_MAX_SECONDS."""
        self._poll_failures += 1
        interval = min(self._poll_interval * 2, POLL_BACKOFF_MAX_SECONDS)
        if self._poll_failures == 1:
            LOG.warning(
                "Periodic sync from server failed (%s); retrying, backing off "
                "to at most every %d seconds until the server answers again.",
                err,
                POLL_BACKOFF_MAX_SECONDS,
            )
            LOG.debug("Periodic sync failure detail", exc_info=err)
        else:
            LOG.debug(
                "Periodic sync from server still failing after %d attempts (%s); "
                "next retry in %d seconds.",
                self._poll_failures,
                err,
                interval,
                exc_info=err,
            )
        self._reschedule_poll(interval)

    def _reschedule_poll(self, interval):
        """Point the record poll at a new interval. A no-op when the
        interval is unchanged, which is the common case on both a
        healthy poll and a failing one already sitting at
        POLL_BACKOFF_MAX_SECONDS.

        Unlike the old synchronous _poll_tick(), which could report
        GLib.SOURCE_REMOVE from inside the very timeout callback being
        replaced (letting GLib itself drop that firing instance), this
        is now always called from an async on_done/on_error, well after
        _poll_tick() already returned GLib.SOURCE_CONTINUE to keep the
        current timer alive -- so the old timer has to be removed
        explicitly (GLib.timeout_add_seconds() has no way to retime an
        existing source in place either way) rather than relying on a
        return value GLib is no longer watching for by the time this
        runs."""
        if interval == self._poll_interval:
            return
        self._poll_interval = interval
        GLib.source_remove(self._poll_source_id)
        self._poll_source_id = GLib.timeout_add_seconds(interval, self._poll_tick)

    def _media_poll_tick(self):
        """GLib.timeout_add_seconds callback for the slower media-file
        scan -- same contract as _poll_tick() (must return True to keep
        firing), just for _sync_media_files_async() instead of the
        record-history poll.

        Unlike _poll_tick(), this always returns GLib.SOURCE_CONTINUE
        immediately: starting _sync_media_files_async() can't report
        success or failure synchronously the way the old
        _sync_media_files() call this replaced could, so that bookkeeping
        (_on_media_poll_success()/_on_media_poll_error()) happens later,
        from its on_done/on_error. A tree closed mid-sync needs no
        special handling here the way it once did to stop this very
        timer -- close() removes the timeout itself, and _guarded()
        (wrapping _sync_media_files_async()'s callbacks) silently drops
        one belonging to an abandoned chain rather than this method
        having to notice and react.

        Reported once per outage for the same reason as _poll_tick(), but
        with no backoff to go with it: MEDIA_POLL_INTERVAL_SECONDS is
        already as coarse as that poll's backoff cap."""
        if self._syncing:
            LOG.debug("media poll: a sync is already running; skipping this tick")
            return GLib.SOURCE_CONTINUE
        self._syncing = True
        self._sync_media_files_async(
            on_done=self._finish_async_op(self._on_media_poll_success),
            on_error=self._finish_async_op(self._on_media_poll_error),
        )
        return GLib.SOURCE_CONTINUE

    def _on_media_poll_success(self, result):
        """_media_poll_tick()'s on_done -- see that method."""
        if self._media_poll_failures:
            LOG.info(
                "Media file sync succeeded again after %d failed attempt(s).",
                self._media_poll_failures,
            )
            self._media_poll_failures = 0

    def _on_media_poll_error(self, exc):
        """_media_poll_tick()'s on_error -- see that method."""
        if not isinstance(exc, _CONNECTION_ERRORS):
            # Not a connectivity classification this poll knows how to
            # back off from. The old synchronous _sync_media_files() let
            # anything else propagate out of _media_poll_tick() uncaught
            # (there was nowhere for it to go but the caller); there is no
            # such caller for an async on_error, so log it loudly here
            # instead of silently losing it.
            LOG.error("Unexpected error during periodic media file sync.", exc_info=exc)
            return
        if self._media_poll_failures == 0:
            LOG.warning(
                "Periodic media file sync failed (%s); will retry every " "%d seconds.",
                exc,
                MEDIA_POLL_INTERVAL_SECONDS,
            )
            LOG.debug("Periodic media file sync failure detail", exc_info=exc)
        else:
            LOG.debug(
                "Periodic media file sync still failing after %d attempts (%s).",
                self._media_poll_failures + 1,
                exc,
                exc_info=exc,
            )
        self._media_poll_failures += 1

    def transaction_begin(self, transaction):
        """Hook DbTxn.__enter__ (which calls this immediately, before the
        transaction's body runs) to snapshot every primary object's full
        current data ahead of a batch=True transaction that isn't one of
        _sync_from_server()'s own (self._pulling) -- _reconcile_batch_
        commit() needs that "before" picture (not just which handles
        exist) to diff against, since DBAPI skips its usual undo-log
        recording for a batch commit regardless of who started it. See
        the module docstring and _reconcile_batch_commit()'s own
        docstring for why full data, not just handles or timestamps."""
        result = super().transaction_begin(transaction)
        if transaction.batch and not self._pulling:
            transaction._webapidb_before = self._snapshot_all_objects()
        return result

    def transaction_commit(self, transaction):
        # Must run before super(): it clears the transaction's records.
        payload = transaction_to_json(transaction)
        super().transaction_commit(transaction)
        before = getattr(transaction, "_webapidb_before", None)
        if before is not None:
            self._reconcile_batch_commit(before)
            return
        # self._retrying is set by _retry_after_conflict() while it holds
        # its own DbTxn open, so the push this commit triggers knows it is
        # itself a conflict retry and won't retry again on a second
        # conflict -- see _start_push().
        self._start_push(payload, is_retry=self._retrying)

    def undo(self, update_history=True):
        # Peek before super(): DbGenericUndo._undo() pops this DbTxn off
        # undoq. The DbTxn's own backing data isn't touched by that (it
        # just moves queues), so building its JSON payload could happen
        # either side of super() -- only grabbing the reference itself
        # can't wait.
        transaction = self.undodb.undoq[-1] if self.undodb.undo_count else None
        result = super().undo(update_history)
        if result and transaction is not None:
            self._start_push(transaction_to_json(transaction), undo=True)
        return result

    def redo(self, update_history=True):
        transaction = self.undodb.redoq[-1] if self.undodb.redo_count else None
        result = super().redo(update_history)
        if result and transaction is not None:
            # Redo is just re-applying the original transaction forward --
            # not a variant of undo=True. See push_transaction()'s docstring.
            self._start_push(transaction_to_json(transaction))
        return result

    def _start_push(self, payload, undo=False, is_retry=False):
        """Route a locally-intended push through the single-flight gate
        self._syncing (see the module docstring): the true top-level
        entry point for a given local edit -- transaction_commit(),
        undo(), redo() -- claims self._syncing here before anything
        touches the network, and only the terminal handler
        _finish_async_op() wraps releases it, once this whole chain
        (including any conflict-recovery detour through
        _push_payload_async() -> _resync_after_conflict_async() ->
        _retry_after_conflict()'s own nested push) has actually
        finished -- not merely been started.

        A recursive call (is_retry=True, reached only via
        _retry_after_conflict()'s own nested transaction_commit()) never
        claims self._syncing itself: it is always already held by
        whichever outer call started this chain, and reuses that outer
        call's own completion callbacks (self._retry_chain_done/
        self._retry_chain_error, stashed by _after_conflict_resync())
        so the chain's real end -- not just this recursive leg's local
        commit -- is what finally clears the flag. An earlier version of
        this design let self._syncing clear as soon as the retry's local
        DbTxn committed, before its own nested re-push (a real network
        round trip) had actually resolved -- exactly the class of race
        this refactor exists to eliminate, just reintroduced one level
        up if not guarded against here too.

        If self._syncing is already held by something else when a
        non-retry payload arrives, the push is queued
        (_queue_pending_push()) rather than raced against whatever is in
        flight -- deferred, not dropped: _finish_async_op() flushes the
        queue once the in-flight chain completes.
        """
        if not payload:
            if is_retry and self._retry_chain_done is not None:
                self._retry_chain_done(None)
            return
        if not is_retry:
            if self._syncing:
                self._queue_pending_push(payload, undo=undo)
                return
            self._syncing = True
            on_done = self._finish_async_op(None)
            on_error = self._finish_async_op(None)
        else:
            on_done = self._retry_chain_done or self._finish_async_op(None)
            on_error = self._retry_chain_error or self._finish_async_op(None)
        self._push_payload_async(
            payload, on_done, on_error, undo=undo, is_retry=is_retry
        )

    def _finish_async_op(self, on_done):
        """Wrap a top-level async chain's true completion handler so
        self._syncing only clears once the chain is genuinely done --
        including one attempt at flushing anything that arrived and got
        queued (_queue_pending_push()) while this chain held the flag.
        Shared by every top-level entry point that claims self._syncing
        (_start_push(), _poll_tick(), _media_poll_tick()), so a push
        that had to wait behind, say, a poll-triggered resync goes out
        as soon as that resync's chain finishes, not on the next poll
        tick.

        Deliberately *one* flush attempt, not a "keep looping while the
        queue is non-empty" recursion: _flush_pending_pushes_async()
        already drains the queue as far as it currently can in that one
        call (see its own docstring), stopping naturally at the first
        still-undeliverable entry -- if it stopped there, the queue is
        non-empty for exactly that reason, and calling it again
        immediately would just retry the identical failing entry,
        synchronously, forever. An earlier version of this method did
        exactly that (loop while non-empty) and deadlocked every test
        (and would have hung a real session) the moment any push failed
        for a connectivity reason, since the same queued entry made the
        post-flush check non-empty again on every pass. A push that
        arrives genuinely *during* this flush (a concurrent edit while
        self._syncing is still held) is not lost, just not flushed
        immediately -- it waits for the next chain's own completion, or
        the next poll tick, same as any other queued push today.
        """

        def finish(*args):
            if self._get_metadata("pending_pushes", default=[]):
                # self._syncing stays True until the flush -- a
                # continuation of this same chain, not a new operation
                # free to race whatever comes next -- itself finishes.
                def done_flushing(_result):
                    self._syncing = False
                    if on_done is not None:
                        on_done(*args)

                self._flush_pending_pushes_async(done_flushing, done_flushing)
                return
            self._syncing = False
            if on_done is not None:
                on_done(*args)

        return finish

    def _push_payload_async(
        self, payload, on_done, on_error, undo=False, is_retry=False
    ):
        """Push a change-list payload to the server, handling a rejected
        push (conflict or otherwise) the same way regardless of whether
        it came from a plain commit, an undo, or a redo. The async
        counterpart of the old (pump-based) _push_payload(): the network
        call runs entirely on io_runner (see taskrunner.py) -- no
        self.dbapi touch anywhere in this method or anything it
        schedules.

        Caller (_start_push()) already owns self._syncing; this method
        and everything it chains into never touches that flag itself --
        see that method's docstring.

        is_retry marks a push that is itself the replay
        _retry_after_conflict() made from an earlier conflict -- a
        second conflict on that replay is logged and dropped rather than
        retried again, so a genuinely hot object can't send this into an
        unbounded retry loop.
        """
        if not payload:
            on_done(None)
            return
        started = monotonic()

        def do_push():
            # io_runner: pure network, no self.dbapi touch.
            # _use_background_push()'s own network call
            # (supports_background_transactions()) belongs here too, not
            # on the main thread -- see that method's docstring.
            background = self._use_background_push(payload)
            LOG.debug(
                "push: %d change(s) (%s)%s%s",
                len(payload),
                ", ".join(sorted({entry["type"] for entry in payload})),
                " undo" if undo else "",
                " background" if background else "",
            )
            self.web_client.push_transaction(payload, undo=undo, background=background)
            LOG.debug("push: accepted in %.2fs", monotonic() - started)

        def on_pushed(_result):
            on_done(None)

        def on_push_error(exc):
            if isinstance(exc, WebApiPushConflict):
                LOG.warning(
                    "Server rejected %d local change(s): the object(s) "
                    "changed server-side since the local mirror last "
                    "synced. Resyncing the mirror from the server now.",
                    len(payload),
                )

                def on_resync_error(resync_exc):
                    LOG.error(
                        "Resync after a push conflict also failed.",
                        exc_info=resync_exc,
                    )
                    on_error(resync_exc)

                # A full resync, not the incremental history feed: a
                # conflict can be caused by a server-side change the
                # history feed cannot describe at all -- a bulk import
                # runs entirely outside gramps-web-api's own transaction
                # log (see _resync_after_conflict_async()'s docstring),
                # ordinary server administration rather than an edge
                # case -- and a totals check can't catch a content-only
                # change to an already-known object either. See
                # _resync_after_conflict_async() for why nothing cheaper
                # is trustworthy here.
                self._resync_after_conflict_async(
                    on_done=lambda _: self._after_conflict_resync(
                        payload, undo, is_retry, on_done, on_error
                    ),
                    on_error=on_resync_error,
                )
                return
            if not _is_retryable_push_error(exc):
                # A permission/payload rejection is not going to start
                # working on its own; queueing it would retry it on every
                # poll forever and eventually push real, retryable work
                # out of the capped queue.
                LOG.error(
                    "Server permanently rejected %d local change(s) (%s). "
                    "They will not be retried, and the local mirror has "
                    "drifted from the server for those object(s).",
                    len(payload),
                    exc,
                )
                on_error(exc)
                return
            # LOG.exception() (used by the old synchronous _push_payload())
            # relies on sys.exc_info(), which has nothing to show from
            # inside a callback outside any active except block -- exc is
            # passed explicitly via exc_info instead, same as elsewhere
            # in this file's ..._async() error handlers.
            LOG.error(
                "Failed to push %d local change(s) to the server; queued "
                "for retry on the next successful contact with the server.",
                len(payload),
                exc_info=exc,
            )
            self._queue_pending_push(payload, undo=undo)
            on_error(exc)

        self.io_runner.run(
            do_push, self._guarded(on_pushed), self._guarded(on_push_error)
        )

    def _after_conflict_resync(self, payload, undo, is_retry, on_done, on_error):
        """_push_payload_async()'s continuation once
        _resync_after_conflict_async() has brought the local mirror back
        to the server's true current state: replay the original edit on
        top of it (_retry_after_conflict()), unless this is already a
        retry or an undo/redo -- see _push_payload_async()'s docstring
        on is_retry.

        _retry_after_conflict()'s own DbTxn body is 100% local DB work
        (no network), so it runs as one runner (main-thread) step --
        run_retry() below. What it triggers on exit
        (DbTxn.__exit__ -> transaction_commit() -> _start_push(...,
        is_retry=True)) is a *nested* push, itself asynchronous;
        run_retry()'s own runner.run() completing therefore does NOT
        mean this chain is done, only that the local commit landed. The
        chain's real on_done/on_error are stashed on self
        (self._retry_chain_done/_retry_chain_error) so that nested
        _start_push() call can find and use them instead of treating the
        retry's local commit as the finish line -- see _start_push()'s
        docstring for the bug this specifically fixes.
        """
        if undo or is_retry:
            LOG.warning(
                "Giving up on %d local change(s) after a repeated or "
                "undo/redo conflict; the local mirror was not resent to "
                "the server.",
                len(payload),
            )
            on_done(None)
            return

        # This call is itself already known-valid (reached only via a
        # self._guarded() callback further up the chain), but scheduling
        # run_retry() below is a fresh hop through the main loop
        # (self.runner.run() -> another GLib.idle_add) -- close() could
        # still run in that narrow gap before run_retry() actually
        # executes. Re-checked inside run_retry() itself, same reasoning
        # as _full_resync_async()'s rebuild() -- see that method's
        # comment for the fuller explanation of why a fresh self._guarded()
        # wrapping alone can't catch this (it only stops the *outcome*
        # from being delivered, not the DbTxn from running in the first
        # place).
        run_id = self._run_id

        def on_retry_db_error(exc):
            # _retry_after_conflict()'s own DbTxn body (data_to_object(),
            # commit_<type>(), the merge) is what can raise here -- its
            # nested transaction_commit() -> _start_push() call handles a
            # rejected push itself and does not re-raise, so reaching
            # this means the DbTxn body never finished and aborted
            # without committing. Nothing local to lose; queue the
            # original payload the same as any other connectivity
            # failure.
            LOG.warning(
                "Could not replay %d local change(s) after a conflict "
                "(%s); queued for retry on the next successful contact "
                "with the server.",
                len(payload),
                exc,
            )
            self._queue_pending_push(payload, undo=undo)
            on_error(exc)

        def run_retry():
            if self._run_id != run_id:
                # The tree closed between this being scheduled and
                # actually running. No resource to clean up here (unlike
                # _full_resync_async()'s temp file) -- just don't touch
                # self.dbapi, which may already be closed.
                LOG.debug("retry: tree closed before it ran; discarding it")
                return
            # Read synchronously by _start_push() inside this same call
            # (via DbTxn.__exit__ -> transaction_commit()), before the
            # finally below clears it -- same single-callback-body
            # ordering guarantee as self._retrying itself.
            #
            # DbTxn.__exit__() calls transaction_commit() unconditionally
            # on a clean exit (txn.py), whether or not the transaction's
            # body actually committed anything -- so _start_push(...,
            # is_retry=True) is *always* reached exactly once here, never
            # skipped. Its own "if not payload:" branch already handles
            # the all-entries-were-no-ops case by calling
            # self._retry_chain_done(None) itself; there is deliberately
            # no fallback completion call here after
            # _retry_after_conflict() returns -- an earlier version of
            # this method had one, on the mistaken assumption that an
            # empty commit skips transaction_commit() entirely, and it
            # fired unconditionally, completing the chain the moment the
            # *local* commit landed regardless of whether the recursive
            # push it had just scheduled was still genuinely in flight --
            # reintroducing the exact premature-completion bug
            # _start_push()'s docstring describes. Only a real exception
            # from _retry_after_conflict() itself (caught below via
            # on_retry_db_error) is a valid reason for this chain to stop
            # here instead of via that recursive push's own eventual
            # on_done/on_error.
            self._retry_chain_done, self._retry_chain_error = on_done, on_error
            try:
                self._retry_after_conflict(payload)
            finally:
                self._retry_chain_done = None
                self._retry_chain_error = None

        self.runner.run(
            run_retry,
            # No-op: the chain's real completion fires from inside
            # run_retry() itself (via the nested push's on_done/
            # on_error), not from runner.run()'s own on_success --
            # run_retry() returning just means the *local* commit
            # landed, not that the chain is done.
            self._guarded(lambda _: None),
            self._guarded(on_retry_db_error),
        )

    def _use_background_push(self, payload):
        """Whether to ask the server to process this payload as a
        background task rather than inline -- see BACKGROUND_PUSH_THRESHOLD
        and webapi_client.push_transaction()'s ``background`` param.

        A server that can't do it (too old, or its version can't be
        determined) always answers False. A failure asking is not worth
        aborting the push over: fall back to the synchronous path, which
        works everywhere.
        """
        if len(payload) < BACKGROUND_PUSH_THRESHOLD:
            return False
        try:
            return self.web_client.supports_background_transactions()
        except _CONNECTION_ERRORS:
            LOG.debug(
                "Could not determine server support for background "
                "transactions; pushing synchronously.",
                exc_info=True,
            )
            return False

    def _queue_pending_push(self, payload, undo=False):
        """Persist a payload whose push failed for a connectivity reason,
        so _flush_pending_pushes() can retry it later -- including after a
        close()/reopen, since this goes through _set_metadata() (the same
        mechanism sync_last_time already uses) rather than an in-memory
        list. See the module docstring."""
        pending = self._get_metadata("pending_pushes", default=[])
        pending.append({"payload": payload, "undo": undo})
        if len(pending) > MAX_PENDING_PUSHES:
            dropped = len(pending) - MAX_PENDING_PUSHES
            LOG.error(
                "Pending-push queue exceeded %d entries; dropping the %d "
                "oldest. Those local change(s) will not reach the server -- "
                "the local mirror has permanently drifted and needs a manual "
                "reconciliation against it.",
                MAX_PENDING_PUSHES,
                dropped,
            )
            pending = pending[dropped:]
        self._set_metadata("pending_pushes", pending)

    def _flush_pending_pushes_async(self, on_done, on_error):
        """Retry queued pushes that previously failed for a connectivity
        reason, oldest first, stopping at the first that still can't be
        delivered -- see the module docstring on why this doesn't skip
        ahead past a stuck entry.

        A queued entry that comes back as a *conflict* rather than a
        connectivity failure is dropped rather than retried forever: by
        the time it is replayed the server has moved on, and
        _push_payload_async()'s resync-and-merge path needs an "old"
        snapshot contemporaneous with the edit, which a queued payload
        no longer has. An entry the server permanently rejects (see
        _is_retryable_push_error()) is likewise dropped rather than left
        to block the queue forever -- permissions may well have changed
        between queueing and now.

        Stopping early (a still-undeliverable entry) or exhausting the
        queue both call on_done, not on_error: neither is a failure of
        this method itself, and its caller (currently only
        _finish_async_op(), via a fresh self._get_metadata() check each
        time it re-wraps itself) always treats "flushed as far as
        possible" as success. Reads the queue itself (rather than
        taking it as a parameter) for the same reason _flush_pending_
        pushes() always did: called from more than one place, each
        needing the current persisted state, not a snapshot from
        whenever the caller happened to start.
        """
        pending = self._get_metadata("pending_pushes", default=[])
        if not pending:
            on_done(None)
            return
        LOG.info("Retrying %d queued push(es) to the server.", len(pending))
        self._flush_one_pending_push(pending, on_done, on_error)

    def _flush_one_pending_push(self, pending, on_done, on_error):
        """_flush_pending_pushes_async()'s per-entry step. ``pending`` is
        mutated in place (entries popped off the front as they're
        delivered or dropped) and persisted once this recursion bottoms
        out, exactly the way the old synchronous while-loop this
        replaces did with its own local variable."""
        if not pending:
            self._set_metadata("pending_pushes", pending)
            LOG.debug("queue: %d push(es) still pending after the flush", len(pending))
            on_done(None)
            return
        entry = pending[0]

        def do_push():
            # io_runner: pure network, no self.dbapi touch. See
            # _push_payload_async()'s do_push() for why
            # _use_background_push() belongs here too.
            background = self._use_background_push(entry["payload"])
            self.web_client.push_transaction(
                entry["payload"], undo=entry.get("undo", False), background=background
            )

        def pop_and_continue():
            pending.pop(0)
            self._flush_one_pending_push(pending, on_done, on_error)

        def on_pushed(_result):
            pop_and_continue()

        def on_push_error(exc):
            if isinstance(exc, WebApiPushConflict):
                LOG.warning(
                    "A queued push of %d change(s) conflicts with the "
                    "server's current data and cannot be replayed safely; "
                    "dropping it. The local mirror has drifted from the "
                    "server for those object(s).",
                    len(entry["payload"]),
                )
                pop_and_continue()
                return
            if _is_retryable_push_error(exc):
                LOG.warning(
                    "Still unable to deliver %d queued push(es); will retry.",
                    len(pending),
                )
                self._set_metadata("pending_pushes", pending)
                LOG.debug(
                    "queue: %d push(es) still pending after the flush", len(pending)
                )
                on_done(None)
                return
            LOG.error(
                "Server permanently rejected a queued push of %d change(s) "
                "(%s); dropping it. The local mirror has drifted from the "
                "server for those object(s).",
                len(entry["payload"]),
                exc,
            )
            pop_and_continue()

        self.io_runner.run(
            do_push, self._guarded(on_pushed), self._guarded(on_push_error)
        )

    def _retry_after_conflict(self, payload):
        """Reapply each locally-intended change as a fresh local edit --
        see the module docstring's write-through section. An add/update
        whose object still exists is combined with the current object via
        _merge_or_overwrite() rather than blindly replacing it.

        Callers are responsible for making sure the local mirror already
        holds the server's true current state for whatever this payload
        touches, *before* this runs: DBAPI computes this retry's own "old"
        snapshot from whatever is stored locally at commit time
        (_commit_base()'s _get_raw_data() call), so a stale mirror means
        the retry pushes the same stale "old" as the original failed push
        and is rejected again identically, no matter how correct its
        "new" is. _push_payload_async()'s conflict handler does this with
        a full resync (_resync_after_conflict_async()) before calling
        here (via _after_conflict_resync()); see that method's docstring
        for why nothing cheaper is trustworthy. This is only ever reached
        via that path now -- a local batch operation's own reconciled
        changes (_reconcile_batch_commit()) push directly through
        _start_push(), landing here only if that push itself conflicts,
        the same as any other edit.

        Runs as one ordinary (non-batch) DbTxn, so it goes through the
        normal transaction_commit() -> _start_push() path again -- this
        time with an "old" snapshot that matches the local mirror's
        current (freshly-resynced, for the conflict path) state, so it
        will only be rejected again if something else changed server-side
        in the brief window since then. _after_conflict_resync() runs
        this as one runner (main-thread) step, since it's 100% local DB
        work with no network of its own.
        """
        self._retrying = True
        try:
            with DbTxn(_("Retry local change after server conflict"), self) as trans:
                for entry in payload:
                    key = CLASS_TO_KEY_MAP.get(entry["_class"])
                    if key is None:
                        continue
                    name = KEY_TO_NAME_MAP[key]
                    handle = entry["handle"]
                    has_handle = getattr(self, f"has_{name}_handle")
                    if entry["type"] == "delete":
                        if has_handle(handle):
                            getattr(self, f"remove_{name}")(handle, trans)
                    else:
                        obj = data_to_object(entry["new"])
                        if has_handle(handle):
                            current = getattr(self, f"get_{name}_from_handle")(handle)
                            obj = _merge_or_overwrite(current, obj, self)
                        getattr(self, f"commit_{name}")(obj, trans)
        finally:
            self._retrying = False

    def _resync_after_conflict_async(self, on_done, on_error):
        """Rebuild the local mirror from a fresh server export
        (_full_resync_async()) before a conflict retry -- called by
        _push_payload_async()'s WebApiPushConflict handler in place of
        an incremental sync. Neither the incremental history feed nor a
        totals check is trustworthy here: gramps-web-api's bulk-import
        path (POST /importers/<ext>/file -- GEDCOM, Gramps XML, CSV,
        ...) runs the same batch=True import machinery a local Gramps
        client's own Import menu action would, which never touches the
        transaction-history table at all (see the module docstring), so
        the incremental feed can be blind to an object's true current
        state indefinitely -- ordinary server administration for any
        real installation, not a quirk of one server. A totals
        comparison doesn't catch this either: the object count doesn't
        change when an already-known object's content changes
        server-side, only when objects are added or removed, so a
        conflict caused by a content edit on a bulk-imported object
        leaves totals matching on both sides even though the mirror's
        copy of that object is stale.

        A per-object REST fetch (GET /<type>/<handle>) was tried here
        first and doesn't work: gramps-web-api's single-object endpoints
        serialize with GrampsJSONEncoder.extract_object() (a walk of the
        object's own __dict__/properties for the frontend's display
        schema -- no "_class" tag on GrampsType-derived fields), not the
        gramps.gen.lib.json_utils shape data_to_object() requires to
        reconstruct a Gramps object. Only two things produce that
        compatible shape: the transaction-history feed's new_data, and a
        raw Gramps XML export -- see _full_resync_async()'s own
        docstring. So a full resync, expensive as it is, is the only
        server round-trip that can bring the local mirror back into a
        state _retry_after_conflict() can safely build an "old" snapshot
        from.

        Caller already owns self._syncing (see _start_push()); this is a
        thin, purpose-named wrapper around _full_resync_async() rather
        than a second flag-managing layer -- unlike the old synchronous
        _resync_after_conflict() this replaces, which had to manage
        self._syncing itself since nothing else did for a plain push.
        """
        self._full_resync_async(on_done, on_error)

    def _full_resync_async(self, on_done, on_error, progress_callback=None):
        """Rebuild the local mirror from scratch: download the server's
        own current Gramps XML export and reimport it, after clearing
        every local primary object first. Called by
        _resync_after_conflict_async() (a push conflict) and, from phase
        4 on, also when the transaction-history feed contains an
        empty-changes marker -- by definition there is nothing in that
        history to replay for whatever produced it, so the only way to
        recover is to fetch the server's current state wholesale, the
        same way populating a brand new local mirror already works.

        Deliberately reuses the stock ImportXml importer against a raw
        XML export rather than reconstructing objects from the REST
        /people/, /families/, ... endpoints: those return a marshalled
        display schema (plain ints for GrampsType fields, no "_class"
        tag), not the json_utils shape data_to_object() needs. Only the
        transaction-history feed's new_data and a raw XML export share
        that shape, and the whole point of this method is that the
        former can't be trusted here.

        Two steps: the download runs on io_runner (network + disk, no
        self.dbapi touch); the clear-then-reimport runs as a single
        runner (main-thread) step -- both the explicit clearing DbTxn
        and ImportXml's own internal batch DbTxn, under self._pulling so
        transaction_commit() treats them as pull-side replays rather
        than local bulk edits to reconstruct and push back. Doing both
        halves inside one callback body (rather than pumping between
        them, as the old synchronous _full_resync() this will eventually
        replace still does) means close() can no longer interrupt a
        rebuild mid-way -- it can only run strictly before this step
        starts or strictly after it returns.

        rebuild() re-checks self._run_id itself, rather than relying
        solely on self._guarded() around its scheduling, for a reason
        specific to this method: the downloaded export is a real
        resource (a temp file) that needs cleaning up even if the tree
        closes in the gap between the download finishing and this step
        actually running -- a self._guarded()-dropped callback runs
        nothing at all, which would leak the file. Checking inside
        rebuild() itself (before it does anything else) additionally
        closes the narrower window between that check and the step
        being scheduled, so self.dbapi -- possibly already closed by
        then -- is never touched once the chain is known to be stale.

        progress_callback, if given, gets a 0 marker before the download,
        then real percentages throughout the reimport -- forwarded to
        importData() via _import_progress_user(), which builds exactly
        the gui.user.User Gramps' own GUI import uses (see that
        function's docstring) -- and a final 100 once everything,
        including request_rebuild(), has finished.

        Also (re)sets sync_last_time to a timestamp taken right before
        the export download starts, so the next incremental sync asks
        the history feed for changes after that point instead of
        wherever the walk that triggered this rebuild happened to leave
        the cursor -- for the totals-shortfall case, that walk can be a
        single empty page, which leaves sync_last_time at its untouched
        starting value (0 for a brand new mirror) rather than anywhere
        near "now". Left uncorrected, every later poll asks for history
        "after 0" forever on a server whose history can't describe its
        own data anyway, so it's a harmless no-op -- but a *push
        conflict*'s own recovery (resync then retry) uses that exact
        same stuck cursor, so the resync it does can never actually pick
        up what changed and the retry is doomed to repeat the same
        conflict and give up. Taken before the download rather than
        after: a transaction the server commits while the export is
        being generated or transferred is safer to see again on the
        next poll (re-applying an already-reflected change is a no-op)
        than to have it fall silently before the cursor and only be
        discovered next time a shortfall check runs.
        """
        if progress_callback is not None:
            progress_callback(0)
        sync_cutoff = time()
        started = monotonic()
        # Captured once, up front, and reused for every hop below --
        # deliberately not re-wrapped via self._guarded() partway through
        # (see on_downloaded()'s own comment for why that would be wrong
        # here specifically).
        run_id = self._run_id
        guarded_done = self._guarded(lambda _: on_done(None))
        guarded_error = self._guarded(on_error)

        def download():
            # io_runner: network + disk only -- the single longest
            # transfer this addon makes. No on_chunk to pump for anymore
            # (a worker thread has nothing to hand back to); one plain
            # read is fine.
            data = self.web_client.download_export()
            LOG.debug(
                "resync: downloaded a %.1f MB export in %.2fs",
                len(data) / (1024 * 1024),
                monotonic() - started,
            )
            with NamedTemporaryFile(suffix=".gramps", delete=False) as tmp_file:
                tmp_file.write(data)
                return tmp_file.name

        def rebuild(tmp_path):
            # runner: clear + reimport + rebuild-signal + sync_last_time,
            # all in one main-thread callback body -- see this method's
            # own docstring on why that's the point, not incidental.
            if self._run_id != run_id:
                # The tree closed somewhere between the download
                # finishing and this step actually running. Clean up the
                # temp file -- nothing else will -- but do not touch
                # self.dbapi, which may already be closed. See this
                # method's own docstring on why this check lives here
                # rather than relying on self._guarded() alone.
                LOG.debug("resync: tree closed before rebuild ran; discarding it")
                os.remove(tmp_path)
                return
            self._pulling = True
            try:
                before = self._snapshot_all_objects()
                birth_death_snapshot = _snapshot_birth_death_indices(self)
                cleared = 0
                with DbTxn(
                    _("Clear local mirror before full resync"), self, batch=True
                ) as trans:
                    for key in set(CLASS_TO_KEY_MAP.values()):
                        name = KEY_TO_NAME_MAP[key]
                        handles = list(getattr(self, f"get_{name}_handles")())
                        remove = getattr(self, f"remove_{name}")
                        for handle in handles:
                            remove(handle, trans)
                        cleared += len(handles)
                LOG.debug("resync: cleared %d local object(s); reimporting", cleared)
                imported_at = monotonic()
                import_user = (
                    _import_progress_user(progress_callback)
                    if progress_callback is not None
                    else User()
                )
                importData(self, tmp_path, import_user)
                LOG.debug(
                    "resync: reimport left %d object(s) (%.2fs)",
                    self.get_total(),
                    monotonic() - imported_at,
                )
                if birth_death_snapshot:
                    with DbTxn(
                        _("Restore birth/death event references lost on reimport"),
                        self,
                        batch=True,
                    ) as trans:
                        restored = _restore_birth_death_indices(
                            self, birth_death_snapshot, trans
                        )
                    if restored:
                        LOG.debug(
                            "resync: restored birth/death event reference "
                            "index on %d person(s) Gramps XML re-import "
                            "can't preserve",
                            restored,
                        )
                self._describe_resync_to_views(before)
            finally:
                self._pulling = False
                os.remove(tmp_path)
            self._set_metadata("sync_last_time", sync_cutoff)
            if progress_callback is not None:
                progress_callback(100)

        def on_downloaded(tmp_path):
            # Deliberately NOT wrapped in self._guarded(): tmp_path is a
            # real resource (a downloaded temp file) that needs cleaning
            # up even if the tree closed while the download was in
            # flight, and a self._guarded()-dropped callback runs
            # nothing at all. rebuild() re-checks self._run_id itself
            # (see its own comment) before touching self.dbapi, so
            # scheduling it unconditionally here is still safe -- and
            # guarded_done/guarded_error (captured once, above, against
            # this call's original run_id) are reused rather than
            # wrapped fresh here, since a fresh self._guarded() call made
            # from inside this always-firing callback would capture
            # self._run_id as it is *now* (already stale, in the case
            # this comment is about), defeating the check entirely.
            self.runner.run(lambda: rebuild(tmp_path), guarded_done, guarded_error)

        self.io_runner.run(download, on_downloaded, guarded_error)

    def _bootstrap_full_resync(self, progress_callback=None):
        """load()'s own alternative to _full_resync_async(), used
        specifically for the totals-shortfall check load() runs itself
        before the ordinary record-sync call (see load()'s own comment)
        -- most commonly hit opening a brand new mirror against a large
        existing tree, exactly the scenario that prompted this method.

        _full_resync_async() schedules its reimport step via
        self.runner.run() (GLib.idle_add underneath), dispatched from
        inside _run_async_to_completion()'s own pump loop
        (_pump_main_loop(), using GLib.MainContext.iteration()) when
        called from load(). importData()'s own progress reporting (see
        _import_progress_user()) then calls Gtk.main_iteration() --
        a *different* pumping API -- from inside that already-running
        step. Gramps' own native GUI Import never has that outer
        wrapping at all: it calls importData() directly from an ordinary
        GTK signal handler. This method reproduces that same shape for
        load()'s bootstrap case instead: plain sequential calls, on the
        calling thread, with importData() itself never scheduled via
        io_runner/runner/GLib.idle_add at all -- so there is nothing of
        this addon's own left for importData()'s own pumping to end up
        nested inside.

        Confirmed via live GUI testing (2026-08-17) that this resolves a
        freeze reported for exactly this load()-time scenario -- delete
        an existing mirror, create a fresh one, open it against a large
        (26540-object) tree. That investigation also uncovered an
        unrelated, session-long confound (a stale/misresolved installed
        plugin copy, see project memory) that had made every earlier
        live test that session meaningless, regardless of what the code
        actually did -- worth keeping in mind before reading too much
        into the reentrant-pumping theory above as *proven*: it is
        plausible and this method is a reasonable defensive structural
        match to Gramps' own working native-Import shape, but the
        specific freeze reports blamed on it before the stale-plugin
        discovery are not reliable evidence either way. _full_resync_async()
        itself is unchanged and still used for both its other callers
        (_resync_after_conflict_async(), and _finish_sync()'s own
        empty-"changes"-marker trigger) -- neither has actually been
        shown to freeze; this method exists for the highest-traffic case
        (a brand new or far-behind mirror at load() time) rather than as
        a proven-required fix for the other two.

        Safe to skip _full_resync_async()'s _run_id staleness checks and
        self._guarded() wrapping here specifically because load() calls
        this before the tree is open at all (dbloader.py's read_file()
        doesn't call dbstate.change_database(db) until load() returns),
        so there is no UI path by which close() could run against this
        tree while this method is still executing -- unlike
        _full_resync_async()'s other callers, which run against an
        already-open tree where that's a live concern.

        Body is otherwise a direct copy of _full_resync_async()'s
        rebuild() (see that method for the fuller explanation of each
        step): download, clear every local primary object, reimport,
        signal a rebuild, and advance sync_last_time.

        The download itself IS still run on io_runner and awaited via
        _run_async_to_completion(), unlike everything after it -- unlike
        importData(), nothing reentrant happens while it's in flight, so
        there is no second pumping API for _run_async_to_completion()'s
        own loop to end up nested under. Confirmed live (2026-08-17) that
        running the download as a plain blocking call here instead --
        unlike every other network call in this file -- froze the window
        for its whole duration (6+ seconds for this export, longer for a
        bigger one).

        progress_callback, if given, is called throughout -- not just the
        0/100 bookend load()'s other callers get. load() itself has
        already reported 5/10/15/20 by the time this method is called
        (see its own comments); from here, DOWNLOAD_START_PCT..
        DOWNLOAD_END_PCT is a slow, fixed-rate pulse for the download
        (there is no real byte-level progress to report for a single
        unchunked read -- see the download() closure below -- so this is
        proof of life, not a measurement), and
        REIMPORT_START_PCT..100 is importData()'s own real percentage
        (via _import_progress_user()), rescaled onto that remaining span
        so the bar keeps climbing instead of resetting to 0% once the
        reimport itself starts reporting.
        """
        DOWNLOAD_START_PCT = 20
        DOWNLOAD_END_PCT = 30
        REIMPORT_START_PCT = 30

        sync_cutoff = time()
        started = monotonic()

        def download():
            return self.web_client.download_export()

        # Ticks once a second, capped at DOWNLOAD_END_PCT, for as long as
        # the download is in flight -- fires because
        # _run_async_to_completion()'s own wait loop below pumps this
        # same GLib main context. Cancelled in the finally below the
        # instant the download finishes (success, failure, or a closed
        # tree alike), so it never fires during the reimport phase, which
        # reports its own real percentages instead.
        pulse_source_id = None
        if progress_callback is not None:
            pulse_state = {"value": DOWNLOAD_START_PCT}

            def pulse():
                pulse_state["value"] = min(pulse_state["value"] + 1, DOWNLOAD_END_PCT)
                progress_callback(pulse_state["value"])
                return GLib.SOURCE_CONTINUE

            pulse_source_id = GLib.timeout_add_seconds(1, pulse)

        try:
            data = self._run_async_to_completion(
                lambda on_done, on_error: self.io_runner.run(
                    download, self._guarded(on_done), self._guarded(on_error)
                )
            )
        finally:
            if pulse_source_id is not None:
                GLib.source_remove(pulse_source_id)
        if data is None:
            # Tree closed while the download was in flight -- see
            # _run_async_to_completion()'s own docstring. Not expected in
            # practice for load()'s bootstrap case (see this method's own
            # docstring on why), but handled the same way the rest of
            # this file does rather than assumed away.
            LOG.debug("bootstrap resync: tree closed during download; aborting")
            return
        LOG.debug(
            "bootstrap resync: downloaded a %.1f MB export in %.2fs",
            len(data) / (1024 * 1024),
            monotonic() - started,
        )
        with NamedTemporaryFile(suffix=".gramps", delete=False) as tmp_file:
            tmp_file.write(data)
            tmp_path = tmp_file.name
        self._pulling = True
        try:
            before = self._snapshot_all_objects()
            birth_death_snapshot = _snapshot_birth_death_indices(self)
            cleared = 0
            with DbTxn(
                _("Clear local mirror before full resync"), self, batch=True
            ) as trans:
                for key in set(CLASS_TO_KEY_MAP.values()):
                    name = KEY_TO_NAME_MAP[key]
                    handles = list(getattr(self, f"get_{name}_handles")())
                    remove = getattr(self, f"remove_{name}")
                    for handle in handles:
                        remove(handle, trans)
                    cleared += len(handles)
            LOG.debug(
                "bootstrap resync: cleared %d local object(s); reimporting", cleared
            )
            imported_at = monotonic()
            if progress_callback is not None:

                def rescaled_progress(value):
                    progress_callback(
                        REIMPORT_START_PCT
                        + int(value * (100 - REIMPORT_START_PCT) / 100)
                    )

                import_user = _import_progress_user(rescaled_progress)
            else:
                import_user = User()
            importData(self, tmp_path, import_user)
            LOG.debug(
                "bootstrap resync: reimport left %d object(s) (%.2fs)",
                self.get_total(),
                monotonic() - imported_at,
            )
            if birth_death_snapshot:
                with DbTxn(
                    _("Restore birth/death event references lost on reimport"),
                    self,
                    batch=True,
                ) as trans:
                    restored = _restore_birth_death_indices(
                        self, birth_death_snapshot, trans
                    )
                if restored:
                    LOG.debug(
                        "bootstrap resync: restored birth/death event "
                        "reference index on %d person(s) Gramps XML "
                        "re-import can't preserve",
                        restored,
                    )
            self._describe_resync_to_views(before)
        finally:
            self._pulling = False
            os.remove(tmp_path)
        self._set_metadata("sync_last_time", sync_cutoff)
        if progress_callback is not None:
            progress_callback(100)

    def _snapshot_all_objects(self):
        """{(obj_class, handle): data} across every primary object the
        local mirror holds right now, ``data`` being the same
        json_utils-shaped, "_object"-stripped form transaction_to_json()
        sends as "old"/"new" (_iter_raw_data() reads it straight back out
        of storage via the same serializer _commit_base() wrote it with
        -- see dbapi.py). Two callers, both diffing a before/after pair
        via _diff_snapshots(): _reconcile_batch_commit() around a local
        batch=True transaction (transaction_begin()'s own call is the
        "before" half), and _full_resync_async()/_bootstrap_full_resync()
        around a full wipe-and-reimport (see _describe_resync_to_views()).

        Uses _iter_raw_data() (one bulk SELECT per object type) rather
        than _get_raw_data() per handle, so this is O(types) queries,
        not O(handles) -- cheap regardless of how many objects a batch
        operation actually touches.
        """
        snapshot = {}
        for obj_class, key in CLASS_TO_KEY_MAP.items():
            for handle, data in self._iter_raw_data(key):
                snapshot[(obj_class, handle)] = remove_object(data)
        return snapshot

    def _describe_resync_to_views(self, before):
        """Tell every already-open view what a full resync's clear+
        reimport actually changed -- called by _full_resync_async()'s
        rebuild() and _bootstrap_full_resync(), once each has finished
        reimporting (and, for the former, restoring whatever
        _restore_birth_death_indices() could).

        request_rebuild() (DbGeneric's own "too much changed to describe
        incrementally" signal, gen/db/generic.py) is correct for the
        genuinely-everything-changed case -- a brand new mirror, or one
        so far behind a repair effectively rebuilds it -- but it is
        needlessly disruptive for the far more common case this resync
        recovers from: a push conflict or a mirror-repair shortfall,
        where the mirror was already correct for everything except the
        handful of objects actually involved and the wipe+reimport was
        only ever a (surprisingly expensive) way to get back to that
        state. gramps.gui.displaystate.py's own History.history_changed()
        listens for exactly this signal and responds by resetting Active
        Person to find_initial_person() unconditionally -- confirmed live
        (2026-08-17): a user mid-edit on one Person, with a different
        Person active, would see Active Person silently reset out from
        under them on every conflict-triggered resync, since a plain
        commit conflict already means at least one resync ran before the
        edit could even be retried.

        _diff_snapshots() (the same before/after diff
        _reconcile_batch_commit() uses to reconstruct a local batch
        commit, minus the push -- what was just pulled *from* the server
        must never be pushed back) turns ``before`` and a fresh
        _snapshot_all_objects() into the same shape _emit_change_signals()
        already knows how to turn into precise person-add/family-update/
        event-delete/... signals. A view listening for those (rather than
        a blanket rebuild) only reloads what actually changed -- and
        History only resets Active Person if the active object's own
        handle is among them.

        GRANULAR_REBUILD_MAX_CHANGES caps this: above it, the diff itself
        is legitimately "everything" (an empty-mirror bootstrap, or a
        repair recovering from a mirror badly out of step), where one
        rebuild signal per type is cheaper for every view than replaying
        that many individual signals -- so request_rebuild() stays the
        right tool there. An empty diff (nothing genuinely changed --
        possible for a mirror-repair triggered by a totals check that
        turns out to have been spurious) skips telling views anything at
        all, rather than either signal shape.
        """
        entries = _diff_snapshots(before, self._snapshot_all_objects())
        if not entries:
            return
        if len(entries) > GRANULAR_REBUILD_MAX_CHANGES:
            self.request_rebuild()
            return
        net_changes = {
            (entry["_class"], entry["handle"]): _NAME_TO_TRANS_TYPE[entry["type"]]
            for entry in entries
        }
        self._emit_change_signals(net_changes)

    def _reconcile_batch_commit(self, before):
        """Reconstruct exactly what a local batch=True transaction
        changed, by diffing the pre-transaction object snapshot
        (transaction_begin()'s _snapshot_all_objects() call) against a
        fresh one taken now (via _diff_snapshots()), and push the result
        -- see the module docstring's note on why a batch commit is
        otherwise invisible to transaction_to_json().

        Getting "old" right this way -- genuinely the pre-transaction
        state, not whatever commit_<type>()/remove_<type>() happens to
        find in local storage if replayed afterward -- is the point.
        local storage by reconciliation time already holds the batch's
        own result, not what the mirror last actually synced with the
        server; replaying against it (an earlier version of this method
        did, via _retry_after_conflict()) sends a false "old" a real
        server always rejects as a conflict for an add, and a no-op
        "old"-matches-"new" for an update -- and for a delete, replaying
        against already-gone-for-real local storage does nothing at
        all, silently dropping it. Building the payload directly here
        instead avoids all three: pushed the same way as any other
        local edit (transaction_commit() -> _push_payload()), with that
        method's existing conflict handling (full resync then
        _retry_after_conflict()) intact for the rare case something
        else changed the same object in the meantime.

        Cost: a full before/after object snapshot, not just handle sets
        or timestamps -- see _snapshot_all_objects()'s own docstring for
        why, and why that stays cheap (O(types) queries) regardless. If
        this ever shows up as a real bottleneck, the fix is to make the
        batch operation's own transaction non-batch, not to make this
        cleverer.
        """
        entries = _diff_snapshots(before, self._snapshot_all_objects())
        if not entries:
            return
        LOG.info(
            "Reconstructed %d change(s) from a local batch transaction that "
            "Gramps did not record per-object; pushing them to the server.",
            len(entries),
        )
        self._start_push(entries)

    def _sync_from_server_async(
        self, on_done, on_error, progress_callback=None, verify_totals=False
    ):
        """
        Pull every transaction after the last-seen timestamp and replay
        its changes into the local mirror. Calls on_done(applied) with
        the number of changes applied.

        An empty "changes" list on a transaction is not a no-op: it is
        what a batch=True commit leaves behind (see the module
        docstring's note on trans.batch guards around trans.add()) --
        something happened server-side that this feed cannot describe.
        Flagged rather than silently skipped; _full_resync_async() is
        the fallback once the whole page range has been walked (so
        sync_last_time still advances past it and any *describable*
        changes around it are applied normally either way). A feed that
        is empty *altogether*, or too sparse to account for what the
        server holds, is the same kind of gap and gets the same
        fallback -- see _mirror_is_short_of_the_server_async(), which
        ``verify_totals`` asks for (load() does; the poll doesn't).

        progress_callback, if given, is called with an int 0-100 after
        each page -- see load()'s callback param. "total" comes from the
        server's X-Total-Count for this "after" filter (get_transaction_
        history()'s docstring), so it stays a stable denominator across
        pages barring concurrent server-side writes during the sync.

        Caller already owns self._syncing (see _start_push()'s
        docstring for why none of this file's ..._async() chains touch
        that flag themselves). Alternates io_runner (fetch one page) and
        runner (apply that page's batch DbTxn replay) for as many pages
        as the feed has -- a recursive continuation (_sync_page())
        rather than a fixed-length chain, since the page count isn't
        known up front.
        """
        started = monotonic()

        def after_flush(_result):
            after = self._get_metadata("sync_last_time", default=0)
            LOG.debug("sync: asking for transactions after %s", after)
            self._sync_page(
                after=after,
                page=1,
                seen=0,
                applied=0,
                skipped=0,
                needs_full_resync=False,
                started=started,
                progress_callback=progress_callback,
                verify_totals=verify_totals,
                on_done=on_done,
                on_error=on_error,
            )

        self._flush_pending_pushes_async(after_flush, on_error)

    def _sync_page(
        self,
        after,
        page,
        seen,
        applied,
        skipped,
        needs_full_resync,
        started,
        progress_callback,
        verify_totals,
        on_done,
        on_error,
    ):
        """_sync_from_server_async()'s per-page step: fetches one page
        on io_runner, applies it on runner, and recurses for the next
        page until the feed runs dry or hands back a short page."""
        run_id = self._run_id

        def fetch():
            # io_runner: network only.
            return self.web_client.get_transaction_history(
                after=after, page=page, pagesize=SYNC_PAGE_SIZE
            )

        def on_fetched(result):
            transactions, total = result
            if not transactions:
                self._finish_sync(
                    after,
                    seen,
                    applied,
                    skipped,
                    needs_full_resync,
                    started,
                    progress_callback,
                    verify_totals,
                    on_done,
                    on_error,
                )
                return

            def apply_page():
                # runner: self._pulling around a batch=True DbTxn
                # replay, then signal emission -- identical body to the
                # old synchronous per-page work, no pump in the middle.
                # Re-checks self._run_id itself, like
                # _full_resync_async()'s rebuild(): this step was
                # scheduled from inside an already-guarded callback
                # (on_fetched), and close() could in principle run in
                # the gap between that scheduling and this actually
                # executing -- see that method's own comment for the
                # fuller explanation.
                if self._run_id != run_id:
                    LOG.debug(
                        "sync: tree closed before this page was applied; "
                        "discarding it"
                    )
                    return None
                new_after = after
                # (obj_class, handle) -> trans_type, collapsed to the
                # net effect within this page -- see
                # _emit_change_signals().
                net_changes = {}
                new_applied = applied
                new_skipped = skipped
                new_needs_full_resync = needs_full_resync
                # _pulling marks this batch DbTxn as one of our own
                # replays, so transaction_begin() doesn't snapshot
                # handles for it and transaction_commit() doesn't try to
                # push it back out as if it were a local bulk edit -- see
                # the module docstring.
                self._pulling = True
                try:
                    with DbTxn("Sync from server", self, batch=True) as trans:
                        for server_trans in transactions:
                            if not server_trans["changes"]:
                                new_needs_full_resync = True
                            for change in server_trans["changes"]:
                                if self._apply_change(change, trans):
                                    new_applied += 1
                                    net_changes[
                                        (change["obj_class"], change["obj_handle"])
                                    ] = change["trans_type"]
                                else:
                                    # Reference-type changes and anything
                                    # else with no primary-object class
                                    # to map -- counted rather than
                                    # logged per change, which would be
                                    # one line per row of the feed.
                                    new_skipped += 1
                            new_after = max(new_after, server_trans["timestamp"])
                finally:
                    self._pulling = False
                self._emit_change_signals(net_changes)
                return new_after, new_applied, new_skipped, new_needs_full_resync

            def on_applied(result2):
                if result2 is None:
                    # Stale (see apply_page()'s own check) -- nothing to
                    # continue with. self._guarded() below already drops
                    # this same case for a tree closed *before*
                    # apply_page() even started; this covers the
                    # narrower gap where it closed after.
                    return
                (
                    new_after,
                    new_applied,
                    new_skipped,
                    new_needs_full_resync,
                ) = result2
                new_seen = seen + len(transactions)
                LOG.debug(
                    "sync: page %d, %d transaction(s) of %s, %d change(s) "
                    "applied so far, cursor %s",
                    page,
                    len(transactions),
                    total,
                    new_applied,
                    new_after,
                )
                if progress_callback is not None and total:
                    progress_callback(min(100, int(new_seen * 100 / total)))
                if len(transactions) < SYNC_PAGE_SIZE:
                    self._finish_sync(
                        new_after,
                        new_seen,
                        new_applied,
                        new_skipped,
                        new_needs_full_resync,
                        started,
                        progress_callback,
                        verify_totals,
                        on_done,
                        on_error,
                    )
                else:
                    self._sync_page(
                        after=new_after,
                        page=page + 1,
                        seen=new_seen,
                        applied=new_applied,
                        skipped=new_skipped,
                        needs_full_resync=new_needs_full_resync,
                        started=started,
                        progress_callback=progress_callback,
                        verify_totals=verify_totals,
                        on_done=on_done,
                        on_error=on_error,
                    )

            self.runner.run(
                apply_page, self._guarded(on_applied), self._guarded(on_error)
            )

        self.io_runner.run(fetch, self._guarded(on_fetched), self._guarded(on_error))

    def _finish_sync(
        self,
        after,
        seen,
        applied,
        skipped,
        needs_full_resync,
        started,
        progress_callback,
        verify_totals,
        on_done,
        on_error,
    ):
        """_sync_page()'s tail once the feed runs dry (immediately, or
        after the last, short page): persist the cursor, log a summary,
        fall back to a full resync if the feed couldn't describe
        everything (or, if asked, the mirror's own object count says
        it's short), and call on_done(applied). Always reached on the
        main thread (either from on_fetched()'s own immediate branch or
        from apply_page()'s on_applied(), a runner step's on_success),
        so self._set_metadata() here is safe."""
        self._set_metadata("sync_last_time", after)
        LOG.debug(
            "sync: %d change(s) applied, %d skipped, from %d transaction(s) "
            "in %.2fs; cursor now %s",
            applied,
            skipped,
            seen,
            monotonic() - started,
            after,
        )

        def maybe_full_resync(needs_resync):
            if needs_resync:
                # Deliver the record-sync's own applied count to on_done
                # regardless of the resync outcome, matching what the
                # old synchronous method always returned here -- a full
                # resync's own result isn't what a caller of *this*
                # method is asking about.
                self._full_resync_async(
                    lambda _: on_done(applied),
                    on_error,
                    progress_callback=progress_callback,
                )
            else:
                on_done(applied)

        if not needs_full_resync and verify_totals:
            self._mirror_is_short_of_the_server_async(maybe_full_resync, on_error)
        else:
            maybe_full_resync(needs_full_resync)

    def _mirror_is_short_of_the_server_async(self, on_done, on_error):
        """Whether the mirror holds fewer objects than the server says
        its tree has, once the incremental sync has had its turn -- the
        other way the history feed can fail to describe the server's
        state, alongside the empty-"changes" marker
        _sync_from_server_async() already watches for. Calls
        on_done(True) if the mirror is short and needs a full resync,
        on_done(False) otherwise.

        A server can hold a full tree that its history does not account
        for: that table only records what gramps-web-api itself wrote, so
        anything populated by another route (a server-side import straight
        into the database, a restored dump, a truncated history table) has
        nothing to replay. https://demo.grampsweb.org is exactly this --
        4668 people, and GET /transactions/history/ returned X-Total-Count
        0 until someone edited it through the API. Without this check,
        syncing such a server is *silently* wrong: load() succeeds, the
        feed describes only the handful of edits it does know about, and
        the user gets a Family Tree holding those and nothing else, with
        nothing in the log to say why.

        Comparing totals rather than asking whether the feed came back
        empty is what makes that case detectable at all. An empty feed is
        only the extreme of it: one API edit against a history-less server
        is enough to hand back a transaction, advance sync_last_time, and
        make the sync look like it worked. Both counts cover the same ten
        primary types (webapi_client.OBJECT_COUNT_KEYS mirrors Gramps'
        own DbGeneric.get_total()), so equality is the invariant this
        addon exists to maintain and a mirror that falls short of it is
        provably missing data -- _full_resync_async()'s wholesale XML
        export being the same recovery used for the empty-"changes" case,
        and for the same reason: the history cannot describe what is
        already there.

        Only run where _sync_from_server_async()'s caller asks for it --
        load(), not the 10-second poll (see POLL_INTERVAL_SECONDS): an
        outdated mirror is repaired when the tree is opened, not on a
        timer, so the extra GET /metadata/ costs one request per open and
        a rebuild can never land in the middle of a working session.

        Skipped outright while pushes are queued (see
        _queue_pending_push()): those are local edits the server has not
        accepted yet, so the two counts are legitimately out of step, and
        rebuilding from the server's export in that state would fight with
        work still waiting to go the other way.

        A *larger* local total isn't treated as damage: an extra local
        object is either something this mirror is about to push or
        something the export would silently destroy, neither of which a
        rebuild should decide on its own. Only a shortfall is repaired.

        The local total is a DB read (must run on runner); the server's
        count is a network call (must run on io_runner) -- one extra hop
        rather than reading self.dbapi from io_runner, consistent with
        every other DB-read-then-network-call split in this file.
        """
        if self._get_metadata("pending_pushes", default=[]):
            LOG.debug("Pending pushes queued; skipping the mirror total check.")
            on_done(False)
            return

        def read_local_total():
            return self.get_total()

        def on_local_total(local_total):
            def fetch_server_total():
                return self.web_client.get_object_count()

            def on_server_total(server_total):
                LOG.debug(
                    "totals: local mirror %d, server %d", local_total, server_total
                )
                if local_total >= server_total:
                    on_done(False)
                    return
                LOG.warning(
                    "Local mirror holds %d objects but the server reports "
                    "%d; its transaction history cannot account for the "
                    "difference, so the mirror is being rebuilt from a "
                    "full export.",
                    local_total,
                    server_total,
                )
                on_done(True)

            self.io_runner.run(
                fetch_server_total,
                self._guarded(on_server_total),
                self._guarded(on_error),
            )

        self.runner.run(
            read_local_total, self._guarded(on_local_total), self._guarded(on_error)
        )

    def _sync_media_files_async(self, on_done, on_error):
        """
        Download media files missing locally, then upload local media
        files the server doesn't have yet -- the file-transfer half of
        keeping the mirror in sync, alongside _sync_from_server()'s
        object-record replay (which only ever moves a Media object's
        *metadata* -- path, description, checksum, ... -- never the file
        the path points at). See the module docstring's note on why this
        runs on its own, coarser timer instead of every record-sync tick.

        A single file failing to transfer (network error, a stale handle,
        a 409 because something else uploaded it first) is logged and
        skipped rather than aborting the rest of the pass -- the same
        shape as _push_payload_async()'s error handling, just applied per
        file here since there is no single all-or-nothing request
        covering every file the way POST /transactions/ does for object
        records.

        Three steps, alternating io_runner (network) and runner (DB
        reads) -- the old per-file loop interleaved a DB read with a
        network call on every single file, which a worker thread must
        never do (self.dbapi is only safe to touch from the main thread),
        so this instead resolves every handle this pass will touch to a
        (handle, path) pair up front, on the main thread, before any
        network I/O starts:

          1. io_runner: ask the server which files it's missing.
          2. runner: resolve this pass's missing-local and missing-remote
             media to (handle, path) pairs (_scan_and_resolve_media()) --
             the last thing to touch self.dbapi.
          3. io_runner: actually move the files (_transfer_media_files()),
             pure network + local disk I/O.

        Calls on_done((downloaded, uploaded)) when finished. Caller
        already owns self._syncing (see the module docstring's note on
        why _push_payload_async()'s ..._async() methods never touch it
        themselves).
        """
        started = monotonic()

        def fetch_remote_missing():
            return self.web_client.get_missing_files()

        def on_remote_missing_fetched(remote_missing):
            def scan():
                return self._scan_and_resolve_media(remote_missing)

            def on_scanned(scan_result):
                missing_local, missing_remote = scan_result

                def transfer():
                    return self._transfer_media_files(missing_local, missing_remote)

                def on_transferred(transfer_result):
                    downloaded, uploaded = transfer_result
                    LOG.debug(
                        "media: %d missing locally (%d downloaded), %d missing "
                        "on the server (%d uploaded), in %.2fs",
                        len(missing_local),
                        downloaded,
                        len(missing_remote),
                        uploaded,
                        monotonic() - started,
                    )
                    if downloaded or uploaded:
                        LOG.info(
                            "Media file sync: downloaded %d file(s), uploaded "
                            "%d file(s).",
                            downloaded,
                            uploaded,
                        )
                    on_done((downloaded, uploaded))

                self.io_runner.run(
                    transfer, self._guarded(on_transferred), self._guarded(on_error)
                )

            self.runner.run(scan, self._guarded(on_scanned), self._guarded(on_error))

        self.io_runner.run(
            fetch_remote_missing,
            self._guarded(on_remote_missing_fetched),
            self._guarded(on_error),
        )

    def _scan_and_resolve_media(self, remote_missing):
        """Resolve this pass's missing-local and missing-remote media to
        ``(handle, path)`` pairs while still on the main thread -- DB
        reads (iter_media(), get_media_from_handle()) plus a cheap
        os.path.exists() check, no network. Ported from the old
        _missing_local_media_handles()/_missing_remote_media_handles(),
        fused with the local-object lookup the old per-file
        _download_one_media_file()/_upload_one_media_file() each did
        separately, so _transfer_media_files() below never needs to
        touch self.dbapi again once this returns -- see
        _sync_media_files_async()'s docstring for why that split exists.

        ``remote_missing`` is the server's own answer (web_client.
        get_missing_files()) to "which Media objects have no uploaded
        file yet" -- a list of dicts with a "handle" key.
        """
        missing_local = []
        for media in self.iter_media():
            path = media_path_full(self, media.get_path())
            if not os.path.exists(path):
                missing_local.append((media.handle, path))

        missing_remote = []
        for item in remote_missing:
            handle = item["handle"]
            try:
                obj = self.get_media_from_handle(handle)
            except HandleError:
                # The object was removed locally between the scan and here.
                continue
            path = media_path_full(self, obj.get_path())
            if os.path.exists(path):
                missing_remote.append((handle, path))
        return missing_local, missing_remote

    def _transfer_media_files(self, missing_local, missing_remote):
        """Actually move the files: pure network + local disk I/O, no
        self.dbapi touch at all -- every handle needed was already
        resolved to a path by _scan_and_resolve_media() on the main
        thread, so this is safe to run entirely on io_runner. A transfer
        failing (network error, a 409 because something else uploaded it
        first) is logged and skipped rather than aborting the rest of
        the pass.

        Logs by handle rather than gramps_id, unlike the old per-file
        helpers this replaces: gramps_id would mean a get_media_from_
        handle() call here, and this method must not touch self.dbapi.
        """
        downloaded = 0
        for handle, path in missing_local:
            try:
                self.web_client.download_media_file(handle, path)
            except _CONNECTION_ERRORS as err:
                LOG.warning(
                    "Failed to download media file for handle %s: %s", handle, err
                )
                continue
            downloaded += 1

        uploaded = 0
        for handle, path in missing_remote:
            try:
                if self.web_client.upload_media_file(handle, path):
                    uploaded += 1
            except _CONNECTION_ERRORS as err:
                LOG.warning(
                    "Failed to upload media file for handle %s: %s", handle, err
                )
        return downloaded, uploaded

    def _apply_change(self, change, trans):
        """Replay one server change into the local mirror. Returns True
        if it was a recognized primary-object change (as opposed to a
        reference-type change, which carries no obj_class we can map)."""
        obj_class = change["obj_class"]
        key = CLASS_TO_KEY_MAP.get(obj_class)
        if key is None:
            return False
        name = KEY_TO_NAME_MAP[key]
        handle = change["obj_handle"]
        if change["trans_type"] == TXNDEL:
            getattr(self, f"remove_{name}")(handle, trans)
        else:
            # add and update are both upserts at the DBAPI level, so
            # there's no need to treat them differently here.
            obj = data_to_object(change["new_data"])
            getattr(self, f"commit_{name}")(obj, trans)
        return True

    def _emit_change_signals(self, net_changes):
        """Emit the person-add/family-update/event-delete/... signals a
        normal (non-batch) local commit would have emitted for these same
        changes -- see the module docstring's note on why
        _sync_from_server()'s batch=True replay needs this done by hand.

        net_changes: {(obj_class, obj_handle): trans_type}, already
        collapsed to the net effect per handle (see _sync_from_server()).
        Unrecognized obj_class values (reference-type changes never reach
        here in the first place -- see _apply_change()) are skipped the
        same way _apply_change() skips them.

        Grouped and emitted in the same order DBAPI.transaction_commit()
        uses for a normal commit -- deletes and adds before updates -- so
        a view that (for instance) cares about total counts sees them
        change before it sees an in-place update to one of the survivors.
        """
        by_type = {TXNDEL: {}, TXNADD: {}, TXNUPD: {}}
        for (obj_class, handle), trans_type in net_changes.items():
            key = CLASS_TO_KEY_MAP.get(obj_class)
            if key is None:
                continue
            name = KEY_TO_NAME_MAP[key]
            by_type[trans_type].setdefault(name, []).append(handle)
        for trans_type in (TXNDEL, TXNADD, TXNUPD):
            for name, handles in by_type[trans_type].items():
                self.emit(name + _TRANS_TYPE_ACTION[trans_type], (handles,))
