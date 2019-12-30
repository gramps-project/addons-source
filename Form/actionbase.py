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

"""
ActionBase definitions.
"""

from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import (Event, EventType, EventRef, EventRoleType,
                            Person)

class ActionBase():
    """
    A class to read form definitions from an XML file.
    """
    def __init__(self):
        pass

    def add_event_to_person(db, trans, person_handle, event_type, event_date_object, event_description, citation_handle, event_role_type):
        """
        Add a new event to the specified person.
        """
        event = Event()
        event.set_type(event_type)
        event.set_date_object(event_date_object)
        event.add_citation(citation_handle)
        event.set_description(event_description)

        # add to the database
        db.add_event(event, trans)
        # Add new event reference to the Person record
        event_ref = EventRef()
        event_ref.ref = event.get_handle()
        event_ref.set_role(event_role_type)
        person = db.get_person_from_handle(person_handle)
        person.add_event_ref(event_ref)
        db.commit_person(person, trans)

def represents_int(s):
    """
    return True iff s is convertable to an int, False otherwise
    """
    try:
        int(s)
        return True
    except ValueError:
        return False
