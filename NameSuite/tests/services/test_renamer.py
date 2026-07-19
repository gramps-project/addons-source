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

import re
import unittest

from name_processor.models.renamer import MatchMode
from name_processor.services.renamer import RenamerService


class TestRenamerService(unittest.TestCase):
    def test_regex_capture_group_single(self):
        """Test regex with single capture group using Python \1 syntax."""
        service = RenamerService()
        rule = service.create_config(MatchMode.REGEX, "А(.*)", r"О\1")

        result = service.evaluate_person("Анна", rule)

        self.assertIsNotNone(result)
        self.assertEqual(result, "Онна")

    def test_regex_capture_group_single_arkady(self):
        """Test regex with single capture group using Python \1 syntax for Аркадий."""
        service = RenamerService()
        rule = service.create_config(MatchMode.REGEX, "А(.*)", r"О\1")

        result = service.evaluate_person("Аркадий", rule)

        self.assertIsNotNone(result)
        self.assertEqual(result, "Оркадий")

    def test_regex_capture_group_multiple(self):
        """Test regex with multiple capture groups using Python \1, \2 syntax."""
        service = RenamerService()
        rule = service.create_config(MatchMode.REGEX, "(А)(.*)", r"О\2")

        result = service.evaluate_person("Анна", rule)

        self.assertIsNotNone(result)
        self.assertEqual(result, "Онна")

    def test_regex_no_capture_group(self):
        """Test regex without capture groups still works."""
        service = RenamerService()
        rule = service.create_config(MatchMode.REGEX, "Анна", "Анна Мария")

        result = service.evaluate_person("Анна", rule)

        self.assertIsNotNone(result)
        self.assertEqual(result, "Анна Мария")

    def test_regex_no_match(self):
        """Test regex that doesn't match returns None."""
        service = RenamerService()
        rule = service.create_config(MatchMode.REGEX, "Б(.*)", "О$1")

        result = service.evaluate_person("Анна", rule)

        self.assertIsNone(result)

    def test_exact_match(self):
        """Test exact match mode."""
        service = RenamerService()
        rule = service.create_config(MatchMode.EXACT, "Анна", "Анна Мария")

        result = service.evaluate_person("Анна", rule)

        self.assertIsNotNone(result)
        self.assertEqual(result, "Анна Мария")

    def test_substring_match(self):
        """Test substring match mode."""
        service = RenamerService()
        rule = service.create_config(MatchMode.SUBSTRING, "Анна", "Анна Мария")

        result = service.evaluate_person("Анна Иванова", rule)

        self.assertIsNotNone(result)
        self.assertEqual(result, "Анна Мария Иванова")

    def test_invalid_regex(self):
        """Test invalid regex raises exception during config creation."""
        service = RenamerService()
        with self.assertRaises(re.error):
            service.create_config(MatchMode.REGEX, "[invalid", "replacement")
