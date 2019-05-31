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

        self.get_person_image = get_person_image

        self.search_entry = SearchEntry()
        self.popover_widget = Popover(_('Persons from current graph'),
                                      _('Other persons from database'),
                                      sort_func)
        self.popover_widget.set_relative_to(self.search_entry)

        # connect signals
        self.popover_widget.connect('item-activated', self.activate_item)
        self.search_entry.connect('start-search', self.start_search)
        self.search_entry.connect('empty-search', self.hide_search_popover)
        self.search_entry.connect('focus-to-result', self.focus_results)

        self.search_all_db_option = True
        self.show_images_option = True
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
            self.show_images_option = show_images

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

        GLib.idle_add(self.popover_widget.main_panel.set_progress, True)
        # search persons in the graph
        for item in self.items_list:
            if self.check_person(item.title, search_words):
                self.found_list.append(item.title)
                added = self.add_to_result(
                    item.title, self.popover_widget.main_panel)
                # wait until person is added to list
                while not added:
                    if not self.in_search:
                        return
                    GLib.usleep(add_delay)
                    added = self.add_to_result(
                        item.title, self.popover_widget.main_panel)
                GLib.usleep(add_delay)
        if not self.found_list:
            GLib.idle_add(self.popover_widget.main_panel.add_no_result,
                          _('No persons found...'))
        GLib.idle_add(self.popover_widget.main_panel.set_progress, False)

        # search other persons from db
        # ============================
        if not self.search_all_db_option:
            self.in_search = False
            return
        GLib.idle_add(self.popover_widget.show_other_panel,
                      self.search_all_db_option)
        GLib.idle_add(self.popover_widget.other_panel.set_progress, True)

        # get all person handles
        all_person_handles = self.dbstate.db.get_person_handles()

        found = False
        if all_person_handles:
            for person_handle in all_person_handles:
                # excluding found persons
                if person_handle not in self.found_list:
                    if self.check_person(person_handle, search_words):
                        added = self.add_to_result(
                            person_handle, self.popover_widget.other_panel)
                        # wait until person is added to list
                        while not added:
                            if not self.in_search:
                                return
                            GLib.usleep(add_delay)
                            added = self.add_to_result(
                                person_handle, self.popover_widget.other_panel)
                        found = True
                if not self.in_search:
                    return
                GLib.usleep(add_delay)

        if not found:
            GLib.idle_add(self.popover_widget.other_panel.add_no_result,
                          _('No persons found...'))

        GLib.idle_add(self.popover_widget.other_panel.set_progress, False)

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

    def add_to_result(self, person_handle, panel):
        """
        Add found person to results.
        "GLib.idle_add" used for using method in thread.
        """
        person = self.get_person_from_handle(person_handle)
        if person:
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
                person_image = self.get_person_image(person, 32, 32,
                                                     kind='image')
                if person_image:
                    hbox.pack_start(person_image, False, True, 2)

            GLib.idle_add(panel.add_to_panel, ['row', row])
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
    Widget to display lists results.
    It contain 2 panels: main and other.
    """

    __gsignals__ = {
        'item-activated': (GObject.SIGNAL_RUN_FIRST, None, (str, )),
        }

    def __init__(self, main_label, other_label, sort_func=None):
        Gtk.Popover.__init__(self)
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_modal(False)

        # build panels
        self.main_panel = Panel(main_label, sort_func)
        self.other_panel = Panel(other_label, sort_func)
        self.other_panel.set_margin_top(10)

        # connect signals
        self.main_panel.list_box.connect("row-activated", self.activate_item)
        self.other_panel.list_box.connect("row-activated", self.activate_item)

        all_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        all_box.add(self.main_panel)
        all_box.add(self.other_panel)
        # set all widgets visible
        all_box.show_all()

        self.add(all_box)

    def show_other_panel(self, state):
        """
        Show or hide other panel.
        """
        if state:
            self.other_panel.show_all()
        else:
            self.other_panel.hide()

    def activate_item(self, list_box, row):
        """
        Emit signal on item activation.
        """
        if row is None:
            return
        handle = row.description
        if handle is not None:
            self.emit('item-activated', handle)
        # hide popover on activation
        self.popdown()

    def clear_items(self):
        """
        Remove all old items from popover lists.
        """
        for panel in (self.main_panel, self.other_panel):
            panel.clear_items()


class ListBoxRow(Gtk.ListBoxRow):
    """
    Extended Gtk.ListBoxRow with description property.
    """
    def __init__(self, description=None):
        Gtk.ListBoxRow.__init__(self)
        self.description = description     # useed to store person handle


class ScrolledListBox(Gtk.ScrolledWindow):
    """
    Extended Gtk.ScrolledWindow with max_height property.
    And with Gtk.ListBox inside.
    """
    def __init__(self, max_height=-1):
        Gtk.ScrolledWindow.__init__(self)

        self.list_box = Gtk.ListBox()
        self.add(self.list_box)

        self.max_height = max_height

        self.connect("draw", self.set_max_height)

    def set_max_height(self, widget, cr):
        """
        Workaround to set max height of scrolled window.
        """
        minimum_height, natural_height = self.list_box.get_preferred_height()
        if natural_height > self.max_height:
            self.set_size_request(-1, self.max_height)
        else:
            self.set_size_request(-1, natural_height)


class Panel(Gtk.Box):
    """
    Panel for popover.
    Contain in vertical Gtk.Box: Label, Status, Scrolled list.
    """
    def __init__(self, label, sort_func):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        slb = ScrolledListBox(max_height=200)
        slb.set_policy(Gtk.PolicyType.NEVER,
                       Gtk.PolicyType.AUTOMATIC)

        self.list_box = slb.list_box
        self.list_box.set_activate_on_single_click(True)
        self.list_box.set_sort_func(sort_func)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel_lable = Gtk.Label(_('<b>%s:</b>') % label)
        panel_lable.set_use_markup(True)
        vbox.add(panel_lable)
        self.progress_label = Gtk.Label(_('Search in progress...'))
        vbox.add(self.progress_label)

        self.add(vbox)
        self.add(slb)

    def set_progress(self, state):
        """
        Show or hide progress label.
        """
        if state:
            self.progress_label.show()
        else:
            self.progress_label.hide()

    def add_to_panel(self, data):
        """
        Add found item to specified panel (ListBox).
        data - ['row', ListBoxRow] or ['widget', [Gtk.Widget, description]]
        """
        if data[0] == 'row':
            row = data[1]
        elif data[0] == 'widget':
            row = ListBoxRow(description=data[1][1])
            row.add(data[1][0])
        else:
            return False

        self.list_box.prepend(row)
        row.show_all()

    def add_no_result(self, text):
        """
        Add only one row with no results label.
        """
        row = ListBoxRow()
        row.add(Gtk.Label(text))
        self.clear_items()
        self.list_box.add(row)
        row.show_all()

    def clear_items(self):
        """
        Remove all old items from list_box.
        """
        self.list_box.foreach(self.list_box.remove)
