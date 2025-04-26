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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
"""Filter rule that matches people by their age at death."""

# ------------------------------------------------
# Standard python modules
# ------------------------------------------------
from __future__ import annotations
from operator import lt, eq, gt

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gui.editors.filtereditor import MyInteger, MyLesserEqualGreater
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
# Age number option
#
# -------------------------------------------------------------------------
class AgeOption(MyInteger):
    """Number option for filter editor."""

    def __init__(self, database):
        MyInteger.__init__(self, 0, 125)
        self.set_tooltip_text(_("Age in years at person's death."))


# -------------------------------------------------------------------------
#
# LesserEqualGreater option
#
# -------------------------------------------------------------------------
class LesserEqualGreaterOption(MyLesserEqualGreater):
    """LesserEqualGreater option for filter editor."""

    def __init__(self, database):
        MyLesserEqualGreater.__init__(self)


# -------------------------------------------------------------------------
#
# Age at death filter rule class
#
# -------------------------------------------------------------------------
class AgeAtDeath(Rule):
    """Filter rule that matches people by their age at death."""

    labels = [('', LesserEqualGreaterOption),
              (_("Age:"), AgeOption)]
    name = _('Filter people by their age at death')
    category = _("General filters")
    description = _("Filter people by their age at death")

    def prepare(self, db: Database, user):
        """Prepare a reference list for the filter."""
        self.selected_handles: Set[PersonHandle] = set()

        cmp = None
        leg = self.list[0]  # LesserEqualGreater
        if leg == "less than":
            cmp = lt
        elif leg == "equal to":
            cmp = eq
        elif leg == "greater than":
            cmp = gt

        max_age = int(self.list[1])

        for person_h in db.iter_person_handles():
            person = db.get_person_from_handle(person_h)
            birth_ref = person.get_birth_ref()
            death_ref = person.get_death_ref()
            if birth_ref and death_ref:
                birth = db.get_event_from_handle(birth_ref.ref)
                birth_date = birth.get_date_object()
                death = db.get_event_from_handle(death_ref.ref)
                death_date = death.get_date_object()
                if birth_date.is_regular() and death_date.is_regular():
                    age = death_date - birth_date
                    if cmp(age[0], max_age):
                        self.selected_handles.add(person_h)

    def apply_to_one(self, db: Database, person: Person) -> bool:
        """Check if the filter applies to the person."""
        return person.handle in self.selected_handles
