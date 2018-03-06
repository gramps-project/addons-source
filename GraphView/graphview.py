# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010-2012  Gary Burton
#                          GraphvizSvgParser is based on the Gramps XML import
#                          DotGenerator is based on the relationship graph
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import os
from xml.parsers.expat import ParserCreate
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
import string
from subprocess import Popen, PIPE
from io import StringIO
from threading import Thread
from math import sqrt, pow

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.db import DbTxn
import gramps.gen.lib
from gramps.gui.views.navigationview import NavigationView
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gen.display.name import displayer
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.utils.thumbnails import get_thumbnail_path
from gramps.gen.utils.file import search_for, media_path_full, find_file
from gramps.gui.editors import EditPerson, EditFamily, EditTagList
from gramps.gen.errors import WindowActiveError
import gramps.gen.datehandler
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.constfunc import win
from gramps.gen.config import config
from gramps.gui.dialog import OptionDialog, ErrorDialog
from gramps.gui.utils import color_graph_box, color_graph_family, rgb_to_hex
from gramps.gen.lib import Person, Family
from gramps.gui.widgets.menuitem import add_menuitem
import gramps.gui.widgets.progressdialog as progressdlg

if win():
    DETACHED_PROCESS = 8

try:
    import cairo
except ImportError:
    raise Exception("Cairo (http://www.cairographics.org) is required "
                    "for this view to work")
try:
    import gi
    gi.require_version('GooCanvas', '2.0')
    from gi.repository import GooCanvas
except ImportError:
    raise Exception("Goocanvas 2 (http://live.gnome.org/GooCanvas) is "
                    "required for this view to work")

if os.sys.platform == "win32":
    _DOT_FOUND = search_for("dot.exe")
else:
    _DOT_FOUND = search_for("dot")

if not _DOT_FOUND:
    raise Exception("GraphViz (http://www.graphviz.org) is "
                    "required for this view to work")

