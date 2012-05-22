# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010-2011  Gary Burton
#                          GraphvizSvgParser is based on the Gramps XML import
#                          DotGenerator is based on the relationship graph
#                          report.
#                          Mouse panning is derived from the pedigree view
# Copyright (C) 2012       Mathieu MD
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
import sys
from xml.parsers.expat import ExpatError, ParserCreate
from TransUtils import get_addon_translator
_ = get_addon_translator().ugettext
import gtk
import string
from subprocess import Popen, PIPE
from cStringIO import StringIO

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
import gen.lib
from gui.views.navigationview import NavigationView
import Bookmarks
from gen.display.name import displayer
from gen.utils import get_birth_or_fallback, get_death_or_fallback
import ThumbNails
import Utils
from gui.editors import EditPerson, EditFamily
import Errors

try:
    import cairo
except ImportError:
    raise Exception("Cairo (http://www.cairographics.org) is required "
                    "for this view to work")
try:
    import goocanvas
except ImportError:
    raise Exception("pyGoocanvas (http://live.gnome.org/PyGoocanvas) is "
                    "required for this view to work")

if os.sys.platform == "win32":
    _DOT_FOUND = Utils.search_for("dot.exe")
else:
    _DOT_FOUND = Utils.search_for("dot")

if not _DOT_FOUND:
    raise Exception("GraphViz (http://www.graphviz.org) is "
                    "required for this view to work")


