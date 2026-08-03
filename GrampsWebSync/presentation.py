# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       David Straub
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

"""Everything the interface needs that does not need GTK.

Two kinds of thing live here: the wording, and the shaping of session data into
something a widget can render row by row. Neither touches a widget, so both can
be tested without a display, and the rule for where a new string goes is simply
whether it needs GTK.

:func:`build_review` is the important one. The confirmation list used to show
*changes* -- what differs between the two trees -- while the user was choosing
a *mode* that decides what to do about them, so under "Reset remote to local"
rows filed under "Added" were in fact about to be deleted from the server. It
takes actions instead, grouped by the database they will change.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from const import (
    A_ADD_LOC,
    A_ADD_REM,
    A_DEL_LOC,
    A_DEL_REM,
    A_MRG_REM,
    A_UPD_LOC,
    A_UPD_REM,
    API_MAJOR_TEXT,
    MIN_API_VERSION_TEXT,
    MODE_BIDIRECTIONAL,
    MODE_RESET_TO_LOCAL,
    MODE_RESET_TO_REMOTE,
    Actions,
)
from gramps.gen.const import GRAMPS_LOCALE as glocale
from session import (
    STATUS_COMPARING,
    STATUS_CONNECTING,
    STATUS_FETCHING,
    STATUS_LOCAL_APPLIED,
    STATUS_PUSHING,
    STATUS_SCANNING_MEDIA,
    ErrorKind,
    State,
)

if TYPE_CHECKING:
    # Imported for annotations only: `adapters` pulls in GTK, and this module
    # stays importable without it.
    from adapters import KeyringUnavailable
    from session import SyncSession

LOG = logging.getLogger("grampswebsync")

assert glocale is not None  # for type checker
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
ngettext = _trans.ngettext

#: Gramps' own catalogue, for terms it already translates in every language.
#: Reusing them keeps object class names off the addon's translators' plate.
_core = glocale.translation.gettext

#: The tool's plugin id, as registered in ``grampswebsync.gpr.py``.
PLUGIN_ID = "gramps_web_sync"

#: How long a note excerpt may get before it is cut short.
NOTE_EXCERPT = 60


# ------------------------------------------------------------
#
# Versions
#
# ------------------------------------------------------------
def addon_version() -> str:
    """Return the addon's registered version.

    :returns: The version, or ``""`` if the plugin registry cannot supply it.
    """
    try:
        from gramps.gen.plug import PluginRegister

        plugin = PluginRegister.get_instance().get_plugin(PLUGIN_ID)
    except Exception as exc:  # noqa: BLE001 -- a version is never worth a crash
        LOG.debug("Cannot read the addon version: %s", exc)
        return ""
    return getattr(plugin, "version", "") or ""


def version_line(api_version: str | None) -> str:
    """Return the footer naming this addon and the server it is talking to.

    Shown so that a bug report says which build produced it, and so that a
    version mismatch is visible before it turns into a failure.

    :param api_version: The server's Gramps Web API version, once known.
    :returns: A one-line summary.
    """
    addon = addon_version() or _("unknown")
    if api_version:
        return _("Gramps Web Sync %(addon)s, Web API %(api)s") % {
            "addon": addon,
            "api": api_version,
        }
    return _("Gramps Web Sync %s") % addon


# ------------------------------------------------------------
#
# URLs
#
# ------------------------------------------------------------
def sanitize_url(url: str) -> str:
    """Return the URL to actually use for a server.

    Only completes what the user typed. The warning about plain http is a
    separate question, answered by :func:`is_insecure` as the URL is edited,
    rather than by a modal fired once the user has already moved on.

    :param url: The URL as typed.
    :returns: The URL with a scheme.
    """
    url = url.strip()
    if url and urlparse(url).scheme == "":
        return f"https://{url}"
    return url


def is_insecure(url: str) -> bool:
    """Whether ``url`` would send the password in clear text."""
    return urlparse(url.strip()).scheme == "http"


def insecure_warning() -> str:
    """Return the notice shown while an http URL is in the entry."""
    return _(
        "This URL uses http, so your password will be sent in clear text. "
        "Use only for local testing."
    )


# ------------------------------------------------------------
#
# Errors, status and other wording the view shows verbatim
#
# ------------------------------------------------------------
def keyring_message(problem: KeyringUnavailable) -> str:
    """Return the localized notice for an unusable keyring.

    :param problem: What the keyring reported.
    :returns: A message suitable for display.
    """
    if problem.snap_command:
        return _(
            "The system keyring could not be used. Snap confinement blocks "
            "access until you run: %s"
        ) % problem.snap_command
    return _(
        "The system keyring could not be used. "
        "You will need to enter your password each time."
    )


def error_message(kind: ErrorKind, detail: str = "") -> str:
    """Return the localized message for an error kind.

    Translation lives here rather than in :mod:`session` so the flow logic can
    be asserted on stable enum values instead of translated prose.

    :param kind: The classification recorded by the session.
    :param detail: Optional extra context, e.g. an HTTP status.
    :returns: A message suitable for display.
    """
    messages = {
        ErrorKind.AUTH_FAILED: _(
            "Authentication failed. Please check your username and password."
        ),
        ErrorKind.FORBIDDEN: _(
            "Access forbidden. Please check username and password."
        ),
        ErrorKind.NOT_FOUND: _("GrampsWeb service not found. Please check the URL."),
        ErrorKind.RATE_LIMITED: _(
            "Too many requests, please try again in a few seconds."
        ),
        ErrorKind.TREE_DISABLED: _("GrampsWeb tree is disabled."),
        ErrorKind.CONNECTION_FAILED: _(
            "Connection failed. Please check the URL and your internet connection."
        ),
        ErrorKind.INVALID_RESPONSE: _(
            "Invalid server response. Please check the URL."
        ),
        ErrorKind.INSUFFICIENT_PERMISSIONS: _(
            "Your user does not have sufficient server permissions to use sync."
        ),
        ErrorKind.XML_IMPORT_FAILED: _("Failed importing downloaded XML file."),
        ErrorKind.CONFLICT: _(
            "Unable to synchronize changes to server: objects have been modified."
        ),
        ErrorKind.APPLY_FAILED: _("Unexpected error while applying changes."),
        ErrorKind.STALE_LOCAL_DATA: _(
            "The family tree was modified while the changes were being "
            "reviewed. Nothing has been applied. Please compare again."
        ),
    }
    if kind is ErrorKind.SERVER_TOO_OLD:
        if detail:
            return _(
                "This server runs Gramps Web API %(found)s, but synchronization "
                "needs %(needed)s or newer. Please update the server."
            ) % {"found": detail, "needed": MIN_API_VERSION_TEXT}
        return _(
            "This server did not report a Gramps Web API version, so it is too "
            "old to synchronize with. Version %s or newer is needed."
        ) % MIN_API_VERSION_TEXT
    if kind is ErrorKind.SERVER_TOO_NEW:
        return _(
            "This server runs Gramps Web API %(found)s. This version of Gramps "
            "works with Gramps Web API %(major)s, so synchronizing with this "
            "server needs a newer version of Gramps."
        ) % {"found": detail, "major": API_MAJOR_TEXT}
    if kind is ErrorKind.SERVER_NO_TASK_QUEUE:
        return _(
            "This server is not configured to use a background task queue. "
            "Synchronization needs one: without it, applying changes times "
            "out before the server has finished. Please enable it on the "
            "server."
        )
    if kind is ErrorKind.SERVER_TASK_FAILED:
        return _("The server could not apply the changes: %s") % detail
    if kind is ErrorKind.SERVER_ERROR:
        return _("Server error %s. Please check your connection.") % detail
    if kind is ErrorKind.UNEXPECTED:
        return _("Unexpected error: %s") % detail
    return messages.get(kind, _("Unexpected error: %s") % detail)


def status_message(stage: str) -> str:
    """Return the detail line shown while a step runs."""
    messages = {
        STATUS_CONNECTING: _("Signing in…"),
        STATUS_FETCHING: _("Downloading the remote family tree…"),
        STATUS_COMPARING: _("Comparing the two family trees…"),
        STATUS_SCANNING_MEDIA: _("Checking which media files are missing…"),
        STATUS_LOCAL_APPLIED: _("Applied the changes to this computer."),
        STATUS_PUSHING: _("Sending the changes to the server…"),
    }
    return messages.get(stage, "")


def transfer_message(kind: str) -> str:
    """Return the detail line for a media transfer in progress.

    :param kind: The progress channel, as reported by the session.
    :returns: The message, or ``""`` for a channel that is not a transfer.
    """
    messages = {
        "download": _("Downloading media files…"),
        "upload": _("Uploading media files…"),
    }
    return messages.get(kind, "")


def state_label(state: State) -> str:
    """Return the name of one phase in the working pane's list."""
    labels = {
        State.CONNECTING: _("Connect"),
        State.COMPARING: _("Compare"),
        State.APPLYING: _("Apply changes"),
        State.TRANSFERRING: _("Transfer media files"),
    }
    return labels.get(state, "")


