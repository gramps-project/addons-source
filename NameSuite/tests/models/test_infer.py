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

from name_processor.models.infer import (
    PatronymicInferenceStatus,
    ProposedPatronymic,
)


class TestPatronymicInferenceStatus(unittest.TestCase):
    def test_patronymic_inference_status_enum(self):
        self.assertEqual(PatronymicInferenceStatus.SUCCESS.value, "SUCCESS")
        self.assertEqual(
            PatronymicInferenceStatus.NO_ACTIVE_PERSON.value, "NO_ACTIVE_PERSON"
        )
        self.assertEqual(
            PatronymicInferenceStatus.MORPHOLOGY_FAIL.value, "MORPHOLOGY_FAIL"
        )


class TestProposedPatronymicDataclass(unittest.TestCase):
    def test_proposed_patronymic_dataclass_defaults(self):
        res = ProposedPatronymic()
        self.assertIsNone(res.patronymic)
        self.assertIsNone(res.father_name)
        self.assertEqual(res.status, PatronymicInferenceStatus.UNKNOWN_ERROR)

    def test_proposed_patronymic_dataclass_assignment(self):
        res = ProposedPatronymic(
            patronymic="Petrovich",
            father_name="Petr",
            status=PatronymicInferenceStatus.SUCCESS,
        )
        self.assertEqual(res.patronymic, "Petrovich")
        self.assertEqual(res.father_name, "Petr")
        self.assertEqual(res.status, PatronymicInferenceStatus.SUCCESS)


if __name__ == "__main__":
    unittest.main()
