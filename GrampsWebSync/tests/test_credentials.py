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
import os
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
        """Return a config manager writing into this test's directory.

        The override has to name the ``.ini`` file. Given a bare directory,
        Gramps splits it and keeps only the parent, so every test would share
        one file in the system temporary directory and inherit whatever a
        previous run left in it.
        """
        name = name or f"webapisync_test_{next(_counter)}"
        return configman.register_manager(
            name, os.path.join(self.tmpdir, f"{name}.ini"), use_plugins_path=False
        )

    def make_store(
        self, config=None, keyring=None, tree_id: str = ""
    ) -> ConfigCredentialStore:
        """Return a store over an isolated config manager."""
        return ConfigCredentialStore(
            keyring=cast(Keyring, keyring or FakeKeyring()),
            config=config or self.make_config(),
            tree_id=tree_id,
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


class RememberPasswordChoiceTest(StoreTestCase):
    """The stored choice comes back, so the checkbox can show it."""

    def test_a_server_never_seen_before_defaults_to_remembering(self) -> None:
        """Which is what the tool did unconditionally before there was a box."""
        self.assertTrue(self.make_store().get_remember_password())

    def test_declining_is_remembered(self) -> None:
        store = self.make_store()
        store.save_credentials(URL, "owner", "secret", remember_password=False)
        self.assertFalse(store.get_remember_password())

    def test_accepting_is_remembered(self) -> None:
        store = self.make_store()
        store.save_credentials(URL, "owner", "secret", remember_password=True)
        self.assertTrue(store.get_remember_password())

    def test_it_survives_being_reopened(self) -> None:
        config = self.make_config()
        first = self.make_store(config=config)
        first.save_credentials(URL, "owner", "secret", remember_password=False)

        self.assertFalse(self.make_store(config=config).get_remember_password())

    def test_the_choice_is_per_server(self) -> None:
        config = self.make_config()
        store = self.make_store(config=config)
        store.save_credentials(URL, "owner", "secret", remember_password=False)
        store.save_credentials(OTHER, "owner", "secret", remember_password=True)

        self.assertTrue(self.make_store(config=config).get_remember_password())


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


class OpenTreeTest(StoreTestCase):
    """Entries record the local tree they were synced from.

    Nothing else ties a server to a family tree, and syncing a tree against a
    server holding a different one classifies every object as deleted on the
    far side, so a bidirectional run proposes emptying both.
    """

    def synced(self, config, tree_id: str, url: str, username: str) -> None:
        """Drive one complete sync of ``tree_id`` against ``url``."""
        store = self.make_store(config=config, tree_id=tree_id)
        store.save_credentials(url, username, "pw")
        store.set_timestamp(url, username, 100.0)

    def test_a_completed_sync_records_the_open_tree(self) -> None:
        store = self.make_store(config=self.make_config(), tree_id="tree-a")
        store.save_credentials(URL, "owner", "pw")
        store.set_timestamp(URL, "owner", 100.0)

        self.assertTrue(store.is_for_open_tree())
        self.assertFalse(store.is_from_another_tree())

    def test_merely_connecting_claims_nothing(self) -> None:
        """Backing out at the review pane must leave no association behind.

        Authenticating against the wrong server is an easy mistake and its own
        review pane is where it gets noticed. Claiming the tree at that point
        would go on connecting there unprompted, with no warning, because the
        entry would say it *is* this tree.
        """
        config = self.make_config()
        self.make_store(config=config, tree_id="my-tree").save_credentials(
            OTHER, "someone", "pw"
        )

        reopened = self.make_store(config=config, tree_id="my-tree")

        self.assertFalse(reopened.is_for_open_tree())

    def test_the_wrong_server_is_still_offered_for_correcting(self) -> None:
        """Refusing to connect unprompted must not also empty the pane."""
        config = self.make_config()
        self.make_store(config=config, tree_id="my-tree").save_credentials(
            OTHER, "someone", "pw"
        )

        reopened = self.make_store(config=config, tree_id="my-tree")

        self.assertEqual(reopened.get_url(), OTHER)

    def test_moving_a_tree_to_another_server_drops_the_old_claim(self) -> None:
        """Otherwise both entries claim the tree and which one wins depends on
        the order they happen to sit in."""
        config = self.make_config()
        first = self.make_store(config=config, tree_id="tree-a")
        first.save_credentials(URL, "owner", "pw")
        first.set_timestamp(URL, "owner", 100.0)

        moved = self.make_store(config=config, tree_id="tree-a")
        moved.save_credentials(OTHER, "owner", "pw")
        moved.set_timestamp(OTHER, "owner", 200.0)

        claims = [
            entry["url"]
            for entry in config.get("credentials.servers")
            if entry.get("tree_id") == "tree-a"
        ]
        self.assertEqual(claims, [OTHER])

    def test_another_tree_may_not_be_connected_to_unprompted(self) -> None:
        config = self.make_config()
        self.synced(config, "tree-a", URL, "owner")

        reopened = self.make_store(config=config, tree_id="tree-b")

        self.assertFalse(reopened.is_for_open_tree())
        self.assertTrue(reopened.is_from_another_tree())

    def test_another_tree_still_gets_its_fields_pre_filled(self) -> None:
        """Withholding the automatic connect must not also empty the pane."""
        config = self.make_config()
        self.synced(config, "tree-a", URL, "owner")

        reopened = self.make_store(config=config, tree_id="tree-b")

        self.assertEqual(reopened.get_url(), URL)
        self.assertEqual(reopened.get_username(), "owner")

    def test_each_tree_is_offered_its_own_server(self) -> None:
        """Once both are recorded, opening either finds the right one."""
        config = self.make_config()
        self.synced(config, "tree-a", URL, "owner")
        self.synced(config, "tree-b", OTHER, "other")

        back_to_a = self.make_store(config=config, tree_id="tree-a")

        self.assertEqual(back_to_a.get_url(), URL)
        self.assertTrue(back_to_a.is_for_open_tree())

    def test_the_tree_beats_the_last_used_entry(self) -> None:
        """Otherwise reopening a tree would offer whichever server was touched
        most recently, which is the hazard being fixed."""
        config = self.make_config()
        self.synced(config, "tree-a", URL, "owner")
        self.synced(config, "tree-b", OTHER, "other")

        back_to_a = self.make_store(config=config, tree_id="tree-a")

        self.assertEqual(back_to_a.get_url(), URL)


class MultiTreeServerTest(StoreTestCase):
    """One server hosting several trees, with one account per tree.

    The shape of a hosted Gramps Web deployment: the URL is shared, and only
    the account distinguishes one tree from another. Entries are keyed by both,
    so nothing here may fall together.
    """

    def setUp(self) -> None:
        super().setUp()
        self.config = self.make_config()
        self.keyring = FakeKeyring()
        for tree, user, baseline in (
            ("tree-a", "alice", 1000.0),
            ("tree-b", "bob", 2000.0),
        ):
            store = self.store_for(tree)
            store.save_credentials(URL, user, f"pw-{user}")
            store.set_timestamp(URL, user, baseline)

    def store_for(self, tree_id: str) -> ConfigCredentialStore:
        """Return a store as it would be built with ``tree_id`` open."""
        return self.make_store(
            config=self.config, keyring=self.keyring, tree_id=tree_id
        )

    def test_each_tree_is_offered_its_own_account(self) -> None:
        self.assertEqual(self.store_for("tree-a").get_username(), "alice")
        self.assertEqual(self.store_for("tree-b").get_username(), "bob")

    def test_both_may_connect_unprompted(self) -> None:
        self.assertTrue(self.store_for("tree-a").is_for_open_tree())
        self.assertTrue(self.store_for("tree-b").is_for_open_tree())

    def test_the_tree_wins_over_whichever_was_used_last(self) -> None:
        """``tree-b`` synced most recently, so a last-used fallback would
        hand ``tree-a`` the wrong account."""
        self.assertEqual(self.store_for("tree-a").get_username(), "alice")

    def test_each_account_keeps_its_own_baseline(self) -> None:
        self.assertEqual(self.store_for("tree-a").get_timestamp(URL, "alice"), 1000.0)
        self.assertEqual(self.store_for("tree-b").get_timestamp(URL, "bob"), 2000.0)

    def test_passwords_do_not_collide_in_the_keyring(self) -> None:
        """The keyring is keyed by service and user, and the service is the
        shared URL, so the account has to be what separates them."""
        self.assertEqual(self.store_for("tree-a").get_password(), "pw-alice")
        self.assertEqual(self.store_for("tree-b").get_password(), "pw-bob")

    def test_a_third_tree_is_pre_filled_but_not_connected_to(self) -> None:
        """Opening an unsynced tree must not sync it against someone else's."""
        store = self.store_for("tree-c")
        self.assertFalse(store.is_for_open_tree())
        self.assertTrue(store.is_from_another_tree())
        self.assertEqual(store.get_url(), URL)


class ForgetClearsAssociationTest(StoreTestCase):
    """Forgetting a server also gives up the tree it had claimed."""

    def synced(self, config, tree_id: str, url: str, username: str, keyring=None):
        """Drive one complete sync of ``tree_id`` against ``url``."""
        store = self.make_store(config=config, keyring=keyring, tree_id=tree_id)
        store.save_credentials(url, username, "pw")
        store.set_timestamp(url, username, 100.0)
        return store

    def test_the_entry_and_its_claim_are_both_gone(self) -> None:
        config = self.make_config()
        store = self.synced(config, "tree-a", URL, "owner")

        store.forget(URL, "owner")

        self.assertEqual(config.get("credentials.servers"), [])
        self.assertFalse(store.is_for_open_tree())

    def test_the_password_goes_too(self) -> None:
        """Leaving it behind would be the setting appearing to do nothing."""
        config = self.make_config()
        keyring = FakeKeyring()
        store = self.synced(config, "tree-a", URL, "owner", keyring=keyring)

        store.forget(URL, "owner")

        self.assertIn((URL, "owner"), keyring.deleted)

    def test_the_baseline_goes_with_it(self) -> None:
        """Which is why forgetting is worth confirming: the next run compares
        the two trees from scratch."""
        config = self.make_config()
        store = self.synced(config, "tree-a", URL, "owner")

        store.forget(URL, "owner")

        self.assertEqual(store.get_timestamp(URL, "owner"), 0.0)

    def test_another_tree_keeps_its_own_server(self) -> None:
        config = self.make_config()
        self.synced(config, "tree-a", URL, "alice")
        self.synced(config, "tree-b", OTHER, "bob")

        self.make_store(config=config, tree_id="tree-a").forget(URL, "alice")

        still_there = self.make_store(config=config, tree_id="tree-b")
        self.assertTrue(still_there.is_for_open_tree())
        self.assertEqual(still_there.get_url(), OTHER)


class MovedServerTest(StoreTestCase):
    """A tree that moves to another deployment leaves the old one behind."""

    def move(self, config, url: str, username: str, timestamp: float):
        """Sync ``tree-a`` against ``url``."""
        store = self.make_store(config=config, tree_id="tree-a")
        store.save_credentials(url, username, "pw")
        store.set_timestamp(url, username, timestamp)
        return store

    def test_the_new_server_is_the_one_offered(self) -> None:
        config = self.make_config()
        self.move(config, URL, "owner", 100.0)

        moved = self.move(config, OTHER, "owner", 200.0)

        self.assertEqual(moved.get_url(), OTHER)
        self.assertTrue(moved.is_for_open_tree())

    def test_the_old_server_loses_its_baseline(self) -> None:
        """It asserted the tree and that server were identical at a moment
        which syncing elsewhere has since made untrue. The comparison takes the
        later of the stored baseline and what it computes, so keeping a stale
        one can only push the cutoff too far forward -- and too far forward is
        where objects stop looking added and start looking deleted.
        """
        config = self.make_config()
        self.move(config, URL, "owner", 100.0)

        self.move(config, OTHER, "owner", 200.0)

        self.assertEqual(
            self.make_store(config=config).get_timestamp(URL, "owner"), 0.0
        )

    def test_the_old_entry_itself_survives(self) -> None:
        """Only the claim and the baseline go; the address and user name are
        still worth offering if the user goes back."""
        config = self.make_config()
        self.move(config, URL, "owner", 100.0)

        self.move(config, OTHER, "owner", 200.0)

        urls = [entry["url"] for entry in config.get("credentials.servers")]
        self.assertIn(URL, urls)


class UpgradedEntryTest(StoreTestCase):
    """An entry stored before tree ids existed must keep working."""

    def make_pre_upgrade_entry(self, config) -> None:
        """Store an entry the way the previous version did, with no tree id."""
        store = self.make_store(config=config)
        store.save_credentials(URL, "owner", "pw")
        store.set_timestamp(URL, "owner", 1234.0)

    def test_it_is_still_offered(self) -> None:
        config = self.make_config()
        self.make_pre_upgrade_entry(config)

        store = self.make_store(config=config, tree_id="tree-a")

        self.assertEqual(store.get_url(), URL)
        self.assertEqual(store.get_username(), "owner")

    def test_its_baseline_survives(self) -> None:
        """Losing it would turn the next run into a full cold resync."""
        config = self.make_config()
        self.make_pre_upgrade_entry(config)

        store = self.make_store(config=config, tree_id="tree-a")

        self.assertEqual(store.get_timestamp(URL, "owner"), 1234.0)

    def test_it_does_not_connect_unprompted_until_it_has_synced_once(self) -> None:
        """No tree was recorded, so which one it belongs to is simply unknown."""
        config = self.make_config()
        self.make_pre_upgrade_entry(config)

        store = self.make_store(config=config, tree_id="tree-a")

        self.assertFalse(store.is_for_open_tree())

    def test_nor_is_it_reported_as_belonging_elsewhere(self) -> None:
        """An unknown tree is not a different tree; warning would be a guess."""
        config = self.make_config()
        self.make_pre_upgrade_entry(config)

        store = self.make_store(config=config, tree_id="tree-a")

        self.assertFalse(store.is_from_another_tree())

    def test_the_first_completed_sync_adopts_the_tree(self) -> None:
        config = self.make_config()
        self.make_pre_upgrade_entry(config)

        store = self.make_store(config=config, tree_id="tree-a")
        store.save_credentials(URL, "owner", "pw")
        store.set_timestamp(URL, "owner", 5678.0)

        self.assertTrue(store.is_for_open_tree())
        self.assertEqual(store.get_timestamp(URL, "owner"), 5678.0)

    def test_a_tool_that_cannot_identify_the_tree_never_auto_connects(self) -> None:
        """``get_dbid`` returning nothing must fail safe, not fail open."""
        config = self.make_config()
        store_a = self.make_store(config=config, tree_id="tree-a")
        store_a.save_credentials(URL, "owner", "pw")
        store_a.set_timestamp(URL, "owner", 100.0)

        store = self.make_store(config=config, tree_id="")

        self.assertFalse(store.is_for_open_tree())
        self.assertFalse(store.is_from_another_tree())
        self.assertEqual(store.get_url(), URL)


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
