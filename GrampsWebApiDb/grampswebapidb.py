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
fine, but _sync_from_server() cannot deserialize its transaction history.

Credentials come from a single environment variable, GRAMPS_WEB_API_KEY
(see webapi_client.py for its "<REFRESH_TOKEN>*<BASE64URL(URL)>" shape and
the tradeoffs of using a refresh token here rather than a real scoped
personal-access-token). There is deliberately no per-tree settings.ini and
no login dialog: the same env var also works as a bare SDK credential
(WebApiHandler.from_env()) for scripts that talk to the server directly,
without going through Gramps at all -- one credential, two consumers.

Because of that, nothing but the Family Tree's own name ties its local
mirror to one particular server account. _check_identity() requires that
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

The other place a DbTxn gets used is _sync_from_server() itself, applying
server-pulled changes -- that uses batch=True, and DBAPI._commit_base()
skips trans.add() entirely for batch transactions (see dbapi.py), so
transaction_to_json() naturally sees nothing there and no push happens.
No separate "am I currently syncing" flag is needed to stop synced
changes from being echoed straight back to the server.

_sync_from_server() can only replay what the history feed actually
logged, and a batch=True commit -- any bulk import, merge, or tool run
through gramps-web-api, not just a one-off -- logs nothing per-object:
DBAPI's own commit_*/remove_* methods guard their trans.add() undo-log
call with `if not trans.batch`, so a batch transaction leaves behind an
empty-changes marker (a real Transaction row, but with no Change rows)
instead of the usual per-object entries. Confirmed live: bulk-importing
example.gramps produced exactly one such marker, and the 2157 people it
added were otherwise invisible to this addon's sync no matter how often
it resynced, because the transaction history itself never recorded
them. _sync_from_server() treats an empty-changes transaction as a
signal that its history-replay approach cannot describe what happened,
and falls back to _full_resync() -- downloading the server's current
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
against the server's after each sync (_mirror_is_short_of_the_server(),
via _sync_from_server()'s verify_totals) and routes a shortfall to the
same _full_resync(). Comparing totals rather than watching for an empty
feed is what makes the case detectable: one API edit against such a
server is enough for the feed to hand back a transaction and for the
sync to look like it worked.

Pushes go out without force=1, so the server compares each item's "old"
snapshot against its own current data and rejects the whole batch with
WebApiPushConflict (see webapi_client.push_transaction()) if anything
changed server-side since the local mirror last synced -- a real, if
coarse, optimistic-concurrency check: the whole push either applies or
none of it does, with no indication of which item conflicted.

