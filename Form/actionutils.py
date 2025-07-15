#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019-2020 Steve Youngs
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

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import (Event, EventType, EventRef, EventRoleType,
                            Name, Person)
from gramps.gui.editors import EditEvent, EditName, EditPerson

# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation

_ = _trans.gettext

# Constants to define the options for editing the details of an action
CANNOT_EDIT_DETAIL = 0
CAN_EDIT_DETAIL = 1
MUST_EDIT_DETAIL = 2


def __init__():
    pass


def make_event(type=EventType(), description=None, date_object=None, citation_handle=None, place_handle=None):
    """
    make an event initialised with the supplied values.
    return the event created
    """
    event = Event()
    event.set_type(type)
    event.set_description(description)
    event.set_date_object(date_object)
    event.add_citation(citation_handle)
    event.set_place_handle(place_handle)
    return event


def make_event_ref(event_handle=None, role=EventRoleType()):
    """
    make an event_ref initialised with the supplied values.
    return the event_ref created
    """
    event_ref = EventRef()
    event_ref.set_reference_handle(event_handle)
    event_ref.set_role(role)
    return event_ref


def make_name(first_name=None, citation_handle=None):
    name = Name()
    if first_name:
        name.set_first_name(first_name)
    if citation_handle:
        name.add_citation(citation_handle)
    return name


def update_name(name, first_name=None, citation_handle=None):
    if first_name:
        name.set_first_name(first_name)
    if citation_handle:
        name.add_citation(citation_handle)
    return name


def update_person(person, primary_name=None):
    person.set_primary_name(primary_name)
    return person


def commit_person(person, dbstate, uistate, track, edit_detail, callback):
    """
    commit person to the database, optionally showing the editor window first.
    callback(person) is called after successful commit.
    Note: If the editor window is cancelled, the callback is not called.
    """
    if edit_detail:
        EditPerson(dbstate, uistate, track, person, callback)
    else:
        db = dbstate.db
        with DbTxn(_("Update Person ({name})").format(name=name_displayer.display(person)), db) as trans:
            db.commit_person(person, trans)
        if callback:
            callback(person)


def add_event(event, dbstate, uistate, track, edit_detail, callback):
    """
    Add a new event to the database, calling callback(event) on successful completion.
    If edit_detail is true, and the user cancels the editor window, the callback is not called.
    """
    db = dbstate.db
    if edit_detail:
        EditEvent(dbstate, uistate, track, event, callback)
    else:
        # add the event to the database
        with DbTxn(_("Add Event ({0})").format(event.get_gramps_id()), db) as trans:
            db.add_event(event, trans)
        if callback:
            callback(event)


def do_add_event_ref_to_person(event_ref, person_handle, dbstate):
    """
    Add event_ref to person_handle
    return: person_handle
    """
    # Add new event reference to the person person_handle
    db = dbstate.db
    person = db.get_person_from_handle(person_handle)
    person.add_event_ref(event_ref)
    with DbTxn(_("Add Event ({name})").format(name=name_displayer.display(person)), db) as trans:
        db.commit_person(person, trans)
    return person_handle


def add_alternate_name_to_person(name, person_handle, dbstate, uistate, track, edit_detail, callback):
    # Add new altername name to the person person_handle
    db = dbstate.db
    person = db.get_person_from_handle(person_handle)
    person.add_alternate_name(name)
    commit_person(person, dbstate, uistate, track, edit_detail, callback)


def add_event_ref_to_person(event_ref, person_handle, dbstate, uistate, track, edit_detail, callback):
    """
    Add event_ref to person_handle, calling callback(person) on successful completion.
    If edit_detail is true, and the user cancels the editor window, the callback is not called.
    return: the person to whom the evert_ref was added.
    """
    # Add new event reference to the person person_handle
    db = dbstate.db
    person = db.get_person_from_handle(person_handle)
    person.add_event_ref(event_ref)
    commit_person(person, dbstate, uistate, track, edit_detail, callback)


def edit_name(name, dbstate, uistate, track, edit_detail, callback):
    if edit_detail:
        EditName(dbstate, uistate, track, name, callback)
    else:
        callback(name)


def get_form_person_attr(db, form_event_handle, attr_type):
    """
    Find all persons referencing the form_event and which have an attribute of type attr_type.
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
