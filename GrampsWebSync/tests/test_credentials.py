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

"""Tests for :class:`adapters.ConfigCredentialStore` and its keyring guard.

Every store is built against a config manager in a temporary directory, so no
test can write to the user's own Gramps configuration.
"""

from __future__ import annotations

import itertools
import shutil
import tempfile
import unittest
import unittest.mock
from typing import cast

from adapters import (
    LEGACY_TIMESTAMP,
    LEGACY_URL,
    LEGACY_USERNAME,
    ConfigCredentialStore,
    Keyring,
    normalize_url,
    snap_connect_command,
)
from gramps.gen.config import config as configman

URL = "https://example.org/api"
OTHER = "https://other.example/api"

#: Config managers are cached by name, so each store needs its own.
_counter = itertools.count()


class FakeKeyring:
    """A keyring that records calls and can be made to fail."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.stored: dict[tuple[str, str], str] = {}
        self.deleted: list[tuple[str, str]] = []
        self.unavailable = None
        self._fail = fail

    def get(self, service, username):
        return self.stored.get((service, username))

    def set(self, service, username, password):
        if self._fail is not None:
            self.unavailable = self._fail
            return False
        self.stored[(service, username)] = password
        return True

    def delete(self, service, username):
        self.deleted.append((service, username))
        self.stored.pop((service, username), None)


class StoreTestCase(unittest.TestCase):
    """Builds isolated stores."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="gws_config_")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def make_config(self, name: str | None = None):
        """Return a config manager writing into this test's directory."""
        name = name or f"webapisync_test_{next(_counter)}"
        return configman.register_manager(
            name, self.tmpdir, use_plugins_path=False
        )

    def make_store(self, config=None, keyring=None) -> ConfigCredentialStore:
        """Return a store over an isolated config manager."""
        return ConfigCredentialStore(
            keyring=cast(Keyring, keyring or FakeKeyring()),
            config=config or self.make_config(),
        )


class NormalizeUrlTest(unittest.TestCase):
    """The key has to survive the ways people type a URL."""

    def test_trailing_slash_and_whitespace_are_ignored(self) -> None:
        """These used to look like different servers and cost the baseline."""
        self.assertEqual(normalize_url(" https://x.org/ "), "https://x.org")
        self.assertEqual(normalize_url("https://x.org///"), "https://x.org")


class PerServerBaselineTest(StoreTestCase):
    """Each server keeps its own last-sync time."""

    def test_two_servers_do_not_share_a_baseline(self) -> None:
        store = self.make_store()
        store.set_timestamp(URL, "owner", 111.0)
        store.set_timestamp(OTHER, "owner", 222.0)
        self.assertEqual(store.get_timestamp(URL, "owner"), 111.0)
        self.assertEqual(store.get_timestamp(OTHER, "owner"), 222.0)

    def test_same_server_different_users_are_separate_trees(self) -> None:
        """A Gramps Web account maps to one tree, so the user is part of the key."""
        store = self.make_store()
        store.set_timestamp(URL, "alice", 111.0)
        store.set_timestamp(URL, "bob", 222.0)
        self.assertEqual(store.get_timestamp(URL, "alice"), 111.0)

    def test_a_trailing_slash_does_not_lose_the_baseline(self) -> None:
        store = self.make_store()
        store.set_timestamp(URL, "owner", 111.0)
        self.assertEqual(store.get_timestamp(URL + "/", "owner"), 111.0)

    def test_an_unknown_server_has_no_baseline(self) -> None:
        store = self.make_store()
        self.assertEqual(store.get_timestamp("https://new.example", "owner"), 0.0)


class MigrationTest(StoreTestCase):
    """Upgrading from the pre-multi-server layout must lose nothing."""

    def test_legacy_keys_become_an_entry(self) -> None:
        config = self.make_config()
        config.register(LEGACY_URL, "")
        config.register(LEGACY_USERNAME, "")
        config.register(LEGACY_TIMESTAMP, 0)
        config.set(LEGACY_URL, URL)
        config.set(LEGACY_USERNAME, "owner")
        config.set(LEGACY_TIMESTAMP, 999)

        store = self.make_store(config=config)

        self.assertEqual(store.get_url(), URL)
        self.assertEqual(store.get_username(), "owner")
        self.assertEqual(store.get_timestamp(URL, "owner"), 999.0)

    def test_migration_preserves_the_baseline(self) -> None:
        """Losing it would make the first run after upgrading a cold sync."""
        config = self.make_config()
        for key, value in (
            (LEGACY_URL, URL),
            (LEGACY_USERNAME, "owner"),
            (LEGACY_TIMESTAMP, 4242),
        ):
            config.register(key, "" if isinstance(value, str) else 0)
            config.set(key, value)
        store = self.make_store(config=config)
        self.assertNotEqual(store.get_timestamp(URL, "owner"), 0.0)

    def test_nothing_stored_migrates_to_nothing(self) -> None:
        store = self.make_store()
        self.assertEqual(store.get_url(), "")
        self.assertEqual(store.get_username(), "")


