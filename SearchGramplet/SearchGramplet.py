#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2022  vantu5z <vantu5z@mail.ru>
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

# $Id: $

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import pickle
from threading import Event
from queue import Queue, Empty
from gi.repository import Gtk, Gdk, GLib, GObject, GdkPixbuf

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.plug import Gramplet

from gramps.gen import datehandler
from gramps.gen.display.name import displayer
from gramps.gen.config import config
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 find_parents)
from gramps.gen.utils.file import media_path_full, find_file
from gramps.gen.utils.thumbnails import get_thumbnail_path
from gramps.gen.errors import WindowActiveError

from gramps.gui.editors import EditPerson
from gramps.gui.ddtargets import DdTargets
from gramps.gui.widgets.menuitem import add_menuitem

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------
# gtk version
gtk_version = float("%s.%s" % (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION))

# mark icons
STARRED = 'starred'
NON_STARRED = 'non-starred'

#-------------------------------------------------------------------------
#
# Configuration
#
#-------------------------------------------------------------------------
CONFIG = config.register_manager('search_gramplet')
CONFIG.register("options.show_images", True)
CONFIG.register("options.marked_first", True)
CONFIG.register("search.persons", True)
CONFIG.register("search.families", True)
CONFIG.load()
CONFIG.save()
#-------------------------------------------------------------------------
#
# Search Gramplet
#
#-------------------------------------------------------------------------
class SearchGramplet(Gramplet):
    """
    Search Gramplet.
    """
    def init(self):
        # load
        # {option_name: [value, label]}
        self.options = {
            "options.show_images": [CONFIG.get("options.show_images"),
                                    _('Show images')],
            "options.marked_first": [CONFIG.get("options.marked_first"),
                                     _('Show bookmarked first')],
        }
        # {option_name: [value, label, nav_type]}
        self.search_options = {
            "search.persons": [CONFIG.get("search.persons"),
                               _('Persons'), 'Person'],
            "search.families": [CONFIG.get("search.families"),
                                _('Families'), 'Family'],
        }

        self.top = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.top)
        self.top.show_all()

        if self.dbstate.is_open():
            self.bookmarks = self.dbstate.db.get_bookmarks()
        else:
            self.bookmarks = None

        self.search_words = None
        # search status
        self.stop_search_event = Event()
        # queues used for search
        self.queue = Queue()

        self.empty_search(None)

    def build_gui(self):
        """
        Build gramplet GUI.
        """
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5,
                       margin_top=5, margin_left=5, margin_right=5)
        search_obj_btn = Gtk.Button.new_from_icon_name(
            "category-search-symbolic", Gtk.IconSize.BUTTON)
        self.obj_popover = OptionsPopover(search_obj_btn,
                                          _('Select objects to search'),
                                          self.search_options)
        search_obj_btn.connect('clicked', self.obj_popover.popup)
        hbox.add(search_obj_btn)

        s_entry = SearchEntry()
        s_entry.connect('start-search', self.start_search)
        s_entry.connect('empty-search', self.empty_search)
        hbox.add(s_entry)

        config_btn = Gtk.Button.new_from_icon_name("gramps-config",
                                                   Gtk.IconSize.BUTTON)
        self.config_popover = OptionsPopover(config_btn, _('Configuration'),
                                             self.options)
        config_btn.connect('clicked', self.config_popover.popup)
        hbox.add(config_btn)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add(hbox)

        self.search_panel = Panel()
        box.pack_end(self.search_panel, True, True, 5)

        return box

    def db_changed(self):
        """
        Called when db is changed.
        """
        self.bookmarks = self.dbstate.db.get_bookmarks()

    def start_search(self, widget, search_words):
        """
        Start search process.
        """
        self.stop_search()
        self.search_panel.clear_items()

        self.stop_search_event = Event()

        all_person_handles = self.dbstate.db.get_person_handles()

        GLib.idle_add(self.make_search, self.queue,
                      self.stop_search_event, all_person_handles, search_words,
                      priority=GLib.PRIORITY_LOW-10)

        GLib.idle_add(self.apply_search, self.queue,
                      self.search_panel, self.stop_search_event,
                      priority=GLib.PRIORITY_LOW)

    def make_search(self, queue, stop_search_event,
                    items_list, search_words):
        """
        Recursive search persons in "items_list".
        Use "GLib.idle_add()" to make UI responsiveness.
        Param 'items_list' - list of person_handles.
        """
        if not items_list or stop_search_event.is_set():
            queue.put('stop')
            return

        try:
            item = items_list.pop()
        except (KeyError, IndexError):
            queue.put('stop')
            return

        person = self.check_person(item, search_words)
        if person:
            queue.put(person)

        GLib.idle_add(self.make_search, queue,
                      stop_search_event, items_list, search_words)

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
                panel.add_no_result(_('No matches...'))
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
        bookmarks = self.bookmarks.get()
        if person:
            name = displayer.display_name(person.get_primary_name())

            row = ListBoxRow(person_handle=person.handle, label=name,
                             dbstate=self.dbstate, uistate=self.uistate)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add(hbox)

            # add person name
            label = Gtk.Label(name, wrap=True, xalign=0)
            hbox.pack_start(label, True, True, 2)
            # add person image if needed
            if self.options["options.show_images"][0]:
                person_image = self.get_person_image(person, 32, 32,
                                                     kind='image')
                if person_image:
                    hbox.pack_start(person_image, False, True, 2)

            if person.handle in bookmarks:
                button = Gtk.Button.new_from_icon_name(
                    STARRED, Gtk.IconSize.MENU)
                button.set_tooltip_text(_('Remove from bookmarks'))
                button.set_relief(Gtk.ReliefStyle.NONE)
                button.connect('clicked', self.remove_from_bookmarks,
                               person.handle)
                hbox.add(button)
            else:
                button = Gtk.Button.new_from_icon_name(
                    NON_STARRED, Gtk.IconSize.MENU)
                button.set_tooltip_text(_('Add to bookmarks'))
                button.set_relief(Gtk.ReliefStyle.NONE)
                button.connect('clicked', self.add_to_bookmarks, person.handle)
                hbox.add(button)

            if self.options["options.marked_first"][0]:
                row.marked = person.handle in bookmarks

            panel.add_to_panel(row)

    def stop_search(self, widget=None):
        """
        Stop search process.
        """
        self.stop_search_event.set()
        self.queue = Queue()

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

    def add_to_bookmarks(self, widget, handle):
        """
        Adds bookmark for person.
        """
        self.bookmarks.append(handle)

        # change icon and reconnect
        img = Gtk.Image.new_from_icon_name(STARRED,
                                           Gtk.IconSize.MENU)
        widget.set_image(img)
        widget.set_tooltip_text(_('Remove from bookmarks'))
        widget.disconnect_by_func(self.add_to_bookmarks)
        widget.connect('clicked', self.remove_from_bookmarks, handle)

    def remove_from_bookmarks(self, widget, handle):
        """
        Remove person from the list of bookmarked people.
        """
        self.bookmarks.remove(handle)
        # change icon and reconnect
        img = Gtk.Image.new_from_icon_name(NON_STARRED,
                                           Gtk.IconSize.MENU)
        widget.set_image(img)
        widget.set_tooltip_text(_('Add to bookmarks'))
        widget.disconnect_by_func(self.remove_from_bookmarks)
        widget.connect('clicked', self.add_to_bookmarks, handle)

    def empty_search(self, widget):
        """
        Hint on empty search.
        """
        self.stop_search()
        self.search_panel.add_no_result(_('Start type to search'))

    def get_person_image(self, person, width=-1, height=-1, kind='image'):
        """
        kind - 'image', 'path', 'both'
        Returns default person image and path or None.
        """
        # see if we have an image to use for this person
        image_path = None
        media_list = person.get_media_list()
        if media_list:
            media_handle = media_list[0].get_reference_handle()
            media = self.dbstate.db.get_media_from_handle(media_handle)
            media_mime_type = media.get_mime_type()
            if media_mime_type[0:5] == "image":
                rectangle = media_list[0].get_rectangle()
                path = media_path_full(self.dbstate.db, media.get_path())
                image_path = get_thumbnail_path(path, rectangle=rectangle)
                # test if thumbnail actually exists in thumbs
                # (import of data means media files might not be present
                image_path = find_file(image_path)
        if image_path:
            if kind == 'path':
                return image_path
            # get and scale image
            person_image = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                filename=image_path,
                width=width, height=height,
                preserve_aspect_ratio=True)
            person_image = Gtk.Image.new_from_pixbuf(person_image)
            if kind == 'image':
                return person_image
            elif kind == 'both':
                return person_image, image_path

        return None


