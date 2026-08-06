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

"""Production implementations of the :mod:`session` ports.

Two task runners are provided rather than one. :class:`GLibTaskRunner` keeps a
step on the GTK main loop, which is mandatory for anything touching a Gramps
database: the sqlite backend binds a connection to its creating thread.
:class:`IoRunner` moves a step to a worker thread, which is where the network
calls belong -- they are the only part of a sync that can block indefinitely.

:class:`ConfigCredentialStore` keeps one entry per ``(url, username)`` pair, so
each server carries its own sync baseline.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from gi.repository import GLib
from gramps.gen.config import config as configman
from gramps.gen.utils.file import media_path_full

LOG = logging.getLogger("grampswebsync")

#: Keys the pre-multi-server versions of the addon used. Still written, as a
#: mirror of the last-used entry, so that downgrading keeps working.
LEGACY_URL = "credentials.url"
LEGACY_USERNAME = "credentials.username"
LEGACY_TIMESTAMP = "credentials.timestamp"

#: snapd interface granting access to ``org.freedesktop.secrets``. Declared by
#: the Gramps snap but manually connected, so it is off until the user says so.
SNAP_KEYRING_INTERFACE = "password-manager-service"


def normalize_url(url: str) -> str:
    """Return ``url`` in the form used as a credential-store key.

    Normalizing here rather than in :class:`webapihandler.WebApiHandler` keeps a
    stray trailing slash from looking like a different server, which would
    otherwise cost the entry its sync baseline.

    :param url: The URL as typed or stored.
    :returns: The URL without surrounding whitespace or trailing slashes.
    """
    return url.strip().rstrip("/")


# ------------------------------------------------------------
#
# Keyring
#
# ------------------------------------------------------------
@dataclass(frozen=True)
class KeyringUnavailable:
    """A keyring call that failed, for the view to report.

    :param detail: The underlying exception text, for logs and details views.
    :param snap_command: The ``snap connect`` command that would fix it, when
        running confined under snap; ``None`` elsewhere.
    """

    detail: str
    snap_command: str | None = None


def snap_connect_command() -> str | None:
    """Return the command connecting the keyring interface, under snap only.

    ``SNAP_INSTANCE_NAME`` rather than ``SNAP_NAME`` is what makes the command
    correct under a parallel install.

    :returns: The command, or ``None`` when not running as a snap.
    """
    if not os.environ.get("SNAP"):
        return None
    name = (
        os.environ.get("SNAP_INSTANCE_NAME")
        or os.environ.get("SNAP_NAME")
        or "gramps"
    )
    return f"snap connect {name}:{SNAP_KEYRING_INTERFACE}"


class Keyring:
    """The system keyring, degrading to unavailable instead of raising.

    Every call is guarded with a bare ``except Exception``. The failures seen in
    practice do not derive from ``keyring.errors``: under snap confinement the
    Secret Service backend raises ``jeepney.wrappers.DBusErrorResponse``, from a
    transitive dependency, so catching the keyring package's own hierarchy is
    not enough.

    After a failure the keyring is marked unavailable and no further calls are
    attempted for the lifetime of this object.
    """

    def __init__(self) -> None:
        self.unavailable: KeyringUnavailable | None = None

    def _module(self):
        """Return the ``keyring`` module, or ``None`` if it cannot be used."""
        if self.unavailable is not None:
            return None
        try:
            import keyring
        except Exception as exc:  # noqa: BLE001 -- absence is not an error here
            LOG.warning("Keyring is not available: %s", exc)
            self.unavailable = KeyringUnavailable(str(exc), snap_connect_command())
            return None
        return keyring

    def _failed(self, action: str, exc: Exception) -> None:
        """Record that ``action`` failed and stop using the keyring."""
        LOG.warning("Keyring %s failed: %s", action, exc)
        self.unavailable = KeyringUnavailable(str(exc), snap_connect_command())

    def get(self, service: str, username: str) -> str | None:
        """Return the stored password, or ``None`` if it cannot be read."""
        keyring = self._module()
        if keyring is None:
            return None
        try:
            return keyring.get_password(service, username)
        except Exception as exc:  # noqa: BLE001 -- reported through `unavailable`
            self._failed("read", exc)
            return None

    def set(self, service: str, username: str, password: str) -> bool:
        """Store ``password``. Returns whether it was actually stored."""
        keyring = self._module()
        if keyring is None:
            return False
        try:
            keyring.set_password(service, username, password)
        except Exception as exc:  # noqa: BLE001 -- reported through `unavailable`
            self._failed("write", exc)
            return False
        return True

    def delete(self, service: str, username: str) -> bool:
        """Remove a stored password.

        :returns: Whether the password is now gone.
        """
        keyring = self._module()
        if keyring is None:
            return False
        try:
            keyring.delete_password(service, username)
        except Exception as exc:  # noqa: BLE001 -- absent entries raise too
            # Deleting what was never there raises, and is harmless; a keyring
            # that is actually broken still has the password afterwards. A read
            # that fails proves nothing either way, so it counts as a failure.
            before = self.unavailable
            if self.get(service, username) is None and self.unavailable is before:
                LOG.debug("Nothing to delete for %s: %s", username, exc)
                return True
            self._failed("delete", exc)
            return False
        return True


# ------------------------------------------------------------
#
# Credential store
#
# ------------------------------------------------------------
class ConfigCredentialStore:
    """Server entries in the Gramps config file, passwords in the keyring.

    Each entry is keyed by ``(url, username)`` -- which identifies a tree, since
    a Gramps Web account belongs to exactly one -- and carries its own
    ``timestamp``, the baseline the diff uses. Per-entry baselines are why
    switching servers no longer discards one.
    """

    def __init__(
        self,
        keyring: Keyring | None = None,
        config: Any = None,
        tree_id: str = "",
    ) -> None:
        """Initialize the store.

        :param keyring: Password storage. A real one is built if omitted.
        :param config: An already-registered config manager. Tests pass one
            pointed at a temporary directory so a run cannot write to the
            user's own Gramps configuration.
        :param tree_id: Identifier of the local family tree that is open, from
            ``db.get_dbid()``. Entries record the tree they were synced from,
            so that opening another one does not silently offer this tree's
            server. Empty means the tree is unknown and no entry can match.
        """
        self.keyring = keyring if keyring is not None else Keyring()
        self.tree_id = tree_id or ""
        self.config = (
            config if config is not None else configman.register_manager("webapisync")
        )
        self.config.register(LEGACY_URL, "")
        self.config.register(LEGACY_USERNAME, "")
        self.config.register(LEGACY_TIMESTAMP, 0)
        self.config.register("credentials.servers", [])
        self.config.register("credentials.last_used", [])
        self.config.load()
        self._reconcile_legacy()

    # --------------------------------------------------------
    # Raw access
    # --------------------------------------------------------
    def _servers(self) -> list[dict[str, Any]]:
        """Return the stored entries, tolerating a corrupted config value.

        A value the config manager could not parse is stored as ``None`` rather
        than falling back to the registered default, so the type has to be
        checked rather than assumed.
        """
        servers = self.config.get("credentials.servers")
        if not isinstance(servers, list):
            LOG.warning("Ignoring unreadable server list in config.")
            return []
        return [entry for entry in servers if isinstance(entry, dict)]

    def _find(
        self, servers: list[dict[str, Any]], url: str, username: str
    ) -> dict[str, Any] | None:
        """Return the entry for ``(url, username)``, or ``None``."""
        url = normalize_url(url)
        for entry in servers:
            if normalize_url(entry.get("url", "")) == url and (
                entry.get("username", "") == username
            ):
                return entry
        return None

    def _last_used(self) -> tuple[str, str] | None:
        """Return the ``(url, username)`` last synced, if any."""
        pair = self.config.get("credentials.last_used")
        if isinstance(pair, list) and len(pair) == 2:
            return str(pair[0]), str(pair[1])
        return None

    def _for_tree(self, servers: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Return the entry recorded against the tree that is open, if any.

        The last-used entry is preferred among several, which only arises if
        one tree has been synced to more than one account.
        """
        if not self.tree_id:
            return None
        matches = [
            entry for entry in servers if entry.get("tree_id") == self.tree_id
        ]
        if not matches:
            return None
        pair = self._last_used()
        if pair is not None:
            entry = self._find(matches, *pair)
            if entry is not None:
                return entry
        return matches[0]

    def _current(self) -> dict[str, Any] | None:
        """Return the entry to offer: this tree's, else the last used.

        Falling back to the last-used entry rather than to nothing keeps the
        connect pane pre-filled for anyone whose entries predate tree ids.
        """
        servers = self._servers()
        entry = self._for_tree(servers)
        if entry is not None:
            return entry
        pair = self._last_used()
        if pair is not None:
            entry = self._find(servers, *pair)
            if entry is not None:
                return entry
        return servers[0] if len(servers) == 1 else None

    def _write(self, servers: list[dict[str, Any]]) -> None:
        """Persist the entry list and the legacy mirror, then save."""
        self.config.set("credentials.servers", servers)
        self._write_legacy_mirror(servers)
        self.config.save()

    def _write_legacy_mirror(self, servers: list[dict[str, Any]]) -> None:
        """Mirror the last-used entry into the pre-multi-server keys.

        An older version of the addon reads only those keys. Keeping them
        current means a downgrade finds its credentials and its baseline where
        it expects them, instead of resyncing from scratch.
        """
        pair = self._last_used()
        entry = self._find(servers, *pair) if pair is not None else None
        if entry is None:
            self.config.set(LEGACY_URL, "")
            self.config.set(LEGACY_USERNAME, "")
            self.config.set(LEGACY_TIMESTAMP, 0)
            return
        self.config.set(LEGACY_URL, entry.get("url", ""))
        self.config.set(LEGACY_USERNAME, entry.get("username", ""))
        self.config.set(LEGACY_TIMESTAMP, int(entry.get("timestamp", 0) or 0))

    def _reconcile_legacy(self) -> None:
        """Fold the legacy keys into the entry list.

        Covers both cases in one path: on first run after an upgrade there is no
        matching entry and the legacy triple becomes one, and after a downgrade
        and back the entry exists but an older version may have synced in the
        meantime, so the later of the two baselines wins.
        """
        legacy_url = normalize_url(self.config.get(LEGACY_URL) or "")
        if not legacy_url:
            return
        legacy_username = self.config.get(LEGACY_USERNAME) or ""
        legacy_timestamp = float(self.config.get(LEGACY_TIMESTAMP) or 0)

        servers = self._servers()
        entry = self._find(servers, legacy_url, legacy_username)
        if entry is None:
            LOG.info("Migrating stored credentials to the server list.")
            servers.append(
                {
                    "url": legacy_url,
                    "username": legacy_username,
                    "timestamp": legacy_timestamp,
                    "remember_password": True,
                }
            )
            self.config.set("credentials.last_used", [legacy_url, legacy_username])
        elif legacy_timestamp > float(entry.get("timestamp", 0) or 0):
            entry["timestamp"] = legacy_timestamp
        else:
            return
        self.config.set("credentials.servers", servers)
        self.config.save()

    # --------------------------------------------------------
    # CredentialStore protocol
    # --------------------------------------------------------
    def get_url(self) -> str:
        """Return the last-used server URL, for pre-filling the login page."""
        entry = self._current()
        return entry.get("url", "") if entry else ""

    def get_username(self) -> str:
        """Return the last-used user name."""
        entry = self._current()
        return entry.get("username", "") if entry else ""

    def get_password(self) -> str | None:
        """Return the last-used password, if one was stored and is readable."""
        entry = self._current()
        if not entry or not entry.get("remember_password", True):
            return None
        url = entry.get("url", "")
        username = entry.get("username", "")
        if not url or not username:
            return None
        return self.keyring.get(url, username)

    def get_remember_password(self) -> bool:
        """Whether the entry on offer is allowed to keep its password.

        :returns: The stored choice, defaulting to true for a server that has
            not been seen before.
        """
        entry = self._current()
        if entry is None:
            return True
        return bool(entry.get("remember_password", True))

    def get_timestamp(self, url: str, username: str) -> float:
        """Return the sync baseline for one server.

        :param url: The server URL.
        :param username: The account on that server.
        :returns: The last successful sync time, or ``0`` if never synced.
        """
        entry = self._find(self._servers(), url, username)
        return float(entry.get("timestamp", 0) or 0) if entry else 0.0

    def set_timestamp(self, url: str, username: str, timestamp: float) -> None:
        """Record a successful sync against one server.

        This is also where an entry adopts the tree that is open. Merely
        authenticating is deliberately not enough: connecting to the wrong
        server by mistake would otherwise claim the tree before the user has
        seen what the sync would do, and go on connecting there unprompted.
        """
        servers = self._servers()
        entry = self._find(servers, url, username)
        if entry is None:
            entry = {
                "url": normalize_url(url),
                "username": username,
                "remember_password": True,
            }
            servers.append(entry)
        entry["timestamp"] = timestamp
        if self.tree_id:
            self._claim_tree(servers, entry)
        LOG.debug("Recording last successful sync at %s", timestamp)
        self.config.set("credentials.last_used", [normalize_url(url), username])
        self._write(servers)

    def _claim_tree(
        self, servers: list[dict[str, Any]], entry: dict[str, Any]
    ) -> None:
        """Record the open tree on ``entry``, and take it off every other one.

        Any entry that loses the claim also loses its baseline.
        """
        # A tree has one current server, or the choice falls to list order.
        # The old baseline no longer describes anything true, and keeping it
        # would raise the comparison cutoff; too high a cutoff makes objects
        # look deleted instead of added.
        for other in servers:
            if other is not entry and other.get("tree_id") == self.tree_id:
                LOG.info(
                    "Tree moved away from %s; dropping its baseline.",
                    other.get("url"),
                )
                del other["tree_id"]
                other["timestamp"] = 0.0
        entry["tree_id"] = self.tree_id

    def save_credentials(
        self, url: str, username: str, password: str, remember_password: bool = True
    ) -> None:
        """Persist one server entry, and its password if asked to.

        The entry itself is always stored: it carries the sync baseline, which
        is not a credential, and discarding it would make every later run a cold
        sync. ``remember_password`` governs the keyring only.

        :param url: The server URL, already sanitized by the caller.
        :param username: The account name.
        :param password: The password, stored only if ``remember_password``.
        :param remember_password: Whether the password may go to the keyring.
        """
        url = normalize_url(url)
        servers = self._servers()
        entry = self._find(servers, url, username)
        if entry is None:
            entry = {"url": url, "username": username, "timestamp": 0.0}
            servers.append(entry)
        entry["remember_password"] = remember_password

        if remember_password:
            self.keyring.set(url, username, password)
        else:
            # Turning the setting off has to erase what is already stored, not
            # merely stop writing, or it appears to do nothing.
            self.keyring.delete(url, username)

        self.config.set("credentials.last_used", [url, username])
        self._write(servers)

    def forget(self, url: str, username: str) -> None:
        """Remove one server entry entirely, keyring item included."""
        url = normalize_url(url)
        servers = [
            entry
            for entry in self._servers()
            if not (
                normalize_url(entry.get("url", "")) == url
                and entry.get("username", "") == username
            )
        ]
        self.keyring.delete(url, username)
        if self._last_used() == (url, username):
            self.config.set("credentials.last_used", [])
        self._write(servers)

    def is_for_open_tree(self) -> bool:
        """Whether the stored credentials belong to the tree that is open.

        Only then may a server be contacted without the user asking, since a
        sync against the wrong tree proposes deleting both of them.
        """
        return self._for_tree(self._servers()) is not None

    def is_from_another_tree(self) -> bool:
        """Whether the credentials on offer were last synced from a different tree.

        Distinguished from merely having no tree recorded, which is what every
        entry looks like until its first sync after upgrading, and which says
        nothing either way.
        """
        entry = self._current()
        if entry is None or not self.tree_id:
            return False
        recorded = entry.get("tree_id", "")
        return bool(recorded) and recorded != self.tree_id

    def keyring_error(self) -> KeyringUnavailable | None:
        """Return the keyring failure to report, if one has occurred."""
        return self.keyring.unavailable