def mode_label(mode: int) -> str:
    """Return the name of a sync mode."""
    labels = {
        MODE_BIDIRECTIONAL: _("Bidirectional synchronization"),
        MODE_RESET_TO_LOCAL: _("Reset the server to match this computer"),
        MODE_RESET_TO_REMOTE: _("Reset this computer to match the server"),
    }
    return labels.get(mode, "")


def mode_description(mode: int) -> str:
    """Return the one-line explanation of a sync mode.

    With per-object selection out of scope the mode is the user's only control,
    so each option has to say what it will do.
    """
    descriptions = {
        MODE_BIDIRECTIONAL: _(
            "Changes from both sides are combined. Objects edited in both "
            "places are merged."
        ),
        MODE_RESET_TO_LOCAL: _(
            "The server is made to match this computer. Anything changed only "
            "on the server is discarded."
        ),
        MODE_RESET_TO_REMOTE: _(
            "This computer is made to match the server. Anything changed only "
            "here is discarded."
        ),
    }
    return descriptions.get(mode, "")


# ------------------------------------------------------------
#
# Describing objects
#
# ------------------------------------------------------------
def object_type_label(obj_type: str) -> str:
    """Return the localized name of a Gramps object class."""
    return _core(obj_type)


def object_id(obj, obj_type: str) -> str:
    """Return the Gramps ID of ``obj``.

    :returns: The ID, or ``""`` for a tag, which has none.
    """
    if obj_type == "Tag":
        return ""
    return getattr(obj, "gramps_id", "") or ""


