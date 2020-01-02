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

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import (Event, EventType, EventRef, EventRoleType,
                            Person)

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

def add_event_to_person(dbstate, uistate, track, person_handle, event_type, event_date_object, event_description, citation_handle, event_role_type):
    db = dbstate.db
    """
    Add a new event to the specified person.
    """
    event = Event()
    event.set_type(event_type)
    event.set_date_object(event_date_object)
    event.add_citation(citation_handle)
    event.set_description(event_description)

    # add to the database
    with DbTxn(_("Add Event ({0})").format(event.get_gramps_id()), db) as trans:
        db.add_event(event, trans)
    # Add new event reference to the Person record
    event_ref = EventRef()
    event_ref.ref = event.get_handle()
    event_ref.set_role(event_role_type)
    person = db.get_person_from_handle(person_handle)
    person.add_event_ref(event_ref)
    with DbTxn(_("Add Event ({name})").format(name=name_displayer.display(person)), db) as trans:
        db.commit_person(person, trans)

def get_form_person_attr(db, form_event_handle, attr_type):
    """
    Find all persons referencing the form_event and which have an attribute of type attr_type
    returns a list of matching (person, attribute) tuples
    """
    result = []
    for item in db.find_backlink_handles(form_event_handle, include_classes=['Person']):
        handle = item[1]
        person = db.get_person_from_handle(handle)
        for event_ref in person.get_event_ref_list():
            if event_ref.ref == form_event_handle:
                for attr in event_ref.get_attribute_list():
                    if (attr.get_type() == attr_type):
                        result.append((person, attr))
    return result

def represents_int(s):
    """
    return True iff s is convertable to an int, False otherwise
    """
    try:
        int(s)
        return True
    except ValueError:
        return False
