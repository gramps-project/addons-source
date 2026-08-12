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

Pushes go out without force=1, so the server compares each item's "old"
snapshot against its own current data and rejects the whole batch with
WebApiPushConflict (see webapi_client.push_transaction()) if anything
changed server-side since the local mirror last synced -- a real, if
coarse, optimistic-concurrency check: the whole push either applies or
none of it does, with no indication of which item conflicted. On a
conflict, _push_payload() below resyncs from the server (so the local
mirror picks up whatever changed) and then, for a plain commit (not an
undo/redo -- see _retry_after_conflict()), replays each object's intended
*new* state as a fresh local edit via commit_<type>()/remove_<type>() on
top of that just-resynced data. That fresh edit goes through the normal
transaction_commit() -> _push_payload() path again with is_retry=True,
so it carries an up-to-date "old" snapshot and will only be rejected a
second time if something changes server-side in the brief window between
the resync and the retry -- in which case it is logged and dropped rather
than retried again, to avoid retrying forever against a genuinely hot
object.

For an add/update whose handle still exists after the resync (i.e. the
conflicting server-side edit changed the same object rather than deleting
it), _merge_or_overwrite() below combines the two edits with the object's
own merge() -- the same list-unioning logic behind Gramps' Merge People/
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

import logging
import os
import re
from copy import deepcopy
from tempfile import NamedTemporaryFile
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
LOG = logging.getLogger("grampswebapidb")

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


def _describe_connection_error(err):
    """
    Turn a _CONNECTION_ERRORS exception into DbConnectionError's message
    body. A 403 means the account GRAMPS_WEB_API_KEY authenticates as was
    correctly identified but isn't allowed to do this -- worth calling out
    specifically, since the raw HTTPError text ("HTTP Error 403:
    Forbidden") reads like an auth failure rather than a permissions one.
    """
    if isinstance(err, HTTPError) and err.code == 403:
        return _(
            "The account authenticating via GRAMPS_WEB_API_KEY does not "
            "have permission on the server for this operation (HTTP 403 "
            "Forbidden). Generate a key for an account with sufficient "
            "permissions, or ask the server administrator to grant this "
            "one access."
        )
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

    def requires_login(self):
        # Credentials come from GRAMPS_WEB_API_KEY, not a login dialog.
        return False

    def _initialize(self, directory, username, password):
        try:
            self.web_client = WebApiHandler.from_env()
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(_describe_connection_error(err), directory) from err

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
        super().load(*args, **kwargs)
        self._check_identity()
        self._check_permissions(writable=(mode == DBMODE_W))
        self._check_server_version()
        try:
            self._sync_from_server(progress_callback=callback)
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(
                _describe_connection_error(err), self._directory
            ) from err
        try:
            self._sync_media_files()
        except _CONNECTION_ERRORS:
            # Unlike the record sync above, a media-file-sync failure here
            # doesn't block opening the tree: the record mirror is already
            # usable, and missing/un-uploaded media files are recovered on
            # the next successful media poll (or the next load()).
            LOG.exception("Initial media file sync failed; will retry.")
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

    def _poll_tick(self):
        """GLib.timeout_add_seconds callback -- see the module docstring's
        polling section. Must return True (GLib.SOURCE_CONTINUE) to keep
        firing; returning a falsy value cancels the timeout, so a network
        error is caught and logged here rather than left to propagate."""
        try:
            self._sync_from_server()
        except _CONNECTION_ERRORS:
            LOG.exception("Periodic sync from server failed; will retry.")
        return GLib.SOURCE_CONTINUE

    def _media_poll_tick(self):
        """GLib.timeout_add_seconds callback for the slower media-file
        scan -- same contract as _poll_tick() (must return True to keep
        firing; a connection error is caught and logged here rather than
        left to propagate), just for _sync_media_files() instead of the
        record-history poll."""
        try:
            self._sync_media_files()
        except _CONNECTION_ERRORS:
            LOG.exception("Periodic media file sync failed; will retry.")
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
        try:
            self.web_client.push_transaction(
                payload, undo=undo, background=self._use_background_push(payload)
            )
        except WebApiPushConflict:
            LOG.warning(
                "Server rejected %d local change(s): the object(s) changed "
                "server-side since the local mirror last synced. Resyncing "
                "the mirror from the server now.",
                len(payload),
            )
            try:
                self._sync_from_server()
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
            self._retry_after_conflict(payload)
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

    def _retry_after_conflict(self, payload):
        """Reapply each locally-intended change on top of the mirror
        _push_payload() just resynced, as a fresh local edit -- see the
        module docstring's write-through section. An add/update whose
        object still exists after the resync is combined with the current
        (server-fresh) object via _merge_or_overwrite() rather than
        blindly replacing it.

        Runs as one ordinary (non-batch) DbTxn, so it goes through the
        normal transaction_commit() -> _push_payload() path again -- this
        time with an "old" snapshot that matches what the resync just
        pulled down, so it will only be rejected again if something else
        changed server-side in the brief window since that resync.
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

    def _sync_from_server(self, progress_callback=None):
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
        changes around it are applied normally either way).

        progress_callback, if given, is called with an int 0-100 after
        each page -- see load()'s callback param. "total" comes from the
        server's X-Total-Count for this "after" filter (get_transaction_
        history()'s docstring), so it stays a stable denominator across
        pages barring concurrent server-side writes during the sync.
        """
        self._flush_pending_pushes()
        after = self._get_metadata("sync_last_time", default=0)
        applied = 0
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
                        after = max(after, server_trans["timestamp"])
            finally:
                self._pulling = False
            self._emit_change_signals(net_changes)
            seen += len(transactions)
            if progress_callback is not None and total:
                progress_callback(min(100, int(seen * 100 / total)))
            if len(transactions) < SYNC_PAGE_SIZE:
                break
            page += 1
        self._set_metadata("sync_last_time", after)
        if needs_full_resync:
            self._full_resync(progress_callback=progress_callback)
        return applied

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
        """
        if progress_callback is not None:
            progress_callback(0)
        data = self.web_client.download_export()
        with NamedTemporaryFile(suffix=".gramps", delete=False) as tmp_file:
            tmp_file.write(data)
            tmp_path = tmp_file.name
        # Both halves below are pull-side rebuilds, not local edits -- see
        # _sync_from_server()'s own note on the _pulling flag. ImportXml
        # opens its own batch DbTxn internally, so this has to stay set
        # across importData() too, not just the explicit DbTxn above it.
        self._pulling = True
        try:
            with DbTxn(
                _("Clear local mirror before full resync"), self, batch=True
            ) as trans:
                for key in set(CLASS_TO_KEY_MAP.values()):
                    name = KEY_TO_NAME_MAP[key]
                    handles = list(getattr(self, f"get_{name}_handles")())
                    remove = getattr(self, f"remove_{name}")
                    for handle in handles:
                        remove(handle, trans)
            importData(self, tmp_path, User())
            # importData() runs its own batch=True DbTxn internally, so
            # (like _sync_from_server()'s replay) it emits nothing to
            # already-open views on its own -- request_rebuild() is the
            # "too much changed to describe incrementally" signal DbGeneric
            # itself defines for exactly this case (one <type>-rebuild per
            # object type, telling every view to reload wholesale).
            self.request_rebuild()
        finally:
            self._pulling = False
            os.remove(tmp_path)
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
        downloaded = 0
        for handle in self._missing_local_media_handles():
            if self._download_one_media_file(handle):
                downloaded += 1
        uploaded = 0
        for handle in self._missing_remote_media_handles():
            if self._upload_one_media_file(handle):
                uploaded += 1
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
