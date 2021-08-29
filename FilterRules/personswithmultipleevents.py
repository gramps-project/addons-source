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
"""Matches persons which have multiple events of given type."""

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
class PeronsWithMultipleEvents(Rule):
    """Filter rule matching persons which have multiple events of given type."""

    labels = [_('Event type:')]
    name = _('Persons with multiple events of <type>')
    category = _("Event filters")
    description = _("Matches persons which have multiple events of given type.")
    namespace = 'Event'

    def apply(self, db, person):
        counter = 0
        for event_ref in person.event_ref_list:
            event = db.get_event_from_handle(event_ref.ref)
            if event.type.is_type(self.list[0]) and event_ref.role == EventRoleType.PRIMARY:
                counter += 1
        if counter >= 2:
            return True
        else:
            return False
