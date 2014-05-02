# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011      Nick Hall
# Copyright (C) 2011      Tim G L Lyons
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
# $Id: SourceReferences.py 2228 2013-10-17 16:46:53Z romjerome $
#

from ListModel import ListModel, NOSORT
from Utils import navigation_label
from gen.plug import Gramplet
import gtk

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).gettext

class SourceReferences(Gramplet):
    """
    Displays the back references for an object.
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
        top = gtk.TreeView()
        titles = [(_('Type'), 0, 100),
                  (_('Name'), 1, 100),
                  ('', 2, 1), #hidden column for the handle
                  ('', 3, 1)] #hidden column for non-localized object type 
        self.model = ListModel(top, titles, event_func=self.cb_double_click)
        return top
        
    def display_backlinks(self, active_handle):
        """
        Display the back references for an object.
        """
        for classname, handle in self.dbstate.db.find_backlink_handles(active_handle):
            for classname, handle in self.dbstate.db.find_backlink_handles(handle):
                name = navigation_label(self.dbstate.db, classname, handle)[0]
                self.model.add((_(classname), name, handle, classname))
            self.set_has_data(self.model.count > 0)

    def get_has_data(self, active_handle):
        """
        Return True if the gramplet has data, else return False.
        """
        if active_handle is None:
            return False
        for classname, handle in self.dbstate.db.find_backlink_handles(active_handle):
            for classname, handle in self.dbstate.db.find_backlink_handles(handle):
                return True
        return False
        
    def cb_double_click(self, treeview):
        """
        Handle double click on treeview.
        """
        (model, iter_) = treeview.get_selection().get_selected()
        if not iter_:
            return

        (objclass, handle) = (model.get_value(iter_, 3), 
                              model.get_value(iter_, 2))

        edit_object(self.dbstate, self.uistate, objclass, handle)

    def db_changed(self):
        self.dbstate.db.connect('source-update', self.update)
        self.connect_signal('Source', self.update)

    def update_has_data(self):
        active_handle = self.get_active('Source')
        self.set_has_data(self.get_has_data(active_handle))
    
    def main(self):
        active_handle = self.get_active('Source')
        self.model.clear()
        if active_handle:
            self.display_backlinks(active_handle)
        else:
            self.set_has_data(False)

def edit_object(dbstate, uistate, reftype, ref):
    """
    Invokes the appropriate editor for an object type and given handle.
    """
    from gui.editors import (EditEvent, EditPerson, EditFamily, EditSource,
                             EditPlace, EditMedia, EditRepository,
                             EditCitation)

    if reftype == 'Person':
        try:
            person = dbstate.db.get_person_from_handle(ref)
            EditPerson(dbstate, uistate, [], person)
        except Errors.WindowActiveError:
            pass
    elif reftype == 'Family':
        try:
            family = dbstate.db.get_family_from_handle(ref)
            EditFamily(dbstate, uistate, [], family)
        except Errors.WindowActiveError:
            pass
    elif reftype == 'Source':
        try:
            source = dbstate.db.get_source_from_handle(ref)
            EditSource(dbstate, uistate, [], source)
        except Errors.WindowActiveError:
            pass
    elif reftype == 'Citation':
        try:
            citation = dbstate.db.get_citation_from_handle(ref)
            EditCitation(dbstate, uistate, [], citation)
        except Errors.WindowActiveError:
            """
            Return the text used when citation cannot be edited
            """
            blocked_text = _("Cannot open new citation editor at this time. "
                             "Either the citation is already being edited, "
                             "or the associated source is already being "
                             "edited, and opening a citation editor "
                             "(which also allows the source "
                             "to be edited), would create ambiguity "
                             "by opening two editors on the same source. "
                             "\n\n"
                             "To edit the citation, close the source "
                             "editor and open an editor for the citation "
                             "alone")
            
            from QuestionDialog import WarningDialog
            WarningDialog(_("Cannot open new citation editor"),
                          blocked_text)
    elif reftype == 'Place':
        try:
            place = dbstate.db.get_place_from_handle(ref)
            EditPlace(dbstate, uistate, [], place)
        except Errors.WindowActiveError:
            pass
    elif reftype == 'MediaObject':
        try:
            obj = dbstate.db.get_object_from_handle(ref)
            EditMedia(dbstate, uistate, [], obj)
        except Errors.WindowActiveError:
            pass
    elif reftype == 'Event':
        try:
            event = dbstate.db.get_event_from_handle(ref)
            EditEvent(dbstate, uistate, [], event)
        except Errors.WindowActiveError:
            pass
    elif reftype == 'Repository':
        try:
            repo = dbstate.db.get_repository_from_handle(ref)
            EditRepository(dbstate, uistate, [], repo)
        except Errors.WindowActiveError:
            pass
