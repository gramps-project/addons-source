#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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
#

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable
import unittest
from unittest.mock import Mock, call

from name_processor.repositories.entity_cache import EntityCache
from name_processor.repositories.invalidation import InvalidationSignalManager


class TestInvalidationSignalManager(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_db = Mock()
        self.cache = EntityCache()
        # Mock connect to return sequential integers as keys
        self.connected_signals: dict[str, Callable[..., None]] = {}
        self.next_key = 100

        def mock_connect(signal_name: str, handler: Callable[..., None]) -> int:
            self.connected_signals[signal_name] = handler
            key = self.next_key
            self.next_key += 1
            return key

        self.mock_db.connect.side_effect = mock_connect
        self.manager = InvalidationSignalManager(self.mock_db, self.cache)

    def test_connect_registers_all_12_signals(self) -> None:
        """Verify db.connect called 12 times with correct signals."""
        self.assertEqual(self.mock_db.connect.call_count, 12)
        expected_signals = [
            "person-add",
            "person-update",
            "person-delete",
            "person-rebuild",
            "family-add",
            "family-update",
            "family-delete",
            "family-rebuild",
            "event-add",
            "event-update",
            "event-delete",
            "event-rebuild",
        ]
        for sig in expected_signals:
            self.assertIn(sig, self.connected_signals)

    def test_person_update_invalidates_handles(self) -> None:
        """Signal callback invalidates each handle in the list."""
        self.cache.put_person("p1", Mock())
        self.cache.put_person("p2", Mock())

        # Trigger person-update signal callback
        person_update_handler = self.connected_signals["person-update"]
        person_update_handler(["p1", "p2"])

        self.assertEqual(self.cache.person_count, 0)

    def test_person_rebuild_clears_all_persons(self) -> None:
        """Rebuild signal clears entire person cache."""
        self.cache.put_person("p1", Mock())
        self.cache.put_person("p2", Mock())

        person_rebuild_handler = self.connected_signals["person-rebuild"]
        person_rebuild_handler()

        self.assertEqual(self.cache.person_count, 0)

    def test_family_update_invalidates_handles(self) -> None:
        """Family signal invalidates family cache."""
        self.cache.put_family("f1", Mock())
        self.cache.put_family("f2", Mock())

        family_update_handler = self.connected_signals["family-update"]
        family_update_handler(["f1"])

        self.assertEqual(self.cache.family_count, 1)
        # Let's import _MISSING
        from name_processor.repositories.entity_cache import _MISSING

        self.assertIs(self.cache.get_family("f1"), _MISSING)

    def test_event_update_invalidates_handles(self) -> None:
        """Event signal invalidates event cache."""
        self.cache.put_event("e1", Mock())
        self.cache.put_event("e2", Mock())

        event_update_handler = self.connected_signals["event-update"]
        event_update_handler(["e1"])

        self.assertEqual(self.cache.event_count, 1)
        from name_processor.repositories.entity_cache import _MISSING

        self.assertIs(self.cache.get_event("e1"), _MISSING)

    def test_disconnect_all_unhooks_signals(self) -> None:
        """All signal keys disconnected."""
        keys_connected = self.manager._signal_keys.copy()
        self.assertEqual(len(keys_connected), 12)

        self.manager.disconnect_all()
        self.assertEqual(len(self.manager._signal_keys), 0)

        # Verify db.disconnect was called for each key
        expected_calls = [call(key) for key in keys_connected]
        self.mock_db.disconnect.assert_has_calls(expected_calls, any_order=True)

    def test_disconnect_all_is_idempotent(self) -> None:
        """Calling twice does not raise or call disconnect again."""
        self.manager.disconnect_all()
        self.mock_db.disconnect.reset_mock()

        self.manager.disconnect_all()
        self.mock_db.disconnect.assert_not_called()

    def test_person_delete_invalidates_handle(self) -> None:
        """Delete signal evicts handle."""
        self.cache.put_person("p1", Mock())
        person_delete_handler = self.connected_signals["person-delete"]
        person_delete_handler(["p1"])

        from name_processor.repositories.entity_cache import _MISSING

        self.assertIs(self.cache.get_person("p1"), _MISSING)

    def test_handles_empty_handle_list(self) -> None:
        """Signal with empty list is a no-op."""
        self.cache.put_person("p1", Mock())
        person_update_handler = self.connected_signals["person-update"]
        person_update_handler([])  # Empty list
        self.assertEqual(self.cache.person_count, 1)

    def test_handles_single_string_handle(self) -> None:
        """Defensive callback supports a single string handle instead of a list."""
        self.cache.put_person("p1", Mock())
        person_update_handler = self.connected_signals["person-update"]
        person_update_handler("p1")  # Single string
        from name_processor.repositories.entity_cache import _MISSING

        self.assertIs(self.cache.get_person("p1"), _MISSING)


if __name__ == "__main__":
    unittest.main()
