# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021-2026       David Straub
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

"""Headless sync session for the Gramps Web Sync addon.

:class:`SyncSession` runs a synchronization against a Gramps Web server,
progressing through the stages in :class:`State`. Callers drive it with
:meth:`~SyncSession.begin`, :meth:`~SyncSession.submit_credentials`,
:meth:`~SyncSession.confirm_changes` and :meth:`~SyncSession.confirm_files`,
and observe it through a :class:`SessionListener`.

Collaborators are supplied as ports: :class:`Backend`,
:class:`CredentialStore`, :class:`MediaStore`, :class:`TaskRunner` and
:class:`Clock`. Failures are recorded as a :class:`SyncError` carrying an
:class:`ErrorKind`; callers are responsible for localizing them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError

from const import MODE_BIDIRECTIONAL, Actions
from diffhandler import (
    WebApiSyncDiffHandler,
    changes_to_actions,
    has_local_actions,
    has_remote_actions,
)
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import import_as_dict
from gramps.gen.errors import HandleError
from webapihandler import transaction_to_json

LOG = logging.getLogger("grampswebsync")

#: Transaction description recorded in both databases' undo history.
TXN_MSG = "Apply Gramps Web Sync changes"

#: Server permission required to run a sync at all.
REQUIRED_PERMISSION = "ViewPrivate"

#: Stages reported through :meth:`SessionListener.on_status`.
STATUS_FETCHING = "fetching"
STATUS_COMPARING = "comparing"
STATUS_LOCAL_APPLIED = "local_applied"


# ------------------------------------------------------------
#
# States and errors
#
# ------------------------------------------------------------
class State(Enum):
    """The stages of a sync run."""

    INTRO = auto()
    LOGIN = auto()
    COMPARING = auto()
    REVIEW_CHANGES = auto()
    APPLYING = auto()
    REVIEW_FILES = auto()
    TRANSFERRING = auto()
    DONE = auto()
    FAILED = auto()


class ErrorKind(Enum):
    """Classification of a failure, independent of its localized wording."""

    AUTH_FAILED = auto()  # HTTP 401
    FORBIDDEN = auto()  # HTTP 403
    NOT_FOUND = auto()  # HTTP 404
    RATE_LIMITED = auto()  # HTTP 429
    TREE_DISABLED = auto()  # HTTP 503
    CONFLICT = auto()  # HTTP 409
    SERVER_ERROR = auto()
    CONNECTION_FAILED = auto()
    INVALID_RESPONSE = auto()
    INSUFFICIENT_PERMISSIONS = auto()
    XML_IMPORT_FAILED = auto()
    APPLY_FAILED = auto()
    UNEXPECTED = auto()


@dataclass(frozen=True)
class SyncError:
    """A failure recorded by the session.

    :param kind: The classification.
    :param detail: Untranslated detail, e.g. an HTTP status or exception text.
    """

    kind: ErrorKind
    detail: str = ""


class XmlImportFailed(Exception):
    """The downloaded Gramps XML could not be imported."""


class ApplyFailed(Exception):
    """Applying the confirmed actions to the databases raised."""


# Login and mid-sync failures read a few status codes differently.
_LOGIN_HTTP_ERRORS: dict[int, ErrorKind] = {
    401: ErrorKind.AUTH_FAILED,
    403: ErrorKind.FORBIDDEN,
    404: ErrorKind.NOT_FOUND,
    429: ErrorKind.RATE_LIMITED,
    503: ErrorKind.TREE_DISABLED,
}

_SYNC_HTTP_ERRORS: dict[int, ErrorKind] = {
    401: ErrorKind.AUTH_FAILED,
    403: ErrorKind.FORBIDDEN,
    404: ErrorKind.NOT_FOUND,
    409: ErrorKind.CONFLICT,
}


def classify_http_error(exc: HTTPError, *, login: bool) -> SyncError:
    """Classify an :class:`HTTPError` into a :class:`SyncError`.

    :param exc: The raised error.
    :param login: Whether this happened while establishing the connection.
    :returns: The corresponding :class:`SyncError`.
    """
    table = _LOGIN_HTTP_ERRORS if login else _SYNC_HTTP_ERRORS
    kind = table.get(exc.code, ErrorKind.SERVER_ERROR)
    return SyncError(kind, str(exc.code))


# ------------------------------------------------------------
#
# Ports
#
# ------------------------------------------------------------
class Backend(Protocol):
    """What the session needs from a Gramps Web server.

    Implemented by :class:`webapihandler.WebApiHandler`.
    """

    def get_permissions(self) -> set[str]: ...

    def get_lang(self) -> str | None: ...

    def download_xml(self) -> Path: ...

    def commit(
        self,
        payload: list[dict[str, Any]],
        force: bool = True,
        progress_callback: Callable | None = None,
    ) -> None: ...

    def get_missing_files(self) -> list[dict[str, Any]]: ...

    def download_media_file(self, handle: str, path: str) -> bool: ...

    def upload_media_file(self, handle: str, path: str) -> bool: ...


class CredentialStore(Protocol):
    """Persistence for server credentials and the last-sync timestamp."""

    def get_url(self) -> str: ...

    def get_username(self) -> str: ...

    def get_password(self) -> str | None: ...

    def get_timestamp(self) -> float: ...

    def set_timestamp(self, timestamp: float) -> None: ...

    def save_credentials(self, url: str, username: str, password: str) -> None: ...


class MediaStore(Protocol):
    """Access to local media files belonging to the local database."""

    def full_path(self, media: Any) -> str: ...

    def exists(self, media: Any) -> bool: ...


class TaskRunner(Protocol):
    """Runs a potentially slow callable and reports the outcome back."""

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None: ...


class Clock(Protocol):
    """Source of the current time."""

    def now(self) -> float: ...


class SessionListener(Protocol):
    """Receives session state changes, status and progress updates."""

    def on_state_changed(self, state: State) -> None: ...

    def on_progress(self, kind: str, fraction: float) -> None: ...

    def on_status(self, stage: str) -> None: ...


# ------------------------------------------------------------
#
# Transition table
#
# ------------------------------------------------------------
def next_state(state: State, session: SyncSession) -> State:
    """Return the state that follows ``state``.

    :param state: The state being left.
    :param session: The session, consulted for the branch conditions.
    :returns: The next state.
    """
    if session.error is not None:
        return State.FAILED
    if state is State.INTRO:
        return State.LOGIN
    if state is State.LOGIN:
        return State.COMPARING
    if state is State.COMPARING:
        if session.changes:
            return State.REVIEW_CHANGES
        return State.REVIEW_FILES if session.has_missing_files else State.DONE
    if state is State.REVIEW_CHANGES:
        return State.APPLYING
    if state is State.APPLYING:
        # Skipped entirely rather than shown empty: there is nothing to
        # confirm when no file is missing on either side.
        return State.REVIEW_FILES if session.has_missing_files else State.DONE
    if state is State.REVIEW_FILES:
        return State.TRANSFERRING if session.has_missing_files else State.DONE
    if state is State.TRANSFERRING:
        return State.DONE
    return state


# ------------------------------------------------------------
#
# SyncSession
#
# ------------------------------------------------------------
class SyncSession:
    """Drives one synchronization run against a Gramps Web server."""

    def __init__(
        self,
        db,
        user,
        backend_factory: Callable[[str, str, str], Backend],
        credentials: CredentialStore,
        media: MediaStore,
        runner: TaskRunner,
        clock: Clock,
        listener: SessionListener | None = None,
    ) -> None:
        """Initialize the session.

        :param db: The local (currently open) Gramps database.
        :param user: A :class:`gramps.gen.user.User` for import/diff progress.
        :param backend_factory: Builds a :class:`Backend` from url, username
            and password.
        :param credentials: Where credentials and the last-sync time live.
        :param media: Access to local media files.
        :param runner: Executes the slow steps.
        :param clock: Supplies the time recorded as the last successful sync.
        :param listener: Optional observer of state and progress.
        """
        self.db1 = db
        self.db2 = None
        self._user = user
        self._backend_factory = backend_factory
        self.credentials = credentials
        self.media = media
        self.runner = runner
        self.clock = clock
        self.listener = listener

        self.state: State = State.INTRO
        self.error: SyncError | None = None
        #: Set when login fails. Recoverable, unlike :attr:`error`.
        self.login_error: SyncError | None = None

        self.backend: Backend | None = None
        self.sync: WebApiSyncDiffHandler | None = None
        self.changes: Actions = []
        self.actions: Actions = []
        self.sync_mode: int = MODE_BIDIRECTIONAL

        self.missing_local: list[tuple[str, str]] = []
        self.missing_remote: list[tuple[str, str]] = []
        self.downloaded: dict[str, bool] = {}
        self.uploaded: dict[str, bool] = {}

        self._closing = False

    # --------------------------------------------------------
    # Observable state
    # --------------------------------------------------------
    @property
    def has_missing_files(self) -> bool:
        """Whether any media file is missing on either side."""
        return bool(self.missing_local or self.missing_remote)

    @property
    def has_local_actions(self) -> bool:
        """Whether the pending actions touch the local database."""
        return has_local_actions(self.actions)

    @property
    def has_remote_actions(self) -> bool:
        """Whether the pending actions touch the remote database."""
        return has_remote_actions(self.actions)

    # --------------------------------------------------------
    # Internals
    # --------------------------------------------------------
    def _goto(self, state: State) -> None:
        """Enter ``state`` and notify the listener."""
        LOG.debug("Sync session: %s -> %s", self.state.name, state.name)
        self.state = state
        if self.listener is not None:
            self.listener.on_state_changed(state)

    def _advance(self) -> None:
        """Move to whatever :func:`next_state` says comes next."""
        self._goto(next_state(self.state, self))

    def _fail(self, error: SyncError) -> None:
        """Record a terminal failure and move to :attr:`State.FAILED`."""
        LOG.warning("Sync failed: %s (%s)", error.kind.name, error.detail)
        self.error = error
        self._goto(State.FAILED)

    def _progress(self, kind: str, fraction: float) -> None:
        """Forward a progress update to the listener, if any."""
        if self.listener is not None:
            self.listener.on_progress(kind, fraction)

    def _status(self, stage: str) -> None:
        """Forward a status update to the listener, if any."""
        if self.listener is not None:
            self.listener.on_status(stage)

    def _classify(self, exc: BaseException, *, login: bool = False) -> SyncError:
        """Turn an exception raised by a port into a :class:`SyncError`."""
        if isinstance(exc, XmlImportFailed):
            return SyncError(ErrorKind.XML_IMPORT_FAILED)
        if isinstance(exc, ApplyFailed):
            return SyncError(ErrorKind.APPLY_FAILED, str(exc))
        if isinstance(exc, HTTPError):
            return classify_http_error(exc, login=login)
        if isinstance(exc, URLError):
            return SyncError(ErrorKind.CONNECTION_FAILED, str(exc.reason))
        if isinstance(exc, ValueError):
            kind = ErrorKind.INVALID_RESPONSE if login else ErrorKind.SERVER_ERROR
            return SyncError(kind, str(exc))
        return SyncError(ErrorKind.UNEXPECTED, str(exc))

    # --------------------------------------------------------
    # Intents
    # --------------------------------------------------------
    def begin(self) -> None:
        """Leave the introduction page."""
        self._advance()

    def submit_credentials(self, url: str, username: str, password: str) -> None:
        """Connect, authenticate, then download and diff the remote tree.

        On an authentication or permission problem the session stays on
        :attr:`State.LOGIN` with :attr:`login_error` set.

        :param url: Server URL, already sanitized by the caller.
        :param username: Login name.
        :param password: Password.
        """
        self.login_error = None
        self.credentials.save_credentials(url, username, password)

        try:
            self.backend = self._backend_factory(url, username, password)
            permissions = self.backend.get_permissions()
        except Exception as exc:  # noqa: BLE001 -- classified below
            self.backend = None
            self.login_error = self._classify(exc, login=True)
            self._goto(State.LOGIN)
            return

        if REQUIRED_PERMISSION not in permissions:
            self.login_error = SyncError(ErrorKind.INSUFFICIENT_PERMISSIONS)
            self._goto(State.LOGIN)
            return

        self._goto(State.COMPARING)
        self.runner.run(self._compare, self._on_compared, self._on_step_error)

    def confirm_changes(self, sync_mode: int) -> None:
        """Accept the reviewed changes and apply them.

        :param sync_mode: One of the ``MODE_*`` constants from :mod:`const`.
        """
        self.sync_mode = sync_mode
        self._goto(State.APPLYING)
        self.runner.run(self._apply, self._on_applied, self._on_step_error)

    def confirm_files(self) -> None:
        """Accept the media file transfer and carry it out.

        Goes straight to :attr:`State.DONE` if nothing is missing.
        """
        if not self.has_missing_files:
            self._advance()
            return
        self._goto(State.TRANSFERRING)
        self.runner.run(self._transfer, self._on_transferred, self._on_step_error)

    def cancel(self) -> None:
        """Abandon the run and release the in-memory remote database."""
        self._closing = True
        if self.db2 is not None:
            self.db2.close()
            self.db2 = None
        self.sync = None  # holds references to both databases

    # --------------------------------------------------------
    # Steps
    # --------------------------------------------------------
    def _on_step_error(self, exc: BaseException) -> None:
        """Handle an exception escaping one of the background steps."""
        self._fail(self._classify(exc))

    def _compare(self) -> None:
        """Download the remote tree and diff it against the local one."""
        if self._closing:
            return
        assert self.backend is not None
        LOG.info("Downloading Gramps XML file.")
        self._status(STATUS_FETCHING)
        path = self.backend.download_xml()
        LOG.debug("Downloaded XML to %s", path)

        db2 = import_as_dict(str(path), self._user)
        path.unlink()
        if db2 is None:
            raise XmlImportFailed()
        self.db2 = db2

        LOG.info("Comparing local and remote data.")
        self._status(STATUS_COMPARING)
        last_synced = self.credentials.get_timestamp() or None
        self.sync = WebApiSyncDiffHandler(
            self.db1, self.db2, user=self._user, last_synced=last_synced
        )
        self.changes = self.sync.get_changes()

    def _on_compared(self, _result: Any) -> None:
        """Move on once the diff is available."""
        if self._closing:
            return
        if not self.changes:
            LOG.info("Databases are in sync.")
            self.credentials.set_timestamp(self.clock.now())
            self.missing_local = self._find_missing_local()
            self.missing_remote = self._find_missing_remote()
        self._advance()

    def _apply(self) -> None:
        """Apply the confirmed actions locally, then push them to the server."""
        if self._closing:
            return
        assert self.backend is not None and self.sync is not None
        self.actions = changes_to_actions(self.changes, self.sync_mode)
        if not self.actions:
            return

        LOG.info("Committing %s actions.", len(self.actions))
        try:
            with DbTxn(TXN_MSG, self.sync.db1) as trans1:
                with DbTxn(TXN_MSG, self.sync.db2) as trans2:
                    self.sync.commit_actions(self.actions, trans1, trans2)
                    lang = self.backend.get_lang()
                    payload = transaction_to_json(trans2, lang)
        except Exception as exc:
            raise ApplyFailed(str(exc)) from exc

        if self.has_local_actions:
            self._status(STATUS_LOCAL_APPLIED)

        # Always force: the server compares against the XML-round-tripped
        # object, which differs from the live one through serialization
        # artifacts alone, yielding spurious 409s.
        self.backend.commit(
            payload, True, lambda fraction: self._progress("api", fraction)
        )

    def _on_applied(self, _result: Any) -> None:
        """Record the sync time and collect media state."""
        if self._closing:
            return
        self.credentials.set_timestamp(self.clock.now())
        self.missing_local = self._find_missing_local()
        self.missing_remote = self._find_missing_remote()
        self._advance()

    def _transfer(self) -> None:
        """Download media missing locally, then upload media missing remotely.

        Progress reporting lets the view pump the event loop, so the user can
        cancel mid-transfer; both loops check for that between files.
        """
        if self._closing:
            return
        assert self.backend is not None
        for gramps_id, handle in self.missing_local:
            if self._closing:
                return
            LOG.debug("Downloading file %s", gramps_id)
            self.downloaded[gramps_id] = self._download_one(handle)
            self._progress("download", len(self.downloaded) / len(self.missing_local))
        for gramps_id, handle in self.missing_remote:
            if self._closing:
                return
            LOG.debug("Uploading file %s", gramps_id)
            self.uploaded[gramps_id] = self._upload_one(handle)
            self._progress("upload", len(self.uploaded) / len(self.missing_remote))

    def _on_transferred(self, _result: Any) -> None:
        """Finish the run."""
        if self._closing:
            return
        self._advance()

    # --------------------------------------------------------
    # Media helpers
    # --------------------------------------------------------
    def _find_missing_local(self) -> list[tuple[str, str]]:
        """Return ``(gramps_id, handle)`` for media whose file is absent locally."""
        return [
            (media.gramps_id, media.handle)
            for media in self.db1.iter_media()
            if not self.media.exists(media)
        ]

    def _find_missing_remote(self) -> list[tuple[str, str]]:
        """Return ``(gramps_id, handle)`` for media whose file is absent remotely."""
        assert self.backend is not None
        return [
            (media["gramps_id"], media["handle"])
            for media in self.backend.get_missing_files() or []
        ]

    def _download_one(self, handle: str) -> bool:
        """Download one media file, reporting failure rather than raising."""
        assert self.backend is not None
        try:
            obj = self.db1.get_media_from_handle(handle)
        except HandleError:
            LOG.warning("Cannot access media object %s", handle)
            return False
        try:
            return self.backend.download_media_file(handle, self.media.full_path(obj))
        except Exception as exc:  # noqa: BLE001 -- one bad file must not abort
            LOG.warning("Failed to download media file %s: %s", obj.gramps_id, exc)
            return False

    def _upload_one(self, handle: str) -> bool:
        """Upload one media file.

        A file absent on both sides appears in both missing lists: the
        download cannot supply it and there is nothing local to send, so it is
        recorded as a failure instead of raising.

        :param handle: Handle of the media object to upload.
        :returns: Whether the file was uploaded.
        """
        assert self.backend is not None
        try:
            obj = self.db1.get_media_from_handle(handle)
        except HandleError:
            LOG.warning("Cannot access media object %s", handle)
            return False
        if not self.media.exists(obj):
            LOG.warning(
                "Cannot upload media file %s: missing locally as well (%s)",
                obj.gramps_id,
                self.media.full_path(obj),
            )
            return False
        return self.backend.upload_media_file(handle, self.media.full_path(obj))


