# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013-2016 Nick Hall
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

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gui.editors import EditEvent
from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gen.plug import Gramplet
from gramps.gen.lib import AttributeType
from gramps.gen.datehandler import get_date
from gramps.gen.errors import WindowActiveError

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

#------------------------------------------------------------------------
#
# Overview class
#
#------------------------------------------------------------------------
class Overview(Gramplet):
    """
    Displays an overview of events for a person or family.
    """
    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip = _('Double-click on a row to edit the selected event.')
        self.set_tooltip(tip)
        top = Gtk.TreeView()
        titles = [('', NOSORT, 50,),
                  (_('Type'), 1, 100),
                  (_('Date'), 3, 100),
                  ('', 3, 100),
                  (_('Age'), 4, 35),
                  (_('Where Born'), 5, 160),
                  (_('Condition'), 6, 75),
                  (_('Occupation'), 7, 160),
                  (_('Residence'), 8, 160)]
        self.model = ListModel(top, titles, event_func=self.edit_event)
        return top

    def add_event_ref(self, event_ref, spouse=None):
        """
        Add an event to the model.
        """
        values = self.get_attributes(event_ref)
        event = self.dbstate.db.get_event_from_handle(event_ref.ref)
        event_date = get_date(event)
        event_sort = '%012d' % event.get_date_object().get_sort_value()
        self.model.add((event.get_handle(),
                        str(event.get_type()),
                        event_date,
                        event_sort,
                        values[0],
                        values[1],
                        values[2],
                        values[3],
                        values[4]
                        ))

    def get_attributes(self, event_ref):
        """
        Get selected attributes from event reference.
        """
        values = [''] * 5
        for attr in event_ref.get_attribute_list():
            if attr.get_type() == AttributeType.AGE:
                values[0] = attr.get_value()
            elif str(attr.get_type()) == _('Where Born'):
                values[1] = attr.get_value()
            elif str(attr.get_type()) == _('Condition'):
                values[2] = attr.get_value()
            elif str(attr.get_type()) == _('Occupation'):
                values[3] = attr.get_value()
            elif str(attr.get_type()) == _('Residence'):
                values[4] = attr.get_value()
        return values

    def edit_event(self, treeview):
        """
        Edit the selected event.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            try:
                event = self.dbstate.db.get_event_from_handle(handle)
                EditEvent(self.dbstate, self.uistate, [], event)
            except WindowActiveError:
                pass

class PersonOverview(Overview):
    """
    Displays an overview of events for a person.
    """
    def db_changed(self):
        self.dbstate.db.connect('person-update', self.update)

    def active_changed(self, handle):
        self.update()

    def update_has_data(self):
        active_handle = self.get_active('Person')
        active = self.dbstate.db.get_person_from_handle(active_handle)
        self.set_has_data(self.get_has_data(active))

    def get_has_data(self, active_person):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_person:
            if active_person.get_event_ref_list():
                return True
            for family_handle in active_person.get_family_handle_list():
                family = self.dbstate.db.get_family_from_handle(family_handle)
                for event_ref in family.get_event_ref_list():
                    return True
        return False

    def main(self): # return false finishes
        active_handle = self.get_active('Person')

        self.model.clear()
        if active_handle:
            self.display_person(active_handle)
        else:
            self.set_has_data(False)

    def display_person(self, active_handle):
        """
        Display the events for the active person.
        """
        active_person = self.dbstate.db.get_person_from_handle(active_handle)
        for event_ref in active_person.get_event_ref_list():
            self.add_event_ref(event_ref)
        for family_handle in active_person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            if father_handle == active_handle:
                spouse = self.dbstate.db.get_person_from_handle(mother_handle)
            else:
                spouse = self.dbstate.db.get_person_from_handle(father_handle)
            for event_ref in family.get_event_ref_list():
                self.add_event_ref(event_ref, spouse)
        self.set_has_data(self.model.count > 0)

class FamilyOverview(Overview):
    """
    Displays an overview of events for a family.
    """
    def db_changed(self):
        self.dbstate.db.connect('family-update', self.update)
        self.connect_signal('Family', self.update)

    def update_has_data(self):
        active_handle = self.get_active('Family')
        active = self.dbstate.db.get_family_from_handle(active_handle)
        self.set_has_data(self.get_has_data(active))

    def get_has_data(self, active_family):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_family:
            for event_ref in active_family.get_event_ref_list():
                return True
        return False

    def main(self): # return false finishes
        active_handle = self.get_active('Family')

        self.model.clear()
        if active_handle:
            self.display_family(active_handle)
        else:
            self.set_has_data(False)

    def display_family(self, active_handle):
        """
        Display the events for the active family.
        """
        active_family = self.dbstate.db.get_family_from_handle(active_handle)
        for event_ref in active_family.get_event_ref_list():
            self.add_event_ref(event_ref)
        self.set_has_data(self.model.count > 0)
