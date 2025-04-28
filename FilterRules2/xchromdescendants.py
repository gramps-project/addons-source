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
"""X-chromosomal descendants of <person>."""

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

# -------------------------------------------------------------------------
# Internationalization
# -------------------------------------------------------------------------
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
# XChromDescendants Filter Rule
#
# -------------------------------------------------------------------------
class XChromDescendants(HasGrampsId):
    """X-chromosomal descendants of <person>."""

    labels = [_("ID:")]
    name = _("X-chromosomal descendants of <person>")
    category = _("Descendant filters")
    description = _(
        "Matches all descendants of <person> following a "
        "X-chromosomal inheritance pattern."
    )

    def prepare(self, db: Database, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.selected_handles: Set[PersonHandle] = set()
        person = self.db.get_person_from_gramps_id(self.list[0])
        self.get_descendants(person)
        self.selected_handles.add(person.get_handle())

    def get_descendants(self, person):
        """Get all descendants following a X-chrom inheritance pattern."""
        family_list = person.get_family_handle_list()
        for family_h in family_list:
            family = self.db.get_family_from_handle(family_h)
            children = family.get_child_ref_list()
            for child_ref in children:
                child = self.db.get_person_from_handle(child_ref.ref)
                gender = child.get_gender()
                if (
                    person.get_gender() == 0
                    and child_ref.get_mother_relation() == _("Birth")
                    and gender in [0, 1]
                ):
                    self.selected_handles.add(child.get_handle())
                    self.get_descendants(child)
                if (
                    person.get_gender() == 1
                    and child_ref.get_father_relation() == _("Birth")
                    and gender == 0
                ):
                    self.selected_handles.add(child.get_handle())
                    self.get_descendants(child)

    def apply_to_one(self, db: Database, person: Person) -> bool:
        """Check if the filter applies to a person."""
        return person.handle in self.selected_handles