class SearchEntry(Gtk.SearchEntry):
    """
    Search entry widget for persons search.
    """

    __gsignals__ = {
        'start-search': (GObject.SignalFlags.RUN_FIRST, None, (object, )),
        'empty-search': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'focus-to-result': (GObject.SignalFlags.RUN_FIRST, None, ()),
        }

    def __init__(self, **kwargs):
        Gtk.SearchEntry.__init__(self, **kwargs)

        self.set_hexpand(True)
        self.set_tooltip_text(
            _('Search objects in database.'))
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


class Panel(Gtk.Box):
    """
    Panel for found items.
    Contain in vertical Gtk.Box: Status, Scrolled list.
    """
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        sw = Gtk.ScrolledWindow(vexpand=True)
        sw.set_policy(Gtk.PolicyType.NEVER,
                      Gtk.PolicyType.AUTOMATIC)
        self.list_box = Gtk.ListBox()
        self.list_box.set_activate_on_single_click(True)
        self.list_box.set_sort_func(self.sort_func)
        sw.add(self.list_box)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        vbox.add(self.progress_bar)

        self.add(vbox)
        self.add(sw)

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


class ListBoxRow(Gtk.ListBoxRow):
    """
    Extended Gtk.ListBoxRow with person DnD support.
    """
    def __init__(self, person_handle=None, label='', marked=False,
                 dbstate=None, uistate=None):
        Gtk.ListBoxRow.__init__(self)

        self.label = label                  # person name for sorting
        self.person_handle = person_handle
        self.marked = marked                # is bookmarked (used for sorting)
        self.dbstate = dbstate
        self.uistate = uistate
        self.kind = 'Person'

        self.set_has_tooltip(True)
        self.connect('query-tooltip', self.query_tooltip)
        self.connect('button-press-event', self.button_press)
        self.setup_dnd()

    def add(self, widget):
        """
        Override "container.add" to catch drag events.
        Pack content of ListBoxRow to Gtk.EventBox.
        """
        ebox = Gtk.EventBox()
        ebox.add(widget)
        super().add(ebox)

    def button_press(self, widget, event):
        """
        Handle mouse button press.
        """
        button = event.get_button()[1]
        # show popup menu by right mouse button
        if button == 3 and self.dbstate:
            menu = PopupMenu(self.dbstate, self.uistate,
                             self.kind, self.person_handle)
            menu.show_menu()
        return True     # stop event emission

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
        if (self.get_tooltip_text() is None) and (self.dbstate is not None):
            person = self.dbstate.db.get_person_from_handle(self.person_handle)
            text = self.get_person_tooltip(person)
            if text:
                self.set_tooltip_text(text)
            else:
                self.set_has_tooltip(False)

    def get_person_tooltip(self, person):
        """
        Get Person tooltip string.
        """
        # get birth/christening and death/burying date strings.
        birth_event = get_birth_or_fallback(self.dbstate.db, person)
        if birth_event:
            birth = datehandler.get_date(birth_event)
        else:
            birth = ''

        death_event = get_death_or_fallback(self.dbstate.db, person)
        if death_event:
            death = datehandler.get_date(death_event)
        else:
            death = ''

        # get list of parents.
        parents = []

        parents_list = find_parents(self.dbstate.db, person)
        for parent_id in parents_list:
            if not parent_id:
                continue
            parent = self.dbstate.db.get_person_from_handle(parent_id)
            if not parent:
                continue
            parents.append(displayer.display(parent))

        # build tooltip string
        tooltip = 'ID: %s\n' % person.gramps_id
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


