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
from threading import Thread, Event

from gramps.gen.display.name import displayer

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# gtk version
gtk_version = float("%s.%s" % (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION))


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
                 items_list=None, bookmarks=None):
        """
        Initialise the SearchWidget class.
        """
        GObject.GObject.__init__(self)

        self.dbstate = dbstate
        self.bookmarks = bookmarks

        # 'item' - is GooCanvas.CanvasGroup object
        self.items_list = items_list
        self.found_list = []

        self.get_person_image = get_person_image

        self.search_entry = SearchEntry()
        self.popover_widget = Popover(_('Persons from current graph'),
                                      _('Other persons from database'))
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

        self.search_words = None
        # search status
        self.in_search = False
        # thread for search
        self.thread = Thread()

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
        thread_event = Event()
        self.in_search = True

        # set progree to 0
        GLib.idle_add(
            self.popover_widget.main_panel.set_progress, 0, '')
        GLib.idle_add(
            self.popover_widget.other_panel.set_progress, 0, '')

        # search persons in the graph
        progress = 0
        count = 0
        for item in self.items_list:
            progress += 1
            if self.check_person(item.title, search_words):
                self.found_list.append(item.title)
                GLib.idle_add(self.do_this, thread_event,
                              self.add_to_result,
                              item.title, self.popover_widget.main_panel)
                # wait until person is added to list
                while not thread_event.wait(timeout=0.01):
                    if not self.in_search:
                        return
                thread_event.clear()

                count += 1
                GLib.idle_add(self.popover_widget.main_panel.set_progress,
                              progress/len(self.items_list),
                              'found: %s' % count)
            if not self.in_search:
                return

        if not self.found_list:
            GLib.idle_add(self.popover_widget.main_panel.add_no_result,
                          _('No persons found...'))
        GLib.idle_add(self.popover_widget.main_panel.set_progress,
                      0, 'found: %s' % count)

        # search other persons from db
        # ============================
        if not self.search_all_db_option:
            self.in_search = False
            return
        GLib.idle_add(self.popover_widget.show_other_panel,
                      self.search_all_db_option)

        # get all person handles
        all_person_handles = self.dbstate.db.get_person_handles()

        progress = 0
        count = 0
        if all_person_handles:
            for person_handle in all_person_handles:
                progress += 1
                # excluding found persons
                if person_handle not in self.found_list:
                    if self.check_person(person_handle, search_words):
                        GLib.idle_add(self.do_this, thread_event,
                                      self.add_to_result,
                                      person_handle,
                                      self.popover_widget.other_panel)
                        # wait until person is added to list
                        while not thread_event.wait(timeout=0.01):
                            if not self.in_search:
                                return
                        thread_event.clear()

                        count += 1
                if not self.in_search:
                    return
                GLib.idle_add(self.popover_widget.other_panel.set_progress,
                              progress/len(all_person_handles),
                              'found: %s' % count)
        if not count:
            GLib.idle_add(self.popover_widget.other_panel.add_no_result,
                          _('No persons found...'))

        GLib.idle_add(self.popover_widget.other_panel.set_progress,
                      0, 'found: %s' % count)

        self.in_search = False

    def do_this(self, event, func, *args):
        """
        Do some function (and wait "event" it the thread).
        It should be called by "GLib.idle_add".
        In the end "event" will be set.
        """
        func(*args)
        event.set()

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
        bookmarks = self.bookmarks.get_bookmarks().bookmarks
        if person:
            name = displayer.display_name(person.get_primary_name())

            row = ListBoxRow(description=person.handle, label=name)
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

            if person_handle in bookmarks:
                button = Gtk.Button.new_from_icon_name(
                    'user-bookmarks-symbolic', Gtk.IconSize.MENU)
                button.set_tooltip_text(_('Remove from bookmarks'))
                button.connect('clicked', self.remove_from_bookmarks,
                               person_handle)
                hbox.add(button)
            else:
                button = Gtk.Button.new_from_icon_name(
                    'bookmark-new-symbolic', Gtk.IconSize.MENU)
                button.set_tooltip_text(_('Add to bookmarks'))
                button.connect('clicked', self.add_to_bookmarks, person_handle)
                hbox.add(button)

            panel.add_to_panel(['row', row])

        else:
            # we should return 'True' to restart function from GLib.idle_add
            return True

    def stop_search(self):
        """
        Stop search.
        And wait while thread is finished.
        """
        self.in_search = False

        while self.thread.is_alive():
            self.thread.join()

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

    def add_to_bookmarks(self, widget, handle):
        """
        Adds bookmark for person.
        """
        self.bookmarks.add(handle)

        # change icon and reconnect
        img = Gtk.Image.new_from_icon_name('user-bookmarks-symbolic',
                                           Gtk.IconSize.MENU)
        widget.set_image(img)
        widget.set_tooltip_text(_('Remove from bookmarks'))
        widget.disconnect_by_func(self.add_to_bookmarks)
        widget.connect('clicked', self.remove_from_bookmarks, handle)

    def remove_from_bookmarks(self, widget, handle):
        """
        Remove person from the list of bookmarked people.
        """
        self.bookmarks.remove_handles([handle])
        # change icon and reconnect
        img = Gtk.Image.new_from_icon_name('bookmark-new-symbolic',
                                           Gtk.IconSize.MENU)
        widget.set_image(img)
        widget.set_tooltip_text(_('Add to bookmarks'))
        widget.disconnect_by_func(self.remove_from_bookmarks)
        widget.connect('clicked', self.add_to_bookmarks, handle)

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

    def __init__(self, main_label, other_label, ext_panel=None):
        """
        ext_panel - Gtk.Widget (container) placeed in the botom.
        """
        Gtk.Popover.__init__(self)
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_modal(False)

        # build panels
        self.main_panel = Panel(main_label)
        self.other_panel = Panel(other_label)
        self.other_panel.set_margin_top(10)

        # connect signals
        self.main_panel.list_box.connect("row-activated", self.activate_item)
        self.other_panel.list_box.connect("row-activated", self.activate_item)

        all_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        all_box.add(self.main_panel)
        all_box.add(self.other_panel)

        if ext_panel is not None:
            all_box.add(ext_panel)

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

    def popup(self):
        """
        Different popup depending on gtk version.
        """
        if gtk_version >= 3.22:
            super(self.__class__, self).popup()
        else:
            self.show()

    def popdown(self):
        """
        Different popdown depending on gtk version.
        """
        if gtk_version >= 3.22:
            super(self.__class__, self).popdown()
        else:
            self.hide()

