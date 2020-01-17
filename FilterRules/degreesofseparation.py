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
"""Filter rule that matches relatives by degrees of separation."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gui.editors.filtereditor import MyBoolean
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# IncPartners boolean option
#
# -------------------------------------------------------------------------
class InclPartner(MyBoolean):
    """Bolean option for filter editor."""

    def __init__(self, database):
        MyBoolean.__init__(self, _('Include Partners'))
        self.set_tooltip_text(_("Include the partners."))
        self.set_active(True)

    def set_text(self, val):
        """Set the checkbox active."""
        is_active = bool(int(val))
        self.set_active(is_active)


# -------------------------------------------------------------------------
#
# Degrees of separation filter rule class
#
# -------------------------------------------------------------------------
class DegreesOfSeparation(Rule):
    """Filter rule that matches relatives by degrees of separation."""

    labels = [_('ID:'), _("Degrees:"), (_('Include Partners:'), InclPartner)]
    name = _('People separated less than <N> degrees of <person>')
    category = _("General filters")
    description = _("Filter rule that matches relatives by degrees of"
                    " separation")

    def prepare(self, db, user):
        """Prepare a refernece list for the filter."""
        self.db = db
        self.persons = set()
        self.ancestors = set()
        pid = self.list[0]
        person = db.get_person_from_gramps_id(pid)
        root_handle = person.get_handle()

        self.__get_ancestors(root_handle)
        for ancestor in self.ancestors:
            self.__get_desc(ancestor, self.list[1])

        if bool(int(self.list[2])):
            self.__get_partners()

    def __get_ancestors(self, root_handle):
        """Get the ancestors of a person."""
        queue = [(root_handle, 1)]
        while queue:
            handle, gen = queue.pop(0)
            if handle in self.ancestors:
                continue
            self.ancestors.add(handle)
            gen += 1
            if gen <= int(self.list[1]):
                person = self.db.get_person_from_handle(handle)
                fam_id = person.get_main_parents_family_handle()
                if fam_id:
                    fam = self.db.get_family_from_handle(fam_id)
                    if fam:
                        f_id = fam.get_father_handle()
                        m_id = fam.get_mother_handle()
                        if f_id:
                            queue.append((f_id, gen))
                        if m_id:
                            queue.append((m_id, gen))

    def __get_desc(self, root_handle, gen):
        """Get the descendants of a person."""
        queue = [(root_handle, 1)]
        while queue:
            handle, gen = queue.pop(0)
            if handle in self.persons:
                continue
            self.persons.add(handle)
            gen += 1
            if gen <= int(self.list[1]):
                p = self.db.get_person_from_handle(handle)
                fam_list = p.get_family_handle_list()
                for fam_id in fam_list:
                    fam = self.db.get_family_from_handle(fam_id)
                    if fam:
                        for child_ref in fam.get_child_ref_list():
                            self.__get_desc(child_ref.ref, gen)

    def __get_partners(self):
        """Get the partners."""
        person_handles = list()
        for handle in self.persons:
            person_handles.append(handle)

        for handle in person_handles:
            person = self.db.get_person_from_handle(handle)
            family_list = person.get_family_handle_list()
            for family_handle in family_list:
                family = self.db.get_family_from_handle(family_handle)
                father = family.get_father_handle()
                mother = family.get_mother_handle()
                if father:
                    self.persons.add(father)
                if mother:
                    self.persons.add(mother)

    def apply(self, db, person):
        """Check if the filter applies to the person."""
        return person.handle in self.persons
