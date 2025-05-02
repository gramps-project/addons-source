#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020    Matthias Kemmer
# Copyright (C) 2025    Steve Youngs
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
"""Matches the earliest recorded patrilineal ancestor father."""

# ------------------------------------------------
# Standard python modules
# ------------------------------------------------
from __future__ import annotations

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.person._hasidof import HasGrampsId
from gramps.gen.const import GRAMPS_LOCALE as glocale

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import Set
from gramps.gen.types import PersonHandle
from gramps.gen.lib import Person
from gramps.gen.db import Database

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# PatrilinealProgenitor Filter Rule
#
# -------------------------------------------------------------------------
class PatrilinealProgenitor(HasGrampsId):
    """Matches the earliest recorded patrilineal ancestor father."""

    labels = [_("ID:")]
    name = _("Patrilineal progenitor of <person>")
    category = _("Ancestral filters")
    description = _("Matches the earliest recorded patrilineal " "ancestor father.")

    def prepare(self, db: Database, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.selected_handles: Set[PersonHandle] = set()
        self.run_search = True

        person = self.db.get_person_from_gramps_id(self.list[0])
        if person:
            start_father = self.get_father(person)
            if start_father:
                self.get_root_father(start_father)

    def get_father(self, person):
        """
        Get the father of a person.

        This function returns the father of a person if the child relationship
        type to the father is brith and only one father exists.
        """
        family_list = person.get_parent_family_handle_list()
        father_set = set()

        if not family_list:
            return False

        for family_handle in family_list:
            family = self.db.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                if (
                    person.get_handle() == child_ref.ref
                    and child_ref.get_father_relation() == _("Birth")
                ):
                    father_handle = family.get_father_handle()
                    father_set.add(father_handle)

        if len(father_set) == 1 and None not in father_set:
            father = self.db.get_person_from_handle(father_set.pop())
            return father
        return False

    def get_root_father(self, person):
        """Search recursively for the root father of a person."""
        while self.run_search:
            father = self.get_father(person)
            if father:
                self.get_root_father(father)
            else:
                self.run_search = False
                self.selected_handles.add(person.get_handle())

    def apply_to_one(self, db: Database, person: Person) -> bool:
        """Check if the filter applies to a person."""
        return person.handle in self.selected_handles
