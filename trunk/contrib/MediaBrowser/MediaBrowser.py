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

from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gen.utils.db import navigation_label
from gramps.gen.plug import Gramplet
from gramps.gui.widgets import Photo
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext
from gramps.gen.utils.file import media_path_full
from gi.repository import Gtk

class MediaBrowser(Gramplet):
    """
    Displays an object tree and a media preview for a person.
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
        top = Gtk.HBox()
        self.photo = Photo()
        self.photo.show()
        view = Gtk.TreeView()
        titles = [(_('Object'), 1, 250)]
        self.model = ListModel(view, titles, list_mode="tree",
                               select_func=self.row_selected)
        top.pack_start(view, True, True, 0)
        top.pack_start(self.photo, True, False, 5)
        top.show_all()
        return top
        
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
        self.photo.set_image(None)
        if active:
            self.display_data(active)
        else:
            self.set_has_data(False)

    def display_data(self, person):
        """
        Display the object tree for the active person.
        """
        self.add_media(person)
        self.add_events(person)
        self.add_sources(person)
        self.set_has_data(self.model.count > 0)

    def add_events(self, obj, parent_node=None):
        """
        Add event nodes to the model.
        """
        for event_ref in obj.get_event_ref_list():
            handle = event_ref.ref
            name, event = navigation_label(self.dbstate.db, 'Event', handle)
            node = self.model.add([name], node=parent_node)
            self.add_sources(event, node)
            self.add_media(event, node)

    def add_sources(self, obj, parent_node=None):
        """
        Add source nodes to the model.
        """
        for citation_handle in obj.get_citation_list():
            citation = self.dbstate.db.get_citation_from_handle(citation_handle)
            handle = citation.get_reference_handle()
            name, src = navigation_label(self.dbstate.db, 'Source', handle)
            node = self.model.add([name], node=parent_node)
            self.add_media(src, node)

    def add_media(self, obj, parent_node=None):
        """
        Add media object nodes to the model.
        """
        for media_ref in obj.get_media_list():
            handle = media_ref.ref
            name, media = navigation_label(self.dbstate.db, 'Media', handle)
            full_path = media_path_full(self.dbstate.db, media.get_path())
            rect = media_ref.get_rectangle()
            self.model.add([name], info=media_ref, node=parent_node)

    def row_selected(self, selection):
        """
        Change the image when a row is selected.
        """
        selected = self.model.get_selected_objects()
        if selected:
            if selected[0]:
                self.load_image(selected[0])
            else:
                self.photo.set_image(None)
        else:
            self.photo.set_image(None)

    def load_image(self, media_ref):
        """
        Display an image from the given media reference.
        """
        media = self.dbstate.db.get_object_from_handle(media_ref.ref)
        full_path = media_path_full(self.dbstate.db, media.get_path())
        mime_type = media.get_mime_type()
        rectangle = media_ref.get_rectangle()
        self.photo.set_image(full_path, mime_type, rectangle)

    def get_has_data(self, person):
        """
        Return True if the gramplet has data, else return False.
        """
        if person.get_event_ref_list():
            return True
        if person.get_citation_list():
            return True
        if person.get_media_list():
            return True
        return False
