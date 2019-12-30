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
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib import (Date, Event, EventType, EventRef, EventRoleType,
                            Person)

#------------------------------------------------------------------------
#
# Gramplet modules
#
#------------------------------------------------------------------------
from actionbase import ActionBase, represents_int

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

    def populate_model(self, dbstate, citation, form_event, model):
        db = dbstate.db
        parent = model.append(None, (_("Add Primary Name citation"), None, None))
        for (person, attr) in ActionBase.get_form_person_attr(db, form_event.get_handle(), 'Name'):
            model.append(parent, (name_displayer.display(person), attr.get_value(),
                         lambda dbstate, uistate, track, citation_handle = citation.handle, person_handle = person.handle: PrimaryNameCitation.command(dbstate, uistate, track, citation_handle, person_handle)))

    def command(dbstate, uistate, track, citation_handle, person_handle):
        db = dbstate.db
        person = db.get_person_from_handle(person_handle)
        person.get_primary_name().add_citation(citation_handle)
        with DbTxn(_("Add Person (%s)") % name_displayer.display(person), db) as trans:
            db.commit_person(person, trans)

class BirthEvent(ActionBase):
    def __init__(self):
        ActionBase.__init__(self)
        pass

    def populate_model(self, dbstate, citation, form_event, model):
        db = dbstate.db
        # if there is no date on the form, no actions can be performed
        if form_event.get_date_object():
            parent = model.append(None, (_("Add Birth event"), None, None))
            for (person, attr) in ActionBase.get_form_person_attr(db, form_event.get_handle(), 'Age'):
                age_string = attr.get_value()
                if age_string and represents_int(age_string):
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
                            birth_range = (birth_date - 5).get_dmy() + (False,) + birth_date.get_dmy() + (False,)
                            birth_date.set(Date.QUAL_NONE, Date.MOD_RANGE, birth_date.get_calendar(), birth_range, newyear=birth_date.get_new_year())
                        birth_date.set_quality(Date.QUAL_CALCULATED)

                        model.append(parent, (name_displayer.display(person), date_displayer.display(birth_date),
                                        lambda dbstate, uistate, track, citation_handle = citation.handle, person_handle = person.handle, birth_date_ = birth_date: ActionBase.add_event_to_person(dbstate, uistate, track, person_handle, EventType.BIRTH, birth_date_, None, citation_handle, EventRoleType.PRIMARY)))

class OccupationEvent(ActionBase):
    def __init__(self):
        ActionBase.__init__(self)
        pass

    def populate_model(self, dbstate, citation, form_event, model):
        db = dbstate.db
        parent = model.append(None, (_('Add Occupation event'), None, None))
        for (person, attr) in ActionBase.get_form_person_attr(db, form_event.get_handle(), 'Occupation'):
            occupation = attr.get_value()
            if (occupation) :
                model.append(parent, (name_displayer.display(person), occupation,
                                lambda dbstate, uistate, track, citation_handle = citation.handle, person_handle = person.handle, occupation_ = occupation: ActionBase.add_event_to_person(dbstate, uistate, track, person_handle, EventType.OCCUPATION, form_event.get_date_object(), occupation_, citation_handle, EventRoleType.PRIMARY)))
