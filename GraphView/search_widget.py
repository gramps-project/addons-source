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

import pickle

from gi.repository import Gtk, Gdk, GLib, GObject
from threading import Event
from queue import Queue, Empty

from gramps.gen import datehandler
from gramps.gen.display.name import displayer
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 find_parents)
from gramps.gui.ddtargets import DdTargets

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# gtk version
gtk_version = float("%s.%s" % (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION))

# mark icons
starred = 'starred'
non_starred = 'non-starred'


class SearchWidget(GObject.GObject):
    """
    Search widget for persons search.
    SearchEntry to input text.
    Popover to display results.
    """

    __gsignals__ = {
        'item-activated': (GObject.SignalFlags.RUN_FIRST, None, (str, )),
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

        self.get_person_image = get_person_image

        self.search_entry = SearchEntry()
        self.popover_widget = Popover(_('Persons from current graph'),
                                      _('Other persons from database'))
        self.popover_widget.set_relative_to(self.search_entry)

        # connect signals
        self.popover_widget.connect('item-activated', self.activate_item)
        self.popover_widget.connect('closed', self.stop_search)
        self.search_entry.connect('start-search', self.start_search)
        self.search_entry.connect('empty-search', self.hide_search_popover)
        self.search_entry.connect('focus-to-result', self.focus_results)

        # set default options
        self.search_all_db_option = True
        self.show_images_option = True
        self.show_marked_first = True

        self.search_words = None
        # search status
        self.stop_search_event = Event()
        # queues used for search
        self.graph_queue = Queue()
        self.other_queue = Queue()

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

    def get_items_handles(self):
        """
        Convert self.items_list (GooCanvas.CanvasGroup objects) to handles.
        """
        items_list = set()
        if self.items_list:
            if isinstance(self.items_list[0], str):
                items_list = self.items_list
            else:
                for item in self.items_list:
                    items_list.add(item.title)  # get handles
        return items_list

    def set_options(self, search_all_db=None, show_images=None,
                    marked_first=None):
        """
        Set options for search.
        """
        if search_all_db is not None:
            self.search_all_db_option = search_all_db
        if show_images is not None:
            self.show_images_option = show_images
        if marked_first is not None:
            self.show_marked_first = marked_first

    def activate_item(self, widget, person_handle):
        """
        Activate item in results.
        """
        if person_handle is not None:
            self.emit('item-activated', person_handle)

    def start_search(self, widget, search_words):
        """
        Start search process.
        """
        self.stop_search()
        self.popover_widget.clear_items()
        self.popover_widget.popup()

        self.stop_search_event = Event()

        current_person_list = self.get_items_handles()

        # search for current graph

        GLib.idle_add(self.make_search, self.graph_queue,
                      self.stop_search_event, current_person_list.copy(),
                      search_words,
                      priority=GLib.PRIORITY_LOW-10)

        GLib.idle_add(self.apply_search, self.graph_queue,
                      self.popover_widget.main_panel, self.stop_search_event,
                      priority=GLib.PRIORITY_LOW)

        # search all db

        self.popover_widget.show_other_panel(self.search_all_db_option)
        if not self.search_all_db_option:
            return

        all_person_handles = self.dbstate.db.get_person_handles()

        GLib.idle_add(self.make_search, self.other_queue,
                      self.stop_search_event, all_person_handles, search_words,
                      current_person_list.copy(),
                      priority=GLib.PRIORITY_LOW-10)

        GLib.idle_add(self.apply_search, self.other_queue,
                      self.popover_widget.other_panel, self.stop_search_event,
                      priority=GLib.PRIORITY_LOW)

    def make_search(self, queue, stop_search_event,
                    items_list, search_words, exclude=[]):
        """
        Recursive search persons in "items_list".
        Use "GLib.idle_add()" to make UI responsiveness.
        Params 'items_list' and 'exclude' - list of person_handles.
        """
        if not items_list or stop_search_event.is_set():
            queue.put('stop')
            return

        while True:
            try:
                item = items_list.pop()
            except (KeyError, IndexError):
                queue.put('stop')
                return
            if item not in exclude:
                break

        person = self.check_person(item, search_words)
        if person:
            queue.put(person)

        GLib.idle_add(self.make_search, queue,
                      stop_search_event, items_list, search_words, exclude)

    def apply_search(self, queue, panel, stop_search_event, count=0):
        """
        Recursive add persons to specified panel from queue.
        Use GLib.idle_add() to communicate with GUI.
        """
        if stop_search_event.is_set():
            return
        try:
            person = queue.get(timeout=0.05)
        except Exception as err:
            if type(err) is Empty:
                GLib.idle_add(self.apply_search, queue, panel,
                              stop_search_event, count)
            return

        if person == 'stop':
            panel.set_progress(0, _('found: %s') % count)
            if count == 0:
                panel.add_no_result(_('No persons found...'))
            return

        # insert person to panel
        self.add_to_result(person, panel)

        # calculate and update progress
        count += 1
        try:
            found_count = count + queue.qsize()
            if found_count > 0:
                progress = count/found_count
            else:
                progress = 0
        except NotImplementedError:
            progress = 0

        panel.set_progress(progress, _('found: %s') % count)

        GLib.idle_add(self.apply_search, queue, panel,
                      stop_search_event, count)

    def add_to_result(self, person, panel):
        """
        Add found person to results.
        """
        bookmarks = self.bookmarks.get_bookmarks().bookmarks
        if person:
            name = displayer.display_name(person.get_primary_name())

            row = ListBoxRow(person_handle=person.handle, label=name,
                             db=self.dbstate.db)
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

            if person.handle in bookmarks:
                button = Gtk.Button.new_from_icon_name(
                    starred, Gtk.IconSize.MENU)
                button.set_tooltip_text(_('Remove from bookmarks'))
                button.set_relief(Gtk.ReliefStyle.NONE)
                button.connect('clicked', self.remove_from_bookmarks,
                               person.handle)
                hbox.add(button)
            else:
                button = Gtk.Button.new_from_icon_name(
                    non_starred, Gtk.IconSize.MENU)
                button.set_tooltip_text(_('Add to bookmarks'))
                button.set_relief(Gtk.ReliefStyle.NONE)
                button.connect('clicked', self.add_to_bookmarks, person.handle)
                hbox.add(button)

            if self.show_marked_first:
                row.marked = person.handle in bookmarks

            panel.add_to_panel(row)

    def stop_search(self, widget=None):
        """
        Stop search process.
        """
        self.stop_search_event.set()

        self.graph_queue = Queue()
        self.other_queue = Queue()

    def check_person(self, person_handle, search_words):
        """
        Check if person name and id contains all words of the search.
        """
        try:
            # try used for not person handles
            # and other problems to get person
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
            return person
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
        img = Gtk.Image.new_from_icon_name(starred,
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
        img = Gtk.Image.new_from_icon_name(non_starred,
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
        'start-search': (GObject.SignalFlags.RUN_FIRST, None, (object, )),
        'empty-search': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'focus-to-result': (GObject.SignalFlags.RUN_FIRST, None, ()),
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
        'item-activated': (GObject.SignalFlags.RUN_FIRST, None, (str, )),
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
        handle = row.person_handle
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
    Extended Gtk.ListBoxRow with person DnD support.
    """
    def __init__(self, person_handle=None, label='', marked=False, db=None):
        Gtk.ListBoxRow.__init__(self)

        self.label = label                  # person name for sorting
        self.person_handle = person_handle
        self.marked = marked                # is bookmarked (used for sorting)
        self.database = db                  # database to get tooltip

        self.set_has_tooltip(True)
        self.connect('query-tooltip', self.query_tooltip)
        self.setup_dnd()

    def add(self, widget):
        """
        Override "container.add" to catch drag events.
        Pack content of ListBoxRow to Gtk.EventBox.
        """
        ebox = Gtk.EventBox()
        ebox.add(widget)
        super().add(ebox)

    def setup_dnd(self):
        """
        Setup drag-n-drop.
        """
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                             [],
                             Gdk.DragAction.COPY)
        tglist = Gtk.TargetList.new([])
        tglist.add(DdTargets.PERSON_LINK.atom_drag_type,
                   DdTargets.PERSON_LINK.target_flags,
                   DdTargets.PERSON_LINK.app_id)
        self.drag_source_set_target_list(tglist)

        self.connect("drag-data-get", self.drag_data_get)

        self.drag_source_set_icon_name('gramps-person')

    def drag_data_get(self, widget, context, sel_data, info, time):
        """
        Returned parameters after drag.
        """
        data = (DdTargets.PERSON_LINK.drag_type,
                id(widget), self.person_handle, 0)
        sel_data.set(sel_data.get_target(), 8, pickle.dumps(data))

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Get tooltip for person on demand.
        """
        if (self.get_tooltip_text() is None) and (self.database is not None):
            person = self.database.get_person_from_handle(self.person_handle)
            text = get_person_tooltip(person, self.database)
            if text:
                self.set_tooltip_text(text)
            else:
                self.set_has_tooltip(False)


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
        panel_lable = Gtk.Label(label=_('<b>%s:</b>') % label)
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

    def add_to_panel(self, row):
        """
        Add found item to panel (ListBox).
        row - ListBoxRow
        """
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
        self.set_progress(0, '')

    def sort_func(self, row_1, row_2):
        """
        Function to sort rows by person name.
        Priority for bookmarked persons.
        """
        # both rows are marked or not
        if row_1.marked == row_2.marked:
            return row_1.label > row_2.label
        # if one row is marked
        return row_2.marked


def get_person_tooltip(person, database):
    """
    Get Person tooltip string.
    """
    # get birth/christening and death/burying date strings.
    birth_event = get_birth_or_fallback(database, person)
    if birth_event:
        birth = datehandler.get_date(birth_event)
    else:
        birth = ''

    death_event = get_death_or_fallback(database, person)
    if death_event:
        death = datehandler.get_date(death_event)
    else:
        death = ''

    # get list of parents.
    parents = []

    parents_list = find_parents(database, person)
    for parent_id in parents_list:
        if not parent_id:
            continue
        parent = database.get_person_from_handle(parent_id)
        if not parent:
            continue
        parents.append(displayer.display(parent))

    # build tooltip string
    tooltip = ''
    if birth:
        tooltip += _('Birth: %s' % birth)
    if death:
        if tooltip:
            tooltip += '\n'
        tooltip += _('Death: %s' % death)

    if (birth or death) and parents:
        tooltip += '\n\n'

    if parents:
        tooltip += _('Parents:')
        for p in parents:
            tooltip += ('\n  %s' % p)

    return tooltip
