#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013 Nick Hall
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# $Id$
#

from gi.repository import Gtk

from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gen.display.name import displayer
from gramps.gen.plug import Gramplet
from gramps.gui.dbguielement import DbGUIElement
from gramps.gui.editors import EditPerson
from gramps.gen.utils.db import get_birth_or_fallback
from gramps.gen.datehandler import get_date
from gramps.gen.errors import WindowActiveError
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    trans = glocale.get_addon_translator(__file__)
except ValueError:
    trans = glocale.translation
_ = trans.gettext

class Participants(Gramplet, DbGUIElement):
    """
    Displays the participants of an event.
    """
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)
        DbGUIElement.__init__(self, self.dbstate.db)

    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def _connect_db_signals(self):
        """
        called on init of DbGUIElement, connect to db as required.
        """
        self.callman.register_callbacks({'person-update': self.changed, 
                                         'event-update': self.changed})
        self.callman.connect_all(keys=['person', 'event'])
        #self.dbstate.db.connect('person-update', self.update)
        self.connect_signal('Event', self.update)
    
    def changed(self, handle):
        """
        Called when a registered person is updated.
        """
        self.update()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip = _('Double-click on a row to edit the selected participant.')
        self.set_tooltip(tip)
        top = Gtk.TreeView()
        titles = [('', NOSORT, 50,),
                  (_('Name'), 1, 250),
                  (_('Role'), 2, 80),
                  (_('Birth Date'), 3, 100),
                  ('', 3, 100),
                  (_('Spouses'), 4, 200)]
        self.model = ListModel(top, titles, event_func=self.edit_person)
        return top
        
    def display_participants(self, active_handle):
        """
        Display the participants of an event.
        """
        for classname, handle in \
                        self.dbstate.db.find_backlink_handles(active_handle):
            if classname == 'Person':
                self.display_person(handle, active_handle)
            elif classname == 'Family':
                self.display_family(handle, active_handle)
        self.set_has_data(self.model.count > 0)

    def display_person(self, handle, event_handle):
        """
        Display a participant in the event.
        """
        person = self.dbstate.db.get_person_from_handle(handle)
        role = self.get_role(person, event_handle)
        self.add_person(person, role)

    def display_family(self, handle, event_handle):
        """
        Display a participant in the event.
        """
        family = self.dbstate.db.get_family_from_handle(handle)
        role = self.get_role(family, event_handle)

        mother_handle = family.get_mother_handle()
        mother = self.dbstate.db.get_person_from_handle(mother_handle)
        self.add_person(mother, role)

        father_handle = family.get_father_handle()
        father = self.dbstate.db.get_person_from_handle(father_handle)
        self.add_person(father, role)

    def add_person(self, person, role):
        """
        Add a person to the model.
        """
        self.callman.register_handles({'person': [person.get_handle()]})
        name = displayer.display(person)
        spouses = self.get_spouses(person)
        birth = get_birth_or_fallback(self.dbstate.db, person)
        self.callman.register_handles({'event': [birth.get_handle()]})
        birth_date, birth_sort, birth_place = self.get_date_place(birth)
        self.model.add((person.get_handle(),
                        name,
                        role,
                        birth_date,
                        birth_sort,
                        spouses))

    def get_role(self, obj, event_handle):
        """
        Get the role of a person or family in an event.
        """
        for event_ref in obj.get_event_ref_list():
            if event_ref.ref == event_handle:
                return str(event_ref.get_role())
        return None

    def get_spouses(self, person):
        """
        Get the spouses of a given person.
        """
        spouses = []
        for handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(handle)
            father_handle = family.get_father_handle()
            if father_handle and father_handle != person.get_handle():
                self.callman.register_handles({'person': [father_handle]})
                father = self.dbstate.db.get_person_from_handle(father_handle)
                spouses.append(displayer.display(father))
            mother_handle = family.get_mother_handle()
            if mother_handle and mother_handle != person.get_handle():
                self.callman.register_handles({'person': [mother_handle]})
                mother = self.dbstate.db.get_person_from_handle(mother_handle)
                spouses.append(displayer.display(mother))
        return ' | '.join(spouses)

    def get_date_place(self, event):
        """
        Return the date and place of the given event.
        """
        event_date = ''
        event_place = ''
        event_sort = '%012d' % 0
        if event:
            event_date = get_date(event)
            event_sort = '%012d' % event.get_date_object().get_sort_value()
            handle = event.get_place_handle()
            if handle:
                place = self.dbstate.db.get_place_from_handle(handle)
                event_place = place.get_title()
        return (event_date, event_sort, event_place)

    def edit_person(self, treeview):
        """
        Edit the selected child.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            try:
                person = self.dbstate.db.get_person_from_handle(handle)
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass

    def get_has_data(self, active_handle):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_handle is None:
            return False
        for handle in self.dbstate.db.find_backlink_handles(active_handle):
            return True
        return False
        
    def update_has_data(self):
        active_handle = self.get_active('Event')
        self.set_has_data(self.get_has_data(active_handle))
    
    def main(self):
        active_handle = self.get_active('Event')
        self.model.clear()
        self.callman.unregister_all()
        if active_handle:
            self.display_participants(active_handle)
        else:
            self.set_has_data(False)
