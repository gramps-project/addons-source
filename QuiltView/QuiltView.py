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
from gi.repository import GLib
from gi.repository import Pango, PangoCairo

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.lib import Person, Family, ChildRef, Name
from gramps.gui.views.navigationview import NavigationView
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.errors import WindowActiveError
from gramps.gui.editors import EditPerson, EditFamily, EditTagList
from gramps.gen.config import config
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gen.const import CUSTOM_FILTERS
from gramps.gui.dialog import RunDatabaseRepair, ErrorDialog
from gramps.gui.utils import ProgressMeter
from gramps.gui.utils import color_graph_box, color_graph_family, rgb_to_hex
from gramps.gen.plug import MenuOptions
from gramps.gen.constfunc import win
from gramps.gui.widgets.menuitem import add_menuitem
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 find_children, find_parents, preset_name,
                                 find_witnessed_people)
from html import escape
import gramps.gui.widgets.progressdialog as progressdlg
from gramps.gen.utils.libformatting import FormattingHelper
from gramps.gen.db import DbTxn
from gramps.gui.display import display_url

BORDER = 10
HEIGHT = 18
WIKI_PAGE = 'https://gramps-project.org/wiki/index.php?title=Quilt_Chart'

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
        result = False
        if self.x and self.y:
            result = (self.x < x < self.x + self.width and
                      self.y < y < self.y + self.height)
        return result

    def draw(self, canvas, cr):
        pass

class PersonNode(Node):
    def __init__(self, handle, layer, name, sex, ident, fg_color, bg_color):
        Node.__init__(self, handle, layer)
        self.name = name
        self.sex = sex
        self.ident = ident
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.parents = []
        self.children = []

    def add_main_family(self, family):
        self.parents.append(family)

    def add_family(self, family):
        self.children.append(family)

    def draw(self, canvas, cr):
        if self.sex == Person.MALE:
            label = '\u2642 ' + self.name
        elif self.sex == Person.FEMALE:
            label = '\u2640 ' + self.name
        else:
            label = '\u2650 ' + self.name

        layout = canvas.create_pango_layout(label)
        width, height = layout.get_size()
        self.width = width / 1024

        # Set the name background depending on the sex
        cr.set_source_rgb(*self.bg_color)
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

        cr.set_source_rgb(*self.fg_color)
        cr.move_to(self.x, self.y)
        PangoCairo.show_layout(cr, layout)

