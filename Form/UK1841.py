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
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib import (Date, Event, EventType, EventRef, EventRoleType,
                            Name, Person)
from gramps.gen.utils.db import get_participant_from_event

# ------------------------------------------------------------------------
#
# Gramplet modules
#
# ------------------------------------------------------------------------
import actionutils

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


def get_actions(dbstate, citation, form_event):
    """
    return a list of all actions that this module can provide for the given citation and form
    each list entry is a string, describing the action category, and a list of actions that can be performed.
    """
    actions = []
    actions.append(PrimaryNameCitation.get_actions(
        dbstate, citation, form_event))
    actions.append(AlternateName.get_actions(dbstate, citation, form_event))
    actions.append(BirthEvent.get_actions(dbstate, citation, form_event))
    actions.append(OccupationEvent.get_actions(dbstate, citation, form_event))
    actions.append(ResidenceEvent.get_actions(dbstate, citation, form_event))
    return actions


class PrimaryNameCitation:
    @staticmethod
    def get_actions(dbstate, citation, form_event):
        db = dbstate.db
        actions = []
        for (person, attr) in actionutils.get_form_person_attr(db, form_event.get_handle(), 'Name'):
            actions.append((name_displayer.display(person), attr.get_value(), actionutils.CAN_EDIT_DETAIL,
                            # lambda dbstate, uistate, track, edit_detail, callback, citation_handle=citation.handle, person_handle=person.handle: PrimaryNameCitation.command(dbstate, uistate, track, edit_detail, callback, citation_handle, person_handle)))
                            # action command callback
                            lambda dbstate, uistate, track, edit_detail, callback, person=person:
                            actionutils.edit_name(actionutils.update_name(name=person.get_primary_name(), citation_handle=citation.handle),
                                                  dbstate, uistate, track, edit_detail,
                                                  # edit_name callback
                                                  lambda name, person=person, dbstate=dbstate, uistate=uistate, track=track, edit_detail=edit_detail:
                                                  actionutils.commit_person(actionutils.update_person(person=person, primary_name=name),
                                                                            dbstate, uistate, track, False, # nothing to edit, so force edit_detail=False
                                                                            # commit_person callback
                                                                            # call the top level callback
                                                                            lambda person, callback=callback: callback()))))

        return (_("Add Primary Name citation"), actions)


class AlternateName:
    @staticmethod
    def get_actions(dbstate, citation, form_event):
        db = dbstate.db
        actions = []
        for (person, attr) in actionutils.get_form_person_attr(db, form_event.get_handle(), 'Name'):
            detail = _('Given Name: {name}').format(name=attr.get_value())
            actions.append((name_displayer.display(person), detail,
                            # the user should split the 'Name' attribute into the consituent parts of a Name object, so force MUST_EDIT_DETAIL
                            actionutils.MUST_EDIT_DETAIL,
                            # action command callback
                            lambda dbstate, uistate, track, edit_detail, callback, person=person, name=attr.get_value():
                            actionutils.edit_name(actionutils.make_name(first_name=name, citation_handle=citation.handle), dbstate, uistate, track, edit_detail,
                                                  # edit_name callback
                                                  lambda name, dbstate=dbstate, uistate=uistate, track=track, edit_detail=edit_detail:
                                                  actionutils.add_alternate_name_to_person(name, person.handle,
                                                                                           dbstate, uistate, track, False,  # nothing to edit, so force edit_detail=False
                                                                                           # add_alternate_name_to_person callback
                                                                                           # call the top level callback
                                                                                           lambda person, callback=callback: callback()))))
        return (_("Add alternate name"), actions)


