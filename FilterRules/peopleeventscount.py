#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021    Matthias Kemmer
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
"""Matches persons which have events of given type and number."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import Rule
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# Filter Rule Class
#
# -------------------------------------------------------------------------
class PeopleEventsCount(Rule):
    """Matches persons which have events of given type and number."""

    labels = [
        _('Personal event:'),
        _('Number of instances:'),
        _('Number must be:'),
        _('Primary Role:')]
    name = _('People with <count> of <event>')
    description = _(
        "Matches persons which have events of given type and number.")
    category = _("Event filters")
    allow_regex = False

    def prepare(self, db, user):
        if self.list[2] == 'less than':
            self.count_type = 0
        elif self.list[2] == 'greater than':
            self.count_type = 2
        else:
            self.count_type = 1  # "equal to"
        self.userSelectedCount = int(self.list[1])

    def apply(self, dbase, person):
        counter = 0
        for event_ref in person.get_event_ref_list():
            if not event_ref:
                continue
            if int(self.list[3]) and event_ref.role != EventRoleType.PRIMARY:
                continue
            event = dbase.get_event_from_handle(event_ref.ref)
            if event.type.is_type(self.list[0]):
                counter += 1

        if self.count_type == 0:  # "less than"
            return counter < self.userSelectedCount
        elif self.count_type == 2:  # "greater than"
            return counter > self.userSelectedCount
        # "equal to"
        return counter == self.userSelectedCount
