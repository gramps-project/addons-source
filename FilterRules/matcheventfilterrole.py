#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2002-2006  Donald N. Allingham
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.person import MatchesEventFilter

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from gramps.gen.lib import Person
from gramps.gen.db import Database
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gui.editors.filtereditor import MySelect


class Roletype(MySelect):
    """Provide a Role type selector"""

    def __init__(self, db):
        MySelect.__init__(self, EventRoleType, db.get_event_roles())


class MatchesEventFilterRole(MatchesEventFilter):
    labels = [_("Event filter name:"), _("Include Family events:"), (_('Role:'), Roletype)]
    name = _("Persons with events matching the <event filter> with role")
    
    def prepare(self, db: Database, user):
        MatchesEventFilter.prepare(self, db, user)

        try:
            if int(self.list[1]):
                self.MPF_famevents = True
            else:
                self.MPF_famevents = False
        except IndexError:
            self.MPF_famevents = False
    
    def apply_to_one(self, db: Database, person: Person) -> bool:
        
        filt = self.find_filter()
        if filt:
            for event_ref in person.get_event_ref_list():
                if not event_ref:
                    continue
                if event_ref.role.xml_str() == self.list[2]:
                    event = db.get_event_from_handle(event_ref.get_reference_handle())
                    if filt.apply_to_one(db, event):
                        return True
            if self.MPF_famevents:
                # also include if family event of the person
                for handle in person.get_family_handle_list():
                    family = db.get_family_from_handle(handle)
                    for event_ref in family.get_event_ref_list():
                        if not event_ref:
                            continue
                        if event_ref.role.xml_str() == self.list[2]:
                            event = db.get_event_from_handle(event_ref.get_reference_handle())
                            if filt.apply_to_one(db, event):
                                return True
            return False
    