Neither side of this addon's own resync machinery can be trusted to
explain a conflict, and this is not a one-server edge case: gramps-web-
api's bulk-import path (POST /importers/<ext>/file -- GEDCOM, Gramps
XML, CSV, ...) runs the same batch=True import machinery a local Gramps
client's own Import menu action would, which never touches its
transaction-history table at all (DBAPI's own _commit_base() only calls
trans.add() when `not trans.batch`) -- ordinary server administration
for any real installation, not a quirk of any particular one. So: the
incremental history feed can be blind to an object's true current state
from the moment it was imported, and even this addon's own full-tree
resync (_full_resync(), the verify_totals=True fallback below and
load()'s) only proves the mirror was accurate at the moment its export
was taken -- seconds to tens of seconds before the retry actually goes
out, plenty of time for another push (through the API, so it would
appear in history) to land in between.

So: on a conflict, _push_payload() below resyncs from the server (with
verify_totals=True, the same defense load() uses, for its own sake --
other objects may genuinely have changed) and then, for a plain commit
(not an undo/redo -- see _retry_after_conflict()), replays each object's
intended *new* state as a fresh local edit via commit_<type>()/
remove_<type>(), the same as before -- except the "current" object each
add/update is merged against comes from a direct GET /<type>/<handle>
(WebApiHandler.get_object()) taken right before that replay, not from
the resync or the local mirror. That is the one thing this addon can
ask the server that is authoritative regardless of whether history or a
resync's snapshot can explain how the object got there. That fresh edit
goes through the normal transaction_commit() -> _push_payload() path
again with is_retry=True, so it carries an up-to-date "old" snapshot
matching what was just read, and will only be rejected a second time if
something changes server-side in the brief window since then -- in
which case it is logged and dropped rather than retried again, to avoid
retrying forever against a genuinely hot object.

For an add/update whose object still exists server-side (i.e. the
conflicting edit changed the same object rather than deleting it),
_merge_or_overwrite() below combines the two edits with the object's own
merge() -- the same list-unioning logic behind Gramps' Merge People/
Family/... tools (ported from GrampsWebSync's diffhandler.py, credit
David Straub, same license) -- rather than letting the retry blindly
clobber whatever the other side changed. merge() only unions *list*-valued
fields (notes, citations, media, urls, event/family refs, ...); it never
touches scalar fields (a name, a date, a gender), so two edits to the
exact same scalar field still resolve as local-overwrites-remote -- real
field-level conflict *resolution* for that narrower case (diff, prompt the
user) is still out of scope. If the push fails for a non-conflict reason
(network error, auth failure), the local commit has already happened and
is not rolled back -- the local mirror just drifts from the server until
the next successful push or read sync.

Not every local batch=True commit is a pull-side replay, though: the same
trans.batch guard that makes _sync_from_server()'s own replay silent to
transaction_to_json() applies equally to *local* bulk operations run
against this open tree from outside this file entirely -- ImportXml/
ImportGedcom/ImportCsv/..., and stock Tools like Check and Repair
Database, Media Manager, Extract Information from Names, Rename Event
Types, Reorder Gramps IDs, and Sort Events all open their own DbTxn with
batch=True for performance. Left alone, any of those would apply locally
and never reach the server: transaction_commit() would see the same empty
transaction_to_json() payload it correctly sees for _sync_from_server()'s
own pull-side batch replay, with nothing in the payload itself to tell the
two apart. transaction_begin() (called by DbTxn.__enter__, so before the
batch operation's body runs) tells them apart with a _pulling flag set
only around _sync_from_server()'s own batch DbTxns (including the ones
_full_resync() opens) -- everywhere else, a batch=True transaction gets a
snapshot of every primary object type's handle set stashed on the
transaction itself (_handles_by_class()). transaction_commit() diffs that
snapshot against the post-commit state (_reconcile_batch_commit()) to
reconstruct what changed: a handle that appeared is an add, one that
disappeared is a delete, and one that persisted but whose .change moved to
at or after the transaction's own start_time was an update -- _commit_
base() always stamps .change on every commit, batch or not; only the
undo-log recording that batch skips is what normally would have let
transaction_to_json() see this directly. The reconstructed entries are
handed to _retry_after_conflict() -- not because anything conflicted, but
because it already does exactly what's needed here: replay each entry as
a fresh, ordinary (non-batch) local edit, so it picks up a real "old"
snapshot from DBAPI's own commit path and goes out through the normal
push path one object at a time, with the same conflict handling a live
edit gets. This costs roughly double the local writes for whatever the
batch operation actually touched (once for the batch commit, once more
for this replay) -- accepted as the price of correctness, the same trade
_full_resync() already makes for the equivalent pull-side blind spot.

A second, previously-unhandled kind of silent drift: when a push's own
HTTP call fails for a plain connectivity reason (network down, server
unreachable -- not a conflict), the local commit has already happened and
is never rolled back, but until now nothing remembered that the push
still needed to go out -- "the next successful push or read sync" above
was aspirational, not implemented. _push_payload() now persists such a
payload (via _set_metadata(), the same mechanism sync_last_time already
uses, so it survives close()/reopen) to a "pending_pushes" queue instead
of just logging and forgetting it. _flush_pending_pushes(), called at the
top of every _sync_from_server() (both the load()-time call and every
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
export, which _full_resync() would then import over a wiped local mirror,
quietly dropping every private record from the mirror. Checking the
permission set up front costs no extra round trip (gramps-web-api puts it
in the access token's own claims, so get_permissions() just decodes the
JWT already in hand) and names exactly what is missing. A tree opened
read-only (DBMODE_R) never pushes, so it is held to the read permission
only.

GET /metadata/ (cached per handler; needs no special permission) supplies
the two versions the addon reasons about. The server's *Gramps* version
gates compatibility outright: _check_server_version() refuses at load()
below MIN_SERVER_GRAMPS_VERSION, since anything older serializes its
transaction history in the pre-6.0 shape and would otherwise fail much
later as a bare KeyError out of data_to_object() mid-sync. It is
deliberately lenient about a server that reports no parseable version at
all -- better to try than to block on a guess.

The server's *gramps-web-api* version gates one optimization: from 2.7,
POST /transactions/ accepts ?background=1, queueing the work and
answering 202 immediately instead of holding the connection open while it
processes. _push_payload() uses that only for payloads at or above
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
that re-runs _sync_from_server() for as long as the database stays open --
the same timestamp-cursor poll gramps-connect's browser client uses against
this same endpoint (see gramps-connect's store/historyPoll.ts), so a change
made from any other client shows up here without closing and reopening the
tree. It runs synchronously on the GTK main thread (like the initial
load()-time sync already did, and like viewmanager.py's own autobackup
timer) rather than on a background thread -- correct but simple, at the
cost of a brief UI pause during each poll's network round trip; moving it
off-thread (GrampsWebSync's GLibTaskRunner is the precedent, not imported
here for the same no-cross-addon-dependency reason as transaction_to_json()
below) is a reasonable future improvement, not attempted here. close()
cancels the pending timeout so a closed database doesn't keep polling.

A server that stops answering does not interrupt the session: the poll
reports the outage once, backs off towards POLL_BACKOFF_MAX_SECONDS while
it lasts, and picks the mirror up again from the persisted sync cursor on
the first tick that succeeds -- meanwhile local edits go on working
against the mirror and queue for push (see _queue_pending_push()). See
_poll_tick() and _record_poll_failure().

Keeping the GUI alive
---------------------
All of that network work runs synchronously on the GTK main thread, so
anything long -- the initial catch-up, a full-export rebuild, a first
media sync, a backgrounded push being waited on -- is time the main loop
is not answering. The window stops redrawing and the window manager
offers to force-quit Gramps. _pump_main_loop() gives the loop its turn at
the boundaries of each of those (between sync pages, between media files,
across the export download's chunks and the task-poll loop, either side
of ImportXml), which keeps the window live and Gramps' own progress bar
moving. Doing the work off-thread would be the real fix and remains the
better long-term answer (GrampsWebSync's GLibTaskRunner is the
precedent); this is the version that doesn't restructure every call path.
Pumping re-enters, so the poll timeouts check _syncing and skip a tick
rather than starting a second sync underneath the first.

Reentering the main loop can also let the *user* act on this very Family
Tree while a pump-driven operation is suspended partway through it --
switching to another tree or quitting Gramps calls close() from a GTK
event dispatched during the pump, which closes self.dbapi's connection
out from under the still-running caller. Left unhandled, that caller
resumes after the pump and crashes on its next database touch
(sqlite3.ProgrammingError: Cannot operate on a closed database) instead
of unwinding cleanly. Every _pump_main_loop() call this class makes goes
through _guarded_pump() instead of the bare function for exactly this
reason: it raises _DatabaseClosed if close() ran during that pump, and
the entry points that can trigger one (_poll_tick(), _media_poll_tick(),
load(), _push_payload(), _flush_pending_pushes()) catch it as "nothing
left to do here", not a failure.

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
POLL_INTERVAL_SECONDS) drives _sync_media_files(): downloading media files
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

_sync_from_server()'s replay runs inside a batch=True DbTxn deliberately
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

A _full_resync() (see below) is the one path that doesn't go through
_emit_change_signals(): a full wipe-and-reimport is exactly the "too much
changed to describe incrementally" case DbGeneric's own request_rebuild()
exists for (it emits a single <type>-rebuild signal per object type,
telling every view to reload wholesale rather than replay a specific
add/update/delete) -- so _full_resync() calls that once after a successful
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
from gramps.gen.lib.json_utils import data_to_object, object_to_data, remove_object
from gramps.gen.user import User
from gramps.gen.utils.file import media_path_full
from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.plugins.importer.importxml import importData

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

#: Server-side permission names (gramps-web-api's auth/const.py) this
#: addon depends on, checked at load() by _check_permissions().
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
#: Checked at load() by _check_server_version() so an incompatible server
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
    """Dispatch whatever the main loop has pending, without blocking.

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
    """
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


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


def _is_retryable_push_error(err):
    """Whether a failed push is worth queueing for a later retry.

    A 4xx is the server's considered answer about *this* request -- 403
    (the account lacks AddObject/EditObject/DeleteObject; see
    _check_permissions()), 404, or a 400 that push_transaction() already
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
#: _check_identity() normalizes through this same substitution on both
#: sides before comparing -- see that method.
_FAMILY_TREE_NAME_UNSAFE_CHARS = re.compile(r"[':<>|,;=\"\[\]\.\+\*\/\?\\]")

_TRANS_TYPE_NAME = {TXNADD: "add", TXNUPD: "update", TXNDEL: "delete"}

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


def _merge_or_overwrite(current, local_obj):
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
    """
    if type(current).merge is BaseObject.merge:
        return local_obj
    merged = deepcopy(current)
    local_copy = deepcopy(local_obj)
    local_copy.gramps_id = None
    merged.merge(local_copy)
    return merged


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

    #: Set for the duration of a sync (records or media files), so the
    #: timeouts don't start a second one underneath the first when
    #: _pump_main_loop() hands the main loop back mid-operation.
    _syncing = False

    #: Set by close(), before anything else it does, so a pump-driven
    #: sync/push suspended elsewhere on the call stack sees it as soon as
    #: the main loop gives control back -- see _guarded_pump().
    _closed = False

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

        # Local mirror: reuse SQLite's own _initialize for the on-disk
        # cache file, then sync from the server on load().
        super()._initialize(directory, username, password)

    def load(self, *args, **kwargs):
        # callback is Gramps' own load-progress hook -- position 2 in
        # DbGeneric.load()'s signature, or the "callback" kwarg -- the same
        # plain percentage function cli/grampscli.py's _pulse_progress and
        # gui/dbloader.py's real progress-bar wiring already provide.
        # Forwarded to _sync_from_server() so a slow initial catch-up (a
        # new mirror, or one that's been offline a while) shows real
        # progress instead of Gramps just looking hung; _poll_tick()'s own
        # background-poll call deliberately leaves this at its None
        # default, since a 10-second background tick shouldn't pop a
        # progress bar.
        callback = kwargs.get("callback")
        if callback is None and len(args) >= 2:
            callback = args[1]
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
        self._check_identity()
        self._check_permissions(writable=(mode == DBMODE_W))
        self._check_server_version()
        try:
            self._sync_from_server(progress_callback=callback, verify_totals=True)
        except _DatabaseClosed:
            # The tree was closed (or switched away from) while this
            # initial sync was suspended mid-pump -- see _guarded_pump().
            # Nothing left to open; don't schedule polling for it.
            LOG.debug("load: tree closed during initial sync; aborting")
            return
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(
                _describe_connection_error(err), self._directory
            ) from err
        # Fresh outage state for a freshly opened tree: these are class
        # attributes, so an instance reused across a close()/load() would
        # otherwise start out backed off from the previous tree's outage.
        self._poll_failures = 0
        self._media_poll_failures = 0
        self._poll_interval = POLL_INTERVAL_SECONDS
        try:
            self._sync_media_files()
        except _DatabaseClosed:
            LOG.debug("load: tree closed during initial media sync; aborting")
            return
        except _CONNECTION_ERRORS:
            # Unlike the record sync above, a media-file-sync failure here
            # doesn't block opening the tree: the record mirror is already
            # usable, and missing/un-uploaded media files are recovered on
            # the next successful media poll (or the next load()).
            LOG.exception("Initial media file sync failed; will retry.")
            # Counts as this outage's one loud report, so _media_poll_tick()
            # doesn't immediately say the same thing again 300 seconds later.
            self._media_poll_failures = 1
        self._poll_source_id = GLib.timeout_add_seconds(
            POLL_INTERVAL_SECONDS, self._poll_tick
        )
        self._media_poll_source_id = GLib.timeout_add_seconds(
            MEDIA_POLL_INTERVAL_SECONDS, self._media_poll_tick
        )

    def _check_identity(self):
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
        """
        try:
            expected = self.web_client.get_identity()
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(
                _describe_connection_error(err), self._directory
            ) from err
        expected_typeable = _FAMILY_TREE_NAME_UNSAFE_CHARS.sub("_", expected)
        actual = self.get_dbname()
        actual_normalized = _FAMILY_TREE_NAME_UNSAFE_CHARS.sub("_", actual)
        if actual_normalized != expected_typeable:
            raise DbConnectionError(
                _(
                    'This Family Tree is named "%(actual)s", but '
                    "GRAMPS_WEB_API_KEY currently authenticates as "
                    '"%(expected)s". Rename this Family Tree to '
                    '"%(expected_typeable)s" (Family Trees -> Manage '
                    "Family Trees) if it's meant to mirror that account, "
                    "or open/create the Family Tree already named that -- "
                    "reusing this one would mix its existing local data "
                    "with the other account's."
                )
                % {
                    "actual": actual,
                    "expected": expected,
                    "expected_typeable": expected_typeable,
                },
                self._directory,
            )

    def _check_permissions(self, writable=True):
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
        """
        required = [_PERM_VIEW_PRIVATE]
        if writable:
            required += list(_WRITE_PERMISSIONS)
        try:
            granted = set(self.web_client.get_permissions())
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(
                _describe_connection_error(err), self._directory
            ) from err
        missing = [perm for perm in required if perm not in granted]
        if not missing:
            return
        raise DbConnectionError(
            _(
                "The account authenticating via GRAMPS_WEB_API_KEY is "
                "missing server permission(s) this addon requires: "
                "%(missing)s. Grant it at least the "
                '"%(role)s" role on the server (or ask an administrator '
                "to), then reopen this Family Tree. Opening it as-is would "
                "leave the local mirror silently incomplete or unable to "
                "save changes back."
            )
            % {"missing": ", ".join(missing), "role": _REQUIRED_ROLE_NAME},
            self._directory,
        )

    def _check_server_version(self):
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
        """
        try:
            reported = self.web_client.get_gramps_version()
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(
                _describe_connection_error(err), self._directory
            ) from err
        version = parse_version(reported)
        if version is None or version >= MIN_SERVER_GRAMPS_VERSION:
            return
        raise DbConnectionError(
            _(
                "This server runs Gramps %(actual)s, but this addon needs "
                "a server running Gramps %(required)s or newer: older "
                "servers serialize their transaction history in a format "
                "it cannot read. Upgrade the Gramps installation behind "
                "the Gramps Web API server (or ask its administrator to)."
            )
            % {
                "actual": reported,
                "required": ".".join(str(part) for part in MIN_SERVER_GRAMPS_VERSION),
            },
            self._directory,
        )

    def close(self, *args, **kwargs):
        # Set first, before anything else: a sync/push elsewhere on the
        # call stack may be suspended inside _guarded_pump(), waiting to
        # find out whether it's still safe to touch self.dbapi once the
        # main loop hands control back. See _guarded_pump() and the module
        # docstring's "Keeping the GUI alive" section.
        self._closed = True
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
        """
        _pump_main_loop()
        if self._closed:
            raise _DatabaseClosed()

    def _poll_tick(self):
        """GLib.timeout_add_seconds callback -- see the module docstring's
        polling section. Must return True (GLib.SOURCE_CONTINUE) to keep
        firing; returning a falsy value cancels the timeout, so a network
        error is caught and handled here rather than left to propagate.

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
            # Reached from inside _pump_main_loop(), part-way through a
            # sync this would otherwise start again underneath itself.
            LOG.debug("poll: a sync is already running; skipping this tick")
            return GLib.SOURCE_CONTINUE
        try:
            self._sync_from_server()
        except _DatabaseClosed:
            # The tree got closed (or switched away from) while this tick
            # was suspended mid-sync -- see _guarded_pump(). The GLib
            # source is already gone (close() removed it); nothing more
            # to do or report.
            LOG.debug("poll: tree closed mid-sync; stopping this timer")
            return GLib.SOURCE_REMOVE
        except _CONNECTION_ERRORS as err:
            return self._record_poll_failure(err)
        if self._poll_failures:
            LOG.info(
                "Sync from server succeeded again after %d failed attempt(s).",
                self._poll_failures,
            )
            self._poll_failures = 0
        return self._reschedule_poll(POLL_INTERVAL_SECONDS)

    def _record_poll_failure(self, err):
        """Handle a failed _poll_tick() sync: report it (once per outage,
        with the detail kept at DEBUG for whoever is diagnosing one) and
        slow the timer down, doubling up to POLL_BACKOFF_MAX_SECONDS.

        Returns what _poll_tick() must return: GLib.SOURCE_REMOVE if the
        interval changed (_reschedule_poll() has already installed the
        replacement timeout), GLib.SOURCE_CONTINUE otherwise."""
        self._poll_failures += 1
        interval = min(self._poll_interval * 2, POLL_BACKOFF_MAX_SECONDS)
        if self._poll_failures == 1:
            LOG.warning(
                "Periodic sync from server failed (%s); retrying, backing off "
                "to at most every %d seconds until the server answers again.",
                err,
                POLL_BACKOFF_MAX_SECONDS,
            )
            LOG.debug("Periodic sync failure detail", exc_info=True)
        else:
            LOG.debug(
                "Periodic sync from server still failing after %d attempts (%s); "
                "next retry in %d seconds.",
                self._poll_failures,
                err,
                interval,
                exc_info=True,
            )
        return self._reschedule_poll(interval)

    def _reschedule_poll(self, interval):
        """Point the record poll at a new interval, GLib.timeout_add_
        seconds() having no way to retime an existing source: a fresh
        timeout is installed and the caller (always _poll_tick(), the
        running callback) reports GLib.SOURCE_REMOVE so the old one is
        dropped rather than left firing alongside it. A no-op -- and so
        plain GLib.SOURCE_CONTINUE -- when the interval is unchanged,
        which is the common case on both a healthy poll and a failing one
        already sitting at POLL_BACKOFF_MAX_SECONDS."""
        if interval == self._poll_interval:
            return GLib.SOURCE_CONTINUE
        self._poll_interval = interval
        self._poll_source_id = GLib.timeout_add_seconds(interval, self._poll_tick)
        return GLib.SOURCE_REMOVE

    def _media_poll_tick(self):
        """GLib.timeout_add_seconds callback for the slower media-file
        scan -- same contract as _poll_tick() (must return True to keep
        firing; a connection error is caught and reported here rather than
        left to propagate), just for _sync_media_files() instead of the
        record-history poll.

        Reported once per outage for the same reason as _poll_tick(), but
        with no backoff to go with it: MEDIA_POLL_INTERVAL_SECONDS is
        already as coarse as that poll's backoff cap."""
        if self._syncing:
            LOG.debug("media poll: a sync is already running; skipping this tick")
            return GLib.SOURCE_CONTINUE
        try:
            self._sync_media_files()
        except _DatabaseClosed:
            LOG.debug("media poll: tree closed mid-sync; stopping this timer")
            return GLib.SOURCE_REMOVE
        except _CONNECTION_ERRORS as err:
            if self._media_poll_failures == 0:
                LOG.warning(
                    "Periodic media file sync failed (%s); will retry every "
                    "%d seconds.",
                    err,
                    MEDIA_POLL_INTERVAL_SECONDS,
                )
                LOG.debug("Periodic media file sync failure detail", exc_info=True)
            else:
                LOG.debug(
                    "Periodic media file sync still failing after %d attempts (%s).",
                    self._media_poll_failures + 1,
                    err,
                    exc_info=True,
                )
            self._media_poll_failures += 1
            return GLib.SOURCE_CONTINUE
        if self._media_poll_failures:
            LOG.info(
                "Media file sync succeeded again after %d failed attempt(s).",
                self._media_poll_failures,
            )
            self._media_poll_failures = 0
        return GLib.SOURCE_CONTINUE

    def transaction_begin(self, transaction):
        """Hook DbTxn.__enter__ (which calls this immediately, before the
        transaction's body runs) to snapshot the local per-type handle
        sets ahead of a batch=True transaction that isn't one of
        _sync_from_server()'s own (self._pulling) -- _reconcile_batch_
        commit() needs that "before" picture to diff against, since DBAPI
        skips its usual undo-log recording for a batch commit regardless
        of who started it. See the module docstring."""
        result = super().transaction_begin(transaction)
        if transaction.batch and not self._pulling:
            transaction._webapidb_before_handles = self._handles_by_class()
        return result

    def transaction_commit(self, transaction):
        # Must run before super(): it clears the transaction's records.
        payload = transaction_to_json(transaction)
        super().transaction_commit(transaction)
        before_handles = getattr(transaction, "_webapidb_before_handles", None)
        if before_handles is not None:
            self._reconcile_batch_commit(before_handles, transaction.start_time)
            return
        # self._retrying is set by _retry_after_conflict() while it holds
        # its own DbTxn open, so the push this commit triggers knows it is
        # itself a conflict retry and won't retry again on a second
        # conflict -- see _push_payload().
        self._push_payload(payload, is_retry=self._retrying)

    def undo(self, update_history=True):
        # Peek before super(): DbGenericUndo._undo() pops this DbTxn off
        # undoq. The DbTxn's own backing data isn't touched by that (it
        # just moves queues), so building its JSON payload could happen
        # either side of super() -- only grabbing the reference itself
        # can't wait.
        transaction = self.undodb.undoq[-1] if self.undodb.undo_count else None
        result = super().undo(update_history)
        if result and transaction is not None:
            self._push_payload(transaction_to_json(transaction), undo=True)
        return result

    def redo(self, update_history=True):
        transaction = self.undodb.redoq[-1] if self.undodb.redo_count else None
        result = super().redo(update_history)
        if result and transaction is not None:
            # Redo is just re-applying the original transaction forward --
            # not a variant of undo=True. See push_transaction()'s docstring.
            self._push_payload(transaction_to_json(transaction))
        return result

    def _push_payload(self, payload, undo=False, is_retry=False):
        """Push a change-list payload to the server, handling a rejected
        push (conflict or otherwise) the same way regardless of whether it
        came from a plain commit, an undo, or a redo.

        is_retry marks a push that is itself the replay _retry_after_conflict()
        made from an earlier conflict -- a second conflict on that replay is
        logged and dropped rather than retried again, so a genuinely hot
        object can't send this into an unbounded retry loop.
        """
        if not payload:
            return
        started = monotonic()
        background = self._use_background_push(payload)
        LOG.debug(
            "push: %d change(s) (%s)%s%s",
            len(payload),
            ", ".join(sorted({entry["type"] for entry in payload})),
            " undo" if undo else "",
            " background" if background else "",
        )
        try:
            self.web_client.push_transaction(
                payload, undo=undo, background=background, on_wait=self._guarded_pump
            )
            LOG.debug("push: accepted in %.2fs", monotonic() - started)
        except _DatabaseClosed:
            # The tree was closed (or switched away from) while this push
            # was suspended mid-wait -- see _guarded_pump(). Nothing left
            # to push to; the edit stays local and unsent.
            LOG.debug("push: tree closed mid-push; abandoning it")
            return
        except WebApiPushConflict:
            LOG.warning(
                "Server rejected %d local change(s): the object(s) changed "
                "server-side since the local mirror last synced. Resyncing "
                "the mirror from the server now.",
                len(payload),
            )
            try:
                # verify_totals=True, same as load(): a conflict can be
                # caused by a server-side change the incremental history
                # feed cannot describe at all -- a bulk import runs
                # entirely outside gramps-web-api's own transaction log
                # (see webapi_client.get_object()'s docstring), ordinary
                # server administration rather than an edge case -- as
                # easily as by an ordinary edit the feed would replay
                # normally. Without this, that resync can come back
                # describing nothing relevant either way; it is still
                # worth doing for its own sake (other objects may
                # genuinely have changed), just not trusted on its own
                # for the object(s) in this payload -- see
                # _retry_after_conflict()'s refresh_from_server below.
                self._sync_from_server(verify_totals=True)
            except _DatabaseClosed:
                LOG.debug("push: tree closed during conflict resync; abandoning it")
                return
            except _CONNECTION_ERRORS:
                LOG.exception("Resync after a push conflict also failed.")
                return
            if undo or is_retry:
                LOG.warning(
                    "Giving up on %d local change(s) after a repeated or "
                    "undo/redo conflict; the local mirror was not resent to "
                    "the server.",
                    len(payload),
                )
                return
            try:
                self._retry_after_conflict(payload, refresh_from_server=True)
            except _CONNECTION_ERRORS as err:
                # Nothing has been committed locally yet at this point --
                # see _retry_after_conflict()'s docstring -- so this is a
                # plain connectivity failure, queued like any other.
                LOG.warning(
                    "Could not fetch current server data for %d local "
                    "change(s) after a conflict (%s); queued for retry on "
                    "the next successful contact with the server.",
                    len(payload),
                    err,
                )
                self._queue_pending_push(payload, undo=undo)
        except _CONNECTION_ERRORS as err:
            if not _is_retryable_push_error(err):
                # A permission/payload rejection is not going to start
                # working on its own; queueing it would retry it on every
                # poll forever and eventually push real, retryable work out
                # of the capped queue.
                LOG.error(
                    "Server permanently rejected %d local change(s) (%s). "
                    "They will not be retried, and the local mirror has "
                    "drifted from the server for those object(s).",
                    len(payload),
                    err,
                )
                return
            LOG.exception(
                "Failed to push %d local change(s) to the server; queued "
                "for retry on the next successful contact with the server.",
                len(payload),
            )
            self._queue_pending_push(payload, undo=undo)

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

    def _flush_pending_pushes(self):
        """Retry queued pushes that previously failed for a connectivity
        reason, oldest first, stopping at the first that still can't be
        delivered -- see the module docstring on why this doesn't skip
        ahead past a stuck entry.

        A queued entry that comes back as a *conflict* rather than a
        connectivity failure is dropped rather than retried forever: by the
        time it is replayed the server has moved on, and _push_payload()'s
        resync-and-merge path needs an "old" snapshot contemporaneous with
        the edit, which a queued payload no longer has. An entry the server
        permanently rejects (see _is_retryable_push_error()) is likewise
        dropped rather than left to block the queue forever -- permissions
        may well have changed between queueing and now.
        """
        pending = self._get_metadata("pending_pushes", default=[])
        if not pending:
            return
        LOG.info("Retrying %d queued push(es) to the server.", len(pending))
        while pending:
            entry = pending[0]
            try:
                self.web_client.push_transaction(
                    entry["payload"],
                    undo=entry.get("undo", False),
                    background=self._use_background_push(entry["payload"]),
                    on_wait=self._guarded_pump,
                )
            except WebApiPushConflict:
                LOG.warning(
                    "A queued push of %d change(s) conflicts with the "
                    "server's current data and cannot be replayed safely; "
                    "dropping it. The local mirror has drifted from the "
                    "server for those object(s).",
                    len(entry["payload"]),
                )
            except _CONNECTION_ERRORS as err:
                if _is_retryable_push_error(err):
                    LOG.warning(
                        "Still unable to deliver %d queued push(es); will retry.",
                        len(pending),
                    )
                    break
                LOG.error(
                    "Server permanently rejected a queued push of %d "
                    "change(s) (%s); dropping it. The local mirror has "
                    "drifted from the server for those object(s).",
                    len(entry["payload"]),
                    err,
                )
            pending.pop(0)
        self._set_metadata("pending_pushes", pending)
        LOG.debug("queue: %d push(es) still pending after the flush", len(pending))

    def _retry_after_conflict(self, payload, refresh_from_server=False):
        """Reapply each locally-intended change as a fresh local edit --
        see the module docstring's write-through section. An add/update
        whose object still exists is combined with the current object via
        _merge_or_overwrite() rather than blindly replacing it.

        refresh_from_server, set only by _push_payload()'s conflict
        handler, reads each entry's "current" object with a direct
        GET /<type>/<handle> (WebApiHandler.get_object()) instead of the
        local mirror. A resync -- incremental, or the object-count check
        verify_totals asks for -- can be blind to what the server
        actually holds for this exact object: a bulk import never
        touches the transaction-history feed at all (see get_object()'s
        docstring), which is normal server administration for a real
        installation, not a rare condition, so the local mirror is not a
        reliable merge base right after a conflict. Fetched up front, all
        at once, before the DbTxn below opens -- so a network failure
        here fails cleanly with nothing committed locally yet, rather
        than leaving a partially-applied transaction; _push_payload()
        queues the whole payload for a later retry on that failure, the
        same as any other connectivity failure.

        _reconcile_batch_commit()'s call leaves this off -- replaying a
        local batch operation's own changes as a first push, not
        recovering from a conflict, so there is nothing to refresh
        against yet, and fetching every entry individually would cost one
        request per object for what can be a large batch.

        Runs as one ordinary (non-batch) DbTxn, so it goes through the
        normal transaction_commit() -> _push_payload() path again -- this
        time with an "old" snapshot that matches what was just read, so it
        will only be rejected again if something else changed server-side
        in the brief window since then.
        """
        fresh = {}
        if refresh_from_server:
            for entry in payload:
                if entry["type"] != "delete":
                    fresh[entry["handle"]] = self.web_client.get_object(
                        entry["_class"], entry["handle"]
                    )
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
                        if refresh_from_server:
                            server_data = fresh.get(handle)
                            if server_data is not None:
                                current = data_to_object(server_data)
                                obj = _merge_or_overwrite(current, obj)
                        elif has_handle(handle):
                            current = getattr(self, f"get_{name}_from_handle")(handle)
                            obj = _merge_or_overwrite(current, obj)
                        getattr(self, f"commit_{name}")(obj, trans)
        finally:
            self._retrying = False

    def _handles_by_class(self):
        """{obj_class: set(handles)} across every primary object type --
        the "before" snapshot transaction_begin() stashes on a local
        batch=True transaction for _reconcile_batch_commit() to diff
        against. See the module docstring."""
        return {
            obj_class: set(getattr(self, f"get_{KEY_TO_NAME_MAP[key]}_handles")())
            for obj_class, key in CLASS_TO_KEY_MAP.items()
        }

    def _reconcile_batch_commit(self, before_handles, start_time):
        """Reconstruct what a local batch=True transaction changed, by
        diffing the pre-transaction handle snapshot against the current
        state, and push it -- see the module docstring's note on why a
        batch commit is otherwise invisible to transaction_to_json().

        An object present now but not before is an add; one present before
        but not now is a delete; one present in both whose .change is at or
        after the transaction's start_time was updated during it
        (_commit_base() stamps .change on every commit, batch included).
        Objects the batch left untouched keep an older .change and are
        correctly skipped.

        The reconstructed entries go to _retry_after_conflict(), which
        replays each as an ordinary non-batch local edit -- so each one
        picks up a real "old" snapshot and goes out through the normal
        transaction_commit() -> _push_payload() path.

        Cost: the surviving-handle pass reads every primary object in the
        tree to check its .change, so this is O(total objects) per batch
        commit, not O(objects the batch touched). That is the same order
        as whatever opened a batch transaction in the first place (a bulk
        import writes everything; Check and Repair reads everything), and
        .change isn't a queryable secondary column in DBAPI's schema --
        only handle plus a couple of per-type extras are -- so there is no
        cheaper way to ask "what did this transaction touch" after the
        fact. If this ever shows up as a real bottleneck, the fix is to
        make the batch operation's own transaction non-batch, not to
        make this cleverer.
        """
        entries = []
        for obj_class, key in CLASS_TO_KEY_MAP.items():
            name = KEY_TO_NAME_MAP[key]
            before = before_handles.get(obj_class, set())
            after = set(getattr(self, f"get_{name}_handles")())
            for handle in after - before:
                entries.append({"type": "add", "handle": handle, "_class": obj_class})
            for handle in before - after:
                entries.append(
                    {"type": "delete", "handle": handle, "_class": obj_class}
                )
            get_obj = getattr(self, f"get_{name}_from_handle")
            for handle in after & before:
                if get_obj(handle).change >= start_time:
                    entries.append(
                        {"type": "update", "handle": handle, "_class": obj_class}
                    )
        if not entries:
            return
        LOG.info(
            "Reconstructed %d change(s) from a local batch transaction that "
            "Gramps did not record per-object; pushing them to the server.",
            len(entries),
        )
        self._retry_after_conflict(self._fill_entry_payloads(entries))

    def _fill_entry_payloads(self, entries):
        """Attach the "new" object data _retry_after_conflict() needs to
        each reconstructed add/update entry, read from the local mirror as
        it stands after the batch commit. A delete carries no "new" data,
        and an add/update whose handle has since vanished is dropped."""
        filled = []
        for entry in entries:
            if entry["type"] == "delete":
                filled.append({**entry, "old": None, "new": None})
                continue
            key = CLASS_TO_KEY_MAP[entry["_class"]]
            name = KEY_TO_NAME_MAP[key]
            try:
                obj = getattr(self, f"get_{name}_from_handle")(entry["handle"])
            except HandleError:
                continue
            filled.append(
                {**entry, "old": None, "new": remove_object(object_to_data(obj))}
            )
        return filled

    def _sync_from_server(self, progress_callback=None, verify_totals=False):
        """
        Pull every transaction after the last-seen timestamp and replay
        its changes into the local mirror. Returns the number of changes
        applied.

        An empty "changes" list on a transaction is not a no-op: it is
        what a batch=True commit leaves behind (see the module
        docstring's note on trans.batch guards around trans.add()) --
        something happened server-side that this feed cannot describe.
        Flagged rather than silently skipped; _full_resync() is the
        fallback once the whole page range has been walked (so
        sync_last_time still advances past it and any *describable*
        changes around it are applied normally either way). A feed that is
        empty *altogether*, or too sparse to account for what the server
        holds, is the same kind of gap and gets the same fallback -- see
        _mirror_is_short_of_the_server(), which ``verify_totals`` asks for
        (load() does; the poll doesn't).

        progress_callback, if given, is called with an int 0-100 after
        each page -- see load()'s callback param. "total" comes from the
        server's X-Total-Count for this "after" filter (get_transaction_
        history()'s docstring), so it stays a stable denominator across
        pages barring concurrent server-side writes during the sync.
        """
        self._syncing = True
        try:
            return self._sync_from_server_inner(progress_callback, verify_totals)
        finally:
            self._syncing = False

    def _sync_from_server_inner(self, progress_callback, verify_totals):
        """_sync_from_server()'s body, minus the _syncing bookkeeping --
        see that method for what this does and why."""
        self._flush_pending_pushes()
        after = self._get_metadata("sync_last_time", default=0)
        started = monotonic()
        LOG.debug("sync: asking for transactions after %s", after)
        applied = 0
        skipped = 0
        needs_full_resync = False
        page = 1
        seen = 0
        while True:
            transactions, total = self.web_client.get_transaction_history(
                after=after, page=page, pagesize=SYNC_PAGE_SIZE
            )
            if not transactions:
                break
            # (obj_class, handle) -> trans_type, collapsed to the net
            # effect within this page -- see _emit_change_signals().
            net_changes = {}
            # _pulling marks this batch DbTxn as one of our own replays, so
            # transaction_begin() doesn't snapshot handles for it and
            # transaction_commit() doesn't try to push it back out as if it
            # were a local bulk edit -- see the module docstring.
            self._pulling = True
            try:
                with DbTxn("Sync from server", self, batch=True) as trans:
                    for server_trans in transactions:
                        if not server_trans["changes"]:
                            needs_full_resync = True
                        for change in server_trans["changes"]:
                            if self._apply_change(change, trans):
                                applied += 1
                                net_changes[
                                    (change["obj_class"], change["obj_handle"])
                                ] = change["trans_type"]
                            else:
                                # Reference-type changes and anything else
                                # with no primary-object class to map --
                                # counted rather than logged per change,
                                # which would be one line per row of the
                                # feed.
                                skipped += 1
                        after = max(after, server_trans["timestamp"])
            finally:
                self._pulling = False
            self._emit_change_signals(net_changes)
            seen += len(transactions)
            LOG.debug(
                "sync: page %d, %d transaction(s) of %s, %d change(s) applied "
                "so far, cursor %s",
                page,
                len(transactions),
                total,
                applied,
                after,
            )
            if progress_callback is not None and total:
                progress_callback(min(100, int(seen * 100 / total)))
            # Between pages: a batch DbTxn has just closed and the next
            # one hasn't opened, so this is the one point in the replay
            # where handing the main loop back is safe. A catch-up of any
            # size would otherwise hold it for its whole duration.
            self._guarded_pump()
            if len(transactions) < SYNC_PAGE_SIZE:
                break
            page += 1
        # Also once on the way out: the loop above breaks before its own
        # pump whenever the feed hands back a short page or nothing at
        # all, which is every routine poll -- and each of those still
        # cost a blocking round trip to find out.
        self._guarded_pump()
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
        if not needs_full_resync and verify_totals:
            needs_full_resync = self._mirror_is_short_of_the_server()
        if needs_full_resync:
            self._full_resync(progress_callback=progress_callback)
        return applied

    def _mirror_is_short_of_the_server(self):
        """Whether the mirror holds fewer objects than the server says its
        tree has, once the incremental sync has had its turn -- the other
        way the history feed can fail to describe the server's state,
        alongside the empty-"changes" marker _sync_from_server() already
        watches for.

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
        provably missing data -- _full_resync()'s wholesale XML export
        being the same recovery used for the empty-"changes" case, and for
        the same reason: the history cannot describe what is already
        there.

        Only run where _sync_from_server()'s caller asks for it -- load(),
        not the 10-second poll (see POLL_INTERVAL_SECONDS): an outdated
        mirror is repaired when the tree is opened, not on a timer, so the
        extra GET /metadata/ costs one request per open and a rebuild can
        never land in the middle of a working session.

        Skipped outright while pushes are queued (see
        _queue_pending_push()): those are local edits the server has not
        accepted yet, so the two counts are legitimately out of step, and
        rebuilding from the server's export in that state would fight with
        work still waiting to go the other way.

        A *larger* local total isn't treated as damage: an extra local
        object is either something this mirror is about to push or
        something the export would silently destroy, neither of which a
        rebuild should decide on its own. Only a shortfall is repaired.
        """
        if self._get_metadata("pending_pushes", default=[]):
            LOG.debug("Pending pushes queued; skipping the mirror total check.")
            return False
        local_total = self.get_total()
        server_total = self.web_client.get_object_count()
        LOG.debug("totals: local mirror %d, server %d", local_total, server_total)
        if local_total >= server_total:
            return False
        LOG.warning(
            "Local mirror holds %d objects but the server reports %d; its "
            "transaction history cannot account for the difference, so the "
            "mirror is being rebuilt from a full export.",
            local_total,
            server_total,
        )
        return True

    def _full_resync(self, progress_callback=None):
        """
        Rebuild the local mirror from scratch: download the server's own
        current Gramps XML export and reimport it, after clearing every
        local primary object first. Called by _sync_from_server() when
        the transaction-history feed contains an empty-changes marker --
        by definition there is nothing in that history to replay for
        whatever produced it, so the only way to recover is to fetch the
        server's current state wholesale, the same way populating a
        brand new local mirror already works.

        Deliberately reuses the stock ImportXml importer against a raw
        XML export rather than reconstructing objects from the REST
        /people/, /families/, ... endpoints: those return a marshalled
        display schema (plain ints for GrampsType fields, no "_class"
        tag), not the json_utils shape data_to_object() needs. Only the
        transaction-history feed's new_data and a raw XML export share
        that shape, and the whole point of this method is that the
        former can't be trusted here.

        The clear-then-import pair each run inside their own batch=True
        DbTxn (ImportXml's own, internally, for the import half -- see
        importxml.py), both under the _pulling flag so transaction_commit()
        treats them as pull-side replays rather than local bulk edits to
        reconstruct and push back -- this is a purely local rebuild from
        what the server already has, same as _sync_from_server()'s own
        transactions.

        progress_callback, if given, only gets 0/100 markers bookending
        the download+reimport -- unlike _sync_from_server()'s page-by-page
        reporting, ImportXml has no internal step reporting to forward
        finer-grained progress from.

        Also (re)sets sync_last_time to a timestamp taken right before the
        export download starts, so the next incremental sync asks the
        history feed for changes after that point instead of wherever the
        walk that triggered this rebuild happened to leave the cursor --
        for the totals-shortfall case (_mirror_is_short_of_the_server()),
        that walk can be a single empty page, which leaves sync_last_time
        at its untouched starting value (0 for a brand new mirror) rather
        than anywhere near "now". Left uncorrected, every later poll asks
        for history "after 0" forever on a server whose history can't
        describe its own data anyway, so it's a harmless no-op -- but a
        *push conflict*'s own recovery (_push_payload()'s "resync from the
        server now, then retry") uses that exact same stuck cursor, so the
        resync it does can never actually pick up what changed and the
        retry is doomed to repeat the same conflict and give up. Taken
        before the download rather than after: a transaction the server
        commits while the export is being generated or transferred is
        safer to see again on the next poll (re-applying an already-
        reflected change is a no-op) than to have it fall silently before
        the cursor and only be discovered next time a shortfall check runs.
        """
        if progress_callback is not None:
            progress_callback(0)
        sync_cutoff = time()
        started = monotonic()
        # The single longest transfer this addon makes -- streamed rather
        # than read in one go so the main loop keeps its turn throughout
        # (see _guarded_pump() and download_export()'s on_chunk).
        data = self.web_client.download_export(on_chunk=self._guarded_pump)
        LOG.debug(
            "resync: downloaded a %.1f MB export in %.2fs",
            len(data) / (1024 * 1024),
            monotonic() - started,
        )
        with NamedTemporaryFile(suffix=".gramps", delete=False) as tmp_file:
            tmp_file.write(data)
            tmp_path = tmp_file.name
        # Last chance to let the main loop catch up while the mirror is
        # still intact: from here to request_rebuild() the local data is
        # being torn down and rebuilt, and anything dispatched in the
        # middle of that would be looking at a half-empty tree. See
        # _guarded_pump().
        self._guarded_pump()
        # Both halves below are pull-side rebuilds, not local edits -- see
        # _sync_from_server()'s own note on the _pulling flag. ImportXml
        # opens its own batch DbTxn internally, so this has to stay set
        # across importData() too, not just the explicit DbTxn above it.
        self._pulling = True
        try:
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
            # ImportXml exposes no per-step hook to drive (it never calls
            # User.step_progress), so this one call is uninterruptible --
            # the longest stall left in a rebuild, and the reason
            # off-thread sync remains the real fix. See the module
            # docstring's "Keeping the GUI alive".
            importData(self, tmp_path, User())
            LOG.debug(
                "resync: reimport left %d object(s) (%.2fs)",
                self.get_total(),
                monotonic() - imported_at,
            )
            # importData() runs its own batch=True DbTxn internally, so
            # (like _sync_from_server()'s replay) it emits nothing to
            # already-open views on its own -- request_rebuild() is the
            # "too much changed to describe incrementally" signal DbGeneric
            # itself defines for exactly this case (one <type>-rebuild per
            # object type, telling every view to reload wholesale).
            self.request_rebuild()
            # The mirror is whole again and every view has been told to
            # reload, so it's safe to let the loop run once more.
            self._guarded_pump()
        finally:
            self._pulling = False
            os.remove(tmp_path)
        self._set_metadata("sync_last_time", sync_cutoff)
        if progress_callback is not None:
            progress_callback(100)

    def _sync_media_files(self):
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
        shape as _push_payload()'s error handling, just applied per file
        here since there is no single all-or-nothing request covering
        every file the way POST /transactions/ does for object records.

        Returns ``(downloaded, uploaded)`` file counts.
        """
        self._syncing = True
        try:
            return self._sync_media_files_inner()
        finally:
            self._syncing = False

    def _sync_media_files_inner(self):
        """_sync_media_files()'s body, minus the _syncing bookkeeping --
        see that method for what this does and why."""
        started = monotonic()
        missing_local = self._missing_local_media_handles()
        downloaded = 0
        for handle in missing_local:
            if self._download_one_media_file(handle):
                downloaded += 1
            # One file is one blocking transfer; a first sync of a tree
            # with media runs hundreds of them back to back.
            self._guarded_pump()
        missing_remote = self._missing_remote_media_handles()
        uploaded = 0
        for handle in missing_remote:
            if self._upload_one_media_file(handle):
                uploaded += 1
            self._guarded_pump()
        LOG.debug(
            "media: %d missing locally (%d downloaded), %d missing on the "
            "server (%d uploaded), in %.2fs",
            len(missing_local),
            downloaded,
            len(missing_remote),
            uploaded,
            monotonic() - started,
        )
        if downloaded or uploaded:
            LOG.info(
                "Media file sync: downloaded %d file(s), uploaded %d file(s).",
                downloaded,
                uploaded,
            )
        return downloaded, uploaded

    def _missing_local_media_handles(self):
        """Handles of local Media objects whose file isn't on disk.
        Ported from GrampsWebSync's get_missing_files_local()."""
        return [
            media.handle
            for media in self.iter_media()
            if not os.path.exists(media_path_full(self, media.get_path()))
        ]

    def _missing_remote_media_handles(self):
        """Handles of Media objects the server has no uploaded file for
        yet. Ported from GrampsWebSync's get_missing_files_remote()."""
        return [item["handle"] for item in self.web_client.get_missing_files()]

    def _download_one_media_file(self, handle):
        """Download one locally-missing media file. Returns True on
        success; logs and returns False on a HandleError (the object was
        removed locally between the scan and here) or a connection error,
        rather than aborting the rest of _sync_media_files()'s pass."""
        try:
            obj = self.get_media_from_handle(handle)
        except HandleError:
            return False
        path = media_path_full(self, obj.get_path())
        try:
            self.web_client.download_media_file(handle, path)
        except _CONNECTION_ERRORS as err:
            LOG.warning("Failed to download media file for %s: %s", obj.gramps_id, err)
            return False
        return True

    def _upload_one_media_file(self, handle):
        """Upload one media file the server is missing. Returns True on
        success; False if the local object no longer exists, its file
        isn't actually on disk either (nothing to upload), the server
        already got a file for it from elsewhere in the meantime (a 409
        -- see WebApiHandler.upload_media_file()), or the upload
        otherwise failed."""
        try:
            obj = self.get_media_from_handle(handle)
        except HandleError:
            return False
        path = media_path_full(self, obj.get_path())
        if not os.path.exists(path):
            return False
        try:
            return self.web_client.upload_media_file(handle, path)
        except _CONNECTION_ERRORS as err:
            LOG.warning("Failed to upload media file for %s: %s", obj.gramps_id, err)
            return False

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
