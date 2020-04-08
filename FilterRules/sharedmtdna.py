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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
"""Filter rule that matches people sharing same mtDNA."""

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
# SharedMtDNA
#
# -------------------------------------------------------------------------
class SharedMtDNA(HasGrampsId):
    """Filter rule that matches people sharing same mtDNA."""

    labels = [_('ID:')]
    name = _('Descendants of <person> sharing mtDNA')
    description = _("Matches descendants of <person> sharing mtDNA")
    category = _("General filters")

    def prepare(self, db, user):
        """Prepare a reference list for the filter."""
        self.db = db
        self.persons = set()
        self.root_mother = self.db.get_person_from_gramps_id(self.list[0])
        self.current_children = set()
        self.next_children = set()
        self.setup()
        self.get_mt_desc()

    def setup(self):
        """Get the first round of male descendants."""
        self.persons.add(self.root_mother.get_handle())
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
                if child_handle not in self.persons:
                    self.persons.add(child_handle)
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

    def apply(self, db, obj):
        """Check if the filter applies to a person."""
        return obj.get_handle() in self.persons
