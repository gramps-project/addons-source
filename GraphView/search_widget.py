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


class SearchWidget(GObject.GObject):
    """
    Search widget for persons search.
    SearchEntry to input text.
    Popover to display results.
    """

    __gsignals__ = {
        'item-activated': (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        }

    def __init__(self, dbstate, get_person_image,
                 items_list=None, sort_func=None):
        """
        Initialise the SearchWidget class.
        """
        GObject.GObject.__init__(self)

        self.dbstate = dbstate

        # 'item' - is GooCanvas.CanvasGroup object
        self.items_list = items_list
        self.found_list = []

        self.search_entry = SearchEntry()
        self.popover_widget = Popover(get_person_image, sort_func)
        self.popover_widget.set_relative_to(self.search_entry)

        # connect signals
        self.popover_widget.connect('item-activated', self.activate_item)
        self.search_entry.connect('start-search', self.start_search)
        self.search_entry.connect('empty-search', self.hide_search_popover)
        self.search_entry.connect('focus-to-result', self.focus_results)

        self.search_all_db_option = True
        # set default options
        self.set_options(True, True)

        # thread for search
        self.thread = None

        # search status
        self.in_search = False

    def get_widget(self):
        """
        Returns search entry widget.
        """
        return self.search_entry

    def set_items_list(self, items_list):
        """
        Set items list for search.
        'items_list' - is GooCanvas.CanvasGroup objects list.
        """
        self.items_list = items_list

    def set_options(self, search_all_db=None, show_images=None):
        """
        Set options for search.
        """
        if search_all_db is not None:
            self.search_all_db_option = search_all_db
        if show_images is not None:
            self.popover_widget.show_images_option = show_images

    def activate_item(self, widget, person_handle):
        """
        Activate item in results.
        """
        if person_handle is not None:
            self.emit('item-activated', person_handle)

    def start_search(self, widget, search_words):
        """
        Start search thread.
        """
        self.stop_search()
        self.popover_widget.clear_items()
        self.popover_widget.popup()

        self.found_list.clear()
        self.thread = Thread(target=self.make_search,
                             args=[search_words])
        self.thread.start()

    def make_search(self, search_words):
        """
        Search persons in the current graph and after in the db.
        Use Thread to make UI responsiveness.
        """
        self.in_search = True

        add_delay = 1000

        # search persons in the graph
        for item in self.items_list:
            if self.check_person(item.title, search_words):
                self.found_list.append(item.title)
                added = self.add_to_result(item.title, 'graph')
                # wait until person is added to list
                while not added:
                    if not self.in_search:
                        return
                    GLib.usleep(add_delay)
                    added = self.add_to_result(person_handle, 'graph')
                GLib.usleep(add_delay)
        if not self.found_list:
            GLib.idle_add(self.popover_widget.add_no_result, 'graph')

        # search other persons from db
        # ============================
        if not self.search_all_db_option:
            self.in_search = False
            return
        GLib.idle_add(self.popover_widget.show_all_db,
                      self.search_all_db_option)

        GLib.idle_add(self.popover_widget.progress_label.show)

        # get all person handles
        all_person_handles = self.dbstate.db.get_person_handles()

        found = False
        if all_person_handles:
            for person_handle in all_person_handles:
                if person_handle not in self.found_list:
                    if self.check_person(person_handle, search_words):
                        added = self.add_to_result(person_handle, 'other')
                        # wait until person is added to list
                        while not added:
                            if not self.in_search:
                                return
                            GLib.usleep(add_delay)
                            added = self.add_to_result(person_handle, 'other')
                        found = True
                if not self.in_search:
                    return
                GLib.usleep(add_delay)

        if not found:
            GLib.idle_add(self.popover_widget.add_no_result, 'other')

        GLib.idle_add(self.popover_widget.progress_label.hide)

        self.in_search = False

    def get_person_from_handle(self, person_handle):
        """
        Get person from handle.
        """
        try:
            # try used for not person handles
            # and other problems to get person
            person = self.dbstate.db.get_person_from_handle(person_handle)
            return person
        except:
            return False

    def add_to_result(self, person_handle, kind):
        """
        Add found person to results.
        "GLib.idle_add" used for using method in thread.
        """
        person = self.get_person_from_handle(person_handle)
        if person:
            GLib.idle_add(self.popover_widget.add_to_found, person, kind)
            return True
        else:
            return False

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
        person = self.get_person_from_handle(person_handle)
        if person:
            name = displayer.display_name(person.get_primary_name()).lower()
            search_str = name + person.gramps_id.lower()
            for word in search_words:
                if word not in search_str:
                    # if some of words not present in the person name
                    return False
            return True
        return False

    def focus_results(self, widget):
        """
        Focus to result popover.
        """
        self.popover_widget.grab_focus()

    def hide_search_popover(self, *args):
        """
        Hide search results.
        """
        self.stop_search()
        self.popover_widget.popdown()


class SearchEntry(Gtk.SearchEntry):
    """
    Search entry widget for persons search.
    """

    __gsignals__ = {
        'start-search': (GObject.SIGNAL_RUN_FIRST, None, (object, )),
        'empty-search': (GObject.SIGNAL_RUN_FIRST, None, ()),
        'focus-to-result': (GObject.SIGNAL_RUN_FIRST, None, ()),
        }

    def __init__(self):
        Gtk.SearchEntry.__init__(self)

        self.set_hexpand(True)
        self.set_tooltip_text(
            _('Search people in the current visible graph and database.\n'
              'Use <Ctrl+F> to make search entry active.'))
        self.set_placeholder_text(_("Search..."))

        self.connect("key-press-event", self.on_key_press_event)

    def on_key_press_event(self, widget, event):
        """
        Handle 'Esc' and 'Down' keys.
        """
        key = event.keyval
        if key == Gdk.KEY_Escape:
            self.set_text("")
            self.emit('empty-search')
        elif key == Gdk.KEY_Down:
            self.emit('focus-to-result')
            return True

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
        search_str = self.get_text().lower()
        search_words = search_str.split()

        if search_words:
            self.emit('start-search', search_words)
        else:
            self.emit('empty-search')


class Popover(Gtk.Popover):
    """
    Widget to display search results.
    It separated to 2 parts: graph and db search results.
    """

    __gsignals__ = {
        'item-activated': (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        }

    def __init__(self, get_person_image, sort_func):
        Gtk.Popover.__init__(self)

        self.get_person_image = get_person_image
        self.sort_func = sort_func
        self.show_images_option = False

        self.progress_label = Gtk.Label(_('Search in progress...'))
        self.search_all_db_box = None

        self.found_box, self.other_box = self.build_popover()

    def build_popover(self):
        """
        Builds popover widget.
        """
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_modal(False)

        # scroll window for found in the graph
        sw_popover = Gtk.ScrolledWindow()
        sw_popover.set_policy(Gtk.PolicyType.NEVER,
                              Gtk.PolicyType.AUTOMATIC)
        # scroll window for found in the database
        sw_popover_other = Gtk.ScrolledWindow()
        sw_popover_other.set_policy(Gtk.PolicyType.NEVER,
                                    Gtk.PolicyType.AUTOMATIC)

        all_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        found_box = Gtk.ListBox()
        found_box.set_activate_on_single_click(True)
        found_box.set_sort_func(self.sort_func)
        found_lable = Gtk.Label(_('<b>Persons from current graph:</b>'))
        found_lable.set_use_markup(True)
        all_box.pack_start(found_lable, False, True, 2)
        sw_popover.add(found_box)
        all_box.add(sw_popover)

        self.search_all_db_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search_all_db_box.set_margin_top(10)
        other_box = Gtk.ListBox()
        other_box.set_activate_on_single_click(True)
        other_box.set_sort_func(self.sort_func)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        other_lable = Gtk.Label(_('<b>Other persons from database:</b>'))
        vbox.add(other_lable)
        vbox.add(self.progress_label)
        other_lable.set_use_markup(True)
        self.search_all_db_box.add(vbox)
        sw_popover_other.add(other_box)
        self.search_all_db_box.pack_start(sw_popover_other, False, True, 2)
        all_box.add(self.search_all_db_box)

        # set max size of scrolled windows
        # use try because methods available since Gtk 3.22
        try:
            sw_popover.set_max_content_height(200)
            sw_popover.set_propagate_natural_height(True)
            sw_popover_other.set_max_content_height(200)
            sw_popover_other.set_propagate_natural_height(True)
        except:
            sw_popover.connect("draw", self.on_draw_scroll_search, found_box)
            sw_popover_other.connect("draw", self.on_draw_scroll_search,
                                     other_box)

        # set all widgets visible
        all_box.show_all()

        self.add(all_box)

        # connect signals
        found_box.connect("row-activated", self.activate_item)
        other_box.connect("row-activated", self.activate_item)

        return found_box, other_box

    def show_all_db(self, state):
        """
        Show/hide results for all db search.
        """
        if state:
            self.search_all_db_box.show_all()
        else:
            self.search_all_db_box.hide()

    def activate_item(self, list_box, row):
        """
        Emit signal on item activation.
        """
        if row is None:
            return
        person_handle = row.description
        if person_handle is not None:
            self.emit('item-activated', person_handle)
        # hide popover on activation
        self.popdown()

    def on_draw_scroll_search(self, widget, cr, list_box):
        """
        Workaround to set max height of scrolled windows.
        widget - Gtk.ScrolledWindow
        list_box - Gtk.ListBox
        """
        max_height = 200
        minimum_height, natural_height = list_box.get_preferred_height()
        if natural_height > max_height:
            widget.set_size_request(-1, max_height)
        else:
            widget.set_size_request(-1, natural_height)

    def add_to_found(self, person, kind):
        """
        Add found item(person) to specified ListBox.
        """
        if kind == 'graph':
            list_box = self.found_box
        else:
            list_box = self.other_box

        name = displayer.display_name(person.get_primary_name())

        row = ListBoxRow(description=person.handle)
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

        list_box.prepend(row)
        row.show_all()

    def add_no_result(self, kind):
        """
        Add only one row to specified ListBox with no results lable.
        """
        if kind == 'graph':
            list_box = self.found_box
        else:
            list_box = self.other_box
        # remove all old items from popover list_box
        list_box.foreach(list_box.remove)

        row = ListBoxRow()
        row.add(Gtk.Label(_('No persons found...')))
        list_box.add(row)
        row.show_all()

    def clear_items(self):
        """
        Remove all old items from popover lists.
        """
        self.found_box.foreach(self.found_box.remove)
        self.other_box.foreach(self.other_box.remove)


class ListBoxRow(Gtk.ListBoxRow):
    """
    Extended Gtk.ListBoxRow whit description property.
    """
    def __init__(self, description=None):
        Gtk.ListBoxRow.__init__(self)
        self.description = description     # useed to store person handle
