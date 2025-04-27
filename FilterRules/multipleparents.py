#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2002-2006  Donald N. Allingham
# Copyright (C) 2025       Steve Youngs
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

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import Set
from gramps.gen.types import PersonHandle
from gramps.gen.lib import Person
from gramps.gen.db import Database

# -------------------------------------------------------------------------
# "People with multiple parent records"
# -------------------------------------------------------------------------
class MultipleParents(Rule):
    """People with multiple parent records"""

    name = _("People with multiple parent records")
    description = _("Matches people who have more than one set of parents")
    category = _("Family filters")

    def prepare(self, db: Database, user):
        self.selected_handles: Set[PersonHandle] = set()
        for person in db.iter_people():
            if len(person.get_parent_family_handle_list()) > 1:
                self.selected_handles.add(person.handle)

    def apply_to_one(self, db: Database, person: Person) -> bool:
        return person.handle in self.selected_handles
