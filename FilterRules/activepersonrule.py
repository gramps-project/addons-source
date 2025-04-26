#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Paul Culley
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

#-------------------------------------------------------------------------
#
# Standard Python modules
#
#-------------------------------------------------------------------------
from __future__ import annotations
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
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

#-------------------------------------------------------------------------
#
# IsActivePerson
#
#-------------------------------------------------------------------------
class IsActivePerson(Rule):
    """Rule that checks for the active person in the database"""

    name = _('Active person')
    category = _('General filters')
    description = _("Matches the active person")

    def prepare(self, db: Database, user):
        self.selected_handles: Set[PersonHandle] = set()
        active_person = user.uistate.get_active('Person') if (user and user.uistate) else None
        if active_person:
            self.selected_handles.add(active_person)
        else:
            user.warn("No active Person")

    def apply_to_one(self, db: Database, person: Person) -> bool:
        return person.handle in self.selected_handles
