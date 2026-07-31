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

"""In-process test doubles for the :mod:`session` ports.

:class:`FakeGrampsWebServer` implements :class:`session.Backend` over a real
Gramps database, exporting Gramps XML and applying transaction payloads;
:meth:`~FakeGrampsWebServer.fail_next` and
:meth:`~FakeGrampsWebServer.fail_always` inject faults.

The remaining classes stand in for the other ports:
:class:`InlineTaskRunner`, :class:`FrozenClock`,
:class:`MemoryCredentialStore`, :class:`DirectoryMediaStore` and
:class:`RecordingListener`. None depend on a test framework.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

from gramps.cli.user import User
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import make_database
from gramps.gen.lib.json_utils import data_to_object
from gramps.plugins.export.exportxml import export_data

#: Permissions a Gramps Web user needs for a sync to be allowed to proceed.
DEFAULT_PERMISSIONS = frozenset({"ViewPrivate", "EditObject", "AddObject"})


def http_error(code: int, url: str = "https://example.org/api/") -> HTTPError:
    """Build an :class:`HTTPError` with ``code``, for fault injection.

    :param code: The HTTP status to simulate.
    :param url: The URL to attribute the error to.
    :returns: A ready-to-raise :class:`HTTPError`.
    """
    return HTTPError(url, code, f"Simulated HTTP {code}", {}, None)  # type: ignore[arg-type]


# ------------------------------------------------------------
#
# FakeGrampsWebServer
#
# ------------------------------------------------------------
class FakeGrampsWebServer:
    """A Gramps Web server backed by a real in-memory Gramps database.

    Satisfies the :class:`session.Backend` protocol.

    :param db: The database to serve. A fresh empty one is created if omitted.
    :param permissions: Permissions to report for the logged-in user.
    :param lang: Value returned by :meth:`get_lang`.
    """

    def __init__(
        self,
        db=None,
        permissions: set[str] | frozenset[str] = DEFAULT_PERMISSIONS,
        lang: str | None = "en",
    ) -> None:
        if db is None:
            db = make_database("sqlite")
            db.load(":memory:")
        self.db = db
        self.permissions = set(permissions)
        self.lang = lang
        self.user = User(auto_accept=True, quiet=True)

        #: Handles of media objects whose file the server actually holds.
        self.media_files: dict[str, bytes] = {}
        #: Every method call made against this server, in order.
        self.calls: list[str] = []
        #: Each payload passed to :meth:`commit`.
        self.committed: list[list[dict[str, Any]]] = []
        #: Method name -> exception, raised once then cleared.
        self._fail_once: dict[str, BaseException] = {}
        #: Method name -> exception, raised on every call.
        self._fail_always: dict[str, BaseException] = {}
        self._tempfiles: list[Path] = []

    # --------------------------------------------------------
    # Fault injection
    # --------------------------------------------------------
    def fail_next(self, method: str, exc: BaseException) -> None:
        """Make the next call to ``method`` raise ``exc``.

        :param method: Name of the backend method, e.g. ``"download_xml"``.
        :param exc: The exception to raise.
        """
        self._fail_once[method] = exc

    def fail_always(self, method: str, exc: BaseException) -> None:
        """Make every call to ``method`` raise ``exc``."""
        self._fail_always[method] = exc

    def _enter(self, method: str) -> None:
        """Record a call and honour any fault configured for it."""
        self.calls.append(method)
        exc = self._fail_once.pop(method, None) or self._fail_always.get(method)
        if exc is not None:
            raise exc

    # --------------------------------------------------------
    # Backend protocol
    # --------------------------------------------------------
    def get_permissions(self) -> set[str]:
        """Return the logged-in user's permissions."""
        self._enter("get_permissions")
        return set(self.permissions)

    def get_lang(self) -> str | None:
        """Return the server's configured language."""
        self._enter("get_lang")
        return self.lang

    def download_xml(self) -> Path:
        """Export the served database to a Gramps XML file.

        The caller owns the file and is expected to unlink it.

        :returns: Path to the exported ``.gramps`` file.
        """
        self._enter("download_xml")
        handle, name = tempfile.mkstemp(suffix=".gramps", prefix="fakeweb_")
        os.close(handle)
        path = Path(name)
        self._tempfiles.append(path)
        if not export_data(self.db, str(path), self.user):
            raise ValueError("Fake server failed to export XML")
        return path

    def commit(
        self,
        payload: list[dict[str, Any]],
        force: bool = True,
        progress_callback: Callable | None = None,
    ) -> None:
        """Apply a transaction payload to the served database.

        :param payload: Items as produced by
            :func:`webapihandler.transaction_to_json`.
        :param force: Accepted for protocol compatibility; ignored.
        :param progress_callback: Called with a fraction in ``[0, 1]``.
        """
        self._enter("commit")
        self.committed.append(payload)
        if not payload:
            return
        with DbTxn("Fake server transaction", self.db, batch=True) as trans:
            for index, item in enumerate(payload):
                self._apply_item(item, trans)
                if progress_callback is not None:
                    progress_callback((index + 1) / len(payload))

    def _apply_item(self, item: dict[str, Any], trans: DbTxn) -> None:
        """Apply a single transaction item to the served database."""
        class_name = item["_class"]
        if item["type"] == "delete":
            method = self.db.method("remove_%s", class_name)
            assert method is not None
            method(item["handle"], trans)
            return
        obj = data_to_object(item["new"])
        # commit_* upserts, covering both "add" and "update". Passing the
        # object's own change time keeps timestamps meaningful across a sync.
        method = self.db.method("commit_%s", class_name)
        assert method is not None
        method(obj, trans, obj.change)

    def get_missing_files(self) -> list[dict[str, Any]]:
        """Return media objects the server knows about but has no file for."""
        self._enter("get_missing_files")
        return [
            {"gramps_id": media.gramps_id, "handle": media.handle}
            for media in self.db.iter_media()
            if media.handle not in self.media_files
        ]

    def download_media_file(self, handle: str, path: str) -> bool:
        """Write the server's copy of a media file to ``path``."""
        self._enter("download_media_file")
        if handle not in self.media_files:
            raise http_error(404)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(self.media_files[handle])
        return True

    def upload_media_file(self, handle: str, path: str) -> bool:
        """Store a media file uploaded by the client."""
        self._enter("upload_media_file")
        self.media_files[handle] = Path(path).read_bytes()
        return True

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    def close(self) -> None:
        """Close the served database and remove leftover export files."""
        for path in self._tempfiles:
            path.unlink(missing_ok=True)
        self._tempfiles.clear()
        try:
            self.db.close()
        except Exception:  # noqa: BLE001 -- teardown must not mask failures
            pass