class BirthEvent:
    @staticmethod
    def get_actions(dbstate, citation, form_event):
        db = dbstate.db
        actions = []
        # if there is no date on the form, no actions can be performed
        if form_event.get_date_object():
            for (person, attr) in actionutils.get_form_person_attr(db, form_event.get_handle(), 'Age'):
                age_string = attr.get_value()
                if age_string:
                    birth_date = None
                    if actionutils.represents_int(age_string):
                        age = int(age_string)
                        if age:
                            birth_date = form_event.get_date_object() - age
                            birth_date.make_vague()
                            # Age was rounded down to the nearest five years for those aged 15 or over
                            # In practice this rule was not always followed by enumerators
                            if age < 15:
                                # no adjustment required
                                birth_date.set_modifier(Date.MOD_ABOUT)
                            elif not birth_date.is_compound():
                                # in theory, birth_date will never be compound since 1841 census date was 1841-06-06. Let's handle it anyway.
                                # create a compound range spanning the possible birth years
                                birth_range = (birth_date - 5).get_dmy() + \
                                    (False,) + birth_date.get_dmy() + (False,)
                                birth_date.set(Date.QUAL_NONE, Date.MOD_RANGE, birth_date.get_calendar(
                                ), birth_range, newyear=birth_date.get_new_year())
                            birth_date.set_quality(Date.QUAL_CALCULATED)
                            detail = _('Age: {age}\nDate: {date}').format(
                                age=age_string, date=date_displayer.display(birth_date))
                    else:
                        detail = _('Age: {age}').format(age=age_string)

                    actions.append((name_displayer.display(person), detail,
                                    actionutils.CAN_EDIT_DETAIL if birth_date else actionutils.MUST_EDIT_DETAIL,
                                    # action command callback
                                    lambda dbstate, uistate, track, edit_detail, callback, person=person, birth_date=birth_date:
                                        # add a birth event
                                        actionutils.add_event(actionutils.make_event(type=EventType.BIRTH, date_object=birth_date, citation_handle=citation.handle),
                                                              dbstate, uistate, track, edit_detail,
                                                              # add_event callback
                                                              lambda event, dbstate=dbstate, uistate=uistate, track=track, edit_detail=edit_detail, callback=callback, person_handle=person.handle:
                                                              # and then add a reference to the event to person
                                                              actionutils.add_event_ref_to_person(actionutils.make_event_ref(event_handle=event.get_handle(), role=EventRoleType.PRIMARY), person_handle, dbstate, uistate, track, edit_detail,
                                                                                                  # add_event_ref_to_person callback
                                                                                                  # call the top level callback
                                                                                                  lambda person, callback=callback: callback()))))
        return (_("Add Birth event"), actions)


class OccupationEvent:
    @staticmethod
    def get_actions(dbstate, citation, form_event):
        db = dbstate.db
        actions = []
        for (person, attr) in actionutils.get_form_person_attr(db, form_event.get_handle(), 'Occupation'):
            occupation = attr.get_value()
            if (occupation):
                detail = _('Description: {occupation}').format(
                    occupation=occupation)
                actions.append((name_displayer.display(person), detail,
                                actionutils.CAN_EDIT_DETAIL,
                                # action command callback
                                lambda dbstate, uistate, track, edit_detail, callback, person=person, occupation=occupation:
                                    # add a occupation event
                                    actionutils.add_event(actionutils.make_event(type=EventType.OCCUPATION, description=occupation, date_object=form_event.get_date_object(), citation_handle=citation.handle),
                                                          dbstate, uistate, track, edit_detail,
                                                          # add_event callback
                                                          lambda event, dbstate=dbstate, uistate=uistate, track=track, edit_detail=edit_detail, callback=callback, person_handle=person.handle:
                                                          # and then add a reference to the event to person
                                                          actionutils.add_event_ref_to_person(actionutils.make_event_ref(event_handle=event.get_handle(), role=EventRoleType.PRIMARY), person_handle, dbstate, uistate, track, edit_detail,
                                                                                              # add_event_ref_to_person callback
                                                                                              # call the top level callback
                                                                                              lambda person, callback=callback: callback()))))
        return (_("Add Occupation event"), actions)


class ResidenceEvent:
    @staticmethod
    def get_actions(dbstate, citation, form_event):
        db = dbstate.db
        # build a list of all the people referenced in the form. For 1841, all people have a PRIMARY event role
        event_ref_details = []
        for item in db.find_backlink_handles(form_event.get_handle(), include_classes=['Person']):
            handle = item[1]
            person = db.get_person_from_handle(handle)
            for event_ref in person.get_event_ref_list():
                if event_ref.ref == form_event.get_handle():
                    event_ref_details.append(
                        (person.get_handle(), EventRoleType.PRIMARY))
        actions = []
        if event_ref_details:
            detail = None
            if form_event.get_place_handle():
                place = place_displayer.display(
                    db, db.get_place_from_handle(form_event.get_place_handle()))
                detail = _('Place: {place}').format(place=place)

            actions.append((get_participant_from_event(db, form_event.get_handle()), detail, actionutils.MUST_EDIT_DETAIL,
                            # action command callback
                            lambda dbstate, uistate, track, edit_detail, callback:
                                # add a residence event
                                actionutils.add_event(actionutils.make_event(type=EventType.RESIDENCE, place_handle=form_event.get_place_handle(), date_object=form_event.get_date_object(), citation_handle=citation.handle),
                                                      dbstate, uistate, track, edit_detail,
                                                      # add_event callback
                                                      lambda event, dbstate=dbstate, uistate=uistate, track=track, edit_detail=edit_detail, callback=callback:
                                                      # call the top level callback with a dummy people argument that is the list of people to who we added an event_ref to
                                                      callback(people=[actionutils.do_add_event_ref_to_person(actionutils.make_event_ref(event_handle=event.get_handle(), role=event_ref_detail[1]), event_ref_detail[0], dbstate) for event_ref_detail in event_ref_details]))))

        return (_("Add Residence event"), actions)
