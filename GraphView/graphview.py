# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010-2012  Gary Burton
#                          GraphvizSvgParser is based on the Gramps XML import
#                          DotSvgGenerator is based on the relationship graph
#                          report.
#                          Mouse panning is derived from the pedigree view
# Copyright (C) 2012       Mathieu MD
# Copyright (C) 2015-      Serge Noiraud
# Copyright (C) 2016-      Ivan Komaritsyn
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

# $Id$

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import os
import logging
from re import MULTILINE, findall
from xml.parsers.expat import ParserCreate
import string
from subprocess import Popen, PIPE
from io import StringIO
from threading import Thread
from math import sqrt, pow
from html import escape
from collections import abc, deque
import gi
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen import datehandler
from gramps.gen.config import config
from gramps.gen.constfunc import win
from gramps.gen.db import DbTxn
from gramps.gen.display.name import displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.errors import WindowActiveError
from gramps.gen.lib import (Person, Family, ChildRef, Name, Surname,
                            ChildRefType, EventType, EventRoleType)
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.callback import Callback
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 find_children, find_parents, preset_name,
                                 find_witnessed_people)
from gramps.gen.utils.file import search_for, media_path_full, find_file
from gramps.gen.utils.libformatting import FormattingHelper
from gramps.gen.utils.thumbnails import get_thumbnail_path

from gramps.gui.dialog import (OptionDialog, ErrorDialog, QuestionDialog2,
                               WarningDialog)
from gramps.gui.display import display_url
from gramps.gui.editors import EditPerson, EditFamily, EditTagList
from gramps.gui.utils import (color_graph_box, color_graph_family,
                              rgb_to_hex, hex_to_rgb_float,
                              process_pending_events)
from gramps.gui.views.navigationview import NavigationView
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gui.views.tags import OrganizeTagsDialog
from gramps.gui.widgets import progressdialog as progressdlg
from gramps.gui.widgets.menuitem import add_menuitem
from gramps.gen.utils.symbols import Symbols

from gramps.gui.pluginmanager import GuiPluginManager
from gramps.gen.plug import CATEGORY_QR_PERSON, CATEGORY_QR_FAMILY
from gramps.gui.plug.quick import run_report

from gramps.gen.filters import GenericFilterFactory, rules

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

if win():
    DETACHED_PROCESS = 8

for goo_ver in ('3.0', '2.0'):
    try:
        gi.require_version('GooCanvas', goo_ver)
        from gi.repository import GooCanvas
        _GOO = True
        break
    except (ImportError, ValueError):
        _GOO = False
if not _GOO:
    raise Exception("Goocanvas 2 or 3 (http://live.gnome.org/GooCanvas) is "
                    "required for this view to work")

if os.sys.platform == "win32":
    _DOT_FOUND = search_for("dot.exe")
else:
    _DOT_FOUND = search_for("dot")

if not _DOT_FOUND:
    raise Exception("GraphViz (http://www.graphviz.org) is "
                    "required for this view to work")

SPLINE = {0: 'false', 1: 'true', 2: 'ortho'}

WIKI_PAGE = 'https://gramps-project.org/wiki/index.php?title=Graph_View'

# gtk version
gtk_version = float("%s.%s" % (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION))

#-------------------------------------------------------------------------
#
# GraphView modules
#
#-------------------------------------------------------------------------
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from search_widget import SearchWidget, Popover, ListBoxRow, get_person_tooltip
from avatars import Avatars
from drag_n_drop import DragAndDrop


