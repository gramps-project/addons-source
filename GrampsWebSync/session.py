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
and observe it through a :class:`SessionListener`. A failed run can be resumed
with :meth:`~SyncSession.retry`.

Collaborators are supplied as ports: :class:`Backend`,
:class:`CredentialStore`, :class:`MediaStore`, :class:`TaskRunner` and
:class:`Clock`. Failures are recorded as a :class:`SyncError` carrying an
:class:`ErrorKind`; callers are responsible for localizing them.

Each stage is split into the part that touches a database and the part that
talks to the network, because only the latter may leave the main loop -- see
:class:`adapters.IoRunner`. :data:`Step` names the pieces so that a retry can
resume at the one that failed rather than redoing the work before it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Protocol

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
from webapihandler import ServerTaskFailed, transaction_to_json

LOG = logging.getLogger("grampswebsync")

#: Transaction description recorded in both databases' undo history.
TXN_MSG = "Apply Gramps Web Sync changes"

#: Server permission required to run a sync at all.
REQUIRED_PERMISSION = "ViewPrivate"

#: A media transfer, resolved to a local path before it leaves the main loop.
Transfers = list[tuple[str, str, str]]

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


class Step(Enum):
    """The resumable pieces of a run.

    A stage that both touches a database and talks to the network is two of
    these, so that a retry after, say, a dropped connection while pushing does
    not re-apply the local half that already succeeded.
    """

    FETCH = auto()  # download the remote XML (network)
    DIFF = auto()  # import it and compare (database)
    APPLY_LOCAL = auto()  # write the local half (database)
    PUSH_REMOTE = auto()  # send the remote half (network)
    SCAN_MEDIA = auto()  # ask which files the server lacks (network)
    TRANSFER = auto()  # move media files (network)


class ErrorKind(Enum):
    """Classification of a failure, independent of its localized wording."""

    AUTH_FAILED = auto()  # HTTP 401
    FORBIDDEN = auto()  # HTTP 403
    NOT_FOUND = auto()  # HTTP 404
    RATE_LIMITED = auto()  # HTTP 429
    TREE_DISABLED = auto()  # HTTP 503
    CONFLICT = auto()  # HTTP 409
    SERVER_ERROR = auto()
    SERVER_TASK_FAILED = auto()
    CONNECTION_FAILED = auto()
    INVALID_RESPONSE = auto()
    INSUFFICIENT_PERMISSIONS = auto()
    XML_IMPORT_FAILED = auto()
    APPLY_FAILED = auto()
    STALE_LOCAL_DATA = auto()
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


class StaleLocalData(Exception):
    """The local tree changed between the comparison and the commit."""


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


def classify_http_error(exc: Any, *, login: bool) -> SyncError:
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
    """Persistence for server credentials and per-server sync baselines."""

    def get_url(self) -> str: ...

    def get_username(self) -> str: ...

    def get_password(self) -> str | None: ...

    def get_timestamp(self, url: str, username: str) -> float: ...

    def set_timestamp(self, url: str, username: str, timestamp: float) -> None: ...

    def save_credentials(
        self, url: str, username: str, password: str, remember_password: bool = True
    ) -> None: ...


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

    def post(self, func: Callable[[], None]) -> None: ...


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