class FamilyNode(Node):
    def __init__(self, handle, layer, rel_type, ident, fg_color, bg_color):
        Node.__init__(self, handle, layer)
        self.rel_type = rel_type
        self.ident = ident
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.parents = []
        self.children = []

    def add_parent(self, person):
        self.parents.append(person)

    def add_child(self, person):
        self.children.append(person)

    def draw(self, canvas, cr):
        cr.set_source_rgb(*self.bg_color)
        cr.rectangle(self.x, self.y, self.width, self.height)
        cr.fill()

        cr.set_source_rgb(*self.fg_color)
        cr.rectangle(self.x, self.y, self.width, self.height)
        cr.stroke()

        layout = canvas.create_pango_layout('F')
        font = Pango.FontDescription('Sans')
        layout.set_font_description(font)
        width, height = layout.get_size()

        cr.set_source_rgb(*self.fg_color)
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
    CONFIGSETTINGS = (
                      ('interface.quiltview-center', True),
                      ('interface.quiltview-color-path', 'red'),
                      ('interface.quiltview-color-selected', 'blue'),
                      ('interface.quiltview-path-transparency', 6),
                      )

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
        self.format_helper = FormattingHelper(self.dbstate)
        scheme = config.get('colors.scheme')
        self.home_person_color = config.get('colors.home-person')[scheme]
        self.timeout = None
        self.save_tooltip = None
        self.plist = []
        self.total = 0
        self.progress = None
        self.load = 0 # avoid to load the database twice

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

        self.canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                               Gdk.EventMask.BUTTON_RELEASE_MASK |
                               Gdk.EventMask.POINTER_MOTION_MASK |
                               Gdk.EventMask.SCROLL_MASK |
                               Gdk.EventMask.KEY_PRESS_MASK)

        self.scrolledwindow.add(self.canvas)

        self.preview_rect = None

        self.vbox = Gtk.Box(False, 4, orientation=Gtk.Orientation.VERTICAL)
        self.vbox.set_border_width(4)
        hbox = Gtk.Box(False, 4, orientation=Gtk.Orientation.HORIZONTAL)
        self.vbox.pack_start(hbox, False, False, 0)

        self.name_store = Gtk.ListStore(str, str)
        self.name_combo = Gtk.ComboBox.new_with_model_and_entry(self.name_store)
        self.name_combo.set_tooltip_text(
            _("Select the name for which you want to see."))
        self.name_combo.connect('changed', self._entry_key_event)
        self.name_combo.set_entry_text_column(0)
        hbox.pack_start(self.name_combo, False, False, 0)

        clear = Gtk.Button(_("Clear"))
        clear.set_tooltip_text(
            _("Clear the entry field in the name selection box."))
        clear.connect('clicked', self._erase_name_selection)
        hbox.pack_start(clear, False, False, 0)

        self.message = Gtk.Label()
        self.message.set_label(_("Nothing is selected"))
        hbox.pack_start(self.message, False, False, 0)

        self.vbox.pack_start(self.scrolledwindow, True, True, 0)

        return self.vbox

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
        self.load += 1 # avoid to load the database twice
        if self.load == 1:
            return
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
        self._erase_name_selection()
        self._clear_list_store()
        if self.load > 1: # avoid to load the database twice
            self.load = 0
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

    def _entry_key_event(self, combobox):
        """
        If the user enter characters, we create the list for the combobox.
        If the user select one field, the tree_iter is not None
        """
        tree_iter = combobox.get_active_iter()
        if tree_iter is not None:
            model = combobox.get_model()
            name, handle = model[tree_iter][:2]
            self.move_to_node(None, handle)
            #print("Selected: name=%s, handle=%s" % (name, handle))
        else:
            self._clear_list_store()
            entry = combobox.get_child()
            search = entry.get_text()
            count = 0
            for name in self.plist:
                if search in name[0].lower():
                    count += 1
                    found = name[0]
                    self.name_store.append(name)
            self.message.set_label(
                _("You have %(filter)d filtered people, "
                  "%(count)d people shown on the tree "
                  "and %(total)d people in your database."
                  % {'filter': count if search != "" else 0,
                     'count': len(self.plist),
                     'total': self.total}))

    def _clear_list_store(self):
        """
        We erase the list store
        """
        self.name_store = Gtk.ListStore(str, str)
        self.name_combo.set_model(self.name_store)

    def _erase_name_selection(self, arg=None):
        """
        We erase the name in the entrybox
        """
        self.name_combo.get_child().set_text("")

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

    def move_to_node(self, obj, handle):
        self.add_bookmark(handle)
        self.center_on_node(None, handle)

    def center_on_node(self, obj, handle):
        if handle in self.people.keys():
            node = self.people[handle]
            if node.x and node.y:
                hadjustment = self.scrolledwindow.get_hadjustment()
                vadjustment = self.scrolledwindow.get_vadjustment()
                if self._config.get('interface.quiltview-center'):
                    hadj = ((node.x - 10 * math.log(node.y) ) * self.scale)
                    vadj = ((node.y - 10 * math.log(node.x) ) * self.scale)
                else:
                    hadj = ((node.x - 50 * math.log(node.y) ) * self.scale)
                    vadj = ((node.y - 50 * math.log(node.x) ) * self.scale)
                self.update_scrollbar_positions(vadjustment, vadj)
                self.update_scrollbar_positions(hadjustment, hadj)
        if handle in self.people.keys():
            node = self.people[handle]
            if node.x is not None: # not totaly initialized.
                self.highlight_person(node, "#00ff00")
                self.set_path_lines(self.people[handle])

    def goto_handle(self, handle=None):
        self._erase_name_selection()
        self._clear_list_store()
        if self.load < 3: # avoid to load the database twice
            self.load = 3
            self.rebuild()
        if handle not in self.people.keys():
            self.rebuild()
        else:
            obj = self.people[handle]
            if obj.x is not None: # not totaly initialized.
                self.set_path_lines(self.people[handle])
                self.center_on_node(None, handle)
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
        self.plist.clear()
        home = self.dbstate.db.get_default_person()
        home_person = home.get_handle() if home else None

        message = _('Loading individuals')
        self.progress = ProgressMeter(_("Loading the data"),
                                      can_cancel=False,
                                      parent=self.uistate.window)
        self.progress.set_pass(message, self.total)
        todo = [(handle, 0)]
        count = 0
        while todo:
            handle, layer = todo.pop()
            count += 1 # persons + families
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
                    ident = person.get_gramps_id()
                else:
                    name = "???"
                    sex = Person.UNKNOWN
                    ident = None
                self.plist.append([name, handle])
                # get alive status of person to get box color
                death_event = get_death_or_fallback(self.dbstate.db, person)
                if death_event:
                    fill, color = color_graph_box(False, sex)
                else:
                    fill, color = color_graph_box(True, sex)
                color = Gdk.color_parse(color)
                fg_color = (float(color.red / 65535.0),
                            float(color.green / 65535.0),
                            float(color.blue / 65535.0))
                if home_person and handle == home_person:
                    color = Gdk.color_parse(self.home_person_color)
                    bg_color = (float(color.red / 65535.0),
                                float(color.green / 65535.0),
                                float(color.blue / 65535.0))
                else:
                    color = Gdk.color_parse(fill)
                    bg_color = (float(color.red / 65535.0),
                                float(color.green / 65535.0),
                                float(color.blue / 65535.0))

                people[handle] = PersonNode(handle, layer, name,
                                            sex, ident, fg_color, bg_color)

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
                ident = family.get_gramps_id()
                fill, color = color_graph_family(family, self.dbstate)
                color = Gdk.color_parse(color)
                fg_color = (float(color.red / 65535.0),
                            float(color.green / 65535.0),
                            float(color.blue / 65535.0))
                color = Gdk.color_parse(fill)
                bg_color = (float(color.red / 65535.0),
                            float(color.green / 65535.0),
                            float(color.blue / 65535.0))
                families[handle] = FamilyNode(handle, layer, rel_type,
                                              ident, fg_color, bg_color)

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
            self.progress.step()
        self.progress.close()
        return people, families, layers

    def rebuild(self):
        """
        Rebuild.
        """
        if not self.active:
            return # Don't rebuild, we are hidden.
        if self.load < 3: # avoid to load the database twice
            return
        self.total = self.dbstate.db.get_number_of_people()
        active = self.get_active()
        if active != "":
            self.people, self.families, self.layers = self.read_data(active)
            self.name_combo.get_child().set_text(" ") # force entry change
            self.name_combo.get_child().set_text("")
            self.canvas.queue_draw()
            self.canvas.grab_focus()
            self.center_on_node(None, active)
            self.set_path_lines(active)

    def on_draw(self, canvas, cr):
        """
        Draw.
        """
        if self.layers is None:
            return
        transparency = self._config.get('interface.quiltview-path-transparency')
        transparency = transparency / 10
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
            x1, y1, x2, y2, color_name = path
            if color_name is not None:
                color = Gdk.color_parse(color_name)
                cr.set_source_rgba(float(color.red / 65535.0),
                                   float(color.green / 65535.0),
                                   float(color.blue / 65535.0),
                                   transparency)
            else:
                cr.set_source_rgba(0.90, 0.20, 0.20, transparency)
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

    def edit_person_cb(self, obj, handle=None):
        if not (obj or handle):
            return False

        if not handle:
            handle = obj.get_data()

        self.add_bookmark(handle)
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
            return True
        return False

    def edit_family_cb(self, obj, handle=None):
        if not (obj or handle):
            return False

        if not handle:
            handle = obj.get_data()

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
        self.center_on_node(None, active)
        return True

    def resized_cb(self, widget, size):
        self.set_preview_position()

    def get_object_for(self, handle):
        if len(self.people) == 0:
            return None
        for p in self.people.values():
            if p.handle == handle:
                return p
        for f in self.families.values():
            if f.handle == handle:
                return f
        return None

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
                    self.person_menu(obj.handle, event)
                    self.set_path_lines(obj)
                elif isinstance(obj, FamilyNode):
                    self.family_menu(obj.handle, event)
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

    def add_menu_separator(self, menu):
        """
        Adds separator to menu.
        """
        menu_item = Gtk.SeparatorMenuItem()
        menu_item.show()
        menu.append(menu_item)

    def append_help_menu_entry(self, menu):
        """
        Adds help (about) menu entry.
        """
        item = Gtk.MenuItem(label=_("About Quilt View"))
        item.connect("activate", self.on_help_clicked)
        item.show()
        menu.append(item)

    def on_help_clicked(self, widget):
        """
        Display the relevant portion of Gramps manual.
        """
        display_url(WIKI_PAGE)

    def set_home_person(self, obj):
        """
        Set the home person for database and make it active.
        """
        handle = obj.get_data()
        person = self.dbstate.db.get_person_from_handle(handle)
        if person:
            self.dbstate.db.set_default_person_handle(handle)

    def copy_person_to_clipboard(self, obj, person_handle):
        """
        Renders the person data into some lines of text
        and puts that into the clipboard.
        """
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            cb = Gtk.Clipboard.get_for_display(Gdk.Display.get_default(),
                                               Gdk.SELECTION_CLIPBOARD)
            cb.set_text(self.format_helper.format_person(person, 11), -1)
            return True
        return False

    def get_person_name(self, person):
        """
        Return a string containing the person's primary name in the name
        format chosen in the preferences options

        @param: person -- person object from database
        """
        primary_name = person.get_primary_name()
        name = Name(primary_name)
        return name_displayer.display_name(name)

    def get_family_name(self, handle):
        """
        Create the family name
        """
        if handle:
            family = self.dbstate.db.get_family_from_handle(handle)
        else:
            return ''

        if family:
            husband_handle = family.get_father_handle()
            spouse_handle = family.get_mother_handle()

            if husband_handle:
                husband = self.dbstate.db.get_person_from_handle(husband_handle)
            else:
                husband = None
            if spouse_handle:
                spouse = self.dbstate.db.get_person_from_handle(spouse_handle)
            else:
                spouse = None

            if husband and spouse:
                husband_name = self.get_person_name(husband)
                spouse_name = self.get_person_name(spouse)
                # The next strings already translated for the narrative web
                title_str = _("Family of %(husband)s and %(spouse)s"
                             ) % {'husband' : husband_name,
                                  'spouse'  : spouse_name}
            elif husband:
                husband_name = self.get_person_name(husband)
                # Only the name of the husband is known
                title_str = _("Family of %s") % husband_name
            elif spouse:
                spouse_name = self.get_person_name(spouse)
                # Only the name of the wife is known
                title_str = _("Family of %s") % spouse_name
            else:
                title_str = ''
        return title_str

    def show_family_name(self, handle, event):
        """
        Popup menu for node (family).
        """
        if handle:
            family = self.dbstate.db.get_family_from_handle(handle)
        else:
            return False

        if family:
            if not self.timeout:
                self.save_tooltip = handle
                self.scrolledwindow.set_property("has-tooltip", True)
                tooltip = self.get_family_name(handle)
                self.scrolledwindow.set_tooltip_text(tooltip)
                self.timeout = GLib.timeout_add(3*1000, self.remove_tooltip)
            elif handle != self.save_tooltip:
                self.save_tooltip = handle
                GLib.source_remove(self.timeout)
                tooltip = self.get_family_name(handle)
                self.scrolledwindow.set_tooltip_text(tooltip)
                self.timeout = GLib.timeout_add(3*1000, self.remove_tooltip)

    def remove_tooltip(self):
        self.timeout = None
        self.save_tooltip = None
        self.scrolledwindow.set_property("has-tooltip", False)
        self.scrolledwindow.set_tooltip_text("")
        return False

    def family_menu(self, handle, event):
        """
        Popup menu for node (family).
        """
        if handle:
            family = self.dbstate.db.get_family_from_handle(handle)
        else:
            return False

        self.menu = Gtk.Menu()
        self.menu.set_reserve_toggle_size(False)

        if family:
            label = Gtk.MenuItem(label=self.get_family_name(handle))
            label.show()
            label.set_sensitive(False)
            self.menu.append(label)

            self.add_menu_separator(self.menu)

            add_menuitem(self.menu, _('Edit'),
                         handle, self.edit_family_cb)

            add_menuitem(self.menu, _('Edit tags'),
                         [handle, 'family'], self.edit_tag_list)
            self.add_children_submenu(self.menu, None, family)

            self.add_menu_separator(self.menu)
            self.append_help_menu_entry(self.menu)

        # new from gtk 3.22:
        # self.menu.popup_at_pointer(event)
        self.menu.popup(None, None, None, None,
                        event.get_button()[1], event.time)

    def add_children_submenu(self, menu, person, family=None):
        """
        Go over children and build their menu.
        """
        item = Gtk.MenuItem(label=_("Children"))
        item.set_submenu(Gtk.Menu())
        child_menu = item.get_submenu()
        child_menu.set_reserve_toggle_size(False)

        no_child = 1

        if family:
            childlist = []
            for child_ref in family.get_child_ref_list():
                childlist.append(child_ref.ref)
            # allow to add a child to this family
            add_child_item = Gtk.MenuItem()
            add_child_item.set_label(_("Add child to family"))
            add_child_item.connect("activate", self.add_child_to_family,
                                   family.get_handle())
            add_child_item.show()
            child_menu.append(add_child_item)
            no_child = 0
        else:
            childlist = find_children(self.dbstate.db, person)

        for child_handle in childlist:
            child = self.dbstate.db.get_person_from_handle(child_handle)
            if not child:
                continue

            if no_child:
                no_child = 0

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
            child_item.connect("activate", self.move_to_person,
                               child_handle, True)
            child_item.show()
            child_menu.append(child_item)

        if no_child:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

    def add_child_to_family(self, obj, family_handle):
        """
        Open person editor to create and add child to family.
        """
        callback = lambda x: self.callback_add_child(x, family_handle)
        person = Person()
        name = Name()
        # the editor requires a surname
        name.add_surname(Surname())
        name.set_primary_surname(0)
        family = self.dbstate.db.get_family_from_handle(family_handle)
        father = self.dbstate.db.get_person_from_handle(
                                    family.get_father_handle())
        if father:
            preset_name(father, name)
        person.set_primary_name(name)
        try:
            EditPerson(self.dbstate, self.uistate, [], person,
                       callback=callback)
        except WindowActiveError:
            pass

    def callback_add_child(self, person, family_handle):
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

    def person_menu(self, handle, event):
        """
        Popup menu for node (person).
        """
        if handle:
            person = self.dbstate.db.get_person_from_handle(handle)
        else:
            return
        self.menu = Gtk.Menu()
        self.menu.set_reserve_toggle_size(False)

        label = Gtk.MenuItem(label=name_displayer.display(person))
        label.show()
        label.set_sensitive(False)
        self.menu.append(label)

        self.add_menu_separator(self.menu)

        if handle and person:
            add_menuitem(self.menu, _('Edit'),
                         handle, self.edit_person_cb)

            add_menuitem(self.menu, _('Edit tags'),
                         [handle, 'person'], self.edit_tag_list)

            clipboard_item = Gtk.MenuItem.new_with_mnemonic(_('_Copy'))
            clipboard_item.connect("activate",
                                   self.copy_person_to_clipboard,
                                   handle)
            clipboard_item.show()
            self.menu.append(clipboard_item)

            self.add_menu_separator(self.menu)

            # go over spouses and build their menu
            item = Gtk.MenuItem(label=_("Spouses"))
            item.set_submenu(Gtk.Menu())
            sp_menu = item.get_submenu()
            sp_menu.set_reserve_toggle_size(False)

            add_menuitem(sp_menu, _('Add'),
                         handle, self.add_partner)
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

                sp_item = Gtk.MenuItem(label=name_displayer.display(spouse))
                sp_item.connect("activate", self.move_to_node, sp_id)
                sp_item.show()
                sp_menu.append(sp_item)

            item.show()
            self.menu.append(item)

            # go over siblings and build their menu
            item = Gtk.MenuItem(label=_("Siblings"))
            pfam_list = person.get_parent_family_handle_list()
            siblings = []
            step_siblings = []
            for f in pfam_list:
                fam = self.dbstate.db.get_family_from_handle(f)
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
                        fam_stepsiblings = [sib_ref.ref
                                            for sib_ref in
                                            step_fam.get_child_ref_list()
                                            if not (
                                        sib_ref.ref == person.get_handle())]
                        if fam_stepsiblings:
                            step_siblings.append(fam_stepsiblings)

            # add siblings sub-menu with a bar between each siblings group
            if siblings or step_siblings:
                item.set_submenu(Gtk.Menu())
                sib_menu = item.get_submenu()
                sib_menu.set_reserve_toggle_size(False)
                sibs = [siblings] + step_siblings
                for sib_group in sibs:
                    for sib_id in sib_group:
                        sib = self.dbstate.db.get_person_from_handle(sib_id)
                        if not sib:
                            continue
                        if find_children(self.dbstate.db, sib):
                            label = Gtk.Label(
                                    label='<b><i>%s</i></b>'
                                          % escape(name_displayer.display(sib)))
                        else:
                            label = Gtk.Label(
                                label=escape(name_displayer.display(sib)))
                        sib_item = Gtk.MenuItem()
                        label.set_use_markup(True)
                        label.show()
                        label.set_alignment(0, 0)
                        sib_item.add(label)
                        sib_item.connect("activate", self.move_to_node, sib_id)
                        sib_item.show()
                        sib_menu.append(sib_item)
                    if sibs.index(sib_group) < len(sibs) - 1:
                        self.add_menu_separator(sib_menu)
            else:
                item.set_sensitive(0)
            item.show()
            self.menu.append(item)

            self.add_children_submenu(self.menu, person)

            # Go over parents and build their menu
            item = Gtk.MenuItem(label=_("Parents"))
            item.set_submenu(Gtk.Menu())
            par_menu = item.get_submenu()
            par_menu.set_reserve_toggle_size(False)
            no_parents = 1
            par_list = find_parents(self.dbstate.db, person)
            for par_id in par_list:
                if not par_id:
                    continue
                par = self.dbstate.db.get_person_from_handle(par_id)
                if not par:
                    continue

                if no_parents:
                    no_parents = 0

                if find_parents(self.dbstate.db, par):
                    label = Gtk.Label(label='<b><i>%s</i></b>'
                                      % escape(name_displayer.display(par)))
                else:
                    label = Gtk.Label(label=escape(name_displayer.display(par)))

                par_item = Gtk.MenuItem()
                label.set_use_markup(True)
                label.show()
                label.set_halign(Gtk.Align.START)
                par_item.add(label)
                par_item.connect("activate", self.move_to_node, par_id)
                par_item.show()
                par_menu.append(par_item)

            if no_parents:
                # add button to add parents
                add_menuitem(par_menu, _('Add'), handle,
                             self.add_parents_to_person)
            item.show()
            self.menu.append(item)

            # go over related persons and build their menu
            item = Gtk.MenuItem(label=_("Related"))
            no_related = 1
            for p_id in find_witnessed_people(self.dbstate.db, person):
                per = self.dbstate.db.get_person_from_handle(p_id)
                if not per:
                    continue

                if no_related:
                    no_related = 0
                item.set_submenu(Gtk.Menu())
                per_menu = item.get_submenu()
                per_menu.set_reserve_toggle_size(False)

                label = Gtk.Label(label=escape(name_displayer.display(per)))

                per_item = Gtk.MenuItem()
                label.set_use_markup(True)
                label.show()
                label.set_halign(Gtk.Align.START)
                per_item.add(label)
                per_item.connect("activate", self.move_to_node, p_id)
                per_item.show()
                per_menu.append(per_item)

            if no_related:
                item.set_sensitive(0)
            item.show()
            self.menu.append(item)

            self.add_menu_separator(self.menu)

            add_menuitem(self.menu, _('Set as home person'),
                         handle, self.set_home_person)

            self.add_menu_separator(self.menu)
            self.append_help_menu_entry(self.menu)

        # new from gtk 3.22:
        # self.menu.popup_at_pointer(event)
        self.menu.popup(None, None, None, None,
                        event.get_button()[1], event.time)

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
        self.person_to_focus = person_handle

    def add_children_submenu(self, menu, person, family=None):
        """
        Go over children and build their menu.
        """
        item = Gtk.MenuItem(label=_("Children"))
        item.set_submenu(Gtk.Menu())
        child_menu = item.get_submenu()
        child_menu.set_reserve_toggle_size(False)

        no_child = 1

        if family:
            childlist = []
            for child_ref in family.get_child_ref_list():
                childlist.append(child_ref.ref)
            # allow to add a child to this family
            add_child_item = Gtk.MenuItem()
            add_child_item.set_label(_("Add child to family"))
            add_child_item.connect("activate", self.add_child_to_family,
                                   family.get_handle())
            add_child_item.show()
            child_menu.append(add_child_item)
            no_child = 0
        else:
            childlist = find_children(self.dbstate.db, person)

        for child_handle in childlist:
            child = self.dbstate.db.get_person_from_handle(child_handle)
            if not child:
                continue

            if no_child:
                no_child = 0

            if find_children(self.dbstate.db, child):
                label = Gtk.Label(label='<b><i>%s</i></b>'
                                  % escape(name_displayer.display(child)))
            else:
                label = Gtk.Label(label=escape(name_displayer.display(child)))

            child_item = Gtk.MenuItem()
            label.set_use_markup(True)
            label.show()
            label.set_halign(Gtk.Align.START)
            child_item.add(label)
            child_item.connect("activate", self.move_to_node, child_handle)
            child_item.show()
            child_menu.append(child_item)

        if no_child:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

    def add_partner(self, obj):
        """
        Add partner to person (create new family to person).
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
        else:
            if self._config.get('interface.quiltview-center'):
                return False
            obj = self.get_object_at(event.x / self.scale,
                                     event.y / self.scale)
            if obj:
                if isinstance(obj, PersonNode):
                    self.set_path_lines(obj)
                elif isinstance(obj, FamilyNode):
                    self.show_family_name(obj.handle, event)
        return False

    def highlight_person(self, obj, color):
        (x1, x2) = self.calculate_segment_length(obj)
        self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                           x2+HEIGHT, obj.y-HEIGHT/2,
                           color))

    def get_ascendants(self, obj, color):
        for fam in obj.children:
            if fam in self.families:
                for parent in self.families[fam].parents:
                    self.get_ascendants(self.people[parent], color)
                    # prepare to draw the vertical bar
                    self.paths.append((self.families[fam].x+HEIGHT,
                                       obj.y+HEIGHT/2,
                                       self.families[fam].x+HEIGHT,
                                       self.people[parent].y-HEIGHT/2,
                                       color))
        # prepare to hightligt the name
        (x1, x2) = self.calculate_segment_length(obj)
        self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                           x2+HEIGHT, obj.y-HEIGHT/2,
                           color))

    def get_descendants(self, obj, color):
        for fam in obj.parents:
            if fam in self.families:
                for child in self.families[fam].children:
                    self.get_descendants(self.people[child], color)
                    # prepare to draw the vertical bar
                    self.paths.append((self.families[fam].x+HEIGHT,
                                       obj.y+HEIGHT/2,
                                       self.families[fam].x+HEIGHT,
                                       self.people[child].y-HEIGHT/2,
                                       color))
        # prepare to hightligt the name
        (x1, x2) = self.calculate_segment_length(obj)
        self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                           x2+HEIGHT, obj.y-HEIGHT/2,
                           color))

    def set_path_lines(self, obj):
        """
        obj : either a person or a family
        """
        self.paths = []
        _col = self._config.get
        color_path = _col('interface.quiltview-color-path')
        color_selected = _col('interface.quiltview-color-selected')
        if isinstance(obj, PersonNode):
            (x1, x2) = self.calculate_segment_length(obj)
            self.paths.append((x1+HEIGHT, obj.y+HEIGHT/2,
                               x2+HEIGHT, obj.y-HEIGHT/2,
                               color_selected))
            # Draw linking path for descendant
            for fam in obj.parents:
                if fam in self.families:
                    for child in self.families[fam].children:
                        self.get_descendants(self.people[child], color_path)
                        self.paths.append((self.families[fam].x+HEIGHT,
                                           obj.y+HEIGHT/4,
                                           self.families[fam].x+HEIGHT,
                                           self.people[child].y-HEIGHT/4,
                                           color_path))
            # Draw linking path for ascendant
            for fam in obj.children:
                if fam in self.families:
                    for parent in self.families[fam].parents:
                        self.get_ascendants(self.people[parent], color_path)
                        self.paths.append((self.families[fam].x+HEIGHT,
                                           obj.y+HEIGHT/4,
                                           self.families[fam].x+HEIGHT,
                                           self.people[parent].y-HEIGHT+HEIGHT/4,
                                           color_path))
            self.canvas.queue_draw()

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
        page_setup = Gtk.print_run_page_setup_dialog(None, page_setup,
                                                     self.print_settings)
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

        if win():
            res = self.print_op.run(Gtk.PrintOperationAction.PRINT_DIALOG,
                                    self.uistate.window)
        else:
            res = self.print_op.run(Gtk.PrintOperationAction.PREVIEW,
                                    self.uistate.window)

    def begin_print(self, operation, context):
        rect = self.canvas.get_allocation()
        self.pages_per_row = int(int(rect.width) *
                                 self.print_zoom / self.width_used + 1)
        self.nb_pages = int(self.pages_per_row *
                            int(int(rect.height) *
                                self.print_zoom / self.height_used + 1))
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
        x = ((page_nr % self.pages_per_row )
              * self.width_used) if page_nr > 0 else 0
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

    def can_configure(self):
        """
        See :class:`~gui.views.pageview.PageView
        :return: bool
        """
        return True

    #-------------------------------------------------------------------------
    #
    # QuiltView preferences
    #
    #-------------------------------------------------------------------------

    def _get_configure_page_funcs(self):
        """
        The function which is used to create the configuration window.
        """
        return [self.general_options]

    def general_options(self, configdialog):
        """
        Function that builds the widget in the configuration dialog
        for the general options.
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        self.path_entry = Gtk.Entry()
        configdialog.add_checkbox(grid,
                _('Center on the selected person.\nThe new position of the '
                  'person will be near the top left corner.'
                  ),
                0, 'interface.quiltview-center')
        configdialog.add_text(grid,
                _('The path color'),
                1, line_wrap=False)
        configdialog.add_color(grid, "",
                2, 'interface.quiltview-color-path')
        configdialog.add_text(grid,
                _('The selected person color'),
                3, line_wrap=False)
        configdialog.add_color(grid, "",
                4, 'interface.quiltview-color-selected')
        configdialog.add_slider(grid,
                _('The path transparency'),
                5, 'interface.quiltview-path-transparency',
                (1, 9))
        return _('General options'), grid