class LegacyMirrorTest(StoreTestCase):
    """The old keys stay current so a downgrade still works."""

    def test_saving_mirrors_into_the_legacy_keys(self) -> None:
        config = self.make_config()
        store = self.make_store(config=config)
        store.save_credentials(URL, "owner", "secret")
        store.set_timestamp(URL, "owner", 777.0)

        self.assertEqual(config.get(LEGACY_URL), URL)
        self.assertEqual(config.get(LEGACY_USERNAME), "owner")
        self.assertEqual(config.get(LEGACY_TIMESTAMP), 777)

    def test_a_newer_legacy_baseline_wins_on_re_upgrade(self) -> None:
        """An older version may have synced while it was installed."""
        config = self.make_config()
        store = self.make_store(config=config)
        store.set_timestamp(URL, "owner", 100.0)
        # Stand in for an older version syncing and writing only its own keys.
        config.set(LEGACY_TIMESTAMP, 500)
        config.save()

        reopened = self.make_store(config=config)

        self.assertEqual(reopened.get_timestamp(URL, "owner"), 500.0)

    def test_an_older_legacy_baseline_does_not_regress_the_entry(self) -> None:
        config = self.make_config()
        store = self.make_store(config=config)
        store.set_timestamp(URL, "owner", 500.0)
        config.set(LEGACY_TIMESTAMP, 100)
        config.save()

        reopened = self.make_store(config=config)

        self.assertEqual(reopened.get_timestamp(URL, "owner"), 500.0)

    def test_an_unreadable_server_list_is_treated_as_empty(self) -> None:
        """A value the config manager could not parse is stored as None.

        Registering a default does not help: defaults apply only when a key is
        absent, not when it is present and None, so the store has to check the
        type rather than assume it. Written to the file directly because
        ``set`` type-checks and would reject it.
        """
        config = self.make_config()
        with open(config.filename, "w", encoding="utf-8") as fobj:
            fobj.write("[credentials]\nservers=<<<not python\n")

        store = self.make_store(config=config)

        self.assertEqual(store.get_url(), "")
        self.assertEqual(store.get_timestamp(URL, "owner"), 0.0)


class RememberPasswordTest(StoreTestCase):
    """The password, and only the password, is optional."""

    def test_the_password_is_stored_when_remembered(self) -> None:
        keyring = FakeKeyring()
        store = self.make_store(keyring=keyring)
        store.save_credentials(URL, "owner", "secret", remember_password=True)
        self.assertEqual(keyring.stored[(URL, "owner")], "secret")

    def test_declining_deletes_rather_than_merely_skipping(self) -> None:
        """Otherwise the setting appears inert for anyone who had it on."""
        keyring = FakeKeyring()
        store = self.make_store(keyring=keyring)
        store.save_credentials(URL, "owner", "secret", remember_password=True)

        store.save_credentials(URL, "owner", "secret", remember_password=False)

        self.assertNotIn((URL, "owner"), keyring.stored)
        self.assertIn((URL, "owner"), keyring.deleted)

    def test_the_entry_survives_even_when_the_password_does_not(self) -> None:
        """The baseline is not a credential; dropping it would force cold syncs."""
        store = self.make_store()
        store.set_timestamp(URL, "owner", 321.0)
        store.save_credentials(URL, "owner", "secret", remember_password=False)
        self.assertEqual(store.get_timestamp(URL, "owner"), 321.0)

    def test_an_unremembered_password_is_not_returned(self) -> None:
        store = self.make_store()
        store.save_credentials(URL, "owner", "secret", remember_password=False)
        self.assertIsNone(store.get_password())


