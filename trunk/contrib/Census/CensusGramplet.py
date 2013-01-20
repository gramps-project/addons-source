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
from gramps.gen.display.name import displayer as name_displayer
import gramps.gen.datehandler
from gramps.gen.errors import WindowActiveError
import gramps.gen.lib
from gramps.gen.db import DbTxn
from gramps.gen.constfunc import cuni

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class CensusGramplet(Gramplet):
    """
    Gramplet to display census events for the active person.
    It allows a census to be created or edited with a census editor.
    """
    def init(self):
        """
        Initialise the gramplet.
        """
        root = self.__create_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(root)
        root.show_all()
        self.dbstate.db.connect('person-rebuild', self.update)
        self.dbstate.db.connect('event-rebuild', self.update)

    def __create_gui(self):
        """
        Create and display the GUI components of the gramplet.
        """
        vbox = Gtk.VBox()
        hbox = Gtk.HBox(False)

        person_label = Gtk.Label(_("Census details for: "))
        person_label.set_alignment(0.0, 0.5)
        hbox.pack_start(person_label, False, True, 0)

        self.person_text = Gtk.Label()
        self.person_text.set_alignment(0.0, 0.5)
        hbox.pack_start(self.person_text, True, True, 0)

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
      
        vbox.pack_start(hbox, False, True, 10)
        vbox.pack_start(view, True, True, 10)
        vbox.pack_end(button_box, False, True, 0)
        
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
        event = gramps.gen.lib.Event()
        event.set_type(gramps.gen.lib.EventType.CENSUS)
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
        if active_person:
            self.person_text.set_text(name_displayer.display(active_person))
        else:
            self.person_text.set_text(_('No active person set.'))
            return
        
        db = self.dbstate.db
        for event_ref in active_person.get_event_ref_list():
            if event_ref:
                event = db.get_event_from_handle(event_ref.ref)
                if event:
                    if event.get_type() == gramps.gen.lib.EventType.CENSUS:

                        p_handle = event.get_place_handle()
                        if p_handle:
                            place = db.get_place_from_handle(p_handle)
                            place_text = place.get_display_info()[0]
                        else:
                            place_text = ''
                            
                        citation = get_census_citation(db, event)
                        if citation:
                            source_handle = citation.get_reference_handle()
                            source = db.get_source_from_handle(source_handle)
                            source_text = source.get_title()
                            self.model.append((event,
                                              source_text,
                                              gen.datehandler.get_date(event),
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
from Census import (get_census_date, get_census_columns, get_census_citation,
                    get_census_sources, get_report_columns)
from gramps.gui.selectors import SelectorFactory

class CensusEditor(ManagedWindow):
    """
    Census Editor.
    """
    SelectPerson = SelectorFactory('Person')

    def __init__(self, dbstate, uistate, track, event):

        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        self.db = dbstate.db
        
        self.event = event
        self.citation = get_census_citation(self.db, self.event)
        if self.citation is None:
            self.citation = gramps.gen.lib.Citation()

        ManagedWindow.__init__(self, uistate, track, event)

        self.widgets = {}
        top = self.__create_gui()
        self.set_window(top, None, self.get_menu_title())

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

        self.initial_people = []
        if self.event.get_handle():
            self.widgets['census_combo'].set_sensitive(False)
            self.__populate_gui(event)

    def get_menu_title(self):
        """
        Get the menu title.
        """
        if self.event.get_handle():
            date = gen.datehandler.get_date(self.event)
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
        root.set_default_size(600, 400)
        root.set_transient_for(self.uistate.window)

        vbox = Gtk.VBox()

        tab = Gtk.Table(4, 4, False)
        tab.set_row_spacings(10)
        tab.set_col_spacings(10)

        census_label = Gtk.Label(_("Source:"))
        census_label.set_alignment(0.0, 0.5)
        tab.attach(census_label, 0, 1, 0, 1, xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        liststore = Gtk.ListStore(str, str, str)
        for row in get_census_sources(self.db):
            liststore.append(row)

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
        tab.attach(date_label, 0, 1, 1, 2, xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        date_text = Gtk.Label()
        date_text.set_alignment(0.0, 0.5)
        tab.attach(date_text, 1, 2, 1, 2)
        self.widgets['date_text'] = date_text
        
        ref_label = Gtk.Label(_("Reference:"))
        ref_label.set_alignment(0.0, 0.5)
        tab.attach(ref_label, 0, 1, 2, 3, xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
        ref_entry = Gtk.Entry()
        tab.attach(ref_entry, 1, 2, 2, 3)
        self.widgets['ref_entry'] = ref_entry

        place_label = Gtk.Label(_("Place:"))
        place_label.set_alignment(0.0, 0.5)
        tab.attach(place_label, 0, 1, 3, 4, xoptions=Gtk.AttachOptions.FILL, xpadding=10)
        
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
 
        hbox = Gtk.HBox()
        
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_ADD, Gtk.IconSize.BUTTON)
        add_btn = Gtk.Button()
        add_btn.set_relief(Gtk.ReliefStyle.NONE)
        add_btn.add(image)
        add_btn.connect('clicked', self.__add_person)
        hbox.pack_start(add_btn, False, True, 3)
        
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_INDEX, Gtk.IconSize.BUTTON)
        share_btn = Gtk.Button()
        share_btn.set_relief(Gtk.ReliefStyle.NONE)
        share_btn.add(image)
        share_btn.connect('clicked', self.__share_person)
        hbox.pack_start(share_btn, False, True, 3)
        
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_REMOVE, Gtk.IconSize.BUTTON)
        del_btn = Gtk.Button()
        del_btn.set_relief(Gtk.ReliefStyle.NONE)
        del_btn.add(image)
        del_btn.connect('clicked', self.__remove_person)
        hbox.pack_start(del_btn, False, True, 3)

        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_GO_UP, Gtk.IconSize.BUTTON)
        up_btn = Gtk.Button()
        up_btn.set_relief(Gtk.ReliefStyle.NONE)
        up_btn.add(image)
        up_btn.connect('clicked', self.__move_person, 'up')
        hbox.pack_start(up_btn, False, True, 3)

        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_GO_DOWN, Gtk.IconSize.BUTTON)
        down_btn = Gtk.Button()
        down_btn.set_relief(Gtk.ReliefStyle.NONE)
        down_btn.add(image)
        down_btn.connect('clicked', self.__move_person, 'down')
        hbox.pack_start(down_btn, False, True, 3)

        self.view = Gtk.TreeView()
        self.selection = self.view.get_selection()
        
        scrollwin = Gtk.ScrolledWindow()
        scrollwin.add_with_viewport(self.view)
        scrollwin.set_policy(Gtk.PolicyType.AUTOMATIC, 
                             Gtk.PolicyType.AUTOMATIC)

        #self.__create_table([_('Name')])

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
      
        vbox.pack_start(tab, False, True, 10)
        vbox.pack_start(hbox, False, True, 0)
        vbox.pack_start(scrollwin, True, True, 0)
        vbox.pack_end(button_box, False, True, 10)
        
        root.add(vbox)
        root.show_all()

        return root

    def __create_table(self, columns):
        self.columns = list(columns)
        self.model = Gtk.ListStore(*[str] * (len(columns) + 1))
        self.view.set_model(self.model)
        self.view.set_headers_visible(True)
        self.view.set_has_tooltip(True)
        self.view.connect('query-tooltip', self.on_query_tooltip)        

        for column in self.view.get_columns():
            self.view.remove_column(column)

        for index, name in enumerate(columns):
            renderer = Gtk.CellRendererText()
            renderer.set_property('editable', True)
            renderer.connect('edited', self.__cell_edited,
                                            (self.model, index + 1))
            column = Gtk.TreeViewColumn(name, renderer, text=index + 1)
            self.view.append_column(column)
        self.view.connect("row-activated", self.__edit_person)

    def on_query_tooltip(self, widget, x, y, keyboard_tip, tooltip):
        on_item, x_pos, y_pos, model, path, iter_ = widget.get_tooltip_context(x, y, keyboard_tip)
        if not on_item:
            return False
        else:
            bin_x, bin_y = widget.convert_widget_to_bin_window_coords(x, y)
            result = widget.get_path_at_pos(bin_x, bin_y)
    
            if result is not None:
                path, column, cell_x, cell_y = result

                if column is not None:
                    longname = self.longnames.get(column.get_title(),'')
                    tooltip.set_markup('<b>%s</b>' % longname)
                    widget.set_tooltip_cell(tooltip, path, None, None)
                return True

    def __get_longnames(self, columns, report_columns):
        self.longnames = dict(
            [c, r[0]] for c, r in zip(columns, report_columns)
            )
    
    def __populate_gui(self, event):
        """
        Populate the GUI for a given census event.
        """
        census_combo = self.widgets['census_combo']
        for pos, row in enumerate(census_combo.get_model()):
            if row[0] == self.citation.get_reference_handle():
                census_combo.set_active(pos)
                
        date_text = self.widgets['date_text']
        date_text.set_text(gen.datehandler.get_date(event))

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
                        attr_type = cuni(attr.get_type())
                        if attr_type == ORDER_ATTR:
                            order = int(attr.get_value())
                        else:
                            attrs[attr_type] = attr.get_value()
                    name = name_displayer.display(person)
                    person_list.append([order, handle, name, attrs])

        person_list.sort()
        
        for person_data in person_list:
            row = person_data[1:3] # Assumes name is first column
            for attr in self.columns[1:]:
                row.append(person_data[3].get(attr))
            self.model.append(tuple(row))

    def __add_person(self, button):
        """
        Create a new person and add them to the census.
        """
        if self.widgets['census_combo'].get_active() == -1:
            ErrorDialog(_('Cannot add a person to this census.'),
                        _('First select a census from the drop-down list.'))
            return
            
        person = gramps.gen.lib.Person()
        EditPerson(self.dbstate, self.uistate, self.track, person,
                   self.__person_added)

    def __person_added(self, person):
        """
        Called when a person is added to the census.
        """
        self.model.append(self.__new_person_row(person))
        self.widgets['census_combo'].set_sensitive(False)

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
        if self.widgets['census_combo'].get_active() == -1:
            ErrorDialog(_('Cannot add a person to this census.'),
                        _('First select a census from the drop-down list.'))
            return

        skip_list = []
        handle = None
        if len(self.model) > 0:
            model, iter_ = self.selection.get_selected()
            if iter_: # get from selection:
                handle = model.get_value(iter_, 0)
            else: # get from first row
                handle = self.model[0][0]
        else: # no rows, let's try to get active person:
            handle = self.uistate.get_active('Person')

        sel = self.SelectPerson(self.dbstate, self.uistate, self.track,
                   _("Select Person"), skip=skip_list, default=handle)
        person = sel.run()
        if person:
            self.model.append(self.__new_person_row(person))
            self.widgets['census_combo'].set_sensitive(False)
            
    def __new_person_row(self, person):
        """
        Create a new model entry for a person.
        """
        row = [None] * (len(self.columns) + 1)
        row[0] = person.handle

        # Insert name in column called "Name", if present
        try:
            row[self.columns.index("Name") + 1] = name_displayer.display(person)
        except ValueError:
            pass
        return row

    def __remove_person(self, button):
        """
        Remove a person from the census.
        """
        model, iter_ = self.selection.get_selected()
        if iter_:
            model.remove(iter_)
            if len(self.model) == 0:
                self.widgets['census_combo'].set_sensitive(True)
        
    def __move_person(self, button, direction):
        """
        Change the position of a person in the list.
        """
        model, iter_ = self.selection.get_selected()
        if iter_ is None:
            return
            
        if direction == 'up':
            prev = model.iter_previous(iter_)
            if prev:
                model.move_before(iter_, prev)
            
        if direction == 'down':
            next = model.iter_next(iter_)
            if next:
                model.move_after(iter_, next)

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
        date_text.set_text(gen.datehandler.displayer.display(census_date))
        self.event.set_date_object(census_date)
        self.citation.set_date_object(census_date)

        # Set source
        self.citation.set_reference_handle(model[index][0])

        # Set new columns
        columns = get_census_columns(census_id)
        report_columns = get_report_columns(census_id)
        self.__create_table(columns)
        self.__get_longnames(columns, report_columns)
        
    def __cell_edited(self, cell, row, new_text, data):
        """
        Called when a cell is edited in the list of people.
        """
        model, column = data
        model[row][column] = new_text

        next_column = self.view.get_column(column)
        if next_column:
            # Setting start_editing=True causes problems if Tab key ends entry
            path = Gtk.TreePath(row)
            self.view.set_cursor_on_cell(path, next_column, None, False)
            #self.view.grab_focus()
        
    def save(self, button):
        """
        Called when the user clicks the OK button.
        """
        with DbTxn(self.get_menu_title(), self.db) as trans:
            if not self.event.get_handle():
                self.db.add_event(self.event, trans)

            # Update people on the census
            all_people = []    
            for order, row in enumerate(self.model):
                all_people.append(row[0])
                person = self.db.get_person_from_handle(row[0])
                event_ref = self.get_census_event_ref(person)
                if event_ref is None:
                    # Add new link to census
                    event_ref = gramps.gen.lib.EventRef()
                    event_ref.ref = self.event.get_handle()
                    event_ref.set_role(gramps.gen.lib.EventRoleType.PRIMARY)
                    person.add_event_ref(event_ref)
                # Write attributes
                attrs = event_ref.get_attribute_list()
                self.set_attribute(event_ref, attrs, ORDER_ATTR, str(order + 1))
                for offset, name in enumerate(self.columns[1:]):
                    self.set_attribute(event_ref, attrs, name, row[offset + 2])
                self.db.commit_person(person, trans)

            # Remove links to people no longer on census
            for handle in (set(self.initial_people) - set(all_people)):
                person = self.db.get_person_from_handle(handle)
                ref_list = [event_ref for event_ref in person.get_event_ref_list()
                                    if event_ref.ref != self.event.handle]
                person.set_event_ref_list(ref_list)
                self.db.commit_person(person, trans)

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
        ManagedWindow.close(self)

    def help_clicked(self, obj):
        """
        Display the relevant portion of GRAMPS manual
        """
        display_help(webpage='Census_Addons')

    def get_attribute(self, attrs, name):
        """
        Return a named attribute from a list of attributes.  Return 'None' if
        the attribute is not in the list.
        """
        for attr in attrs:
            if attr.get_type() == name:
                return attr
        return None

    def set_attribute(self, event_ref, attrs, name, value):
        """
        Set a named attribute to a given value.  Create the attribute if it
        does not already exist.  Delete it if the value is None or ''.
        """
        attr = self.get_attribute(attrs, name)
        if attr is None:
            if value:
                # Add
                attr = gramps.gen.lib.Attribute()
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
        
    def get_census_event_ref(self, person):
        """
        Return the event reference for a given person the points to the census
        event being edited.
        """
        for event_ref in person.get_event_ref_list():
            if event_ref.ref == self.event.get_handle():
                return event_ref
        return None
