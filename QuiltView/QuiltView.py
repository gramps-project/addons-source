#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012-2015 Nick Hall
# Copyright (C) 2015-     Serge Noiraud
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

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import math
from time import clock

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation

_ = _trans.gettext

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango, PangoCairo

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.lib import Person
from gramps.gui.views.navigationview import NavigationView
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.errors import WindowActiveError
from gramps.gui.editors import EditPerson, EditFamily
from gramps.gen.config import config
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gen.const import CUSTOM_FILTERS
from gramps.gui.dialog import RunDatabaseRepair, ErrorDialog
from gramps.gui.utils import ProgressMeter

BORDER = 10
HEIGHT = 18

class Node(object):
    def __init__(self, handle, layer):
        self.handle = handle
        self.layer = layer
        self.x = None
        self.y = None
        self.width = 18
        self.height = 18

    def set_position(self, x, y):
        self.x = x
        self.y = y

    def get_width(self):
        return self.width

    def is_at(self, x, y):
        return (self.x < x < self.x + self.width and
                self.y < y < self.y + self.height)

    def draw(self, canvas, cr):
        pass

class PersonNode(Node):
    def __init__(self, handle, layer, name, sex):
        Node.__init__(self, handle, layer)
        self.name = name
        self.sex = sex
        self.parents = []
        self.children = []

    def add_main_family(self, family):
        self.parents.append(family)

    def add_family(self, family):
        self.children.append(family)

    def draw(self, canvas, cr):
        if self.sex == Person.MALE:
            label = '\u2642 ' + self.name
            bg_color = (0.72, 0.81, 0.90)
        elif self.sex == Person.FEMALE:
            label = '\u2640 ' + self.name
            bg_color = (1, 0.80, 0.94)
        else:
            label = '\u2650 ' + self.name
            bg_color = (0.95, 0.86, 0.71)

        layout = canvas.create_pango_layout(label)
        font = Pango.FontDescription('Sans')
        layout.set_font_description(font)
        width, height = layout.get_size()
        self.width = width / 1024

        # Set the name background depending on the sex
        cr.set_source_rgb(*bg_color)
        cr.rectangle(self.x + 1, self.y + 1, self.width - 2, self.height - 2)
        cr.fill()

        # Set the name border
        cr.set_source_rgb(0.50, 0.50, 0.50)
        cr.move_to(self.x, self.y)
        cr.line_to(self.x + self.width, self.y)
        cr.stroke()
        cr.move_to(self.x, self.y + self.height)
        cr.line_to(self.x + self.width, self.y + self.height)
        cr.stroke()

        cr.set_source_rgb(0, 0, 0)
        cr.move_to(self.x, self.y)
        PangoCairo.show_layout(cr, layout)

class FamilyNode(Node):
    def __init__(self, handle, layer, rel_type):
        Node.__init__(self, handle, layer)
        self.rel_type = rel_type
        self.parents = []
        self.children = []

    def add_parent(self, person):
        self.parents.append(person)

    def add_child(self, person):
        self.children.append(person)

    def draw(self, canvas, cr):
        cr.set_source_rgb(0.83, 0.83, 0.83)
        cr.rectangle(self.x, self.y, self.width, self.height)
        cr.fill()

        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(self.x, self.y, self.width, self.height)
        cr.stroke()

        layout = canvas.create_pango_layout('F')
        font = Pango.FontDescription('Sans')
        layout.set_font_description(font)
        width, height = layout.get_size()

        cr.set_source_rgb(0, 0, 0)
        cr.move_to(self.x, self.y)
        PangoCairo.show_layout(cr, layout)