def _describe(obj, obj_type: str, db) -> str:
    """Return a human-readable name for one object, without guarding."""
    if obj_type == "Person":
        from gramps.gen.display.name import displayer as name_displayer

        return name_displayer.display(obj)
    if obj_type == "Family":
        if db is None:
            return ""
        from gramps.gen.utils.db import family_name

        return family_name(obj, db)
    if obj_type == "Place":
        if db is not None:
            from gramps.gen.display.place import displayer as place_displayer

            return place_displayer.display(db, obj)
        return obj.get_title()
    if obj_type == "Event":
        return obj.get_description() or str(obj.get_type())
    if obj_type == "Media":
        return obj.get_description() or os.path.basename(obj.get_path() or "")
    if obj_type == "Note":
        text = " ".join((obj.get() or "").split())
        return text[:NOTE_EXCERPT] + "…" if len(text) > NOTE_EXCERPT else text
    if obj_type == "Source":
        return obj.get_title()
    if obj_type == "Citation":
        return obj.get_page()
    if obj_type == "Repository":
        return obj.get_name()
    if obj_type == "Tag":
        return obj.get_name()
    return ""


def describe_object(obj, obj_type: str, db=None) -> str:
    """Return a human-readable name for one object.

    A row identifying only a class and an ID -- "Person / I0123" -- tells the
    user nothing about what is being changed, which is the whole point of the
    review.

    :param obj: The object to describe.
    :param obj_type: Its Gramps class name.
    :param db: The database it came from, needed for the classes whose name is
        assembled from other objects. Omitting it degrades those to ``""``.
    :returns: The name, or ``""`` if none could be derived.
    """
    if obj is None:
        return ""
    try:
        return (_describe(obj, obj_type, db) or "").strip()
    except Exception as exc:  # noqa: BLE001 -- a label is never worth a crash
        LOG.debug("Cannot describe %s: %s", obj_type, exc)
        return ""


