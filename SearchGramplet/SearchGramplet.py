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
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer
from gramps.gen.config import config
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 find_parents)
from gramps.gen.utils.file import media_path_full, find_file
from gramps.gen.utils.thumbnails import get_thumbnail_path
from gramps.gen.errors import WindowActiveError

from gramps.gui.editors import EditPerson
from gramps.gui.views.tags import EditTag
from gramps.gui.ddtargets import DdTargets, _DdType
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
CONFIG.register("options.sort_by_kind", True)
CONFIG.register("search.persons", True)
CONFIG.register("search.tags", True)
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
        # {option_name: [value, label]}
        self.options = {
            "options.show_images": [CONFIG.get("options.show_images"),
                                    _('Show images')],
            "options.marked_first": [CONFIG.get("options.marked_first"),
                                     _('Show bookmarked first')],
            "options.sort_by_kind": [CONFIG.get("options.sort_by_kind"),
                                     _('Sort by object type')],
        }
        # {option_name: [value, label, nav_type]}
        self.search_options = {
            "search.persons": [CONFIG.get("search.persons"),
                               _('Persons'), 'Person'],
            "search.tags": [CONFIG.get("search.tags"),
                            _('Tags'), 'Tag'],
        }

        self.top = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.top)
        self.top.show_all()

        self.search_words = None
        # search events
        self.stop_search_event = Event()
        self.finish_events = {'Person': Event(),
                              'Tag': Event(),
                              }
        # queue for search
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
        search_obj_btn.set_tooltip_text(_('Menu to set search objects'))
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
        config_btn.set_tooltip_text(_('SearchGramplet configuration menu'))
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
        pass

    def start_search(self, widget, search_words):
        """
        Start search process.
        """
        self.stop_search()
        self.search_panel.clear_items()

        self.stop_search_event = Event()
        self.finish_events = {'Person': Event(),
                              'Tag': Event(),
                              }

        if self.search_options['search.persons'][0]:
            all_person_handles = self.dbstate.db.get_person_handles()

            GLib.idle_add(self.make_search, self.queue,
                          self.stop_search_event, self.finish_events,
                          all_person_handles, search_words,
                          self.search_options['search.persons'][2],
                          priority=GLib.PRIORITY_LOW-10)
        else:
            self.finish_events['Person'].set()

        if self.search_options['search.tags'][0]:
            all_tags_handles = self.dbstate.db.get_tag_handles()

            GLib.idle_add(self.make_search, self.queue,
                          self.stop_search_event, self.finish_events,
                          all_tags_handles, search_words,
                          self.search_options['search.tags'][2],
                          priority=GLib.PRIORITY_LOW-10)
        else:
            self.finish_events['Tag'].set()

        GLib.idle_add(self.apply_search, self.queue, self.search_panel,
                      self.stop_search_event, self.finish_events,
                      priority=GLib.PRIORITY_LOW)

    def make_search(self, queue, stop_search_event, finish_events,
                    items_list, search_words, kind):
        """
        Recursive search persons in "items_list".
        Use "GLib.idle_add()" to make UI responsiveness.
        Param 'items_list' - list of person_handles.
        """
        if not items_list or stop_search_event.is_set():
            finish_events[kind].set()
            return

        try:
            handle = items_list.pop()
        except (KeyError, IndexError):
            finish_events[kind].set()
            return

        if kind == self.search_options['search.persons'][2]:
            obj = self.check_person(handle, search_words)
        elif kind == self.search_options['search.tags'][2]:
            obj = self.check_tag(handle, search_words)
        else:
            obj = False

        if obj:
            queue.put((obj, kind))

        GLib.idle_add(self.make_search, queue,
                      stop_search_event, finish_events,
                      items_list, search_words, kind)

    def apply_search(self, queue, panel, stop_search_event, finish_events,
                     count=0):
        """
        Recursive add persons to specified panel from queue.
        Use GLib.idle_add() to communicate with GUI.
        """
        if stop_search_event.is_set():
            return
        try:
            item = queue.get(timeout=0.05)
        except Exception as err:
            if type(err) is Empty:
                done = True
                for event in finish_events.values():
                    if not event.is_set():
                        done = False
                        break
                if done:
                    panel.set_progress(0, _('found: %s') % count)
                    if count == 0:
                        panel.add_no_result(_('No matches...'))
                    return
                GLib.idle_add(self.apply_search, queue, panel,
                              stop_search_event, finish_events, count)
            return

        # insert person to panel
        self.add_to_result(item[0], item[1], panel)

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
                      stop_search_event, finish_events, count)

    def add_to_result(self, obj, kind, panel):
        """
        Add found person to results.
        """
        row = ListBoxRow(handle=obj.get_handle(), kind=kind,
                         dbstate=self.dbstate, uistate=self.uistate,
                         options=self.options,
                         search_options=self.search_options)
        panel.add_to_panel(row)

    def stop_search(self, widget=None):
        """
        Stop search process.
        """
        self.stop_search_event.set()
        for event in self.finish_events.values():
            event.set()
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
            if len(search_words) == 1 and search_words[0] == '*':
                return person
            name = displayer.display_name(person.get_primary_name()).lower()
            search_str = name + person.gramps_id.lower()
            search_str += self.get_person_dates(person)
            for word in search_words:
                if word not in search_str:
                    # if some of words not present in the person name
                    return False
            return person
        return False

    def check_tag(self, handle, search_words):
        """
        Check if tag contains all words of the search.
        """
        try:
            tag = self.dbstate.db.get_tag_from_handle(handle)
        except:
            return False

        if tag:
            if len(search_words) == 1 and search_words[0] == '*':
                return tag
            search_str = tag.get_name().lower()
            for word in search_words:
                if word not in search_str:
                    return False
            return tag
        return False

    def empty_search(self, widget):
        """
        Hint on empty search.
        """
        self.stop_search()
        self.search_panel.add_no_result(_('Start type to search'))

    def get_person_dates(self, person):
        """
        Get birth/christening and death/burying dates strings.
        """
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
        return birth + death


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
            _('Start type to search objects.\n'
              'To show all objects enter only «*» symbol.'))
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

        CONFIG.connect("options.sort_by_kind", self.invalidate_sort)

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
        Return True if row_1 should be placed after row_2.
        Priority for bookmarked persons.
        """
        # different kind
        if CONFIG.get('options.sort_by_kind'):
            if row_1.kind != row_2.kind:
                return row_1.kind > row_2.kind
        # both rows are marked or not
        if row_1.marked == row_2.marked:
            return row_1.label > row_2.label
        # if one row is marked
        return row_2.marked

    def invalidate_sort(self, *args):
        """
        Update sorting.
        """
        self.list_box.invalidate_sort()


class ListBoxRow(Gtk.ListBoxRow):
    """
    Extended Gtk.ListBoxRow with person DnD support.
    """
    def __init__(self, handle=None, kind='', marked=False,
                 dbstate=None, uistate=None,
                 options=[], search_options=[]):
        Gtk.ListBoxRow.__init__(self)

        self.label = ''                     # object string for sorting
        self.handle = handle
        self.marked = marked                # is bookmarked (used for sorting)
        self.dbstate = dbstate
        self.uistate = uistate
        self.kind = kind
        self.bookmarks = None
        self.options = options
        self.search_options = search_options

        if self.search_options:
            if self.kind == self.search_options['search.persons'][2]:
                self.build_person(self.handle)
                self.set_has_tooltip(True)
            elif self.kind == self.search_options['search.tags'][2]:
                self.build_tag(self.handle)
        self.connect('query-tooltip', self.query_tooltip)
        self.connect('button-press-event', self.button_press)

    def add(self, widget):
        """
        Override "container.add" to catch drag events.
        Pack content of ListBoxRow to Gtk.EventBox.
        """
        ebox = Gtk.EventBox()
        ebox.add(widget)
        self.setup_dnd(ebox)
        super().add(ebox)

    def button_press(self, widget, event):
        """
        Handle mouse button press.
        """
        if self.dbstate is None:
            return True

        button = event.get_button()[1]
        # edit person by double click
        if button == 1 and event.type == getattr(Gdk.EventType,
                                                 "DOUBLE_BUTTON_PRESS"):
            data = ItemWithData()
            if self.kind == self.search_options['search.persons'][2]:
                data.set_data([self.handle, self.update_person])
                Actions(self.dbstate, self.uistate).edit_person(data)
            elif self.kind == self.search_options['search.tags'][2]:
                data.set_data([self.handle, self.update_tag_color])
                Actions(self.dbstate, self.uistate).edit_tag(data)
        # show popup menu by right mouse button
        if button == 3:
            menu = PopupMenu(self, self.dbstate, self.uistate,
                             self.kind, self.handle)
            menu.show_menu()
        return True     # stop event emission

    def setup_dnd(self, ebox):
        """
        Setup drag-n-drop.
        """
        if not self.kind:
            return

        ebox.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                             [],
                             Gdk.DragAction.COPY)
        tglist = Gtk.TargetList.new([])
        if self.kind == self.search_options['search.persons'][2]:
            tglist.add(DdTargets.PERSON_LINK.atom_drag_type,
                       DdTargets.PERSON_LINK.target_flags,
                       DdTargets.PERSON_LINK.app_id)
            ebox.drag_source_set_icon_name('gramps-person')
        elif self.kind == self.search_options['search.tags'][2]:
            # add new target type for tag
            tag_target = _DdType(DdTargets, 'gramps-tag')
            tglist.add(tag_target.atom_drag_type,
                       tag_target.target_flags,
                       tag_target.app_id)
            ebox.drag_source_set_icon_name('gramps-tag')

        ebox.drag_source_set_target_list(tglist)
        ebox.connect("drag-data-get", self.drag_data_get)

    def drag_data_get(self, widget, context, sel_data, info, time):
        """
        Returned parameters after drag.
        """
        if self.kind == self.search_options['search.persons'][2]:
            data = (DdTargets.PERSON_LINK.drag_type,
                    id(widget), self.handle, 0)
        elif self.kind == self.search_options['search.tags'][2]:
            data = ('gramps-tag', id(widget), self.handle, 0)

        sel_data.set(sel_data.get_target(), 8, pickle.dumps(data))

    def build_person(self, handle):
        """
        Build person row.
        """
        self.bookmarks = self.dbstate.db.get_bookmarks().get()
        person = self.dbstate.db.get_person_from_handle(handle)
        self.label = displayer.display_name(person.get_primary_name())

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add(hbox)

        # add icon
        hbox.add(Gtk.Image.new_from_icon_name('gramps-person',
                                              Gtk.IconSize.MENU))
        # add person name
        self.person_label = Gtk.Label(self.label, wrap=True, xalign=0)
        hbox.pack_start(self.person_label, True, True, 2)
        # add person image if needed
        if self.options["options.show_images"][0]:
            person_image = self.get_person_image(person, 32, 32,
                                                 kind='image')
            if person_image:
                hbox.pack_start(person_image, False, True, 2)

        if handle in self.bookmarks:
            button = Gtk.Button.new_from_icon_name(
                STARRED, Gtk.IconSize.MENU)
            button.set_tooltip_text(_('Remove from bookmarks'))
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.connect('clicked', self.remove_from_bookmarks,
                           handle)
            hbox.add(button)
        else:
            button = Gtk.Button.new_from_icon_name(
                NON_STARRED, Gtk.IconSize.MENU)
            button.set_tooltip_text(_('Add to bookmarks'))
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.connect('clicked', self.add_to_bookmarks, handle)
            hbox.add(button)

        if self.options["options.marked_first"][0]:
            self.marked = handle in self.bookmarks

    def update_person(self, person):
        """
        Update person row data on change.
        """
        self.label = displayer.display_name(person.get_primary_name())
        self.person_label.set_label(self.label)

    def build_tag(self, handle):
        """
        Build tag row.
        """
        tag = self.dbstate.db.get_tag_from_handle(handle)
        self.label = tag.get_name()

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add(hbox)

        # add icon
        hbox.add(Gtk.Image.new_from_icon_name('gramps-tag',
                                              Gtk.IconSize.MENU))
        # add tag name
        label = Gtk.Label(self.label, wrap=True, xalign=0)
        hbox.pack_start(label, True, True, 2)

        # add color button
        self.color_btn = Gtk.ColorButton()
        self.update_tag_color(tag)
        self.color_btn.connect(
            'color-set', Actions(self.dbstate, self.uistate).set_tag_color, tag)
        hbox.add(self.color_btn)

    def update_tag_color(self, tag):
        """
        Update tag color in button.
        """
        rgba = Gdk.RGBA()
        rgba.parse(tag.get_color())
        color = rgba.to_color()
        self.color_btn.set_color(color)

    def query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Get tooltip for person on demand.
        """
        if self.get_tooltip_text() is not None:
            return
        if self.dbstate is None:
            self.set_has_tooltip(False)
            return

        if self.kind == self.search_options['search.persons'][2]:
            person = self.dbstate.db.get_person_from_handle(self.handle)
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
        self.options[option][0] = check_btn.get_active()
        CONFIG.set(option, check_btn.get_active())
        CONFIG.save()


