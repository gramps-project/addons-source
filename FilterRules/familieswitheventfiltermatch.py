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
"""Filter rule which matches families that are matched by an event filter."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.family._matchesfilter import MatchesFilter
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
class FamiliesWithEventFilterMatch(MatchesFilter):
    """Rule that checks against an event filter."""

    labels = [_('Event filter name:')]
    name = _('Families matching <event filter>')
    category = _("Event filters")
    description = _("Matches families that are matched by an event filter")
    namespace = 'Event'

    def prepare(self, db, user):
        """
        Overwrite inherited 'prepare' fuction from :class:`MatchesFilter`.

        Families matching an event filter are put into class attribute
        'families' (set). This set of families serves as reference for the
        filter to apply to.
        """
        self.db = db
        self.families = set()
        self.events = set()
        MatchesFilter.prepare(self, db, user)
        self.MEF_filt = self.find_filter()
        for event_handle in db.iter_event_handles():
            if self.MEF_filt.check(db, event_handle):
                self.events.add(event_handle)
        self.__get_families()

    def apply(self, db, obj):
        """
        Return True if a family appies to the filter rule.

        :returns: True or False
        """
        if obj.handle in self.families:
            return True
        return False

    def __get_families(self):
        """Get all families matching an event filter."""
        for person_handle in self.db.iter_person_handles():
            person = self.db.get_person_from_handle(person_handle)
            for ref in person.get_event_ref_list():
                for ref_type, ref_handle in ref.get_referenced_handles():
                    if ref_type == "Event" and ref_handle in self.events:
                        for family in person.get_family_handle_list():
                            self.families.add(family)