# ------------------------------------------------------------
#
# The review model
#
# ------------------------------------------------------------
#: Which database an action writes to.
LOCAL = "local"
REMOTE = "remote"

VERB_ADD = "add"
VERB_UPDATE = "update"
VERB_MERGE = "merge"
VERB_DELETE = "delete"

#: Verbs in the order they are listed, deletions last so the destructive part
#: of a group reads as the exception rather than the headline.
VERB_ORDER = (VERB_ADD, VERB_UPDATE, VERB_MERGE, VERB_DELETE)

#: What each action does, as ``(destination, verb)``. A merge writes the
#: combined object to both databases, so it has two effects and appears twice.
ACTION_EFFECTS: dict[str, tuple[tuple[str, str], ...]] = {
    A_ADD_LOC: ((LOCAL, VERB_ADD),),
    A_UPD_LOC: ((LOCAL, VERB_UPDATE),),
    A_DEL_LOC: ((LOCAL, VERB_DELETE),),
    A_ADD_REM: ((REMOTE, VERB_ADD),),
    A_UPD_REM: ((REMOTE, VERB_UPDATE),),
    A_DEL_REM: ((REMOTE, VERB_DELETE),),
    A_MRG_REM: ((LOCAL, VERB_MERGE), (REMOTE, VERB_MERGE)),
}


@dataclass(frozen=True)
class ObjectRow:
    """One object as it appears in the review list.

    :param type_label: The localized class name, e.g. "Person".
    :param name: What the object is called, or ``""`` if it has no name.
    :param gramps_id: Its Gramps ID, or ``""`` for a tag.
    """

    type_label: str
    name: str
    gramps_id: str


@dataclass(frozen=True)
class ActionGroup:
    """The objects one verb applies to, within one destination.

    :param verb: One of the ``VERB_*`` constants.
    :param rows: The objects, sorted.
    """

    verb: str
    rows: tuple[ObjectRow, ...]

    @property
    def count(self) -> int:
        """How many objects this verb applies to."""
        return len(self.rows)


@dataclass(frozen=True)
class Destination:
    """Everything that will change in one of the two databases.

    :param where: :data:`LOCAL` or :data:`REMOTE`.
    :param groups: The verbs applying there, in :data:`VERB_ORDER`.
    """

    where: str
    groups: tuple[ActionGroup, ...]

    @property
    def count(self) -> int:
        """How many objects will change here."""
        return sum(group.count for group in self.groups)


@dataclass(frozen=True)
class ReviewModel:
    """What a run will do, grouped for display.

    :param destinations: The databases that will change, local first. A
        database nothing happens to is left out.
    :param local_deletions: How many objects will be removed locally.
    :param remote_deletions: How many will be removed on the server.
    """

    destinations: tuple[Destination, ...]
    local_deletions: int
    remote_deletions: int

    @property
    def deletes(self) -> bool:
        """Whether anything will be removed on either side."""
        return bool(self.local_deletions or self.remote_deletions)


def _row_key(row: ObjectRow) -> tuple[str, str, str]:
    """Sort rows by type, then name, then ID, so a list never reshuffles."""
    return (row.type_label, row.name, row.gramps_id)