#: Which state a retry of each step returns to while it runs.
STATE_FOR_STEP: dict[Step, State] = {
    Step.FETCH: State.COMPARING,
    Step.DIFF: State.COMPARING,
    Step.APPLY_LOCAL: State.APPLYING,
    Step.PUSH_REMOTE: State.APPLYING,
    Step.SCAN_MEDIA: State.APPLYING,  # overridden by _scan_resume_state
    Step.TRANSFER: State.TRANSFERRING,
}


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
        io_runner: TaskRunner | None = None,
    ) -> None:
        """Initialize the session.

        :param db: The local (currently open) Gramps database.
        :param user: A :class:`gramps.gen.user.User` for import/diff progress.
        :param backend_factory: Builds a :class:`Backend` from url, username
            and password.
        :param credentials: Where credentials and sync baselines live.
        :param media: Access to local media files.
        :param runner: Executes steps that touch a database, on the main loop.
        :param clock: Supplies the time recorded as the last successful sync.
        :param listener: Optional observer of state and progress.
        :param io_runner: Executes network steps. Defaults to ``runner``, which
            keeps everything on one thread -- useful in tests.
        """
        self.db1 = db
        self.db2 = None
        self._user = user
        self._backend_factory = backend_factory
        self.credentials = credentials
        self.media = media
        self.runner = runner
        self.io_runner = io_runner if io_runner is not None else runner
        self.clock = clock
        self.listener = listener

        self.state: State = State.INTRO
        self.error: SyncError | None = None
        #: Set when login fails. Recoverable, unlike :attr:`error`.
        self.login_error: SyncError | None = None
        #: Which step failed, so :meth:`retry` can resume at the right place.
        self.failed_in: Step | None = None

        self.url: str = ""
        self.username: str = ""
        self.password: str = ""
        self.remember_password: bool = True

        self.backend: Backend | None = None
        self.sync: WebApiSyncDiffHandler | None = None
        self.changes: Actions = []
        self.actions: Actions = []
        self.sync_mode: int = MODE_BIDIRECTIONAL

        self.missing_local: list[tuple[str, str]] = []
        self.missing_remote: list[tuple[str, str]] = []
        #: Media absent on both sides. Neither transfer can supply these, so
        #: they are reported up front rather than as two failures each.
        self.missing_both: list[tuple[str, str]] = []
        self.downloaded: dict[str, bool] = {}
        self.uploaded: dict[str, bool] = {}

        #: Held between the two halves of the apply stage, because a retry
        #: after a failed push must not re-run the local commit. Everything
        #: else a step hands to its successor travels as an argument.
        self._payload: list[dict[str, Any]] | None = None
        #: Where a media scan was scheduled from, so a retry resumes there.
        self._scan_resume_state: State = State.COMPARING
        self._closing = False

    # --------------------------------------------------------
    # Observable state
    # --------------------------------------------------------
    @property
    def has_missing_files(self) -> bool:
        """Whether any media file can actually be transferred either way."""
        return bool(self.missing_local or self.missing_remote)

    @property
    def has_local_actions(self) -> bool:
        """Whether the pending actions touch the local database."""
        return has_local_actions(self.actions)

    @property
    def has_remote_actions(self) -> bool:
        """Whether the pending actions touch the remote database."""
        return has_remote_actions(self.actions)

    @property
    def can_retry(self) -> bool:
        """Whether :meth:`retry` has a step to resume."""
        return self.state is State.FAILED and self.failed_in is not None

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

    def _fail(self, error: SyncError, step: Step | None = None) -> None:
        """Record a terminal failure and move to :attr:`State.FAILED`.

        The remote database is deliberately kept open: a retry that had to
        re-download and re-diff it would throw away the most expensive part of
        the run for what is usually a transient network problem.
        """
        LOG.warning("Sync failed: %s (%s)", error.kind.name, error.detail)
        self.error = error
        self.failed_in = step
        self._goto(State.FAILED)

    def _progress(self, kind: str, fraction: float) -> None:
        """Forward a progress update to the listener, if any."""
        if self.listener is not None:
            self.listener.on_progress(kind, fraction)

    def _status(self, stage: str) -> None:
        """Forward a status update to the listener, if any."""
        if self.listener is not None:
            self.listener.on_status(stage)

    def _progress_from_worker(self, kind: str, fraction: float) -> None:
        """Report progress raised inside a network step.

        Marshalled onto the main loop, since the listener draws widgets and the
        step is running on a worker thread.
        """
        self.io_runner.post(lambda: self._progress(kind, fraction))

    def _status_from_worker(self, stage: str) -> None:
        """Report a status update raised inside a network step."""
        self.io_runner.post(lambda: self._status(stage))

    def _classify(self, exc: BaseException, *, login: bool = False) -> SyncError:
        """Turn an exception raised by a port into a :class:`SyncError`."""
        # Imported here so the module stays importable without urllib present.
        from urllib.error import HTTPError, URLError

        if isinstance(exc, XmlImportFailed):
            return SyncError(ErrorKind.XML_IMPORT_FAILED)
        if isinstance(exc, StaleLocalData):
            return SyncError(ErrorKind.STALE_LOCAL_DATA)
        if isinstance(exc, ServerTaskFailed):
            return SyncError(ErrorKind.SERVER_TASK_FAILED, str(exc))
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

    def _run(self, step: Step, func, on_success) -> None:
        """Schedule ``step`` on the runner that is allowed to execute it.

        Network steps go to a worker thread; database steps stay on the main
        loop, because a Gramps sqlite connection belongs to the thread that
        created it.
        """
        runner = (
            self.io_runner
            if step
            in (Step.FETCH, Step.PUSH_REMOTE, Step.SCAN_MEDIA, Step.TRANSFER)
            else self.runner
        )
        runner.run(func, on_success, lambda exc: self._on_step_error(exc, step))

    # --------------------------------------------------------
    # Intents
    # --------------------------------------------------------
    def begin(self) -> None:
        """Leave the introduction page."""
        self._advance()

    def submit_credentials(
        self,
        url: str,
        username: str,
        password: str,
        remember_password: bool = True,
    ) -> None:
        """Connect, authenticate, then download and diff the remote tree.

        On an authentication or permission problem the session stays on
        :attr:`State.LOGIN` with :attr:`login_error` set. Credentials are stored
        only once the server has accepted them, so a typo never reaches the
        keyring.

        :param url: Server URL, already sanitized by the caller.
        :param username: Login name.
        :param password: Password.
        :param remember_password: Whether the password may be stored.
        """
        self.login_error = None
        self.url = url
        self.username = username
        self.password = password
        self.remember_password = remember_password

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

        self.credentials.save_credentials(
            url, username, password, remember_password
        )
        self._start_compare()

    def confirm_changes(self, sync_mode: int) -> None:
        """Accept the reviewed changes and apply them.

        :param sync_mode: One of the ``MODE_*`` constants from :mod:`const`.
        """
        self.sync_mode = sync_mode
        self._goto(State.APPLYING)
        self._run(Step.APPLY_LOCAL, self._apply_local, self._on_local_applied)

    def confirm_files(self) -> None:
        """Accept the media file transfer and carry it out.

        Goes straight to :attr:`State.DONE` if nothing is missing.
        """
        if not self.has_missing_files:
            self._advance()
            return
        self._goto(State.TRANSFERRING)
        self._start_transfer()

    def retry(self) -> None:
        """Resume a failed run at the step that failed.

        Everything before that step is left alone: the remote tree is still
        downloaded and diffed, and a local commit that already succeeded is not
        repeated.
        """
        step = self.failed_in
        if step is None:
            return
        LOG.info("Retrying sync from %s.", step.name)
        self.error = None
        self.failed_in = None
        self._goto(
            self._scan_resume_state
            if step is Step.SCAN_MEDIA
            else STATE_FOR_STEP[step]
        )
        if step is Step.FETCH:
            self._run(Step.FETCH, self._fetch_xml, self._on_fetched)
        elif step is Step.DIFF:
            self._start_compare()
        elif step is Step.APPLY_LOCAL:
            self._run(Step.APPLY_LOCAL, self._apply_local, self._on_local_applied)
        elif step is Step.PUSH_REMOTE:
            self._run(Step.PUSH_REMOTE, self._push_remote, self._on_applied)
        elif step is Step.SCAN_MEDIA:
            self._start_media_scan()
        elif step is Step.TRANSFER:
            self._start_transfer()

    def cancel(self) -> None:
        """Abandon the run and release the in-memory remote database."""
        self._closing = True
        self._release_remote()

    def _release_remote(self) -> None:
        """Close the downloaded remote database, if one is open."""
        if self.db2 is not None:
            self.db2.close()
            self.db2 = None
        self.sync = None  # holds references to both databases

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------
    def _start_compare(self) -> None:
        """Enter the comparison stage and fetch the remote tree."""
        self._goto(State.COMPARING)
        self._run(Step.FETCH, self._fetch_xml, self._on_fetched)

    def _fetch_xml(self) -> Path | None:
        """Download the remote tree as Gramps XML. Network only.

        :returns: Where the export was written, for the next step.
        """
        if self._closing:
            return None
        assert self.backend is not None
        LOG.info("Downloading Gramps XML file.")
        self._status_from_worker(STATUS_FETCHING)
        path = self.backend.download_xml()
        LOG.debug("Downloaded XML to %s", path)
        return path

    def _on_fetched(self, path: Path | None) -> None:
        """Import and diff, back on the main loop."""
        if self._closing or path is None:
            return
        self._run(
            Step.DIFF, lambda: self._import_and_diff(path), self._on_compared
        )

    def _import_and_diff(self, path: Path) -> None:
        """Import the downloaded XML and diff it against the local tree.

        Runs on the main loop: ``import_as_dict`` builds an in-memory sqlite
        database on the calling thread, and ``diff_dbs`` reads the local one,
        which belongs to the main thread.

        :param path: The export downloaded by :meth:`_fetch_xml`. It is
            consumed here, which is why retrying this step downloads again.
        """
        if self._closing:
            return
        try:
            db2 = import_as_dict(str(path), self._user)
        finally:
            path.unlink(missing_ok=True)
        if db2 is None:
            raise XmlImportFailed()
        self._release_remote()
        self.db2 = db2

        LOG.info("Comparing local and remote data.")
        self._status(STATUS_COMPARING)
        last_synced = self.credentials.get_timestamp(self.url, self.username) or None
        self.sync = WebApiSyncDiffHandler(
            self.db1, self.db2, user=self._user, last_synced=last_synced
        )
        self.changes = self.sync.get_changes()

    def _on_compared(self, _result: Any) -> None:
        """Move on once the diff is available."""
        if self._closing:
            return
        if self.changes:
            self._advance()
            return
        LOG.info("Databases are in sync.")
        self.credentials.set_timestamp(self.url, self.username, self.clock.now())
        self._start_media_scan()

    # --------------------------------------------------------
    # Applying
    # --------------------------------------------------------
    def _apply_local(self) -> None:
        """Write the local half of the sync and build the remote payload.

        Runs on the main loop: both halves are prepared inside Gramps
        transactions against databases owned by this thread.
        """
        if self._closing:
            return
        assert self.backend is not None and self.sync is not None
        self.actions = changes_to_actions(self.changes, self.sync_mode)
        self._payload = []
        if not self.actions:
            return

        self._assert_local_unchanged()

        LOG.info("Committing %s actions.", len(self.actions))
        try:
            with DbTxn(TXN_MSG, self.sync.db1) as trans1:
                with DbTxn(TXN_MSG, self.sync.db2) as trans2:
                    self.sync.commit_actions(self.actions, trans1, trans2)
                    lang = self.backend.get_lang()
                    self._payload = transaction_to_json(trans2, lang)
        except StaleLocalData:
            raise
        except Exception as exc:
            raise ApplyFailed(str(exc)) from exc

        if self.has_local_actions:
            self._status(STATUS_LOCAL_APPLIED)

    def _assert_local_unchanged(self) -> None:
        """Verify the local tree still matches what the comparison saw.

        The comparison captured object snapshots, and the user may have gone on
        editing the tree while reviewing them -- the tool does not block the
        main window. Committing those snapshots would silently overwrite any
        edit made in between, so the run stops instead and re-compares.

        :raises StaleLocalData: If any affected object changed or appeared.
        """
        for _typ, handle, obj_type, obj1, _obj2 in self.actions:
            method = self.db1.method("get_%s_from_handle", obj_type)
            if method is None:
                continue
            try:
                current = method(handle)
            except HandleError:
                current = None
            if obj1 is None:
                # Absent locally when compared; anything here now is new.
                if current is not None:
                    raise StaleLocalData(f"{obj_type} {handle} was added locally")
            elif current is None:
                raise StaleLocalData(f"{obj_type} {handle} was deleted locally")
            elif current.change != obj1.change:
                raise StaleLocalData(f"{obj_type} {handle} was modified locally")

    def _on_local_applied(self, _result: Any) -> None:
        """Push the remote half, off the main loop."""
        if self._closing:
            return
        self._run(Step.PUSH_REMOTE, self._push_remote, self._on_applied)

    def _push_remote(self) -> None:
        """Send the remote half of the sync to the server. Network only."""
        if self._closing:
            return
        assert self.backend is not None
        if not self._payload:
            return
        # Always force: the server compares against the XML-round-tripped
        # object, which differs from the live one through serialization
        # artifacts alone, yielding spurious 409s.
        self.backend.commit(
            self._payload,
            True,
            lambda fraction: self._progress_from_worker("api", fraction),
        )
        self._payload = []

    def _on_applied(self, _result: Any) -> None:
        """Record the sync time and collect media state."""
        if self._closing:
            return
        self.credentials.set_timestamp(self.url, self.username, self.clock.now())
        self._start_media_scan()

    # --------------------------------------------------------
    # Media
    # --------------------------------------------------------
    def _start_media_scan(self) -> None:
        """Ask the server which files it lacks, off the main loop.

        The state to come back to is captured here, because a failure moves the
        session to ``FAILED`` and a retry has to resume from where the scan was
        scheduled rather than from wherever it ended up.
        """
        self._scan_resume_state = self.state
        self._run(Step.SCAN_MEDIA, self._fetch_remote_missing, self._on_media_scanned)

    def _fetch_remote_missing(self) -> list[dict[str, Any]]:
        """Return the server's list of media objects with no file. Network only."""
        if self._closing:
            return []
        assert self.backend is not None
        return self.backend.get_missing_files() or []

    def _on_media_scanned(self, remote: list[dict[str, Any]] | None) -> None:
        """Combine the server's answer with a local scan, back on the main loop."""
        if self._closing:
            return
        self._scan_media(remote or [])
        self._advance()

    def _scan_media(self, remote: list[dict[str, Any]]) -> None:
        """Work out which media files are missing, and on which side.

        A file absent from both sides cannot be transferred in either
        direction, so it is separated out here rather than being attempted
        twice and reported as two failures.

        :param remote: The server's missing-file list, already fetched.
        """
        local_missing = {
            media.handle: media.gramps_id
            for media in self.db1.iter_media()
            if not self.media.exists(media)
        }
        remote_missing = {
            media["handle"]: media["gramps_id"] for media in remote
        }
        both = set(local_missing) & set(remote_missing)

        self.missing_both = [(local_missing[h], h) for h in both]
        self.missing_local = [
            (gid, h) for h, gid in local_missing.items() if h not in both
        ]
        self.missing_remote = [
            (gid, h) for h, gid in remote_missing.items() if h not in both
        ]
        if self.missing_both:
            LOG.warning(
                "%s media file(s) are missing on both sides.", len(self.missing_both)
            )

    def _resolve_transfers(self) -> tuple[Transfers, Transfers]:
        """Turn the missing-file lists into paths, on the main loop.

        The transfer itself runs on a worker thread and must not touch the
        local database, so every handle is resolved to a path first. Files a
        previous attempt already moved are left out, so a retry after a dropped
        connection resumes rather than starting over.

        :returns: The downloads and uploads still to do.
        """
        downloads: Transfers = []
        uploads: Transfers = []
        for gramps_id, handle in self.missing_local:
            path = self._path_for(handle)
            if path is None:
                self.downloaded[gramps_id] = False
            elif not self.downloaded.get(gramps_id):
                downloads.append((gramps_id, handle, path))
        for gramps_id, handle in self.missing_remote:
            path = self._path_for(handle)
            if path is None:
                self.uploaded[gramps_id] = False
            elif not self.uploaded.get(gramps_id):
                uploads.append((gramps_id, handle, path))
        return downloads, uploads

    def _start_transfer(self) -> None:
        """Resolve paths on the main loop, then transfer off it."""
        downloads, uploads = self._resolve_transfers()
        self._run(
            Step.TRANSFER,
            lambda: self._transfer(downloads, uploads),
            self._on_transferred,
        )

    def _path_for(self, handle: str) -> str | None:
        """Return the local path of a media object, or ``None`` if unusable."""
        try:
            obj = self.db1.get_media_from_handle(handle)
        except HandleError:
            LOG.warning("Cannot access media object %s", handle)
            return None
        return self.media.full_path(obj)

    def _transfer(self, downloads: Transfers, uploads: Transfers) -> None:
        """Download then upload media files. Network only.

        Both loops check for cancellation between files, so closing the window
        stops the transfer rather than waiting for it to finish.

        :param downloads: Files to fetch, as ``(gramps_id, handle, path)``.
        :param uploads: Files to send, in the same form.
        """
        if self._closing:
            return
        assert self.backend is not None
        for index, (gramps_id, handle, path) in enumerate(downloads, start=1):
            if self._closing:
                return
            LOG.debug("Downloading file %s", gramps_id)
            self.downloaded[gramps_id] = self._download_one(handle, path)
            self._progress_from_worker("download", index / len(downloads))
        for index, (gramps_id, handle, path) in enumerate(uploads, start=1):
            if self._closing:
                return
            LOG.debug("Uploading file %s", gramps_id)
            self.uploaded[gramps_id] = self._upload_one(handle, path)
            self._progress_from_worker("upload", index / len(uploads))

    def _on_transferred(self, _result: Any) -> None:
        """Finish the run."""
        if self._closing:
            return
        self._advance()

    def _download_one(self, handle: str, path: str) -> bool:
        """Download one media file, reporting failure rather than raising."""
        assert self.backend is not None
        try:
            return self.backend.download_media_file(handle, path)
        except Exception as exc:  # noqa: BLE001 -- one bad file must not abort
            LOG.warning("Failed to download media file %s: %s", handle, exc)
            return False

    def _upload_one(self, handle: str, path: str) -> bool:
        """Upload one media file.

        :param handle: Handle of the media object to upload.
        :param path: Where its file lives locally.
        :returns: Whether the file was uploaded.
        """
        import os

        assert self.backend is not None
        if not os.path.exists(path):
            LOG.warning("Cannot upload media file %s: not on disk (%s)", handle, path)
            return False
        return self.backend.upload_media_file(handle, path)

    # --------------------------------------------------------
    # Step failure
    # --------------------------------------------------------
    def _on_step_error(self, exc: BaseException, step: Step) -> None:
        """Handle an exception escaping one of the steps."""
        if self._closing:
            return
        # Stale local data means the snapshots are worthless; a retry has to
        # compare again rather than resume where it stopped.
        resume = Step.DIFF if isinstance(exc, StaleLocalData) else step
        self._fail(self._classify(exc), resume)