#-------------------------------------------------------------------------
#
# GraphView
#
#-------------------------------------------------------------------------
class GraphView(NavigationView):
    """
    View for pedigree tree.
    Displays the ancestors and descendants of a selected individual.
    """
    # default settings in the config file
    CONFIGSETTINGS = (
        ('interface.graphview-show-images', True),
        ('interface.graphview-show-avatars', True),
        ('interface.graphview-avatars-style', 1),
        ('interface.graphview-avatars-male', ''),       # custom avatar
        ('interface.graphview-avatars-female', ''),     # custom avatar
        ('interface.graphview-show-full-dates', False),
        ('interface.graphview-show-places', False),
        ('interface.graphview-place-format', 0),
        ('interface.graphview-show-lines', 1),
        ('interface.graphview-show-tags', False),
        ('interface.graphview-highlight-home-person', True),
        ('interface.graphview-home-path-color', '#000000'),
        ('interface.graphview-descendant-generations', 10),
        ('interface.graphview-ancestor-generations', 3),
        ('interface.graphview-show-animation', True),
        ('interface.graphview-animation-speed', 3),
        ('interface.graphview-animation-count', 4),
        ('interface.graphview-search-all-db', True),
        ('interface.graphview-search-show-images', True),
        ('interface.graphview-search-marked-first', True),
        ('interface.graphview-ranksep', 5),
        ('interface.graphview-nodesep', 2),
        ('interface.graphview-person-theme', 0),
        ('interface.graphview-scale', 1),
        ('interface.graphview-person-border-size', 1),
        ('interface.graphview-active-person-border-size', 3),
        ('interface.graphview-font', ['', 14]),
        ('interface.graphview-direction', 0),
        ('interface.graphview-show-all-connected', False))

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(self, _('Graph View'), pdata, dbstate, uistate,
                                PersonBookmarks, nav_group)

        self.show_images = self._config.get('interface.graphview-show-images')
        self.show_full_dates = self._config.get(
            'interface.graphview-show-full-dates')
        self.show_places = self._config.get('interface.graphview-show-places')
        self.show_tag_color = self._config.get('interface.graphview-show-tags')
        self.highlight_home_person = self._config.get(
            'interface.graphview-highlight-home-person')
        self.home_path_color = self._config.get(
            'interface.graphview-home-path-color')
        self.descendant_generations = self._config.get(
            'interface.graphview-descendant-generations')
        self.ancestor_generations = self._config.get(
            'interface.graphview-ancestor-generations')

        self.dbstate = dbstate
        self.uistate = uistate
        self.graph_widget = None
        self.dbstate.connect('database-changed', self.change_db)

        # dict {handle, tooltip_str} of tooltips in markup format
        self.tags_tooltips = {}

        # for disable animation options in config dialog
        self.ani_widgets = []
        # for disable custom avatar options in config dialog
        self.avatar_widgets = []

        self.additional_uis.append(self.additional_ui)
        self.define_print_actions()
        self.uistate.connect('font-changed', self.font_changed)

    def on_delete(self):
        """
        Method called on shutdown.
        See PageView class (../gramps/gui/views/pageview.py).
        """
        super().on_delete()
        # stop search to allow close app properly
        self.graph_widget.search_widget.stop_search()

    def font_changed(self):
        self.graph_widget.font_changed(self.get_active())
        #self.goto_handle(None)

    def define_print_actions(self):
        """
        Associate the print button to the PrintView action.
        """
        self._add_action('PrintView', self.printview, "<PRIMARY><SHIFT>P")
        self._add_action('PRIMARY-J', self.jump, '<PRIMARY>J')

    def _connect_db_signals(self):
        """
        Set up callbacks for changes to person and family nodes.
        """
        self.callman.add_db_signal('person-update', self.goto_handle)
        self.callman.add_db_signal('family-update', self.goto_handle)
        self.callman.add_db_signal('event-update', self.goto_handle)

    def change_db(self, _db):
        """
        Set up callback for changes to the database.
        """
        self._change_db(_db)
        self.graph_widget.scale = self._config.get(
            'interface.graphview-scale')

        if self.active:
            if self.get_active() != "":
                self.graph_widget.populate(self.get_active())
                self.graph_widget.set_available(True)
            else:
                self.graph_widget.set_available(False)
        else:
            self.dirty = True
            self.graph_widget.set_available(False)

    def get_stock(self):
        """
        The category stock icon.
        """
        return 'gramps-pedigree'

    def get_viewtype_stock(self):
        """
        Type of view in category.
        """
        return 'gramps-pedigree'

    def build_widget(self):
        """
        Builds the widget with canvas and controls.
        """
        self.graph_widget = GraphWidget(self, self.dbstate, self.uistate)
        return self.graph_widget.get_widget()

    def build_tree(self):
        """
        There is no separate step to fill the widget with data.
        The data is populated as part of canvas widget construction.
        It can be called to rebuild tree.
        """
        if self.active:
            if self.get_active() != "":
                self.graph_widget.populate(self.get_active())

    additional_ui = [  # Defines the UI string for UIManager
        '''
      <placeholder id="CommonGo">
      <section>
        <item>
          <attribute name="action">win.Back</attribute>
          <attribute name="label" translatable="yes">_Back</attribute>
        </item>
        <item>
          <attribute name="action">win.Forward</attribute>
          <attribute name="label" translatable="yes">_Forward</attribute>
        </item>
      </section>
      <section>
        <item>
          <attribute name="action">win.HomePerson</attribute>
          <attribute name="label" translatable="yes">_Home</attribute>
        </item>
      </section>
      </placeholder>
''',
        '''
      <section id='CommonEdit' groups='RW'>
        <item>
          <attribute name="action">win.PrintView</attribute>
          <attribute name="label" translatable="yes">_Print...</attribute>
        </item>
      </section>
''',  # Following are the Toolbar items
        '''
    <placeholder id='CommonNavigation'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-previous</property>
        <property name="action-name">win.Back</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Go to the previous object in the history</property>
        <property name="label" translatable="yes">_Back</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-next</property>
        <property name="action-name">win.Forward</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Go to the next object in the history</property>
        <property name="label" translatable="yes">_Forward</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-home</property>
        <property name="action-name">win.HomePerson</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Go to the default person</property>
        <property name="label" translatable="yes">_Home</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
''',
        '''
    <placeholder id='BarCommonEdit'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">document-print</property>
        <property name="action-name">win.PrintView</property>
        <property name="tooltip_text" translatable="yes">"Save the dot file '''
        '''for a later print.\nThis will save a .gv file and a svg file.\n'''
        '''You must select a .gv file"</property>
        <property name="label" translatable="yes">_Print...</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
''']

    def navigation_type(self):
        """
        The type of forward and backward navigation to perform.
        """
        return 'Person'

    def goto_handle(self, handle):
        """
        Go to a named handle.
        """
        if self.active:
            if self.get_active() != "":
                self.graph_widget.populate(self.get_active())
                self.graph_widget.set_available(True)
        else:
            self.dirty = True
            self.graph_widget.set_available(False)

    def change_active_person(self, _menuitem=None, person_handle=''):
        """
        Change active person.
        """
        if person_handle:
            self.change_active(person_handle)

    def can_configure(self):
        """
        See :class:`~gui.views.pageview.PageView
        :return: bool
        """
        return True

    def cb_update_show_images(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the images setting.
        """
        self.show_images = entry == 'True'
        self.graph_widget.populate(self.get_active())

    def cb_update_show_avatars(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the avatars setting.
        """
        self.show_avatars = entry == 'True'
        self.graph_widget.populate(self.get_active())

    def cb_update_avatars_style(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the avatars setting.
        """
        for widget in self.avatar_widgets:
            widget.set_visible(entry == '0')
        self.graph_widget.populate(self.get_active())

    def cb_on_combo_show(self, combobox):
        """
        Called when the configuration menu show combobox widget for avatars.
        Used to hide custom avatars settings.
        """
        for widget in self.avatar_widgets:
            widget.set_visible(combobox.get_active() == 0)

    def cb_male_avatar_set(self, file_chooser_button):
        """
        Called when the configuration menu changes the male avatar.
        """
        self._config.set('interface.graphview-avatars-male',
                         file_chooser_button.get_filename())
        self.graph_widget.populate(self.get_active())

    def cb_female_avatar_set(self, file_chooser_button):
        """
        Called when the configuration menu changes the female avatar.
        """
        self._config.set('interface.graphview-avatars-female',
                         file_chooser_button.get_filename())
        self.graph_widget.populate(self.get_active())

    def cb_update_show_full_dates(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the date setting.
        """
        self.show_full_dates = entry == 'True'
        self.graph_widget.populate(self.get_active())

    def cb_update_show_places(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the place setting.
        """
        self.show_places = entry == 'True'
        self.graph_widget.populate(self.get_active())

    def cb_update_place_fmt(self, _client, _cnxn_id, _entry, _data):
        """
        Called when the configuration menu changes the place setting.
        """
        self.graph_widget.populate(self.get_active())

    def cb_update_show_tag_color(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the show tags setting.
        """
        self.show_tag_color = entry == 'True'
        self.graph_widget.populate(self.get_active())

    def cb_update_show_lines(self, _client, _cnxn_id, _entry, _data):
        """
        Called when the configuration menu changes the line setting.
        """
        self.graph_widget.populate(self.get_active())

    def cb_update_highlight_home_person(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the highlight home
        person setting.
        """
        self.highlight_home_person = entry == 'True'
        self.graph_widget.populate(self.get_active())

    def cb_update_home_path_color(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the path person color.
        """
        self.home_path_color = entry
        self.graph_widget.populate(self.get_active())

    def cb_update_desc_generations(self, _client, _cnxd_id, entry, _data):
        """
        Called when the configuration menu changes the descendant generation
        count setting.
        """
        self.descendant_generations = entry
        self.graph_widget.populate(self.get_active())

    def cb_update_ancestor_generations(self, _client, _cnxd_id, entry, _data):
        """
        Called when the configuration menu changes the ancestor generation
        count setting.
        """
        self.ancestor_generations = entry
        self.graph_widget.populate(self.get_active())

    def cb_update_show_animation(self, _client, _cnxd_id, entry, _data):
        """
        Called when the configuration menu changes the show animation
        setting.
        """
        if entry == 'True':
            self.graph_widget.animation.show_animation = True
            # enable animate options
            for widget in self.ani_widgets:
                widget.set_sensitive(True)
        else:
            self.graph_widget.animation.show_animation = False
            # diable animate options
            for widget in self.ani_widgets:
                widget.set_sensitive(False)

    def cb_update_animation_count(self, _client, _cnxd_id, entry, _data):
        """
        Called when the configuration menu changes the animation count
        setting.
        """
        self.graph_widget.animation.max_count = int(entry) * 2

    def cb_update_animation_speed(self, _client, _cnxd_id, entry, _data):
        """
        Called when the configuration menu changes the animation speed
        setting.
        """
        self.graph_widget.animation.speed = 50 * int(entry)

    def cb_update_search_all_db(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the search setting.
        """
        value = entry == 'True'
        self.graph_widget.search_widget.set_options(search_all_db=value)

    def cb_update_search_show_images(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the search setting.
        """
        value = entry == 'True'
        self.graph_widget.search_widget.set_options(show_images=value)
        self.graph_widget.show_images_option = value

    def cb_update_search_marked_first(self, _client, _cnxn_id, entry, _data):
        """
        Called when the configuration menu changes the search setting.
        """
        value = entry == 'True'
        self.graph_widget.search_widget.set_options(marked_first=value)

    def cb_update_spacing(self, _client, _cnxd_id, _entry, _data):
        """
        Called when the ranksep or nodesep setting changed.
        """
        self.graph_widget.populate(self.get_active())

    def cb_update_person_theme(self, _client, _cnxd_id, _entry, _data):
        """
        Called when person theme setting changed.
        """
        self.graph_widget.populate(self.get_active())

    def cb_show_all_connected(self, _client, _cnxd_id, _entry, _data):
        """
        Called when show all connected setting changed.
        """
        value = _entry == 'True'
        self.graph_widget.all_connected_btn.set_active(value)
        self.graph_widget.populate(self.get_active())

    def cb_update_active_person_border_size(self, _client, _cnxd_id, entry, _data):
        """
        Called when the active person border size changes
        """
        self.graph_widget.populate(self.get_active())

    def cb_update_person_border_size(self, _client, _cnxd_id, entry, _data):
        """
        Called when the person border size changes
        """
        self.graph_widget.populate(self.get_active())

    def cb_update_direction(self, _client, _cnxn_id, _entry, _data):
        """
        Called when the configuration menu changes the direction setting.
        """
        self.graph_widget.populate(self.get_active())

    def config_change_font(self, font_button):
        """
        Called when font is change.
        """
        font_family = font_button.get_font_family()
        if font_family is not None:
            font_name = font_family.get_name()
        else:
            font_name = ''
        # apply Pango.SCALE=1024 to font size
        font_size = int(font_button.get_font_size() / 1024)
        self._config.set('interface.graphview-font', [font_name, font_size])
        self.graph_widget.retest_font = True
        self.graph_widget.populate(self.get_active())

    def config_connect(self):
        """
        Overwriten from  :class:`~gui.views.pageview.PageView method
        This method will be called after the ini file is initialized,
        use it to monitor changes in the ini file.
        """
        self._config.connect('interface.graphview-show-images',
                             self.cb_update_show_images)
        self._config.connect('interface.graphview-show-avatars',
                             self.cb_update_show_avatars)
        self._config.connect('interface.graphview-avatars-style',
                             self.cb_update_avatars_style)
        self._config.connect('interface.graphview-show-full-dates',
                             self.cb_update_show_full_dates)
        self._config.connect('interface.graphview-show-places',
                             self.cb_update_show_places)
        self._config.connect('interface.graphview-place-format',
                             self.cb_update_place_fmt)
        self._config.connect('interface.graphview-show-tags',
                             self.cb_update_show_tag_color)
        self._config.connect('interface.graphview-show-lines',
                             self.cb_update_show_lines)
        self._config.connect('interface.graphview-highlight-home-person',
                             self.cb_update_highlight_home_person)
        self._config.connect('interface.graphview-home-path-color',
                             self.cb_update_home_path_color)
        self._config.connect('interface.graphview-descendant-generations',
                             self.cb_update_desc_generations)
        self._config.connect('interface.graphview-ancestor-generations',
                             self.cb_update_ancestor_generations)
        self._config.connect('interface.graphview-show-animation',
                             self.cb_update_show_animation)
        self._config.connect('interface.graphview-animation-speed',
                             self.cb_update_animation_speed)
        self._config.connect('interface.graphview-animation-count',
                             self.cb_update_animation_count)
        self._config.connect('interface.graphview-search-all-db',
                             self.cb_update_search_all_db)
        self._config.connect('interface.graphview-search-show-images',
                             self.cb_update_search_show_images)
        self._config.connect('interface.graphview-search-marked-first',
                             self.cb_update_search_marked_first)
        self._config.connect('interface.graphview-ranksep',
                             self.cb_update_spacing)
        self._config.connect('interface.graphview-nodesep',
                             self.cb_update_spacing)
        self._config.connect('interface.graphview-person-theme',
                             self.cb_update_person_theme)
        self._config.connect('interface.graphview-show-all-connected',
                             self.cb_show_all_connected)
        self._config.connect('interface.graphview-active-person-border-size',
                             self.cb_update_active_person_border_size)
        self._config.connect('interface.graphview-person-border-size',
                             self.cb_update_person_border_size)
        self._config.connect('interface.graphview-direction',
                             self.cb_update_direction)

    def _get_configure_page_funcs(self):
        """
        Return a list of functions that create gtk elements to use in the
        notebook pages of the Configure dialog.

        :return: list of functions
        """
        return [self.layout_config_panel,
                self.theme_config_panel,
                self.animation_config_panel,
                self.search_config_panel]

    def layout_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        See "gramps/gui/configure.py" for details.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        row = 0
        configdialog.add_checkbox(
            grid, _('Show images'), row, 'interface.graphview-show-images')
        row += 1
        configdialog.add_checkbox(
            grid, _('Show avatars'), row, 'interface.graphview-show-avatars')
        row += 1
        configdialog.add_checkbox(
            grid, _('Highlight the home person'),
            row, 'interface.graphview-highlight-home-person')
        row += 1
        configdialog.add_checkbox(
            grid, _('Show full dates'),
            row, 'interface.graphview-show-full-dates')
        row += 1
        configdialog.add_checkbox(
            grid, _('Show places'), row, 'interface.graphview-show-places')
        row += 1
        # Place format:
        p_fmts = [(0, _("Default"))]
        for (indx, fmt) in enumerate(place_displayer.get_formats()):
            p_fmts.append((indx + 1, fmt.name))
        active = self._config.get('interface.graphview-place-format')
        if active >= len(p_fmts):
            active = 1
        configdialog.add_combo(grid, _('Place format'), row,
                               'interface.graphview-place-format',
                               p_fmts, setactive=active)
        row += 1
        configdialog.add_checkbox(
            grid, _('Show tags'), row, 'interface.graphview-show-tags')
        row += 1
        direction_fmts = [(0, _("Vertical: Top to Bottom")), (1, _("Vertical: Bottom to Top")), (2, _("Horizontal: Left to Right")), (3, _("Horizontal: Right to Left"))]
        active = self._config.get('interface.graphview-direction')
        configdialog.add_combo(grid, _('Time Direction'), row,
                               'interface.graphview-direction',
                               direction_fmts, setactive=active)

        return _('Layout'), grid

    def theme_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        See "gramps/gui/configure.py" for details.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        p_themes = DotSvgGenerator(self.dbstate, self).get_person_themes()
        themes_list = []
        for t in p_themes:
            themes_list.append((t[0], t[1]))

        row = 0
        configdialog.add_combo(grid, _('Person theme'), row,
                               'interface.graphview-person-theme',
                               themes_list)
        row += 1
        configdialog.add_color(grid,
                               _('Path color to home person'),
                               row, 'interface.graphview-home-path-color',
                               col=1)
        row += 1
        font_lbl = Gtk.Label(label=_('Font:'), xalign=0)
        grid.attach(font_lbl, 1, row, 1, 1)
        font = self._config.get('interface.graphview-font')
        font_str = '%s, %d' % (font[0], font[1])
        font_btn = Gtk.FontButton.new_with_font(font_str)
        font_btn.set_show_style(False)
        grid.attach(font_btn, 2, row, 1, 1)
        font_btn.connect('font-set', self.config_change_font)
        font_btn.set_filter_func(self.font_filter_func)

        # Avatars options
        # ===================================================================
        row += 1
        avatars = Avatars(self._config)
        combo = configdialog.add_combo(grid, _('Avatars style'), row,
                                       'interface.graphview-avatars-style',
                                       avatars.get_styles_list())
        combo.connect('show', self.cb_on_combo_show)

        file_filter = Gtk.FileFilter()
        file_filter.set_name(_('PNG files'))
        file_filter.add_pattern("*.png")

        self.avatar_widgets.clear()
        row += 1
        lbl = Gtk.Label(label=_('Male avatar:'), halign=Gtk.Align.END)
        FCB_male = Gtk.FileChooserButton.new(_('Choose male avatar'),
                                             Gtk.FileChooserAction.OPEN)
        FCB_male.add_filter(file_filter)
        FCB_male.set_filename(
            self._config.get('interface.graphview-avatars-male'))
        FCB_male.connect('file-set', self.cb_male_avatar_set)
        grid.attach(lbl, 1, row, 1, 1)
        grid.attach(FCB_male, 2, row, 1, 1)
        self.avatar_widgets.append(lbl)
        self.avatar_widgets.append(FCB_male)

        row += 1
        lbl = Gtk.Label(label=_('Female avatar:'), halign=Gtk.Align.END)
        FCB_female = Gtk.FileChooserButton.new(_('Choose female avatar'),
                                               Gtk.FileChooserAction.OPEN)
        FCB_female.connect('file-set', self.cb_female_avatar_set)
        FCB_female.add_filter(file_filter)
        FCB_female.set_filename(
            self._config.get('interface.graphview-avatars-female'))
        grid.attach(lbl, 1, row, 1, 1)
        grid.attach(FCB_female, 2, row, 1, 1)
        self.avatar_widgets.append(lbl)
        self.avatar_widgets.append(FCB_female)
        # ===================================================================

        row += 1
        widget = configdialog.add_spinner(
            grid, _('Active person border size'),
            row, 'interface.graphview-active-person-border-size', (1, 20))

        row += 1
        widget = configdialog.add_spinner(
            grid, _('Person border size'),
            row, 'interface.graphview-person-border-size', (1, 20))

        return _('Themes'), grid

    def animation_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        See "gramps/gui/configure.py" for details.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        configdialog.add_checkbox(
            grid, _('Show animation'),
            0, 'interface.graphview-show-animation')
        self.ani_widgets.clear()
        widget = configdialog.add_spinner(
            grid, _('Animation speed (1..5 and 5 is the slower)'),
            1, 'interface.graphview-animation-speed', (1, 5))
        self.ani_widgets.append(widget)
        widget = configdialog.add_spinner(
            grid, _('Animation count (0..8 use 0 to turn off)'),
            2, 'interface.graphview-animation-count', (0, 8))
        self.ani_widgets.append(widget)

        # disable animate options if needed
        if not self.graph_widget.animation.show_animation:
            for widget in self.ani_widgets:
                widget.set_sensitive(False)

        return _('Animation'), grid

    def search_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        See "gramps/gui/configure.py" for details.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        row = 0
        widget = configdialog.add_checkbox(
            grid, _('Search in all database'), row,
            'interface.graphview-search-all-db')
        widget.set_tooltip_text(_("Also apply search by all database."))
        row += 1
        widget = configdialog.add_checkbox(
            grid, _('Show person images'), row,
            'interface.graphview-search-show-images')
        widget.set_tooltip_text(
            _("Show persons thumbnails in search result list."))
        row += 1
        widget = configdialog.add_checkbox(
            grid, _('Show bookmarked first'), row,
            'interface.graphview-search-marked-first')
        widget.set_tooltip_text(
            _("Show bookmarked persons first in search result list."))

        return _('Search'), grid

    def font_filter_func(self, _family, face):
        """
        Filter function to display only regular fonts.
        """
        desc = face.describe()
        stretch = desc.get_stretch()
        if stretch != Pango.Stretch.NORMAL:
            return False  # avoid Condensed or Expanded
        sty = desc.get_style()
        if sty != Pango.Style.NORMAL:
            return False  # avoid italic etc.
        weight = desc.get_weight()
        if weight != Pango.Weight.NORMAL:
            return False  # avoid Bold
        return True

    #-------------------------------------------------------------------------
    #
    # Printing functionalities
    #
    #-------------------------------------------------------------------------
    def printview(self, *obj):
        """
        Save the dot file for a later printing with an appropriate tool.
        """
        # ask for the dot file name
        filter1 = Gtk.FileFilter()
        filter1.set_name("dot files")
        filter1.add_pattern("*.gv")
        dot = Gtk.FileChooserDialog(title=_("Select a dot file name"),
                                    action=Gtk.FileChooserAction.SAVE,
                                    transient_for=self.uistate.window)
        dot.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        dot.add_button(_('_Apply'), Gtk.ResponseType.OK)
        mpath = config.get('paths.report-directory')
        dot.set_current_folder(os.path.dirname(mpath))
        dot.set_filter(filter1)
        dot.set_current_name("Graphview.gv")

        status = dot.run()
        if status == Gtk.ResponseType.OK:
            val = dot.get_filename()
            (spath, _ext) = os.path.splitext(val)
            val = spath + ".gv"  # used to avoid filename without extension
            # selected path is an existing file and we need a file
            if os.path.isfile(val):
                aaa = OptionDialog(_('File already exists'),  # parent-OK
                                   _('You can choose to either overwrite the '
                                     'file, or change the selected filename.'),
                                   _('_Overwrite'), None,
                                   _('_Change filename'), None,
                                   parent=dot)

                if aaa.get_response() == Gtk.ResponseType.YES:
                    dot.destroy()
                    self.printview(obj)
                    return
            svg = val.replace('.gv', '.svg')
            # both dot_data and svg_data are bytes, already utf-8 encoded
            # just write them as binary
            try:
                with open(val, 'wb') as __g, open(svg, 'wb') as __s:
                    __g.write(self.graph_widget.dot_data)
                    __s.write(self.graph_widget.svg_data)
            except IOError as msg:
                msg2 = _("Could not create %s") % (val + ', ' + svg)
                ErrorDialog(msg2, str(msg), parent=dot)
        dot.destroy()


#-------------------------------------------------------------------------
#
# GraphWidget
#
#-------------------------------------------------------------------------
class GraphWidget(object):
    """
    Define the widget with controls and canvas that displays the graph.
    """
    def __init__(self, view, dbstate, uistate):
        """
        :type view: GraphView
        """
        # variables for drag and scroll
        self._last_x = 0
        self._last_y = 0
        self._in_move = False
        self.view = view
        self.dbstate = dbstate
        self.uistate = uistate
        self.parser = None
        self.active_person_handle = None

        self.actions = Actions(dbstate, uistate, self.view.bookmarks)
        self.actions.connect('rebuild-graph', self.view.build_tree)
        self.actions.connect('active-changed', self.populate)
        self.actions.connect('focus-person-changed', self.set_person_to_focus)
        self.actions.connect('path-to-home-person', self.populate)

        self.dot_data = None
        self.svg_data = None

        scrolled_win = Gtk.ScrolledWindow()
        scrolled_win.set_shadow_type(Gtk.ShadowType.IN)
        self.hadjustment = scrolled_win.get_hadjustment()
        self.vadjustment = scrolled_win.get_vadjustment()

        self.canvas = GooCanvas.Canvas()
        self.canvas.connect("scroll-event", self.scroll_mouse)
        self.canvas.props.units = Gtk.Unit.POINTS
        self.canvas.props.resolution_x = 72
        self.canvas.props.resolution_y = 72

        scrolled_win.add(self.canvas)

        self.vbox = Gtk.Box(homogeneous=False, spacing=4,
                            orientation=Gtk.Orientation.VERTICAL)
        self.vbox.set_border_width(4)
        self.toolbar = Gtk.Box(homogeneous=False, spacing=4,
                               orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox.pack_start(self.toolbar, False, False, 0)

        # add zoom-in button
        self.zoom_in_btn = Gtk.Button.new_from_icon_name('zoom-in',
                                                         Gtk.IconSize.MENU)
        self.zoom_in_btn.set_tooltip_text(_('Zoom in'))
        self.toolbar.pack_start(self.zoom_in_btn, False, False, 1)
        self.zoom_in_btn.connect("clicked", self.zoom_in)

        # add zoom-out button
        self.zoom_out_btn = Gtk.Button.new_from_icon_name('zoom-out',
                                                          Gtk.IconSize.MENU)
        self.zoom_out_btn.set_tooltip_text(_('Zoom out'))
        self.toolbar.pack_start(self.zoom_out_btn, False, False, 1)
        self.zoom_out_btn.connect("clicked", self.zoom_out)

        # add original zoom button
        self.orig_zoom_btn = Gtk.Button.new_from_icon_name('zoom-original',
                                                           Gtk.IconSize.MENU)
        self.orig_zoom_btn.set_tooltip_text(_('Zoom to original'))
        self.toolbar.pack_start(self.orig_zoom_btn, False, False, 1)
        self.orig_zoom_btn.connect("clicked", self.set_original_zoom)

        # add best fit button
        self.fit_btn = Gtk.Button.new_from_icon_name('zoom-fit-best',
                                                     Gtk.IconSize.MENU)
        self.fit_btn.set_tooltip_text(_('Zoom to best fit'))
        self.toolbar.pack_start(self.fit_btn, False, False, 1)
        self.fit_btn.connect("clicked", self.fit_to_page)

        # add 'go to active person' button
        self.goto_active_btn = Gtk.Button.new_from_icon_name('go-jump',
                                                             Gtk.IconSize.MENU)
        self.goto_active_btn.set_tooltip_text(_('Go to active person'))
        self.toolbar.pack_start(self.goto_active_btn, False, False, 1)
        self.goto_active_btn.connect("clicked", self.goto_active)

        # add 'go to bookmark' button
        self.goto_other_btn = Gtk.Button(label=_('Go to bookmark'))
        self.goto_other_btn.set_tooltip_text(
            _('Center view on selected bookmark'))
        self.toolbar.pack_start(self.goto_other_btn, False, False, 1)
        self.bkmark_popover = Popover(_('Bookmarks for current graph'),
                                      _('Other Bookmarks'),
                                      ext_panel=self.build_bkmark_ext_panel())
        self.bkmark_popover.set_relative_to(self.goto_other_btn)
        self.goto_other_btn.connect("clicked", self.show_bkmark_popup)
        self.goto_other_btn.connect("key-press-event",
                                    self.goto_other_btn_key_press_event)
        self.bkmark_popover.connect('item-activated', self.activate_popover)
        self.show_images_option = self.view._config.get(
            'interface.graphview-search-show-images')

        # add search widget
        self.search_widget = SearchWidget(self.dbstate,
                                          self.get_person_image,
                                          bookmarks=self.view.bookmarks)
        search_box = self.search_widget.get_widget()
        self.toolbar.pack_start(search_box, True, True, 1)
        self.search_widget.set_options(
            search_all_db=self.view._config.get(
                'interface.graphview-search-all-db'),
            show_images=self.show_images_option)
        self.search_widget.connect('item-activated', self.activate_popover)
        # add accelerator to focus search entry
        accel_group = Gtk.AccelGroup()
        self.uistate.window.add_accel_group(accel_group)
        search_box.add_accelerator('grab-focus', accel_group, Gdk.KEY_f,
                                   Gdk.ModifierType.CONTROL_MASK,
                                   Gtk.AccelFlags.VISIBLE)

        # add spinners for quick generations change
        gen_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box = self.build_spinner('go-up-symbolic', 0, 50,
                                 _('Ancestor generations'),
                                 'interface.graphview-ancestor-generations')
        gen_box.add(box)
        box = self.build_spinner('go-down-symbolic', 0, 50,
                                 _('Descendant generations'),
                                 'interface.graphview-descendant-generations')
        gen_box.add(box)
        # pack generation spinners to popover
        gen_btn = Gtk.Button(label=_('Generations'))
        self.add_popover(gen_btn, gen_box)
        self.toolbar.pack_start(gen_btn, False, False, 1)

        # add spiner for generation (vertical) spacing
        spacing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box = self.build_spinner('object-flip-vertical', 1, 50,
                                 _('Vertical spacing between generations'),
                                 'interface.graphview-ranksep')
        spacing_box.add(box)
        # add spiner for node (horizontal) spacing
        box = self.build_spinner('object-flip-horizontal', 1, 50,
                                 _('Horizontal spacing between generations'),
                                 'interface.graphview-nodesep')
        spacing_box.add(box)
        # pack spacing spinners to popover
        spacing_btn = Gtk.Button(label=_('Spacings'))
        self.add_popover(spacing_btn, spacing_box)
        self.toolbar.pack_start(spacing_btn, False, False, 1)

        # add button to show all connected persons
        self.all_connected_btn = Gtk.ToggleButton(label=_('All connected'))
        self.all_connected_btn.set_tooltip_text(
            _("Show all connected persons limited by generation restrictions.\n"
              "Works slow, so don't set large generation values."))
        self.all_connected_btn.set_active(
            self.view._config.get('interface.graphview-show-all-connected'))
        self.all_connected_btn.connect('clicked', self.toggle_all_connected)
        self.toolbar.pack_start(self.all_connected_btn, False, False, 1)

        self.vbox.pack_start(scrolled_win, True, True, 0)

        # if we have graph lager than graphviz paper size
        # this coef is needed
        self.transform_scale = 1
        self.scale = self.view._config.get('interface.graphview-scale')

        self.animation = CanvasAnimation(self.view, self.canvas, scrolled_win)
        self.search_widget.set_items_list(self.animation.items_list)

        # person that will focus (once) after graph rebuilding
        self.person_to_focus = None

        # for detecting double click
        self.click_events = []
        self.double_click = False

        # for timeout on changing settings by spinners
        self.timeout_event = False

        # Gtk style context for scrollwindow to operate with theme colors
        self.sw_style_context = scrolled_win.get_style_context()

        # used for popup menu, prevent destroy menu as local variable
        self.menu = None
        self.retest_font = True     # flag indicates need to resize font
        self.bold_size = self.norm_size = 0  # font sizes to send to dot

        # setup drag and drop
        self.canvas.connect("drag-begin", self.del_click_events)
        self.dnd = DragAndDrop(self.canvas, self.dbstate, self.uistate,
                               self.hadjustment, self.vadjustment)

    def add_popover(self, widget, container):
        """
        Add popover for button.
        """
        popover = Gtk.Popover()
        popover.set_relative_to(widget)
        popover.add(container)
        widget.connect("clicked", self.spinners_popup, popover)
        container.show_all()

    def build_spinner(self, icon, start, end, tooltip, conf_const):
        """
        Build spinner with icon and pack it into box.
        Changes apply to config with delay.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        box.pack_start(img, False, False, 1)
        spinner = Gtk.SpinButton.new_with_range(start, end, 1)
        spinner.set_tooltip_text(tooltip)
        spinner.set_value(self.view._config.get(conf_const))
        spinner.connect("value-changed", self.apply_spinner_delayed,
                        conf_const)
        box.pack_start(spinner, False, False, 1)
        return box

    def toggle_all_connected(self, widget):
        """
        Change state for "Show all connected" setting.
        """
        self.view._config.set('interface.graphview-show-all-connected',
                              widget.get_active())

    def spinners_popup(self, _widget, popover):
        """
        Popover for generations and spacing params.
        Different popup depending on gtk version.
        """
        if gtk_version >= 3.22:
            popover.popup()
        else:
            popover.show()

    def set_available(self, state):
        """
        Set state for GraphView.
        """
        if not state:
            # if no database is opened
            self.clear()
        self.toolbar.set_sensitive(state)

    def font_changed(self, active):
        self.sym_font = config.get('utf8.selected-font')
        if self.parser:
            self.parser.font_changed()
            self.populate(active)

    def set_person_to_focus(self, handle):
        """
        Set person that will focus (once) after graph rebuilding.
        """
        self.person_to_focus = handle

    def goto_other_btn_key_press_event(self, _widget, event):
        """
        Handle 'Esc' key on bookmarks button to hide popup.
        """
        key = event.keyval
        if event.keyval == Gdk.KEY_Escape:
            self.hide_bkmark_popover()
        elif key == Gdk.KEY_Down:
            self.bkmark_popover.grab_focus()
            return True

    def activate_popover(self, _widget, person_handle):
        """
        Called when some item(person)
        in search or bookmarks popup(popover) is activated.
        """
        self.hide_bkmark_popover()
        self.search_widget.hide_search_popover()
        # move view to person with animation
        self.move_to_person(None, person_handle, True)

    def apply_spinner_delayed(self, widget, conf_const):
        """
        Set params by spinners (generations, spacing).
        Use timeout for better interface responsiveness.
        """
        value = int(widget.get_value())
        # try to remove planed event (changing setting)
        if self.timeout_event and \
                not self.timeout_event.is_destroyed():
            GLib.source_remove(self.timeout_event.get_id())
        # timeout saving setting for better interface responsiveness
        event_id = GLib.timeout_add(300, self.view._config.set,
                                    conf_const, value)
        context = GLib.main_context_default()
        self.timeout_event = context.find_source_by_id(event_id)

    def build_bkmark_ext_panel(self):
        """
        Build bookmark popover extand panel.
        """
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # add button to add active person to bookmarks
        # tooltip will be changed in "self.load_bookmarks"
        self.add_bkmark = Gtk.Button(label=_('Add active person'))
        self.add_bkmark.connect("clicked", self.add_active_to_bkmarks)
        btn_box.pack_start(self.add_bkmark, True, True, 2)
        # add buton to call bookmarks manager
        manage_bkmarks = Gtk.Button(label=_('Edit'))
        manage_bkmarks.set_tooltip_text(_('Call the bookmark editor'))
        manage_bkmarks.connect("clicked", self.edit_bookmarks)
        btn_box.pack_start(manage_bkmarks, True, True, 2)
        return btn_box

    def load_bookmarks(self):
        """
        Load bookmarks in Popover (goto_other_btn).
        """
        # remove all old items from popup
        self.bkmark_popover.clear_items()

        active = self.view.get_active()
        active_in_bkmarks = False
        found = False
        found_other = False
        count = 0
        count_other = 0

        bookmarks = self.view.bookmarks.get_bookmarks().bookmarks
        for bkmark in bookmarks:
            if active == bkmark:
                active_in_bkmarks = True
            person = self.dbstate.db.get_person_from_handle(bkmark)
            if person:
                name = displayer.display_name(person.get_primary_name())
                present = self.animation.get_item_by_title(bkmark)

                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                               spacing=10)
                # add person ID
                label = Gtk.Label("[%s]" % person.gramps_id, xalign=0)
                hbox.pack_start(label, False, False, 2)
                # add person name
                label = Gtk.Label(name, xalign=0)
                hbox.pack_start(label, True, True, 2)
                # add person image if needed
                if self.show_images_option:
                    person_image = self.get_person_image(person, 32, 32)
                    if person_image:
                        hbox.pack_start(person_image, False, True, 2)
                row = ListBoxRow(person_handle=bkmark, label=name,
                                 db=self.dbstate.db)
                row.add(hbox)

                if present is not None:
                    found = True
                    count += 1
                    self.bkmark_popover.main_panel.add_to_panel(row)
                else:
                    found_other = True
                    count_other += 1
                    self.bkmark_popover.other_panel.add_to_panel(row)
                row.show_all()
        if not found and not found_other:
            self.bkmark_popover.show_other_panel(False)
            row = ListBoxRow()
            row.add(Gtk.Label(_("You don't have any bookmarks yet...\n"
                                "Try to add some frequently used persons "
                                "to speedup navigation.")))
            self.bkmark_popover.main_panel.add_to_panel(row)
            row.show_all()
        else:
            if not found:
                row = ListBoxRow()
                row.add(Gtk.Label(_('No bookmarks for this graph...')))
                self.bkmark_popover.main_panel.add_to_panel(row)
                row.show_all()
            if not found_other:
                row = ListBoxRow()
                row.add(Gtk.Label(_('No other bookmarks...')))
                self.bkmark_popover.other_panel.add_to_panel(row)
                row.show_all()
                self.bkmark_popover.show_other_panel(True)

        self.bkmark_popover.main_panel.set_progress(0, _('found: %s') % count)
        self.bkmark_popover.other_panel.set_progress(
            0, _('found: %s') % count_other)

        # set tooltip for "add_bkmark" button
        self.add_bkmark.hide()
        if active and not active_in_bkmarks:
            person = self.dbstate.db.get_person_from_handle(active)
            if person:
                name = displayer.display_name(person.get_primary_name())
                val_to_display = "[%s] %s" % (person.gramps_id, name)
                self.add_bkmark.set_tooltip_text(
                    _('Add active person to bookmarks\n'
                      '%s') % val_to_display)
                self.add_bkmark.show()

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

    def add_active_to_bkmarks(self, _widget):
        """
        Add active person to bookmarks.
        """
        self.view.add_bookmark(None)
        self.load_bookmarks()

    def edit_bookmarks(self, _widget):
        """
        Call the bookmark editor.
        """
        self.view.edit_bookmarks(None)
        self.load_bookmarks()

    def show_bkmark_popup(self, _widget):
        """
        Show bookmark popup.
        """
        self.load_bookmarks()
        self.bkmark_popover.popup()

    def hide_bkmark_popover(self, _widget=None, _event=None):
        """
        Hide bookmark popup.
        """
        self.bkmark_popover.popdown()

    def goto_active(self, button=None):
        """
        Go to active person.
        """
        # check if animation is needed
        animation = bool(button)
        self.animation.move_to_person(self.active_person_handle, animation)

    def move_to_person(self, _menuitem, handle, animate=False):
        """
        Move to specified person (by handle).
        If person not present in the current graphview tree,
        show dialog to change active person.
        """
        self.person_to_focus = None
        if self.animation.get_item_by_title(handle):
            self.animation.move_to_person(handle, animate)
        else:
            person = self.dbstate.db.get_person_from_handle(handle)
            if not person:
                return False
            quest = (_('Person <b><i>%s</i></b> is not in the current view.\n'
                       'Do you want to set it active and rebuild view?')
                     % escape(displayer.display(person)))
            dialog = QuestionDialog2(_("Change active person?"), quest,
                                     _("Yes"), _("No"),
                                     self.uistate.window)
            if dialog.run():
                self.view.change_active(handle)

    def scroll_mouse(self, _canvas, event):
        """
        Zoom by mouse wheel.
        """
        if event.direction == Gdk.ScrollDirection.UP:
            self.zoom_in()
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.zoom_out()

        # stop the signal of scroll emission
        # to prevent window scrolling
        return True

    def populate(self, active_person, path_to_home_person=False):
        """
        Populate the graph with widgets derived from Graphviz.
        """
        self.dnd.enable_dnd(False)
        # set the busy cursor, so the user knows that we are working
        self.uistate.set_busy_cursor(True)
        if self.uistate.window.get_window().is_visible():
            process_pending_events()

        self.clear()
        self.active_person_handle = active_person

        # fit the text to boxes
        self.bold_size, self.norm_size = self.fit_text()

        self.search_widget.hide_search_popover()
        self.hide_bkmark_popover()

        # generate DOT and SVG data
        dot = DotSvgGenerator(self.dbstate, self.view,
                              bold_size=self.bold_size,
                              norm_size=self.norm_size)

        graph_data = dot.build_graph(active_person, path_to_home_person)
        del dot

        if not graph_data:
            # something go wrong when build all-connected tree
            # so turn off this feature
            self.view._config.set('interface.graphview-show-all-connected',
                                  False)
            return

        self.dot_data = graph_data[0]
        self.svg_data = graph_data[1]

        parser = GraphvizSvgParser(self, self.view)
        parser.parse(self.svg_data)

        self.animation.update_items(parser.items_list)

        # save transform scale
        self.transform_scale = parser.transform_scale
        self.set_zoom(self.scale)

        # focus on edited person if posible
        if not self.animation.move_to_person(self.person_to_focus, False):
            self.goto_active()
        self.person_to_focus = None

        # update the status bar
        self.view.change_page()

        self.uistate.set_busy_cursor(False)

    def zoom_in(self, _button=None):
        """
        Increase zoom scale.
        """
        scale_coef = self.scale * 1.1
        self.set_zoom(scale_coef)

    def zoom_out(self, _button=None):
        """
        Decrease zoom scale.
        """
        scale_coef = self.scale * 0.9
        if scale_coef < 0.01:
            scale_coef = 0.01
        self.set_zoom(scale_coef)

    def set_original_zoom(self, _button):
        """
        Set original zoom scale = 1.
        """
        self.set_zoom(1)

    def fit_to_page(self, _button):
        """
        Calculate scale and fit tree to page.
        """
        # get the canvas size
        bounds = self.canvas.get_root_item().get_bounds()
        height_canvas = bounds.y2 - bounds.y1
        width_canvas = bounds.x2 - bounds.x1

        # get scroll window size
        width = self.hadjustment.get_page_size()
        height = self.vadjustment.get_page_size()

        # prevent division by zero
        if height_canvas == 0:
            height_canvas = 1
        if width_canvas == 0:
            width_canvas = 1

        # calculate minimum scale
        scale_h = (height / height_canvas)
        scale_w = (width / width_canvas)
        if scale_h > scale_w:
            scale = scale_w
        else:
            scale = scale_h

        scale = scale * self.transform_scale

        # set scale if it needed, else restore it to default
        if scale < 1:
            self.set_zoom(scale)
        else:
            self.set_zoom(1)

    def clear(self):
        """
        Clear the graph by creating a new root item.
        """
        # remove root item (with all children)
        self.canvas.get_root_item().remove()
        self.canvas.set_root_item(GooCanvas.CanvasGroup())

    def get_widget(self):
        """
        Return the graph display widget that includes the drawing canvas.
        """
        return self.vbox

    def button_press(self, item, _target, event):
        """
        Enter in scroll mode when left or middle mouse button pressed
        on background.
        """
        self.search_widget.hide_search_popover()
        self.hide_bkmark_popover()

        if not (event.type == getattr(Gdk.EventType, "BUTTON_PRESS") and
                item == self.canvas.get_root_item()):
            return False

        button = event.get_button()[1]
        if button in (1, 2):
            self.dnd.enable_dnd(False)
            window = self.canvas.get_parent().get_window()
            window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.FLEUR))
            self._last_x = event.x_root
            self._last_y = event.y_root
            self._in_move = True
            self.animation.stop_animation()
            return False

        if button == 3:
            self.menu = PopupMenu(self, kind='background')
            self.menu.show_menu(event)
            return True

        return False

    def button_release(self, item, target, event):
        """
        Exit from scroll mode when button release.
        """
        button = event.get_button()[1]
        if((button == 1 or button == 2) and
           event.type == getattr(Gdk.EventType, "BUTTON_RELEASE")):

            self.motion_notify_event(item, target, event)
            self.canvas.get_parent().get_window().set_cursor(None)
            self._in_move = False
            return True
        return False

    def motion_notify_event(self, _item, _target, event):
        """
        Function for motion notify events for drag and scroll mode.
        """
        if self._in_move and (event.type == Gdk.EventType.MOTION_NOTIFY or
                              event.type == Gdk.EventType.BUTTON_RELEASE):

            # scale coefficient for prevent flicking when drag
            scale_coef = self.canvas.get_scale()

            new_x = (self.hadjustment.get_value() -
                     (event.x_root - self._last_x) * scale_coef)
            self.hadjustment.set_value(new_x)

            new_y = (self.vadjustment.get_value() -
                     (event.y_root - self._last_y) * scale_coef)
            self.vadjustment.set_value(new_y)
            return True
        self.dnd.enable_dnd(True)
        return False

    def set_zoom(self, value):
        """
        Set value for zoom of the canvas widget and apply it.
        """
        self.scale = value
        self.view._config.set('interface.graphview-scale', value)
        self.canvas.set_scale(value / self.transform_scale)

    def del_click_events(self, *args):
        """
        Remove all single click events.
        """
        for click_item in self.click_events:
            if not click_item.is_destroyed():
                GLib.source_remove(click_item.get_id())
        self.click_events.clear()

    def press_node(self, item, target, event):
        """
        Perform actions when a node is clicked (button press).
        If middle mouse was pressed then try to set scroll mode.
        """
        self.search_widget.hide_search_popover()
        self.hide_bkmark_popover()

        handle = item.title
        node_class = item.description
        button = event.get_button()[1]

        self.person_to_focus = None

        # perform double click on node by left mouse button
        if event.type == getattr(Gdk.EventType, "DOUBLE_BUTTON_PRESS"):
            self.del_click_events()
            if button == 1 and node_class == 'node':
                GLib.idle_add(self.actions.edit_person, None, handle)
            elif button == 1 and node_class == 'familynode':
                GLib.idle_add(self.actions.edit_family, None, handle)
            self.double_click = True
            return True

        if event.type != getattr(Gdk.EventType, "BUTTON_PRESS"):
            return False

        # set targets for drag-n-drop (object type and handle)
        if button == 1 and node_class in ('node', 'familynode'):
            self.dnd.set_target(node_class, handle)

        elif button == 3 and node_class:                    # right mouse
            if node_class == 'node':
                self.menu = PopupMenu(self, 'person', handle)
                self.menu.show_menu(event)
            elif node_class == 'familynode':
                self.menu = PopupMenu(self, 'family', handle)
                self.menu.show_menu(event)

        elif button == 2:                                   # middle mouse
            # to enter in scroll mode (we should change "item" to root item)
            item = self.canvas.get_root_item()
            self.button_press(item, target, event)

        return True

    def release_node(self, item, target, event):
        """
        Perform actions when a node is clicked (button release).
        Set timer to handle single click at node and wait double click.
        """
        # don't handle single click if had double click before
        # because we came here after DOUBLE_BUTTON_PRESS event
        if self.double_click:
            self.double_click = False
            return True

        handle = item.title
        node_class = item.description
        button = event.get_button()[1]

        if button == 1 and node_class == 'node':            # left mouse
            if handle == self.active_person_handle:
                # Find a parent of the active person so that they can become
                # the active person, if no parents then leave as the current
                # active person
                parent_handle = self.find_a_parent(handle)
                if parent_handle:
                    handle = parent_handle
                else:
                    return True

            # redraw the graph based on the selected person
            # schedule after because double click can occur
            click_event_id = GLib.timeout_add(200, self.view.change_active,
                                              handle)
            # add single click events to list, it will be removed if necessary
            context = GLib.main_context_default()
            self.click_events.append(context.find_source_by_id(click_event_id))

    def find_a_parent(self, handle):
        """
        Locate a parent from the first family that the selected person is a
        child of. Try and find the father first, then the mother.
        Either will be OK.
        """
        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            fam_handle = person.get_parent_family_handle_list()[0]
            if fam_handle:
                family = self.dbstate.db.get_family_from_handle(fam_handle)
                if family and family.get_father_handle():
                    handle = family.get_father_handle()
                elif family and family.get_mother_handle():
                    handle = family.get_mother_handle()
        except IndexError:
            handle = None

        return handle

    def update_lines_type(self, _menu_item, lines_type, constant):
        """
        Save the lines type setting.
        """
        self.view._config.set(constant, lines_type)

    def update_setting(self, menu_item, constant):
        """
        Save changed setting.
        menu_item should be Gtk.CheckMenuItem.
        """
        self.view._config.set(constant, menu_item.get_active())

    def fit_text(self):
        """
        Fit the text to the boxes more exactly.  Works by trying some sample
        text, measuring the results, and trying an increasing size of font
        sizes to some sample nodes to see which one will fit the expected
        text size.
        In other words we are telling dot to use different font sizes than
        we are actually displaying, since dot doesn't do a good job of
        determining the text size.
        """
        if not self.retest_font:  # skip this uless font changed.
            return self.bold_size, self.norm_size

        text = "The quick Brown Fox jumped over the Lazy Dogs 1948-01-01."
        dot_test = DotSvgGenerator(self.dbstate, self.view)
        dot_test.init_dot()
        # These are at the desired font sizes.
        dot_test.add_node('test_bold', '<B>%s</B>' % text, shape='box')
        dot_test.add_node('test_norm', text, shape='box')
        # now add nodes at increasing font sizes
        for scale in range(35, 140, 2):
            f_size = dot_test.fontsize * scale / 100.0
            dot_test.add_node(
                'test_bold' + str(scale),
                '<FONT POINT-SIZE="%(bsize)3.1f"><B>%(text)s</B></FONT>' %
                {'text': text, 'bsize': f_size}, shape='box')
            dot_test.add_node(
                'test_norm' + str(scale),
                text, shape='box', fontsize=("%3.1f" % f_size))

        # close the graphviz dot code with a brace
        dot_test.write('}\n')

        # get DOT and generate SVG data by Graphviz
        dot_data = dot_test.dot.getvalue().encode('utf8')
        svg_data = dot_test.make_svg(dot_data)
        svg_data = svg_data.decode('utf8')

        # now lest find the box sizes, and font sizes for the generated svg.
        points_a = findall(r'points="(.*)"', svg_data, MULTILINE)
        font_fams = findall(r'font-family="(.*)" font-weight',
                            svg_data, MULTILINE)
        font_sizes = findall(r'font-size="(.*)" fill', svg_data, MULTILINE)
        box_w = []
        for points in points_a:
            box_pts = points.split()
            x_1 = box_pts[0].split(',')[0]
            x_2 = box_pts[1].split(',')[0]
            box_w.append(float(x_1) - float(x_2) - 16)  # adjust for margins

        text_font = font_fams[0] + ", " + font_sizes[0] + 'px'
        font_desc = Pango.FontDescription.from_string(text_font)

        # lets measure the bold text on our canvas at desired font size
        c_text = GooCanvas.CanvasText(parent=self.canvas.get_root_item(),
                                      text='<b>' + text + '</b>',
                                      x=100,
                                      y=100,
                                      anchor=GooCanvas.CanvasAnchorType.WEST,
                                      use_markup=True,
                                      font_desc=font_desc)
        bold_b = c_text.get_bounds()
        # and measure the normal text on our canvas at desired font size
        c_text.props.text = text
        norm_b = c_text.get_bounds()
        # now scan throught test boxes, finding the smallest that will hold
        # the actual text as measured.  And record the dot font that was used.
        for indx in range(3, len(font_sizes), 2):
            bold_size = float(font_sizes[indx - 1])
            if box_w[indx] > bold_b.x2 - bold_b.x1:
                break
        for indx in range(4, len(font_sizes), 2):
            norm_size = float(font_sizes[indx - 1])
            if box_w[indx] > norm_b.x2 - norm_b.x1:
                break
        self.retest_font = False  # we don't do this again until font changes
        # return the adjusted font size to tell dot to use.
        return bold_size, norm_size


#-------------------------------------------------------------------------
#
# GraphvizSvgParser
#
#-------------------------------------------------------------------------
class GraphvizSvgParser(object):
    """
    Parses SVG produces by Graphviz and adds the elements to a GooCanvas.
    """

    def __init__(self, widget, view):
        """
        Initialise the GraphvizSvgParser class.
        """
        self.func = None
        self.widget = widget
        self.canvas = widget.canvas
        self.view = view
        self.highlight_home_person = self.view._config.get(
            'interface.graphview-highlight-home-person')
        scheme = config.get('colors.scheme')
        self.home_person_color = config.get('colors.home-person')[scheme]
        self.font_size = self.view._config.get('interface.graphview-font')[1]
        self.active_person_border_size = self.view._config.get(
            'interface.graphview-active-person-border-size')
        self.person_border_size = self.view._config.get(
            'interface.graphview-person-border-size')

        self.tlist = []
        self.text_attrs = None
        self.func_list = []
        self.handle = None
        self.func_map = {"g":       (self.start_g, self.stop_g),
                         "svg":     (self.start_svg, self.stop_svg),
                         "polygon": (self.start_polygon, self.stop_polygon),
                         "path":    (self.start_path, self.stop_path),
                         "image":   (self.start_image, self.stop_image),
                         "text":    (self.start_text, self.stop_text),
                         "ellipse": (self.start_ellipse, self.stop_ellipse),
                         "title":   (self.start_title, self.stop_title)}
        self.text_anchor_map = {"start":  GooCanvas.CanvasAnchorType.WEST,
                                "middle": GooCanvas.CanvasAnchorType.CENTER,
                                "end":    GooCanvas.CanvasAnchorType.EAST}
        # This list is used as a LIFO stack so that the SAX parser knows
        # which Goocanvas object to link the next object to.
        self.item_hier = []

        # list of persons items, used for animation class
        self.items_list = []

        self.transform_scale = 1

    def parse(self, ifile):
        """
        Parse an SVG file produced by Graphviz.
        """
        self.item_hier.append(self.canvas.get_root_item())
        parser = ParserCreate()
        parser.StartElementHandler = self.start_element
        parser.EndElementHandler = self.end_element
        parser.CharacterDataHandler = self.characters
        parser.Parse(ifile)

        for key in list(self.func_map.keys()):
            del self.func_map[key]
        del self.func_map
        del self.func_list
        del parser

    def start_g(self, attrs):
        """
        Parse <g> tags.
        """
        # The class attribute defines the group type. There should be one
        # graph type <g> tag which defines the transform for the whole graph.
        if attrs.get('class') == 'graph':
            self.items_list.clear()
            transform = attrs.get('transform')
            item = self.canvas.get_root_item()
            transform_list = transform.split(') ')
            scale = transform_list[0].split()
            scale_x = float(scale[0].lstrip('scale('))
            scale_y = float(scale[1])
            self.transform_scale = scale_x
            if scale_x > scale_y:
                self.transform_scale = scale_y
            # scale should be (0..1)
            # fix graphviz issue from version > 2.40.1
            if self.transform_scale > 1:
                self.transform_scale = 1 / self.transform_scale

            item.set_simple_transform(self.bounds[1],
                                      self.bounds[3],
                                      self.transform_scale,
                                      0)
            item.connect("button-press-event", self.widget.button_press)
            item.connect("button-release-event", self.widget.button_release)
            item.connect("motion-notify-event",
                         self.widget.motion_notify_event)
        else:
            item = GooCanvas.CanvasGroup(parent=self.current_parent())
            item.connect("button-press-event", self.widget.press_node)
            item.connect("button-release-event", self.widget.release_node)
            self.items_list.append(item)

        item.description = attrs.get('class')
        self.item_hier.append(item)

    def stop_g(self, _tag):
        """
        Parse </g> tags.
        """
        item = self.item_hier.pop()
        item.title = self.handle

    def start_svg(self, attrs):
        """
        Parse <svg> tags.
        """
        GooCanvas.CanvasGroup(parent=self.current_parent())

        view_box = attrs.get('viewBox').split()
        v_left = float(view_box[0])
        v_top = float(view_box[1])
        v_right = float(view_box[2])
        v_bottom = float(view_box[3])
        self.canvas.set_bounds(v_left, v_top, v_right, v_bottom)
        self.bounds = (v_left, v_top, v_right, v_bottom)

    def stop_svg(self, tag):
        """
        Parse </svg> tags.
        """
        pass

    def start_title(self, attrs):
        """
        Parse <title> tags.
        """
        pass

    def stop_title(self, tag):
        """
        Parse </title> tags.
        Stripping off underscore prefix added to fool Graphviz.
        """
        self.handle = tag.lstrip("_")

    def start_polygon(self, attrs):
        """
        Parse <polygon> tags.
        Polygons define the boxes around individuals on the graph.
        """
        coord_string = attrs.get('points')
        coord_count = 5
        points = GooCanvas.CanvasPoints.new(coord_count)
        nnn = 0
        for i in coord_string.split():
            coord = i.split(",")
            coord_x = float(coord[0])
            coord_y = float(coord[1])
            points.set_point(nnn, coord_x, coord_y)
            nnn += 1
        style = attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            stroke_color = p_style['stroke']
            fill_color = p_style['fill']
        else:
            stroke_color = attrs.get('stroke')
            fill_color = attrs.get('fill')

        if self.handle == self.widget.active_person_handle:
            line_width = self.active_person_border_size
        else:
            line_width = self.person_border_size

        tooltip = self.view.tags_tooltips.get(self.handle)

        # highlight the home person
        # stroke_color is not '#...' when tags are drawing, so we check this
        # maybe this is not good solution to check for tags but it works
        if self.highlight_home_person and stroke_color[:1] == '#':
            home_person = self.widget.dbstate.db.get_default_person()
            if home_person and home_person.handle == self.handle:
                fill_color = self.home_person_color

        item = GooCanvas.CanvasPolyline(parent=self.current_parent(),
                                        points=points,
                                        close_path=True,
                                        fill_color=fill_color,
                                        line_width=line_width,
                                        stroke_color=stroke_color,
                                        tooltip=tooltip)
        # turn on tooltip show if have it
        if tooltip:
            item_canvas = item.get_canvas()
            item_canvas.set_has_tooltip(True)

        self.item_hier.append(item)

    def stop_polygon(self, _tag):
        """
        Parse </polygon> tags.
        """
        self.item_hier.pop()

    def start_ellipse(self, attrs):
        """
        Parse <ellipse> tags.
        These define the family nodes of the graph.
        """
        center_x = float(attrs.get('cx'))
        center_y = float(attrs.get('cy'))
        radius_x = float(attrs.get('rx'))
        radius_y = float(attrs.get('ry'))
        style = attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            stroke_color = p_style['stroke']
            fill_color = p_style['fill']
        else:
            stroke_color = attrs.get('stroke')
            fill_color = attrs.get('fill')

        tooltip = self.view.tags_tooltips.get(self.handle)

        item = GooCanvas.CanvasEllipse(parent=self.current_parent(),
                                       center_x=center_x,
                                       center_y=center_y,
                                       radius_x=radius_x,
                                       radius_y=radius_y,
                                       fill_color=fill_color,
                                       stroke_color=stroke_color,
                                       line_width=1,
                                       tooltip=tooltip)
        if tooltip:
            item_canvas = item.get_canvas()
            item_canvas.set_has_tooltip(True)

        self.current_parent().description = 'familynode'
        self.item_hier.append(item)

    def stop_ellipse(self, _tag):
        """
        Parse </ellipse> tags.
        """
        self.item_hier.pop()

    def start_path(self, attrs):
        """
        Parse <path> tags.
        These define the links between nodes.
        Solid lines represent birth relationships and dashed lines are used
        when a child has a non-birth relationship to a parent.
        """
        p_data = attrs.get('d')
        line_width = attrs.get('stroke-width')
        if line_width is None:
            line_width = 1
        line_width = float(line_width)
        style = attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            stroke_color = p_style['stroke']
            is_dashed = 'stroke-dasharray' in p_style
        else:
            stroke_color = attrs.get('stroke')
            is_dashed = attrs.get('stroke-dasharray')

        if is_dashed:
            line_dash = GooCanvas.CanvasLineDash.newv([5.0, 5.0])
            item = GooCanvas.CanvasPath(parent=self.current_parent(),
                                        data=p_data,
                                        stroke_color=stroke_color,
                                        line_width=line_width,
                                        line_dash=line_dash)
        else:
            item = GooCanvas.CanvasPath(parent=self.current_parent(),
                                        data=p_data,
                                        stroke_color=stroke_color,
                                        line_width=line_width)
        self.item_hier.append(item)

    def stop_path(self, _tag):
        """
        Parse </path> tags.
        """
        self.item_hier.pop()

    def start_text(self, attrs):
        """
        Parse <text> tags.
        """
        self.text_attrs = attrs

    def stop_text(self, tag):
        """
        Parse </text> tags.
        The text tag contains some textual data.
        """
        tag = escape(tag)

        pos_x = float(self.text_attrs.get('x'))
        pos_y = float(self.text_attrs.get('y'))
        anchor = self.text_attrs.get('text-anchor')
        style = self.text_attrs.get('style')

        # does the following always work with symbols?
        if style:
            p_style = self.parse_style(style)
            font_family = p_style['font-family']
            text_font = font_family + ", " + p_style['font-size'] + 'px'
        else:
            font_family = self.text_attrs.get('font-family')
            text_font = font_family + ", " + str(self.font_size) + 'px'

        font_desc = Pango.FontDescription.from_string(text_font)

        # set bold text using PangoMarkup
        if self.text_attrs.get('font-weight') == 'bold':
            tag = '<b>%s</b>' % tag

        # text color
        fill_color = self.text_attrs.get('fill')

        GooCanvas.CanvasText(parent=self.current_parent(),
                             text=tag,
                             x=pos_x,
                             y=pos_y,
                             anchor=self.text_anchor_map[anchor],
                             use_markup=True,
                             font_desc=font_desc,
                             fill_color=fill_color)

    def start_image(self, attrs):
        """
        Parse <image> tags.
        """
        pos_x = float(attrs.get('x'))
        pos_y = float(attrs.get('y'))
        width = float(attrs.get('width').rstrip(string.ascii_letters))
        height = float(attrs.get('height').rstrip(string.ascii_letters))
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(attrs.get('xlink:href'))

        item = GooCanvas.CanvasImage(parent=self.current_parent(),
                                     x=pos_x,
                                     y=pos_y,
                                     height=height,
                                     width=width,
                                     pixbuf=pixbuf)
        self.item_hier.append(item)

    def stop_image(self, _tag):
        """
        Parse </image> tags.
        """
        self.item_hier.pop()

    def start_element(self, tag, attrs):
        """
        Generic parsing function for opening tags.
        """
        self.func_list.append((self.func, self.tlist))
        self.tlist = []

        try:
            start_function, self.func = self.func_map[tag]
            if start_function:
                start_function(attrs)
        except KeyError:
            self.func_map[tag] = (None, None)
            self.func = None

    def end_element(self, _tag):
        """
        Generic parsing function for closing tags.
        """
        if self.func:
            self.func(''.join(self.tlist))
        self.func, self.tlist = self.func_list.pop()

    def characters(self, data):
        """
        Generic parsing function for tag data.
        """
        if self.func:
            self.tlist.append(data)

    def current_parent(self):
        """
        Returns the Goocanvas object which should be the parent of any new
        Goocanvas objects.
        """
        return self.item_hier[len(self.item_hier) - 1]

    def parse_style(self, style):
        """
        Parse style attributes for Graphviz version < 2.24.
        """
        style = style.rstrip(';')
        return dict([i.split(':') for i in style.split(';')])


#------------------------------------------------------------------------
#
# DotSvgGenerator
#
#------------------------------------------------------------------------
class DotSvgGenerator(object):
    """
    Generator of graphing instructions in dot format and svg data by Graphviz.
    """
    def __init__(self, dbstate, view, bold_size=0, norm_size=0):
        """
        Initialise the DotSvgGenerator class.
        """
        self.bold_size = bold_size
        self.norm_size = norm_size
        self.dbstate = dbstate
        self.uistate = view.uistate
        self.database = dbstate.db
        self.view = view

        self.dot = None         # will be StringIO()

        # This dictionary contains person handle as the index and the value is
        # the number of families in which the person is a parent. From this
        # dictionary is obtained a list of person handles sorted in decreasing
        # value order which is used to keep multiple spouses positioned
        # together.
        self.person_handles_dict = {}
        self.person_handles = []

        # list of persons on path to home person
        self.current_list = list()
        self.home_person = None

        # Gtk style context for scrollwindow
        self.context = self.view.graph_widget.sw_style_context

        # font if we use genealogical symbols
        self.sym_font = None

        self.avatars = Avatars(self.view._config)

    def __del__(self):
        """
        Free stream file on destroy.
        """
        if self.dot:
            self.dot.close()

    def init_dot(self):
        """
        Init/reinit stream for dot file.
        Load and write config data to start of dot file.
        """
        if self.dot:
            self.dot.close()
        self.dot = StringIO()

        self.current_list.clear()
        self.person_handles_dict.clear()

        self.show_images = self.view._config.get(
            'interface.graphview-show-images')
        self.show_avatars = self.view._config.get(
            'interface.graphview-show-avatars')
        self.show_full_dates = self.view._config.get(
            'interface.graphview-show-full-dates')
        self.show_places = self.view._config.get(
            'interface.graphview-show-places')
        self.place_format = self.view._config.get(
            'interface.graphview-place-format') - 1
        self.show_tag_color = self.view._config.get(
            'interface.graphview-show-tags')
        spline = self.view._config.get('interface.graphview-show-lines')
        self.spline = SPLINE.get(int(spline))
        self.descendant_generations = self.view._config.get(
            'interface.graphview-descendant-generations')
        self.ancestor_generations = self.view._config.get(
            'interface.graphview-ancestor-generations')
        self.person_theme_index = self.view._config.get(
            'interface.graphview-person-theme')
        self.show_all_connected = self.view._config.get(
            'interface.graphview-show-all-connected')
        ranksep = self.view._config.get('interface.graphview-ranksep')
        ranksep = ranksep * 0.1
        nodesep = self.view._config.get('interface.graphview-nodesep')
        nodesep = nodesep * 0.1
        self.avatars.update_current_style()
        # get background color from gtk theme and convert it to hex
        # else use white background
        bg_color = self.context.lookup_color('theme_bg_color')
        if bg_color[0]:
            bg_rgb = (bg_color[1].red, bg_color[1].green, bg_color[1].blue)
            bg_color = rgb_to_hex(bg_rgb)
        else:
            bg_color = '#ffffff'

        # get font color from gtk theme and convert it to hex
        # else use black font
        font_color = self.context.lookup_color('theme_fg_color')
        if font_color[0]:
            fc_rgb = (font_color[1].red, font_color[1].green,
                      font_color[1].blue)
            font_color = rgb_to_hex(fc_rgb)
        else:
            font_color = '#000000'

        # get colors from config
        home_path_color = self.view._config.get(
            'interface.graphview-home-path-color')

        # set of colors
        self.colors = {'link_color':      font_color,
                       'home_path_color': home_path_color}

        self.arrowheadstyle = 'none'
        self.arrowtailstyle = 'none'

        dpi = 72
        # use font from config if needed
        font = self.view._config.get('interface.graphview-font')
        fontfamily = self.resolve_font_name(font[0])
        self.fontsize = font[1]
        if not self.bold_size:
            self.bold_size = self.norm_size = font[1]

        pagedir = "BL"
        direction = self.view._config.get('interface.graphview-direction')
        rankdir = {0: "TB", 1: "BT", 2: "LR", 3: "RL"}
        ratio = "compress"
        # as we are not using paper,
        # choose a large 'page' size with no margin
        sizew = 100
        sizeh = 100
        xmargin = 0.00
        ymargin = 0.00

        self.write('digraph GRAMPS_graph\n')
        self.write('{\n')
        self.write(' bgcolor="%s";\n' % bg_color)
        self.write(' center="false"; \n')
        self.write(' charset="utf8";\n')
        self.write(' concentrate="false";\n')
        self.write(' dpi="%d";\n' % dpi)
        self.write(' graph [fontsize=%3.1f];\n' % self.fontsize)
        self.write(' margin="%3.2f,%3.2f"; \n' % (xmargin, ymargin))
        self.write(' mclimit="99";\n')
        self.write(' nodesep="%.2f";\n' % nodesep)
        self.write(' outputorder="edgesfirst";\n')
        self.write(' pagedir="%s";\n' % pagedir)
        self.write(' rankdir="%s";\n' % rankdir.get(direction, "TB"))
        self.write(' ranksep="%.2f";\n' % ranksep)
        self.write(' ratio="%s";\n' % ratio)
        self.write(' searchsize="100";\n')
        self.write(' size="%3.2f,%3.2f"; \n' % (sizew, sizeh))
        self.write(' splines=%s;\n' % self.spline)
        self.write('\n')
        self.write(' edge [style=solid fontsize=%d];\n' % self.fontsize)

        if fontfamily:
            self.write(' node [style=filled fontname="%s" '
                       'fontsize=%3.1f fontcolor="%s"];\n'
                       % (fontfamily, self.norm_size, font_color))
        else:
            self.write(' node [style=filled fontsize=%3.1f fontcolor="%s"];\n'
                       % (self.norm_size, font_color))
        self.write('\n')
        self.uistate.connect('font-changed', self.font_changed)
        self.symbols = Symbols()
        self.font_changed()

    def resolve_font_name(self, font_name):
        """
        Helps to resolve font by graphviz.
        """
        # Sometimes graphviz have problem with font resolving.
        font_family_map = {"Times New Roman": "Times",
                           "Times Roman":     "Times",
                           "Times-Roman":     "Times",
                           }
        font = font_family_map.get(font_name)
        if font is None:
            font = font_name
        return font

    def font_changed(self):
        dth_idx = self.uistate.death_symbol
        if self.uistate.symbols:
            self.bth = self.symbols.get_symbol_for_string(
                self.symbols.SYMBOL_BIRTH)
            self.dth = self.symbols.get_death_symbol_for_char(dth_idx)
        else:
            self.bth = self.symbols.get_symbol_fallback(
                self.symbols.SYMBOL_BIRTH)
            self.dth = self.symbols.get_death_symbol_fallback(dth_idx)
        # make sure to display in selected symbols font
        self.sym_font = config.get('utf8.selected-font')
        self.bth = '<FONT FACE="%s">%s</FONT>' % (self.sym_font, self.bth)
        self.dth = '<FONT FACE="%s">%s</FONT>' % (self.sym_font, self.dth)

    def build_graph(self, active_person, path_to_home_person):
        """
        Builds a GraphViz tree based on the active person.
        """
        # reinit dot file stream (write starting graphviz dot code to file)
        self.init_dot()

        if active_person:
            self.home_person = self.dbstate.db.get_default_person()
            self.set_current_list(active_person)
            self.set_current_list_desc(active_person)
            self.path_to_home_person = True

            if path_to_home_person:
                self.person_handles_dict.update(
                    self.find_path_to_home(active_person))
            else:
                if self.show_all_connected:
                    self.person_handles_dict.update(
                        self.find_connected(active_person))
                else:
                    self.person_handles_dict.update(
                        self.find_descendants(active_person))
                    self.person_handles_dict.update(
                        self.find_ancestors(active_person))

            if self.person_handles_dict:
                self.person_handles = sorted(
                    self.person_handles_dict,
                    key=self.person_handles_dict.__getitem__,
                    reverse=True)
                self.add_persons_and_families()
                self.add_child_links_to_families()

        # close the graphviz dot code with a brace
        self.write('}\n')

        # get DOT and generate SVG data by Graphviz
        dot_data = self.dot.getvalue().encode('utf8')
        svg_data = self.make_svg(dot_data)

        return (dot_data, svg_data)

    def make_svg(self, dot_data):
        """
        Make SVG data by Graphviz.
        """
        if win():
            svg_data = Popen(['dot', '-Tsvg'],
                             creationflags=DETACHED_PROCESS,
                             stdin=PIPE,
                             stdout=PIPE,
                             stderr=PIPE).communicate(input=dot_data)[0]
        else:
            svg_data = Popen(['dot', '-Tsvg'],
                             stdin=PIPE,
                             stdout=PIPE).communicate(input=dot_data)[0]
        return svg_data

    def set_current_list(self, active_person, recurs_list=None):
        """
        Get the path from the active person to the home person.
        Select ancestors.
        """
        if not active_person:
            return False
        person = self.database.get_person_from_handle(active_person)
        if recurs_list is None:
            recurs_list = set()  # make a recursion check list (actually a set)
        # see if we have a recursion (database loop)
        elif active_person in recurs_list:
            logging.warning(_("Relationship loop detected"))
            return False
        recurs_list.add(active_person)  # record where we have been for check
        if person == self.home_person:
            self.current_list.append(active_person)
            return True
        else:
            for fam_handle in person.get_parent_family_handle_list():
                family = self.database.get_family_from_handle(fam_handle)
                if self.set_current_list(family.get_father_handle(),
                                         recurs_list=recurs_list):
                    self.current_list.append(active_person)
                    self.current_list.append(fam_handle)
                    return True
                if self.set_current_list(family.get_mother_handle(),
                                         recurs_list=recurs_list):
                    self.current_list.append(active_person)
                    self.current_list.append(fam_handle)
                    return True
        return False

    def set_current_list_desc(self, active_person, recurs_list=None):
        """
        Get the path from the active person to the home person.
        Select children.
        """
        if not active_person:
            return False
        person = self.database.get_person_from_handle(active_person)
        if recurs_list is None:
            recurs_list = set()  # make a recursion check list (actually a set)
        # see if we have a recursion (database loop)
        elif active_person in recurs_list:
            logging.warning(_("Relationship loop detected"))
            return False
        recurs_list.add(active_person)  # record where we have been for check
        if person == self.home_person:
            self.current_list.append(active_person)
            return True
        else:
            for fam_handle in person.get_family_handle_list():
                family = self.database.get_family_from_handle(fam_handle)
                for child in family.get_child_ref_list():
                    if self.set_current_list_desc(child.ref,
                                                  recurs_list=recurs_list):
                        self.current_list.append(active_person)
                        self.current_list.append(fam_handle)
                        return True
        return False

    def find_connected(self, active_person):
        """
        Spider the database from the active person.
        """
        person = self.database.get_person_from_handle(active_person)
        person_handles = {}
        self.add_connected(person, self.descendant_generations,
                           self.ancestor_generations, person_handles)
        return person_handles

    def add_connected(self, person, num_desc, num_anc, person_handles):
        """
        Include all connected to active in the list of people to graph.
        Recursive algorithm is not used becasue some trees have been found
        that exceed the standard python recursive depth.
        """
        # list of work to do, handles with generation delta,
        # add to right and pop from left
        todo = deque([(person, 0)])

        while todo:
            # check for person count
            if len(person_handles) > 1000:
                w_msg = _("You try to build graph containing more then 1000 "
                          "persons. Not all persons will be shown in the graph."
                         )
                WarningDialog(_("Incomplete graph"), w_msg)
                return

            person, delta_gen = todo.popleft()

            if not person:
                continue
            # check generation restrictions
            if (delta_gen > num_desc) or (delta_gen < -num_anc):
                continue

            # check if handle is not already processed
            if person.handle not in person_handles:
                spouses_list = person.get_family_handle_list()
                person_handles[person.handle] = len(spouses_list)
            else:
                continue

            # add descendants
            for family_handle in spouses_list:
                family = self.database.get_family_from_handle(family_handle)

                # add every child recursively
                if num_desc >= (delta_gen + 1):  # generation restriction
                    for child_ref in family.get_child_ref_list():
                        if (child_ref.ref in person_handles
                            or child_ref.ref in todo):
                                continue
                        todo.append(
                            (self.database.get_person_from_handle(child_ref.ref),
                             delta_gen+1))

                # add person spouses
                for sp_handle in (family.get_father_handle(),
                                  family.get_mother_handle()):
                    if sp_handle and (sp_handle not in person_handles
                                      and sp_handle not in todo):
                        todo.append(
                            (self.database.get_person_from_handle(sp_handle),
                             delta_gen))

            # add ancestors
            if -num_anc <= (delta_gen - 1):  # generation restriction
                for family_handle in person.get_parent_family_handle_list():
                    family = self.database.get_family_from_handle(family_handle)

                    # add every ancestor's spouses
                    for sp_handle in (family.get_father_handle(),
                                      family.get_mother_handle()):
                        if sp_handle and (sp_handle not in person_handles
                                          and sp_handle not in todo):
                            todo.append(
                                (self.database.get_person_from_handle(sp_handle),
                                 delta_gen-1))

    def find_descendants(self, active_person):
        """
        Spider the database from the active person.
        """
        person = self.database.get_person_from_handle(active_person)
        person_handles = {}
        self.add_descendant(person, self.descendant_generations,
                            person_handles)
        return person_handles

    def add_descendant(self, person, num_generations, person_handles):
        """
        Include a descendant in the list of people to graph.
        """
        if not person:
            return

        # check if handle is not already processed
        # and add self and spouses
        if person.handle not in person_handles:
            spouses_list = person.get_family_handle_list()

            person_handles[person.handle] = len(spouses_list)
            self.add_spouses(person, person_handles)
        else:
            return

        if num_generations <= 0:
            return

        # add every child recursively
        for family_handle in spouses_list:
            family = self.database.get_family_from_handle(family_handle)

            for child_ref in family.get_child_ref_list():
                self.add_descendant(
                    self.database.get_person_from_handle(child_ref.ref),
                    num_generations - 1, person_handles)

    def find_path_to_home(self, active_person):
        """
        Find all the people in the direct path between the active person
        and the home person.
        """
        home_person = self.dbstate.db.get_default_person()
        active_person = self.database.get_person_from_handle(active_person)
        FilterClass = GenericFilterFactory('Person')
        filter = FilterClass()
        plist = self.database.iter_person_handles()
        path = rules.person.RelationshipPathBetween([active_person.gramps_id, home_person.gramps_id])
        filter.add_rule(path)
        person_list = filter.apply(self.database, plist)
        person_handles = dict.fromkeys(person_list,0)
        return person_handles

    def add_spouses(self, person, person_handles):
        """
        Add spouses to the list.
        """
        if not person:
            return

        for family_handle in person.get_family_handle_list():
            sp_family = self.database.get_family_from_handle(family_handle)

            for sp_handle in (sp_family.get_father_handle(),
                              sp_family.get_mother_handle()):
                if sp_handle and sp_handle not in person_handles:
                    # add only spouse (num_generations = 0)
                    self.add_descendant(
                        self.database.get_person_from_handle(sp_handle),
                        0, person_handles)

    def find_ancestors(self, active_person):
        """
        Spider the database from the active person.
        """
        person = self.database.get_person_from_handle(active_person)
        person_handles = {}
        self.add_ancestor(person, self.ancestor_generations, person_handles)
        return person_handles

    def add_ancestor(self, person, num_generations, person_handles):
        """
        Include an ancestor in the list of people to graph.
        """
        if not person:
            return

        # add self if handle is not already processed
        if person.handle not in person_handles:
            person_handles[person.handle] = len(person.get_family_handle_list())
        else:
            return

        if num_generations <= 0:
            return

        for family_handle in person.get_parent_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)

            # add parents
            sp_persons = []
            for sp_handle in (family.get_father_handle(),
                              family.get_mother_handle()):
                if sp_handle and sp_handle not in person_handles:
                    sp_person = self.database.get_person_from_handle(sp_handle)
                    self.add_ancestor(sp_person,
                                      num_generations - 1,
                                      person_handles)
                    sp_persons.append(sp_person)

            # add every other spouses for parents
            for sp_person in sp_persons:
                self.add_spouses(sp_person, person_handles)

    def add_child_links_to_families(self):
        """
        Returns string of GraphViz edges linking parents to families or
        children.
        """
        for person_handle in self.person_handles:
            person = self.database.get_person_from_handle(person_handle)
            for fam_handle in person.get_parent_family_handle_list():
                family = self.database.get_family_from_handle(fam_handle)
                father_handle = family.get_father_handle()
                mother_handle = family.get_mother_handle()
                for child_ref in family.get_child_ref_list():
                    if child_ref.ref == person_handle:
                        frel = child_ref.frel
                        mrel = child_ref.mrel
                        break
                if((father_handle in self.person_handles) or
                   (mother_handle in self.person_handles)):
                    # link to the family node if either parent is in graph
                    self.add_family_link(person_handle, family, frel, mrel)

    def add_family_link(self, p_id, family, frel, mrel):
        """
        Links the child to a family.
        """
        style = 'solid'
        adopted = ((int(frel) != ChildRefType.BIRTH) or
                   (int(mrel) != ChildRefType.BIRTH))
        # if birth relation to father is NONE, meaning there is no father and
        # if birth relation to mother is BIRTH then solid line
        if((int(frel) == ChildRefType.NONE) and
           (int(mrel) == ChildRefType.BIRTH)):
            adopted = False
        if adopted:
            style = 'dotted'
        self.add_link(family.handle, p_id, style,
                      self.arrowheadstyle, self.arrowtailstyle,
                      color=self.colors['home_path_color'],
                      bold=self.is_in_path_to_home(p_id))

    def add_parent_link(self, p_id, parent_handle, rel):
        """
        Links the child to a parent.
        """
        style = 'solid'
        if int(rel) != ChildRefType.BIRTH:
            style = 'dotted'
        self.add_link(parent_handle, p_id, style,
                      self.arrowheadstyle, self.arrowtailstyle,
                      color=self.colors['home_path_color'],
                      bold=self.is_in_path_to_home(p_id))

    def add_persons_and_families(self):
        """
        Adds nodes for persons and their families.
        Subgraphs are used to indicate to Graphviz that parents of families
        should be positioned together. The person_handles list is sorted so
        that people with the largest number of spouses are at the start of the
        list. As families are only processed once, this means people with
        multiple spouses will have their additional spouses included in their
        subgraph.
        """
        # variable to communicate with get_person_label
        url = ""

        # The list of families for which we have output the node,
        # so we don't do it twice
        # use set() as it little faster then list()
        family_nodes_done = set()
        family_links_done = set()
        for person_handle in self.person_handles:
            person = self.database.get_person_from_handle(person_handle)
            # Output the person's node
            label = self.get_person_label(person)
            (shape, style, color, fill) = self.get_gender_style(person)
            self.add_node(person_handle, label, shape, color, style, fill, url)

            # Output family nodes where person is a parent
            family_list = person.get_family_handle_list()
            for fam_handle in family_list:
                if fam_handle not in family_nodes_done:
                    family_nodes_done.add(fam_handle)
                    self.__add_family_node(fam_handle)

            # Output family links where person is a parent
            subgraph_started = False
            family_list = person.get_family_handle_list()
            for fam_handle in family_list:
                if fam_handle not in family_links_done:
                    family_links_done.add(fam_handle)
                    if not subgraph_started:
                        subgraph_started = True
                        self.start_subgraph(person_handle)
                    self.__add_family_links(fam_handle)
            if subgraph_started:
                self.end_subgraph()

    def is_in_path_to_home(self, f_handle):
        """
        Is the current person in the path to the home person?
        """
        if f_handle in self.current_list:
            return True
        return False

    def __add_family_node(self, fam_handle):
        """
        Add a node for a family.
        """
        fam = self.database.get_family_from_handle(fam_handle)
        fill, color = color_graph_family(fam, self.dbstate)
        style = "filled"
        label = self.get_family_label(fam)

        self.add_node(fam_handle, label, "ellipse", color, style, fill)

    def __add_family_links(self, fam_handle):
        """
        Add the links for spouses.
        """
        fam = self.database.get_family_from_handle(fam_handle)
        f_handle = fam.get_father_handle()
        m_handle = fam.get_mother_handle()
        if f_handle in self.person_handles:
            self.add_link(f_handle,
                          fam_handle, "",
                          self.arrowheadstyle,
                          self.arrowtailstyle,
                          color=self.colors['home_path_color'],
                          bold=self.is_in_path_to_home(f_handle))
        if m_handle in self.person_handles:
            self.add_link(m_handle,
                          fam_handle, "",
                          self.arrowheadstyle,
                          self.arrowtailstyle,
                          color=self.colors['home_path_color'],
                          bold=self.is_in_path_to_home(m_handle))

    def get_gender_style(self, person):
        """
        Return gender specific person style.
        """
        gender = person.get_gender()
        shape = "box"
        style = "solid, filled"

        # get alive status of person to get box color
        try:
            alive = probably_alive(person, self.dbstate.db)
        except RuntimeError:
            alive = False

        fill, color = color_graph_box(alive, gender)
        return(shape, style, color, fill)

    def get_tags_and_table(self, obj):
        """
        Return html tags table for obj (person or family).
        """
        tag_table = ''
        tags = []

        for tag_handle in obj.get_tag_list():
            tags.append(self.dbstate.db.get_tag_from_handle(tag_handle))

        # prepare html table of tags
        if tags:
            tag_table = ('<TABLE BORDER="0" CELLBORDER="0" '
                         'CELLPADDING="5"><TR>')
            for tag in tags:
                rgba = Gdk.RGBA()
                rgba.parse(tag.get_color())
                value = '#%02x%02x%02x' % (int(rgba.red * 255),
                                           int(rgba.green * 255),
                                           int(rgba.blue * 255))
                tag_table += '<TD BGCOLOR="%s"></TD>' % value
            tag_table += '</TR></TABLE>'

        return tags, tag_table

    def get_person_themes(self, index=-1):
        """
        Person themes.
        If index == -1 return list of themes.
        If index out of range return default theme.
        """
        person_themes = [
            (0, _('Default'),
             '<TABLE '
             'BORDER="0" CELLSPACING="2" CELLPADDING="0" CELLBORDER="0">'
             '<TR><TD>%(img)s</TD></TR>'
             '<TR><TD><FONT POINT-SIZE="%(bsize)3.1f"><B>%(name)s</B>'
             '</FONT></TD></TR>'
             '<TR><TD ALIGN="LEFT">%(birth_str)s</TD></TR>'
             '<TR><TD ALIGN="LEFT">%(death_str)s</TD></TR>'
             '<TR><TD>%(tags)s</TD></TR>'
             '</TABLE>'
             ),
            (1, _('Image on right side'),
             '<TABLE '
             'BORDER="0" CELLSPACING="5" CELLPADDING="0" CELLBORDER="0">'
             '<tr>'
             '<td colspan="2"><FONT POINT-SIZE="%(bsize)3.1f"><B>%(name)s'
             '</B></FONT></td>'
             '</tr>'
             '<tr>'
             '<td ALIGN="LEFT" BALIGN="LEFT" CELLPADDING="5">%(birth_wraped)s'
             '</td>'
             '<td rowspan="2">%(img)s</td>'
             '</tr>'
             '<tr>'
             '<td ALIGN="LEFT" BALIGN="LEFT" CELLPADDING="5">%(death_wraped)s'
             '</td>'
             '</tr>'
             '<tr>'
             '  <td colspan="2">%(tags)s</td>'
             '</tr>'
             '</TABLE>'
             ),
            (2, _('Image on left side'),
             '<TABLE '
             'BORDER="0" CELLSPACING="5" CELLPADDING="0" CELLBORDER="0">'
             '<tr>'
             '<td colspan="2"><FONT POINT-SIZE="%(bsize)3.1f"><B>%(name)s'
             '</B></FONT></td>'
             '</tr>'
             '<tr>'
             '<td rowspan="2">%(img)s</td>'
             '<td ALIGN="LEFT" BALIGN="LEFT" CELLPADDING="5">%(birth_wraped)s'
             '</td>'
             '</tr>'
             '<tr>'
             '<td ALIGN="LEFT" BALIGN="LEFT" CELLPADDING="5">%(death_wraped)s'
             '</td>'
             '</tr>'
             '<tr>'
             '  <td colspan="2">%(tags)s</td>'
             '</tr>'
             '</TABLE>'
             ),
            (3, _('Normal'),
             '<TABLE '
             'BORDER="0" CELLSPACING="2" CELLPADDING="0" CELLBORDER="0">'
             '<TR><TD>%(img)s</TD></TR>'
             '<TR><TD><FONT POINT-SIZE="%(bsize)3.1f"><B>%(name)s'
             '</B></FONT></TD></TR>'
             '<TR><TD ALIGN="LEFT" BALIGN="LEFT">%(birth_wraped)s</TD></TR>'
             '<TR><TD ALIGN="LEFT" BALIGN="LEFT">%(death_wraped)s</TD></TR>'
             '<TR><TD>%(tags)s</TD></TR>'
             '</TABLE>'
             )]

        if index < 0:
            return person_themes

        if index < len(person_themes):
            return person_themes[index]
        else:
            return person_themes[0]

    def get_person_label(self, person):
        """
        Return person label string (with tags).
        """
        # Start an HTML table.
        # Remember to close the table afterwards!
        #
        # This isn't a free-form HTML format here...just a few keywords that
        # happen to be similar to keywords commonly seen in HTML.
        # For additional information on what is allowed, see:
        #
        #       http://www.graphviz.org/info/shapes.html#html
        #
        # Will use html.escape to avoid '&', '<', '>' in the strings.

        # FIRST get all strings: img, name, dates, tags

        # see if we have an image to use for this person
        image = ''
        if self.show_images:
            image = self.view.graph_widget.get_person_image(person,
                                                            kind='path')
            if not image and self.show_avatars:
                image = self.avatars.get_avatar(gender=person.gender)

            if image is not None:
                image = '<IMG SRC="%s"/>' % image
            else:
                image = ''

        # get the person's name
        name = displayer.display_name(person.get_primary_name())
        # name string should not be empty
        name = escape(name) if name else ' '

        # birth, death is a lists [date, place]
        birth, death = self.get_date_strings(person)

        birth_str = ''
        death_str = ''
        birth_wraped = ''
        death_wraped = ''

        # There are two ways of displaying dates:
        # 1) full and on two lines:
        #       b. 1890-12-31 - BirthPlace
        #       d. 1960-01-02 - DeathPlace
        if self.show_full_dates or self.show_places:
            # add symbols
            if birth[0]:
                birth[0] = '%s %s' % (self.bth, birth[0])
                birth_wraped = birth[0]
                birth_str = birth[0]
                if birth[1]:
                    birth_wraped += '<BR/>'
                    birth_str += '  '
            elif birth[1]:
                birth_wraped = _('%s ') % self.bth
                birth_str = _('%s ') % self.bth
            birth_wraped += birth[1]
            birth_str += birth[1]

            if death[0]:
                death[0] = '%s %s' % (self.dth, death[0])
                death_wraped = death[0]
                death_str = death[0]
                if death[1]:
                    death_wraped += '<BR/>'
                    death_str += '  '
            elif death[1]:
                death_wraped = _('%s ') % self.dth
                death_str = _('%s ') % self.dth
            death_wraped += death[1]
            death_str += death[1]

        # 2) simple and on one line:
        #       (1890 - 1960)
        else:
            if birth[0] or death[0]:
                birth_str = '(%s - %s)' % (birth[0], death[0])
                # add symbols
                if image:
                    if birth[0]:
                        birth_wraped = '%s %s' % (self.bth, birth[0])
                    if death[0]:
                        death_wraped = '%s %s' % (self.dth, death[0])
                else:
                    birth_wraped = birth_str

        # get tags table for person and add tooltip for node
        tag_table = ''
        if self.show_tag_color:
            tags, tag_table = self.get_tags_and_table(person)
            if tag_table:
                self.add_tags_tooltip(person.handle, tags)

        # apply theme to person label
        if(image or self.person_theme_index == 0 or
           self.person_theme_index == 3):
            p_theme = self.get_person_themes(self.person_theme_index)
        else:
            # use default theme if no image
            p_theme = self.get_person_themes(3)

        label = p_theme[2] % {'img': image,
                              'name': name,
                              'birth_str': birth_str,
                              'death_str': death_str,
                              'birth_wraped': birth_wraped,
                              'death_wraped': death_wraped,
                              'tags': tag_table,
                              'bsize' : self.bold_size}
        return label

    def get_family_label(self, family):
        """
        Return family label string (with tags).
        """
        # start main html table
        label = ('<TABLE '
                 'BORDER="0" CELLSPACING="2" CELLPADDING="0" CELLBORDER="0">')

        # add dates strtings to table
        event_str = ['', '']
        for event_ref in family.get_event_ref_list():
            event = self.database.get_event_from_handle(event_ref.ref)
            if (event.type == EventType.MARRIAGE and
                    (event_ref.get_role() == EventRoleType.FAMILY or
                     event_ref.get_role() == EventRoleType.PRIMARY)):
                event_str = self.get_event_string(event)
                break
        if event_str[0] and event_str[1]:
            event_str = '%s<BR/>%s' % (event_str[0], event_str[1])
        elif event_str[0]:
            event_str = event_str[0]
        elif event_str[1]:
            event_str = event_str[1]
        else:
            event_str = ''

        label += '<TR><TD>%s</TD></TR>' % event_str

        # add tags table for family and add tooltip for node
        if self.show_tag_color:
            tags, tag_table = self.get_tags_and_table(family)

            if tag_table:
                label += '<TR><TD>%s</TD></TR>' % tag_table
                self.add_tags_tooltip(family.handle, tags)

        # close main table
        label += '</TABLE>'

        return label

    def get_date_strings(self, person):
        """
        Returns tuple of birth/christening and death/burying date strings.
        """
        birth_event = get_birth_or_fallback(self.database, person)
        if birth_event:
            birth = self.get_event_string(birth_event)
        else:
            birth = ['', '']

        death_event = get_death_or_fallback(self.database, person)
        if death_event:
            death = self.get_event_string(death_event)
        else:
            death = ['', '']

        return (birth, death)

    def get_event_string(self, event):
        """
        Return string for an event label.

        Based on the data availability and preferences, we select one
        of the following for a given event:
            year only
            complete date
            place name
            empty string
        """
        if event:
            place_title = place_displayer.display_event(self.database, event,
                                                        fmt=self.place_format)
            date_object = event.get_date_object()
            date = ''
            place = ''
            # shall we display full date
            # or do we have a valid year to display only year
            if(self.show_full_dates and date_object.get_text() or
               date_object.get_year_valid()):
                if self.show_full_dates:
                    date = '%s' % datehandler.get_date(event)
                else:
                    date = '%i' % date_object.get_year()
                # shall we add the place?
                if self.show_places and place_title:
                    place = place_title
                return [escape(date), escape(place)]
            else:
                if place_title and self.show_places:
                    return ['', escape(place_title)]
        return ['', '']

    def add_link(self, id1, id2, style="", head="", tail="", comment="",
                 bold=False, color=""):
        """
        Add a link between two nodes.
        Gramps handles are used as nodes but need to be prefixed
        with an underscore because Graphviz does not like IDs
        that begin with a number.
        """
        self.write('  _%s -> _%s' % (id1, id2))

        boldok = False
        if id1 in self.current_list:
            if id2 in self.current_list:
                boldok = True

        self.write(' [')

        if style:
            self.write(' style=%s' % style)
        if head:
            self.write(' arrowhead=%s' % head)
        if tail:
            self.write(' arrowtail=%s' % tail)
        if bold and boldok:
            self.write(' penwidth=%d' % 5)
            if color:
                self.write(' color="%s"' % color)
        else:
            # if not path to home than set default color of link
            self.write(' color="%s"' % self.colors['link_color'])

        self.write(' ]')

        self.write(';')

        if comment:
            self.write(' // %s' % comment)

        self.write('\n')

    def add_node(self, node_id, label, shape="", color="",
                 style="", fillcolor="", url="", fontsize=""):
        """
        Add a node to this graph.
        Nodes can be different shapes like boxes and circles.
        Gramps handles are used as nodes but need to be prefixed with an
        underscore because Graphviz does not like IDs that begin with a number.
        """
        text = '[margin="0.11,0.08"'

        if shape:
            text += ' shape="%s"' % shape

        if color:
            text += ' color="%s"' % color

        if fillcolor:
            color = hex_to_rgb_float(fillcolor)
            yiq = (color[0] * 299 + color[1] * 587 + color[2] * 114)
            fontcolor = "#ffffff" if yiq < 500 else "#000000"
            text += ' fillcolor="%s" fontcolor="%s"' % (fillcolor, fontcolor)
        if style:
            text += ' style="%s"' % style

        if fontsize:
            text += ' fontsize="%s"' % fontsize
        # note that we always output a label -- even if an empty string --
        # otherwise GraphViz uses the node ID as the label which is unlikely
        # to be what the user wants to see in the graph
        text += ' label=<%s>' % label

        if url:
            text += ' URL="%s"' % url

        text += " ]"
        self.write(' _%s %s;\n' % (node_id, text))

    def add_tags_tooltip(self, handle, tag_list):
        """
        Add tooltip to dict {handle, tooltip}.
        """
        tooltip_str = _('<b>Tags:</b>')
        for tag in tag_list:
            tooltip_str += ('\n<span background="%s">  </span> - %s'
                            % (tag.get_color(), tag.get_name()))
        self.view.tags_tooltips[handle] = tooltip_str

    def start_subgraph(self, graph_id):
        """
        Opens a subgraph which is used to keep together related nodes
        on the graph.
        """
        self.write('\n subgraph cluster_%s\n' % graph_id)
        self.write(' {\n')
        # no border around subgraph (#0002176)
        self.write('  style="invis";\n')

    def end_subgraph(self):
        """
        Closes a subgraph section.
        """
        self.write(' }\n\n')

    def write(self, text):
        """
        Write text to the dot file.
        """
        if self.dot:
            self.dot.write(text)


#-------------------------------------------------------------------------
#
# CanvasAnimation
#
#-------------------------------------------------------------------------
class CanvasAnimation(object):
    """
    Produce animation for operations with canvas.
    """
    def __init__(self, view, canvas, scroll_window):
        """
        We need canvas and window in which it placed.
        And view to get config.
        """
        self.view = view
        self.canvas = canvas
        self.hadjustment = scroll_window.get_hadjustment()
        self.vadjustment = scroll_window.get_vadjustment()
        self.items_list = []
        self.in_motion = False
        self.max_count = self.view._config.get(
            'interface.graphview-animation-count')
        self.max_count = self.max_count * 2  # must be modulo 2

        self.show_animation = self.view._config.get(
            'interface.graphview-show-animation')

        # delay between steps in microseconds
        self.speed = self.view._config.get(
            'interface.graphview-animation-speed')
        self.speed = 50 * int(self.speed)
        # length of step
        self.step_len = 10

        # separated counter and direction of shaking
        # for each item that in shake procedure
        self.counter = {}
        self.shake = {}
        self.in_shake = []

    def update_items(self, items_list):
        """
        Update list of items for current graph.
        """
        self.items_list.clear()
        self.items_list.extend(items_list)

        self.in_shake.clear()
        # clear counters and shakes - items not exists anymore
        self.counter.clear()
        self.shake.clear()

    def stop_animation(self):
        """
        Stop move_to animation.
        And wait while thread is finished.
        """
        self.in_motion = False
        try:
            self.thread.join()
        except:
            pass

    def stop_shake_animation(self, item, stoped):
        """
        Processing of 'animation-finished' signal.
        Stop or keep shaking item depending on counter for item.
        """
        counter = self.counter.get(item.title)
        shake = self.shake.get(item.title)

        if (not stoped) and counter and shake and counter < self.max_count:
            self.shake[item.title] = (-1) * self.shake[item.title]
            self.counter[item.title] += 1
            item.animate(0, self.shake[item.title], 1, 0, False,
                         self.speed, 10, 0)
        else:
            item.disconnect_by_func(self.stop_shake_animation)
            try:
                self.counter.pop(item.title)
                self.shake.pop(item.title)
            except:
                pass

    def shake_person(self, person_handle):
        """
        Shake person node to help to see it.
        Use build-in function of CanvasItem.
        """
        item = self.get_item_by_title(person_handle)
        if item:
            self.shake_item(item)

    def shake_item(self, item):
        """
        Shake item to help to see it.
        Use build-in function of CanvasItem.
        """
        if item and self.show_animation and self.max_count > 0:
            if not self.counter.get(item.title):
                self.in_shake.append(item)
                self.counter[item.title] = 1
                self.shake[item.title] = 10
                item.connect('animation-finished', self.stop_shake_animation)
                item.animate(0, self.shake[item.title], 1, 0, False,
                             self.speed, 10, 0)

    def get_item_by_title(self, handle):
        """
        Find item by title.
        """
        if handle:
            for item in self.items_list:
                if item.title == handle:
                    return item
        return None

    def move_to_person(self, handle, animated):
        """
        Move graph to specified person by handle.
        """
        self.stop_animation()
        item = self.get_item_by_title(handle)
        if item:
            bounds = item.get_bounds()
            # calculate middle of node coordinates
            xxx = (bounds.x2 - (bounds.x2 - bounds.x1) / 2)
            yyy = (bounds.y1 - (bounds.y1 - bounds.y2) / 2)
            self.move_to(item, (xxx, yyy), animated)
            return True
        return False

    def get_trace_to(self, destination):
        """
        Return next point to destination from current position.
        """
        # get current position (left-top corner) with scale
        start_x = self.hadjustment.get_value() / self.canvas.get_scale()
        start_y = self.vadjustment.get_value() / self.canvas.get_scale()

        x_delta = destination[0] - start_x
        y_delta = destination[1] - start_y

        # calculate step count depending on length of the trace
        trace_len = sqrt(pow(x_delta, 2) + pow(y_delta, 2))
        steps_count = int(trace_len / self.step_len * self.canvas.get_scale())

        # prevent division by 0
        if steps_count > 0:
            x_step = x_delta / steps_count
            y_step = y_delta / steps_count

            point = (start_x + x_step, start_y + y_step)
        else:
            point = destination
        return point

    def scroll_canvas(self, point):
        """
        Scroll window to point on canvas.
        """
        self.canvas.scroll_to(point[0], point[1])

    def animation(self, item, destination):
        """
        Animate scrolling to destination point in thread.
        Dynamically get points to destination one by one
        and try to scroll to them.
        """
        self.in_motion = True
        while self.in_motion:
            # correct destination to window centre
            h_offset = self.hadjustment.get_page_size() / 2
            v_offset = self.vadjustment.get_page_size() / 3
            # apply the scaling factor so the offset is adjusted to the scale
            h_offset = h_offset / self.canvas.get_scale()
            v_offset = v_offset / self.canvas.get_scale()

            dest = (destination[0] - h_offset,
                    destination[1] - v_offset)

            # get maximum scroll of window
            max_scroll_x = ((self.hadjustment.get_upper() -
                             self.hadjustment.get_page_size()) /
                            self.canvas.get_scale())
            max_scroll_y = ((self.vadjustment.get_upper() -
                             self.vadjustment.get_page_size()) /
                            self.canvas.get_scale())

            # fix destination to fit in max scroll
            if dest[0] > max_scroll_x:
                dest = (max_scroll_x, dest[1])
            if dest[0] < 0:
                dest = (0, dest[1])
            if dest[1] > max_scroll_y:
                dest = (dest[0], max_scroll_y)
            if dest[1] < 0:
                dest = (dest[0], 0)

            cur_pos = (self.hadjustment.get_value() / self.canvas.get_scale(),
                       self.vadjustment.get_value() / self.canvas.get_scale())

            # finish if we already at destination
            if dest == cur_pos:
                break

            # get next point to destination
            point = self.get_trace_to(dest)

            GLib.idle_add(self.scroll_canvas, point)
            GLib.usleep(20 * self.speed)

            # finish if we try to goto destination point
            if point == dest:
                break

        self.in_motion = False
        # shake item after scroll to it
        self.shake_item(item)

    def move_to(self, item, destination, animated):
        """
        Move graph to specified position.
        If 'animated' is True then movement will be animated.
        It works with 'canvas.scroll_to' in thread.
        """
        # if animated is True than run thread with animation
        # else - just scroll_to immediately
        if animated and self.show_animation:
            self.thread = Thread(target=self.animation,
                                 args=[item, destination])
            self.thread.start()
        else:
            # correct destination to screen centre
            h_offset = self.hadjustment.get_page_size() / 2
            v_offset = self.vadjustment.get_page_size() / 3

            # apply the scaling factor so the offset is adjusted to the scale
            h_offset = h_offset / self.canvas.get_scale()
            v_offset = v_offset / self.canvas.get_scale()

            destination = (destination[0] - h_offset,
                           destination[1] - v_offset)
            self.scroll_canvas(destination)
            # shake item after scroll to it
            self.shake_item(item)


#-------------------------------------------------------------------------
#
# Popup menu widget
#
#-------------------------------------------------------------------------
class PopupMenu(Gtk.Menu):
    """
    Produce popup widget for right-click menu.
    """
    def __init__(self, graph_widget, kind=None, handle=None):
        """
        graph_widget: GraphWidget
        kind: 'person', 'family', 'background'
        handle: person or family handle
        """
        Gtk.Menu.__init__(self)
        self.set_reserve_toggle_size(False)

        self.graph_widget = graph_widget
        self.view = graph_widget.view
        self.dbstate = graph_widget.dbstate

        self.actions = graph_widget.actions

        if kind == 'background':
            self.background_menu()
        elif kind == 'person' and handle is not None:
            self.person_menu(handle)
        elif kind == 'family' and handle is not None:
            self.family_menu(handle)

    def show_menu(self, event=None):
        """
        Show popup menu.
        """
        if (Gtk.MAJOR_VERSION >= 3) and (Gtk.MINOR_VERSION >= 22):
            # new from gtk 3.22:
            self.popup_at_pointer(event)
        else:
            if event:
                self.popup(None, None, None, None,
                           event.get_button()[1], event.time)
            else:
                self.popup(None, None, None, None,
                           0, Gtk.get_current_event_time())
                #self.popup(None, None, None, None, 0, 0)

    def background_menu(self):
        """
        Popup menu on background.
        """
        menu_item = Gtk.CheckMenuItem(_('Show images'))
        menu_item.set_active(
            self.view._config.get('interface.graphview-show-images'))
        menu_item.connect("activate", self.graph_widget.update_setting,
                          'interface.graphview-show-images')
        menu_item.show()
        self.append(menu_item)

        menu_item = Gtk.CheckMenuItem(_('Highlight the home person'))
        menu_item.set_active(
            self.view._config.get('interface.graphview-highlight-home-person'))
        menu_item.connect("activate", self.graph_widget.update_setting,
                          'interface.graphview-highlight-home-person')
        menu_item.show()
        self.append(menu_item)

        menu_item = Gtk.CheckMenuItem(_('Show full dates'))
        menu_item.set_active(
            self.view._config.get('interface.graphview-show-full-dates'))
        menu_item.connect("activate", self.graph_widget.update_setting,
                          'interface.graphview-show-full-dates')
        menu_item.show()
        self.append(menu_item)

        menu_item = Gtk.CheckMenuItem(_('Show places'))
        menu_item.set_active(
            self.view._config.get('interface.graphview-show-places'))
        menu_item.connect("activate", self.graph_widget.update_setting,
                          'interface.graphview-show-places')
        menu_item.show()
        self.append(menu_item)

        menu_item = Gtk.CheckMenuItem(_('Show tags'))
        menu_item.set_active(
            self.view._config.get('interface.graphview-show-tags'))
        menu_item.connect("activate", self.graph_widget.update_setting,
                          'interface.graphview-show-tags')
        menu_item.show()
        self.append(menu_item)

        self.add_separator()

        menu_item = Gtk.CheckMenuItem(_('Show animation'))
        menu_item.set_active(
            self.view._config.get('interface.graphview-show-animation'))
        menu_item.connect("activate", self.graph_widget.update_setting,
                          'interface.graphview-show-animation')
        menu_item.show()
        self.append(menu_item)

        # add sub menu for line type setting
        menu_item, sub_menu = self.add_submenu(label=_('Lines type'))

        spline = self.view._config.get('interface.graphview-show-lines')

        entry = Gtk.RadioMenuItem(label=_('Direct'))
        entry.connect("activate", self.graph_widget.update_lines_type,
                      0, 'interface.graphview-show-lines')
        if spline == 0:
            entry.set_active(True)
        entry.show()
        sub_menu.append(entry)

        entry = Gtk.RadioMenuItem(label=_('Curves'))
        entry.connect("activate", self.graph_widget.update_lines_type,
                      1, 'interface.graphview-show-lines')
        if spline == 1:
            entry.set_active(True)
        entry.show()
        sub_menu.append(entry)

        entry = Gtk.RadioMenuItem(label=_('Ortho'))
        entry.connect("activate", self.graph_widget.update_lines_type,
                      2, 'interface.graphview-show-lines')
        if spline == 2:
            entry.set_active(True)
        entry.show()
        sub_menu.append(entry)

        # add help menu
        self.add_separator()
        self.append_help_menu_entry()

    def add_tags_to_menu(self, obj, otype, tag_menu):
        """
        Add tags to the Popup menu for person or family node.
        """
        idx = 0
        tags_list = obj.get_tag_list()
        handle = obj.get_handle()
        for tag_handle in self.dbstate.db.get_tag_handles():
            idx += 1
            tag = self.dbstate.db.get_tag_from_handle(tag_handle)
            # prepare the tag
            if tag:
                rgba = Gdk.RGBA()
                rgba.parse(tag.get_color())
                rgba2 = Gdk.RGBA()
                # Calculate the brightness of the background.
                # depending on this value, the text is shown
                # either in white, either in black.
                brightness = (int(rgba.red * 255) * 0.299 +
                              int(rgba.green * 255) * 0.587 +
                              int(rgba.blue * 255) * 0.114)
                foreground = "#000" if brightness > 100 else "#fff"
                rgba2.parse(foreground)
                # We can't use add_menuitem here
                tag_name = tag.get_name()
                item = Gtk.RadioMenuItem(label=tag_name)
                if tag_handle in tags_list:
                    item.set_active(True)
                else:
                    item.set_active(False)
                item.override_background_color(Gtk.StateFlags.NORMAL, rgba)
                item.override_color(Gtk.StateFlags.NORMAL, rgba2)
                item.connect("activate", self.actions.add_tag_to_object,
                             [handle, otype, tag_handle])
                item.show()
                style = tag_menu.get_style_context()
                color = style.get_property("background-color",
                                           Gtk.StateFlags.PRELIGHT)
                color.alpha = 0.2
                item.override_background_color(Gtk.StateFlags.PRELIGHT,
                                               color)
                tag_menu.append(item)

    def person_menu(self, handle):
        """
        Popup menu for person node.
        """
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            add_menuitem(self, _('Edit'),
                         handle, self.actions.edit_person)

            add_menuitem(self, _('Copy'),
                         handle, self.actions.copy_person_to_clipboard)

            add_menuitem(self, _('Delete'),
                         person, self.actions.remove_person)

            self.add_separator()

            # build tag submenu
            item, tag_menu = self.add_submenu(label=_("Tags"))

            add_menuitem(tag_menu, _('Select tags for person'),
                         [handle, 'person'], self.actions.edit_tag_list)

            add_menuitem(tag_menu, _('Organize Tags...'),
                         [handle, 'person'], self.actions.organize_tags)

            self.add_tags_to_menu(person, 'person', tag_menu)

            # go over spouses and build their menu
            item, sp_menu = self.add_submenu(label=_("Spouses"))

            add_menuitem(sp_menu, _('Add new family'),
                         handle, self.actions.add_spouse)
            self.add_separator(sp_menu)

            fam_list = person.get_family_handle_list()
            for fam_id in fam_list:
                family = self.dbstate.db.get_family_from_handle(fam_id)
                if family.get_father_handle() == person.get_handle():
                    sp_id = family.get_mother_handle()
                else:
                    sp_id = family.get_father_handle()
                if not sp_id:
                    continue
                spouse = self.dbstate.db.get_person_from_handle(sp_id)
                if not spouse:
                    continue
                self.add_menuitem(sp_menu, displayer.display(spouse),
                                  self.graph_widget.move_to_person,
                                  sp_id, True)

            # go over siblings and build their menu
            item, sib_menu = self.add_submenu(label=_("Siblings"))

            pfam_list = person.get_parent_family_handle_list()
            siblings = []
            step_siblings = []
            for f_h in pfam_list:
                fam = self.dbstate.db.get_family_from_handle(f_h)
                sib_list = fam.get_child_ref_list()
                for sib_ref in sib_list:
                    sib_id = sib_ref.ref
                    if sib_id == person.get_handle():
                        continue
                    siblings.append(sib_id)
                # collect a list of per-step-family step-siblings
                for parent_h in [fam.get_father_handle(),
                                 fam.get_mother_handle()]:
                    if not parent_h:
                        continue
                    parent = self.dbstate.db.get_person_from_handle(
                        parent_h)
                    other_families = [
                        self.dbstate.db.get_family_from_handle(fam_id)
                        for fam_id in parent.get_family_handle_list()
                        if fam_id not in pfam_list]
                    for step_fam in other_families:
                        fam_stepsiblings = [
                            sib_ref.ref for sib_ref in
                            step_fam.get_child_ref_list()
                            if not sib_ref.ref == person.get_handle()]
                        if fam_stepsiblings:
                            step_siblings.append(fam_stepsiblings)

            # add siblings sub-menu with a bar between each siblings group
            if siblings or step_siblings:
                sibs = [siblings] + step_siblings
                for sib_group in sibs:
                    for sib_id in sib_group:
                        sib = self.dbstate.db.get_person_from_handle(
                            sib_id)
                        if not sib:
                            continue
                        if find_children(self.dbstate.db, sib):
                            label = Gtk.Label(
                                label='<b><i>%s</i></b>'
                                % escape(displayer.display(sib)))
                        else:
                            label = Gtk.Label(
                                label=escape(displayer.display(sib)))
                        sib_item = Gtk.MenuItem()
                        label.set_use_markup(True)
                        label.show()
                        label.set_alignment(0, 0)
                        sib_item.add(label)
                        sib_item.connect("activate",
                                         self.graph_widget.move_to_person,
                                         sib_id, True)
                        sib_item.show()
                        sib_menu.append(sib_item)
                    if sibs.index(sib_group) < len(sibs) - 1:
                        self.add_separator(sib_menu)
            else:
                item.set_sensitive(0)

            self.add_children_submenu(person=person)

            # Go over parents and build their menu
            item, par_menu = self.add_submenu(label=_("Parents"))
            no_parents = True
            par_list = find_parents(self.dbstate.db, person)
            for par_id in par_list:
                if not par_id:
                    continue
                par = self.dbstate.db.get_person_from_handle(par_id)
                if not par:
                    continue

                if no_parents:
                    no_parents = False

                if find_parents(self.dbstate.db, par):
                    label = Gtk.Label(label='<b><i>%s</i></b>'
                                      % escape(displayer.display(par)))
                else:
                    label = Gtk.Label(label=escape(displayer.display(par)))

                par_item = Gtk.MenuItem()
                label.set_use_markup(True)
                label.show()
                label.set_halign(Gtk.Align.START)
                par_item.add(label)
                par_item.connect("activate", self.graph_widget.move_to_person,
                                 par_id, True)
                par_item.show()
                par_menu.append(par_item)

            if no_parents:
                # add button to add parents
                add_menuitem(par_menu, _('Add parents'), handle,
                             self.actions.add_parents_to_person)

            # go over related persons and build their menu
            item, per_menu = self.add_submenu(label=_("Related"))

            no_related = True
            for p_id in find_witnessed_people(self.dbstate.db, person):
                per = self.dbstate.db.get_person_from_handle(p_id)
                if not per:
                    continue

                if no_related:
                    no_related = False

                self.add_menuitem(per_menu, displayer.display(per),
                                  self.graph_widget.move_to_person,
                                  p_id, True)
            if no_related:
                item.set_sensitive(0)

            self.add_separator()

            add_menuitem(self, _('Set as home person'),
                         handle, self.actions.set_home_person)

            add_menuitem(self, _('Show path to home person'),
                         handle, self.actions.path_to_home_person)

            # check if we have person in bookmarks
            marks = self.graph_widget.view.bookmarks.get_bookmarks().bookmarks
            if handle in marks:
                add_menuitem(self, _('Remove from bookmarks'), handle,
                             self.actions.remove_from_bookmarks)
            else:
                add_menuitem(self, _('Add to bookmarks'), [handle, person],
                             self.actions.add_to_bookmarks)

            # QuickReports and WebConnect section
            self.add_separator()
            q_exists = self.add_quickreport_submenu(CATEGORY_QR_PERSON, handle)
            w_exists = self.add_web_connect_submenu(handle)

            if q_exists or w_exists:
                self.add_separator()
            self.append_help_menu_entry()

    def add_quickreport_submenu(self, category, handle):
        """
        Adds Quick Reports menu.
        """
        def make_quick_report_callback(pdata, category, dbstate, uistate,
                                       handle, track=[]):
            return lambda x: run_report(dbstate, uistate, category, handle,
                                        pdata, track=track)

        # select the reports to show
        showlst = []
        pmgr = GuiPluginManager.get_instance()
        for pdata in pmgr.get_reg_quick_reports():
            if pdata.supported and pdata.category == category:
                showlst.append(pdata)

        showlst.sort(key=lambda x: x.name)
        if showlst:
            menu_item, quick_menu = self.add_submenu(_("Quick View"))
            for pdata in showlst:
                callback = make_quick_report_callback(
                    pdata, category, self.view.dbstate, self.view.uistate,
                    handle)
                self.add_menuitem(quick_menu, pdata.name, callback)
            return True
        return False

    def add_web_connect_submenu(self, handle):
        """
        Adds Web Connect menu if some installed.
        """
        def flatten(L):
            """
            Flattens a possibly nested list. Removes None results, too.
            """
            retval = []
            if isinstance(L, (list, tuple)):
                for item in L:
                    fitem = flatten(item)
                    if fitem is not None:
                        retval.extend(fitem)
            elif L is not None:
                retval.append(L)
            return retval

        # select the web connects to show
        pmgr = GuiPluginManager.get_instance()
        plugins = pmgr.process_plugin_data('WebConnect')

        nav_group = self.view.navigation_type()

        try:
            connections = [plug(nav_group) if isinstance(plug, abc.Callable) else
                           plug for plug in plugins]
        except BaseException:
            import traceback
            traceback.print_exc()
            connections = []

        connections = flatten(connections)
        connections.sort(key=lambda plug: plug.name)
        if connections:
            menu_item, web_menu = self.add_submenu(_("Web Connection"))

            for connect in connections:
                callback = connect(self.view.dbstate, self.view.uistate,
                                   nav_group, handle)
                self.add_menuitem(web_menu, connect.name, callback)
            return True
        return False

    def family_menu(self, handle):
        """
        Popup menu for family node.
        """
        family = self.dbstate.db.get_family_from_handle(handle)
        if family:
            add_menuitem(self, _('Edit'),
                         handle, self.actions.edit_family)

            add_menuitem(self, _('Delete'),
                         family, self.actions.remove_family)

            self.add_separator()

            # build tag submenu
            _item, tag_menu = self.add_submenu(label=_("Tags"))

            add_menuitem(tag_menu, _('Select tags for family'),
                         [handle, 'family'], self.actions.edit_tag_list)

            add_menuitem(tag_menu, _('Organize Tags...'),
                         [handle, 'family'], self.actions.organize_tags)

            self.add_tags_to_menu(family, 'family', tag_menu)

            # build spouses menu
            _item, sp_menu = self.add_submenu(label=_("Spouses"))

            f_handle = family.get_father_handle()
            m_handle = family.get_mother_handle()
            if f_handle:
                spouse = self.dbstate.db.get_person_from_handle(f_handle)
                self.add_menuitem(sp_menu, displayer.display(spouse),
                                  self.graph_widget.move_to_person,
                                  f_handle, True)
            else:
                add_menuitem(sp_menu, _('Add father'), [family, 'father'],
                             self.actions.add_spouse_to_family)

            if m_handle:
                spouse = self.dbstate.db.get_person_from_handle(m_handle)
                self.add_menuitem(sp_menu, displayer.display(spouse),
                                  self.graph_widget.move_to_person,
                                  m_handle, True)
            else:
                add_menuitem(sp_menu, _('Add mother'), [family, 'mother'],
                             self.actions.add_spouse_to_family)

            self.add_children_submenu(family=family)

            # QuickReports section
            self.add_separator()
            q_exists = self.add_quickreport_submenu(CATEGORY_QR_FAMILY, handle)

            if q_exists:
                self.add_separator()
            self.append_help_menu_entry()

    def add_children_submenu(self, person=None, family=None):
        """
        Go over children and build their menu.
        """
        item, child_menu = self.add_submenu(_("Children"))

        no_child = True

        childlist = []
        if family:
            for child_ref in family.get_child_ref_list():
                childlist.append(child_ref.ref)
            # allow to add a child to this family
            add_menuitem(child_menu, _('Add child to family'),
                         family.get_handle(), self.actions.add_child_to_family)
            self.add_separator(child_menu)
            no_child = False
        elif person:
            childlist = find_children(self.dbstate.db, person)

        for child_handle in childlist:
            child = self.dbstate.db.get_person_from_handle(child_handle)
            if not child:
                continue

            if no_child:
                no_child = False

            if find_children(self.dbstate.db, child):
                label = Gtk.Label(label='<b><i>%s</i></b>'
                                  % escape(displayer.display(child)))
            else:
                label = Gtk.Label(label=escape(displayer.display(child)))

            child_item = Gtk.MenuItem()
            label.set_use_markup(True)
            label.show()
            label.set_halign(Gtk.Align.START)
            child_item.add(label)
            child_item.connect("activate", self.graph_widget.move_to_person,
                               child_handle, True)
            child_item.show()
            child_menu.append(child_item)

        if no_child:
            item.set_sensitive(0)

    def add_menuitem(self, menu, label, func, *args):
        """
        Adds menu item.
        """
        item = Gtk.MenuItem(label=label)
        item.connect("activate", func, *args)

        item.show()
        menu.append(item)
        return item

    def add_submenu(self, label):
        """
        Adds submenu.
        """
        item = Gtk.MenuItem(label=label)
        item.set_submenu(Gtk.Menu())
        item.show()
        self.append(item)
        submenu = item.get_submenu()
        submenu.set_reserve_toggle_size(False)
        return item, submenu

    def add_separator(self, menu=None):
        """
        Adds separator to menu.
        """
        if menu is None:
            menu = self
        menu_item = Gtk.SeparatorMenuItem()
        menu_item.show()
        menu.append(menu_item)

    def append_help_menu_entry(self):
        """
        Adds help (about) menu entry.
        """
        item = Gtk.MenuItem(label=_("About Graph View"))
        item.connect("activate", self.actions.on_help_clicked)
        item.show()
        self.append(item)


class Actions(Callback):
    """
    Define actions.
    """

    __signals__ = {
        'focus-person-changed' : (str, ),
        'active-changed' : (str, ),
        'rebuild-graph' :  None,
        'path-to-home-person' : (str, bool),
        }

    def __init__(self, dbstate, uistate, bookmarks):
        """
        bookmarks - person bookmarks from GraphView(NavigationView).
        """
        Callback.__init__(self)
        self.dbstate = dbstate
        self.uistate = uistate

        self.bookmarks = bookmarks

    def on_help_clicked(self, widget):
        """
        Display the relevant portion of Gramps manual.
        """
        display_url(WIKI_PAGE)

    def add_spouse(self, obj):
        """
        Add spouse to person (create new family to person).
        See: gramps/plugins/view/relview.py (add_spouse)
        """
        handle = obj.get_data()
        family = Family()
        person = self.dbstate.db.get_person_from_handle(handle)

        if not person:
            return

        if person.gender == Person.MALE:
            family.set_father_handle(person.handle)
        else:
            family.set_mother_handle(person.handle)

        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass
        # set edited person to scroll on it after rebuilding graph
        self.emit('focus-person-changed', (handle, ))

    def add_spouse_to_family(self, obj):
        """
        Adds spouse to existing family.
        See: editfamily.py
        """
        family, kind = obj.get_data()

        try:
            dialog = EditFamily(self.dbstate, self.uistate, [], family)
            if kind == 'mother':
                dialog.add_mother_clicked(None)
            if kind == 'father':
                dialog.add_father_clicked(None)
        except WindowActiveError:
            pass

    def edit_person(self, obj, person_handle=None):
        """
        Start a person editor for the selected person.
        """
        if not (obj or person_handle):
            return False

        if person_handle:
            handle = person_handle
        else:
            handle = obj.get_data()

        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass
        # set edited person to scroll on it after rebuilding graph
        self.emit('focus-person-changed', (handle, ))

    def set_home_person(self, obj):
        """
        Set the home person for database and make it active.
        """
        handle = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            self.dbstate.db.set_default_person_handle(handle)
            self.emit('active-changed', (handle, ))

    def path_to_home_person(self, obj):
        """
        Draw the relationship between the active and home people
        """
        handle = obj.get_data()
        self.emit('path-to-home-person', (handle, True))

    def edit_family(self, obj, family_handle=None):
        """
        Start a family editor for the selected family.
        """
        if not (obj or family_handle):
            return False

        if family_handle:
            handle = family_handle
        else:
            handle = obj.get_data()

        family = self.dbstate.db.get_family_from_handle(handle)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

        # set edited family person to scroll on it after rebuilding graph
        f_handle = family.get_father_handle()
        if f_handle:
            self.emit('focus-person-changed', (f_handle, ))
        else:
            m_handle = family.get_mother_handle()
            if m_handle:
                self.emit('focus-person-changed', (m_handle, ))

    def copy_person_to_clipboard(self, obj):
        """
        Renders the person data into some lines of text
        and puts that into the clipboard.
        """
        person_handle = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            _cb = Gtk.Clipboard.get_for_display(Gdk.Display.get_default(),
                                                Gdk.SELECTION_CLIPBOARD)
            format_helper = FormattingHelper(self.dbstate)
            _cb.set_text(format_helper.format_person(person, 11), -1)
            return True
        return False

    def edit_tag_list(self, obj):
        """
        Edit tag list for person or family.
        """
        handle, otype = obj.get_data()
        if otype == 'person':
            target = self.dbstate.db.get_person_from_handle(handle)
            self.emit('focus-person-changed', (handle, ))
        elif otype == 'family':
            target = self.dbstate.db.get_family_from_handle(handle)
            f_handle = target.get_father_handle()
            if f_handle:
                self.emit('focus-person-changed', (f_handle, ))
            else:
                m_handle = target.get_mother_handle()
                if m_handle:
                    self.emit('focus-person-changed', (m_handle, ))
        else:
            return False

        if target:
            tag_list = []
            for tag_handle in target.get_tag_list():
                tag = self.dbstate.db.get_tag_from_handle(tag_handle)
                if tag:
                    tag_list.append((tag_handle, tag.get_name()))

            all_tags = []
            for tag_handle in self.dbstate.db.get_tag_handles(
                    sort_handles=True):
                tag = self.dbstate.db.get_tag_from_handle(tag_handle)
                all_tags.append((tag.get_handle(), tag.get_name()))

            try:
                editor = EditTagList(tag_list, all_tags, self.uistate, [])
                if editor.return_list is not None:
                    tag_list = editor.return_list
                    # Save tags to target object.
                    # Make the dialog modal so that the user can't start
                    # another database transaction while the one setting
                    # tags is still running.
                    pmon = progressdlg.ProgressMonitor(
                        progressdlg.GtkProgressDialog,
                        ("", self.uistate.window, Gtk.DialogFlags.MODAL),
                        popup_time=2)
                    status = progressdlg.LongOpStatus(msg=_("Adding Tags"),
                                                      total_steps=1,
                                                      interval=1 // 20)
                    pmon.add_op(status)
                    target.set_tag_list([item[0] for item in tag_list])
                    if otype == 'person':
                        msg = _('Adding Tags to person (%s)') % handle
                        with DbTxn(msg, self.dbstate.db) as trans:
                            self.dbstate.db.commit_person(target, trans)
                            status.heartbeat()
                    else:
                        msg = _('Adding Tags to family (%s)') % handle
                        with DbTxn(msg, self.dbstate.db) as trans:
                            self.dbstate.db.commit_family(target, trans)
                            status.heartbeat()
                    status.end()
            except WindowActiveError:
                pass

    def organize_tags(self, obj):
        """
        Display the Organize Tags dialog.
        see: .gramps.gui.view.tags
        """
        handle, otype = obj.get_data()
        if otype == 'person':
            target = self.dbstate.db.get_person_from_handle(handle)
            self.emit('focus-person-changed', (handle, ))
        elif otype == 'family':
            target = self.dbstate.db.get_family_from_handle(handle)
            f_handle = target.get_father_handle()
            if f_handle:
                self.emit('focus-person-changed', (f_handle, ))
            else:
                m_handle = target.get_mother_handle()
                if m_handle:
                    self.emit('focus-person-changed', (m_handle, ))

        OrganizeTagsDialog(self.dbstate.db, self.uistate, [])
        self.emit('rebuild-graph')

    def add_tag_to_object(self, obj, data):
        handle, otype, tag_hdle = data
        if otype == 'person':
            target = self.dbstate.db.get_person_from_handle(handle)
            old_tags = target.get_tag_list()
            if tag_hdle in old_tags:
                old_tags.remove(tag_hdle)
            else:
                old_tags.append(tag_hdle)
            target.set_tag_list(old_tags)
            self.emit('focus-person-changed', (handle, ))
            msg = _('Adding Tags to person (%s)') % handle
            with DbTxn(msg, self.dbstate.db) as trans:
                self.dbstate.db.commit_person(target, trans)
        if otype == 'family':
            target = self.dbstate.db.get_family_from_handle(handle)
            old_tags = target.get_tag_list()
            if tag_hdle in old_tags:
                old_tags.remove(tag_hdle)
            else:
                old_tags.append(tag_hdle)
            target.set_tag_list(old_tags)
            msg = _('Adding Tags to family (%s)') % handle
            with DbTxn(msg, self.dbstate.db) as trans:
                self.dbstate.db.commit_family(target, trans)
            self.emit('rebuild-graph')

    def add_parents_to_person(self, obj):
        """
        Open dialog to add parents to person.
        """
        person_handle = obj.get_data()

        family = Family()
        childref = ChildRef()
        childref.set_reference_handle(person_handle)
        family.add_child_ref(childref)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            return
        # set edited person to scroll on it after rebuilding graph
        self.emit('focus-person-changed', (person_handle, ))

    def add_child_to_family(self, obj):
        """
        Open person editor to create and add child to family.
        """
        family_handle = obj.get_data()
        callback = lambda x: self.__callback_add_child(x, family_handle)
        person = Person()
        name = Name()
        # the editor requires a surname
        name.add_surname(Surname())
        name.set_primary_surname(0)
        family = self.dbstate.db.get_family_from_handle(family_handle)
        # try to get father
        father_handle = family.get_father_handle()
        if father_handle:
            father = self.dbstate.db.get_person_from_handle(father_handle)
            if father:
                preset_name(father, name)

        person.set_primary_name(name)
        try:
            EditPerson(self.dbstate, self.uistate, [], person,
                       callback=callback)
        except WindowActiveError:
            pass

    def __callback_add_child(self, person, family_handle):
        """
        Write data to db.
        Callback from self.add_child_to_family().
        """
        ref = ChildRef()
        ref.ref = person.get_handle()
        family = self.dbstate.db.get_family_from_handle(family_handle)
        family.add_child_ref(ref)

        with DbTxn(_("Add Child to Family"), self.dbstate.db) as trans:
            # add parentref to child
            person.add_parent_family_handle(family_handle)
            # default relationship is used
            self.dbstate.db.commit_person(person, trans)
            # add child to family
            self.dbstate.db.commit_family(family, trans)

    def remove_person(self, obj):
        """
        Remove a person from the database.
        see: libpersonview.py
        """
        person = obj.get_data()

        msg1 = _('Delete %s?') % displayer.display(person)
        msg2 = (_('Deleting the person [%s] will remove it '
                  'from the database.') % person.gramps_id)
        dialog = QuestionDialog2(msg1, msg2,
                                 _("Yes"), _("No"),
                                 self.uistate.window)
        if dialog.run():
            # set the busy cursor, so the user knows that we are working
            self.uistate.set_busy_cursor(True)

            # create the transaction
            with DbTxn('', self.dbstate.db) as trans:
                # create description to save
                description = (_("Delete Person (%s)")
                               % displayer.display(person))

                # delete the person from the database
                # Above will emit person-delete signal
                self.dbstate.db.delete_person_from_database(person, trans)
                trans.set_description(description)

            self.uistate.set_busy_cursor(False)

    def remove_family(self, obj):
        """
        Remove a family from the database.
        see: familyview.py
        """
        family = obj.get_data()

        msg1 = _('Delete family [%s]?') % family.gramps_id
        msg2 = _('Deleting the family will remove it from the database.')
        dialog = QuestionDialog2(msg1, msg2,
                                 _("Yes"), _("No"),
                                 self.uistate.window)
        if dialog.run():
            # set the busy cursor, so the user knows that we are working
            self.uistate.set_busy_cursor(True)

            # create the transaction
            with DbTxn('', self.dbstate.db) as trans:
                # create description to save
                description = _("Delete Family [%s]") % family.gramps_id

                # delete the family from the database
                self.dbstate.db.remove_family_relationships(family.handle,
                                                            trans)
                trans.set_description(description)

            self.uistate.set_busy_cursor(False)

    def add_to_bookmarks(self, obj):
        """
        Adds bookmark for person.
        See: navigationview.py and bookmarks.py
        """
        handle, person = obj.get_data()

        self.bookmarks.add(handle)
        name = displayer.display(person)
        self.uistate.push_message(self.dbstate,
                                  _("%s has been bookmarked") % name)

    def remove_from_bookmarks(self, obj):
        """
        Remove person from the list of bookmarked people.
        See: bookmarks.py
        """
        handle = obj.get_data()
        self.bookmarks.remove_handles([handle])
