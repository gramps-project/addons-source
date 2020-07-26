#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Matthias Kemmer
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
"""Matches descendants of person following Y-chrom inheritance patterns."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.person._hasidof import HasGrampsId
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# YChromInheritance
#
# -------------------------------------------------------------------------
class YChromInheritance(HasGrampsId):
    """Matches descendants of person following Y-chrom inheritance patterns."""

    labels = [_('ID:')]
    name = _('Y-chromosomal inheritance of <person>')
    description = _("Matches recorded descendants of person following "
                    "Y-chromosomal inheritance patterns.")
    category = _("Descendant filters")

    def prepare(self, db, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.persons = set()
        self.current_children = set()
        self.next_children = set()
        self.root_father = self.db.get_person_from_gramps_id(self.list[0])
        self.setup()
        self.get_male_desc()

    def setup(self):
        """Get the first round of male descendants."""
        self.persons.add(self.root_father.get_handle())
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
                if child_handle not in self.persons:
                    self.persons.add(child_handle)
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
                if (child_ref.get_father_relation() == _("Birth") and
                        child.get_gender() == 1):
                    male_children.add(child_ref.ref)
        return male_children

    def apply(self, db, obj):
        """Check if the filter applies to a person."""
        return obj.get_handle() in self.persons
