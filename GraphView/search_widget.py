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

from gi.repository import Gtk, Gdk

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

        self.items_list = items_list
        self.found_list = []
        # function that will be called (with person handle)
        # whew choose some of result item
        self.activate_func = activate_func

        self.found_popup, self.vbox_popup = self.build_popup()

        self.connect("key-press-event", self.on_key_press_event)

    def set_items_list(self, items_list):
        """
        Set items list for search.
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
        Called when search string is changed.
        """
        search_str = self.get_text().lower()
        search_words = search_str.split()

        self.found_list.clear()
        for item in self.items_list:
            if self.check_person(item.title, search_words):
                self.found_list.append(item)

        if search_words:
            self.show_search_popup()
        else:
            self.hide_search_popup()

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

        sw_popup = Gtk.ScrolledWindow()
        sw_popup.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw_popup.set_max_content_height(300)
        sw_popup.set_propagate_natural_height(True)
        all_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox_popup = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        all_box.pack_start(Gtk.Label(_('Search results:')), False, True, 2)
        all_box.add(vbox_popup)
        sw_popup.add(all_box)
        found_popup.add(sw_popup)

        return found_popup, vbox_popup

    def show_search_popup(self):
        """
        Show search popup with results.
        """
        # remove all found items from popup
        for child in self.vbox_popup.get_children():
            self.vbox_popup.remove(child)

        for item in self.found_list:
            person = self.dbstate.db.get_person_from_handle(item.title)
            name = displayer.display_name(person.get_primary_name())
            val_to_display = "[%s] %s" % (person.gramps_id, name)

            button = Gtk.Button(val_to_display)
            button.connect("clicked", self.activate_func, item.title)
            self.vbox_popup.pack_start(button, False, True, 2)

        if not self.found_list:
            self.vbox_popup.pack_start(Gtk.Label(_('No person is found...')),
                                       False, True, 2)

        self.found_popup.show_all()
        self.found_popup.popup()

    def hide_search_popup(self, *args):
        """
        Hide search popup window.
        """
        self.found_popup.popdown()
