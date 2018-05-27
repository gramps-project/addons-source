#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2015 Nick Hall
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

"""
Form Gramplet.
"""

import os

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gui.dbguielement import DbGUIElement
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.datehandler import get_date
from gramps.gen.errors import WindowActiveError
from gramps.gen.lib import Citation
from editform import EditForm
from selectform import SelectForm
from form import get_form_citation

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
# FormGramplet class
#
#------------------------------------------------------------------------
class FormGramplet(Gramplet, DbGUIElement):
    """
    Gramplet to display form events for the active person.
    It allows a form to be created or edited with a form editor.
    """
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)
        DbGUIElement.__init__(self, self.dbstate.db)

    def init(self):
        """
        Initialise the gramplet.
        """
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()

    def _connect_db_signals(self):
        """
        called on init of DbGUIElement, connect to db as required.
        """
        self.callman.register_callbacks({'person-update': self.changed})
        self.callman.register_callbacks({'event-update': self.changed})
        self.callman.connect_all(keys=['person', 'event'])

    def changed(self, handle):
        """
        Called when a registered event is updated.
        """
        self.update()

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.model = Gtk.ListStore(object, str, str, str, str)
        view = Gtk.TreeView(self.model)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Source"), renderer, text=1)
        view.append_column(column)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Role"), renderer, text=2)
        view.append_column(column)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Date"), renderer, text=3)
        view.append_column(column)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Place"), renderer, text=4)
        view.append_column(column)
        view.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        view.connect("button_press_event", self.__list_clicked)

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.START)

        new = Gtk.Button(label=_('_New'), use_underline=True)
        new.connect("clicked", self.__new_form)
        button_box.add(new)

        edit = Gtk.Button(label=_('_Edit'), use_underline=True)
        edit.connect("clicked", self.__edit_form, view.get_selection())
        button_box.add(edit)

        vbox.pack_start(view, expand=True, fill=True, padding=0)
        vbox.pack_end(button_box, expand=False, fill=True, padding=4)

        return vbox

    def __list_clicked(self, view, event):
        """
        Called when the user clicks on the list of forms.
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.__edit_form(view, view.get_selection())

    def __new_form(self, widget):
        """
        Create a new form and invoke the editor.
        """
        sel = SelectForm(self.dbstate, self.uistate, [])
        source_handle = sel.run()
        if source_handle:
            citation = Citation()
            citation.set_reference_handle(source_handle)
            try:
                EditForm(self.gui.dbstate, self.gui.uistate, [], citation,
                         self.update)
            except WindowActiveError:
                pass

    def __edit_form(self, widget, selection):
        """
        Edit the selected form.
        """
        model, iter_ = selection.get_selected()
        if iter_:
            citation = model.get_value(iter_, 0)
            try:
                EditForm(self.gui.dbstate, self.gui.uistate, [], citation,
                         self.update)
            except WindowActiveError:
                pass

    def main(self):
        """
        Called to update the display.
        """
        self.model.clear()
        active_person = self.get_active_object("Person")
        if not active_person:
            return

        self.callman.unregister_all()
        self.callman.register_obj(active_person)
        self.callman.register_handles({'person': [active_person.get_handle()]})

        for event_ref in active_person.get_event_ref_list():
            self.add_event_ref(event_ref)
        for family_handle in active_person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            for event_ref in family.get_event_ref_list():
                self.add_event_ref(event_ref)

    def add_event_ref(self, event_ref):
        db = self.dbstate.db
        event = db.get_event_from_handle(event_ref.ref)
        if event:
            role_text = str(event_ref.role)
            place_text = place_displayer.display_event(db, event)
            citation = get_form_citation(db, event)
            if citation:
                source_handle = citation.get_reference_handle()
                source = db.get_source_from_handle(source_handle)
                source_text = source.get_title()
                self.model.append((citation,
                                  source_text,
                                  role_text,
                                  get_date(event),
                                  place_text))

    def active_changed(self, handle):
        """
        Called when the active person is changed.
        """
        self.update()

    def db_changed(self):
        """
        Called when the active person is changed.
        """
        self.update()
