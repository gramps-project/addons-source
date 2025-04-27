#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021    Matthias Kemmer
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
"""Matches persons which have events of given type and number."""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
from operator import lt, eq, gt

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.lib.eventroletype import EventRoleType
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
# Filter Rule Class
#
# -------------------------------------------------------------------------
class PeopleEventsCount(Rule):
    """Matches persons which have events of given type and number."""

    labels = [
        _("Personal event:"),
        _("Number of instances:"),
        _("Number must be:"),
        _("Primary Role:"),
    ]
    name = _("People with <count> of <event>")
    description = _("Matches persons which have events of given type and number.")
    category = _("Event filters")
    allow_regex = False

    def prepare(self, db: Database, user):
        event_type = self.list[0]
        event_count = int(self.list[1])
        cmp = (
            lt
            if self.list[2] == "less than"
            else (
                eq
                if self.list[2] == "equal to"
                else gt if self.list[2] == "greater than" else None
            )
        )
        all_roles = not bool(self.list[3])

        self.selected_handles: Set[PersonHandle] = set()

        for person in db.iter_people():
            count = 0
            for event_ref in person.event_ref_list:
                if event_ref and (all_roles or event_ref.role == EventRoleType.PRIMARY):
                    event = db.get_raw_event_data(event_ref.ref)
                    if event.type.is_type(event_type):
                        count = count + 1
            if cmp(count, event_count):
                self.selected_handles.add(person.handle)

    def apply_to_one(self, dbase: Database, person: Person) -> bool:
        return person.handle in self.selected_handles