class ListBoxRow(Gtk.ListBoxRow):
    """
    Extended Gtk.ListBoxRow with description property.
    """
    def __init__(self, description=None, label=None):
        Gtk.ListBoxRow.__init__(self)
        self.label = label              # person name for sorting
        self.description = description  # useed to store person handle


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
    def __init__(self, label):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        slb = ScrolledListBox(max_height=200)
        slb.set_policy(Gtk.PolicyType.NEVER,
                       Gtk.PolicyType.AUTOMATIC)

        self.list_box = slb.list_box
        self.list_box.set_activate_on_single_click(True)
        self.list_box.set_sort_func(self.sort_func)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        panel_lable = Gtk.Label(_('<b>%s:</b>') % label)
        panel_lable.set_use_markup(True)
        vbox.add(panel_lable)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        vbox.add(self.progress_bar)

        self.add(vbox)
        self.add(slb)

    def set_progress(self, fraction, text=None):
        """
        Set progress and label.
        """
        self.progress_bar.set_fraction(fraction)
        self.progress_bar.set_text(text)

    def add_to_panel(self, data):
        """
        Add found item to specified panel (ListBox).
        data - ['row', ListBoxRow] or
               ['widget', [Gtk.Widget, description, label]]
        """
        if data[0] == 'row':
            row = data[1]
        elif data[0] == 'widget':
            row = ListBoxRow(description=data[1][1], label=data[1][2])
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
        self.set_progress(0)

    def sort_func(self, row_1, row_2):
        def get_row_label(row):
            # get persons names to sort rows
            # row -> hbox -> (id_label, name_label, image)
            try:
                row_children = row.get_children()
                box_children = row_children[0].get_children()
                # label in box than contain person name
                row_label = box_children[1]
                return row_label.get_text().lower()
            except:
                return None
        return get_row_label(row_1) > get_row_label(row_2)
