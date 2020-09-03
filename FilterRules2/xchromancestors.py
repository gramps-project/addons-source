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
"""X-chromosomal ancestors of <person>."""

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
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# XChromAncestors Filter Rule
#
# -------------------------------------------------------------------------
class XChromAncestors(HasGrampsId):
    """X-chromosomal ancestors of <person>."""

    labels = [_('ID:')]
    name = _('X-chromosomal ancestors of <person>')
    category = _("Ancestral filters")
    description = _("Matches ancestors of <person> following a "
                    "X-chromosomal inheritance pattern.")

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
        family_handels = person.get_parent_family_handle_list()
        for family_h in family_handels:
            if (male or female) and family_h:
                family = self.db.get_family_from_handle(family_h)

                if male:  # one X-chromosome from mother
                    mother_h = family.get_mother_handle()
                    if mother_h and self.mother_relationship(person, family):
                        mother = self.db.get_person_from_handle(mother_h)
                        self.get_ancestors(mother)

                if female:  # two X-chromosome, one from each mother and father
                    mother_h = family.get_mother_handle()
                    if mother_h and self.mother_relationship(person, family):
                        mother = self.db.get_person_from_handle(mother_h)
                        self.get_ancestors(mother)
                    father_h = family.get_father_handle()
                    if father_h and self.father_relationship(person, family):
                        father = self.db.get_person_from_handle(father_h)
                        self.get_ancestors(father)

    def mother_relationship(self, person, family):
        """Check if mother-child relationship type is birth."""
        for child_ref in family.get_child_ref_list():
            if child_ref.ref == person.get_handle():
                if child_ref.get_mother_relation() == _("Birth"):
                    return True
        return False

    def father_relationship(self, person, family):
        """Check if father-child relationship type is birth."""
        for child_ref in family.get_child_ref_list():
            if child_ref.ref == person.get_handle():
                if child_ref.get_father_relation() == _("Birth"):
                    return True
        return False

    def apply(self, db, obj):
        """Check if the filter applies to a person."""
        return obj.get_handle() in self.persons
