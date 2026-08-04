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

Conflict handling is not implemented: pushes go out with force=1, which
skips the server's old-data-matches check entirely (see
gramps_webapi/api/tasks.py's process_transactions), so this is
last-write-wins by design. If the push itself fails (network error,
non-conflict validation error), the local commit has already happened
and is not rolled back -- the local mirror just drifts from the server
until the next successful push or read sync. Undo/redo integration is
also still out of scope.
"""

import logging
from urllib.error import HTTPError, URLError

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
from gramps.gen.lib.json_utils import data_to_object, remove_object
from gramps.plugins.db.dbapi.sqlite import SQLite

from webapi_client import WebApiHandler

_ = glocale.translation.gettext
LOG = logging.getLogger("grampswebapidb")

#: How many transactions to request per page while syncing.
SYNC_PAGE_SIZE = 100

#: Failure modes from WebApiHandler.from_env()/push_transaction(): a
#: malformed/missing key (ValueError), a bad server response shape
#: (KeyError/JSONDecodeError, the latter a ValueError subclass), or the
#: server being unreachable (HTTPError/URLError/OSError -- socket.timeout
#: is an OSError subclass).
_CONNECTION_ERRORS = (ValueError, KeyError, HTTPError, URLError, OSError)

_TRANS_TYPE_NAME = {TXNADD: "add", TXNUPD: "update", TXNDEL: "delete"}


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


class WebApiDB(SQLite):
    """
    DBAPI backend whose local SQLite connection is a mirror of a
    Gramps Web API server, kept in sync via the server's transaction
    history endpoint.
    """

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

    def transaction_commit(self, transaction):
        # Must run before super(): it clears the transaction's records.
        payload = transaction_to_json(transaction)
        super().transaction_commit(transaction)
        if payload:
            try:
                self.web_client.push_transaction(payload)
            except _CONNECTION_ERRORS:
                LOG.exception(
                    "Failed to push %d local change(s) to the server; "
                    "local mirror has drifted from the server until the "
                    "next successful push or read sync.",
                    len(payload),
                )

    def _sync_from_server(self):
        """
        Pull every transaction after the last-seen timestamp and replay
        its changes into the local mirror. Returns the number of changes
        applied.
        """
        after = self._get_metadata("sync_last_time", default=0)
        applied = 0
        page = 1
        while True:
            transactions, _total = self.web_client.get_transaction_history(
                after=after, page=page, pagesize=SYNC_PAGE_SIZE
            )
            if not transactions:
                break
            with DbTxn("Sync from server", self, batch=True) as trans:
                for server_trans in transactions:
                    for change in server_trans["changes"]:
                        if self._apply_change(change, trans):
                            applied += 1
                    after = max(after, server_trans["timestamp"])
            if len(transactions) < SYNC_PAGE_SIZE:
                break
            page += 1
        self._set_metadata("sync_last_time", after)
        return applied

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
