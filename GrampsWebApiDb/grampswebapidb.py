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
from copy import deepcopy
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError

from gi.repository import GLib

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.db import DbTxn
from gramps.gen.db.dbconst import (
    CLASS_TO_KEY_MAP,
    KEY_TO_CLASS_MAP,
    KEY_TO_NAME_MAP,
    TXNADD,
    TXNDEL,
    TXNUPD,
)
from gramps.gen.db.exceptions import DbConnectionError
from gramps.gen.lib.baseobj import BaseObject
from gramps.gen.lib.json_utils import data_to_object, remove_object
from gramps.gen.user import User
from gramps.plugins.db.dbapi.sqlite import SQLite
from gramps.plugins.importer.importxml import importData

from webapi_client import WebApiHandler, WebApiPushConflict

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

#: Failure modes from WebApiHandler.from_env()/push_transaction(): a
#: malformed/missing key (ValueError), a bad server response shape
#: (KeyError/JSONDecodeError, the latter a ValueError subclass), or the
#: server being unreachable (HTTPError/URLError/OSError -- socket.timeout
#: is an OSError subclass).
_CONNECTION_ERRORS = (ValueError, KeyError, HTTPError, URLError, OSError)

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

    def requires_login(self):
        # Credentials come from GRAMPS_WEB_API_KEY, not a login dialog.
        return False

    def _initialize(self, directory, username, password):
        try:
            self.web_client = WebApiHandler.from_env()
        except _CONNECTION_ERRORS as err:
            raise DbConnectionError(str(err), directory) from err

        # Local mirror: reuse SQLite's own _initialize for the on-disk
        # cache file, then sync from the server on load().
        super()._initialize(directory, username, password)

    def load(self, *args, **kwargs):
        super().load(*args, **kwargs)
        self._sync_from_server()
        self._poll_source_id = GLib.timeout_add_seconds(
            POLL_INTERVAL_SECONDS, self._poll_tick
        )

    def close(self, *args, **kwargs):
        # Stop polling a database that's no longer open -- otherwise the
        # next tick would run _sync_from_server() (and touch self.dbapi)
        # against a connection that's about to be (or already) closed.
        poll_source_id = getattr(self, "_poll_source_id", None)
        if poll_source_id is not None:
            GLib.source_remove(poll_source_id)
            self._poll_source_id = None
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

    def transaction_commit(self, transaction):
        # Must run before super(): it clears the transaction's records.
        payload = transaction_to_json(transaction)
        super().transaction_commit(transaction)
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
            self.web_client.push_transaction(payload, undo=undo)
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
        except _CONNECTION_ERRORS:
            LOG.exception(
                "Failed to push %d local change(s) to the server; "
                "local mirror has drifted from the server until the "
                "next successful push or read sync.",
                len(payload),
            )

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

    def _sync_from_server(self):
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
        """
        after = self._get_metadata("sync_last_time", default=0)
        applied = 0
        needs_full_resync = False
        page = 1
        while True:
            transactions, _total = self.web_client.get_transaction_history(
                after=after, page=page, pagesize=SYNC_PAGE_SIZE
            )
            if not transactions:
                break
            # (obj_class, handle) -> trans_type, collapsed to the net
            # effect within this page -- see _emit_change_signals().
            net_changes = {}
            with DbTxn("Sync from server", self, batch=True) as trans:
                for server_trans in transactions:
                    if not server_trans["changes"]:
                        needs_full_resync = True
                    for change in server_trans["changes"]:
                        if self._apply_change(change, trans):
                            applied += 1
                            net_changes[(change["obj_class"], change["obj_handle"])] = (
                                change["trans_type"]
                            )
                    after = max(after, server_trans["timestamp"])
            self._emit_change_signals(net_changes)
            if len(transactions) < SYNC_PAGE_SIZE:
                break
            page += 1
        self._set_metadata("sync_last_time", after)
        if needs_full_resync:
            self._full_resync()
        return applied

    def _full_resync(self):
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
        importxml.py), so neither triggers transaction_commit()'s
        push-to-server path (transaction_to_json() sees nothing to
        push for a batch transaction) -- this is a purely local rebuild,
        same as _sync_from_server()'s own transactions.
        """
        data = self.web_client.download_export()
        with NamedTemporaryFile(suffix=".gramps", delete=False) as tmp_file:
            tmp_file.write(data)
            tmp_path = tmp_file.name
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
            os.remove(tmp_path)

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