def build_review(actions: Actions, db1=None, db2=None) -> ReviewModel:
    """Group actions by the database they change and what they do to it.

    :param actions: The actions the selected sync mode produced.
    :param db1: The local database, for naming local objects.
    :param db2: The remote database, for naming objects only it has.
    :returns: The grouped model.
    """
    buckets: dict[tuple[str, str], list[ObjectRow]] = defaultdict(list)
    deletions = {LOCAL: 0, REMOTE: 0}

    for typ, _handle, obj_type, obj1, obj2 in actions:
        effects = ACTION_EFFECTS.get(typ)
        if effects is None:
            LOG.warning("Not showing unknown action type %s", typ)
            continue
        obj, db = (obj1, db1) if obj1 is not None else (obj2, db2)
        row = ObjectRow(
            type_label=object_type_label(obj_type),
            name=describe_object(obj, obj_type, db),
            gramps_id=object_id(obj, obj_type) if obj is not None else "",
        )
        for where, verb in effects:
            buckets[(where, verb)].append(row)
            if verb == VERB_DELETE:
                deletions[where] += 1

    destinations = []
    for where in (LOCAL, REMOTE):
        groups = tuple(
            ActionGroup(verb, tuple(sorted(buckets[(where, verb)], key=_row_key)))
            for verb in VERB_ORDER
            if buckets.get((where, verb))
        )
        if groups:
            destinations.append(Destination(where, groups))

    return ReviewModel(
        destinations=tuple(destinations),
        local_deletions=deletions[LOCAL],
        remote_deletions=deletions[REMOTE],
    )


# ------------------------------------------------------------
#
# Wording
#
# ------------------------------------------------------------
def destination_label(where: str, count: int) -> str:
    """Return the heading for one destination.

    Phrased as what will happen rather than as where a difference was found,
    since that is the question the review answers.
    """
    if where == LOCAL:
        return (
            ngettext(
                "Will change on this computer (%s object)",
                "Will change on this computer (%s objects)",
                count,
            )
            % count
        )
    return (
        ngettext(
            "Will change on the server (%s object)",
            "Will change on the server (%s objects)",
            count,
        )
        % count
    )


def verb_label(verb: str, count: int) -> str:
    """Return the heading for one group of objects within a destination."""
    labels = {
        VERB_ADD: ngettext("Add %s object", "Add %s objects", count),
        VERB_UPDATE: ngettext("Update %s object", "Update %s objects", count),
        VERB_MERGE: ngettext("Merge %s object", "Merge %s objects", count),
        VERB_DELETE: ngettext("Delete %s object", "Delete %s objects", count),
    }
    return labels.get(verb, "%s") % count


def deletion_warning(model: ReviewModel) -> str:
    """Return the warning shown above a run that removes data, if it does.

    Derived from the actions rather than from the selected mode: a plain
    bidirectional sync propagates deletions too, and the user deserves the same
    warning when it does.

    :param model: The review model for the selected mode.
    :returns: The warning, or ``""`` when nothing will be deleted.
    """
    parts = []
    if model.local_deletions:
        parts.append(
            ngettext(
                "%s object will be deleted on this computer.",
                "%s objects will be deleted on this computer.",
                model.local_deletions,
            )
            % model.local_deletions
        )
    if model.remote_deletions:
        parts.append(
            ngettext(
                "%s object will be deleted on the server.",
                "%s objects will be deleted on the server.",
                model.remote_deletions,
            )
            % model.remote_deletions
        )
    return " ".join(parts)


def media_label(n_download: int, n_upload: int) -> str:
    """Return the label for the media transfer checkbox."""
    total = n_download + n_upload
    counts = _("%(down)s to download, %(up)s to upload") % {
        "down": n_download,
        "up": n_upload,
    }
    return (
        ngettext(
            "Also transfer %(total)s media file (%(counts)s)",
            "Also transfer %(total)s media files (%(counts)s)",
            total,
        )
        % {"total": total, "counts": counts}
    )


def missing_both_notice(count: int) -> str:
    """Return the note about files that exist on neither side.

    Called out before the transfer rather than after it: these used to be
    attempted in both directions and reported as two failures each.
    """
    return (
        ngettext(
            "%s media file is missing on both sides and cannot be transferred.",
            "%s media files are missing on both sides and cannot be transferred.",
            count,
        )
        % count
    )


