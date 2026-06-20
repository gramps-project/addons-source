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
from unittest.mock import MagicMock

from name_processor.services.chronology import ChronologyService
from name_processor.protocols.chronology import ChronologyRepository, ChronologySubject


class TestChronologyService(unittest.TestCase):
    def setUp(self):
        self.mock_repo = MagicMock(spec=ChronologyRepository)
        self.service = ChronologyService(self.mock_repo)

    def test_update_median_year_with_valid_years(self):
        """Test update_median_year calculates median correctly."""
        years = [1800, 1850, 1900, 1950, 2000]
        self.service.update_median_year(years)

        self.assertEqual(self.service._db_median_year, 1900)

    def test_update_median_year_with_even_number_of_years(self):
        """Test update_median_year with even number of years (upper median)."""
        years = [1800, 1850, 1900, 1950]
        self.service.update_median_year(years)

        # For even length, returns upper middle element (index 2)
        self.assertEqual(self.service._db_median_year, 1900)

    def test_update_median_year_with_unsorted_years(self):
        """Test update_median_year sorts years before calculating median."""
        years = [1950, 1800, 2000, 1850, 1900]
        self.service.update_median_year(years)

        self.assertEqual(self.service._db_median_year, 1900)

    def test_update_median_year_with_empty_list(self):
        """Test update_median_year resets to None for empty list."""
        self.service.update_median_year([])

        self.assertIsNone(self.service._db_median_year)

    def test_update_median_year_with_none(self):
        """Test update_median_year resets to None when years is None."""
        self.service.update_median_year(None)

        self.assertIsNone(self.service._db_median_year)

    def test_update_median_year_resets_previous_value(self):
        """Test update_median_year resets previous median before calculating new one."""
        # Set an initial median
        self.service._db_median_year = 1900

        # Update with new years
        years = [2000, 2010, 2020]
        self.service.update_median_year(years)

        self.assertEqual(self.service._db_median_year, 2010)

    def test_set_db_median_year(self):
        """Test set_db_median_year sets the median year directly."""
        self.service.set_db_median_year(1950)

        self.assertEqual(self.service._db_median_year, 1950)

    def test_estimate_reference_year_with_direct_events(self):
        """Test estimate_reference_year returns direct event year when available."""
        mock_person = MagicMock(spec=ChronologySubject)
        mock_person.handle = "person1"

        self.mock_repo.get_person.return_value = mock_person
        self.mock_repo.get_event_years.return_value = [1900, 1905, 1910]

        result = self.service.estimate_reference_year("person1")

        self.assertEqual(result, 1910)  # Latest event year

    def test_estimate_reference_year_with_no_person(self):
        """Test estimate_reference_year returns None when person not found."""
        self.mock_repo.get_person.return_value = None

        result = self.service.estimate_reference_year("person1")

        self.assertIsNone(result)

    def test_estimate_reference_year_fallback_to_db_median(self):
        """Test estimate_reference_year falls back to database median."""
        mock_person = MagicMock(spec=ChronologySubject)
        mock_person.handle = "person1"

        self.mock_repo.get_person.return_value = mock_person
        self.mock_repo.get_event_years.return_value = []  # No direct events

        # Set database median
        self.service.set_db_median_year(1900)

        result = self.service.estimate_reference_year("person1")

        self.assertEqual(result, 1900)

    def test_generate_years_with_default_chunk_size(self):
        """Test generate_years collects years and yields periodically."""
        # Mock iter_all_events_years to return years
        self.mock_repo.iter_all_events_years.return_value = iter(
            [1800, 1850, 1900, 1950, 2000]
        )

        generator = self.service.generate_years()

        # Consume generator
        yields = []
        result = None
        try:
            while True:
                next(generator)
                yields.append(None)
        except StopIteration as e:
            result = e.value

        # With 5 years and default chunk_size=100, should not yield
        self.assertEqual(len(yields), 0)
        self.assertEqual(result, [1800, 1850, 1900, 1950, 2000])

    def test_generate_years_with_custom_chunk_size(self):
        """Test generate_years respects custom chunk_size."""
        # Mock iter_all_events_years to return 250 years
        years = list(range(1800, 2050))
        self.mock_repo.iter_all_events_years.return_value = iter(years)

        generator = self.service.generate_years(chunk_size=100)

        # Consume generator
        yields = []
        result = None
        try:
            while True:
                next(generator)
                yields.append(None)
        except StopIteration as e:
            result = e.value

        # With 250 years and chunk_size=100, should yield twice (at 100 and 200)
        self.assertEqual(len(yields), 2)
        self.assertEqual(result, years)

    def test_generate_years_with_empty_repository(self):
        """Test generate_years returns empty list when no years available."""
        self.mock_repo.iter_all_events_years.return_value = iter([])

        generator = self.service.generate_years()

        # Consume generator
        result = None
        try:
            while True:
                next(generator)
        except StopIteration as e:
            result = e.value

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
