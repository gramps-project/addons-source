#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018  Paul Culley
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

"""
Filter rule to match persons with a particular event.
"""
# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
from operator import eq, ne

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gui.editors.filtereditor import MySelect, MyBoolean
from gramps.gen.filters.rules import Rule
from gramps.gen.const import GRAMPS_LOCALE as glocale

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import Set
from gramps.gen.types import PersonHandle
from gramps.gen.lib import Family, Person
from gramps.gen.db import Database

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class Roletype(MySelect):
    """Provide a Role type selector"""

    def __init__(self, db):
        MySelect.__init__(self, EventRoleType, db.get_event_roles())


class NoMatch(MyBoolean):
    """Provide a negation switch"""

    def __init__(self, db):
        MyBoolean.__init__(self, _("Does NOT match with selected Role"))
        self.set_tooltip_text(
            _("Finds the items that don't have event Roles " "of the selected type.")
        )


class HasEventRole(Rule):
    def _prepare(self, db: Database, user, obj_generator):
        self.selected_handles: Set[PersonHandle] = set()
        if self.list[0]:  # was a role specified
            cmp = eq if self.list[1] == "0" else ne
            for obj in obj_generator():
                for event_ref in obj.get_event_ref_list():
                    if cmp(event_ref.role.xml_str(), self.list[0]):
                        self.selected_handles.add(obj.handle)
                        continue


# -------------------------------------------------------------------------
#
# HasEvent
#
# -------------------------------------------------------------------------
class HasPersonEventRole(HasEventRole):
    """Rule that checks for a person with a selected event role"""

    labels = [(_("Role"), Roletype), (_("Inverse"), NoMatch)]
    name = _("People with events with the <role>")
    description = _("Matches people with an event with a selected role")
    category = _("Event filters")

    def prepare(self, db: Database, user):
        self._prepare(db, user, db.iter_people)

    def apply_to_one(self, dbase: Database, person: Person) -> bool:
        return person.handle in self.selected_handles


class HasFamilyEventRole(HasEventRole):
    """Rule that checks for a family with a selected event role"""

    labels = [(_("Role"), Roletype), (_("Inverse"), NoMatch)]
    name = _("Families with events with the <role>")
    description = _("Matches families with an event with a selected role")
    category = _("Event filters")

    def prepare(self, db: Database, user):
        self._prepare(db, user, db.iter_families)

    def apply_to_one(self, dbase: Database, family: Family) -> bool:
        return family.handle in self.selected_handles
