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

"""A small DSL for writing Gramps Web Sync scenarios.

:class:`SyncScenario` holds a local tree and a remote one derived from it.
Seed the local tree, call :meth:`~SyncScenario.share` to create the remote
side, edit either through its :class:`TreeEditor`, then
:meth:`~SyncScenario.run` a full sync and inspect the :class:`RunResult`::

    with SyncScenario() as sc:
        sc.seed_person("I0001", surname="Doe", changed_at=T0)
        sc.share()
        sc.local.edit_person("I0001", surname="Müller", changed_at=T2)
        sc.remote.edit_person("I0001", surname="Mueller", changed_at=T3)
        result = sc.run()

:data:`T0` to :data:`T3` are increasing timestamps for the ``changed_at``
argument every mutator takes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Any

from const import MODE_BIDIRECTIONAL
from gramps.cli.user import User
from gramps.gen.db import DbTxn
from gramps.gen.db.utils import import_as_dict, make_database
from gramps.gen.lib import Media, Name, Person, Surname, Tag
from session import State, SyncSession

from .fakes import (
    DirectoryMediaStore,
    FakeGrampsWebServer,
    FrozenClock,
    InlineTaskRunner,
    MemoryCredentialStore,
    RecordingListener,
)

#: The server a scenario authenticates against unless told otherwise. Named so
#: that tests asserting on a per-server baseline can name the same entry.
DEFAULT_URL = "https://example.org/api"
DEFAULT_USERNAME = "owner"

#: A convenient baseline "already synced" time for scenarios.
T0 = 1_600_000_000.0
#: A time after :data:`T0`, for an edit on one side.
T1 = T0 + 1_000
#: A time after :data:`T1`, for a later or competing edit.
T2 = T0 + 2_000
#: A time after :data:`T2`.
T3 = T0 + 3_000


class TreeEditor:
    """Mutates one side of a scenario with explicit change timestamps.

    :param db: The database to edit.
    :param media_dir: Directory holding this side's media files, if any.
    """

    def __init__(self, db, media_dir: str | None = None) -> None:
        self.db = db
        self.media_dir = media_dir

    # --------------------------------------------------------
    # Lookup
    # --------------------------------------------------------
    def person(self, gramps_id: str) -> Person | None:
        """Return the person with ``gramps_id``, or ``None`` if absent."""
        return self.db.get_person_from_gramps_id(gramps_id)

    def surname(self, gramps_id: str) -> str | None:
        """Return the primary surname of ``gramps_id``, or ``None`` if absent."""
        person = self.person(gramps_id)
        if person is None:
            return None
        return person.get_primary_name().get_surname()

    def tag(self, name: str) -> Tag | None:
        """Return the tag called ``name``, or ``None`` if absent."""
        return self.db.get_tag_from_name(name)

    def person_ids(self) -> set[str]:
        """Return every Gramps ID in this tree."""
        return {
            self.db.get_person_from_handle(handle).gramps_id
            for handle in self.db.get_person_handles()
        }

    # --------------------------------------------------------
    # Mutation
    # --------------------------------------------------------
    def add_person(
        self,
        gramps_id: str,
        surname: str = "Doe",
        first_name: str = "John",
        changed_at: float = T0,
    ) -> str:
        """Add a person and return its handle.

        :param gramps_id: The Gramps ID to assign.
        :param surname: Primary surname.
        :param first_name: Given name.
        :param changed_at: Value to record as the object's change time.
        :returns: The new person's handle.
        """
        person = Person()
        person.set_gramps_id(gramps_id)
        name = Name()
        name.set_first_name(first_name)
        surname_obj = Surname()
        surname_obj.set_surname(surname)
        name.add_surname(surname_obj)
        person.set_primary_name(name)
        with DbTxn(f"add {gramps_id}", self.db) as trans:
            handle = self.db.add_person(person, trans)
            self.db.commit_person(person, trans, changed_at)
        return handle

    def edit_person(
        self,
        gramps_id: str,
        surname: str | None = None,
        first_name: str | None = None,
        changed_at: float = T1,
    ) -> None:
        """Modify an existing person.

        :param gramps_id: Which person to edit.
        :param surname: New primary surname, if given.
        :param first_name: New given name, if given.
        :param changed_at: Value to record as the object's change time.
        :raises LookupError: If no such person exists.
        """
        person = self.person(gramps_id)
        if person is None:
            raise LookupError(f"No person {gramps_id} in this tree")
        name = person.get_primary_name()
        if surname is not None:
            surname_obj = Surname()
            surname_obj.set_surname(surname)
            name.set_surname_list([surname_obj])
        if first_name is not None:
            name.set_first_name(first_name)
        person.set_primary_name(name)
        with DbTxn(f"edit {gramps_id}", self.db) as trans:
            self.db.commit_person(person, trans, changed_at)

    def delete_person(self, gramps_id: str) -> None:
        """Remove a person from this tree.

        :param gramps_id: Which person to remove.
        :raises LookupError: If no such person exists.
        """
        person = self.person(gramps_id)
        if person is None:
            raise LookupError(f"No person {gramps_id} in this tree")
        with DbTxn(f"delete {gramps_id}", self.db) as trans:
            self.db.remove_person(person.handle, trans)

    def add_media(
        self,
        gramps_id: str,
        filename: str,
        content: bytes = b"fake image bytes",
        changed_at: float = T0,
        on_disk: bool = True,
    ) -> str:
        """Add a media object, optionally writing its file.

        :param gramps_id: The Gramps ID to assign.
        :param filename: Path relative to the media directory.
        :param content: Bytes to write when ``on_disk`` is true.
        :param changed_at: Value to record as the object's change time.
        :param on_disk: Whether to create the file. ``False`` produces a media
            object whose file is missing.
        :returns: The new media object's handle.
        """
        media = Media()
        media.set_gramps_id(gramps_id)
        media.set_path(filename)
        media.set_description(gramps_id)
        with DbTxn(f"add media {gramps_id}", self.db) as trans:
            handle = self.db.add_media(media, trans)
            self.db.commit_media(media, trans, changed_at)
        if on_disk and self.media_dir is not None:
            target = os.path.join(self.media_dir, filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as fobj:
                fobj.write(content)
        return handle

    def add_tag(self, name: str, changed_at: float = T0) -> str:
        """Add a tag and return its handle."""
        tag = Tag()
        tag.set_name(name)
        with DbTxn(f"add tag {name}", self.db) as trans:
            handle = self.db.add_tag(tag, trans)
            self.db.commit_tag(tag, trans, changed_at)
        return handle


@dataclass
class RunResult:
    """The outcome of a :meth:`SyncScenario.run`.

    :param states: Every state the session entered, in order.
    :param progress: Progress updates as ``(kind, fraction)``.
    :param statuses: Status stages reported, in order.
    :param session: The session itself, for further assertions.
    """

    states: list[State]
    progress: list[tuple[str, float]]
    statuses: list[str]
    session: SyncSession

    @property
    def final_state(self) -> State:
        """The state the session ended in."""
        return self.states[-1] if self.states else State.INTRO

    @property
    def error(self):
        """The terminal error, if the run failed."""
        return self.session.error

    @property
    def login_error(self):
        """The recoverable login error, if login was rejected."""
        return self.session.login_error

    def change_ids(self, change_type: str) -> set[str]:
        """Return the Gramps IDs reported under a given change type.

        :param change_type: One of the ``C_*`` constants from :mod:`const`.
        :returns: The set of Gramps IDs (tag *names*, for tags).
        """
        ids = set()
        for kind, _handle, class_name, obj1, obj2 in self.session.changes:
            if kind != change_type:
                continue
            obj = obj1 if obj1 is not None else obj2
            ids.add(obj.name if class_name == "Tag" else obj.gramps_id)
        return ids


class SyncScenario:
    """Builds two related trees, then runs a full sync between them.

    Use as a context manager so the databases and temporary directories are
    cleaned up::

        with SyncScenario() as sc:
            ...
    """

    def __init__(self, permissions: set[str] | None = None) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="gws_scenario_")
        self.local_media_dir = os.path.join(self._tmpdir, "local_media")
        os.makedirs(self.local_media_dir, exist_ok=True)

        self.user = User(auto_accept=True, quiet=True)
        self.db1 = make_database("sqlite")
        self.db1.load(":memory:")

        self.local = TreeEditor(self.db1, media_dir=self.local_media_dir)
        #: Set by :meth:`share`; until then there is no remote tree.
        self.remote: TreeEditor | None = None
        self.server: FakeGrampsWebServer | None = None
        self._permissions = permissions

        self.clock = FrozenClock()
        self.credentials = MemoryCredentialStore()
        self.listener = RecordingListener()

    # --------------------------------------------------------
    # Setup
    # --------------------------------------------------------
    def seed_person(self, gramps_id: str, **kwargs: Any) -> str:
        """Add a person to the local tree before it is shared."""
        return self.local.add_person(gramps_id, **kwargs)

    def share(self, last_synced: float | None = T0) -> None:
        """Create the remote tree as a copy of the local one.

        :param last_synced: Value to record as the last successful sync time.
            Pass ``None`` to simulate a first-ever sync.
        """
        export_path = os.path.join(self._tmpdir, "seed.gramps")
        from gramps.plugins.export.exportxml import export_data

        if not export_data(self.db1, export_path, self.user):
            raise RuntimeError("Failed to export the seed tree")
        remote_db = import_as_dict(export_path, self.user)
        if remote_db is None:
            raise RuntimeError("Failed to import the seed tree")

        kwargs: dict[str, Any] = {"db": remote_db}
        if self._permissions is not None:
            kwargs["permissions"] = self._permissions
        self.server = FakeGrampsWebServer(**kwargs)
        self.remote = TreeEditor(remote_db)
        self.credentials.timestamp = last_synced or 0.0

    def _require_shared(self) -> FakeGrampsWebServer:
        """Return the server, raising a clear error if :meth:`share` was skipped."""
        if self.server is None:
            raise RuntimeError("Call share() before running the scenario")
        return self.server

    def make_session(self) -> SyncSession:
        """Build a :class:`SyncSession` wired to this scenario's fakes."""
        server = self._require_shared()
        return SyncSession(
            db=self.db1,
            user=self.user,
            backend_factory=lambda url, username, password: server,
            credentials=self.credentials,
            media=DirectoryMediaStore(self.local_media_dir),
            runner=InlineTaskRunner(),
            clock=self.clock,
            listener=self.listener,
        )

    # --------------------------------------------------------
    # Running
    # --------------------------------------------------------
    def run(
        self,
        mode: int = MODE_BIDIRECTIONAL,
        confirm_files: bool = True,
        url: str = DEFAULT_URL,
        username: str = DEFAULT_USERNAME,
        password: str = "secret",
    ) -> RunResult:
        """Drive a complete sync, answering every confirmation.

        Stops early if the session fails or returns to the login page.

        :param mode: The sync mode to confirm with.
        :param confirm_files: Whether to accept the media transfer. ``False``
            leaves the session on :attr:`State.REVIEW_FILES`.
        :param url: Server URL to submit.
        :param username: User name to submit.
        :param password: Password to submit.
        :returns: A :class:`RunResult` describing the run.
        """
        session = self.make_session()
        session.begin()
        session.submit_credentials(url, username, password)

        if session.state is State.REVIEW_CHANGES:
            session.confirm_changes(mode)
        if session.state is State.REVIEW_FILES and confirm_files:
            session.confirm_files()

        return RunResult(
            states=list(self.listener.states),
            progress=list(self.listener.progress),
            statuses=list(self.listener.statuses),
            session=session,
        )

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    def close(self) -> None:
        """Release databases and temporary directories."""
        if self.server is not None:
            self.server.close()
            self.server = None
        try:
            self.db1.close()
        except Exception:  # noqa: BLE001 -- teardown must not mask failures
            pass
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def __enter__(self) -> SyncScenario:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
