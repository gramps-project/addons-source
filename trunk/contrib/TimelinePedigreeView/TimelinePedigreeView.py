# -*- python -*-
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2001-2007  Donald N. Allingham, Martin Hawlisch
# Copyright (C) 2009       Felix Heß <xilef@nurfuerspam.de>
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

# $Id: TimelinePedigreeView.py 13881 2009-12-21 13:43:50Z flix007 $

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from gen.utils.trans import get_addon_translator
_ = get_addon_translator().gettext
ngettext = get_addon_translator().ngettext
from cgi import escape
import math

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
import gtk
from gen.constfunc import is_quartz
if is_quartz():
    cairo_available = False
else:
    try:
        import cairo
        cairo_available = True
    except:
        cairo_available = False

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
import gen.lib
from gui.views.navigationview import NavigationView
from gen.display.name import displayer as name_displayer
from gen.utils.alive import probably_alive
from Utils import find_children, find_parents, find_witnessed_people
from gen.utils.file import media_path_full
from gen.utils import get_birth_or_fallback, get_death_or_fallback
from libformatting import FormattingHelper
from gui.thumbnails import get_thumbnail_path
from gen.errors import WindowActiveError
from gui.editors import EditPerson, EditFamily
from gui.ddtargets import DdTargets
import cPickle as pickle
from gen.config import config
from gui.views.bookmarks import PersonBookmarks
import const
from gui.dialog import RunDatabaseRepair, ErrorDialog

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------
_PERSON = "p"
_BORN = _('short for born|b.')
_DIED = _('short for died|d.')
_BAPT = _('short for baptized|bap.')
_CHRI = _('short for chistianized|chr.')
_BURI = _('short for buried|bur.')
_CREM = _('short for cremated|crem.')


class _PersonBoxWidgetOld(gtk.Button):
    """Old widget used before revision #5646"""
    def __init__(self, format_helper, person, maxlines, image=None):
        if person:
            gtk.Button.__init__(self,
                                format_helper.format_person(person, maxlines))
            gender = person.get_gender()
            if gender == gen.lib.Person.MALE:
                self.modify_bg(gtk.STATE_NORMAL,
                               self.get_colormap().alloc_color("#F5FFFF"))
            elif gender == gen.lib.Person.FEMALE:
                self.modify_bg(gtk.STATE_NORMAL,
                               self.get_colormap().alloc_color("#FFF5FF"))
            else:
                self.modify_bg(gtk.STATE_NORMAL,
                               self.get_colormap().alloc_color("#FFFFF5"))
        else:
            gtk.Button.__init__(self, "               ")
            #self.set_sensitive(False)
        self.format_helper = format_helper
        self.image = image
        self.set_alignment(0.0, 0.0)
        white = self.get_colormap().alloc_color("white")
        self.modify_bg(gtk.STATE_ACTIVE, white)
        self.modify_bg(gtk.STATE_PRELIGHT, white)
        self.modify_bg(gtk.STATE_SELECTED, white)


class _PersonWidgetBase:
    """
    Default set up for person widgets.
    Set up drag options and button release events.
    """
    def __init__(self, view, format_helper, person):
        self.view = view
        self.format_helper = format_helper
        self.person = person
        self.force_mouse_over = False
        if self.person:
            self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
            self.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
            self.connect("button-release-event", self.on_button_release_cb)
            self.connect("drag_data_get", self.drag_data_get)
            self.connect("drag_begin", self.drag_begin_cb)
            # Enable drag
            self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                                [DdTargets.PERSON_LINK.target()]+
                                [t.target() for t in DdTargets._all_text_types],
                                gtk.gdk.ACTION_COPY)

    def drag_begin_cb(self, widget, data):
        """Set up some inital conditions for drag. Set up icon."""
        self.drag_source_set_icon_stock('gramps-person')

    def drag_data_get(self, widget, context, sel_data, info, time):
        """
        Returned parameters after drag.
        Specified for 'person-link', for others return text info about person.
        """
        if sel_data.target == DdTargets.PERSON_LINK.drag_type:
            data = (DdTargets.PERSON_LINK.drag_type,
                    id(self), self.person.get_handle(), 0)
            sel_data.set(sel_data.target, 8, pickle.dumps(data))
        else:
            sel_data.set(sel_data.target, 8,
                         self.format_helper.format_person(self.person, 11))

    def on_button_release_cb(self, widget, event):
        """
        Default action for release event from mouse.
        Change active person to current.
        """
        if event.button == 1 and event.type == gtk.gdk.BUTTON_RELEASE:
            self.view.on_childmenu_changed(None, self.person.get_handle())
            return True
        return False


class PersonBoxWidgetCairo(gtk.DrawingArea, _PersonWidgetBase):
    """Draw person box using cairo library"""
    def __init__(self, view, format_helper, person, alive, maxlines, image=None):
        gtk.DrawingArea.__init__(self)
        _PersonWidgetBase.__init__(self, view, format_helper, person)
        # Required for popup menu
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        # Required for tooltip and mouse-over
        self.add_events(gtk.gdk.ENTER_NOTIFY_MASK)
        # Required for tooltip and mouse-over
        self.add_events(gtk.gdk.LEAVE_NOTIFY_MASK)
        self.alive = alive
        self.maxlines = maxlines
        self.hightlight = False
        self.connect("expose_event", self.expose)
        self.connect("realize", self.realize)
        self.text = ""
        if self.person:
            self.text = self.format_helper.format_person(self.person, self.maxlines, True)
            if alive and self.person.get_gender() == gen.lib.Person.MALE:
                self.bgcolor = (185/256.0, 207/256.0, 231/256.0)
                self.bordercolor = (32/256.0, 74/256.0, 135/256.0)
            elif alive and self.person.get_gender() == gen.lib.Person.FEMALE:
                self.bgcolor = (255/256.0, 205/256.0, 241/256.0)
                self.bordercolor = (135/256.0, 32/256.0, 106/256.0)
            elif alive:
                self.bgcolor = (244/256.0, 220/256.0, 183/256.0)
                self.bordercolor = (143/256.0, 89/256.0, 2/256.0)
            elif self.person.get_gender() == gen.lib.Person.MALE:
                self.bgcolor = (185/256.0, 207/256.0, 231/256.0)
                self.bordercolor = (0, 0, 0)
            elif self.person.get_gender() == gen.lib.Person.FEMALE:
                self.bgcolor = (255/256.0, 205/256.0, 241/256.0)
                self.bordercolor = (0, 0, 0)
            else:
                self.bgcolor = (244/256.0, 220/256.0, 183/256.0)
                self.bordercolor = (0, 0, 0)
        else:
            self.bgcolor = (211/256.0, 215/256.0, 207/256.0)
            self.bordercolor = (0, 0, 0)
        self.image = image
        try:
            self.img_surf = cairo.ImageSurface.create_from_png(image)
        except:
            self.image = False
        # enable mouse-over
        self.connect("enter-notify-event", self.on_enter_cb)
        # enable mouse-out
        self.connect("leave-notify-event", self.on_leave_cb)
        self.set_size_request(120, 25)
        # GTK object use in realize and expose methods
        self.context = None
        self.textlayout = None

    def on_enter_cb(self, widget, event):
        """On mouse-over highlight border"""
        if self.person or self.force_mouse_over:
            self.hightlight = True
            self.queue_draw()

    def on_leave_cb(self, widget, event):
        """On mouse-out normal border"""
        self.hightlight = False
        self.queue_draw()

    def realize(self, widget):
        """
        Necessary actions when the widget is instantiated on a particular
        display. Print text and resize element.
        """
        self.context = self.window.cairo_create()
        self.textlayout = self.context.create_layout()
        self.textlayout.set_font_description(self.get_style().font_desc)
        self.textlayout.set_markup(self.text)
        size = self.textlayout.get_pixel_size()
        xmin = size[0] + 12
        ymin = size[1] + 11
        if self.image:
            xmin += self.img_surf.get_width()
            ymin = max(ymin, self.img_surf.get_height()+4)
        self.set_size_request(max(xmin, 120), max(ymin, 25))

    def expose(self, widget, event):
        """
        Redrawing the contents of the widget.
        Creat new cairo object and draw in it all (borders, background and etc.)
        witout text.
        """
        alloc = self.get_allocation()
        self.context = self.window.cairo_create()

        # widget area for debugging
        #self.context.rectangle(0, 0, alloc.width, alloc.height)
        #self.context.set_source_rgb(1, 0, 1)
        #self.context.fill_preserve()
        #self.context.stroke()

        # Create box shape and store path
        self.context.move_to(0, 5)
        self.context.curve_to(0, 2, 2, 0, 5, 0)
        self.context.line_to(alloc.width-8, 0)
        self.context.curve_to(alloc.width-5, 0,
                              alloc.width-3, 2,
                              alloc.width-3, 5)
        self.context.line_to(alloc.width-3, alloc.height-8)
        self.context.curve_to(alloc.width-3, alloc.height-5,
                              alloc.width-5, alloc.height-3,
                              alloc.width-8, alloc.height-3)
        self.context.line_to(5, alloc.height-3)
        self.context.curve_to(2, alloc.height-3,
                              0, alloc.height-5,
                              0, alloc.height-8)
        self.context.close_path()
        path = self.context.copy_path()

        # shadow
        self.context.save()
        self.context.translate(3, 3)
        self.context.new_path()
        self.context.append_path(path)
        self.context.set_source_rgba(*(self.bordercolor[:3] + (0.4,)))
        self.context.fill_preserve()
        self.context.set_line_width(0)
        self.context.stroke()
        self.context.restore()

        # box shape used for clipping
        self.context.append_path(path)
        self.context.clip()

        # background
        self.context.append_path(path)
        self.context.set_source_rgb(*self.bgcolor[:3])
        self.context.fill_preserve()
        self.context.stroke()

        # image
        if self.image:
            self.context.set_source_surface(self.img_surf,
                alloc.width-4-self.img_surf.get_width(), 1)
            self.context.paint()

        # text
        self.context.move_to(5, 4)
        self.context.set_source_rgb(0, 0, 0)
        self.context.show_layout(self.textlayout)

        # text extents
        #self.context.set_source_rgba(1, 0, 0, 0.5)
        #s = self.textlayout.get_pixel_size()
        #self.context.set_line_width(1)
        #self.context.rectangle(5.5, 4.5, s[0]-1, s[1]-1)
        #self.context.stroke()

        # Mark deceased
        if self.person and not self.alive:
            self.context.set_line_width(2)
            self.context.move_to(0, 10)
            self.context.line_to(10, 0)
            self.context.stroke()

        #border
        if self.hightlight:
            self.context.set_line_width(5)
        else:
            self.context.set_line_width(2)
        self.context.append_path(path)
        self.context.set_source_rgb(*self.bordercolor[:3])
        self.context.stroke()

