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
"""Filter rule matching associations of <person filter>."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.filters.rules.person._matchesfilter import MatchesFilter
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext


# -------------------------------------------------------------------------
#
# Associations of <person filter>
#
# -------------------------------------------------------------------------
class AssociationsOfPersonMatch(Rule):
    """Filter rule matching associations of <person filter>."""

    labels = [_('Filter name:')]
    name = _('Match associations of <person filter>')
    description = _("Match associations of <person filter>")
    category = _('General filters')
    namespace = 'Person'

    def prepare(self, db, user):
        """Prepare a refernece list for the filter."""
        self.persons = set()
        iter_persons = db.iter_person_handles()
        filter_ = MatchesFilter(self.list).find_filter()
        handle_list = filter_.apply(db, iter_persons)
        for handle in handle_list:
            person = db.get_person_from_handle(handle)
            self.persons.update([i.ref for i in person.get_person_ref_list()])

    def apply(self, db, person):
        """Check if the filter applies to the person."""
        return person.get_handle() in self.persons
