# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
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

from ListModel import ListModel, NOSORT
from QuickReports import run_quick_report_by_name
from gen.plug import Gramplet
from gen.ggettext import gettext as _
import DateHandler
import gtk

class Attributes(Gramplet):
    """
    Displays the attributes of an object.
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
        tip = _('Double-click on a row to view a quick report showing '
                'all people with the selected attribute.')
        self.set_tooltip(tip)
        top = gtk.TreeView()
        titles = [(_('Date'), 1, 100),
                  ('', 1, 100),
                  (_('Key'), 2, 100),
                  (_('Value'), 3, 100)]
        self.model = ListModel(top, titles, event_func=self.display_report)
        return top

    def add_attributes(self, obj, date_object=None):
        """
        Add the attributes of an object to the model.
        """
        event_date = event_sort = ''
        if date_object is not None:
            event_date = DateHandler.displayer.display(date_object)
            event_sort = '%012d' % date_object.get_sort_value()

        for attr in obj.get_attribute_list():
            self.model.add((event_date,
                            event_sort,
                            attr.get_type(),
                            attr.get_value()))

    def display_attributes(self, obj):
        """
        Display the attributes of an object.
        """
        self.add_attributes(obj)

        for event_ref in obj.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            event_date = event.get_date_object()
            self.add_attributes(event_ref, event_date)

        self.set_has_data(self.model.count > 0)
        
    def display_report(self, treeview):
        """
        Display the quick report for matching attribute key.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            key = model.get_value(iter_, 2)
            run_quick_report_by_name(self.dbstate, 
                                     self.uistate, 
                                     'attribute_match', 
                                     key)

    def get_has_data(self, obj):
        """
        Return True if the gramplet has data, else return False.
        """
        if obj is None: 
            return False
        if obj.get_attribute_list():
            return True
        for event_ref in obj.get_event_ref_list():
            if event_ref.get_attribute_list():
                return True
        return False

class ExtendedPersonAttributes(Attributes):
    """
    Displays the attributes of a person.
    """
    def db_changed(self):
        self.dbstate.db.connect('person-update', self.update)
        self.update()

    def active_changed(self, handle):
        self.update()

    def update_has_data(self):
        active_handle = self.get_active('Person')
        active = self.dbstate.db.get_person_from_handle(active_handle)
        self.set_has_data(self.get_has_data(active))
    
    def main(self):
        active_handle = self.get_active('Person')
        active = self.dbstate.db.get_person_from_handle(active_handle)

        self.model.clear()
        if active:
            self.display_attributes(active)
        else:
            self.set_has_data(False)

class ExtendedFamilyAttributes(Attributes):
    """
    Displays the attributes of an event.
    """
    def db_changed(self):
        self.dbstate.db.connect('family-update', self.update)
        self.connect_signal('Family', self.update)
        self.update()

    def update_has_data(self):
        active_handle = self.get_active('Family')
        active = self.dbstate.db.get_family_from_handle(active_handle)
        self.set_has_data(self.get_has_data(active))
    
    def main(self):
        active_handle = self.get_active('Family')
        active = self.dbstate.db.get_family_from_handle(active_handle)

        self.model.clear()
        if active:
            self.display_attributes(active)
        else:
            self.set_has_data(False)
