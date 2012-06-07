# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
# Copyright (C) 2011 Gary Burton
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

from gui.listmodel import ListModel, NOSORT
from gui.plug.quick import run_quick_report_by_name
from gen.plug import Gramplet
from gen.ggettext import gettext as _
import gen.lib
import gen.datehandler
import gtk
from gui.editors import EditPerson, EditFamily, EditEventRef
from gen.errors import WindowActiveError
from gen.db import DbTxn
from gen.display.name import displayer as name_displayer

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
                  (_('Value'), 3, 100),
                  ('', NOSORT, 50,)
                 ]
        self.model = ListModel(top, titles, event_func=self._display_editor)
        return top

    def add_attributes(self, obj, date_object=None):
        """
        Add the attributes of an object to the model.
        """
        event_date = event_sort = handle = ''
        if date_object is not None:
            event_date = gen.datehandler.displayer.display(date_object)
            event_sort = '%012d' % date_object.get_sort_value()

        try:
            handle = obj.get_handle()
        except AttributeError:
            handle = obj.ref
         
        for attr in obj.get_attribute_list():
            self.model.add((event_date,
                            event_sort,
                            attr.get_type(),
                            attr.get_value(),
                            handle
                            ))

    def display_attributes(self, obj):
        """
        Display the attributes of an object.
        """
        self.add_attributes(obj)

        for event_ref in obj.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            event_date = event.get_date_object()
            self.add_attributes(event, event_date)
            self.add_attributes(event_ref, event_date)

        self.set_has_data(self.model.count > 0)
        
    def _display_editor(self, treeview):
        """
        Display the appropriate editor window for the attribute.
        """
        pass

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

    def _get_event_ref(self, event):
        """
        Return the event reference belonging to the active person or
        family for the given event. 
        """
        for event_ref in self.object_for_update.get_event_ref_list():
            if event_ref.ref == event.get_handle():
                return event_ref
        return None

    def _object_edited(self, ref, event):
        pass

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
        active = self.get_active_object('Person')
        self.set_has_data(self.get_has_data(active))

    def _object_edited(self, ref, event):
        """
        Callback method for committing changes to the active person after an
        event ref has been modified.
        """
        with DbTxn('', self.dbstate.db) as trans:
            self.dbstate.db.commit_person(self.object_for_update, trans)
            msg = _("Edit Person (%s)") % \
                    name_displayer.display(self.object_for_update)
            trans.set_description(msg)

    def _display_editor(self, treeview):
        """
        Display the appropriate editor - either event ref or person
        editor depending on the which type of object the handle belongs to
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 4)

            event = self.dbstate.db.get_event_from_handle(handle)
            if event:
                event_ref = self._get_event_ref(event) 
                try:
                    EditEventRef(self.dbstate,
                                 self.uistate,
                                 [],
                                 event,
                                 event_ref,
                                 self._object_edited)
                except WindowActiveError:
                    pass
                return

            person = self.dbstate.db.get_person_from_handle(handle)
            if person:
                try:
                    EditPerson(self.dbstate, self.uistate, [], person)
                except WindowActiveError:
                    pass
    
    def main(self):
        self.model.clear()
        active = self.get_active_object('Person')

        # Keep a pointer to the active person in case the user decides to
        # modify an event ref attribute and we need to commit the change
        self.object_for_update = active

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
        active = self.get_active_object('Family')
        self.set_has_data(self.get_has_data(active))
    
    def _object_edited(self, ref, event):
        """
        Callback method for committing changes to the active person after an
        event ref has been modified.
        """
        with DbTxn(_("Edit Family"), self.dbstate.db) as trans:
            self.dbstate.db.commit_family(self.object_for_update, trans)

    def _display_editor(self, treeview):
        """
        Display the appropriate editor - either event ref or family
        editor depending on the which type of object the handle belongs to
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 4)

            event = self.dbstate.db.get_event_from_handle(handle)
            if event:
                event_ref = self._get_event_ref(event) 
                try:
                    EditEventRef(self.dbstate,
                                 self.uistate,
                                 [],
                                 event,
                                 event_ref,
                                 self._object_edited)
                except WindowActiveError:
                    pass
                return

            family = self.dbstate.db.get_family_from_handle(handle)
            if family:
                try:
                    EditFamily(self.dbstate, self.uistate, [], family)
                except WindowActiveError:
                    pass

    def main(self):
        self.model.clear()
        active = self.get_active_object('Family')
        
        # Keep a pointer to the active family in case the user decides to
        # modify an event ref attribute and we need to commit the change
        self.object_for_update = active

        if active:
            self.display_attributes(active)
        else:
            self.set_has_data(False)
