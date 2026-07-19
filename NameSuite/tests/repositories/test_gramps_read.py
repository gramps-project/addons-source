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
from unittest.mock import Mock, patch

from name_processor.repositories.gramps_read import GrampsReadRepository


def _exhaust_generator(gen):
    """Drive a generator to completion and return its return value.

    Generators communicate their final return value via StopIteration.value.
    This helper consumes all yielded values and captures that return value.
    """
    return_value = None
    try:
        while True:
            next(gen)
    except StopIteration as exc:
        return_value = exc.value
    return return_value


class TestGrampsReadRepository(unittest.TestCase):
    def setUp(self):
        self.mock_db = Mock()
        self.read_repo = GrampsReadRepository(self.mock_db)

    def test_get_person_proxy_returns_none(self):
        self.mock_db.get_person_from_handle.return_value = None
        self.assertIsNone(self.read_repo.get_person("bad_handle"))

    @patch("name_processor.repositories.gramps_read.GrampsPersonProxy")
    def test_get_person_proxy_success(self, mock_proxy_class):
        mock_person = Mock()
        self.mock_db.get_person_from_handle.return_value = mock_person

        result = self.read_repo.get_person("h123")

        mock_proxy_class.assert_called_once_with(mock_person)
        self.assertEqual(result, mock_proxy_class.return_value)

    def test_get_father_proxy_returns_proxy_when_father_exists(self):
        """Test that get_father returns a proxy when father exists."""
        person_handle = "person1"
        father_handle = "father1"
        mock_person = Mock()
        mock_father = Mock()

        self.mock_db.get_person_from_handle.side_effect = [mock_person, mock_father]
        mock_person.get_parent_family_handle_list.return_value = ["family1"]
        mock_family = Mock()
        mock_family.get_father_handle.return_value = father_handle
        self.mock_db.get_family_from_handle.return_value = mock_family

        with patch(
            "name_processor.repositories.gramps_read.GrampsPersonProxy"
        ) as mock_proxy_class:
            result = self.read_repo.get_father(person_handle)

            self.assertIsNotNone(result)
            mock_proxy_class.assert_called_once_with(mock_father)

    def test_get_father_proxy_returns_none_when_no_father(self):
        """Test that get_father returns None when person has no father."""
        person_handle = "person1"
        mock_person = Mock()

        self.mock_db.get_person_from_handle.return_value = mock_person
        mock_person.get_parent_family_handle_list.return_value = []

        result = self.read_repo.get_father(person_handle)

        self.assertIsNone(result)

    def test_get_father_proxy_returns_none_when_invalid_handle(self):
        """Test that get_father returns None when father handle is invalid."""
        person_handle = "person1"
        mock_person = Mock()

        self.mock_db.get_person_from_handle.side_effect = [mock_person, None]
        mock_person.get_parent_family_handle_list.return_value = ["family1"]
        mock_family = Mock()
        mock_family.get_father_handle.return_value = "invalid_father"
        self.mock_db.get_family_from_handle.return_value = mock_family

        result = self.read_repo.get_father(person_handle)

        self.assertIsNone(result)

    def test_get_siblings_proxies_returns_list_when_siblings_exist(self):
        """Test that get_siblings returns list of proxies when siblings exist."""
        person_handle = "person1"
        sibling1_handle = "sibling1"
        sibling2_handle = "sibling2"
        mock_person = Mock()
        mock_sibling1 = Mock()
        mock_sibling2 = Mock()

        self.mock_db.get_person_from_handle.side_effect = [
            mock_person,
            mock_sibling1,
            mock_sibling2,
        ]
        mock_person.get_parent_family_handle_list.return_value = ["family1"]
        mock_family = Mock()
        mock_child_ref1 = Mock()
        mock_child_ref1.ref = sibling1_handle
        mock_child_ref2 = Mock()
        mock_child_ref2.ref = sibling2_handle
        mock_family.get_child_ref_list.return_value = [
            mock_child_ref1,
            mock_child_ref2,
        ]
        self.mock_db.get_family_from_handle.return_value = mock_family

        with patch(
            "name_processor.repositories.gramps_read.GrampsPersonProxy"
        ) as mock_proxy_class:
            result = self.read_repo.get_siblings(person_handle)

            self.assertEqual(len(result), 2)
            self.assertEqual(mock_proxy_class.call_count, 2)

    def test_get_siblings_proxies_returns_empty_list_when_no_siblings(self):
        """Test that get_siblings returns empty list when no siblings."""
        person_handle = "person1"
        mock_person = Mock()

        self.mock_db.get_person_from_handle.return_value = mock_person
        mock_person.get_parent_family_handle_list.return_value = []

        result = self.read_repo.get_siblings(person_handle)

        self.assertEqual(result, [])

    def test_get_siblings_proxies_excludes_person_own_handle(self):
        """Test that get_siblings excludes the person's own handle."""
        person_handle = "person1"
        sibling_handle = "sibling1"
        mock_person = Mock()
        mock_sibling = Mock()

        self.mock_db.get_person_from_handle.side_effect = [mock_person, mock_sibling]
        mock_person.get_parent_family_handle_list.return_value = ["family1"]
        mock_family = Mock()
        mock_child_ref1 = Mock()
        mock_child_ref1.ref = person_handle  # Person's own handle
        mock_child_ref2 = Mock()
        mock_child_ref2.ref = sibling_handle  # Sibling's handle
        mock_family.get_child_ref_list.return_value = [
            mock_child_ref1,
            mock_child_ref2,
        ]
        self.mock_db.get_family_from_handle.return_value = mock_family

        with patch(
            "name_processor.repositories.gramps_read.GrampsPersonProxy"
        ) as mock_proxy_class:
            result = self.read_repo.get_siblings(person_handle)

            # Should only return the sibling, not the person themselves
            self.assertEqual(len(result), 1)
            mock_proxy_class.assert_called_once_with(mock_sibling)

    def test_is_protected_by_alias_returns_true_when_match(self):
        """Test that is_protected_by_alias returns True when string matches an alt name."""
        mock_person = Mock()
        mock_alt_name = Mock()
        mock_alt_name.get_first_name.return_value = "John Smith"
        mock_person.get_alternate_names.return_value = [mock_alt_name]

        result = self.read_repo.is_protected_by_alias(mock_person, "John")

        self.assertTrue(result)

    def test_is_protected_by_alias_returns_false_when_no_match(self):
        """Test that is_protected_by_alias returns False when string doesn't match."""
        mock_person = Mock()
        mock_alt_name = Mock()
        mock_alt_name.get_first_name.return_value = "Jane Doe"
        mock_person.get_alternate_names.return_value = [mock_alt_name]

        result = self.read_repo.is_protected_by_alias(mock_person, "John")

        self.assertFalse(result)

    def test_is_protected_by_alias_handles_empty_alt_name_list(self):
        """Test that is_protected_by_alias handles empty alt name list."""
        mock_person = Mock()
        mock_person.get_alternate_names.return_value = []

        result = self.read_repo.is_protected_by_alias(mock_person, "John")

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
