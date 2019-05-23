# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019-      Ivan Komaritsyn
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

from gi.repository import Gtk, Gdk, GLib, GObject
from threading import Thread

from gramps.gen.display.name import displayer

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class SearchWidget(Gtk.SearchEntry):
    """
    Search widget with popup results.
    """

    __gsignals__ = {
        'item-activated' : (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        }

    def __init__(self, dbstate, get_person_image,
                 items_list=None, sort_func=None):
        """
        get_person_image - function to get person image
        sort_func - function to apply sort
        """
        Gtk.SearchEntry.__init__(self)

        self.set_hexpand(True)
        self.set_tooltip_text(
            _('Search people in the current visible graph and database.'))
        self.set_placeholder_text(_("Search..."))

        self.dbstate = dbstate

        # 'item' - is GooCanvas.CanvasGroup object
        self.items_list = items_list
        self.found_list = []

        self.sort_func = sort_func
        self.get_person_image = get_person_image

        self.found_popup, self.found_box, self.other_box = self.build_popup()

        self.connect("key-press-event", self.on_key_press_event)

        self.search_all_db_option = True
        self.show_images_option = False

    def set_options(self, search_all_db=None, show_images=None):
        """
        Set options for search.
        """
        if search_all_db is not None:
            self.search_all_db_option = search_all_db
        if show_images is not None:
            self.show_images_option = show_images

    def set_items_list(self, items_list):
        """
        Set items list for search.
        'items_list' - is GooCanvas.CanvasGroup objects list.
        """
        self.items_list = items_list

    def on_key_press_event(self, widget, event):
        """
        Handle 'Esc' key.
        """
        if event.keyval == Gdk.KEY_Escape:
            self.set_text("")
            self.hide_search_popup()

    def do_activate(self):
        """
        Handle 'Enter' key.
        """
        self.do_search_changed()

    def do_search_changed(self):
        """
        Apply search.
        Called when search string is changed.
        """
        self.stop_search()

        search_str = self.get_text().lower()
        search_words = search_str.split()

        self.found_list.clear()
        for item in self.items_list:
            if self.check_person(item.title, search_words):
                self.found_list.append(item.title)

        if search_words:
            self.show_search_popup()
            if self.search_all_db_option:
                self.search_all_db_box.show_all()
                self.thread = Thread(target=self.search_all_db,
                                     args=[search_words])
                self.thread.start()
            else:
                self.search_all_db_box.hide()
        else:
            self.hide_search_popup()

    def search_all_db(self, search_words):
        """
        Search persons in all database.
        Use Thread to make UI responsiveness.
        """
        context = GLib.main_context_default()
        self.in_search = True

        events = []
        event_id = GLib.idle_add(self.progress_label.show)
        events.append(context.find_source_by_id(event_id))

        # get all person handles
        all_person_handles = self.dbstate.db.get_person_handles()

        found = False
        if all_person_handles:
            for person_handle in all_person_handles:
                if person_handle not in self.found_list:
                    if self.check_person(person_handle, search_words):
                        event_id = GLib.idle_add(self.add_to_found,
                                                 person_handle, self.other_box)
                        event = context.find_source_by_id(event_id)
                        # wait until person is added to list
                        while not event.is_destroyed():
                            if not self.in_search:
                                break
                            GLib.usleep(50)
                        found = True
                if not self.in_search:
                    break
                GLib.usleep(10)

        if not found:
            event_id = GLib.idle_add(self.add_no_result, self.other_box)
            events.append(context.find_source_by_id(event_id))

        event_id = GLib.idle_add(self.progress_label.hide)
        events.append(context.find_source_by_id(event_id))
        # wait until events finished
        for event in events:
            time_out = 0
            while not event.is_destroyed():
                if time_out > 10000:
                    GLib.source_remove(event.get_id())
                GLib.usleep(50)
                time_out += 50
        self.in_search = False

    def add_no_result(self, list_box):
        """
        Add only one row to specified ListBox with no results lable.
        """
        # remove all old items from popup
        list_box.foreach(list_box.remove)

        row = Gtk.ListBoxRow()
        not_found_label = Gtk.Label(_('No persons found...'))
        row.add(not_found_label)
        list_box.add(row)
        row.show_all()

    def add_to_found(self, person_handle, list_box):
        """
        Add found item(person) to specified ListBox.
        """
        try:
            # try used if we have any problem to get person from Thread
            person = self.dbstate.db.get_person_from_handle(person_handle)
        except:
            # we should return "True" to repeat call (see GLib.idle_add)
            return True
        name = displayer.display_name(person.get_primary_name())

        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add(hbox)

        # add person ID
        label = Gtk.Label("[%s]" % person.gramps_id, xalign=0)
        hbox.pack_start(label, False, False, 2)
        # add person name
        label = Gtk.Label(name, xalign=0)
        hbox.pack_start(label, True, True, 2)
        # add person image if needed
        if self.show_images_option:
            person_image = self.get_person_image(person, 32, 32, kind='image')
            if person_image:
                hbox.pack_start(person_image, False, True, 2)

        row.connect("activate", self.activate_item, person_handle)
        list_box.prepend(row)
        row.show_all()

    def activate_item(self, row, person_handle):
        """
        Activate item in results.
        """
        self.emit('item-activated', person_handle)

    def stop_search(self):
        """
        Stop search.
        And wait while thread is finished.
        """
        self.in_search = False
        try:
            self.thread.join()
        except:
            pass

    def check_person(self, person_handle, search_words):
        """
        Check if person name and id contains all words of the search.
        """
        try:
            # try used for not person handles
            person = self.dbstate.db.get_person_from_handle(person_handle)
        except:
            return False

        if person:
            name = displayer.display_name(person.get_primary_name()).lower()
            search_str = name + person.gramps_id.lower()
            for word in search_words:
                if word not in search_str:
                    # if some of words not present in the person name
                    return False
            return True
        return False

    def build_popup(self):
        """
        Builds popup widget.
        """
        found_popup = Gtk.Popover.new(self)
        found_popup.set_position(Gtk.PositionType.BOTTOM)
        found_popup.set_modal(False)

        # scroll window for found in the graph
        sw_popup = Gtk.ScrolledWindow()
        sw_popup.set_policy(Gtk.PolicyType.NEVER,
                            Gtk.PolicyType.AUTOMATIC)
        # scroll window for found in the database
        sw_popup_other = Gtk.ScrolledWindow()
        sw_popup_other.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        # set max size of scrolled windows
        # use try because methods available since Gtk 3.22
        try:
            sw_popup.set_max_content_height(200)
            sw_popup.set_propagate_natural_height(True)
            sw_popup_other.set_max_content_height(200)
            sw_popup_other.set_propagate_natural_height(True)
        except:
            sw_popup.connect("draw", self.on_draw_scroll_search)
            sw_popup_other.connect("draw", self.on_draw_scroll_search)

        all_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        found_box = Gtk.ListBox()
        found_box.set_activate_on_single_click(True)
        found_box.set_sort_func(self.sort_func)
        found_lable = Gtk.Label(_('<b>Persons from current graph:</b>'))
        found_lable.set_use_markup(True)
        all_box.pack_start(found_lable, False, True, 2)
        sw_popup.add(found_box)
        all_box.add(sw_popup)

        self.search_all_db_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search_all_db_box.set_margin_top(10)
        other_box = Gtk.ListBox()
        other_box.set_activate_on_single_click(True)
        other_box.set_sort_func(self.sort_func)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        other_lable = Gtk.Label(_('<b>Other persons from database:</b>'))
        vbox.add(other_lable)
        self.progress_label = Gtk.Label(_('Search in progress...'))
        vbox.add(self.progress_label)
        other_lable.set_use_markup(True)
        self.search_all_db_box.add(vbox)
        sw_popup_other.add(other_box)
        self.search_all_db_box.pack_start(sw_popup_other, False, True, 2)
        all_box.add(self.search_all_db_box)

        # set all widgets visible
        all_box.show_all()

        found_popup.add(all_box)

        # connect signals
        found_box.connect("row-selected", self.on_row_selected)
        other_box.connect("row-selected", self.on_row_selected)

        return found_popup, found_box, other_box

    def on_draw_scroll_search(self, widget, cr):
        """
        Workaround to set max height of scrolled windows.
        """
        max_height = 200
        for box in (self.found_box, self.other_box):
            minimum_height, natural_height = box.get_preferred_height()
            if natural_height > max_height:
                widget.set_size_request(-1, max_height)
            else:
                widget.set_size_request(-1, natural_height)

    def on_row_selected(self, listbox, row):
        """
        Called on row selection.
        Used to handle mouse click row activation.
        Row already have connected function, so call it by emiting row signal.
        """
        if row:
            row.emit("activate")

    def show_search_popup(self):
        """
        Show search popup with results.
        """
        # remove all old items from popup
        self.found_box.foreach(self.found_box.remove)
        self.other_box.foreach(self.other_box.remove)

        # add rows for all found items(persons)
        for person_handle in self.found_list:
            self.add_to_found(person_handle, self.found_box)

        if not self.found_list:
            self.add_no_result(self.found_box)

        self.found_popup.popup()

    def hide_search_popup(self, *args):
        """
        Hide search popup window.
        """
        self.stop_search()
        self.found_popup.popdown()