class PersonBoxWidget(gtk.DrawingArea, _PersonWidgetBase):
    """
    Draw person box using GC library.
    For version PyGTK < 2.8
    """
    def __init__(self, view, format_helper, person, alive, maxlines, image=None):
        gtk.DrawingArea.__init__(self)
        _PersonWidgetBase.__init__(self, view, format_helper, person)
                        # Required for popup menu and other right mouse button click
        self.add_events(gtk.gdk.BUTTON_PRESS_MASK
                        | gtk.gdk.BUTTON_RELEASE_MASK
                        # Required for tooltip and mouse-over
                        | gtk.gdk.ENTER_NOTIFY_MASK
                        # Required for tooltip and mouse-over
                        | gtk.gdk.LEAVE_NOTIFY_MASK)
        self.maxlines = maxlines
        self.alive = alive
        try:
            self.image = gtk.gdk.pixbuf_new_from_file(image)
        except:
            self.image = None
        self.connect("expose_event", self.expose)
        self.connect("realize", self.realize)
        text = ""
        if self.person:
            text = self.format_helper.format_person(self.person, self.maxlines)
            # enable mouse-over
            self.connect("enter-notify-event", self.on_enter_cb)
            self.connect("leave-notify-event", self.on_leave_cb)
        self.textlayout = self.create_pango_layout(text)
        size = self.textlayout.get_pixel_size()
        xmin = size[0] + 12
        ymin = size[1] + 11
        if self.image:
            xmin += self.image.get_width()
            ymin = max(ymin, self.image.get_height()+4)
        self.set_size_request(max(xmin, 120), max(ymin, 25))
        # GTK object use in realize and expose methods
        self.bg_gc = None
        self.text_gc = None
        self.border_gc = None
        self.shadow_gc = None

    def on_enter_cb(self, widget, event):
        """On mouse-over highlight border"""
        self.border_gc.line_width = 3
        self.queue_draw()

    def on_leave_cb(self, widget, event):
        """On mouse-out normal border"""
        self.border_gc.line_width = 1
        self.queue_draw()

    def realize(self, widget):
        """
        Necessary actions when the widget is instantiated on a particular
        display. Creat all elements for person box(bg_gc, text_gc, border_gc,
        shadow_gc), and setup they style.
        """
        self.bg_gc = self.window.new_gc()
        self.text_gc = self.window.new_gc()
        self.border_gc = self.window.new_gc()
        self.border_gc.line_style = gtk.gdk.LINE_SOLID
        self.border_gc.line_width = 1
        self.shadow_gc = self.window.new_gc()
        self.shadow_gc.line_style = gtk.gdk.LINE_SOLID
        self.shadow_gc.line_width = 4
        if self.person:
            if self.alive and self.person.get_gender() == gen.lib.Person.MALE:
                self.bg_gc.set_foreground(
                    self.get_colormap().alloc_color("#b9cfe7"))
                self.border_gc.set_foreground(
                    self.get_colormap().alloc_color("#204a87"))
            elif self.person.get_gender() == gen.lib.Person.MALE:
                self.bg_gc.set_foreground(
                    self.get_colormap().alloc_color("#b9cfe7"))
                self.border_gc.set_foreground(
                    self.get_colormap().alloc_color("#000000"))
            elif self.alive and \
                self.person.get_gender() == gen.lib.Person.FEMALE:
                self.bg_gc.set_foreground(
                    self.get_colormap().alloc_color("#ffcdf1"))
                self.border_gc.set_foreground(
                    self.get_colormap().alloc_color("#87206a"))
            elif self.person.get_gender() == gen.lib.Person.FEMALE:
                self.bg_gc.set_foreground(
                    self.get_colormap().alloc_color("#ffcdf1"))
                self.border_gc.set_foreground(
                    self.get_colormap().alloc_color("#000000"))
            elif self.alive:
                self.bg_gc.set_foreground(
                    self.get_colormap().alloc_color("#f4dcb7"))
                self.border_gc.set_foreground(
                    self.get_colormap().alloc_color("#8f5902"))
            else:
                self.bg_gc.set_foreground(
                    self.get_colormap().alloc_color("#f4dcb7"))
                self.border_gc.set_foreground(
                    self.get_colormap().alloc_color("#000000"))
        else:
            self.bg_gc.set_foreground(
                self.get_colormap().alloc_color("#eeeeee"))
            self.border_gc.set_foreground(
                self.get_colormap().alloc_color("#777777"))
        self.shadow_gc.set_foreground(
            self.get_colormap().alloc_color("#999999"))


    def expose(self, widget, event):
        """
        Redrawing the contents of the widget.
        Drawing borders and person info on exist elements.
        """
        alloc = self.get_allocation()
        # shadow
        self.window.draw_line(self.shadow_gc, 3, alloc.height-1,
                              alloc.width, alloc.height-1)
        self.window.draw_line(self.shadow_gc, alloc.width-1, 3,
                              alloc.width-1, alloc.height)
        # box background
        self.window.draw_rectangle(self.bg_gc, True, 1, 1,
                                   alloc.width-5, alloc.height-5)
        # text
        if self.person:
            self.window.draw_layout(self.text_gc, 5, 4, self.textlayout)
        # image
        if self.image:
            self.window.draw_pixbuf(self.text_gc, self.image, 0, 0,
                                    alloc.width-4-self.image.get_width(), 1)
        # border
        if self.border_gc.line_width > 1:
            self.window.draw_rectangle(self.border_gc, False, 1, 1,
                                       alloc.width-6, alloc.height-6)
        else:
            self.window.draw_rectangle(self.border_gc, False, 0, 0,
                                       alloc.width-4, alloc.height-4)