class ForgetTest(StoreTestCase):
    """Forgetting is the wider case of the same delete."""

    def test_forget_removes_entry_keyring_and_mirror(self) -> None:
        config = self.make_config()
        keyring = FakeKeyring()
        store = self.make_store(config=config, keyring=keyring)
        store.save_credentials(URL, "owner", "secret")

        store.forget(URL, "owner")

        self.assertEqual(store.get_url(), "")
        self.assertEqual(store.get_timestamp(URL, "owner"), 0.0)
        self.assertIn((URL, "owner"), keyring.deleted)
        self.assertEqual(config.get(LEGACY_URL), "")

    def test_forget_leaves_other_servers_alone(self) -> None:
        store = self.make_store()
        store.set_timestamp(URL, "owner", 111.0)
        store.set_timestamp(OTHER, "owner", 222.0)

        store.forget(URL, "owner")

        self.assertEqual(store.get_timestamp(OTHER, "owner"), 222.0)


class ExplodingBackend:
    """A keyring backend that raises, as one does under snap confinement."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list[str] = []

    def get_password(self, *_args):
        self.calls.append("get")
        raise self.exc

    def set_password(self, *_args):
        self.calls.append("set")
        raise self.exc

    def delete_password(self, *_args):
        self.calls.append("delete")
        raise self.exc


class KeyringOverBackend(Keyring):
    """The real guard logic over a backend the test controls."""

    def __init__(self, backend: ExplodingBackend) -> None:
        super().__init__()
        self.backend = backend

    def _module(self):
        return None if self.unavailable is not None else self.backend


class KeyringGuardTest(unittest.TestCase):
    """A broken keyring must not take Gramps down with it."""

    def test_a_backend_raising_is_reported_not_propagated(self) -> None:
        """Under snap confinement this arrives as a jeepney DBusErrorResponse.

        That does not derive from ``keyring.errors``, because it comes from a
        transitive dependency of the backend, so guarding on the keyring
        package's own exception hierarchy would not catch it.
        """

        class DBusErrorResponse(Exception):
            pass

        keyring = KeyringOverBackend(
            ExplodingBackend(DBusErrorResponse("An AppArmor policy prevents..."))
        )

        self.assertIsNone(keyring.get("svc", "user"))
        problem = keyring.unavailable
        self.assertIsNotNone(problem)
        assert problem is not None  # for the type checker
        self.assertIn("AppArmor", problem.detail)

    def test_a_write_failure_is_reported_as_not_stored(self) -> None:
        keyring = KeyringOverBackend(ExplodingBackend(RuntimeError("denied")))
        self.assertFalse(keyring.set("svc", "user", "pw"))
        self.assertIsNotNone(keyring.unavailable)

    def test_a_failure_stops_further_attempts(self) -> None:
        """One denial is enough; retrying each call just repeats the stall."""
        backend = ExplodingBackend(RuntimeError("denied"))
        keyring = KeyringOverBackend(backend)

        keyring.set("svc", "user", "pw")
        keyring.set("svc", "user", "pw")
        keyring.get("svc", "user")

        self.assertEqual(backend.calls, ["set"])

    def test_deleting_a_missing_entry_is_not_a_failure(self) -> None:
        """Backends raise when asked to delete something that is not there.

        A working keyring still reads cleanly, which is how that is told apart
        from a keyring that cannot delete because it is broken.
        """

        class AbsentEntryBackend(ExplodingBackend):
            def get_password(self, *_args):
                return None

        keyring = KeyringOverBackend(AbsentEntryBackend(RuntimeError("no such item")))
        self.assertTrue(keyring.delete("svc", "nobody"))
        self.assertIsNone(keyring.unavailable)

    def test_a_delete_that_leaves_the_password_behind_is_a_failure(self) -> None:
        """Otherwise turning off "remember password" silently does nothing."""

        class StubbornBackend(ExplodingBackend):
            def get_password(self, *_args):
                return "still here"

        keyring = KeyringOverBackend(StubbornBackend(RuntimeError("denied")))
        self.assertFalse(keyring.delete("svc", "user"))
        self.assertIsNotNone(keyring.unavailable)


class SnapHintTest(unittest.TestCase):
    """Under snap the failure is a setting the user can change."""

    def test_no_command_outside_snap(self) -> None:
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(snap_connect_command())

    def test_the_instance_name_is_used_when_present(self) -> None:
        """A parallel install is named gramps_foo, and the command must match."""
        env = {"SNAP": "/snap/gramps/11", "SNAP_INSTANCE_NAME": "gramps_beta"}
        with unittest.mock.patch.dict("os.environ", env, clear=True):
            command = snap_connect_command() or ""
            self.assertIn("gramps_beta:password-manager-service", command)

    def test_it_falls_back_to_the_snap_name(self) -> None:
        env = {"SNAP": "/snap/gramps/11", "SNAP_NAME": "gramps"}
        with unittest.mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                snap_connect_command(), "snap connect gramps:password-manager-service"
            )


if __name__ == "__main__":
    unittest.main()
