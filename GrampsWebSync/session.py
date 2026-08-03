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
:meth:`~SyncSession.submit_credentials` and :meth:`~SyncSession.confirm`, and
observe it through a :class:`SessionListener`. A failed run can be resumed with
:meth:`~SyncSession.retry`.

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

from const import API_MAJOR, MIN_API_VERSION, MODE_BIDIRECTIONAL, Actions
from diffhandler import (
    WebApiSyncDiffHandler,
    changes_to_actions,
    has_local_actions,
    has_remote_actions,
)
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import import_as_dict
from gramps.gen.errors import HandleError
from webapihandler import ServerTaskFailed, parse_version, transaction_to_json

LOG = logging.getLogger("grampswebsync")

#: Transaction description recorded in both databases' undo history.
TXN_MSG = "Apply Gramps Web Sync changes"

#: Server permission required to run a sync at all.
REQUIRED_PERMISSION = "ViewPrivate"

#: A media transfer, resolved to a local path before it leaves the main loop.
Transfers = list[tuple[str, str, str]]

#: Stages reported through :meth:`SessionListener.on_status`.
STATUS_CONNECTING = "connecting"
STATUS_FETCHING = "fetching"
STATUS_COMPARING = "comparing"
STATUS_SCANNING_MEDIA = "scanning_media"
STATUS_LOCAL_APPLIED = "local_applied"
STATUS_PUSHING = "pushing"


# ------------------------------------------------------------
#
# States and errors
#
# ------------------------------------------------------------
class State(Enum):
    """The stages of a sync run, in the order they occur."""

    CONNECT = auto()  # waiting for the user to supply credentials
    CONNECTING = auto()  # authenticating against the server
    COMPARING = auto()  # downloading, diffing and checking media
    REVIEW = auto()  # waiting for the user to confirm what will happen
    APPLYING = auto()  # writing both databases
    TRANSFERRING = auto()  # moving media files
    DONE = auto()
    FAILED = auto()


#: The stages the view renders as a progress list, in order. Every other state
#: waits for the user or reports an outcome.
WORKING_STATES = (
    State.CONNECTING,
    State.COMPARING,
    State.APPLYING,
    State.TRANSFERRING,
)


class Step(Enum):
    """The resumable pieces of a run.

    A stage that both touches a database and talks to the network is two of
    these, so that a retry after, say, a dropped connection while pushing does
    not re-apply the local half that already succeeded.

    Connecting is absent: it fails back to :attr:`State.CONNECT` for the user to
    correct rather than ending the run, so there is nothing to resume.
    """

    FETCH = auto()  # download the remote XML (network)
    DIFF = auto()  # import it and compare (database)
    SCAN_MEDIA = auto()  # ask which files the server lacks (network)
    APPLY_LOCAL = auto()  # write the local half (database)
    PUSH_REMOTE = auto()  # send the remote half (network)
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
    SERVER_TOO_OLD = auto()
    SERVER_TOO_NEW = auto()
    SERVER_NO_TASK_QUEUE = auto()
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


def api_version_problem(version: str | None) -> ErrorKind | None:
    """Classify a server's API version against what this addon speaks.

    The two ends need opposite advice -- update the server, or move to a newer
    Gramps -- so they are separate kinds rather than one verdict.

    A version that is absent or unreadable counts as too old: the field
    predates neither bound, and a server that cannot report one at all is far
    likelier to be ancient than to be from the future.

    :param version: The server's ``gramps_webapi`` version, as reported.
    :returns: The problem, or ``None`` if the version is usable.
    """
    if not version:
        return ErrorKind.SERVER_TOO_OLD
    try:
        major, _minor = parse_version(version)
    except ValueError:
        LOG.warning("Server reported an unreadable API version: %s", version)
        return ErrorKind.SERVER_TOO_OLD
    if major > API_MAJOR:
        return ErrorKind.SERVER_TOO_NEW
    # An older major is below the minimum too, so one comparison covers both
    # an out-of-date major and an out-of-date minor within the current one.
    if (major, _minor) < MIN_API_VERSION:
        return ErrorKind.SERVER_TOO_OLD
    return None


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

    def get_api_version(self) -> str | None: ...

    def has_task_queue(self) -> bool: ...

    def get_tree_name(self) -> str: ...

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


@dataclass(frozen=True)
class Connection:
    """What one connect attempt learned about a server.

    Carried as one value because the whole attempt happens on a worker thread
    and only its result crosses back to the main loop.

    :param backend: The connected handler.
    :param api_version: The Gramps Web API version it reports, if any.
    :param task_queue: Whether it runs transactions in the background.
    :param tree_name: What the server calls the tree it serves.
    :param permissions: What the authenticated account may do.
    """

    backend: Backend
    api_version: str | None
    task_queue: bool
    tree_name: str
    permissions: set[str]


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
    if state is State.CONNECT:
        return State.CONNECTING
    if state is State.CONNECTING:
        return State.COMPARING
    if state is State.COMPARING:
        # Nothing to decide means nothing to show: a run that finds the trees
        # identical and no file to move reports that and stops.
        return State.REVIEW if session.has_review_content else State.DONE
    if state is State.REVIEW:
        return State.APPLYING
    if state is State.APPLYING:
        return State.TRANSFERRING if session.will_transfer else State.DONE
    if state is State.TRANSFERRING:
        return State.DONE
    return state


