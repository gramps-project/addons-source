#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020       Matthias Kemmer
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
"""Filter rule that matches people who are matched by a family filter."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules._matchesfilterbase import MatchesFilterBase
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# IsRelatedWithFilterMatch
#
# -------------------------------------------------------------------------
class PersonsHavingFamilyFilterMatch(MatchesFilterBase):
    """Filter rule that checks against an family filter."""

    labels = [_('Family filter name:')]
    name = _('People matching <family filter>')
    category = _("Family filters")
    description = _("Matches people who are matched by a family filter")
    namespace = "Family"

    def prepare(self, db, user):
        """
        Overwrite inherited 'prepare' fuction from :class:`MatchesFilterBase`.

        Persons matching an event filter are put into class attribute
        'persons' (set). This set of persons serves as reference for the
        filter to apply to.
        """
        self.persons = set()
        MatchesFilterBase.prepare(self, db, user)
        self.MFF_filt = self.find_filter()
        for family_handle in db.iter_family_handles():
            if self.MFF_filt.check(db, family_handle):
                family = db.get_family_from_handle(family_handle)
                father = family.get_father_handle()
                mother = family.get_mother_handle()
                children = family.get_child_ref_list()
                self.persons.add(father)
                self.persons.add(mother)
                for child in children:
                    child_ref = child.get_referenced_handles()
                    if child_ref[0] == 'Person':
                        self.persons.add(child_ref[1])

    def apply(self, db, obj):
        """
        Return True if a person appies to the filter rule.

        :returns: True or False
        """
        if obj.get_handle() in self.persons:
            return True
        return False