# ------------------------------------------------------------
#
# Media
#
# ------------------------------------------------------------
class GrampsMediaStore:
    """Resolves media paths against the open Gramps database's media path.

    :param db: The local database whose media base path applies.
    """

    def __init__(self, db) -> None:
        self.db = db

    def full_path(self, media: Any) -> str:
        """Return the absolute path of ``media``'s file."""
        return media_path_full(self.db, media.get_path())

    def exists(self, media: Any) -> bool:
        """Whether ``media``'s file is present on disk."""
        return os.path.exists(self.full_path(media))


# ------------------------------------------------------------
#
# Task runners
#
# ------------------------------------------------------------
def _post_to_main_loop(func: Callable[[], None]) -> None:
    """Schedule ``func`` to run once on the GTK main loop."""

    def once() -> bool:
        func()
        return False

    GLib.idle_add(once)


class GLibTaskRunner:
    """Defers a task to the GTK main loop.

    For steps that touch a Gramps database. Those must not run on a worker
    thread: the sqlite backend passes no ``check_same_thread=False`` and shares
    one cursor, so a connection is usable only from the thread that created it.
    They also drive Gramps progress through the GUI
    :class:`gramps.gui.user.User`, which touches widgets.

    :func:`GLib.idle_add` keeps the work on the main loop while still letting the
    caller return, so the view can paint the progress page first.
    """

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Schedule ``func`` on the main loop and dispatch the outcome there."""

        def once() -> bool:
            try:
                result = func()
            except BaseException as exc:  # noqa: BLE001 -- reported, not swallowed
                on_error(exc)
            else:
                on_success(result)
            return False  # run once

        GLib.idle_add(once)

    def post(self, func: Callable[[], None]) -> None:
        """Run ``func`` on the main loop."""
        _post_to_main_loop(func)


class IoRunner:
    """Runs a task on a worker thread, dispatching the outcome on the main loop.

    For steps that only do network I/O. Those are where a sync spends most of
    its wall-clock time and the only place it can block indefinitely, so moving
    them off the main loop is what makes the window stay responsive and Cancel
    actually work. Callbacks are marshalled back through
    :func:`GLib.idle_add`, so listeners still run on the thread that owns GTK.
    """

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        """Run ``func`` on a worker thread; call back on the main loop."""

        def work() -> None:
            try:
                result = func()
            except BaseException as exc:  # noqa: BLE001 -- reported, not swallowed
                # Handed straight on: `except ... as exc` unbinds the name when
                # the block exits, and the callback runs later than that.
                self._dispatch(on_error, exc)
            else:
                self._dispatch(on_success, result)

        threading.Thread(target=work, daemon=True, name="grampswebsync-io").start()

    @staticmethod
    def _dispatch(callback: Callable[[Any], None], value: Any) -> None:
        """Deliver ``value`` to ``callback`` on the main loop."""
        _post_to_main_loop(lambda: callback(value))

    def post(self, func: Callable[[], None]) -> None:
        """Run ``func`` on the main loop.

        Progress raised inside a network step arrives here, so that listeners
        drawing widgets never run on the worker thread.
        """
        _post_to_main_loop(func)


class SystemClock:
    """The wall clock."""

    def now(self) -> float:
        """Return the current POSIX timestamp."""
        return time.time()