#: Which state a retry of each step returns to while it runs.
STATE_FOR_STEP: dict[Step, State] = {
    Step.FETCH: State.COMPARING,
    Step.DIFF: State.COMPARING,
    Step.SCAN_MEDIA: State.COMPARING,  # overridden by _scan_origin
    Step.APPLY_LOCAL: State.APPLYING,
    Step.PUSH_REMOTE: State.APPLYING,
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

        self.state: State = State.CONNECT
        self.error: SyncError | None = None
        #: Set when connecting fails. Recoverable, unlike :attr:`error`.
        self.login_error: SyncError | None = None
        #: Which step failed, so :meth:`retry` can resume at the right place.
        self.failed_in: Step | None = None

        self.url: str = ""
        self.username: str = ""
        self.password: str = ""
        self.remember_password: bool = True
        #: The server's Gramps Web API version, once it has reported one.
        self.api_version: str | None = None
        #: What the server calls the tree it serves, once it has said.
        self.tree_name: str = ""

        self.backend: Backend | None = None
        self.sync: WebApiSyncDiffHandler | None = None
        self.changes: Actions = []
        self.actions: Actions = []
        self.sync_mode: int = MODE_BIDIRECTIONAL
        #: Whether the confirmed run should also move media files.
        self.transfer_media: bool = True

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
        #: Which stage the current media scan was scheduled from.
        self._scan_origin: State = State.COMPARING
        #: Bumped by :meth:`abandon`. Callbacks scheduled under an earlier
        #: value belong to a run the user has walked away from, and are
        #: dropped rather than allowed to drive the session on.
        self._run_id = 0
        self._closing = False

    # --------------------------------------------------------
    # Observable state
    # --------------------------------------------------------
    @property
    def has_missing_files(self) -> bool:
        """Whether any media file can actually be transferred either way."""
        return bool(self.missing_local or self.missing_remote)

    @property
    def has_review_content(self) -> bool:
        """Whether there is anything for the user to confirm.

        Media missing on both sides does not count: nothing can be done about
        those, so they are reported with the outcome rather than as a decision.
        """
        return bool(self.changes or self.has_missing_files)

    @property
    def will_transfer(self) -> bool:
        """Whether the confirmed run still has media files to move."""
        return self.transfer_media and self.has_missing_files

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
        # A read that times out raises this directly, not wrapped in URLError.
        if isinstance(exc, TimeoutError):
            return SyncError(ErrorKind.CONNECTION_FAILED, str(exc))
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
        runner.run(
            func,
            self._guarded(on_success),
            self._guarded(lambda exc: self._on_step_error(exc, step)),
        )

    def _guarded(self, callback: Callable[[Any], None]) -> Callable[[Any], None]:
        """Wrap ``callback`` so a run the user has left cannot resume itself.

        :param callback: What to call if the run is still the current one.
        :returns: The wrapped callback.
        """
        run_id = self._run_id

        def guarded(value: Any) -> None:
            if run_id == self._run_id:
                callback(value)
            else:
                LOG.debug("Dropping a callback from an abandoned run.")

        return guarded

    # --------------------------------------------------------
    # Intents
    # --------------------------------------------------------
    def submit_credentials(
        self,
        url: str,
        username: str,
        password: str,
        remember_password: bool = True,
    ) -> None:
        """Connect, authenticate, then download and diff the remote tree.

        The connection is made off the main loop: building the backend fetches
        an access token, which is a network round trip that used to block the
        window before it had painted anything.

        Anything the user can correct -- a wrong password, a server that is too
        old, an account without the required permission -- returns to
        :attr:`State.CONNECT` with :attr:`login_error` set, rather than ending
        the run. Credentials are stored only once the server has accepted them,
        so a typo never reaches the keyring.

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
        self._goto(State.CONNECTING)
        self.io_runner.run(
            self._connect,
            self._guarded(self._on_connected),
            self._guarded(self._on_connect_error),
        )

    def confirm(self, sync_mode: int, transfer_media: bool = True) -> None:
        """Accept what the review pane showed and carry it out.

        :param sync_mode: One of the ``MODE_*`` constants from :mod:`const`.
        :param transfer_media: Whether to also move the missing media files.
        """
        self.sync_mode = sync_mode
        self.transfer_media = transfer_media
        self._goto(State.APPLYING)
        self._run(Step.APPLY_LOCAL, self._apply_local, self._on_local_applied)

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
            self._scan_origin if step is Step.SCAN_MEDIA else STATE_FOR_STEP[step]
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

    def abandon(self) -> None:
        """Stop the current run and return to the connect pane.

        For changing server without closing the tool. Anything already in
        flight belongs to the run being left, so its callbacks are dropped
        rather than allowed to carry the session forward.

        Refused once writing has begun: walking away mid-apply would leave the
        user with no record of what got through.
        """
        if self.state in (State.APPLYING, State.TRANSFERRING):
            LOG.debug("Not abandoning a run that has started writing.")
            return
        LOG.info("Abandoning the run at %s.", self.state.name)
        self._run_id += 1
        self._release_remote()
        self.tree_name = ""
        self.error = None
        self.login_error = None
        self.failed_in = None
        self.changes = []
        self.actions = []
        self.missing_local = []
        self.missing_remote = []
        self.missing_both = []
        self.downloaded = {}
        self.uploaded = {}
        self._payload = None
        self._goto(State.CONNECT)

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
    # Connecting
    # --------------------------------------------------------
    def _connect(self) -> Connection:
        """Authenticate and read what the server can do. Network only."""
        self._status_from_worker(STATUS_CONNECTING)
        backend = self._backend_factory(self.url, self.username, self.password)
        return Connection(
            backend=backend,
            api_version=backend.get_api_version(),
            task_queue=backend.has_task_queue(),
            tree_name=backend.get_tree_name(),
            permissions=backend.get_permissions(),
        )

    def _on_connected(self, connection: Connection) -> None:
        """Store the credentials and start comparing, back on the main loop."""
        if self._closing:
            return
        self.api_version = connection.api_version
        self.tree_name = connection.tree_name
        problem = self._reject_server(connection)
        if problem is not None:
            self.backend = None
            self.login_error = problem
            self._goto(State.CONNECT)
            return
        self.backend = connection.backend
        self.credentials.save_credentials(
            self.url, self.username, self.password, self.remember_password
        )
        self._start_compare()

    def _on_connect_error(self, exc: BaseException) -> None:
        """Return to the connect pane with something the user can act on."""
        if self._closing:
            return
        self.backend = None
        self.login_error = self._classify(exc, login=True)
        self._goto(State.CONNECT)

    @staticmethod
    def _reject_server(connection: Connection) -> SyncError | None:
        """Return why this server cannot be synced with, or ``None``.

        Ordered from the server outwards. The version comes first because an
        API too old to report a permission claim yields an empty set, which
        would otherwise be reported as a problem with the user's account; what
        the server is configured to do comes before what the account may do,
        for the same reason.
        """
        version_problem = api_version_problem(connection.api_version)
        if version_problem is not None:
            return SyncError(version_problem, connection.api_version or "")
        if not connection.task_queue:
            return SyncError(ErrorKind.SERVER_NO_TASK_QUEUE)
        if REQUIRED_PERMISSION not in connection.permissions:
            return SyncError(ErrorKind.INSUFFICIENT_PERMISSIONS)
        return None

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
        """Check the media state too, so the review can present both at once."""
        if self._closing:
            return
        if not self.changes:
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
        self._status_from_worker(STATUS_PUSHING)
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
        """Record the sync time and move on to the media files."""
        if self._closing:
            return
        self.credentials.set_timestamp(self.url, self.username, self.clock.now())
        if self._media_objects_changed():
            self._start_media_scan()
            return
        self._finish_or_transfer()

    def _media_objects_changed(self) -> bool:
        """Whether the applied actions added or removed media objects.

        Their files are absent on whichever side just received them, so the
        scan taken before the review no longer describes what to transfer and
        has to be repeated. Most runs touch no media object at all and are
        spared the second round trip.
        """
        return any(action[2] == "Media" for action in self.actions)

    # --------------------------------------------------------
    # Media
    # --------------------------------------------------------
    def _start_media_scan(self) -> None:
        """Ask the server which files it lacks, off the main loop.

        The stage the scan was scheduled from is recorded, because a scan
        happens both before the review and again after an apply that touched
        media objects, and the two carry on differently. It also survives a
        failure, which would otherwise leave a retry no way back.
        """
        self._scan_origin = self.state
        self._run(Step.SCAN_MEDIA, self._fetch_remote_missing, self._on_media_scanned)

    def _fetch_remote_missing(self) -> list[dict[str, Any]]:
        """Return the server's list of media objects with no file. Network only."""
        if self._closing:
            return []
        assert self.backend is not None
        self._status_from_worker(STATUS_SCANNING_MEDIA)
        return self.backend.get_missing_files() or []

    def _on_media_scanned(self, remote: list[dict[str, Any]] | None) -> None:
        """Combine the server's answer with a local scan, back on the main loop."""
        if self._closing:
            return
        self._scan_media(remote or [])
        if self._scan_origin is State.APPLYING:
            self._finish_or_transfer()
            return
        self._advance()

    def _finish_or_transfer(self) -> None:
        """Enter whatever follows the apply stage, and start its work."""
        self._advance()
        if self.state is State.TRANSFERRING:
            self._start_transfer()

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

        self.missing_both = sorted((local_missing[h], h) for h in both)
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
