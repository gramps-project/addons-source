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

import unittest
from typing import Callable
from unittest.mock import Mock

from name_processor.repositories.entity_cache import EntityCache
from name_processor.repositories.caching_read import CachingReadRepository
from name_processor.repositories.invalidation import InvalidationSignalManager


class TestCachingIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_db = Mock()
        self.connected_signals: dict[str, Callable[..., None]] = {}

        def mock_connect(signal_name: str, handler: Callable[..., None]) -> int:
            self.connected_signals[signal_name] = handler
            return len(self.connected_signals)

        self.mock_db.connect.side_effect = mock_connect

        # Create real instances of repositories and managers
        self.cache = EntityCache()
        self.read_repo = CachingReadRepository(self.mock_db, self.cache)
        self.signal_manager = InvalidationSignalManager(self.mock_db, self.cache)

    def test_cache_miss_then_invalidate_then_refetch(self) -> None:
        """Full lifecycle: miss → cache → invalidate → re-miss → re-cache."""
        mock_p1 = Mock()
        mock_p2 = Mock()
        self.mock_db.get_person_from_handle.side_effect = [mock_p1, mock_p2]

        # Miss & Cache
        p_first = self.read_repo.get_person("handle1")
        self.assertIsNotNone(p_first)
        assert p_first is not None
        self.assertEqual(p_first._person, mock_p1)  # Proxy wraps raw object

        # Hit (no side_effect consumed)
        p_second = self.read_repo.get_person("handle1")
        self.assertIsNotNone(p_second)
        assert p_second is not None
        self.assertEqual(p_second._person, mock_p1)

        # Invalidate via signal callback
        self.connected_signals["person-update"](["handle1"])

        # Re-miss & Cache again (should fetch second side_effect)
        p_third = self.read_repo.get_person("handle1")
        self.assertIsNotNone(p_third)
        assert p_third is not None
        self.assertEqual(p_third._person, mock_p2)

    def test_relationship_traversal_with_cache(self) -> None:
        """get_father_handle populates person + family caches; second call is pure cache."""
        mock_person = Mock()
        mock_person.get_parent_family_handle_list.return_value = ["fam1"]
        mock_family = Mock()
        mock_family.get_father_handle.return_value = "father1"

        self.mock_db.get_person_from_handle.side_effect = [mock_person, None]
        self.mock_db.get_family_from_handle.side_effect = [mock_family, None]

        # Traversal 1
        father_h = self.read_repo.get_father_handle("child1")
        self.assertEqual(father_h, "father1")

        # Verify cached
        self.assertEqual(self.cache.person_count, 1)
        self.assertEqual(self.cache.family_count, 1)

        # Traversal 2 (should hit cache - no side_effect consumed, which would otherwise return None)
        father_h_cached = self.read_repo.get_father_handle("child1")
        self.assertEqual(father_h_cached, "father1")

    def test_write_then_signal_then_read_gets_fresh_data(self) -> None:
        """Simulate write → signal → verify fresh read."""
        mock_p_old = Mock()
        mock_p_new = Mock()
        self.mock_db.get_person_from_handle.side_effect = [mock_p_old, mock_p_new]

        # Populate cache
        self.read_repo.get_person("handle1")

        # Trigger update signal callback (representing write-around invalidation)
        self.connected_signals["person-update"](["handle1"])

        # Next read should be fresh
        p_fresh = self.read_repo.get_person("handle1")
        self.assertIsNotNone(p_fresh)
        assert p_fresh is not None
        self.assertEqual(p_fresh._person, mock_p_new)

    def test_cache_survives_none_database_return(self) -> None:
        """DB returns None → not cached → second call returns None with DB hit."""
        mock_p1 = Mock()
        self.mock_db.get_person_from_handle.side_effect = [None, mock_p1]

        # First call (misses, gets None)
        res1 = self.read_repo.get_person("handle1")
        self.assertIsNone(res1)

        # Second call (misses again, hits DB)
        res2 = self.read_repo.get_person("handle1")
        self.assertIsNotNone(res2)
        assert res2 is not None
        self.assertEqual(res2._person, mock_p1)

    def test_clear_persons_does_not_affect_families(self) -> None:
        """Type isolation verified on rebuild signal."""
        mock_person = Mock()
        mock_family = Mock()
        self.mock_db.get_person_from_handle.return_value = mock_person
        self.mock_db.get_family_from_handle.return_value = mock_family

        self.read_repo.get_person("p1")
        self.read_repo.get_family("f1")

        # Trigger person rebuild
        self.connected_signals["person-rebuild"]()

        self.assertEqual(self.cache.person_count, 0)
        self.assertEqual(self.cache.family_count, 1)


if __name__ == "__main__":
    unittest.main()
