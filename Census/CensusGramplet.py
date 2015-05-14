#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Nick Hall
#               2011 Gary Burton
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

"""
Census Gramplet.
"""
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
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.datehandler import get_date, displayer
from gramps.gen.errors import WindowActiveError
from gramps.gen.lib import (Event, EventType, EventRef, EventRoleType,
                            Citation, Person, Attribute)
from gramps.gen.db import DbTxn

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
# Gramplet class
#
#------------------------------------------------------------------------
class CensusGramplet(Gramplet, DbGUIElement):
    """
    Gramplet to display census events for the active person.
    It allows a census to be created or edited with a census editor.
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
        vbox = Gtk.VBox()

        self.model = Gtk.ListStore(object, str, str, str)
        view = Gtk.TreeView(self.model)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Source"), renderer, text=1)
        view.append_column(column)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Date"), renderer, text=2)
        view.append_column(column)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_("Place"), renderer, text=3)
        view.append_column(column)
        view.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        view.connect("button_press_event", self.__list_clicked)
        
        button_box = Gtk.HButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.START)
        
        new = Gtk.Button(stock=Gtk.STOCK_NEW)
        new.connect("clicked", self.__new_census)
        button_box.add(new)
                
        edit = Gtk.Button(stock=Gtk.STOCK_EDIT)
        edit.connect("clicked", self.__edit_census, view.get_selection())
        button_box.add(edit)
      
        vbox.pack_start(view, expand=True, fill=True, padding=0)
        vbox.pack_end(button_box, expand=False, fill=True, padding=4)
        
        return vbox

    def __list_clicked(self, view, event):
        """
        Called when the user clicks on the list of censuses.
        """
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self.__edit_census(view, view.get_selection())

    def __new_census(self, widget):
        """
        Create a new census and invoke the editor.
        """
        event = Event()
        event.set_type(EventType.CENSUS)
        try:
            CensusEditor(self.gui.dbstate, self.gui.uistate, [], event)
        except WindowActiveError:
            pass

    def __edit_census(self, widget, selection):
        """
        Edit the selected census.
        """
        model, iter_ = selection.get_selected()
        if iter_:
            event = model.get_value(iter_, 0)
            try:
                CensusEditor(self.gui.dbstate, self.gui.uistate, [], event)
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

        db = self.dbstate.db
        for event_ref in active_person.get_event_ref_list():
            if event_ref:
                event = db.get_event_from_handle(event_ref.ref)
                if event:
                    if event.get_type() == EventType.CENSUS:

                        p_handle = event.get_place_handle()
                        if p_handle:
                            place = db.get_place_from_handle(p_handle)
                            place_text = place.get_title()
                        else:
                            place_text = ''
                            
                        citation = get_census_citation(db, event)
                        if citation:
                            source_handle = citation.get_reference_handle()
                            source = db.get_source_from_handle(source_handle)
                            source_text = source.get_title()
                            self.model.append((event,
                                              source_text,
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

#------------------------------------------------------------------------
#
# Census Editor
#
#------------------------------------------------------------------------
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.editors.objectentries import PlaceEntry
from gramps.gui.widgets import MonitoredEntry
from gramps.gui.editors import EditPerson
from gramps.gui.display import display_help
from gramps.gui.dialog import ErrorDialog
from Census import ORDER_ATTR
from Census import (get_census_date, get_census_columns, get_census_headings,
                    get_census_citation, get_census_sources, get_report_columns)
from gramps.gui.selectors import SelectorFactory
from gramps.gui.editors.displaytabs import GalleryTab, GrampsTab
from gramps.gen.config import config

class CensusEditor(ManagedWindow):
    """
    Census Editor.
    """
    def __init__(self, dbstate, uistate, track, event):

        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        self.db = dbstate.db
        
        self.event = event
        self.citation = get_census_citation(self.db, self.event)
        if self.citation is None:
            self.citation = Citation()

        ManagedWindow.__init__(self, uistate, track, event)

        self.widgets = {}
        top = self.__create_gui()
        self.set_window(top, None, self.get_menu_title())

        self._config = config.get_manager('census')
        width = self._config.get('interface.census-width')
        height = self._config.get('interface.census-height')
        self.window.resize(width, height)

        self.place_field = PlaceEntry(self.dbstate, self.uistate, self.track,
                                      self.widgets['place_text'],
                                      self.event.set_place_handle,
                                      self.event.get_place_handle,
                                      self.widgets['place_add'],
                                      self.widgets['place_share'])

        self.ref_field = MonitoredEntry(
            self.widgets['ref_entry'], 
            self.citation.set_page, 
            self.citation.get_page, 
            self.db.readonly)

        if self.event.get_handle():
            self.widgets['census_combo'].set_sensitive(False)
            self.__populate_gui(event)
            self.details.populate_gui(event)

    def _add_tab(self, notebook, page):
        notebook.append_page(page, page.get_tab_widget())
        page.label.set_use_underline(True)
        return page

    def get_menu_title(self):
        """
        Get the menu title.
        """
        if self.event.get_handle():
            date = get_date(self.event)
            if not date:
                date = 'unknown'
            dialog_title = _('Census: %s')  % date
        else:
            dialog_title = _('New Census')
        return dialog_title

    def build_menu_names(self, event):
        """
        Build menu names. Overrides method in ManagedWindow.
        """
        return (_('Edit Census'), self.get_menu_title())

    def __create_gui(self):
        """
        Create and display the GUI components of the editor.
        """
        root = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        root.set_transient_for(self.uistate.window)

        vbox = Gtk.VBox()

        tab = Gtk.Table(4, 4, False)
        tab.set_row_spacings(10)
        tab.set_col_spacings(10)

        census_label = Gtk.Label(_("Source:"))
        census_label.set_alignment(0.0, 0.5)
        tab.attach(census_label, 0, 1, 0, 1,
                   xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        liststore = Gtk.ListStore(str, str, str)
        for row in get_census_sources(self.db):
            liststore.append([row[0].decode(), row[1], row[2]])

        census_combo = Gtk.ComboBox()
        census_combo.set_model(liststore)
        cell = Gtk.CellRendererText()
        census_combo.pack_start(cell, True)
        census_combo.add_attribute(cell, 'text', 1)
        #cell = Gtk.CellRendererText()
        #census_combo.pack_start(cell, True)
        #census_combo.add_attribute(cell, 'text', 2)
        census_combo.connect('changed', self.__census_changed)
        self.widgets['census_combo'] = census_combo
        
        hbox = Gtk.HBox()
        hbox.pack_start(census_combo, False, True, 0)
        tab.attach(hbox, 1, 2, 0, 1)

        date_label = Gtk.Label(_("Date:"))
        date_label.set_alignment(0.0, 0.5)
        tab.attach(date_label, 0, 1, 1, 2,
                   xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        date_text = Gtk.Label()
        date_text.set_alignment(0.0, 0.5)
        tab.attach(date_text, 1, 2, 1, 2)
        self.widgets['date_text'] = date_text
        
        ref_label = Gtk.Label(_("Reference:"))
        ref_label.set_alignment(0.0, 0.5)
        tab.attach(ref_label, 0, 1, 2, 3,
                   xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        ref_entry = Gtk.Entry()
        tab.attach(ref_entry, 1, 2, 2, 3)
        self.widgets['ref_entry'] = ref_entry

        place_label = Gtk.Label(_("Place:"))
        place_label.set_alignment(0.0, 0.5)
        tab.attach(place_label, 0, 1, 3, 4,
                   xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        place_text = Gtk.Label()
        place_text.set_alignment(0.0, 0.5)
        tab.attach(place_text, 1, 2, 3, 4)
        self.widgets['place_text'] = place_text

        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_INDEX, Gtk.IconSize.BUTTON)
        place_share = Gtk.Button()
        place_share.set_relief(Gtk.ReliefStyle.NONE)
        place_share.add(image)
        tab.attach(place_share, 2, 3, 3, 4, xoptions=0)
        self.widgets['place_share'] = place_share

        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.BUTTON)
        place_add = Gtk.Button()
        place_add.set_relief(Gtk.ReliefStyle.NONE)
        place_add.add(image)
        tab.attach(place_add, 3, 4, 3, 4, xoptions=0)
        self.widgets['place_add'] = place_add
 
        button_box = Gtk.HButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)
        
        help_btn = Gtk.Button(stock=Gtk.STOCK_HELP)
        help_btn.connect('clicked', self.help_clicked)
        button_box.add(help_btn)
        button_box.set_child_secondary(help_btn, True)

        cancel_btn = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        cancel_btn.connect('clicked', self.close)
        button_box.add(cancel_btn)
        
        ok_btn = Gtk.Button(stock=Gtk.STOCK_OK)
        ok_btn.connect('clicked', self.save)
        button_box.add(ok_btn)

        notebook = Gtk.Notebook()

        self.details = DetailsTab(self.dbstate,
                                       self.uistate,
                                       self.track,
                                       self.event,
                                       census_combo)
        self._add_tab(notebook, self.details)

        self.headings = HeadingsTab(self.dbstate,
                                       self.uistate,
                                       self.track,
                                       self.event,
                                       census_combo)
        self._add_tab(notebook, self.headings)

        self.gallery_list = GalleryTab(self.dbstate,
                                       self.uistate,
                                       self.track,
                                       self.citation.get_media_list())
        self._add_tab(notebook, self.gallery_list)

        vbox.pack_start(tab, expand=False, fill=True, padding=10)
        vbox.pack_start(notebook, expand=True, fill=True, padding=0)
        vbox.pack_end(button_box, expand=False, fill=True, padding=10)
        
        root.add(vbox)
        root.show_all()

        notebook.set_current_page(0)

        return root

    def __populate_gui(self, event):
        """
        Populate the GUI for a given census event.
        """
        census_combo = self.widgets['census_combo']
        for pos, row in enumerate(census_combo.get_model()):
            if row[0] == self.citation.get_reference_handle():
                census_combo.set_active(pos)
                
        date_text = self.widgets['date_text']
        date_text.set_text(get_date(event))

    def __census_changed(self, combo):
        """
        Called when the user selects a new census from the combo box.
        """
        model = combo.get_model()
        index = combo.get_active()
        census_id = model[index][2]

        # Set date
        census_date = get_census_date(census_id)

        date_text = self.widgets['date_text']
        date_text.set_text(displayer.display(census_date))
        self.event.set_date_object(census_date)
        self.citation.set_date_object(census_date)

        # Set source
        self.citation.set_reference_handle(model[index][0])

        # Set new columns
        columns = get_census_columns(census_id)
        report_columns = get_report_columns(census_id)
        self.details.create_table(columns, report_columns)
        heading_list = get_census_headings(census_id)
        self.headings.create_table(heading_list)

    def save(self, button):
        """
        Called when the user clicks the OK button.
        """
        if self.widgets['census_combo'].get_active() == -1:
            ErrorDialog(_('Census Editor'),
                        _('Cannot save this census.  First select '
                          'a census from the drop-down list.'))
            return

        with DbTxn(self.get_menu_title(), self.db) as trans:
            if not self.event.get_handle():
                self.db.add_event(self.event, trans)

            self.headings.save()
            self.details.save(trans)

            citation_handle = self.citation.get_handle()
            if not citation_handle:
                citation_handle = self.db.add_citation(self.citation, trans)
                self.event.add_citation(citation_handle)
            else:
                self.db.commit_citation(self.citation, trans)

            self.db.commit_event(self.event, trans)
        self.close()

    def close(self, *args):
        """
        Close the editor window.
        """
        (width, height) = self.window.get_size()
        self._config.set('interface.census-width', width)
        self._config.set('interface.census-height', height)
        self._config.save()
        self.details.entry_grid.clean_up()
        self.details.clean_up()
        self.gallery_list.clean_up()
        ManagedWindow.close(self)

    def help_clicked(self, obj):
        """
        Display the relevant portion of GRAMPS manual
        """
        display_help(webpage='Census_Addons')

#------------------------------------------------------------------------
#
# Details Tab
#
#------------------------------------------------------------------------
class DetailsTab(GrampsTab):
    """
    Details tab in the census editor.
    """
    SelectPerson = SelectorFactory('Person')

    def __init__(self, dbstate, uistate, track, event, source_combo):
        GrampsTab.__init__(self, dbstate, uistate, track, _('Details'))
        self.db = dbstate.db
        self.event = event
        self.source_combo = source_combo
        self.model = None
        self.columns = []
        self.initial_people = []
        self._set_label()

    def get_icon_name(self):
        return 'gramps-attribute'

    def build_interface(self):
        """
        Builds the interface.
        """
        hbox = Gtk.HBox()
        
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.BUTTON)
        add_btn = Gtk.Button()
        add_btn.set_relief(Gtk.ReliefStyle.NONE)
        add_btn.add(image)
        add_btn.connect('clicked', self.__add_person)
        hbox.pack_start(add_btn, expand=False, fill=True, padding=3)
        
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_INDEX, Gtk.IconSize.BUTTON)
        share_btn = Gtk.Button()
        share_btn.set_relief(Gtk.ReliefStyle.NONE)
        share_btn.add(image)
        share_btn.connect('clicked', self.__share_person)
        hbox.pack_start(share_btn, expand=False, fill=True, padding=3)
        
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_REMOVE, Gtk.IconSize.BUTTON)
        del_btn = Gtk.Button()
        del_btn.set_relief(Gtk.ReliefStyle.NONE)
        del_btn.add(image)
        del_btn.connect('clicked', self.__remove_person)
        hbox.pack_start(del_btn, expand=False, fill=True, padding=3)

        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_GO_UP, Gtk.IconSize.BUTTON)
        up_btn = Gtk.Button()
        up_btn.set_relief(Gtk.ReliefStyle.NONE)
        up_btn.add(image)
        up_btn.connect('clicked', self.__move_person, 'up')
        hbox.pack_start(up_btn, expand=False, fill=True, padding=3)

        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_GO_DOWN, Gtk.IconSize.BUTTON)
        down_btn = Gtk.Button()
        down_btn.set_relief(Gtk.ReliefStyle.NONE)
        down_btn.add(image)
        down_btn.connect('clicked', self.__move_person, 'down')
        hbox.pack_start(down_btn, expand=False, fill=True, padding=3)

        self.entry_grid = EntryGrid(callback=self.change_person)
        self.track_ref_for_deletion("entry_grid")
        
        scrollwin = Gtk.ScrolledWindow()
        scrollwin.add_with_viewport(self.entry_grid)
        scrollwin.set_policy(Gtk.PolicyType.AUTOMATIC, 
                             Gtk.PolicyType.AUTOMATIC)

        self.pack_start(hbox, expand=False, fill=True, padding=0)
        self.pack_start(scrollwin, expand=True, fill=True, padding=0)

    def is_empty(self):
        """
        Indicate if the tab contains any data. This is used to determine
        how the label should be displayed.
        """
        if self.model is None:
            return True
        return len(self.model) == 0

    def __add_person(self, button):
        """
        Create a new person and add them to the census.
        """
        if self.source_combo.get_active() == -1:
            ErrorDialog(_('Census Editor'),
                        _('Cannot add a person to this census.  First select '
                          'a census from the drop-down list.'))
            return
            
        person = Person()
        EditPerson(self.dbstate, self.uistate, self.track, person,
                   self.__person_added)

    def __person_added(self, person):
        """
        Called when a person is added to the census.
        """
        self.model.append(self.__new_person_row(person))
        self.source_combo.set_sensitive(False)
        self._set_label()

    def __edit_person(self, treeview, path, view_column):
        """
        Edit a person from selection.
        """
        model, iter_ = self.selection.get_selected()
        if iter_: 
            handle = model.get_value(iter_, 0)
            if handle:
                person = self.dbstate.db.get_person_from_handle(handle)
                EditPerson(self.dbstate, self.uistate, self.track, person)
        
    def __share_person(self, button):
        """
        Select an existing person and add them to the census.
        """
        if self.source_combo.get_active() == -1:
            ErrorDialog(_('Cannot add a person to this census.'),
                        _('First select a census from the drop-down list.'))
            return

        skip_list = []
        handle = None
        if len(self.model) > 0:
            iter_ = self.entry_grid.get_selected()
            if iter_: # get from selection:
                handle = self.model.get_value(iter_, 0)
            else: # get from first row
                handle = self.model[0][0]
        else: # no rows, let's try to get active person:
            handle = self.uistate.get_active('Person')

        sel = self.SelectPerson(self.dbstate, self.uistate, self.track,
                   _("Select Person"), skip=skip_list, default=handle)
        person = sel.run()
        if person:
            self.model.append(self.__new_person_row(person))
            self.source_combo.set_sensitive(False)
            self._set_label()

    def change_person(self, iter_):
        """
        Change an existing person in the census.
        """                
        skip_list = []        
        handle = self.model.get_value(iter_, 0)

        sel = self.SelectPerson(self.dbstate, self.uistate, self.track,
                   _("Select Person"), skip=skip_list, default=handle)
        person = sel.run()

        if person:
            self.model.set_value(iter_, 0, person.get_handle())

    def __new_person_row(self, person):
        """
        Create a new model entry for a person.
        """
        row = [None] * (len(self.columns) + 1)
        row[0] = person.handle

        # Insert name in column called "Name", if present
        if _('Name') in self.columns:
            name = name_displayer.display(person)
            row[self.columns.index(_('Name')) + 1] = name

        return row

    def __remove_person(self, button):
        """
        Remove a person from the census.
        """
        iter_ = self.entry_grid.get_selected()
        if iter_:
            self.model.remove(iter_)
            if len(self.model) == 0:
                self._set_label()

    def __move_person(self, button, direction):
        """
        Change the position of a person in the list.
        """
        iter_ = self.entry_grid.get_selected()
        if iter_ is None:
            return
            
        row = self.model.get_path(iter_)[0]
        if direction == 'up' and row > 0:
            self.model.move_before(iter_, self.model.get_iter((row - 1,)))
            
        if direction == 'down' and row < len(self.model) - 1:
            self.model.move_after(iter_, self.model.get_iter((row + 1,)))

    def create_table(self, columns, report_columns):
        """
        Create a model and treeview for the census details.
        """
        self.columns = list(columns)
        self.model = Gtk.ListStore(*[str] * (len(columns) + 1))
        self.entry_grid.set_model(self.model)
        tooltips = [column[0] for column in report_columns]
        self.entry_grid.set_columns(self.columns, tooltips)
        self.entry_grid.build()

    def populate_gui(self, event):
        """
        Populate the model.
        """
        person_list = []
        for item in self.db.find_backlink_handles(event.get_handle(), 
                             include_classes=['Person']):
            handle = item[1]
            self.initial_people.append(handle)
            person = self.db.get_person_from_handle(handle)
            for event_ref in person.get_event_ref_list():
                if event_ref.ref == event.get_handle():
                    attrs = {}
                    order = 0
                    for attr in event_ref.get_attribute_list():
                        attr_type = str(attr.get_type())
                        if attr_type == ORDER_ATTR:
                            order = int(attr.get_value())
                        else:
                            attrs[attr_type] = attr.get_value()
                    name = name_displayer.display(person)
                    person_list.append([order, handle, name, attrs])

        person_list.sort()
        
        for person_data in person_list:
            row = person_data[1:2] # handle
            for attr in self.columns:
                if attr == _('Name'):
                    row.append(person_data[3].get(attr, person_data[2]))
                else:
                    row.append(person_data[3].get(attr))
            self.model.append(tuple(row))

        self._set_label()
        
    def save(self, trans):
        """
        Save the census details to the database.
        """
        # Update people on the census
        all_people = []    
        for order, row in enumerate(self.model):
            all_people.append(row[0])
            person = self.db.get_person_from_handle(row[0])
            event_ref = self.get_census_event_ref(person)
            if event_ref is None:
                # Add new link to census
                event_ref = EventRef()
                event_ref.ref = self.event.get_handle()
                event_ref.set_role(EventRoleType.PRIMARY)
                person.add_event_ref(event_ref)
            # Write attributes
            attrs = event_ref.get_attribute_list()
            set_attribute(event_ref, attrs, ORDER_ATTR, str(order + 1))
            for offset, name in enumerate(self.columns):
                value = row[offset + 1]
                if name == _('Name'):
                    if value != name_displayer.display(person):
                        set_attribute(event_ref, attrs, name, value)
                else:
                    set_attribute(event_ref, attrs, name, value)
            self.db.commit_person(person, trans)

        # Remove links to people no longer on census
        for handle in (set(self.initial_people) - set(all_people)):
            person = self.db.get_person_from_handle(handle)
            ref_list = [event_ref for event_ref in person.get_event_ref_list()
                                if event_ref.ref != self.event.handle]
            person.set_event_ref_list(ref_list)
            self.db.commit_person(person, trans)

    def get_census_event_ref(self, person):
        """
        Return the event reference for a given person the points to the census
        event being edited.
        """
        for event_ref in person.get_event_ref_list():
            if event_ref.ref == self.event.get_handle():
                return event_ref
        return None

#------------------------------------------------------------------------
#
# Headings Tab
#
#------------------------------------------------------------------------
class HeadingsTab(GrampsTab):
    """
    Headings tab in the census editor.
    """
    def __init__(self, dbstate, uistate, track, event, source_combo):
        GrampsTab.__init__(self, dbstate, uistate, track, _('Headings'))
        self.db = dbstate.db
        self.event = event
        self.heading_list = []
        self.source_combo = source_combo
        self._set_label()

    def get_icon_name(self):
        return 'gramps-attribute'

    def build_interface(self):
        """
        Builds the interface.
        """
        self.model = Gtk.ListStore(str, str)
        self.view = Gtk.TreeView(self.model)
        self.selection = self.view.get_selection()
        
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Key'), renderer, text=0)
        self.view.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        renderer.connect('edited', self.__cell_edited, (self.model, 1))
        column = Gtk.TreeViewColumn(_('Value'), renderer, text=1)
        self.view.append_column(column)

        scrollwin = Gtk.ScrolledWindow()
        scrollwin.add_with_viewport(self.view)
        scrollwin.set_policy(Gtk.PolicyType.AUTOMATIC, 
                             Gtk.PolicyType.AUTOMATIC)

        self.pack_start(scrollwin, expand=True, fill=True, padding=0)

    def is_empty(self):
        """
        Indicate if the tab contains any data. This is used to determine
        how the label should be displayed.
        """
        for row in self.model:
            if row[1]:
                return False
        return True

    def create_table(self, heading_list):
        """
        Create the list of headings.
        """
        self.heading_list = heading_list
        self.model.clear()
        attr_list = self.event.get_attribute_list()
        for heading in heading_list:
            attr = get_attribute(attr_list, heading)
            if attr:
                self.model.append((heading, attr.get_value()))
            else:
                self.model.append((heading, ''))
        self._set_label()

    def save(self):
        """
        Save the census headings to the database.
        """
        new_list = []
        for attr in self.event.get_attribute_list():
            if attr.get_type() not in self.heading_list:
                new_list.append(attr)

        for row in self.model:
            if row[1]:
                attr = Attribute()
                attr.set_type(row[0])
                attr.set_value(row[1])
                new_list.append(attr)

        self.event.set_attribute_list(new_list)                   

    def __cell_edited(self, cell, path, new_text, data):
        """
        Called when a cell is edited in the list of headings.
        """
        model, column = data
        model[path][column] = new_text
        self.source_combo.set_sensitive(False)
        self._set_label()

#------------------------------------------------------------------------
#
# Helper functions
#
#------------------------------------------------------------------------
def get_attribute(attrs, name):
    """
    Return a named attribute from a list of attributes.  Return 'None' if
    the attribute is not in the list.
    """
    for attr in attrs:
        if attr.get_type() == name:
            return attr
    return None

def set_attribute(event_ref, attrs, name, value):
    """
    Set a named attribute to a given value.  Create the attribute if it
    does not already exist.  Delete it if the value is None or ''.
    """
    attr = get_attribute(attrs, name)
    if attr is None:
        if value:
            # Add
            attr = Attribute()
            attr.set_type(name)
            attr.set_value(value)
            if name == ORDER_ATTR:
                attr.set_privacy(True)
            event_ref.add_attribute(attr)
    else:
        if not value:
            # Remove
            event_ref.remove_attribute(attr)
        elif attr.get_value() != value:
            # Update
            attr.set_value(value)

#------------------------------------------------------------------------
#
# Data entry widgets
#
#------------------------------------------------------------------------
class Indicator(Gtk.DrawingArea):

    def __init__(self):
        Gtk.DrawingArea.__init__(self)
        self.connect('draw', self._draw)
        self.active = False
        self.set_size_request(5, -1)

    def set_active(self, value):
        self.active = value
        self.queue_draw()

    def _draw(self, widget, cr):

        # clip area to avoid extra work
        #cr.rectangle(event.area.x, event.area.y, 
                     #event.area.width, event.area.height)
        #cr.clip()

        alloc = self.get_allocation()
        if self.active:
            cr.set_source_rgba(1, 0, 0, 1)
        else:
            cr.set_source_rgba(1, 0, 0, 0)
        cr.rectangle(0, 3, alloc.width, alloc.height-6)
        cr.fill()
        

class EntryGrid(Gtk.Table):

    def __init__(self, headings=None, tooltips=None, model=None, callback=None):
        Gtk.Table.__init__(self)

        self.headings = headings
        self.tooltips = tooltips
        self.model = model
        self.widgets = []
        self.indicators = []
        self.selected = None
        self.callback = callback

    def set_model(self, model):
        self.model = model

        model.connect('row-inserted', self.row_inserted)
        model.connect('row-deleted', self.row_deleted)
        model.connect('rows-reordered', self.rows_reordered)
        self.sig_id = model.connect('row-changed', self.row_changed)

        if len(self.model) > 0:
            self.selected = model.get_iter((0,))
    
    def set_columns(self, columns, tooltips):
        self.headings = columns
        self.tooltips = tooltips

    def build(self):

        for child in self.get_children():
            self.remove(child)
            child.destroy()
        
        self.resize(len(self.model) + 1, len(self.headings) + 2)
        
        self.indicators = []
        self.widgets = []

        for column, heading in enumerate(self.headings):
            label = Gtk.Label(heading)
            label.set_alignment(0, 0.5)
            label.show()
            self.attach(label, column + 2, column + 3, 0, 1,
                        xpadding=5, yoptions=0, ypadding=5)

        for row in range(len(self.model)):
            image = Gtk.Image()
            image.set_from_stock(Gtk.STOCK_INDEX, Gtk.IconSize.BUTTON)
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(image)
            button.connect('clicked', self.clicked, row)
            button.set_can_focus(False)
            button.show_all()
            self.attach(button, 0, 1, row + 1, row + 2, xoptions=0, yoptions=0)
            box = Indicator()
            box.show()
            if self.model.get_path(self.selected)[0] == row:
                box.set_active(True)
            self.attach(box, 1, 2, row + 1, row + 2,
                        xoptions=Gtk.AttachOptions.FILL,
                        yoptions=Gtk.AttachOptions.FILL)
            self.indicators.append(box)
            entry_row = []
            for column, value in enumerate(self.model[row]):
                if column == 0:
                    continue
                entry = Gtk.Entry()
                entry.set_width_chars(5)
                if value is not None:
                    entry.set_text(value)
                    set_size(entry)
                entry.set_tooltip_text(self.tooltips[column - 1])
                entry.connect('changed', self.changed, row, column)
                entry.connect('focus-in-event', self.got_focus, row)
                entry.show()
                self.attach(entry, column + 1, column + 2, row + 1, row + 2, 
                            yoptions=0)
                entry_row.append(entry)
            self.widgets.append(entry_row)

    def get_selected(self):
        return self.selected

    def clicked(self, button, row):
        iter_ = self.model.get_iter((row,))
        self.callback(iter_)

    def got_focus(self, entry, event, row):
        for indicator in self.indicators:
            indicator.set_active(False)
        self.selected = self.model.get_iter((row,))
        self.indicators[row].set_active(True)

    def changed(self, entry, row, column):
        set_size(entry)
        self.model.handler_block(self.sig_id)
        self.model[row][column] = entry.get_text()
        self.model.handler_unblock(self.sig_id)

    def row_inserted(self, model, path, iter_):
        self.selected = model.get_iter((len(model) - 1,))
        self.build()

    def row_changed(self, model, path, iter_):
        for column in range(1, len(self.headings) + 1):
            value = model.get_value(iter_, column)
            if value is not None:
                self.widgets[path[0]][column - 1].set_text(value)

    def row_deleted(self, model, path):
        if len(model) > 0:
            self.selected = model.get_iter((0,))
        else:
            self.selected = None
        self.build()

    def rows_reordered(self, model, path, iter_, new_order):
        self.build()

    def clean_up(self):
        self.headings = None
        self.tooltips = None
        self.model = None
        self.widgets = None
        self.indicators = None
        self.selected = None
        self.callback = None

def set_size(entry):
    layout = entry.get_layout()
    width, height = layout.get_pixel_size()
    entry.set_size_request(width + 10, -1)
