#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019       Matthias Kemmer
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
"""
Filter rule to match related persons to anybody that matched a person filter.
"""
# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.person._isrelatedwith import IsRelatedWith
from gramps.gen.filters.rules.person._matchesfilter import MatchesFilter
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
class IsRelatedWithFilterMatch(IsRelatedWith):
    """Rule that checks against another person filter"""

    labels = [_('Filter name:')]
    name = _('People related to <filter>')
    category = _("Relationship filters")
    description = _("Matches people who are related to anybody matched by "
                    "a person filter")

    def prepare(self, db, user):
        self.db = db
        self.relatives = []
        self.filt = MatchesFilter(self.list)
        self.filt.requestprepare(db, user)

        num = db.get_number_of_people()
        if user:
            user.begin_progress(self.category,
                                _('Retrieving all sub-filter matches'),
                                num)
        for handle in db.iter_person_handles():
            person = db.get_person_from_handle(handle)
            if user:
                user.step_progress()
            if person and self.filt.apply(db, person):
                self.add_relative(person)
        if user:
            user.end_progress()
