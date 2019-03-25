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

from gi.repository import Gtk, Gdk, GLib
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
    def __init__(self, activate_func, dbstate, items_list=None):
        Gtk.SearchEntry.__init__(self)
        self.set_hexpand(True)
        self.set_tooltip_text(
            _('Search people in the current visible graph.'))
        self.set_placeholder_text(_("Search in the graph..."))

        self.dbstate = dbstate

        # 'item' - is GooCanvas.CanvasGroup object
        self.items_list = items_list
        self.found_list = []
        # function that will be called (with person handle)
        # whew choose some of result item
        self.activate_func = activate_func

        self.found_popup, self.found_box, self.other_box = self.build_popup()

        self.connect("key-press-event", self.on_key_press_event)

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
            self.thread = Thread(target=self.search_all_db,
                                 args=[search_words])
            self.thread.start()
        else:
            self.hide_search_popup()

    def search_all_db(self, search_words):
        """
        Search persons in all database.
        Use Thread to make UI responsiveness.
        """
        self.in_search = True

        progress_label = Gtk.Label(_('Search in progress...'))
        self.other_box.pack_start(progress_label, False, True, 2)
        progress_label.show()

        # get all person handles
        all_person_handles = self.dbstate.db.get_person_handles()

        found = False
        if all_person_handles:
            for person_handle in all_person_handles:
                if person_handle not in self.found_list:
                    if self.check_person(person_handle, search_words):
                        GLib.idle_add(self.add_to_found,
                                      person_handle, self.other_box)
                        found = True
                if not self.in_search:
                    break
                GLib.usleep(100)

        if not found:
            no_result = Gtk.Label(_('No persons found...'))
            self.other_box.pack_start(no_result, False, True, 2)
            no_result.show()

        progress_label.hide()
        self.in_search = False

    def add_to_found(self, person_handle, box):
        """
        Add found item(person) to specified box.
        """
        try:
            # try used for not person handles
            person = self.dbstate.db.get_person_from_handle(person_handle)
        except:
            return False
        name = displayer.display_name(person.get_primary_name())
        val_to_display = "[%s] %s" % (person.gramps_id, name)

        button = Gtk.Button(val_to_display)
        button.connect("clicked", self.activate_func, person_handle)
        box.pack_start(button, False, True, 2)

        button.show()

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
        Check if person name contains all words of the search.
        """
        try:
            # try used for not person handles
            person = self.dbstate.db.get_person_from_handle(person_handle)
        except:
            return False

        if person:
            name = displayer.display_name(person.get_primary_name()).lower()
            for word in search_words:
                if word not in name:
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
        sw_popup.set_max_content_height(200)
        sw_popup.set_propagate_natural_height(True)
        # scroll window for found in the database
        sw_popup_other = Gtk.ScrolledWindow()
        sw_popup_other.set_policy(Gtk.PolicyType.NEVER,
                                  Gtk.PolicyType.AUTOMATIC)
        sw_popup_other.set_max_content_height(200)
        sw_popup_other.set_propagate_natural_height(True)

        all_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        found_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        found_lable = Gtk.Label(_('<b>Persons from current graph:</b>'))
        found_lable.set_use_markup(True)
        all_box.pack_start(found_lable, False, True, 2)
        sw_popup.add(found_box)
        all_box.add(sw_popup)

        other_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        other_lable = Gtk.Label(_('<b>Other persons from database:</b>'))
        other_lable.set_use_markup(True)
        other_lable.set_margin_top(10)
        all_box.pack_start(other_lable, False, True, 2)
        sw_popup_other.add(other_box)
        all_box.add(sw_popup_other)

        found_popup.add(all_box)

        return found_popup, found_box, other_box

    def show_search_popup(self):
        """
        Show search popup with results.
        """
        # remove all old items from popup
        for child in self.found_box.get_children():
            self.found_box.remove(child)
        for child in self.other_box.get_children():
            self.other_box.remove(child)

        # add buttons for all found items(persons)
        for person_handle in self.found_list:
            self.add_to_found(person_handle, self.found_box)

        if not self.found_list:
            self.found_box.pack_start(
                Gtk.Label(_('No persons found...')),
                False, True, 2)

        self.found_popup.show_all()
        self.found_popup.popup()

    def hide_search_popup(self, *args):
        """
        Hide search popup window.
        """
        self.stop_search()
        self.found_popup.popdown()
