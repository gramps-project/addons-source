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

"""Production implementations of the :mod:`session` ports."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any

from gi.repository import GLib
from gramps.gen.config import config as configman
from gramps.gen.utils.file import media_path_full

LOG = logging.getLogger("grampswebsync")


def get_password(service: str, username: str) -> str | None:
    """Return the stored password for ``username``, if a keyring is available.

    :param service: Keyring service name; the server URL is used.
    :param username: The account whose password is wanted.
    :returns: The password, or ``None`` if unavailable.
    """
    LOG.debug("Retrieving password for user %s", username)
    try:
        import keyring
    except ImportError:
        LOG.warning("Keyring is not installed, cannot retrieve password.")
        return None
    return keyring.get_password(service, username)


def set_password(service: str, username: str, password: str) -> None:
    """Store ``password`` in the keyring, if one is available."""
    try:
        import keyring
    except ImportError:
        return
    LOG.debug("Storing password for user %s", username)
    keyring.set_password(service, username, password)


class ConfigCredentialStore:
    """Credentials in the Gramps config file, password in the system keyring."""

    def __init__(self) -> None:
        self.config = configman.register_manager("webapisync")
        self.config.register("credentials.url", "")
        self.config.register("credentials.username", "")
        self.config.register("credentials.timestamp", 0)
        self.config.load()

    def get_url(self) -> str:
        return self.config.get("credentials.url")

    def get_username(self) -> str:
        return self.config.get("credentials.username")

    def get_password(self) -> str | None:
        url = self.get_url()
        username = self.get_username()
        if not url or not username:
            return None
        return get_password(url, username)

    def get_timestamp(self) -> float:
        return self.config.get("credentials.timestamp")

    def set_timestamp(self, timestamp: float) -> None:
        LOG.debug("Recording last successful sync at %s", timestamp)
        self.config.set("credentials.timestamp", timestamp)
        self.config.save()

    def save_credentials(self, url: str, username: str, password: str) -> None:
        """Persist the credentials, resetting the sync time if the URL changed."""
        if url != self.get_url():
            self.config.set("credentials.timestamp", 0)
        self.config.set("credentials.url", url)
        self.config.set("credentials.username", username)
        set_password(url, username, password)
        self.config.save()


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


class GLibTaskRunner:
    """Defers a task to the GTK main loop.

    The task must not run on a worker thread: it drives Gramps progress
    through the GUI :class:`gramps.gui.user.User`, which touches widgets, and
    GTK is not thread-safe -- doing so segfaults inside ``diff_dbs``.
    :func:`GLib.idle_add` keeps the work on the main loop while still letting
    the caller return so the assistant can paint the progress page first.
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


class SystemClock:
    """The wall clock."""

    def now(self) -> float:
        """Return the current POSIX timestamp."""
        return time.time()