#-------------------------------------------------------------------------
#
# QuiltView
#
#-------------------------------------------------------------------------
class QuiltView(NavigationView):
    """
    Displays a quilt chart visualisation of a family tree.
    """

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(self, _('Quilt chart'),
                                      pdata, dbstate, uistate,
                                      PersonBookmarks,
                                      nav_group)

        self.dbstate = dbstate
        self.uistate = uistate
        self.dbstate.connect('database-changed', self.change_db)

        self.additional_uis.append(self.additional_ui())

        # GTK objects
        self.scrolledwindow = None
        self.canvas = None
        self.scale = 1.0
        self._in_move = False
        self.layers = None
        self.people = []
        self.paths = []

    def get_stock(self):
        """
        The category stock icon
        """
        return 'gramps-pedigree'

    def get_viewtype_stock(self):
        """
        Type of view in category
        """
        return 'gramps-pedigree'

    def build_widget(self):
        """
        Builds the interface and returns a gtk.Container type that
        contains the interface. This containter will be inserted into
        a gtk.ScrolledWindow page.
        """
        self.scrolledwindow = Gtk.ScrolledWindow(None, None)
        self.scrolledwindow.set_policy(Gtk.PolicyType.AUTOMATIC,
                                       Gtk.PolicyType.AUTOMATIC)

        self.canvas = Gtk.DrawingArea()

        self.canvas.connect("draw", self.on_draw)
        self.canvas.connect("button-press-event", self.press_cb)
        self.canvas.connect("button-release-event", self.release_cb)
        self.canvas.connect("motion-notify-event", self.motion_notify_cb)
        self.canvas.connect("scroll-event", self.scrolled_cb)
        #self.canvas.connect("size-allocate", self.resized_cb)

        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                               Gdk.EventMask.BUTTON_RELEASE_MASK |
                               Gdk.EventMask.POINTER_MOTION_MASK |
                               Gdk.EventMask.SCROLL_MASK |
                               Gdk.EventMask.KEY_PRESS_MASK)

        self.scrolledwindow.add(self.canvas)

        self.preview_rect = None

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
              <toolitem action="Print"/>
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

        self._add_action('FilterEdit', None, _('Person Filter Editor'),
                        callback=self.filter_editor)
        self._add_action('Print', Gtk.STOCK_PRINT, _('Print the entire tree'),
                        callback=self.on_print)

    def filter_editor(self, obj):
        from gramps.gui.editors import FilterEditor
        try:
            FilterEditor('Person', CUSTOM_FILTERS,
                         self.dbstate, self.uistate)
        except WindowActiveError:
            return

    def build_tree(self):
        """
        This is called by the parent class when the view becomes visible. Since
        all handling of visibility is now in rebuild, see that for more
        information.
        """
        try:
            self.rebuild()
        except AttributeError as msg:
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
        self.bookmarks.update_bookmarks()
        if self.active:
            self.bookmarks.redraw()
        self.build_tree()

    def navigation_type(self):
        return 'Person'

    def add_bookmark(self, handle):
        if handle:
            self.uistate.set_active(handle, self.navigation_type())
            self.bookmarks.add(handle)
            self.bookmarks.redraw()
        else:
            from gramps.gui.dialog import WarningDialog
            # The following message is already translated
            WarningDialog(
                _("Could Not Set a Bookmark"),
                _("A bookmark could not be set because "
                  "no one was selected."))

    def center_on_node(self, handle):
        if handle in self.people.keys():
            node = self.people[handle]
            if node.x and node.y:
                hadjustment = self.scrolledwindow.get_hadjustment()
                vadjustment = self.scrolledwindow.get_vadjustment()
                hadj = ((node.x - 10 * math.log(node.y) ) * self.scale)
                vadj = ((node.y - 10 * math.log(node.x) ) * self.scale)
                self.update_scrollbar_positions(vadjustment, vadj)
                self.update_scrollbar_positions(hadjustment, hadj)

    def goto_handle(self, handle=None):
        if handle not in self.people.keys():
            self.rebuild()
        else:
            obj = self.people[handle]
            if obj.x is not None: # not totaly initialized.
                self.set_path_lines(self.people[handle])
        self.uistate.modify_statusbar(self.dbstate)

    def person_rebuild_bm(self, dummy=None):
        self.person_rebuild(dummy)
        if self.active:
            self.bookmarks.redraw()

    def person_rebuild(self, dummy=None):
        self.rebuild()

    def read_data(self, handle):

        c = clock()
        people = {}
        families = {}
        layers = {}

        todo = [(handle, 0)]
        while todo:
            handle, layer = todo.pop()
            if layer not in layers:
                layers[layer] = [(0, handle)]
            else:
                layers[layer].append((0, handle))

            if layer % 2 == 0:
                # person
                person = self.dbstate.db.get_person_from_handle(handle)
                if person is not None:
                    name = name_displayer.display(person)
                    sex = person.get_gender()
                else:
                    name = "???"
                    sex = Person.UNKNOWN
                people[handle] = PersonNode(handle, layer, name, sex)

                for fhandle in person.get_family_handle_list():
                    people[handle].add_main_family(fhandle)
                    if fhandle not in families:
                        todo.append((fhandle, layer + 1))

                for fhandle in person.get_parent_family_handle_list():
                    people[handle].add_family(fhandle)
                    if fhandle not in families:
                        todo.append((fhandle, layer - 1))

            else:
                # family
                family = self.dbstate.db.get_family_from_handle(handle)
                rel_type = family.get_relationship()
                families[handle] = FamilyNode(handle, layer, rel_type)

                for child_ref in family.get_child_ref_list():
                    families[handle].add_child(child_ref.ref)
                    if child_ref.ref not in people:
                        todo.append((child_ref.ref, layer + 1))
                parent = family.get_father_handle()
                if parent is not None:
                    families[handle].add_parent(parent)
                    if parent not in people:
                        todo.append((parent, layer - 1))
                parent = family.get_mother_handle()
                if parent is not None:
                    families[handle].add_parent(parent)
                    if parent not in people:
                        todo.append((parent, layer - 1))

        return people, families, layers

    def rebuild(self):
        """
        Rebuild.
        """
        active = self.get_active()
        if active != "":
            self.people, self.families, self.layers = self.read_data(active)
            self.canvas.queue_draw()
            self.center_on_node(active)

    def on_draw(self, canvas, cr):
        """
        Draw.
        """
        if self.layers is None:
            return
        #c = clock()

        cr.scale(self.scale, self.scale)

        x = BORDER
        y = BORDER
        # Draw person and family nodes
        for layer in sorted(self.layers.keys()):
            nodes = self.layers[layer]
            layer_width = 0
            for item in sorted(nodes):
                handle = item[1]
                if layer % 2 == 0:
                    # person
                    p = self.people[handle]
                    p.set_position(x, y)
                    item = p.draw(canvas, cr)
                    if p.get_width() > layer_width:
                        layer_width = p.get_width()
                    y += HEIGHT
                else:
                    # family
                    f = self.families[handle]
                    f.set_position(x, y)
                    item = f.draw(canvas, cr)
                    x += HEIGHT
            if layer % 2 == 0:
                # person
                x += layer_width
            else:
                # family
                y += HEIGHT

        # Draw linking lines
        for family in self.families.values():
            miny = None
            for phandle in family.parents:
                parent = self.people[phandle]
                x1 = parent.x + parent.width
                x2 = family.x + HEIGHT
                y1 = parent.y
                y2 = parent.y + HEIGHT
                if miny is None or y1 < miny:
                    miny = y1

                cr.set_source_rgb(0.50, 0.50, 0.50)
                cr.move_to(x1, y1)
                cr.line_to(x2, y1)
                cr.stroke()
                cr.move_to(x1, y2)
                cr.line_to(x2, y2)
                cr.stroke()

                cr.set_source_rgb(0.25, 0.25, 0.25)
                if parent.sex == Person.MALE:
                    cr.rectangle(family.x + 4, y1 + 4, 10, 10)
                else:
                    cr.arc((family.x + x2) / 2, (y1 + y2) / 2,
                           5, 0, 2 * math.pi)
                cr.fill()

            if miny is not None:
                cr.set_source_rgb(0.50, 0.50, 0.50)
                cr.move_to(family.x, miny)
                cr.line_to(family.x, family.y)
                cr.stroke()
                cr.move_to(x2, miny)
                cr.line_to(x2, family.y)
                cr.stroke()

            maxy = None
            for phandle in family.children:
                child = self.people[phandle]
                x1 = family.x
                x2 = child.x
                y1 = child.y
                y2 = child.y + HEIGHT
                if maxy is None or y2 > maxy:
                    maxy = y2
                cr.set_source_rgb(0.50, 0.50, 0.50)
                cr.move_to(x1, y1)
                cr.line_to(x2, y1)
                cr.stroke()
                cr.move_to(x1, y2)
                cr.line_to(x2, y2)
                cr.stroke()

                cr.set_source_rgb(0.25, 0.25, 0.25)
                if child.sex == Person.MALE:
                    cr.rectangle(x1 + 4, y1 + 4, 10, 10)
                else:
                    cr.arc((x1 + family.x + HEIGHT) / 2, (y1 + y2) / 2,
                           5, 0, 2 * math.pi)
                cr.fill()

            if maxy is not None:
                cr.set_source_rgb(0.50, 0.50, 0.50)
                cr.move_to(family.x, family.y + HEIGHT)
                cr.line_to(family.x, maxy)
                cr.stroke()
                cr.move_to(family.x + HEIGHT, family.y + HEIGHT)
                cr.line_to(family.x + HEIGHT, maxy)
                cr.stroke()

        for path in self.paths:
            x1, y1, x2, y2 = path
            cr.set_source_rgba(0.90, 0.20, 0.20, 0.6)
            cr.set_line_width(HEIGHT/2)
            cr.move_to(x1 - HEIGHT/2, y1)
            cr.line_to(x2 - HEIGHT/2, y2+HEIGHT)
            cr.stroke()

        self.canvas.set_size_request((x + BORDER) * self.scale,
                                     (y + BORDER) * self.scale)

        #print ('draw time', clock()- c)

    def home(self, menuitem):
        defperson = self.dbstate.db.get_default_person()
        if defperson:
            self.change_active(defperson.handle)

    def edit_person_cb(self, obj, handle):
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
            return True
        return False

    def edit_family_cb(self, obj, handle):
        family = self.dbstate.db.get_family_from_handle(handle)
        if family:
            try:
                EditFamily(self.dbstate, self.uistate, [], family)
            except WindowActiveError:
                pass
            return True
        return False

    def set_preview_position(self):
        hadj = self.scrolledwindow.get_hadjustment()
        vadj = self.scrolledwindow.get_vadjustment()

        x_start = hadj.get_value() / self.scale
        y_start = vadj.get_value() / self.scale

        alloc = self.canvas.get_allocation()
        width = alloc.width / self.scale
        height = alloc.height / self.scale

    def scrolled_cb(self, widget, event):
        """
        Zoom in and out.
        """
        if event.direction == Gdk.ScrollDirection.UP:
            self.scale *= 1.1
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.scale /= 1.1
        self.canvas.queue_draw()
        active = self.get_active()
        self.center_on_node(active)
        return True

    def resized_cb(self, widget, size):
        self.set_preview_position()

    def get_object_at(self, x, y):
        if len(self.people) == 0:
            return None
        for p in self.people.values():
            if p.is_at(x, y):
                return p
        for f in self.families.values():
            if f.is_at(x, y):
                return f
        return None

    def press_cb(self, widget, event):
        if (event.get_button()[1] == 1 and
            event.type == Gdk.EventType.BUTTON_PRESS):
            obj = self.get_object_at(event.x / self.scale,
                                     event.y / self.scale)
            if obj:
                if isinstance(obj, PersonNode):
                    #print("Clicked for", obj.name, "in", obj.x, obj.y)
                    self.add_bookmark(obj.handle)
                    self.set_path_lines(obj)
                else:
                    #print ('Clicked family')
                    self.set_path_lines(obj)
            else:
                cursor = Gdk.Cursor.new(Gdk.CursorType.FLEUR)
                self.canvas.get_window().set_cursor(cursor)
                self._last_x = event.x
                self._last_y = event.y
                self._in_move = True
                return True
        if (event.get_button()[1] == 3 and
            event.type == Gdk.EventType.BUTTON_PRESS):
            obj = self.get_object_at(event.x / self.scale,
                                     event.y / self.scale)
            if obj:
                if isinstance(obj, PersonNode):
                    self.edit_person_cb(event, obj.handle)
                else:
                    self.edit_family_cb(event, obj.handle)
        return False

    def release_cb(self, widget, event):
        if (event.get_button()[1] == 1 and
            event.type == Gdk.EventType.BUTTON_RELEASE):
            self.motion_notify_cb(widget, event)
            self.canvas.get_window().set_cursor(None)
            self._in_move = False
            return True
        return False

    def update_scrollbar_positions(self, adjustment, value):
        if value > (adjustment.get_upper() - adjustment.get_page_size()):
            adjustment.set_value(adjustment.get_upper() -
                                 adjustment.get_page_size())
        else:
            adjustment.set_value(value)
        return True

    def motion_notify_cb(self, widget, event):
        if self._in_move and (event.type == Gdk.EventType.MOTION_NOTIFY or
           event.type == Gdk.EventType.BUTTON_RELEASE):
            hadjustment = self.scrolledwindow.get_hadjustment()
            vadjustment = self.scrolledwindow.get_vadjustment()
            self.update_scrollbar_positions(vadjustment,
                vadjustment.get_value() - (event.y - self._last_y))
            self.update_scrollbar_positions(hadjustment,
                hadjustment.get_value() - (event.x - self._last_x))
            return True
        return False

    def get_ascendants(self, obj):
        for fam in obj.children:
            if fam in self.families:
                for parent in self.families[fam].parents:
                    self.get_ascendants(self.people[parent])
                    # prepare to draw the vertical bar
                    self.paths.append((self.families[fam].x+HEIGHT,
                                       obj.y+HEIGHT/2,
                                       self.families[fam].x+HEIGHT,
                                       self.people[parent].y-HEIGHT/2))
        # prepare to hightligt the name
        (x1, x2) = self.calculate_segment_length(obj)
        self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                           x2+HEIGHT, obj.y-HEIGHT/2))

    def get_descendants(self, obj):
        for fam in obj.parents:
            if fam in self.families:
                for child in self.families[fam].children:
                    self.get_descendants(self.people[child])
                    # prepare to draw the vertical bar
                    self.paths.append((self.families[fam].x+HEIGHT,
                                       obj.y+HEIGHT/2,
                                       self.families[fam].x+HEIGHT,
                                       self.people[child].y-HEIGHT/2))
        # prepare to hightligt the name
        (x1, x2) = self.calculate_segment_length(obj)
        self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                           x2+HEIGHT, obj.y-HEIGHT/2))

    def set_path_lines(self, obj):
        """
        obj : either a person or a family
        """
        self.paths = []
        if isinstance(obj, PersonNode):
            (x1, x2) = self.calculate_segment_length(obj)
            self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                               x2+HEIGHT, obj.y-HEIGHT/2))
            # Draw linking path for descendant
            for fam in obj.parents:
                if fam in self.families:
                    for child in self.families[fam].children:
                        self.get_descendants(self.people[child])
                        self.paths.append((self.families[fam].x+HEIGHT,
                                           obj.y+HEIGHT/4,
                                           self.families[fam].x+HEIGHT,
                                           self.people[child].y-HEIGHT/4))
            # Draw linking path for ascendant
            for fam in obj.children:
                if fam in self.families:
                    for parent in self.families[fam].parents:
                        self.get_ascendants(self.people[parent])
                        self.paths.append((self.families[fam].x+HEIGHT,
                                           obj.y+HEIGHT/4,
                                           self.families[fam].x+HEIGHT,
                                           self.people[parent].y-HEIGHT+HEIGHT/4
                                          ))
            self.canvas.queue_draw()
            self.center_on_node(obj.handle)

    def calculate_segment_length(self, obj):
        """
        We need to know the coordinates for the name to display
        These coordinates include the name,
        the segment for the parents and the segment for the children
        """
        if isinstance(obj, PersonNode):
            x1 = obj.x
            x2 = obj.x + obj.width
        else:
            obj = self.people[obj]
            x1 = obj.x
            x2 = obj.x + obj.width
        if len(obj.parents) > 0:
            par1 = obj.parents[0]
            if par1 in self.families:
                fam1 = self.families[par1]
                x1 = fam1.x
        else:
            x1 += obj.width
        if len(obj.children) > 0:
            par2 = obj.children[0]
            if par2 in self.families:
                fam2 = self.families[par2]
                x2 = fam2.x
        else:
            x2 -= obj.width
        return(x1, x2)

    ##################################################################
    #
    # Print this tree in a multipages way.
    #
    ##################################################################
    print_zoom = 1.0
    print_settings = None

    def on_print(self, action=None):
        self.print_op = Gtk.PrintOperation()
        self.print_op.connect("begin_print", self.begin_print)
        self.print_op.connect("draw_page", self.draw_page)

        page_setup = Gtk.PageSetup()
        if self.print_settings is None:
            self.print_settings = Gtk.PrintSettings()
        page_setup = Gtk.print_run_page_setup_dialog(None, page_setup, self.print_settings)
        paper_size_used = page_setup.get_paper_size()
        self.format = paper_size_used.get_name()
        self.print_settings.set_paper_size(paper_size_used)
        self.print_settings.set_orientation(page_setup.get_orientation())
        self.print_op.set_print_settings(self.print_settings)
        if page_setup.get_orientation() == Gtk.PageOrientation.PORTRAIT:
            self.height_used = int(paper_size_used.get_height(Gtk.Unit.POINTS))
            self.width_used = int(paper_size_used.get_width(Gtk.Unit.POINTS))
        else:
            self.height_used = int(paper_size_used.get_width(Gtk.Unit.POINTS))
            self.width_used = int(paper_size_used.get_height(Gtk.Unit.POINTS))

        res = self.print_op.run(Gtk.PrintOperationAction.PREVIEW,
                           self.uistate.window)

    def begin_print(self, operation, context):
        rect = self.canvas.get_allocation()
        self.pages_per_row = int(int(rect.width)*self.print_zoom/self.width_used + 1)
        self.nb_pages = int(self.pages_per_row * int(int(rect.height)*self.print_zoom/self.height_used + 1))
        operation.set_n_pages(self.nb_pages)
        return True

    def draw_page(self, operation, context, page_nr):
        if page_nr == 0:
            self.progress = ProgressMeter(_("Printing the tree"),
                                          can_cancel=True,
                                          cancel_callback=self.cancel_print,
                                          parent=self.uistate.window)
            message = _('Need to print %(pages)s pages (%(format)s format)')
            self.progress.set_pass(message % { 'pages' : self.nb_pages,
                                               'format' : self.format },
                                   self.nb_pages)
        cr = context.get_cairo_context()
        x = y = 0
        x = ((page_nr % self.pages_per_row ) * self.width_used) if page_nr > 0 else 0
        y = (int(page_nr / self.pages_per_row) * self.height_used)
        cr.save()
        cr.translate(-x, -y)
        cr.scale(self.print_zoom, self.print_zoom)
        self.canvas.draw(cr)
        cr.restore()
        if page_nr == self.nb_pages-1:
            self.progress.close()
        self.progress.step()

    def cancel_print(self, arg1):
        self.progress.close()
        self.print_op.cancel()
