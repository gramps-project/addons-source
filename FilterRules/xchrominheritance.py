#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020    Matthias Kemmer
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
"""X-chromosomal inheritance of <person>."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.person._hasidof import HasGrampsId
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


# -------------------------------------------------------------------------
#
# XChromInheritance Filter Rule
#
# -------------------------------------------------------------------------
class XChromInheritance(HasGrampsId):
    """X-chromosomal inheritance of <person>."""

    labels = [_('ID:')]
    name = _('X-chromosomal inheritance of <person>')
    category = _("Ancestral filters")
    description = _("Matches all ancestors of <person> who contributed to"
                    " X-chromosomal inheritance.")

    def prepare(self, db, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.persons = set()
        person = self.db.get_person_from_gramps_id(self.list[0])
        self.get_ancestors(person)

    def get_ancestors(self, person):
        """Get all ancestors who contributed to X-chromosomal inheritance."""
        self.persons.add(person.get_handle())
        male = person.get_gender() == 1
        female = person.get_gender() == 0
        family_h = person.get_main_parents_family_handle()
        if (male or female) and family_h:
            family = self.db.get_family_from_handle(family_h)

            if male:  # one X-chromosome from mother
                mother_h = family.get_mother_handle()
                if mother_h:
                    mother = self.db.get_person_from_handle(mother_h)
                    self.get_ancestors(mother)

            if female:  # two X-chromosome, one from each mother and father
                mother_h = family.get_mother_handle()
                if mother_h:
                    mother = self.db.get_person_from_handle(mother_h)
                    self.get_ancestors(mother)
                father_h = family.get_father_handle()
                if father_h:
                    father = self.db.get_person_from_handle(father_h)
                    self.get_ancestors(father)

    def apply(self, db, obj):
        """Check if the filter applies to a person."""
        return obj.get_handle() in self.persons