class PopupMenu(Gtk.Menu):
    """
    Produce popup widget for right-click menu.
    """
    def __init__(self, row, dbstate, uistate, kind=None, handle=None):
        """
        db:     dbstate.db
        kind:   'Person', 'Family'
        handle: person or family handle
        """
        Gtk.Menu.__init__(self)
        self.set_reserve_toggle_size(False)

        self.row = row
        self.dbstate = dbstate
        self.uistate = uistate
        self.actions = Actions(self.dbstate, self.uistate)

        self.kind = kind
        if kind == 'Person' and handle is not None:
            self.build_person_menu(handle)
        elif kind == 'Tag' and handle is not None:
            self.build_tag_menu(handle)
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
                     [person_handle, self.row.update_person],
                     self.actions.edit_person)
        add_menuitem(self, _('Set as Active person'),
                     [person_handle, self.kind], self.actions.set_active)
        add_menuitem(self, _('Set as Home person'),
                     person_handle, self.actions.edit_person)

    def build_tag_menu(self, tag_handle):
        """
        Generate menu for tag item.
        """
        add_menuitem(self, _('Edit'),
                     [tag_handle, self.row.update_tag_color],
                     self.actions.edit_tag)


class Actions():
    """
    Define actions.
    Parameter "obj" packed by MenuItemWithData().set_data(...),
    and should be unpacked by "obj.get_data()".
    For internal usage ItemWithData class can be used.
    """
    def __init__(self, dbstate, uistate):
        self.dbstate = dbstate
        self.uistate = uistate

    def edit_person(self, obj):
        """
        Start a person editor for the selected person.
        """
        handle, callback = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            EditPerson(self.dbstate, self.uistate, [], person,
                       callback=callback)
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

    def edit_tag(self, obj):
        """
        Start a tag editor for the selected tag.
        """
        handle, callback = obj.get_data()
        tag = self.dbstate.db.get_tag_from_handle(handle)
        color = tag.get_color()
        try:
            EditTag(self.dbstate.db, self.uistate, [], tag)

        except WindowActiveError:
            pass
        if callback is not None and color != tag.get_color():
            callback(tag)

    def set_tag_color(self, color_chooser, tag):
        """
        Change tag color.
        """
        rgba = color_chooser.get_rgba()
        hexval = "#%02x%02x%02x" % (int(rgba.red * 255),
                                    int(rgba.green * 255),
                                    int(rgba.blue * 255))
        tag.set_color(hexval)
        msg = _("Edit Tag (%s)") % tag.get_name()
        with DbTxn(msg, self.dbstate.db) as trans:
            self.dbstate.db.commit_tag(tag, trans)


class ItemWithData(GObject.GObject):
    """
    A Item that stores a data property.
    Based on MenuItemWithData class.
    As set_data in GTK3 is not working, this is a workaround to have set_data.
    """
    data = GObject.Property(type=object)

    def __init__(self):
        GObject.GObject.__init__(self)

    def set_data(self, data):
        self.data = data

    def get_data(self, _=None):
        """
        Obtain the data, for backward compat, we allow a dummy argument.
        """
        return self.data
