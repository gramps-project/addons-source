#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Matthias Kemmer
# Copyright (C) 2025  Steve Youngs
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
"""Matches descendants of filter result following Y-chrom inheritance patterns."""

# ------------------------------------------------
# Standard python modules
# ------------------------------------------------
from __future__ import annotations

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules._rule import Rule
from gramps.gen.filters.rules.person._matchesfilter import MatchesFilter
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
# YChromInheritanceFilterMatch
#
# -------------------------------------------------------------------------
class YChromInheritanceFilterMatch(Rule):
    """Matches descendants of filter result following Y-chromosomal inheritance patterns."""

    labels = [_("Filter name:")]
    name = _("Y-chromosomal inheritance of <filter>")
    description = _(
        "Matches recorded descendants of a filter result "
        "following Y-chromosomal inheritance patterns."
    )
    category = _("Descendant filters")

    def prepare(self, db: Database, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.selected_handles: Set[PersonHandle] = set()
        self.current_children = set()
        self.next_children = set()

        self.matchfilt = MatchesFilter(self.list)
        self.matchfilt.requestprepare(db, user)
        for person in db.iter_people():
            if self.matchfilt.apply(db, person) and person.get_gender() == 1:
                self.root_father = person
                self.setup()
                self.get_male_desc()

    def setup(self):
        """Get the first round of male descendants."""
        self.selected_handles.add(self.root_father.get_handle())
        children = self.get_male_children(self.root_father)
        if children:
            for child_handle in children:
                self.current_children.update(children)
        else:
            return False

    def get_male_desc(self):
        """Get all male descendant lines of root father recursively."""
        if self.current_children and (False not in self.current_children):
            for child_handle in self.current_children:
                if child_handle not in self.selected_handles:
                    self.selected_handles.add(child_handle)
                    child = self.db.get_person_from_handle(child_handle)
                    has_children = self.get_male_children(child)
                    if has_children:
                        self.next_children.update(has_children)
            self.current_children.clear()
            self.get_male_desc()
        elif len(self.current_children) == 0 and len(self.next_children) > 0:
            self.current_children.update(self.next_children)
            self.next_children.clear()
            self.get_male_desc()

    def get_male_children(self, person):
        """
        Get all male children of a person.

        This function returns a set of male children if a person has male
        children and their relationship type to the father is birth.
        """
        male_children = set()
        family_list = person.get_family_handle_list()

        if len(family_list) == 0:
            return False

        for family_handle in family_list:
            family = self.db.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                child = self.db.get_person_from_handle(child_ref.ref)
                if (
                    child_ref.get_father_relation() == _("Birth")
                    and child.get_gender() == 1
                ):
                    male_children.add(child_ref.ref)
        return male_children

    def apply_to_one(self, db: Database, person: Person) -> bool:
        """Check if the filter applies to a person."""
        return person.handle in self.selected_handles