class OptionsPopover(Gtk.Popover):
    """
    Configuration Popover.
    """
    def __init__(self, widget, label, options):
        Gtk.Popover.__init__(self, relative_to=widget,
                             position=Gtk.PositionType.BOTTOM)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3,
                           margin_top=3, margin_left=3, margin_right=3)
        self.box.add(Gtk.Label(label))

        self.options = options

        for option, item in self.options.items():
            check_btn = Gtk.CheckButton(item[1])
            check_btn.set_active(item[0])
            check_btn.connect('clicked', self.option_changed, option)
            self.box.add(check_btn)
        self.box.show_all()
        self.add(self.box)

    def popup(self, *args):
        """
        Different popup depending on gtk version.
        """
        if gtk_version >= 3.22:
            super().popup()
        else:
            self.show()

    def popdown(self, *args):
        """
        Different popdown depending on gtk version.
        """
        if gtk_version >= 3.22:
            super().popdown()
        else:
            self.hide()

    def option_changed(self, check_btn, option):
        """
        Save option state.
        """
        CONFIG.set(option, check_btn.get_active())
        CONFIG.save()
        self.options[option][0] = check_btn.get_active()


class PopupMenu(Gtk.Menu):
    """
    Produce popup widget for right-click menu.
    """
    def __init__(self, dbstate, uistate, kind=None, handle=None):
        """
        db:     dbstate.db
        kind:   'Person', 'Family'
        handle: person or family handle
        """
        Gtk.Menu.__init__(self)
        self.set_reserve_toggle_size(False)

        self.dbstate = dbstate
        self.uistate = uistate
        self.actions = Actions(self.dbstate, self.uistate)

        self.kind = kind
        if kind == 'Person' and handle is not None:
            self.build_person_menu(handle)
        elif kind == 'Family' and handle is not None:
            pass
        else:
            pass

    def show_menu(self, event=None):
        """
        Show popup menu.
        """
        if gtk_version >= 3.22:
            self.popup_at_pointer(event)
        else:
            if event:
                self.popup(None, None, None, None,
                           event.get_button()[1], event.time)
            else:
                self.popup(None, None, None, None,
                           0, Gtk.get_current_event_time())

    def build_person_menu(self, person_handle):
        """
        Generate menu for person item.
        """
        add_menuitem(self, _('Edit'),
                     person_handle, self.actions.edit_person)
        add_menuitem(self, _('Set as Active person'),
                     [person_handle, self.kind], self.actions.set_active)
        add_menuitem(self, _('Set as Home person'),
                     person_handle, self.actions.edit_person)


class Actions():
    """
    Define actions.
    Parameter "obj" packed by MenuItemWithData().set_data(...),
    and should be unpacked by "obj.get_data()"
    """
    def __init__(self, dbstate, uistate):
        self.dbstate = dbstate
        self.uistate = uistate

    def edit_person(self, obj):
        """
        Start a person editor for the selected person.
        """
        handle = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def set_active(self, obj):
        """
        Set person as active.
        """
        handle, nav_type = obj.get_data()
        self.uistate.set_active(handle, nav_type)

    def set_home_person(self, obj):
        """
        Set home person for database.
        """
        handle = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            self.dbstate.db.set_default_person_handle(handle)
