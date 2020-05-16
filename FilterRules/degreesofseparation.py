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
"""Filter rule that matches relatives by degrees of separation."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gui.editors.filtereditor import MyBoolean, MyInteger
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# Degrees number option
#
# -------------------------------------------------------------------------
class DegreesOption(MyInteger):
    """Number option for filter editor."""

    def __init__(self, database):
        MyInteger.__init__(self, 1, 32)
        self.set_tooltip_text(_("Number of degrees of separation from"
                                " person."))


# -------------------------------------------------------------------------
#
# IncPartners boolean option
#
# -------------------------------------------------------------------------
class InclPartner(MyBoolean):
    """Boolean option for filter editor."""

    def __init__(self, database):
        MyBoolean.__init__(self, _('Include Partners'))
        self.set_tooltip_text(_("Include all partners."))
        self.set_active(True)

    def set_text(self, val):
        """Set the checkbox active."""
        is_active = bool(int(val))
        self.set_active(is_active)


# -------------------------------------------------------------------------
#
# IncPartners boolean option
#
# -------------------------------------------------------------------------
class InclAllParents(MyBoolean):
    """Boolean option for filter editor."""

    def __init__(self, database):
        MyBoolean.__init__(self, _('Include all parents'))
        self.set_tooltip_text(_("Include parents with relationship foster,"
                                " adopted, stepchild, etc."))
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

    labels = [_('ID:'),
              (_("Degrees:"), DegreesOption),
              ('', InclPartner),
              ('', InclAllParents)]
    name = _('People separated less than <N> degrees of <person>')
    category = _("Relationship filters")
    description = _("Filter rule that matches relatives by degrees of"
                    " separation")

    def prepare(self, db, user):
        """Prepare a refernece list for the filter."""
        self.db = db
        self.persons = set()
        self.ancestors = list()
        root_handle = self.__get_root_handle()

        self.__get_ancestors(root_handle)
        for ancestor in self.ancestors:
            self.__get_desc(ancestor, 0)

        get_partners = bool(int(self.list[2]))
        if get_partners:
            self.__get_partners()

    def __get_root_handle(self):
        """Get the handle of the starting person."""
        pid = self.list[0]
        person = self.db.get_person_from_gramps_id(pid)
        root_handle = person.get_handle()
        return root_handle

    def __get_ancestors(self, root_handle):
        """Get the ancestors of a person."""
        self.queue = [(root_handle, 1)]
        while self.queue:
            handle, gen = self.queue.pop(0)
            if handle in self.ancestors:
                continue
            self.ancestors.append(handle)
            gen += 1
            if gen <= int(self.list[1]):
                person = self.db.get_person_from_handle(handle)
                fam_list = person.get_parent_family_handle_list()
                for fam_id in fam_list:
                    if fam_id:
                        fam = self.db.get_family_from_handle(fam_id)
                        if fam:
                            f_id = fam.get_father_handle()
                            m_id = fam.get_mother_handle()
                            self.__check_parents(fam, f_id, m_id, person, gen)

    def __check_parents(self, fam, f_id, m_id, person, gen):
        """Check InclAllParents option and parent-child relationship type."""
        for child_ref in fam.get_child_ref_list():
            if child_ref.ref == person.get_handle():
                f_rel = child_ref.get_father_relation()
                m_rel = child_ref.get_mother_relation()
                # check father
                if f_id and self.list[3] == '1':
                    self.queue.append((f_id, gen))
                elif f_id and f_rel == _("Birth"):
                    self.queue.append((f_id, gen))
                # check mother
                if m_id and self.list[3] == '1':
                    self.queue.append((m_id, gen))
                elif m_id and m_rel == _("Birth"):
                    self.queue.append((m_id, gen))

    def __get_desc(self, root_handle, gen):
        """Get the descendants of a person."""
        if root_handle in self.persons:
            return

        self.persons.add(root_handle)
        if gen >= int(self.list[1]):
            return

        person = self.db.get_person_from_handle(root_handle)
        fam_list = person.get_family_handle_list()
        for fam_id in fam_list:
            fam = self.db.get_family_from_handle(fam_id)
            if fam:
                for child_ref in fam.get_child_ref_list():
                    self.__get_desc(child_ref.ref, gen+1)

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
