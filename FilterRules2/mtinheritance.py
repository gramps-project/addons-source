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
"""Matches descendants following mitochondrial inheritance patterns."""

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
# MtChromInheritance
#
# -------------------------------------------------------------------------
class MtChromInheritance(HasGrampsId):
    """Matches descendants following mitochondrial inheritance patterns."""

    labels = [_('ID:')]
    name = _('Mitochondrial inheritance of <person>')
    description = _("Matches recorded descendants of person following"
                    " mitochondrial inheritance patterns.")
    category = _("Descendant filters")

    def prepare(self, db: Database, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.selected_handles: Set[PersonHandle] = set()
        self.root_mother = self.db.get_person_from_gramps_id(self.list[0])
        self.current_children = set()
        self.next_children = set()
        self.setup()
        self.get_mt_desc()

    def setup(self):
        """Get the first round of male descendants."""
        self.selected_handles.add(self.root_mother.get_handle())
        children = self.get_all_children(self.root_mother)
        if children:
            for child_handle in children:
                self.current_children.update(children)
        else:
            return False

    def get_all_children(self, person):
        """Get all children of a person."""
        children = set()
        family_list = person.get_family_handle_list()

        if len(family_list) == 0:
            return False

        for family_handle in family_list:
            family = self.db.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                if child_ref.get_mother_relation() == _("Birth"):
                    children.add(child_ref.ref)
        return children

    def get_mt_desc(self, setup=False):
        """Get all descendants of a person sharing mtDNA."""
        if self.current_children and (False not in self.current_children):
            for child_handle in self.current_children:
                if child_handle not in self.selected_handles:
                    self.selected_handles.add(child_handle)
                    child = self.db.get_person_from_handle(child_handle)
                    if child.get_gender() == 0:
                        has_children = self.get_all_children(child)
                        if has_children:
                            self.next_children.update(has_children)
            self.current_children.clear()
            self.get_mt_desc()
        elif len(self.current_children) == 0 and len(self.next_children) > 0:
            self.current_children.update(self.next_children)
            self.next_children.clear()
            self.get_mt_desc()

    def apply_to_one(self, db: Database, person: Person) -> bool:
        """Check if the filter applies to a person."""
        return person.handle in self.selected_handles
