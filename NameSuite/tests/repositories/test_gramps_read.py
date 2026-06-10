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
        self.assertIsNone(self.read_repo.get_person_proxy("bad_handle"))

    @patch("name_processor.repositories.gramps_read.GrampsPersonProxy")
    def test_get_person_proxy_success(self, mock_proxy_class):
        mock_person = Mock()
        self.mock_db.get_person_from_handle.return_value = mock_person

        result = self.read_repo.get_person_proxy("h123")

        mock_proxy_class.assert_called_once_with(mock_person, self.mock_db)
        self.assertEqual(result, mock_proxy_class.return_value)

    @patch("name_processor.repositories.gramps_read.GrampsPersonProxy")
    def test_get_chronology_subject_success(self, mock_proxy_class):
        mock_person = Mock()
        self.mock_db.get_person_from_handle.return_value = mock_person

        result = self.read_repo.get_chronology_subject("h123")
        self.assertEqual(result, mock_proxy_class.return_value)

    def test_get_database_median_year_chunked_empty(self):
        self.mock_db.get_event_handles.return_value = []

        generator = self.read_repo.get_database_median_year_chunked()

        # An empty database yields nothing; the return value should be None.
        result = _exhaust_generator(generator)
        self.assertIsNone(result)

    def test_get_database_median_year_chunked(self):
        # Create 5 mock events
        self.mock_db.get_event_handles.return_value = ["e1", "e2", "e3", "e4", "e5"]

        def create_mock_event(year):
            event = Mock()
            date_obj = Mock()
            date_obj.is_empty.return_value = False
            date_obj.get_year.return_value = year
            event.get_date_object.return_value = date_obj
            return event

        # Unsorted years: 1910, 1950, 1890, 1900, 1920
        # Sorted: 1890, 1900, 1910, 1920, 1950 -> Median: 1910
        self.mock_db.get_event_from_handle.side_effect = [
            create_mock_event(1910),
            create_mock_event(1950),
            create_mock_event(1890),
            create_mock_event(1900),
            create_mock_event(1920),
        ]

        generator = self.read_repo.get_database_median_year_chunked(chunk_size=2)

        # Chunk 1 (e1, e2)
        self.assertIsNone(next(generator))
        # Chunk 2 (e3, e4)
        self.assertIsNone(next(generator))
        # Chunk 3 (e5)
        self.assertIsNone(next(generator))

        # Completion — generator return value carries the median year
        result = _exhaust_generator(generator)
        self.assertEqual(result, 1910)


if __name__ == "__main__":
    unittest.main()