#-------------------------------------------------------------------------
#
# PedigreeView
#
#-------------------------------------------------------------------------
class TimelinePedigreeView(NavigationView):
    """
    View for a timeline pedigree.
    Displays the ancestors and descendants of a selected individual.
    """

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(self, _('Timeline pedigree'),
                                      pdata, dbstate, uistate, 
                                      dbstate.db.get_bookmarks(), 
                                      PersonBookmarks,
                                      nav_group)

        self.func_list = {
            'F2' : self.kb_goto_home,
            'F3' : self.kb_change_style,
            'F4' : self.kb_change_direction,
            'F6' : self.kb_plus_generation,
            'F5' : self.kb_minus_generation,
            '<CONTROL>J' : self.jump,
            }

        self.dbstate = dbstate
        self.dbstate.connect('database-changed', self.change_db)

        self.additional_uis.append(self.additional_ui())

        # Tree Dimensions
        self.generations_in_tree = [3, 4]
        
        # Define configuration settings
        self.cman = config.register_manager("timelinepedigreeview")
        self.cman.register("interface.show-images", False)
        self.cman.register("interface.show-marriage", False)
        self.cman.register("interface.use-timeline", True)
        self.cman.register("interface.show-lifespan", True)
        self.cman.register("interface.scroll-direction", True)
        self.cman.register("interface.ancestor-size", 4)
        self.cman.register("interface.descendant-size", 3)
        
        self.cman.register("interface.tree-size", 5)
        self.cman.register("interface.layout", 0)
        self.cman.register("interface.tree-direction", 0)
        self.cman.register("interface.show-unknown-people", False)
        self.cman.init()

        # Show photos of persons
        self.show_images = self.cman.get('interface.show-images')
        # Hide marriage data by default
        self.show_marriage_data = self.cman.get('interface.show-marriage')
        # Position the person in the timeline
        self.use_timeline = self.cman.get('interface.use-timeline')
        # Show the lifespan of the person
        self.show_lifespan = self.cman.get('interface.show-lifespan')
        # Change or nor mouse whell scroll direction
        self.scroll_direction = self.cman.get('interface.scroll-direction')
        # Number of ancestor generations to display
        self.generations_in_tree[1] = self.cman.get('interface.ancestor-size')
        # Number of descendant generations to display
        self.generations_in_tree[0] = self.cman.get('interface.descendant-size')

        # Automatic resize
        self.force_size = self.cman.get('interface.tree-size') 
        # Nice tree
        self.tree_style = self.cman.get('interface.layout')
        # Tree draw direction
        self.tree_direction = self.cman.get('interface.tree-direction')
        # Show on not unknown peoples.
        # Default - not show, for mo fast display hight tree
        self.show_unknown_peoples = self.cman.get('interface.show-unknown-people')
        
        self.format_helper = FormattingHelper(self.dbstate)
        
        # Depth of tree.
        self._depth = 1
        # Variables for drag and scroll
        self._last_x = 0
        self._last_y = 0
        self._in_move = False
        self.key_active_changed = None
        # GTK objects
        self.scrolledwindow = None
        self.table = None
        self.gtklayout = None
        self.gtklayout_lines = []
        self.gtklayout_boxes = []
        self._birth_cache = {}

    def on_delete(self):
        """Save the configuration settings on shutdown."""
        NavigationView.on_delete(self)
        self.cman.save()

    def change_page(self):
        """Called when the page changes."""
        NavigationView.change_page(self)
        self.uistate.clear_filter_results()

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
        Builds the interface and returns a gtk.Container type that
        contains the interface. This containter will be inserted into
        a gtk.ScrolledWindow page.
        """
        self.scrolledwindow = gtk.ScrolledWindow(None, None)
        self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                                       gtk.POLICY_AUTOMATIC)
        self.scrolledwindow.add_events(gtk.gdk.SCROLL_MASK)
        self.scrolledwindow.connect("scroll-event", self.bg_scroll_event)

        self.gtklayout = gtk.Layout(None, None)
        # Required for drag-scroll events and popup menu
        self.gtklayout.add_events(gtk.gdk.BUTTON_PRESS_MASK
                             | gtk.gdk.BUTTON_RELEASE_MASK
                             | gtk.gdk.BUTTON1_MOTION_MASK)
        
        self.gtklayout.connect("expose_event", self.gtklayout_expose)
        self.gtklayout.connect("button-press-event", self.bg_button_press_cb)
        self.gtklayout.connect("button-release-event", self.bg_button_release_cb)
        self.gtklayout.connect("motion-notify-event", self.bg_motion_notify_event_cb)

        #self.table = gtk.Table(1, 1, False)
        #self.table.set_row_spacings(0)
        #self.table.set_col_spacings(0)

        #event_box.add(self.table)
        #event_box.add(self.gtklayout)        
        #event_box.get_parent().set_shadow_type(gtk.SHADOW_NONE)
        #self.scrolledwindow.add_with_viewport(event_box)
        
        self.scrolledwindow.add(self.gtklayout)

        return self.scrolledwindow

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
              <menuitem action="FilterEdit"/>
            </menu>
            <menu action="BookMenu">
              <placeholder name="AddEditBook">
                <menuitem action="AddBook"/>
                <menuitem action="EditBook"/>
              </placeholder>
            </menu>
          </menubar>
          <toolbar name="ToolBar">
            <placeholder name="CommonNavigation">
              <toolitem action="Back"/>
              <toolitem action="Forward"/>
              <toolitem action="HomePerson"/>
            </placeholder>
          </toolbar>
        </ui>'''

    def define_actions(self):
        """
        Required define_actions function for PageView. Builds the action
        group information required. We extend beyond the normal here,
        since we want to have more than one action group for the PersonView.
        Most PageViews really won't care about this.

        Special action groups for Forward and Back are created to allow the
        handling of navigation buttons. Forward and Back allow the user to
        advance or retreat throughout the history, and we want to have these
        be able to toggle these when you are at the end of the history or
        at the beginning of the history.
        """
        NavigationView.define_actions(self)
        
        self._add_action('FilterEdit',  None, _('Person Filter Editor'), 
                        callback=self.filter_editor)

    def filter_editor(self, obj):
        from FilterEditor import FilterEditor

        try:
            FilterEditor('Person', const.CUSTOM_FILTERS, 
                         self.dbstate, self.uistate)
        except WindowActiveError:
            return

    def build_tree(self):
        """
        This is called by the parent class when the view becomes visible. Since
        all handling of visibility is now in Tree_Rebuild, see that for more
        information.
        """
        try:
            self.Tree_Rebuild()
        except AttributeError, msg:
            RunDatabaseRepair(str(msg))

    def change_db(self, db):
        """
        Callback associated with DbState. Whenever the database
        changes, this task is called. In this case, we rebuild the
        columns, and connect signals to the connected database. Tree
        is no need to store the database, since we will get the value
        from self.state.db
        """
        db.connect('person-add', self.person_rebuild)
        db.connect('person-update', self.person_rebuild)
        db.connect('person-delete', self.person_rebuild)
        db.connect('person-rebuild', self.person_rebuild_bm)
        db.connect('family-update', self.person_rebuild)
        db.connect('family-add', self.person_rebuild)
        db.connect('family-delete', self.person_rebuild)
        db.connect('family-rebuild', self.person_rebuild)
        self.bookmarks.update_bookmarks(self.dbstate.db.get_bookmarks())
        if self.active:
            self.bookmarks.redraw()
        self.build_tree()

    def navigation_type(self):
        return 'Person'

    def goto_handle(self, handle=None):
        """Callback function for change active person in other GRAMPS page."""
        self.dirty = True
        self.Tree_Rebuild()
        self.uistate.modify_statusbar(self.dbstate)

    def person_rebuild_bm(self, dummy=None):
        """Large change to person database"""
        self.person_rebuild(dummy)
        if self.active:
            self.bookmarks.redraw()

    def person_rebuild(self, dummy=None):
        """Callback function for signals of change database."""
        self.format_helper.clear_cache()
        self.dirty = True
        self.Tree_Rebuild()

    def Tree_Rebuild(self):
        """ 
        Build and draw full tree from the database with root person_handle
        Called from many fuctions, when need a full redraw of the tree.
        """
        
        self.dirty = False

        person = None
        if self.get_active():
            person_handle = self.get_active()
            if person_handle:
                person = self.dbstate.db.get_person_from_handle(person_handle)
        if person is None:
            return
        
        layout_widget = self.gtklayout
        
        generations = self.generations_in_tree       # Descendant and Ancestor generations
        
        # Purge current view content
        self.gtklayout_lines = []
        self.gtklayout_boxes = []
        for child in layout_widget.get_children():
            child.destroy()
        
        layout_widget.set_size(600, 600)        # set it to a dummy size
        
        # Create PersonBoxes, do calculations later needed for positioning
        LstDescendants = self.Tree_Find_Relatives(layout_widget, person, 0, generations[0], 1)
        LstAncestors   = self.Tree_Find_Relatives(layout_widget, person, 0, generations[1], -1, LstDescendants[1])
        # print "LstDescendants[0] is " + name_displayer.display(LstDescendants[0])
        
        TimeLineHeight = 0
        if self.use_timeline:
            TimeLineHeight = 40
        
        ActivePersonX = 10 + max(LstAncestors[2][2], LstDescendants[2][0]) + 10
        ActivePersonY = TimeLineHeight + max( LstAncestors[2][4], LstDescendants[2][4])
        A_Top = ActivePersonY - LstAncestors[2][4]
        D_Top = ActivePersonY - LstDescendants[2][4]
        
        RequiredHeight = max(A_Top+LstAncestors[2][1], D_Top+LstDescendants[2][1])
        RequiredWidth  = 10 + LstAncestors[2][0] + ActivePersonX
        
        # The required size is known now
        layout_widget.set_size(RequiredWidth, RequiredHeight)
        
        if True:    # Draw Border of the layout for debugging
            self.gtklayout_lines.append([1,1,1, RequiredHeight-1])
            self.gtklayout_lines.append([1,1, RequiredWidth-1, 1])
            self.gtklayout_lines.append([RequiredWidth-1,RequiredHeight-1, RequiredWidth-1, 1])
            self.gtklayout_lines.append([RequiredWidth-1,RequiredHeight-1, 1, RequiredHeight-1])
        
        # Move boxes to their desired position, draw connection lines, etc.
        self.Tree_MoveBranchBoxes(layout_widget, LstAncestors,   ActivePersonX, A_Top, -1, 0)
        self.Tree_MoveBranchBoxes(layout_widget, LstDescendants, ActivePersonX, D_Top, 1, 0)
        
        # Draw time line at top
        # FIXME see bug #5148
        # hardcoded gregorian calendar
        # cal = config.get('preferences.calendar-format-report')
        if self.use_timeline and self.Tree_EstimateBirth( LstDescendants[0]):
            self.gtklayout_lines.append([10, 3*TimeLineHeight/4, RequiredWidth-10, 3*TimeLineHeight/4, 1])
            Pos50 = ActivePersonX + ( self.Tree_EstimateBirth( LstDescendants[0] ).to_calendar("gregorian").get_year() - 1950 ) * 11
            Ticks = [ [1950, Pos50] ]
            for k in range(1,10):
                Ticks.append( [1950 + k*50, Pos50 - k * 11 * 50] )          # 50 year - tick
                Ticks.append( [1950 - k*50, Pos50 + k * 11 * 50] )
                for i in range(1,9):
                    Ticks.append( [None, Pos50 - ((k-1)*50 + i*10) * 11 ] )      # 10 year - tick
                    Ticks.append( [None, Pos50 + ((k-1)*50 + i*10) * 11 ] )
                
            for Tick in Ticks:
                if Tick[1] > 0 and Tick[1] < RequiredWidth:
                    self.gtklayout_lines.append([Tick[1], int(5*TimeLineHeight/8), Tick[1], int(7*TimeLineHeight/8), 1])
                    if Tick[0]:
                        label = gtk.Label(Tick[0])
                        label.set_justify(gtk.JUSTIFY_CENTER)
                        layout_widget.put(label, int(Tick[1]-label.size_request()[0]/2), 1*TimeLineHeight/4)
            
        
        layout_widget.show_all()
        layout_widget.queue_draw()      # widget needs redraw for connection lines
        
    def Tree_MoveBranchBoxes(self, layout_widget, BranchData, BoxRight, BranchTop, Direction, genDepth):
        """ 
            Recursively move all person boxes in a branch to its destination
        """
        BoxSizes = self.GetBoxSizes(genDepth)
        DistX = BoxSizes[2]

        if False:        # draw Branch-Border for debugging
            self.gtklayout_lines.append([BoxRight, BranchTop+1, BoxRight-Direction*BranchData[2][0], BranchTop+1])
            self.gtklayout_lines.append([BoxRight, BranchTop+BranchData[2][1]-1, BoxRight-Direction*BranchData[2][0], BranchTop+BranchData[2][1]-1])

        # Move personbox to its required position
        pbwSize = BranchData[1].size_request()
        xBox = BoxRight - pbwSize[0]
        yBox = BranchTop + BranchData[2][4]
        layout_widget.move(BranchData[1], int(xBox), int(yBox))

        # Add livespan to personbox
        if self.use_timeline and self.show_lifespan and BranchData[0] and not (Direction < 0 and genDepth == 0):
            lifespan = BranchData[5]
            try:
                color = BranchData[1].bgcolor[:3] + (0.7,)
            except AttributeError:
                color = (211/256.0, 215/256.0, 207/256.0)[:3] + (0.7,)
            self.gtklayout_boxes.append([xBox - lifespan * 11 + pbwSize[0], yBox, xBox + 5, yBox+pbwSize[1], color])   # +5 for overlapping with the box
        
        # Calculate position of connection point of this box
        yBoxConnection = yBox + BranchData[1].size_request()[1]/2
        xBoxConnection = BoxRight
        if Direction > 0:
            xBoxConnection -= pbwSize[0]
        
        # calculate x-position of vertical line
        xvline = xBoxConnection - Direction * DistX/2           # default for descendants and if date of marriage not known
        if self.use_timeline and Direction<0 and BranchData[0]:
            family_handle = BranchData[0].get_main_parents_family_handle()
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family: 
                marriagedate = self.get_date_marriage(family)
                if marriagedate:
                    mDate = marriagedate.get_date_object()
                    bDate = self.Tree_EstimateBirth(BranchData[0])
                    if bDate is not None and mDate is not None:
                        timespan = bDate.to_calendar("gregorian").get_year() - mDate.to_calendar("gregorian").get_year()
                        xvline = xBoxConnection - Direction * 11 * timespan
                    
        # Move all relatives in this branch
        ChildBranchTop = BranchTop + BranchData[2][5]
        yChildBoxConnection = [ yBoxConnection ]
        for branch in BranchData[3]:
            ChildBoxRight      = BoxRight - Direction * branch[4]
            ChildBoxConnection = self.Tree_MoveBranchBoxes(layout_widget, branch, ChildBoxRight, ChildBranchTop, Direction, genDepth+1)
            ChildBranchTop    += branch[2][1]
            yChildBoxConnection.append( ChildBoxConnection[1] )
        # Draw connection lines
            self.gtklayout_lines.append([ xvline, ChildBoxConnection[1], ChildBoxConnection[0],ChildBoxConnection[1] ])
        
        if len(BranchData[3])>0:    # There are relatives, so Connection lines must be drawn
            self.gtklayout_lines.append([ xvline, min(yChildBoxConnection), xvline, max(yChildBoxConnection) ])
            self.gtklayout_lines.append([ xBoxConnection, yBoxConnection, xvline, yBoxConnection ])
        
        # Direction<0 -> Drawing ancestors: Show Marriage Info    
        if Direction<0 and len(BranchData[3])>0 and self.show_marriage_data and BoxSizes[4] > 0:
            text = " "
            family_handle = None
            if BranchData[0]:
                family_handle = BranchData[0].get_main_parents_family_handle()
                family = self.dbstate.db.get_family_from_handle(family_handle)
                if family:
                    text = self.format_helper.format_relation( family, BoxSizes[4])
            label = gtk.Label(text)
            label.set_justify(gtk.JUSTIFY_LEFT)
            label.set_line_wrap(True)
            label.set_alignment(0.1,0.5)
            if family_handle:
                label.add_events(gtk.gdk.BUTTON_PRESS_MASK)
                label.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
                label.connect("button-press-event", self.family_button_press_cb, family_handle)
            
            layout_widget.put(label, xvline + 5, int(yBoxConnection-label.size_request()[1]/2))
        
        return [xBoxConnection, yBoxConnection]
        
    def get_date_marriage(self, family):
        for event_ref in family.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            if event and event.get_type() == gen.lib.EventType.MARRIAGE and \
            (event_ref.get_role() == gen.lib.EventRoleType.FAMILY or 
            event_ref.get_role() == gen.lib.EventRoleType.PRIMARY ):
                return event
        return None


    def GetBoxSizes(self, genDepth):
        BoxHeight = 50
        BoxWidth = 120
        DistX = 50
        DistY = 14
        MarriageLines = 3
        BoxMaxLines = 5
        
        if genDepth > 1:
            MarriageLines = 1
            
        if genDepth > 2:            
            BoxMaxLines = 3
        
        if genDepth > 3:
            BoxHeight = 10
            BoxMaxLines = 1
        
        return [BoxHeight, BoxWidth, DistX, DistY, MarriageLines, BoxMaxLines]
    
    def Tree_Create_PersonBox( self, layout_widget, person, x, y, maxlines, Relative):
        # Get foto
        image = None
        if person:
            if maxlines>3 and self.show_images: # and i < ((len(positions)-1)/2) and  positions[i][0][3] > 1:
                media_list = person.get_media_list()
                if media_list:
                    photo = media_list[0]
                    object_handle = photo.get_reference_handle()
                    obj = self.dbstate.db.get_object_from_handle(object_handle)
                    if obj:
                        mtype = obj.get_mime_type()
                        if mtype and mtype[0:5] == "image":
                            image = get_thumbnail_path(
                                        media_path_full(
                                                    self.dbstate.db,
                                                    obj.get_path()),
                                        rectangle=photo.get_rectangle())

            try:
                alive = probably_alive(person, self.dbstate.db)
            except RuntimeError:
                ErrorDialog(_('Relationship loop detected'),
                            _('A person was found to be his/her own ancestor.'))
                alive = False
        else:
            alive = True

        if cairo_available:
            pbw = PersonBoxWidgetCairo( self, self.format_helper, person, alive, maxlines, image);
        else:
            pbw = PersonBoxWidget( self, self.format_helper, person, alive, maxlines, image);
        if maxlines < 7:
            pbw.set_tooltip_text(self.format_helper.format_person(person, 11))

        if person:
            pbw.connect("button-press-event", self.person_button_press_cb, person.get_handle(), None)
        elif Relative:
            family_handle = Relative.get_main_parents_family_handle()
            if not self.dbstate.db.readonly:
                pbw.connect("button-press-event",
                            self.missing_parent_button_press_cb,
                            Relative.get_handle(), family_handle)
                pbw.force_mouse_over = True
        layout_widget.put(pbw, x, y)
        #table_widget.attach(pbw,x,x+w,y,y+h,gtk.FILL,gtk.FILL,0,0)
        
        return pbw
    
    def Tree_Find_Relatives(self, layout_widget, person, genDepth, genMax, Direction, Widget = None, CalledFromPerson = None):
        """ 
            Recursively find descendants or ancestors
            Create PersonBox-Widget
            Calculate height of each tree branch
            Calculate width of each tree branch
        """
        RelPersons = []                                 # depending on Direction find descendants / ancestors
        if genMax-genDepth > 0 and Direction > 0:       # find descendants
            if person:
                family_handles = person.get_family_handle_list()
                for family_handle in family_handles:
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family is not None:
                        for child_ref in family.get_child_ref_list():
                            child = self.dbstate.db.get_person_from_handle(child_ref.ref)
                            if child is not None:
                                RelPersons.append(child)

        elif genMax-genDepth > 0 and Direction < 0:     # find ancestors
            if person:
                family_handle = person.get_main_parents_family_handle()
                family = self.dbstate.db.get_family_from_handle(family_handle)
                if family is not None:
                    father_handle = family.get_father_handle()
                    if father_handle is not None:
                        RelPersons.append(self.dbstate.db.get_person_from_handle(father_handle))
                    else:
                        RelPersons.append(None)
                    mother_handle = family.get_mother_handle()
                    if mother_handle is not None:
                        RelPersons.append(self.dbstate.db.get_person_from_handle(mother_handle))
                    else:
                        RelPersons.append(None) 
                else:
                    RelPersons.append(None)
                    RelPersons.append(None)
        
        BoxSizes = self.GetBoxSizes(genDepth)
        DistX = BoxSizes[2]
        DistY = BoxSizes[3]
        BoxMaxLines = BoxSizes[5]
        
        if Widget:
            pbw = Widget
        else:
            pbw = self.Tree_Create_PersonBox( layout_widget, person, 100, 100, BoxMaxLines, CalledFromPerson)
        
        pbwSize = pbw.size_request()
        
        birthyear = None
        birthdate = self.Tree_EstimateBirth(person)
        if birthdate:
            birthyear = birthdate.to_calendar("gregorian").get_year()
            
        # Calculate lifespan
        lifespan = 0
        if self.show_lifespan and person:
            death = get_death_or_fallback(self.dbstate.db, person)
            if death:
                deathdate = death.get_date_object()
                lifespan = deathdate.to_calendar("gregorian").get_year() - birthdate.to_calendar("gregorian").get_year()
        
        negWidth = 11 * lifespan
        
        Branch_Width = 0
        if Direction > 0:
            Branch_Width = pbwSize[0]
               
        Child_Branch_Height = 0
        RelLst = []
        MaxRelWidth = 0
        yRelBranchTop = 0
        yRelConnect = []
        for Relative in RelPersons:
            Ret = self.Tree_Find_Relatives(layout_widget, Relative, genDepth+1, genMax, Direction, None, person)
            if Ret[4] and birthyear:
                DeltaX =  int(11 * abs( Ret[4]-birthyear ))
            else:
                DeltaX = 220
            Child_Branch_Height += Ret[2][1]
            Branch_Width  = max(Branch_Width, Ret[2][0] + DeltaX )
            negWidth = max(negWidth, Ret[2][2] - DeltaX)
            Ret[4] = DeltaX
            RelLst.append(Ret);
            
            MaxRelWidth = max(MaxRelWidth, Ret[1].size_request()[0])
            
            yRelConnect.append( yRelBranchTop + Ret[2][4] + Ret[1].size_request()[1]/2 )
            yRelBranchTop = yRelBranchTop + Ret[2][1]
        
        yPersonBoxTop = DistY / 2       # y-Position of PersonBox relative to BranchTop
        if len( yRelConnect ) > 0:
            yPersonBoxTop = (max(yRelConnect) + min(yRelConnect)) / 2 - pbwSize[1]/2

        if self.use_timeline and Direction > 0:
            Branch_Width = max(Branch_Width, lifespan * 11)
        elif not self.use_timeline:
            negWidth = 0
            if Direction > 0:
                DeltaX = DistX + pbwSize[0]
            else:
                DeltaX = DistX + MaxRelWidth
            
            Branch_Width = 0
            if Direction > 0:
                Branch_Width = pbwSize[0]
            
            for Ret in RelLst:
                Branch_Width = max(Branch_Width, Ret[2][0] + DeltaX)
                Ret[4] = DeltaX
                
        Branch_Height = Child_Branch_Height
        yChildBranchTop = 0
        if yPersonBoxTop < DistY/2:
            DeltaY = DistY/2 - yPersonBoxTop
            yPersonBoxTop = DistY/2
            yChildBranchTop = DeltaY
            Branch_Height += DeltaY
        
        Branch_Height = max(Branch_Height, yPersonBoxTop + pbwSize[1] + DistY/2)
        
        return [ person, pbw, (Branch_Width, Branch_Height, negWidth, Child_Branch_Height, yPersonBoxTop, yChildBranchTop), RelLst, birthyear, lifespan ]
    
    def Tree_EstimateBirth(self, person, callerHandles = []):
        if not person:
            # print "Estimate Birth called with no person"
            return None
        
        if person.handle in self._birth_cache:
            return self._birth_cache[person.handle]
        
        callerHandleList = callerHandles[:]             # Create a copy of the list
        callerHandleList.append(person.handle)
        
        birthdate = None
        birth = get_birth_or_fallback(self.dbstate.db, person)
        if birth:
            birthdate = birth.get_date_object()
        else:
            #if len(callerHandleList) == 1:
            #    print "==== Birth estimate requested for " + name_displayer.display(person)
            #print "Estimate birthdate by looking at children of " + name_displayer.display(person)
            ChildBirthDates = []        # Estimate birth by looking at children
            family_handles = person.get_family_handle_list()
            for family_handle in family_handles:
                family = self.dbstate.db.get_family_from_handle(family_handle)
                if family is not None:
                    for child_ref in family.get_child_ref_list():
                        child = self.dbstate.db.get_person_from_handle(child_ref.ref)
                        if child is not None:
                            if child.handle not in callerHandleList:
                                childDate = self.Tree_EstimateBirth(child, callerHandleList)
                                if childDate is not None:
                                    ChildBirthDates.append(childDate)
            if len(ChildBirthDates) > 0:
                birthdate = min( ChildBirthDates ) - 25
            else:                   # Estimate by looking at parents if there was no success
                #print "Estimate birthdate by looking at parents of " + name_displayer.display(person)
                ParentDates = []
                family_handle = person.get_main_parents_family_handle()
                family = self.dbstate.db.get_family_from_handle(family_handle)
                # pdb.set_trace()
                if family is not None:
                    father_handle = family.get_father_handle()
                    if father_handle is not None and father_handle not in callerHandleList:
                        ParentDate = self.Tree_EstimateBirth(self.dbstate.db.get_person_from_handle(father_handle), callerHandleList)
                        if ParentDate is not None:
                            ParentDates.append( ParentDate )
                    mother_handle = family.get_mother_handle()
                    if mother_handle is not None and mother_handle not in callerHandleList:
                        ParentDate = self.Tree_EstimateBirth(self.dbstate.db.get_person_from_handle(mother_handle), callerHandleList)
                        if ParentDate is not None:
                            ParentDates.append( ParentDate )
                if len(ParentDates) > 0:
                    birthdate = min( ParentDates ) + 25
        
        if len(callerHandleList) == 1 and birthdate is None:
            print "Cannot estimate birth of " + name_displayer.display(person)
        
        if len(callerHandleList) == 1:
            self._birth_cache[person.handle] = birthdate
                
        #elif callerHandle == 0:
        #    print "Estimate for " + name_displayer.display(person) + " is", birthdate
        
        return birthdate
                    
    def gtklayout_expose_old(self, area, event):
        window = self.gtklayout.get_bin_window()
        size =  self.gtklayout.get_size()
        if window:
            gc = window.new_gc()
            gc.line_style = gtk.gdk.LINE_SOLID
            gc.line_width = 3
            
            for box in self.gtklayout_boxes:
                window.draw_rectangle(gc, False, int(box[0]), int(box[1]), int(box[2]-box[0]), int(box[3]-box[1]))
            for line in self.gtklayout_lines:
                if len(line) == 4:
                    gc.line_width = 3
                else:
                    gc.line_width = line[4]
                window.draw_line(gc, int(line[0]), int(line[1]), int(line[2]), int(line[3]))
   
    def gtklayout_expose(self, area, event):
        #window = self.gtklayout.get_bin_window()
        window = self.gtklayout.bin_window
        if window:   
            # Create the cairo context
            cr = window.cairo_create()

            # Restrict Cairo to the exposed area; avoid extra work
            cr.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
            cr.clip()
            
            for box in self.gtklayout_boxes:
                cr.set_source_rgba(box[4][0], box[4][1], box[4][2], box[4][3])
                cr.rectangle(int(box[0]), int(box[1]), int(box[2]-box[0]), int(box[3]-box[1]))
                cr.fill()

            cr.set_source_rgb(0.0, 0.0, 0.0)
            for line in self.gtklayout_lines:
                #if len(line) == 4:
                #    gc.line_width = 3
                #else:
                #    gc.line_width = line[4]
                cr.move_to(int(line[0]), int(line[1]))
                cr.line_to(int(line[2]), int(line[3]))
                cr.stroke()
   
   
    def home(self, menuitem):
        """Change root person to default person for database."""
        defperson = self.dbstate.db.get_default_person()
        if defperson:
            self.change_active(defperson.handle)

    def edit_person_cb(self, obj, person_handle):
        """
        Open edit person window for person_handle.
        Called after double click or from submenu.
        """
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
            return True
        return False

    def edit_family_cb(self, obj, family_handle):
        """
        Open edit person family for family_handle.
        Called after double click or from submenu.
        """
        family = self.dbstate.db.get_family_from_handle(family_handle)
        if family:
            try:
                EditFamily(self.dbstate, self.uistate, [], family)
            except WindowActiveError:
                pass
            return True
        return False

    def add_parents_cb(self, obj, person_handle, family_handle):
        """Edit not full family."""
        if family_handle:   # one parent already exists -> Edit current family
            family = self.dbstate.db.get_family_from_handle(family_handle)
        else:   # no parents -> create new family
            family = gen.lib.Family()
            childref = gen.lib.ChildRef()
            childref.set_reference_handle(person_handle)
            family.add_child_ref(childref)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def copy_person_to_clipboard_cb(self, obj, person_handle):
        """
        Renders the person data into some lines of text and
        puts that into the clipboard
        """
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(self.format_helper.format_person(person, 11))
            return True
        return False

    def copy_family_to_clipboard_cb(self, obj, family_handle):
        """
        Renders the family data into some lines of text and
        puts that into the clipboard
        """
        family = self.dbstate.db.get_family_from_handle(family_handle)
        if family:
            clipboard = gtk.clipboard_get(gtk.gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(self.format_helper.format_relation(family, 11))
            return True
        return False

    def on_show_option_menu_cb(self, obj, event, data=None):
        """Right click option menu."""
        menu = gtk.Menu()
        self.add_nav_portion_to_menu(menu)
        self.add_settings_to_menu(menu)
        menu.popup(None, None, None, 0, event.time)
        return True

    def bg_button_press_cb(self, widget, event):
        """
        Enter in scroll mode when mouse button pressed in background
        or call option menu.
        """
        if event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS:
            widget.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.FLEUR))
            self._last_x = event.x
            self._last_y = event.y
            self._in_move = True
            return True
        elif event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.on_show_option_menu_cb(widget, event)
            return True
        return False

    def bg_button_release_cb(self, widget, event):
        """Exit from scroll mode when button release."""
        if event.button == 1 and event.type == gtk.gdk.BUTTON_RELEASE:
            self.bg_motion_notify_event_cb(widget, event)
            widget.window.set_cursor(None)
            self._in_move = False
            return True
        return False

    def bg_motion_notify_event_cb(self, widget, event):
        """Function for motion notify events for drag and scroll mode."""
        if self._in_move and (event.type == gtk.gdk.MOTION_NOTIFY or \
           event.type == gtk.gdk.BUTTON_RELEASE):
            window = widget.get_parent()
            hadjustment = window.get_hadjustment()
            vadjustment = window.get_vadjustment()
            self.update_scrollbar_positions(vadjustment,
                vadjustment.value - (event.y - self._last_y))
            self.update_scrollbar_positions(hadjustment,
                hadjustment.value - (event.x - self._last_x))
            return True
        return False

    def update_scrollbar_positions(self, adjustment, value):
        """Controle value then try setup in scrollbar."""
        if value > (adjustment.upper - adjustment.page_size):
            adjustment.set_value(adjustment.upper - adjustment.page_size)
        else:
            adjustment.set_value(value)
        return True

    def bg_scroll_event(self, widget, event):
        """
        Function change scroll direction to horizontally
        if variable self.scroll_direction setup.
        """
        if self.scroll_direction and event.type == gtk.gdk.SCROLL:
            if event.direction == gtk.gdk.SCROLL_UP:
                event.direction = gtk.gdk.SCROLL_LEFT
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                event.direction = gtk.gdk.SCROLL_RIGHT
        return False
        
    def family_button_press_cb(self, obj, event, family_handle):
        """
        Call edit family function for mouse left button double click on family
        or submenu for family for mouse right click.
        And setup plug for button press on person widget.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            # self.build_full_nav_menu_cb(obj, event, person_handle, family_handle)
            print "Menu request"
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if family:
                try:
                    EditFamily(self.dbstate, self.uistate, [], family)
                except WindowActiveError:
                    pass

        return True
        
    def person_button_press_cb(self, obj, event, person_handle, family_handle):
        """
        Call edit person function for mouse left button double click on person
        or submenu for person for mouse right click.
        And setup plug for button press on person widget.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.build_full_nav_menu_cb(obj, event, person_handle, family_handle)
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.edit_person_cb(obj, person_handle)
        return True

    def relation_button_press_cb(self, obj, event, family_handle):
        """
        Call edit family function for mouse left button double click
        on family line or call full submenu for mouse right click.
        And setup plug for button press on family line.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.build_relation_nav_menu_cb(obj, event, family_handle)
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.edit_family_cb(obj, family_handle)
            return True
        return True

    def missing_parent_button_press_cb(self, obj, event,
                                       person_handle, family_handle):
        """
        Callback function for not full family for mouse left button double click
        on missing persons or call submenu for mouse right click.
        """
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.add_parents_cb(obj, person_handle, family_handle)
            return True
        elif event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.build_missing_parent_nav_menu_cb(obj, event, person_handle,
                                                  family_handle)
            return True
        return False

    def on_show_child_menu(self, obj):
        """User clicked button to move to child of active person"""
        if self.dbstate.active:
            # Build and display the menu attached to the left pointing arrow
            # button. The menu consists of the children of the current root
            # person of the tree. Attach a child to each menu item.

            childlist = find_children(self.dbstate.db, self.dbstate.active)
            if len(childlist) == 1:
                child = self.dbstate.db.get_person_from_handle(childlist[0])
                if child:
                    self.change_active(child)
            elif len(childlist) > 1:
                myMenu = gtk.Menu()
                for child_handle in childlist:
                    child = self.dbstate.db.get_person_from_handle(child_handle)
                    cname = escape(name_displayer.display(child))
                    if find_children(self.dbstate.db, child):
                        label = gtk.Label('<b><i>%s</i></b>' % cname)
                    else:
                        label = gtk.Label(cname)
                    label.set_use_markup(True)
                    label.show()
                    label.set_alignment(0, 0)
                    menuitem = gtk.ImageMenuItem(None)
                    go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                                        gtk.ICON_SIZE_MENU)
                    go_image.show()
                    menuitem.set_image(go_image)
                    menuitem.add(label)
                    myMenu.append(menuitem)
                    menuitem.connect("activate", self.on_childmenu_changed,
                                     child_handle)
                    menuitem.show()
                myMenu.popup(None, None, None, 0, 0)
            return 1
        return 0

    def on_childmenu_changed(self, obj, person_handle):
        """
        Callback for the pulldown menu selection, changing to the person
        attached with menu item.
        """
        self.change_active(person_handle)
        return True

    def change_generations_in_tree_cb(self, menuitem, i, data):
        """Change force_size option."""
        if data in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] and i in [0, 1]:
            self.generations_in_tree[i] = data
            if i:
                self.cman.set('interface.ancestor-size', data)
            else:
                self.cman.set('interface.descendant-size', data)
            self.dirty = True
            self.Tree_Rebuild()
    
    def change_show_lifespan_cb(self, menuitem):
        """Change show lifespan option."""
        self.show_lifespan = not self.show_lifespan
        self.cman.set('interface.show-lifespan', self.show_lifespan)
        self.dirty = True
        self.Tree_Rebuild()
        
    def change_use_timeline_cb(self, menuitem):
        """Change use timeline option."""
        self.use_timeline = not self.use_timeline
        self.cman.set('interface.use-timeline', self.use_timeline)
        self.dirty = True
        self.Tree_Rebuild()

    def change_tree_direction_cb(self, menuitem, data):
        """Change tree_direction option."""
        if data in [0, 1, 2, 3]:
            self.cman.set('interface.tree-direction', data)
            if self.tree_direction != data:
                self.dirty = True
                self.tree_direction = data
                self.Tree_Rebuild()

    def change_show_images_cb(self, event):
        """Change show_images option."""
        self.show_images = not self.show_images
        self.cman.set('interface.show-images', self.show_images)
        self.dirty = True
        self.Tree_Rebuild()

    def change_show_marriage_cb(self, event):
        """Change show_marriage_data option."""
        self.show_marriage_data = not self.show_marriage_data
        self.cman.set('interface.show-marriage', self.show_marriage_data)
        self.dirty = True
        self.Tree_Rebuild()

    def change_show_unknown_peoples_cb(self, event):
        """Change show_unknown_peoples option."""
        self.show_unknown_peoples = not self.show_unknown_peoples
        self.cman.set('interface.show-unknown-people', 
                    self.show_unknown_peoples)
        self.dirty = True
        self.Tree_Rebuild()

    def change_scroll_direction_cb(self, menuitem, data):
        """Change scroll_direction option."""
        self.cman.set('interface.scroll-direction', self.scroll_direction)
        if data:
            self.scroll_direction = True
        else:
            self.scroll_direction = False

    def kb_goto_home(self):
        """Goto home person from keyboard."""
        self.home(None)

    def kb_plus_generation(self):
        """Increment size of tree from keyboard."""
        self.change_force_size_cb(None, self.force_size + 1)

    def kb_minus_generation(self):
        """Decrement size of tree from keyboard."""
        self.change_force_size_cb(None, self.force_size - 1)

    def kb_change_style(self):
        """Change style of tree from keyboard."""
        next_style = self.tree_style + 1
        if next_style > 2:
            next_style = 0
        self.change_tree_style_cb(None, next_style)

    def kb_change_direction(self):
        """Change direction of tree from keyboard."""
        next_direction = self.tree_direction + 1
        if next_direction > 3:
            next_direction = 0
        self.change_tree_direction_cb(None, next_direction)

    def add_nav_portion_to_menu(self, menu):
        """
        This function adds a common history-navigation portion
        to the context menu. Used by both build_nav_menu() and
        build_full_nav_menu() methods.
        """
        #hobj = self.uistate.phistory
        #home_sensitivity = True
        #if not self.dbstate.db.get_default_person():
        #    home_sensitivity = False
        entries = [
        #    (gtk.STOCK_GO_BACK, self.back_clicked, not hobj.at_front()),
        #    (gtk.STOCK_GO_FORWARD, self.fwd_clicked, not hobj.at_end()),
            (gtk.STOCK_HOME, self.home, 1),
            (None, None, 0)
        ]

        for stock_id, callback, sensitivity in entries:
            item = gtk.ImageMenuItem(stock_id)
            item.set_sensitive(sensitivity)
            if callback:
                item.connect("activate", callback)
            item.show()
            menu.append(item)

    def add_settings_to_menu(self, menu):
        """
        Add settings to menu (Show images, Show marriage data,
        Show unknown people, Mouse scroll direction, Tree style,
        Tree size, Tree direction), marked selected items.
        Othet menu for othet styles.
        """

        menu.append(self.create_menu_item(_("Show images"), self.show_images, self.change_show_images_cb) )
        
        menu.append(self.create_menu_item(_("Show marriage data"), self.show_marriage_data, self.change_show_marriage_cb) )
        
        menu.append(self.create_menu_item(_("Order by timeline"), self.use_timeline, self.change_use_timeline_cb) )
        
        menu.append(self.create_menu_item(_("Show lifespan"), self.show_lifespan, self.change_show_lifespan_cb) )

        item = gtk.MenuItem(_("Mouse scroll direction"))
        item.set_submenu(gtk.Menu())
        scroll_direction_menu = item.get_submenu()

        scroll_direction_image = gtk.image_new_from_stock(gtk.STOCK_APPLY,
                                                       gtk.ICON_SIZE_MENU)
        scroll_direction_image.show()

        entry = gtk.ImageMenuItem(_("Top <-> Bottom"))
        entry.connect("activate", self.change_scroll_direction_cb, False)
        if self.scroll_direction == False:
            entry.set_image(scroll_direction_image)
        entry.show()
        scroll_direction_menu.append(entry)

        entry = gtk.ImageMenuItem(_("Left <-> Right"))
        entry.connect("activate", self.change_scroll_direction_cb, True)
        if self.scroll_direction == True:
            entry.set_image(scroll_direction_image)
        entry.show()
        scroll_direction_menu.append(entry)

        scroll_direction_menu.show()
        item.show()
        menu.append(item)

        
        item = gtk.MenuItem(_("Descendant Generations"))
        item.set_submenu(gtk.Menu())
        DescendantSize_menu = item.get_submenu()

        current_size_image = gtk.image_new_from_stock(gtk.STOCK_APPLY,
                                                      gtk.ICON_SIZE_MENU)
        current_size_image.show()

        for num in range(0, 10):
            entry = gtk.ImageMenuItem(ngettext("%d generation", "%d generations", num) %num)
            if self.generations_in_tree[0] == num:
                entry.set_image(current_size_image)
            entry.connect("activate", self.change_generations_in_tree_cb, 0, num)
            entry.show()
            DescendantSize_menu.append(entry)
        DescendantSize_menu.show()
        item.show()
        menu.append(item)
        
        item = gtk.MenuItem(_("Ancestor Generations"))
        item.set_submenu(gtk.Menu())
        AncestorSize_menu = item.get_submenu()

        current_size_image = gtk.image_new_from_stock(gtk.STOCK_APPLY,
                                                      gtk.ICON_SIZE_MENU)
        current_size_image.show()

        for num in range(0, 10):
            entry = gtk.ImageMenuItem(ngettext("%d generation", "%d generations", num) %num)
            if self.generations_in_tree[1] == num:
                entry.set_image(current_size_image)
            entry.connect("activate", self.change_generations_in_tree_cb, 1, num)
            entry.show()
            AncestorSize_menu.append(entry)
            
        AncestorSize_menu.show()
        item.show()
        menu.append(item)

    def create_menu_item(self, text, currValue, callback):
        entry = gtk.ImageMenuItem(text)
        if currValue:
            current_image = gtk.image_new_from_stock(gtk.STOCK_APPLY, gtk.ICON_SIZE_MENU)
            current_image.show()
            entry.set_image(current_image)
        entry.connect("activate", callback)
        entry.show()
        return entry

    def build_missing_parent_nav_menu_cb(self, obj, event,
                                         person_handle, family_handle):
        """Builds the menu for a missing parent."""
        menu = gtk.Menu()
        menu.set_title(_('People Menu'))

        add_item = gtk.ImageMenuItem(gtk.STOCK_ADD)
        add_item.connect("activate", self.add_parents_cb, person_handle,
                         family_handle)
        add_item.show()
        menu.append(add_item)

        # Add history-based navigation
        self.add_nav_portion_to_menu(menu)
        self.add_settings_to_menu(menu)
        menu.popup(None, None, None, 0, event.time)
        return 1

    def build_full_nav_menu_cb(self, obj, event, person_handle, family_handle):
        """
        Builds the full menu (including Siblings, Spouses, Children,
        and Parents) with navigation.
        """

        menu = gtk.Menu()
        menu.set_title(_('People Menu'))

        person = self.dbstate.db.get_person_from_handle(person_handle)
        if not person:
            return 0

        go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                            gtk.ICON_SIZE_MENU)
        go_image.show()
        go_item = gtk.ImageMenuItem(name_displayer.display(person))
        go_item.set_image(go_image)
        go_item.connect("activate", self.on_childmenu_changed, person_handle)
        go_item.show()
        menu.append(go_item)

        edit_item = gtk.ImageMenuItem(gtk.STOCK_EDIT)
        edit_item.connect("activate", self.edit_person_cb, person_handle)
        edit_item.show()
        menu.append(edit_item)

        clipboard_item = gtk.ImageMenuItem(gtk.STOCK_COPY)
        clipboard_item.connect("activate", self.copy_person_to_clipboard_cb,
                               person_handle)
        clipboard_item.show()
        menu.append(clipboard_item)

        # collect all spouses, parents and children
        linked_persons = []

        # Go over spouses and build their menu
        item = gtk.MenuItem(_("Spouses"))
        fam_list = person.get_family_handle_list()
        no_spouses = 1
        for fam_id in fam_list:
            family = self.dbstate.db.get_family_from_handle(fam_id)
            if family.get_father_handle() == person.get_handle():
                sp_id = family.get_mother_handle()
            else:
                sp_id = family.get_father_handle()
            spouse = self.dbstate.db.get_person_from_handle(sp_id)
            if not spouse:
                continue

            if no_spouses:
                no_spouses = 0
                item.set_submenu(gtk.Menu())
                sp_menu = item.get_submenu()

            go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                                gtk.ICON_SIZE_MENU)
            go_image.show()
            sp_item = gtk.ImageMenuItem(name_displayer.display(spouse))
            sp_item.set_image(go_image)
            linked_persons.append(sp_id)
            sp_item.connect("activate", self.on_childmenu_changed, sp_id)
            sp_item.show()
            sp_menu.append(sp_item)

        if no_spouses:
            item.set_sensitive(0)

        item.show()
        menu.append(item)

        # Go over siblings and build their menu
        item = gtk.MenuItem(_("Siblings"))
        pfam_list = person.get_parent_family_handle_list()
        no_siblings = 1
        for pfam in pfam_list:
            fam = self.dbstate.db.get_family_from_handle(pfam)
            sib_list = fam.get_child_ref_list()
            for sib_ref in sib_list:
                sib_id = sib_ref.ref
                if sib_id == person.get_handle():
                    continue
                sib = self.dbstate.db.get_person_from_handle(sib_id)
                if not sib:
                    continue

                if no_siblings:
                    no_siblings = 0
                    item.set_submenu(gtk.Menu())
                    sib_menu = item.get_submenu()

                if find_children(self.dbstate.db, sib):
                    label = gtk.Label('<b><i>%s</i></b>' % \
                        escape(name_displayer.display(sib)))
                else:
                    label = gtk.Label(escape(name_displayer.display(sib)))

                go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                                    gtk.ICON_SIZE_MENU)
                go_image.show()
                sib_item = gtk.ImageMenuItem(None)
                sib_item.set_image(go_image)
                label.set_use_markup(True)
                label.show()
                label.set_alignment(0, 0)
                sib_item.add(label)
                linked_persons.append(sib_id)
                sib_item.connect("activate", self.on_childmenu_changed, sib_id)
                sib_item.show()
                sib_menu.append(sib_item)

        if no_siblings:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

        # Go over children and build their menu
        item = gtk.MenuItem(_("Children"))
        no_children = 1
        childlist = find_children(self.dbstate.db, person)
        for child_handle in childlist:
            child = self.dbstate.db.get_person_from_handle(child_handle)
            if not child:
                continue

            if no_children:
                no_children = 0
                item.set_submenu(gtk.Menu())
                child_menu = item.get_submenu()

            if find_children(self.dbstate.db, child):
                label = gtk.Label('<b><i>%s</i></b>' % \
                    escape(name_displayer.display(child)))
            else:
                label = gtk.Label(escape(name_displayer.display(child)))

            go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                                gtk.ICON_SIZE_MENU)
            go_image.show()
            child_item = gtk.ImageMenuItem(None)
            child_item.set_image(go_image)
            label.set_use_markup(True)
            label.show()
            label.set_alignment(0, 0)
            child_item.add(label)
            linked_persons.append(child_handle)
            child_item.connect("activate", self.on_childmenu_changed,
                               child_handle)
            child_item.show()
            child_menu.append(child_item)

        if no_children:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

        # Go over parents and build their menu
        item = gtk.MenuItem(_("Parents"))
        no_parents = 1
        par_list = find_parents(self.dbstate.db, person)
        for par_id in par_list:
            par = self.dbstate.db.get_person_from_handle(par_id)
            if not par:
                continue

            if no_parents:
                no_parents = 0
                item.set_submenu(gtk.Menu())
                par_menu = item.get_submenu()

            if find_parents(self.dbstate.db, par):
                label = gtk.Label('<b><i>%s</i></b>' % \
                    escape(name_displayer.display(par)))
            else:
                label = gtk.Label(escape(name_displayer.display(par)))

            go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                                gtk.ICON_SIZE_MENU)
            go_image.show()
            par_item = gtk.ImageMenuItem(None)
            par_item.set_image(go_image)
            label.set_use_markup(True)
            label.show()
            label.set_alignment(0, 0)
            par_item.add(label)
            linked_persons.append(par_id)
            par_item.connect("activate", self.on_childmenu_changed, par_id)
            par_item.show()
            par_menu.append(par_item)

        if no_parents:
            if self.tree_style == 2 and not self.show_unknown_peoples:
                item.set_submenu(gtk.Menu())
                par_menu = item.get_submenu()
                par_item = gtk.ImageMenuItem(_("Add New Parents..."))
                par_item.connect("activate", self.add_parents_cb, person_handle,
                         family_handle)
                par_item.show()
                par_menu.append(par_item)
            else:
                item.set_sensitive(0)
        item.show()
        menu.append(item)

        # Go over parents and build their menu
        item = gtk.MenuItem(_("Related"))
        no_related = 1
        for p_id in find_witnessed_people(self.dbstate.db, person):
            #if p_id in linked_persons:
            #    continue    # skip already listed family members

            per = self.dbstate.db.get_person_from_handle(p_id)
            if not per:
                continue

            if no_related:
                no_related = 0
                item.set_submenu(gtk.Menu())
                per_menu = item.get_submenu()

            label = gtk.Label(escape(name_displayer.display(per)))

            go_image = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
                                                gtk.ICON_SIZE_MENU)
            go_image.show()
            per_item = gtk.ImageMenuItem(None)
            per_item.set_image(go_image)
            label.set_use_markup(True)
            label.show()
            label.set_alignment(0, 0)
            per_item.add(label)
            per_item.connect("activate", self.on_childmenu_changed, p_id)
            per_item.show()
            per_menu.append(per_item)

        if no_related:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

        # Add separator
        item = gtk.MenuItem(None)
        item.show()
        menu.append(item)

        # Add history-based navigation
        self.add_nav_portion_to_menu(menu)
        self.add_settings_to_menu(menu)
        menu.popup(None, None, None, 0, event.time)
        return 1

    def build_relation_nav_menu_cb(self, obj, event, family_handle):
        """Builds the menu for a parents-child relation line."""
        menu = gtk.Menu()
        menu.set_title(_('Family Menu'))

        family = self.dbstate.db.get_family_from_handle(family_handle)
        if not family:
            return 0

        edit_item = gtk.ImageMenuItem(gtk.STOCK_EDIT)
        edit_item.connect("activate", self.edit_family_cb, family_handle)
        edit_item.show()
        menu.append(edit_item)

        clipboard_item = gtk.ImageMenuItem(gtk.STOCK_COPY)
        clipboard_item.connect("activate", self.copy_family_to_clipboard_cb,
                               family_handle)
        clipboard_item.show()
        menu.append(clipboard_item)

        # Add separator
        item = gtk.MenuItem(None)
        item.show()
        menu.append(item)

        # Add history-based navigation
        self.add_nav_portion_to_menu(menu)
        self.add_settings_to_menu(menu)
        menu.popup(None, None, None, 0, event.time)
        return 1
