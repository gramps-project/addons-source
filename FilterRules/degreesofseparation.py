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
        MyInteger.__init__(self, 0, 32)
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
# Degrees of separation filter rule class
#
# -------------------------------------------------------------------------
class DegreesOfSeparation(Rule):
    """Filter rule that matches relatives by degrees of separation."""

    labels = [_('ID:'),
              (_("Degrees:"), DegreesOption),
              ('', InclPartner)]
    name = _('People separated less than <N> degrees of <person>')
    category = _("Relationship filters")
    description = _("Filter rule that matches relatives by degrees of"
                    " separation")

    def prepare(self, db, user):
        """Prepare a refernece list for the filter."""
        self.db = db
        self.ref_list = set()
        self.persons = set()
        opt_partners = bool(int(self.list[2]))
        degree = 0
        max_deg = int(self.list[1])

        self.get_root_handle()
        while degree <= max_deg:
            for handle in list(self.persons):
                person = self.db.get_person_from_handle(handle)
                self.get_parents(person)
                self.get_children(person)
                self.get_siblings(person)
                self.persons.remove(handle)
                self.ref_list.add(handle)
            degree += 1

        if opt_partners:
            self.get_partners()

    def get_root_handle(self):
        """Get the handle of the starting person."""
        pid = self.list[0]
        person = self.db.get_person_from_gramps_id(pid)
        root_handle = person.get_handle()
        self.persons.add(root_handle)

    def get_parents(self, person):
        """Get all parents of a person."""
        fam_list = person.get_parent_family_handle_list()
        for fam_h in fam_list:
            fam = self.db.get_family_from_handle(fam_h)
            father_h = fam.get_father_handle()
            mother_h = fam.get_mother_handle()
            if father_h:
                self.persons.add(father_h)
            if mother_h:
                self.persons.add(mother_h)

    def get_children(self, person):
        """Get all children of a person."""
        fam_list = person.get_family_handle_list()
        for fam_h in fam_list:
            fam = self.db.get_family_from_handle(fam_h)
            for child_ref in fam.get_child_ref_list():
                self.persons.add(child_ref.ref)

    def get_siblings(self, person):
        """Get all siblings of a person."""
        fam_list = person.get_parent_family_handle_list()
        for fam_h in fam_list:
            fam = self.db.get_family_from_handle(fam_h)
            father_h = fam.get_father_handle()
            if father_h:
                father = self.db.get_person_from_handle(father_h)
                if father:
                    self.get_children(father)
            mother_h = fam.get_mother_handle()
            if mother_h:
                mother = self.db.get_person_from_handle(mother_h)
                if mother:
                    self.get_children(mother)

    def get_partners(self):
        """Get all partners."""
        for handle in list(self.ref_list):
            person = self.db.get_person_from_handle(handle)
            fam_list = person.get_family_handle_list()
            if fam_list:
                for fam_h in fam_list:
                    fam = self.db.get_family_from_handle(fam_h)
                    father_h = fam.get_father_handle()
                    mother_h = fam.get_mother_handle()
                    self.ref_list.update([father_h, mother_h])

    def apply(self, db, person):
        """Check if the filter applies to the person."""
        return person.handle in self.ref_list