SPLINE = {0: 'false', 1: 'true', 2: 'ortho'}

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
        ('interface.graphview-show-full-dates', False),
        ('interface.graphview-show-places', False),
        ('interface.graphview-show-lines', 1),
        ('interface.graphview-show-tags', False),
        ('interface.graphview-highlight-home-person', True),
        ('interface.graphview-home-path-color', '#000000'),
        ('interface.graphview-descendant-generations', 10),
        ('interface.graphview-ancestor-generations', 3),
        ('interface.graphview-show-animation', True),
        ('interface.graphview-animation-speed', 3),
        ('interface.graphview-animation-count', 4),
        )

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

        self.additional_uis.append(self.additional_ui())
        self.define_print_actions()

    def define_print_actions(self):
        """
        Associate the print button to the PrintView action.
        """
        self._add_action('PrintView', 'document-print', _("_Print..."),
                         accel="<PRIMARY>P",
                         tip=_("Save the dot file for a later print.\n"
                               "This will save a .gv file and a svg file.\n"
                               "You must select a .gv file"),
                         callback=self.printview)

    def _connect_db_signals(self):
        """
        Set up callbacks for changes to person and family nodes.
        """
        self.callman.add_db_signal('person-update', self.goto_handle)
        self.callman.add_db_signal('family-update', self.goto_handle)
        self.callman.add_db_signal('event-update', self.goto_handle)

    def change_db(self, db):
        """
        Set up callback for changes to the database.
        """
        self._change_db(db)
        self.scale = 1
        if self.active:
            self.graph_widget.clear()
            if self.get_active() != "":
                self.graph_widget.populate(self.get_active())
        else:
            self.dirty = True
        # update combobox with bookmarks on db changes
        self.graph_widget.load_bookmarks()

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
        Builds the canvas along with a zoom control.
        """
        self.graph_widget = GraphWidget(self, self.dbstate, self.uistate)
        self.graph_widget.load_bookmarks()
        return self.graph_widget.get_widget()

    def build_tree(self):
        """
        There is no separate step to fill the widget with data.
        The data is populated as part of canvas widget construction.
        """
        pass

    def additional_ui(self):
        """
        Specifies the UIManager XML code that defines the menus and buttons
        associated with the interface.
        """
        return '''<ui>
          <menubar name="MenuBar">
            <menu action="GoMenu">
              <placeholder name="CommonGo">
                <menuitem action="Back"/>
                <menuitem action="Forward"/>
                <separator/>
                <menuitem action="HomePerson"/>
                <separator/>
              </placeholder>
            </menu>
            <menu action="EditMenu">
              <placeholder name="CommonEdit">
                <menuitem action="PrintView"/>
              </placeholder>
            </menu>
          </menubar>
          <toolbar name="ToolBar">
            <placeholder name="CommonNavigation">
              <toolitem action="Back"/>
              <toolitem action="Forward"/>
              <toolitem action="HomePerson"/>
            </placeholder>
            <placeholder name="CommonEdit">
              <toolitem action="PrintView"/>
            </placeholder>
          </toolbar>
        </ui>'''

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
                self.graph_widget.clear()
                self.graph_widget.populate(self.get_active())
                self.graph_widget.load_bookmarks()
        else:
            self.dirty = True

    def can_configure(self):
        """
        See :class:`~gui.views.pageview.PageView
        :return: bool
        """
        return True

    def cb_update_show_images(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the images setting.
        """
        if entry == 'True':
            self.show_images = True
        else:
            self.show_images = False
        self.graph_widget.populate(self.get_active())

    def cb_update_show_full_dates(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the date setting.
        """
        if entry == 'True':
            self.show_full_dates = True
        else:
            self.show_full_dates = False
        self.graph_widget.populate(self.get_active())

    def cb_update_show_places(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the place setting.
        """
        if entry == 'True':
            self.show_places = True
        else:
            self.show_places = False
        self.graph_widget.populate(self.get_active())

    def cb_update_show_tag_color(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the show tags setting.
        """
        if entry == 'True':
            self.show_tag_color = True
        else:
            self.show_tag_color = False
        self.graph_widget.populate(self.get_active())

    def cb_update_show_lines(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the line setting.
        """
        self.graph_widget.populate(self.get_active())

    def cb_update_highlight_home_person(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the highlight home
        person setting.
        """
        if entry == 'True':
            self.highlight_home_person = True
        else:
            self.highlight_home_person = False
        self.graph_widget.populate(self.get_active())

    def cb_update_home_path_color(self, client, cnxn_id, entry, data):
        """
        Called when the configuration menu changes the path person color.
        """
        self.home_path_color = entry
        self.graph_widget.populate(self.get_active())

    def cb_update_descendant_generations(self, client, cnxd_id, entry, data):
        """
        Called when the configuration menu changes the descendant generation
        count setting.
        """
        self.descendant_generations = entry
        self.graph_widget.populate(self.get_active())

    def cb_update_ancestor_generations(self, client, cnxd_id, entry, data):
        """
        Called when the configuration menu changes the ancestor generation
        count setting.
        """
        self.ancestor_generations = entry
        self.graph_widget.populate(self.get_active())

    def cb_update_show_animation(self, client, cnxd_id, entry, data):
        """
        Called when the configuration menu changes the show animation
        setting.
        """
        if entry == 'True':
            self.graph_widget.animation.show_animation = True
        else:
            self.graph_widget.animation.show_animation = False

    def cb_update_animation_count(self, client, cnxd_id, entry, data):
        """
        Called when the configuration menu changes the animation count
        setting.
        """
        self.graph_widget.animation.max_count = int(entry)*2

    def cb_update_animation_speed(self, client, cnxd_id, entry, data):
        """
        Called when the configuration menu changes the animation speed
        setting.
        """
        self.graph_widget.animation.speed = 50*int(entry)

    def config_connect(self):
        """
        Overwriten from  :class:`~gui.views.pageview.PageView method
        This method will be called after the ini file is initialized,
        use it to monitor changes in the ini file.
        """
        self._config.connect('interface.graphview-show-images',
                             self.cb_update_show_images)
        self._config.connect('interface.graphview-show-full-dates',
                             self.cb_update_show_full_dates)
        self._config.connect('interface.graphview-show-places',
                             self.cb_update_show_places)
        self._config.connect('interface.graphview-show-tags',
                             self.cb_update_show_tag_color)
        self._config.connect('interface.graphview-show-lines',
                             self.cb_update_show_lines)
        self._config.connect('interface.graphview-highlight-home-person',
                             self.cb_update_highlight_home_person)
        self._config.connect('interface.graphview-home-path-color',
                             self.cb_update_home_path_color)
        self._config.connect('interface.graphview-descendant-generations',
                             self.cb_update_descendant_generations)
        self._config.connect('interface.graphview-ancestor-generations',
                             self.cb_update_ancestor_generations)
        self._config.connect('interface.graphview-show-animation',
                             self.cb_update_show_animation)
        self._config.connect('interface.graphview-animation-speed',
                             self.cb_update_animation_speed)
        self._config.connect('interface.graphview-animation-count',
                             self.cb_update_animation_count)

    def _get_configure_page_funcs(self):
        """
        Return a list of functions that create gtk elements to use in the
        notebook pages of the Configure dialog.

        :return: list of functions
        """
        return [self.layout_config_panel,
                self.color_config_panel,
                self.animation_config_panel]

    def layout_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        configdialog.add_checkbox(grid,
                            _('Show images'),
                            0, 'interface.graphview-show-images')
        configdialog.add_checkbox(grid,
                            _('Highlight the home person'),
                            1, 'interface.graphview-highlight-home-person')
        configdialog.add_checkbox(grid,
                            _('Show full dates'),
                            2, 'interface.graphview-show-full-dates')
        configdialog.add_checkbox(grid,
                            _('Show places'),
                            3, 'interface.graphview-show-places')
        configdialog.add_checkbox(grid,
                            _('Show tags'),
                            4, 'interface.graphview-show-tags')

        return _('Layout'), grid

    def color_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        configdialog.add_color(grid,
                               _('Path color'),
                               0, 'interface.graphview-home-path-color')

        return _('Colors'), grid

    def animation_config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        configdialog.add_checkbox(grid,
                            _('Show animation'),
                            0, 'interface.graphview-show-animation')
        configdialog.add_spinner(grid,
                            _('Animation speed (1..5 and 5 is the slower)'),
                            1, 'interface.graphview-animation-speed', (1, 5))
        configdialog.add_spinner(grid,
                            _('Animation count (1..8)'),
                            2, 'interface.graphview-animation-count', (1, 8))

        return _('Animation'), grid

    #-------------------------------------------------------------------------
    #
    # Printing functionalities
    #
    #-------------------------------------------------------------------------
    def printview(self, obj):
        """
        Save the dot file for a later printing with an appropriate tool.
        """
        # ask for the dot file name
        filter1 = Gtk.FileFilter()
        filter1.set_name("dot files")
        filter1.add_pattern("*.gv")
        dot = Gtk.FileChooserDialog(
                                _("Select a dot file name"),
                                action=Gtk.FileChooserAction.SAVE,
                                buttons=(_('_Cancel'), Gtk.ResponseType.CANCEL,
                                         _('_Apply'), Gtk.ResponseType.OK),
                                parent=self.uistate.window)
        mpath = config.get('paths.report-directory')
        dot.set_current_folder(os.path.dirname(mpath))
        dot.set_filter(filter1)
        dot.set_current_name("Graphview.gv")

        status = dot.run()
        if status == Gtk.ResponseType.OK:
            val = dot.get_filename()
            (spath, ext) = os.path.splitext(val)
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
                with open(val, 'wb') as g,\
                     open(svg, 'wb') as s:
                        g.write(self.graph_widget.dot_data)
                        s.write(self.graph_widget.svg_data)
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
    Define the canvas that displays the graph along with a zoom control.
    """
    def __init__(self, view, dbstate, uistate):
        # variables for drag and scroll
        self._last_x = 0
        self._last_y = 0
        self._in_move = False
        self.view = view
        self.dbstate = dbstate
        self.uistate = uistate
        self.active_person_handle = None

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

        self.vbox = Gtk.Box(False, 4, orientation=Gtk.Orientation.VERTICAL)
        self.vbox.set_border_width(4)
        hbox = Gtk.Box(False, 4, orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox.pack_start(hbox, False, False, 0)

        # add zoom-in button
        self.zoom_in_btn = Gtk.Button.new_from_icon_name('zoom-in',
                                                         Gtk.IconSize.MENU)
        self.zoom_in_btn.set_tooltip_text(_('Zoom in'))
        hbox.pack_start(self.zoom_in_btn, False, False, 1)
        self.zoom_in_btn.connect("clicked", self.zoom_in)

        # add zoom-out button
        self.zoom_out_btn = Gtk.Button.new_from_icon_name('zoom-out',
                                                          Gtk.IconSize.MENU)
        self.zoom_out_btn.set_tooltip_text(_('Zoom out'))
        hbox.pack_start(self.zoom_out_btn, False, False, 1)
        self.zoom_out_btn.connect("clicked", self.zoom_out)

        # add original zoom button
        self.orig_zoom_btn = Gtk.Button.new_from_icon_name('zoom-original',
                                                           Gtk.IconSize.MENU)
        self.orig_zoom_btn.set_tooltip_text(_('Zoom to original'))
        hbox.pack_start(self.orig_zoom_btn, False, False, 1)
        self.orig_zoom_btn.connect("clicked", self.set_original_zoom)

        # add best fit button
        self.fit_btn = Gtk.Button.new_from_icon_name('zoom-fit-best',
                                                     Gtk.IconSize.MENU)
        self.fit_btn.set_tooltip_text(_('Zoom to best fit'))
        hbox.pack_start(self.fit_btn, False, False, 1)
        self.fit_btn.connect("clicked", self.fit_to_page)

        # add 'go to active person' button
        self.goto_active_btn = Gtk.Button.new_from_icon_name('go-jump',
                                                             Gtk.IconSize.MENU)
        self.goto_active_btn.set_tooltip_text(_('Go to active person'))
        hbox.pack_start(self.goto_active_btn, False, False, 1)
        self.goto_active_btn.connect("clicked", self.goto_active)

        # add 'go to bookmark' combobox
        self.store = Gtk.ListStore(str, str)
        self.goto_other_btn = Gtk.ComboBox(model=self.store)
        cell = Gtk.CellRendererText()
        self.goto_other_btn.pack_start(cell, True)
        self.goto_other_btn.add_attribute(cell, 'text', 1)
        self.goto_other_btn.set_tooltip_text(_('Go to bookmark'))
        self.goto_other_btn.connect("changed", self.goto_other)
        hbox.pack_start(self.goto_other_btn, False, False, 1)

        # add spinners for quick generations change
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(Gtk.Label('↑'), False, False, 1)
        self.ancestors_spinner = Gtk.SpinButton.new_with_range(0, 50, 1)
        self.ancestors_spinner.set_tooltip_text(_('Ancestor generations'))
        self.ancestors_spinner.set_value(
             self.view._config.get('interface.graphview-ancestor-generations'))
        self.ancestors_spinner.connect("value-changed",
                                       self.set_ancestors_generations)
        box.pack_start(self.ancestors_spinner, False, False, 1)

        box.pack_start(Gtk.Label('↓'), False, False, 1)
        self.descendants_spinner = Gtk.SpinButton.new_with_range(1, 50, 1)
        self.descendants_spinner.set_tooltip_text(_('Descendant generations'))
        self.descendants_spinner.set_value(
           self.view._config.get('interface.graphview-descendant-generations'))
        self.descendants_spinner.connect("value-changed",
                                         self.set_descendants_generations)
        box.pack_start(self.descendants_spinner, False, False, 1)
        hbox.pack_start(box, False, False, 1)

        self.vbox.pack_start(scrolled_win, True, True, 0)
        # if we have graph lager than graphviz paper size
        # this coef is needed
        self.transform_scale = 1
        self.scale = 1

        self.animation = CanvasAnimation(self.view, self.canvas, scrolled_win)

        # person that will focus (once) after graph rebuilding
        self.person_to_focus = None

    def set_ancestors_generations(self, widget):
        """
        Set count of ancestors generations to show.
        """
        value = int(widget.get_value())
        self.view._config.set('interface.graphview-ancestor-generations',
                              value)

    def set_descendants_generations(self, widget):
        """
        Set count of descendants generations to show.
        """
        value = int(widget.get_value())
        self.view._config.set('interface.graphview-descendant-generations',
                              value)

    def load_bookmarks(self):
        """
        Load bookmarks in ComboBox (goto_other_btn).
        """
        bookmarks = self.dbstate.db.get_bookmarks().bookmarks
        self.store.clear()
        for bkmark in bookmarks:
            person = self.dbstate.db.get_person_from_handle(bkmark)
            if person:
                name = displayer.display_name(person.get_primary_name())
                val_to_display = "[%s] %s" % (person.gramps_id, name)
                present = self.animation.get_item_by_title(bkmark)
                if present is not None:
                    self.store.append((bkmark, val_to_display))
        self.goto_other_btn.set_active(-1)

    def goto_active(self, button=None):
        """
        Go to active person.
        """
        # check if animation is needed
        if button:
            animation = True
        else:
            animation = False

        self.animation.move_to_person(self.active_person_handle, animation)

    def goto_other(self, obj):
        """
        Go to other person.
        If person not present in the current graphview tree, ignore it.
        """
        if obj.get_active() > -1:
            other = self.store[obj.get_active()][0]
            self.animation.move_to_person(other, True)
            obj.set_active(-1)

    def scroll_mouse(self, canvas, event):
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

    def populate(self, active_person):
        """
        Populate the graph with widgets derived from Graphviz.
        """
        dot = DotGenerator(self.dbstate, self.view)
        self.active_person_handle = active_person
        dot.build_graph(active_person)

        # build the rest of the widget by parsing SVG data from Graphviz
        self.dot_data = dot.get_dot().encode('utf8')
        if win():
            self.svg_data = Popen(['dot', '-Tsvg'],
                               creationflags=DETACHED_PROCESS,
                               stdin=PIPE,
                               stdout=PIPE,
                               stderr=PIPE).communicate(input=self.dot_data)[0]
        else:
            self.svg_data = Popen(['dot', '-Tsvg'],
                               stdin=PIPE,
                               stdout=PIPE).communicate(input=self.dot_data)[0]

        parser = GraphvizSvgParser(self, self.view)
        parser.parse(self.svg_data)

        # save transform scale
        self.transform_scale = parser.transform_scale
        self.set_zoom(self.scale)

        self.animation.update_items(parser.items_list)

        if self.person_to_focus:
            if not self.animation.move_to_person(self.person_to_focus, False):
                self.goto_active()
            self.person_to_focus = None
        else:
            # scroll to active person without animation
            self.goto_active()

        # update the status bar
        self.view.change_page()

    def zoom_in(self, button=None):
        """
        Increase zoom scale.
        """
        scale_coef = self.scale
        if scale_coef < 0.1:
            step = 0.01
        elif scale_coef < 0.3:
            step = 0.03
        elif scale_coef < 1:
            step = 0.05
        elif scale_coef > 2:
            step = 0.5
        else:
            step = 0.1

        scale_coef += step
        self.set_zoom(scale_coef)

    def zoom_out(self, button=None):
        """
        Decrease zoom scale.
        """
        scale_coef = self.scale
        if scale_coef < 0.1:
            step = 0.01
        elif scale_coef < 0.3:
            step = 0.03
        elif scale_coef < 1:
            step = 0.05
        elif scale_coef > 2:
            step = 0.5
        else:
            step = 0.1

        scale_coef -= step
        if scale_coef < 0.02:
            scale_coef = 0.01
        self.set_zoom(scale_coef)

    def set_original_zoom(self, button):
        """
        Set original zoom scale = 1.
        """
        self.set_zoom(1)

    def fit_to_page(self, button):
        """
        Calculate scale and fit tree to page.
        """
        # get the canvas size
        bounds = self.canvas.get_root_item().get_bounds()
        height_canvas = bounds.y2 - bounds.y1
        width_canvas  = bounds.x2 - bounds.x1

        # get scroll window size
        width  = self.hadjustment.get_page_size()
        height = self.vadjustment.get_page_size()

        # prevent division by zero
        if height_canvas == 0: height_canvas = 1
        if width_canvas  == 0: width_canvas  = 1

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
        self.canvas.set_root_item(GooCanvas.CanvasGroup())

    def get_widget(self):
        """
        Return the graph display widget that includes the drawing canvas.
        """
        return self.vbox

    def button_press(self, item, target, event):
        """
        Enter in scroll mode when left or middle mouse button pressed
        on background.
        """
        if not (event.type == getattr(Gdk.EventType, "BUTTON_PRESS")
                and item == self.canvas.get_root_item()):
                    return False

        button = event.get_button()[1]
        if button == 1 or button == 2:
            window = self.canvas.get_parent().get_window()
            window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.FLEUR))
            self._last_x = event.x_root
            self._last_y = event.y_root
            self._in_move = True
            self.animation.stop_animation()
            return False

        if button == 3:
            self.background_menu(event)
            return True

        return False

    def button_release(self, item, target, event):
        """
        Exit from scroll mode when button release.
        """
        button = event.get_button()[1]
        if (button == 1 or button == 2) \
           and event.type == getattr(Gdk.EventType, "BUTTON_RELEASE"):

                self.motion_notify_event(item, target, event)
                self.canvas.get_parent().get_window().set_cursor(None)
                self._in_move = False
                return True
        return False

    def motion_notify_event(self, item, target, event):
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
        return False

    def set_zoom(self, value):
        """
        Set value for zoom of the canvas widget and apply it.
        """
        self.scale = value
        self.canvas.set_scale(value / self.transform_scale)

    def select_node(self, item, target, event):
        """
        Perform actions when a node is clicked.
        If middle mouse was clicked then try to set scroll mode.
        """
        handle = item.title
        node_class = item.description
        button = event.get_button()[1]

        self.person_to_focus = None

        if event.type != getattr(Gdk.EventType, "BUTTON_PRESS"):
            return False

        if button == 1 and node_class == 'node':            # left mouse
            if handle == self.active_person_handle:
                # Find a parent of the active person so that they can become
                # the active person, if no parents then leave as the current
                # active person
                parent_handle = self.find_a_parent(handle)
                if parent_handle:
                    handle = parent_handle

            # redraw the graph based on the selected person
            self.view.change_active(handle)

        elif button == 3 and node_class:                    # right mouse
            self.node_menu(node_class, handle, event)

        elif button == 2:                                   # middle mouse
            # to enter in scroll mode (we should change "item")
            item = self.canvas.get_root_item()
            self.button_press(item, target, event)

        return True

    def background_menu(self, event):
        """
        Popup menu on background.
        """
        self.menu = Gtk.Menu()
        self.menu.set_reserve_toggle_size(False)

        menu_item = Gtk.MenuItem(_('Lines type'))
        menu_item.set_submenu(Gtk.Menu())
        sub_menu = menu_item.get_submenu()

        spline = self.view._config.get('interface.graphview-show-lines')

        entry = Gtk.RadioMenuItem(label=_('Direct'))
        entry.connect("activate", self.update_lines_type,
                      0, 'interface.graphview-show-lines')
        if spline == 0:
            entry.set_active(True)
        entry.show()
        sub_menu.append(entry)

        entry = Gtk.RadioMenuItem(label=_('Curves'))
        entry.connect("activate", self.update_lines_type,
                      1, 'interface.graphview-show-lines')
        if spline == 1:
            entry.set_active(True)
        entry.show()
        sub_menu.append(entry)

        entry = Gtk.RadioMenuItem(label=_('Ortho'))
        entry.connect("activate", self.update_lines_type,
                      2, 'interface.graphview-show-lines')
        if spline == 2:
            entry.set_active(True)
        entry.show()
        sub_menu.append(entry)

        sub_menu.show()
        menu_item.show()
        self.menu.append(menu_item)

        self.menu.popup(None, None, None, None,
                        event.get_button()[1], event.time)

    def node_menu(self, node_class, handle, event):
        """
        Popup menu for node (person or family).
        """
        self.menu = Gtk.Menu()
        self.menu.set_reserve_toggle_size(False)

        if node_class == 'node':
            if handle:
                add_menuitem(self.menu, _('Edit'),
                             handle, self.edit_person)

                add_menuitem(self.menu, _('Edit tags'),
                             [handle, 'person'], self.edit_tag_list)

                add_menuitem(self.menu, _('Add new partner'),
                             handle, self.add_spouse)

                add_menuitem(self.menu, _('Set as home person'),
                             handle, self.set_home_person)

        elif node_class == 'familynode':
            if handle:
                add_menuitem(self.menu, _('Edit'),
                             handle, self.edit_family)

                add_menuitem(self.menu, _('Edit tags'),
                             [handle, 'family'], self.edit_tag_list)
        else:
            return False

        # new from gtk 3.22:
        # self.menu.popup_at_pointer(event)
        self.menu.popup(None, None, None, None,
                        event.get_button()[1], event.time)

    def edit_tag_list(self, obj):
        """
        Edit tag list for person or family.
        """
        handle, type = obj.get_data()
        if type == 'person':
            target = self.dbstate.db.get_person_from_handle(handle)
            self.person_to_focus = handle
        elif type == 'family':
            target = self.dbstate.db.get_family_from_handle(handle)
            f_handle = target.get_father_handle()
            if f_handle:
                self.person_to_focus = f_handle
            else:
                m_handle = target.get_mother_handle()
                if m_handle:
                    self.person_to_focus = m_handle
        else:
            return False

        if target:
            tag_list = []
            for tag_handle in target.get_tag_list():
                tag = self.dbstate.db.get_tag_from_handle(tag_handle)
                if tag:
                    tag_list.append((tag_handle, tag.get_name()))

            all_tags = []
            for tag_handle in self.dbstate.db.get_tag_handles(sort_handles=True):
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
                    if type == 'person':
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

    def set_home_person(self, obj):
        """
        Set the home person for database and make it active.
        """
        handle = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            self.dbstate.db.set_default_person_handle(handle)
            self.populate(handle)

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
        self.person_to_focus = handle

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
        # set edited person to scroll on it after rebuilding graph
        self.person_to_focus = handle

    def edit_family(self, obj):
        """
        Start a family editor for the selected family.
        """
        handle = obj.get_data()
        family = self.dbstate.db.get_family_from_handle(handle)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

        # set edited family person to scroll on it after rebuilding graph
        f_handle = family.get_father_handle()
        if f_handle:
            self.person_to_focus = f_handle
        else:
            m_handle = family.get_mother_handle()
            if m_handle:
                self.person_to_focus = m_handle

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

    def update_lines_type(self, menu_item, type, constant):
        """
        Save the lines type setting.
        """
        self.view._config.set(constant, type)

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

        self.tlist = []
        self.text_attrs = None
        self.func_list = []
        self.handle = None
        self.func_map = {
                         "g":       (self.start_g, self.stop_g),
                         "svg":     (self.start_svg, self.stop_svg),
                         "polygon": (self.start_polygon, self.stop_polygon),
                         "path":    (self.start_path, self.stop_path),
                         "image":   (self.start_image, self.stop_image),
                         "text":    (self.start_text, self.stop_text),
                         "ellipse": (self.start_ellipse, self.stop_ellipse),
                         "title":   (self.start_title, self.stop_title),
                        }
        self.text_anchor_map = {
                                "start":  GooCanvas.CanvasAnchorType.WEST,
                                "middle": GooCanvas.CanvasAnchorType.CENTER,
                                "end":    GooCanvas.CanvasAnchorType.EAST,
                               }
        # This list is used as a LIFO stack so that the SAX parser knows
        # which Goocanvas object to link the next object to.
        self.item_hier = []

        # list of persons items, used for animation class
        self.items_list = []

        # This dictionary maps various specific fonts to their generic font
        # types. Will need to include any truetype fonts here.
        self.font_family_map = {
                                "Times New Roman,serif": "Times",
                                "Times Roman,serif":     "Times",
                                "Times-Roman":           "Times",
                                "Times,serif":           "Times",
                                "Arial":                 "Helvetica",
                               }
        self.active_person_item = None

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
            item.set_simple_transform(self.bounds[1],
                                      self.bounds[3],
                                      scale_x,
                                      0)
            item.connect("button-press-event", self.widget.button_press)
            item.connect("button-release-event", self.widget.button_release)
            item.connect("motion-notify-event", self.widget.motion_notify_event)
        else:
            item = GooCanvas.CanvasGroup(parent=self.current_parent())
            item.connect("button-press-event", self.widget.select_node)
            self.items_list.append(item)

        item.description = attrs.get('class')
        self.item_hier.append(item)

    def stop_g(self, tag):
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
        n = 0
        for i in coord_string.split():
            coord = i.split(",")
            coord_x = float(coord[0])
            coord_y = float(coord[1])
            points.set_point(n, coord_x, coord_y)
            n += 1
        style = attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            stroke_color = p_style['stroke']
            fill_color = p_style['fill']
        else:
            stroke_color = attrs.get('stroke')
            fill_color = attrs.get('fill')

        if self.handle == self.widget.active_person_handle:
            line_width = 3  # thick box
        else:
            line_width = 1  # thin box

        tooltip = self.view.tags_tooltips.get(self.handle)

        # highlight the home person
        # stroke_color is not '#...' when tags are drawing, so we check this
        # maybe this is not good solution to check for tags but it works
        if self.highlight_home_person and stroke_color[:1] == '#':
            home_person = self.widget.dbstate.db.get_default_person()
            if home_person and home_person.handle == self.handle:
                fill_color = self.home_person_color
                tooltip = None

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

    def stop_polygon(self, tag):
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

    def stop_ellipse(self, tag):
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
            if attrs.get('stroke-dasharray'):
                is_dashed = True
            else:
                is_dashed = False

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

    def stop_path(self, tag):
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
        pos_x = float(self.text_attrs.get('x'))
        pos_y = float(self.text_attrs.get('y'))
        anchor = self.text_attrs.get('text-anchor')
        style = self.text_attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            try:
                font_family = self.font_family_map[p_style['font-family']]
            except KeyError:
                font_family = p_style['font-family']
            text_font = font_family + " " + p_style['font-size'] + 'px'
        else:
            font_family = self.font_family_map[self.text_attrs.get('font-family')]
            font_size = self.text_attrs.get('font-size')
            text_font = font_family + " " + font_size + 'px'

        # text color
        fill_color = self.text_attrs.get('fill')

        item = GooCanvas.CanvasText(parent=self.current_parent(),
                                    text=tag,
                                    x=pos_x,
                                    y=pos_y,
                                    anchor=self.text_anchor_map[anchor],
                                    use_markup=True,
                                    font=text_font,
                                    fill_color=fill_color)

        # retain the active person for other use elsewhere
        if self.handle == self.widget.active_person_handle:
            self.active_person_item = item

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

    def stop_image(self, tag):
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

    def end_element(self, tag):
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
# DotGenerator
#
#------------------------------------------------------------------------
class DotGenerator(object):

    def __init__(self, dbstate, view):
        """
        Creates graphing instructions in dot format which is fed to Graphviz,
        so that it can layout the data in a graph and produce an SVG form
        of the graph.
        """
        self.dbstate = dbstate
        self.database = dbstate.db
        self.dot = StringIO()

        self.view = view
        self.show_images = self.view._config.get(
                                  'interface.graphview-show-images')
        self.show_full_dates = self.view._config.get(
                                  'interface.graphview-show-full-dates')
        self.show_places = self.view._config.get(
                                  'interface.graphview-show-places')
        self.show_tag_color = self.view._config.get(
                                  'interface.graphview-show-tags')
        spline = self.view._config.get(
                                  'interface.graphview-show-lines')
        self.spline = SPLINE.get(int(spline))
        self.descendant_generations = self.view._config.get(
                                  'interface.graphview-descendant-generations')
        self.ancestor_generations = self.view._config.get(
                                  'interface.graphview-ancestor-generations')

        # get background color from gtk theme and convert it to hex
        # else use white background
        bg_color = Gtk.StyleContext().lookup_color('theme_bg_color')
        if bg_color[0]:
            bg_rgb = (bg_color[1].red, bg_color[1].green, bg_color[1].blue)
            bg_color = rgb_to_hex(bg_rgb)
        else:
            bg_color = '#ffffff'

        # get font color from gtk theme and convert it to hex
        # else use black font
        font_color = Gtk.StyleContext().lookup_color('theme_fg_color')
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
        self.colors = {
                       'link_color':      font_color,
                       'home_path_color': home_path_color,
                      }

        self.arrowheadstyle = 'none'
        self.arrowtailstyle = 'none'
        self.current_list = list()
        self.home_person = None

        dpi        = 72
        fontfamily = ""
        fontsize   = 14
        nodesep    = 0.20
        pagedir    = "BL"
        rankdir    = "TB"
        ranksep    = 0.40
        ratio      = "compress"
        # as we are not using paper,
        # choose a large 'page' size with no margin
        sizew      = 100
        sizeh      = 100
        xmargin    = 0.00
        ymargin    = 0.00

        self.write('digraph GRAMPS_graph\n')
        self.write('{\n')
        self.write(' bgcolor="%s";\n'                   % bg_color)
        self.write(' center="false"; \n')
        self.write(' charset="utf8";\n')
        self.write(' concentrate="false";\n')
        self.write(' dpi="%d";\n'                       % dpi)
        self.write(' graph [fontsize=%d];\n'            % fontsize)
        self.write(' margin="%3.2f,%3.2f"; \n'          % (xmargin, ymargin))
        self.write(' mclimit="99";\n')
        self.write(' nodesep="%.2f";\n'                 % nodesep)
        self.write(' outputorder="edgesfirst";\n')
        self.write(' pagedir="%s";\n'                   % pagedir)
        self.write(' rankdir="%s";\n'                   % rankdir)
        self.write(' ranksep="%.2f";\n'                 % ranksep)
        self.write(' ratio="%s";\n'                     % ratio)
        self.write(' searchsize="100";\n')
        self.write(' size="%3.2f,%3.2f"; \n'            % (sizew, sizeh))
        self.write(' splines=%s;\n'                     % self.spline)
        self.write('\n')
        self.write(' edge [style=solid fontsize=%d];\n' % fontsize)

        if fontfamily:
            self.write(' node [style=filled fontname="%s" '
                       'fontsize=%d fontcolor="%s"];\n'
                       % (fontfamily, fontsize, font_color))
        else:
            self.write(' node [style=filled fontsize=%d fontcolor="%s"];\n'
                       % (fontsize, font_color))
        self.write('\n')

    def build_graph(self, active_person):
        """
        Builds a GraphViz tree based on the active person.
        """
        if active_person:
            self.person_handles = set()
            self.home_person = self.dbstate.db.get_default_person()
            self.current_list = list()
            self.set_current_list(active_person)
            self.set_current_list_desc(active_person)
            self.person_handles.update(self.find_descendants(active_person))
            self.person_handles.update(self.find_ancestors(active_person))

            if len(self.person_handles) > 0:
                self.add_persons_and_families()
                self.add_child_links_to_families()

        # close the graphviz dot code with a brace.
        self.write('}\n')

    def set_current_list(self, active_person):
        """
        We get the path from the active person to the home person.
        Select ancestors.
        """
        if not active_person:
            return False
        person = self.database.get_person_from_handle(active_person)
        if person == self.home_person:
            self.current_list.append(active_person)
            return True
        else:
            for fam_handle in person.get_parent_family_handle_list():
                family = self.database.get_family_from_handle(fam_handle)
                if self.set_current_list(family.get_father_handle()):
                    self.current_list.append(active_person)
                    self.current_list.append(fam_handle)
                    return True
                if self.set_current_list(family.get_mother_handle()):
                    self.current_list.append(active_person)
                    self.current_list.append(fam_handle)
                    return True
        return False

    def set_current_list_desc(self, active_person):
        """
        We get the path from the active person to the home person.
        Select children.
        """
        if not active_person:
            return False
        person = self.database.get_person_from_handle(active_person)
        if person == self.home_person:
            self.current_list.append(active_person)
            return True
        else:
            for fam_handle in person.get_family_handle_list():
                family = self.database.get_family_from_handle(fam_handle)
                for child in family.get_child_ref_list():
                    if self.set_current_list_desc(child.ref):
                        self.current_list.append(active_person)
                        self.current_list.append(fam_handle)
                        return True
        return False

    def find_descendants(self, active_person):
        """
        Spider the database from the active person.
        """
        person = self.database.get_person_from_handle(active_person)
        person_handles = []
        self.add_descendant(person, self.descendant_generations,
                            person_handles)
        return person_handles

    def add_descendant(self, person, num_generations, person_handles):
        """
        Include a descendant in the list of people to graph.
        """
        if not person:
            return

        if num_generations <= 0:
            return

        # add self
        if person.handle not in person_handles:
            person_handles.append(person.handle)

            for family_handle in person.get_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)

                # add every child recursively
                for child_ref in family.get_child_ref_list():
                    self.add_descendant(
                           self.database.get_person_from_handle(child_ref.ref),
                           num_generations - 1,
                           person_handles)

                self.add_spouses(person, family, person_handles)

    def add_spouses(self, person, family, person_handles):
        """
        Add spouses to the list.
        """
        # get spouse
        if person.handle == family.get_father_handle():
            spouse_handle = family.get_mother_handle()
        else:
            spouse_handle = family.get_father_handle()

        # add spouse itself
        if spouse_handle and spouse_handle not in person_handles:
            person_handles.append(spouse_handle)

        # add all his(her) spouses recursively
        if spouse_handle:
            sp_person = self.database.get_person_from_handle(spouse_handle)
        else:
            sp_person = None

        if sp_person:
            for family_handle in sp_person.get_family_handle_list():
                sp_family = self.database.get_family_from_handle(family_handle)

                m_handle = sp_family.get_mother_handle()
                if m_handle and m_handle not in person_handles:
                    mother = self.database.get_person_from_handle(m_handle)
                    self.add_descendant(mother, 1, person_handles)

                f_handle = sp_family.get_father_handle()
                if f_handle and f_handle not in person_handles:
                    father = self.database.get_person_from_handle(f_handle)
                    self.add_descendant(father, 1, person_handles)

    def find_ancestors(self, active_person):
        """
        Spider the database from the active person.
        """
        person = self.database.get_person_from_handle(active_person)
        person_handles = []
        self.add_ancestor(person, self.ancestor_generations, person_handles)
        return person_handles

    def add_ancestor(self, person, num_generations, person_handles):
        """
        Include an ancestor in the list of people to graph.
        """
        if not person:
            return

        if num_generations <= 0:
            return

        # add self
        if person.handle not in person_handles:
            person_handles.append(person.handle)

            for family_handle in person.get_parent_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)

                # add every parent and spouses recursively
                f_handle = family.get_father_handle()
                if f_handle:
                    person_sp = self.database.get_person_from_handle(f_handle)
                    self.add_ancestor(person_sp,
                                      num_generations - 1,
                                      person_handles)
                    self.add_spouses(person_sp, family, person_handles)

                m_handle = family.get_mother_handle()
                if m_handle:
                    person_sp = self.database.get_person_from_handle(m_handle)
                    self.add_ancestor(person_sp,
                                      num_generations - 1,
                                      person_handles)
                    self.add_spouses(person_sp, family, person_handles)

    def add_child_links_to_families(self):
        """
        Returns string of GraphViz edges linking parents to families or
        children.
        """
        # hash people in a dictionary for faster inclusion checking
        person_dict = dict([handle, 1] for handle in self.person_handles)

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
                if ((father_handle and father_handle in person_dict) or
                   (mother_handle and mother_handle in person_dict)):
                    # link to the family node if either parent is in graph
                    self.add_family_link(person_handle, family, frel, mrel)
                else:
                    # link to the parents' nodes directly, if they are in graph
                    if father_handle and father_handle in person_dict:
                        self.add_parent_link(person_handle, father_handle,
                                             frel)
                    if mother_handle and mother_handle in person_dict:
                        self.add_parent_link(person_handle, mother_handle,
                                             mrel)

    def add_family_link(self, p_id, family, frel, mrel):
        """
        Links the child to a family.
        """
        style = 'solid'
        adopted = ((int(frel) != gramps.gen.lib.ChildRefType.BIRTH) or
                   (int(mrel) != gramps.gen.lib.ChildRefType.BIRTH))
        # if birth relation to father is NONE, meaning there is no father and
        # if birth relation to mother is BIRTH then solid line
        if ((int(frel) == gramps.gen.lib.ChildRefType.NONE) and
           (int(mrel) == gramps.gen.lib.ChildRefType.BIRTH)):
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
        if (int(rel) != gramps.gen.lib.ChildRefType.BIRTH):
            style = 'dotted'
        self.add_link(parent_handle, p_id, style,
                      self.arrowheadstyle, self.arrowtailstyle,
                      color=self.colors['home_path_color'],
                      bold=self.is_in_path_to_home(p_id))

    def add_persons_and_families(self):
        """
        Adds nodes for persons and their families.
        """
        # variable to communicate with get_person_label
        self.is_html_output = False
        url = ""

        # The list of families for which we have output the node,
        # so we don't do it twice
        families_done = {}
        for person_handle in self.person_handles:
            self.is_html_output = True
            person = self.database.get_person_from_handle(person_handle)
            # Output the person's node
            label = self.get_person_label(person)
            (shape, style, color, fill) = self.get_gender_style(person)
            self.add_node(person_handle, label, shape, color, style, fill, url)

            # Output families where person is a parent
            family_list = person.get_family_handle_list()
            for fam_handle in family_list:
                if fam_handle not in families_done:
                    families_done[fam_handle] = 1
                    self.__add_family(fam_handle)

    def is_in_path_to_home(self, f_handle):
        """
        Is the current person in the path to the home person?
        """
        if f_handle in self.current_list:
            return True
        return False

    def __add_family(self, fam_handle):
        """
        Add a node for a family and optionally link the spouses to it.
        """
        fam = self.database.get_family_from_handle(fam_handle)

        label = ""
        for event_ref in fam.get_event_ref_list():
            event = self.database.get_event_from_handle(event_ref.ref)
            if event.type == gramps.gen.lib.EventType.MARRIAGE and \
            (event_ref.get_role() == gramps.gen.lib.EventRoleType.FAMILY or
            event_ref.get_role() == gramps.gen.lib.EventRoleType.PRIMARY):
                label = self.get_event_string(event)
                break
        fill, color = color_graph_family(fam, self.dbstate)
        style = "filled"
        label = label.center(int(len(label)*2))
        self.add_node(fam_handle, label, "ellipse", color, style, fill)

        # If subgraphs are used then we add both spouses here and Graphviz
        # will attempt to position both spouses closely together.
        # A person who is a parent in more than one family may only be
        # positioned next to one of their spouses. The code currently
        # does not take into account multiple spouses.
        self.start_subgraph(fam_handle)
        f_handle = fam.get_father_handle()
        m_handle = fam.get_mother_handle()
        if f_handle:
            self.add_link(f_handle,
                          fam_handle, "",
                          self.arrowheadstyle,
                          self.arrowtailstyle,
                          color=self.colors['home_path_color'],
                          bold=self.is_in_path_to_home(f_handle))
        if m_handle:
            self.add_link(m_handle,
                          fam_handle, "",
                          self.arrowheadstyle,
                          self.arrowtailstyle,
                          color=self.colors['home_path_color'],
                          bold=self.is_in_path_to_home(m_handle))
        self.end_subgraph()

    def get_gender_style(self, person):
        """
        Return gender specific person style.
        """
        gender = person.get_gender()
        shape = "box"
        style = "solid, filled"
        color = ""
        fill = ""

        # get alive status of person to get box color
        death_event = get_death_or_fallback(self.database, person)
        if death_event:
            alive = False
        else:
            alive = True

        fill, color = color_graph_box(alive, gender)
        return(shape, style, color, fill)

    def get_person_label(self, person):
        """
        Return person label string.
        """
        # see if we have an image to use for this person
        image_path = None
        if self.show_images and self.is_html_output:
            media_list = person.get_media_list()
            if len(media_list) > 0:
                media_handle = media_list[0].get_reference_handle()
                media = self.database.get_media_from_handle(media_handle)
                media_mime_type = media.get_mime_type()
                if media_mime_type[0:5] == "image":
                    rectangle = media_list[0].get_rectangle()
                    path = media_path_full(self.database, media.get_path())
                    image_path = get_thumbnail_path(path, rectangle=rectangle)
                    # test if thumbnail actually exists in thumbs
                    # (import of data means media files might not be present
                    image_path = find_file(image_path)

        label = ""
        line_delimiter = '\\n'

        # If we have an image, then start an HTML table.
        # Remember to close the table afterwards!
        #
        # This isn't a free-form HTML format here...just a few keywords that
        # happen to be similar to keywords commonly seen in HTML.
        # For additional information on what is allowed, see:
        #
        #       http://www.graphviz.org/info/shapes.html#html

        if self.is_html_output and image_path:
            line_delimiter = '<BR/>'
            label += ('<TABLE BORDER="0" CELLSPACING="2" CELLPADDING="0" '
                      'CELLBORDER="0"><TR><TD><IMG SRC="%s"/></TD>'
                      % image_path)
            # trick it into not stretching the image
            label += '</TR><TR><TD>'
        else:
            # no need for html label with this person
            self.is_html_output = False

        # get all tags for the person and prepare html table
        # it will be added after dates (on the bottom)
        tag_table = ''
        if self.show_tag_color:
            tags = []
            for tag_handle in person.get_tag_list():
                tags.append(self.dbstate.db.get_tag_from_handle(tag_handle))

            # prepare html table of tags
            if len(tags) > 0:
                tag_table = ('</TD></TR><TR><TD>'
                             '<TABLE BORDER="0" CELLBORDER="0" '
                             'CELLPADDING="5"><TR>')
                for tag in tags:
                    tag_table += '<TD BGCOLOR="%s"></TD>' % tag.get_color()
                tag_table += '</TR></TABLE>'

                # open html table for adding text (name and dates)
                # if it not exist.
                # we need that to add tags table
                if not self.is_html_output:
                    line_delimiter = '<BR/>'
                    label += ('<TABLE BORDER="0" CELLSPACING="2" '
                              'CELLPADDING="0" CELLBORDER="0"><TR><TD>')
                    self.is_html_output = True
                self.add_tags_tooltip(person.handle, tags)

        # at the very least, the label must have the person's name
        name = displayer.display_name(person.get_primary_name())

        if self.is_html_output:
            # avoid < and > in the name, as this is html text
            label += name.replace('<', '&#60;').replace('>', '&#62;')
        else:
            label += name

        label += line_delimiter

        birth, death = self.get_date_strings(person)

        # There are two ways of displaying dates:
        # 1) full and on two lines:
        #       b. 1890-12-31 - BirthPlace
        #       d. 1960-01-02 - DeathPlace
        if self.show_full_dates or self.show_places:
            if birth:
                txt = _('b. %s') % birth  # short for "born" (could be "*")
                # line separator required only if we have both birth and death
                label += txt
            if birth and death:
                label += line_delimiter

            if death:
                txt = _('d. %s') % death  # short for "died" (could be "+")
                label += txt
        # 2) simple and on one line:
        #       (1890 - 1960)
        else:
            txt = '(%s - %s)' % (birth, death)
            label += txt

        # add html tags table
        label += tag_table

        # see if we have a table that needs to be terminated
        if self.is_html_output:
            label += '</TD></TR></TABLE>'
            return label
        else:
            # non html label is enclosed by "" so escape other "
            return label.replace('"', '\\\"')

    def get_date_strings(self, person):
        """
        Returns tuple of birth/christening and death/burying date strings.
        """
        birth_event = get_birth_or_fallback(self.database, person)
        if birth_event:
            birth = self.get_event_string(birth_event)
        else:
            birth = ""

        death_event = get_death_or_fallback(self.database, person)
        if death_event:
            death = self.get_event_string(death_event)
        else:
            death = ""

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
            place_title = place_displayer.display_event(self.database, event)
            if event.get_date_object().get_year_valid():
                if self.show_full_dates:
                    rtrn = '%s' % gramps.gen.datehandler.get_date(event)
                else:
                    rtrn = '%i' % event.get_date_object().get_year()
                # shall we add the place?
                if self.show_places:
                    if place_title:
                        rtrn += ' - %s' % place_title
                return rtrn
            else:
                if place_title:
                    return place_title
        return ''

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
                 style="", fillcolor="", url="", htmloutput=False):
        """
        Add a node to this graph.
        Nodes can be different shapes like boxes and circles.
        Gramps handles are used as nodes but need to be prefixed with an
        underscore because Graphviz does not like IDs that begin with a number.
        """
        text = '['

        if shape:
            text += ' shape="%s"'     % shape

        if color:
            text += ' color="%s"'     % color

        if fillcolor:
            text += ' fillcolor="%s"' % fillcolor

        if style:
            text += ' style="%s"'     % style

        # get all tags for the family and prepare html table
        # it will be added after dates (on the bottom of node)
        if self.show_tag_color:
            tags = []
            try:
                # we need to do the following only if the node id is a
                # family handle, so we try to get family from handle we have
                fam = self.database.get_family_from_handle(node_id)
                for tag_handle in fam.get_tag_list():
                    tags.append(self.dbstate.db.get_tag_from_handle(tag_handle))

                # convert plain text label to html
                # and inset it in the main table
                label_new = ('<TABLE BORDER="0" CELLSPACING="2" '
                             'CELLPADDING="0" CELLBORDER="0">')
                label_new += '<TR><TD>%s' % label.replace('\\n', '<BR/>')

                # prepare html table of tags
                tag_table = ''
                if len(tags) > 0:
                    tag_table = ('</TD></TR><TR><TD><TABLE BORDER="0" '
                                 'CELLBORDER="0" CELLPADDING="5"><TR>')
                    for tag in tags:
                        tag_table += '<TD BGCOLOR="%s"></TD>' % tag.get_color()
                    tag_table += '</TR></TABLE>'
                    self.add_tags_tooltip(node_id, tags)

                # combine new label for family node and close the main table
                label = label_new + tag_table + '</TD></TR></TABLE>'
            except:
                # the node is not a family
                pass

        # note that we always output a label -- even if an empty string --
        # otherwise GraphViz uses the node ID as the label which is unlikely
        # to be what the user wants to see in the graph
        if label.startswith("<") or htmloutput:
            text += ' label=<%s>' % label
        else:
            text += ' label="%s"' % label

        if url:
            text += ' URL="%s"'   % url

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
        self.dot.write(text)

    def get_dot(self):
        return self.dot.getvalue()

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
        self.speed = self.view._config.get('interface.graphview-animation-speed')
        self.speed = 50*int(self.speed)
        # length of step
        self.step_len = 10

        # separated counter and direction of shaking
        # for each item that in shake procedure
        self.counter = {}
        self.shake = {}

    def update_items(self, items_list):
        """
        Update list of items for current graph.
        """
        self.items_list = items_list

        # clear counters and shakes - items not exists anymore
        self.counter = {}
        self.shake = {}

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
        if (self.counter[item.title] < self.max_count) and (not stoped):
            self.shake[item.title] = (-1)*self.shake[item.title]
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

    def shake_item(self, item):
        """
        Shake item to help to see it.
        Use build-in function of CanvasItem.
        """
        if item:
            if not self.counter.get(item.title):
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
            x = (bounds.x2 - (bounds.x2-bounds.x1)/2)
            y = (bounds.y1 - (bounds.y1-bounds.y2)/2)
            self.move_to(item, (x, y), animated)
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
        steps_count = int(trace_len/self.step_len * self.canvas.get_scale())

        # prevent division by 0
        if steps_count > 0:
            x_step = x_delta / steps_count
            y_step = y_delta / steps_count

            point =(start_x + x_step,
                    start_y + y_step)
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
            max_scroll_x = (self.hadjustment.get_upper() -
                            self.hadjustment.get_page_size()) / self.canvas.get_scale()
            max_scroll_y = (self.vadjustment.get_upper() -
                            self.vadjustment.get_page_size()) / self.canvas.get_scale()

            # fix destination to fit in max scroll
            if dest[0] > max_scroll_x: dest = (max_scroll_x, dest[1])
            if dest[0] < 0: dest = (0, dest[1])
            if dest[1] > max_scroll_y: dest = (dest[0], max_scroll_y)
            if dest[1] < 0: dest = (dest[0], 0)

            cur_pos = (self.hadjustment.get_value() / self.canvas.get_scale(),
                       self.vadjustment.get_value() / self.canvas.get_scale())

            # finish if we already at destination
            if dest == cur_pos: break

            # get next point to destination
            point = self.get_trace_to(dest)

            GLib.idle_add(self.scroll_canvas, point)
            GLib.usleep(20 * self.speed)

            # finish if we try to goto destination point
            if point == dest: break

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