# ------------------------------------------------------------
#
# Simple doubles
#
# ------------------------------------------------------------
class InlineTaskRunner:
    """Runs each task synchronously on the calling thread.

    By the time ``run`` returns, the step and its completion callback have
    both finished. Standing in for both runners keeps scenarios single-threaded
    and their assertions deterministic.
    """

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Execute ``func`` and dispatch to the appropriate callback."""
        try:
            result = func()
        except BaseException as exc:  # noqa: BLE001 -- mirrors the real runner
            on_error(exc)
        else:
            on_success(result)

    def post(self, func: Callable[[], None]) -> None:
        """Run ``func`` immediately; there is no other thread to marshal from."""
        func()


class FrozenClock:
    """A clock that only moves when :meth:`advance` is called.

    :param start: The initial time, as a POSIX timestamp.
    """

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.time = start

    def now(self) -> float:
        """Return the current fake time."""
        return self.time

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds``."""
        self.time += seconds


class MemoryCredentialStore:
    """In-memory stand-in for the config file and keyring.

    Keyed by ``(url, username)`` like the real store, so each server keeps its
    own sync baseline and switching between them does not discard one.

    :param url: Initially stored server URL.
    :param username: Initially stored user name.
    :param password: Initially stored password.
    :param timestamp: Initially stored last-sync time.
    """

    def __init__(
        self,
        url: str = "https://example.org/api",
        username: str = "owner",
        password: str = "secret",
        timestamp: float = 0.0,
    ) -> None:
        self.url = url
        self.username = username
        self.password = password
        #: ``(url, username)`` -> last successful sync time.
        self.timestamps: dict[tuple[str, str], float] = {(url, username): timestamp}
        #: ``(url, username)`` -> whether its password may be stored.
        self.remembered: dict[tuple[str, str], bool] = {}
        #: Every ``(url, username, password)`` passed to
        #: :meth:`save_credentials`.
        self.saved: list[tuple[str, str, str]] = []

    @property
    def timestamp(self) -> float:
        """The baseline of the last-used entry, for convenient assertions."""
        return self.timestamps.get((self.url, self.username), 0.0)

    @timestamp.setter
    def timestamp(self, value: float) -> None:
        self.timestamps[(self.url, self.username)] = value

    def get_url(self) -> str:
        return self.url

    def get_username(self) -> str:
        return self.username

    def get_password(self) -> str | None:
        return self.password

    def get_timestamp(self, url: str, username: str) -> float:
        return self.timestamps.get((url, username), 0.0)

    def set_timestamp(self, url: str, username: str, timestamp: float) -> None:
        self.timestamps[(url, username)] = timestamp
        self.url = url
        self.username = username

    def save_credentials(
        self, url: str, username: str, password: str, remember_password: bool = True
    ) -> None:
        self.url = url
        self.username = username
        self.password = password if remember_password else None
        self.remembered[(url, username)] = remember_password
        self.timestamps.setdefault((url, username), 0.0)
        self.saved.append((url, username, password))


class DirectoryMediaStore:
    """Media store resolving paths under a directory owned by the test.

    :param base_dir: Directory that plays the role of the Gramps media path.
    """

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def full_path(self, media: Any) -> str:
        """Return the absolute path of ``media``'s file."""
        return os.path.join(self.base_dir, media.get_path())

    def exists(self, media: Any) -> bool:
        """Whether ``media``'s file is present on disk."""
        return os.path.exists(self.full_path(media))


class RecordingListener:
    """Records state, status and progress updates for later assertions."""

    def __init__(self) -> None:
        #: States entered, in order.
        self.states: list[Any] = []
        #: ``(kind, fraction)`` progress updates, in order.
        self.progress: list[tuple[str, float]] = []
        #: Status stages reported, in order.
        self.statuses: list[str] = []

    def on_state_changed(self, state) -> None:
        self.states.append(state)

    def on_progress(self, kind: str, fraction: float) -> None:
        self.progress.append((kind, fraction))

    def on_status(self, stage: str) -> None:
        self.statuses.append(stage)