#-------------------------------------------------------------------------
#
# GraphView
#
#-------------------------------------------------------------------------
class GraphView(NavigationView):
    """
    View for pedigree tree.
    Displays the ancestors of a selected individual.
    """
    #settings in the config file
    CONFIGSETTINGS = (
        ('interface.graphview-show-images', True),
        )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(self, _('Graph View'), pdata, dbstate, uistate, 
                                      dbstate.db.get_bookmarks(), 
                                      Bookmarks.PersonBookmarks, nav_group)

        self.show_images = self._config.get('interface.graphview-show-images')

        self.dbstate = dbstate
        self.graph_widget = None
        self.dbstate.connect('database-changed', self.change_db)

        self.additional_uis.append(self.additional_ui())

    def _connect_db_signals(self):
        """
        Set up callbacks for changes to person and family nodes
        """
        self.callman.add_db_signal('person-update', self.goto_handle)
        self.callman.add_db_signal('family-update', self.goto_handle)

    def change_db(self, db):
        """
        Set up callback for changes to the database
        """
        self._change_db(db)
        if self.active:
            self.graph_widget.clear()
            if self.get_active() != "":
                self.graph_widget.populate(self.get_active())
        else:
            self.dirty = True

    def get_stock(self):
        """
        The category stock icon
        """
        return 'gramps-pedigree'
    
    def get_viewtype_stock(self):
        """Type of view in category
        """
        return 'gramps-pedigree'

    def build_widget(self):
        """
        Builds the canvas along with a zoom control
        """
        self.graph_widget = GraphWidget(self, self.dbstate, self.uistate)
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
          <toolbar name="ToolBar">
            <placeholder name="CommonNavigation">
              <toolitem action="Back"/>
              <toolitem action="Forward"/>
              <toolitem action="HomePerson"/>
            </placeholder>
          </toolbar>
        </ui>'''

    def navigation_type(self):
        "The type of forward and backward navigation to perform"
        return 'Person'

    def goto_handle(self, handle):
        "Go to a named handle"
        if self.active:
            if self.get_active() != "":
                self.graph_widget.clear()
                self.graph_widget.populate(self.get_active())
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

    def config_connect(self):
        """
        Overwriten from  :class:`~gui.views.pageview.PageView method
        This method will be called after the ini file is initialized,
        use it to monitor changes in the ini file
        """
        self._config.connect('interface.graphview-show-images',
                          self.cb_update_show_images)

    def _get_configure_page_funcs(self):
        """
        Return a list of functions that create gtk elements to use in the 
        notebook pages of the Configure dialog
        
        :return: list of functions
        """
        return [self.config_panel]

    def config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog
        """
        table = gtk.Table(7, 2)
        table.set_border_width(12)
        table.set_col_spacings(6)
        table.set_row_spacings(6)

        configdialog.add_checkbox(table, 
                _('Show images'), 
                0, 'interface.graphview-show-images')

        return _('Layout'), table

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
        # Variables for drag and scroll
        self._last_x = 0
        self._last_y = 0
        self._in_move = False
        self.view = view
        self.dbstate = dbstate
        self.uistate = uistate
        self.active_person_handle = None

        scrolled_win = gtk.ScrolledWindow()
        scrolled_win.set_shadow_type(gtk.SHADOW_IN)

        self.canvas = goocanvas.Canvas()
        self.canvas.props.units = gtk.UNIT_POINTS
        self.canvas.props.resolution_x = 72
        self.canvas.props.resolution_y = 72

        scrolled_win.add(self.canvas)

        self.vbox = gtk.VBox(False, 4)
        self.vbox.set_border_width (4)
        hbox = gtk.HBox(False, 4)
        self.vbox.pack_start(hbox, False, False, 0)
        zoom_label = gtk.Label("Zoom:")
        hbox.pack_start (zoom_label, False, False, 0)

        adj = gtk.Adjustment (1.00, 0.05, 10.00, 0.05, 0.50, 0.50)
        scale = gtk.HScale(adj)
        adj.connect("value_changed", self.zoom_changed)
        hbox.pack_start(scale, True, True, 0)
        self.vbox.pack_start(scrolled_win, True, True, 0)

    def populate(self, active_person):
        """
        Populate the graph with widgets derived from Graphviz
        """
        dot = DotGenerator(self.dbstate, self.view)
        self.active_person_handle = active_person
        dot.build_graph(active_person)

        # Build the rest of the widget by parsing SVG data from Graphviz
        dot_data = dot.get_dot()
        svg_data = Popen(['dot', '-Tsvg'], 
                    stdin=PIPE, stdout=PIPE).communicate(input=dot_data)[0]
        parser = GraphvizSvgParser(self)
        parser.parse(svg_data)
        window = self.canvas.get_parent()

        # The scroll_to method will try and put the active person in the top
        # left part of the screen. We want it in the middle, so make an offset
        # half the width of the scrolled window size.
        h_offset = window.get_hadjustment().page_size / 2

        # Apply the scaling factor so the offset is adjusted to the scale
        h_offset = h_offset / self.canvas.get_scale()

        # Now try and centre the active person
        if parser.active_person_item:
            self.canvas.scroll_to(parser.get_active_person_x() - h_offset,
                                  parser.get_active_person_y())

        # Update the status bar
        self.view.change_page()

    def clear(self):
        """
        Clear the graph by creating a new root item
        """
        self.canvas.set_root_item(goocanvas.Group())

    def get_widget(self):
        """
        Return the graph display widget that includes the drawing canvas.
        """
        return self.vbox

    def button_press(self, item, target, event):
        """
        Enter in scroll mode when mouse button pressed in background
        or call option menu.
        """
        if event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS \
            and item == self.canvas.get_root_item():
            self.canvas.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))
            self._last_x = event.x_root
            self._last_y = event.y_root
            self._in_move = True
            return False
        return False

    def button_release(self, item, target, event):
        """Exit from scroll mode when button release."""
        if event.button == 1 and event.type == gtk.gdk.BUTTON_RELEASE:
            self.motion_notify_event(item, target, event)
            self.canvas.window.set_cursor(None)
            self._in_move = False
            return True
        return False

    def motion_notify_event(self, item, target, event):
        """Function for motion notify events for drag and scroll mode."""
        if self._in_move and (event.type == gtk.gdk.MOTION_NOTIFY or \
           event.type == gtk.gdk.BUTTON_RELEASE):
            window = self.canvas.get_parent()
            hadjustment = window.get_hadjustment()
            vadjustment = window.get_vadjustment()
            self.update_scrollbar_positions(vadjustment,
                vadjustment.value - (event.y_root - self._last_y))
            self.update_scrollbar_positions(hadjustment,
                hadjustment.value - (event.x_root - self._last_x))
            return True
        return False

    def update_scrollbar_positions(self, adjustment, value):
        """Controle value then try setup in scrollbar."""
        if value > (adjustment.upper - adjustment.page_size):
            adjustment.set_value(adjustment.upper - adjustment.page_size)
        else:
            adjustment.set_value(value)
        return True

    def zoom_changed(self, adj):
        """
        Zoom the canvas widget
        """
        self.canvas.set_scale(adj.value)

    def select_node(self, item, target, event):
        """
        Perform actions when a node is clicked.
        """
        handle = item.get_data("handle")
        node_class = item.get_data("class")

        if event.type != gtk.gdk.BUTTON_PRESS:
            pass
        if event.button == 1 and node_class == 'node': # Left mouse
            if handle == self.active_person_handle:
                # Find a parent of the active person so that they can become
                # the active person, if no parents then leave as the current
                # active person
                parent_handle = self.find_a_parent(handle)
                if parent_handle:
                    handle = parent_handle 

            # Redraw the graph based on the selected person
            self.view.change_active(handle)
        elif event.button == 3 and node_class == 'node': # Right mouse
            if handle:
                self.edit_person(handle)
        elif event.button == 3 and node_class == 'familynode': # Right mouse
            if handle:
                self.edit_family(handle)

        return True

    def edit_person(self, handle):
        """
        Start a person editor for the selected person
        """
        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except Errors.WindowActiveError:
            pass

    def edit_family(self, handle):
        """
        Start a family editor for the selected family
        """
        family = self.dbstate.db.get_family_from_handle(handle)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except Errors.WindowActiveError:
            pass

    def find_a_parent(self, handle):
        """
        Locate a parent from the first family that the selected person is a
        child of. Try and find the father first, then the mother. Either will
        be OK. 
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

#-------------------------------------------------------------------------
#
# GraphvizSvgParser
#
#-------------------------------------------------------------------------
class GraphvizSvgParser(object):
    """
    Parses SVG produces by Graphviz and adds the elements to a goocanvas
    """

    def __init__(self, widget):
        """
        Initialise the GraphvizSvgParser class
        """
        self.func = None
        self.widget = widget
        self.canvas = widget.canvas
        self.tlist = []
        self.text_attrs = None
        self.func_list = [None]*50
        self.func_index = 0
        self.handle = None
        self.func_map = {
            "g": (self.start_g, self.stop_g), 
            "svg": (self.start_svg, self.stop_svg), 
            "polygon": (self.start_polygon, self.stop_polygon), 
            "path": (self.start_path, self.stop_path), 
            "image": (self.start_image, self.stop_image), 
            "text": (self.start_text, self.stop_text), 
            "ellipse": (self.start_ellipse, self.stop_ellipse), 
            "title": (self.start_title, self.stop_title), 
        }
        self.text_anchor_map = {"start" : gtk.ANCHOR_WEST,
                                "middle" : gtk.ANCHOR_CENTER,
                                "end" : gtk.ANCHOR_EAST,}
        # This list is used as a LIFO stack so that the SAX parser knows
        # which Goocanvas object to link the next object to.
        self.item_hier = [] 

        # This dictionary maps various specific fonts to their generic font
        # types. Will need to include any truetype fonts here.
        self.font_family_map = {"Times New Roman,serif"   : "Times",
                                "Times Roman,serif"       : "Times",
                                "Times,serif"             : "Times",
                                "Arial"                   : "Helvetica"}
        self.active_person_item = None

    def parse(self, ifile):
        """
        Parse an SVG file produced by Graphviz
        """
        self.item_hier.append(self.canvas.get_root_item())
        parser = ParserCreate()
        parser.StartElementHandler = self.start_element
        parser.EndElementHandler = self.end_element
        parser.CharacterDataHandler = self.characters
        parser.Parse(ifile)

        for key in self.func_map.keys():
            del self.func_map[key]
        del self.func_map
        del self.func_list
        del parser

    def start_g(self, attrs):
        """
        Parse <g> tags.
        """
        item = goocanvas.Group(parent = self.current_parent())
        item.set_data('class', attrs.get('class'))
        self.item_hier.append(item)
        # The class attribute defines the group type. There should be one
        # graph type <g> tag which defines the transform for the whole graph.
        if attrs.get('class') == 'graph':
            transform = attrs.get('transform')
            item = self.canvas.get_root_item()
            transform_list = transform.split(') ')
            scale = transform_list[0].split()
            scale_x = float(scale[0].lstrip('scale('))
            scale_y = float(scale[1])
            bounds = self.canvas.get_bounds()
            c_transform = \
                cairo.Matrix(scale_x, 0, 0, scale_y, bounds[1], bounds[3])
            item.set_transform(c_transform)
            item.connect("button-press-event", self.widget.button_press)
            item.connect("button-release-event", self.widget.button_release)
            item.connect("motion-notify-event", self.widget.motion_notify_event)
        else:
            item.connect("button-press-event", self.widget.select_node)

    def stop_g(self, tag):
        """
        Parse </g> tags
        """
        item = self.item_hier.pop()
        item.set_data('handle', self.handle)

    def start_svg(self, attrs):
        """
        Parse <svg> tags.
        """
        item = goocanvas.Group(parent = self.current_parent())

        view_box = attrs.get('viewBox').split()
        v_left = float(view_box[0])
        v_top = float(view_box[1])
        v_right = float(view_box[2])
        v_bottom = float(view_box[3])
        self.canvas.set_bounds(v_left, v_top, v_right, v_bottom)

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
        Parse </title> tags. Stripping off underscore prefix added to fool
        Graphviz
        """
        self.handle = tag.lstrip("_")

    def start_polygon(self, attrs):
        """
        Parse <polygon> tags. Polygons define the boxes around individuals on
        the graph.
        """
        points = goocanvas.Points(self.parse_points(attrs.get('points')))
        style = attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            stroke_color = p_style['stroke']
            fill_color = p_style['fill']
        else:
            stroke_color = attrs.get('stroke')
            fill_color = attrs.get('fill')

        if self.handle == self.widget.active_person_handle:
            line_width = 3  # Thick box
        else:
            line_width = 1  # Thin box

        item = goocanvas.Polyline(parent = self.current_parent(),
                                  points = points,
                                  close_path = True,
                                  fill_color = fill_color,
                                  line_width = line_width,
                                  stroke_color = stroke_color)
        self.item_hier.append(item)

    def stop_polygon(self, tag):
        """
        Parse </polygon> tags.
        """
        self.item_hier.pop()
        
    def start_ellipse(self, attrs):
        """
        Parse <ellipse> tags. These define the family nodes of the graph
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

        item = goocanvas.Ellipse(parent = self.current_parent(),
                                 center_x = center_x,
                                 center_y = center_y,
                                 radius_x = radius_x,
                                 radius_y = radius_y,
                                 fill_color = fill_color,
                                 stroke_color = stroke_color,
                                 line_width = 1)
        self.current_parent().set_data('class', 'familynode')
        self.item_hier.append(item)

    def stop_ellipse(self, tag):
        """
        Parse </ellipse> tags.
        """
        self.item_hier.pop()

    def start_path(self, attrs):
        """
        Parse <path> tags. These define the links between nodes.
        Solid lines represent birth relationships and dashed lines are used
        when a child has a non-birth relationship to a parent.
        """
        p_data = attrs.get('d')
        style = attrs.get('style')

        if style:
            p_style = self.parse_style(style)
            stroke_color = p_style['stroke']
            is_dashed = p_style.has_key('stroke-dasharray')
        else:
            stroke_color = attrs.get('stroke')
            if attrs.get('stroke-dasharray'):
                is_dashed = True
            else:
                is_dashed = False
        
        if is_dashed:
            item = goocanvas.Path(parent = self.current_parent(),
                                  data = p_data,
                                  stroke_color = stroke_color,
                                  line_width = 1,
                                  line_dash = goocanvas.LineDash([5.0, 5.0]))
        else:
            item = goocanvas.Path(parent = self.current_parent(),
                                  data = p_data,
                                  stroke_color = stroke_color,
                                  line_width = 1)
      
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
        Parse </text> tags. The text tag contains some textual data.
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
            text_font = font_family + " " + p_style['font-size']
        else:
            font_family = self.font_family_map[self.text_attrs.get('font-family')]
            font_size = self.text_attrs.get('font-size')
            text_font = font_family + " " + font_size

        item = goocanvas.Text(parent = self.current_parent(),
                              text = tag,
                              x = pos_x,
                              y = pos_y,
                              anchor = self.text_anchor_map[anchor],
                              use_markup = True,
                              font = text_font)

        # Retain the active person for other use elsewhere
        if self.handle == self.widget.active_person_handle:
            self.active_person_item = item 

    def start_image(self, attrs):
        """
        Parse <image> tags.
        """
        pos_x = float(attrs.get('x'))
        pos_y = float(attrs.get('y'))
        width = int(attrs.get('width').encode('utf-8').rstrip(string.letters))
        height = int(attrs.get('height').encode('utf-8').rstrip(string.letters))
        pixbuf = gtk.gdk.pixbuf_new_from_file(attrs.get('xlink:href'))
        item = goocanvas.Image(parent = self.current_parent(),
                               x = pos_x,
                               y = pos_y,
                               height = height,
                               width = width,
                               pixbuf = pixbuf)
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
        self.func_list[self.func_index] = (self.func, self.tlist)
        self.func_index += 1
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
        self.func_index -= 1    
        self.func, self.tlist = self.func_list[self.func_index]
        
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
        Parse style attributes for Graphviz version < 2.24
        """
        style = style.rstrip(';')
        return dict([i.split(':') for i in style.split(';')])

    def parse_points(self, points):
        """
        Parse points attributes
        """
        return [tuple(float(j) for j in i.split(",")) for i in points.split()]

    def get_active_person_x(self):
        """
        Find the position of the centre of the active person in the horizontal
        dimension
        """
        return self.active_person_item.props.x

    def get_active_person_y(self):
        """
        Find the position of the centre of the active person in the vertical
        dimension
        """
        return self.active_person_item.props.y

#------------------------------------------------------------------------
#
# DotGenerator
#
#------------------------------------------------------------------------
class DotGenerator(object):

    def __init__(self, dbstate, view):
        """
        Creates graphing instructions in dot format which is fed to Graphviz
        so that it can layout the data in a graph and produce an SVG form
        of the graph.
        """
        
        self.dbstate = dbstate
        self.database = dbstate.db
        self.dot = StringIO()

        self.view = view
        self.show_images = self.view._config.get('interface.graphview-show-images')

        self.colors = {
            'male_fill'      : '#b9cfe7',
            'male_border'    : '#204a87',
            'female_fill'    : '#ffcdf1',
            'female_border'  : '#87206a',
            'unknown_fill'   : '#f4dcb7',
            'unknown_border' : '#000000',
            'family_fill'    : '#ffffe0',
            'family_border'  : '#000000',
        }
        self.arrowheadstyle = 'none'
        self.arrowtailstyle = 'none'
        
        dpi        = 72
        fontfamily = ""
        fontsize   = 9 
        nodesep    = 0.20
        pagedir    = "BL"
        rankdir    = "TB"
        ranksep    = 0.40
        ratio      = "compress"
        # As we are not using paper, choose a large 'page' size
        # with no margin
        sizew      = 100
        sizeh      = 100
        xmargin    = 0.00
        ymargin    = 0.00

        self.write( 'digraph GRAMPS_graph\n'        )
        self.write( '{\n'                           )
        self.write( '  bgcolor=white;\n'            )
        self.write( '  center="false"; \n'           )
        self.write( '  charset="utf8";\n'     )
        self.write( '  concentrate="false";\n'      )
        self.write( '  dpi="%d";\n'                 % dpi          )
        self.write( '  graph [fontsize=%d];\n'      % fontsize     )
        self.write( '  margin="%3.2f,%3.2f"; \n'    % (xmargin, ymargin))
        self.write( '  mclimit="99";\n'             )
        self.write( '  nodesep="%.2f";\n'           % nodesep      )
        self.write( '  outputorder="edgesfirst";\n' )
        self.write( '  pagedir="%s";\n'             % pagedir      )
        self.write( '  rankdir="%s";\n'             % rankdir      )
        self.write( '  ranksep="%.2f";\n'           % ranksep      )
        self.write( '  ratio="%s";\n'               % ratio        )
        self.write( '  searchsize="100";\n'         )
        self.write( '  size="%3.2f,%3.2f"; \n'      % (sizew, sizeh)    )
        self.write( '  splines="true";\n'           )
        self.write( '\n'                            )
        self.write( '  edge [style=solid fontsize=%d];\n' % fontsize )
        if fontfamily:
            self.write( '  node [style=filled fontname="%s" fontsize=%d];\n' 
                            % ( fontfamily, fontsize ) )
        else:
            self.write( '  node [style=filled fontsize=%d];\n' 
                            % fontsize )
        self.write( '\n' )

    def build_graph(self, active_person):
        "Builds a GraphViz descendant tree based on the active person"
        if active_person:
            self.person_handles = []
            self.find_descendants(active_person)
            
            if len(self.person_handles) > 0:
                self.add_persons_and_families()
                self.add_child_links_to_families()

        # Close the graphviz dot code with a brace.
        self.write('}\n')

    def find_descendants(self, active_person):
        "Spider the database from the active person"
        person = self.database.get_person_from_handle(active_person)
        self.add_descendant(person)

    def add_descendant(self, person):
        "Include a descendant in the list of people to graph"
        if not person:
            return

        # Add self
        if person.handle not in self.person_handles:
            self.person_handles.append(person.handle)

        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)

            # Add every child recursively
            for child_ref in family.get_child_ref_list():
                self.add_descendant(
                    self.database.get_person_from_handle(child_ref.ref))

            # Add spouse
            if person.handle == family.get_father_handle():
                spouse_handle = family.get_mother_handle()
            else:
                spouse_handle = family.get_father_handle()

            if spouse_handle and spouse_handle not in self.person_handles:
                self.person_handles.append(spouse_handle)

    def add_child_links_to_families(self):
        "returns string of GraphViz edges linking parents to families or \
         children"
        # Hash people in a dictionary for faster inclusion checking
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
                    # Link to the family node if either parent is in graph
                    self.add_family_link(person_handle, family, frel, mrel)
                else:
                    # Link to the parents' nodes directly, if they are in graph
                    if father_handle and father_handle in person_dict:
                        self.add_parent_link(person_handle, father_handle, frel)
                    if mother_handle and mother_handle in person_dict:
                        self.add_parent_link(person_handle, mother_handle, mrel)

    def add_family_link(self, p_id, family, frel, mrel):
        "Links the child to a family"
        style = 'solid'
        adopted = ((int(frel) != gen.lib.ChildRefType.BIRTH) or
                   (int(mrel) != gen.lib.ChildRefType.BIRTH))
        # If birth relation to father is NONE, meaning there is no father and
        # if birth relation to mother is BIRTH then solid line
        if ((int(frel) == gen.lib.ChildRefType.NONE) and
           (int(mrel) == gen.lib.ChildRefType.BIRTH)):
            adopted = False
        if adopted:
            style = 'dotted'
        self.add_link(family.handle, p_id, style,  
                      self.arrowheadstyle, self.arrowtailstyle )
        
    def add_parent_link(self, p_id, parent_handle, rel):
        "Links the child to a parent"
        style = 'solid'
        if (int(rel) != gen.lib.ChildRefType.BIRTH):
            style = 'dotted'
        self.add_link(parent_handle, p_id, style,
                      self.arrowheadstyle, self.arrowtailstyle )
        
    def add_persons_and_families(self):
        "adds nodes for persons and their families"
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
                        
    def __add_family(self, fam_handle):
        """Add a node for a family and optionally link the spouses to it"""
        fam = self.database.get_family_from_handle(fam_handle)

        label = ""
        for event_ref in fam.get_event_ref_list():
            event = self.database.get_event_from_handle(event_ref.ref)
            if event.type == gen.lib.EventType.MARRIAGE and \
            (event_ref.get_role() == gen.lib.EventRoleType.FAMILY or 
            event_ref.get_role() == gen.lib.EventRoleType.PRIMARY ):
                label = self.get_event_string(event)
                break
        color = ""
        fill = self.colors['family_fill']
        style = "filled"
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
                          self.arrowtailstyle)
            # Include spouses from other marriage not selected by filter
            if f_handle not in self.person_handles:
                self.person_handles.append(f_handle)
        if m_handle:
            self.add_link(m_handle,
                          fam_handle, "", 
                          self.arrowheadstyle,
                          self.arrowtailstyle)
            # Include spouses from other marriage not selected by filter
            if m_handle not in self.person_handles:
                self.person_handles.append(m_handle)
        self.end_subgraph()

    def get_gender_style(self, person):
        "return gender specific person style"
        gender = person.get_gender()
        shape = "box"
        style = "solid"
        color = ""
        fill = ""

        style += ",filled"
        if gender == person.MALE:
            fill = self.colors['male_fill']
            color = self.colors['male_border']
        elif gender == person.FEMALE:
            fill = self.colors['female_fill']
            color = self.colors['female_border']
        else:
            fill = self.colors['unknown_fill']
            color = self.colors['unknown_border']
        return(shape, style, color, fill)

    def get_person_label(self, person):
        "return person label string"
        # see if we have an image to use for this person
        image_path = None
        if self.show_images and self.is_html_output:
            media_list = person.get_media_list()
            if len(media_list) > 0:
                media_handle = media_list[0].get_reference_handle()
                media = self.database.get_object_from_handle(media_handle)
                media_mime_type = media.get_mime_type()
                if media_mime_type[0:5] == "image":
                    image_path = ThumbNails.get_thumbnail_path(
                                    Utils.media_path_full(self.database, 
                                                          media.get_path()),
                                        rectangle=media_list[0].get_rectangle())
                    # test if thumbnail actually exists in thumbs
                    # (import of data means media files might not be present
                    image_path = Utils.find_file(image_path)

        label = u""
        line_delimiter = '\\n'

        # If we have an image, then start an HTML table; remember to close
        # the table afterwards!
        #
        # This isn't a free-form HTML format here...just a few keywords that
        # happen to be
        # similar to keywords commonly seen in HTML.  For additional
        # information on what
        # is allowed, see:
        #
        #       http://www.graphviz.org/info/shapes.html#html
        #
        if self.is_html_output and image_path:
            line_delimiter = '<BR/>'
            label += '<TABLE BORDER="0" CELLSPACING="2" CELLPADDING="0" CELLBORDER="0"><TR><TD></TD><TD><IMG SRC="%s"/></TD><TD></TD>'  % image_path
            #trick it into not stretching the image
            label += '</TR><TR><TD COLSPAN="3">'
        else :
            #no need for html label with this person
            self.is_html_output = False

        # at the very least, the label must have the person's name
        name = displayer.display_name(person.get_primary_name())

        # Need to pad the label because of a bug in the SVG output of Graphviz
        # which causes the width of the text to exceed the bounding box.
        if self.is_html_output :
            # avoid < and > in the name, as this is html text
            label += name.replace('<', '&#60;').replace('>', '&#62;')
        else :
            name = name.center(len(name) + 10)
            label += name
        birth, death = self.get_date_strings(person)
        label = label + '%s(%s - %s)' % (line_delimiter, birth, death)
            
        # see if we have a table that needs to be terminated
        if self.is_html_output:
            label += '</TD></TR></TABLE>'
            return label
        else :
            # non html label is enclosed by "" so escape other "
            return label.replace('"', '\\\"')
    
    def get_date_strings(self, person):
        "returns tuple of birth/christening and death/burying date strings"
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
        return string for for an event label.
        
        Based on the data availability and preferences, we select one
        of the following for a given event:
            year only
            complete date
            place name
            empty string
        """
        if event:
            if event.get_date_object().get_year_valid():
                return '%i' % event.get_date_object().get_year()
            else:
                place_handle = event.get_place_handle()
                place = self.database.get_place_from_handle(place_handle)
                if place and place.get_title():
                    return place.get_title()
        return ''

    def add_link(self, id1, id2, style="", head="", tail="", comment=""):
        """
        Add a link between two nodes. Gramps handles are used as nodes but need
        to be prefixed with an underscore because Graphviz does not like IDs
        that begin with a number.
        """
        self.write('  _%s -> _%s' % (id1, id2))
        
        if style or head or tail:
            self.write(' [')
            
            if style:
                self.write(' style=%s' % style)
            if head:
                self.write(' arrowhead=%s' % head)
            if tail:
                self.write(' arrowtail=%s' % tail)
                
            self.write(' ]')

        self.write(';')

        if comment:
            self.write(' // %s' % comment)

        self.write('\n')

    def add_node(self, node_id, label, shape="", color="", 
                 style="", fillcolor="", url="", htmloutput=False):
        """
        Add a node to this graph. Nodes can be different shapes like boxes and
        circles.
        Gramps handles are used as nodes but need to be prefixed with an
        underscore because Graphviz does not like IDs that begin with a number.
        """
        text = '['

        if shape:
            text += ' shape="%s"'       % shape
            
        if color:
            text += ' color="%s"'       % color
            
        if fillcolor:
            text += ' fillcolor="%s"'   % fillcolor

        if style:
            text += ' style="%s"'       % style

        # note that we always output a label -- even if an empty string --
        # otherwise GraphViz uses the node ID as the label which is unlikely
        # to be what the user wants to see in the graph
        if label.startswith("<") or htmloutput:
            text += ' label=<%s>'       % label
        else:
            text += ' label="%s"'       % label

        if url:
            text += ' URL="%s"'         % url

        text += " ]"
        self.write('  _%s %s;\n' % (node_id, text))

    def start_subgraph(self, graph_id):
        """ Opens a subgraph which is used to keep together related nodes on the graph """
        self.write('  subgraph cluster_%s\n' % graph_id)
        self.write('  {\n')
        self.write('  style="invis";\n') # no border around subgraph (#0002176)
    
    def end_subgraph(self):
        """ Closes a subgraph section """
        self.write('  }\n')

    def write(self, text):
        """ Write text to the dot file """
        self.dot.write(text.encode('utf8', 'xmlcharrefreplace'))

    def get_dot(self):
        return self.dot.getvalue()