def outcome_summary(session: SyncSession) -> str:
    """Describe what a run actually did, to both trees and to the media files.

    Composed for a failed run as well as a successful one, so the caller can
    show it alongside an error.

    :param session: The finished session.
    :returns: One or more sentences describing the outcome.
    """
    parts = []
    applied = len(session.actions)
    # The trees are reported on first and unconditionally. Leaving this to a
    # fallback meant the commonest outcome of all -- nothing to do -- was
    # described entirely by the media sentence below, which is the complaint
    # that started this: a run that touched no file said "Media files are in
    # sync." and nothing whatever about the trees.
    if applied:
        parts.append(
            ngettext("Applied %s change.", "Applied %s changes.", applied) % applied
        )
    elif session.error is None:
        parts.append(_("Both trees are already in sync."))
    transfer = transfer_summary(session)
    if transfer:
        parts.append(transfer)
    elif not session.missing_both and session.error is None:
        parts.append(_("Media files are in sync."))
    if session.missing_both:
        parts.append(missing_both_notice(len(session.missing_both)))
    return " ".join(parts)


def transfer_summary(session: SyncSession) -> str:
    """Summarize how many media files moved, and how many failed.

    :param session: The session whose transfers to report.
    :returns: The summary, or ``""`` if nothing was transferred.
    """
    # Spelled out per call site rather than looked up from a table: xgettext
    # extracts literals, and a table would leave these out of the catalogue.
    parts = []
    ok, nok = _tally(session.downloaded)
    if ok:
        parts.append(
            ngettext(
                "Successfully downloaded %s media file.",
                "Successfully downloaded %s media files.",
                ok,
            )
            % ok
        )
    if nok:
        parts.append(
            ngettext(
                "Encountered %s error during download.",
                "Encountered %s errors during download.",
                nok,
            )
            % nok
        )
    ok, nok = _tally(session.uploaded)
    if ok:
        parts.append(
            ngettext(
                "Successfully uploaded %s media file.",
                "Successfully uploaded %s media files.",
                ok,
            )
            % ok
        )
    if nok:
        parts.append(
            ngettext(
                "Encountered %s error during upload.",
                "Encountered %s errors during upload.",
                nok,
            )
            % nok
        )
    return " ".join(parts)


def _tally(outcomes: dict[str, bool]) -> tuple[int, int]:
    """Return how many transfers succeeded and how many did not."""
    ok = sum(1 for succeeded in outcomes.values() if succeeded)
    return ok, len(outcomes) - ok


def context_lines(
    url: str, username: str, tree_name: str = "", last_synced: str = ""
) -> tuple[str, str]:
    """Return the two lines naming what is being synced, and how current it is.

    The remote tree's own name is the heading once the server has reported it.
    It carries more than the address does where the address cannot distinguish
    anything: a hosted deployment serves many trees from one URL, and only the
    account differs.

    :param url: The server being synced with.
    :param username: The account on it.
    :param tree_name: What the server calls its tree, once known.
    :param last_synced: The already-formatted last-sync phrase.
    :returns: The heading and the line below it.
    """
    if not url or not username:
        return _("No server configured"), ""
    where = _("%(user)s on %(server)s") % {"user": username, "server": url}
    if not tree_name:
        return where, last_synced
    if not last_synced:
        return tree_name, where
    return tree_name, _("%(where)s — %(synced)s") % {
        "where": where,
        "synced": last_synced,
    }


def format_last_synced(timestamp: float, now: float | None = None) -> str:
    """Describe when a server was last synced with.

    :param timestamp: The stored baseline, or ``0`` if there is none.
    :param now: The current time; the wall clock if omitted.
    :returns: A phrase for the context strip.
    """
    if not timestamp:
        return _("Never synced")
    now = time.time() if now is None else now
    minutes = int(max(now - timestamp, 0) // 60)
    if minutes < 1:
        return _("Last synced just now")
    if minutes < 60:
        return (
            ngettext("Last synced %s minute ago", "Last synced %s minutes ago", minutes)
            % minutes
        )
    hours = minutes // 60
    if hours < 24:
        return (
            ngettext("Last synced %s hour ago", "Last synced %s hours ago", hours)
            % hours
        )
    days = hours // 24
    if days < 30:
        return ngettext("Last synced %s day ago", "Last synced %s days ago", days) % days
    return _("Last synced on %s") % time.strftime("%x", time.localtime(timestamp))
