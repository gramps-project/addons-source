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

from name_processor.models.person import Person, Gender


class TestGenderEnum(unittest.TestCase):
    def test_gender_enum(self):
        self.assertEqual(Gender.MALE.value, "MALE")
        self.assertEqual(Gender.FEMALE.value, "FEMALE")
        self.assertEqual(Gender.UNKNOWN.value, "UNKNOWN")


class TestPersonDataclass(unittest.TestCase):
    def test_person_dataclass_initialization(self):
        person = Person(
            handle="h123",
            gramps_id="I0001",
            given_name="Ivan",
            gender=Gender.MALE,
            has_patronymic=False,
            display_name="Ivan Petrovich",
        )

        self.assertEqual(person.handle, "h123")
        self.assertEqual(person.gramps_id, "I0001")
        self.assertEqual(person.given_name, "Ivan")
        self.assertEqual(person.gender, Gender.MALE)
        self.assertFalse(person.has_patronymic)
        self.assertEqual(person.display_name, "Ivan Petrovich")

        # Check default factory fields
        self.assertIsNone(person.father_handle)
        self.assertEqual(person.alternate_first_names, [])

    def test_person_dataclass_with_optional_fields(self):
        person = Person(
            handle="h123",
            gramps_id="I0001",
            given_name="Maria",
            gender=Gender.FEMALE,
            has_patronymic=True,
            display_name="Maria Ivanovna",
            father_handle="f456",
            alternate_first_names=["Masha", "Marya"],
        )

        self.assertEqual(person.father_handle, "f456")
        self.assertEqual(person.alternate_first_names, ["Masha", "Marya"])


if __name__ == "__main__":
    unittest.main()
