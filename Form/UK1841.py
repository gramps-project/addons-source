#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019      Steve Youngs
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

from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import (Event, EventType, EventRef, EventRoleType,
                            Person)

from actionbase import ActionBase

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation

_ = _trans.gettext

class PrimaryNameCitation(ActionBase):
    def __init__(self):
        ActionBase.__init__(self)
        pass

    def populate_model(self, db, citation, form_event, model):
        parent = model.append(None, (_("Add Primary Name citation"), None, None))
        for item in db.find_backlink_handles(form_event.get_handle(),
                                             include_classes=['Person']):
            handle = item[1]
            person = db.get_person_from_handle(handle)
            model.append(parent, (name_displayer.display(person), name_displayer.display(person),
                         lambda db, trans, citation_handle = citation.handle, person_handle = person.handle: PrimaryNameCitation.command(db, trans, citation_handle, person_handle)))

    def command(db, trans, citation_handle, person_handle):
        person = db.get_person_from_handle(person_handle)
        person.get_primary_name().add_citation(citation_handle)
        db.commit_person(person, trans)

class OccupationEvent(ActionBase):
    def __init__(self):
        ActionBase.__init__(self)
        pass

    def populate_model(self, db, citation, form_event, model):
        parent = model.append(None, (_("Add Occupation event"), None, None))
        for item in db.find_backlink_handles(form_event.get_handle(),
                                             include_classes=['Person']):
            handle = item[1]
            person = db.get_person_from_handle(handle)
            for event_ref in person.get_event_ref_list():
                if event_ref.ref == form_event.get_handle():
                    for attr in event_ref.get_attribute_list():
                        if (attr.get_type() == "Occupation"): # Form specific _attribute name
                            occupation = attr.get_value()
                            if (occupation) :
                                model.append(parent, (name_displayer.display(person), occupation,
                                             lambda db, trans, citation_handle = citation.handle, person_handle = person.handle, occupation_ = occupation: ActionBase.AddEventToPerson(db, trans, person_handle, EventType.OCCUPATION, form_event.get_date_object(), occupation_, citation_handle, EventRoleType.PRIMARY)))
