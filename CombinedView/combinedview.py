# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2001-2007  Donald N. Allingham
# Copyright (C) 2009-2010  Gary Burton
# Copyright (C) 2015-2016  Nick Hall
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

"""
Combined View
"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
from html import escape
from operator import itemgetter
import pickle
import logging
import os
import re

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import GdkPixbuf

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.lib import (ChildRef, EventRoleType, EventType, Family,
                            FamilyRelType, Name, Person, Surname)
from gramps.gen.lib.date import Today
from gramps.gen.db import DbTxn
from navigationview import NavigationView
from taglist import TagList
from timeline import Timeline
from gramps.gui.uimanager import ActionGroup
from gramps.gui.editors import EditPerson, EditFamily, EditEvent
from gramps.gui.editors import FilterEditor
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.db import get_participant_from_event
from gramps.gui.utils import open_file_with_default_application
from gramps.gen.datehandler import displayer, get_date
from gramps.gen.utils.thumbnails import (get_thumbnail_image, SIZE_NORMAL,
                                         SIZE_LARGE)
from gramps.gen.config import config
from gramps.gen.relationship import get_relationship_calculator
from gramps.gui import widgets
from gramps.gui.widgets.reorderfam import Reorder
from gramps.gui.widgets.styledtexteditor import StyledTextEditor
from gramps.gui.widgets import ShadeBox
from gramps.gui.selectors import SelectorFactory
from gramps.gen.errors import WindowActiveError
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gen.const import CUSTOM_FILTERS
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                                 preset_name)
from gramps.gui.ddtargets import DdTargets
from gramps.gui.display import display_url
from gramps.gen.const import IMAGE_DIR
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext
ngettext = glocale.translation.ngettext # else "nearby" comments are ignored

_LOG = logging.getLogger("plugin.relview")

_GenderCode = {
    Person.MALE    : '\u2642',
    Person.FEMALE  : '\u2640',
    Person.UNKNOWN : '\u2650',
    }

_RETURN = Gdk.keyval_from_name("Return")
_KP_ENTER = Gdk.keyval_from_name("KP_Enter")
_SPACE = Gdk.keyval_from_name("space")
_LEFT_BUTTON = 1
_RIGHT_BUTTON = 3

URL_MATCH = re.compile(r'https?://[^\s]+')

class CombinedView(NavigationView):
    """
    View showing a textual representation of the relationships and events of
    the active person.
    """
    #settings in the config file
    CONFIGSETTINGS = (
        ('preferences.family-siblings', True),
        ('preferences.family-details', True),
        ('preferences.show-tags', True),
        ('preferences.relation-display-theme', "CLASSIC"),
        ('preferences.relation-shade', True),
        ('preferences.releditbtn', True),
        ('preferences.show-tags', True),
        ('preferences.vertical-details', True),
        )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(self, _('Combined'),
                                      pdata, dbstate, uistate,
                                      PersonBookmarks,
                                      nav_group)

        dbstate.connect('database-changed', self.change_db)
        uistate.connect('nameformat-changed', self.build_tree)
        self.redrawing = False

        self.child = None
        self.old_handle = None

        self.reorder_sensitive = False
        self.collapsed_items = {}

        self.person_tab = 'event'
        self.event_tab = 'participant'

        self.additional_uis.append(self.additional_ui)

        self.show_siblings = self._config.get('preferences.family-siblings')
        self.show_details = self._config.get('preferences.family-details')
        self.show_tags = self._config.get('preferences.show-tags')
        self.vertical = self._config.get('preferences.vertical-details')
        self.use_shade = self._config.get('preferences.relation-shade')
        self.theme = self._config.get('preferences.relation-display-theme')
        self.toolbar_visible = config.get('interface.toolbar-on')

    def _connect_db_signals(self):
        """
        implement from base class DbGUIElement
        Register the callbacks we need.
        """
        # Add a signal to pick up event changes, bug #1416
        self.callman.add_db_signal('event-update', self.family_update)

        self.callman.add_db_signal('person-update', self.person_update)
        self.callman.add_db_signal('person-rebuild', self.person_rebuild)
        self.callman.add_db_signal('family-update', self.family_update)
        self.callman.add_db_signal('family-add',    self.family_add)
        self.callman.add_db_signal('family-delete', self.family_delete)
        self.callman.add_db_signal('family-rebuild', self.family_rebuild)

        self.callman.add_db_signal('person-delete', self.redraw)

    def navigation_type(self):
        return None

    def can_configure(self):
        """
        See :class:`~gui.views.pageview.PageView
        :return: bool
        """
        return True

    def goto_handle(self, handle):
        self.change_object(handle)

    def shade_update(self, client, cnxn_id, entry, data):
        self.use_shade = self._config.get('preferences.relation-shade')
        self.toolbar_visible = config.get('interface.toolbar-on')
        self.uistate.modify_statusbar(self.dbstate)
        self.redraw()

    def config_update(self, client, cnxn_id, entry, data):
        self.show_siblings = self._config.get('preferences.family-siblings')
        self.show_details = self._config.get('preferences.family-details')
        self.show_tags = self._config.get('preferences.show-tags')
        self.vertical = self._config.get('preferences.vertical-details')
        self.redraw()

    def build_tree(self):
        self.redraw()

    def person_update(self, handle_list):
        if self.active:
            person = self.get_active()
            if person:
                while not self.change_object(person):
                    pass
            else:
                self.change_object(None)
        else:
            self.dirty = True

    def person_rebuild(self):
        """Large change to person database"""
        if self.active:
            self.bookmarks.redraw()
            person = self.get_active()
            if person:
                while not self.change_object(person):
                    pass
            else:
                self.change_object(None)
        else:
            self.dirty = True

    def family_update(self, handle_list):
        if self.active:
            person = self.get_active()
            if person:
                while not self.change_object(person):
                    pass
            else:
                self.change_object(None)
        else:
            self.dirty = True

    def family_add(self, handle_list):
        if self.active:
            person = self.get_active()
            if person:
                while not self.change_object(person):
                    pass
            else:
                self.change_object(None)
        else:
            self.dirty = True

    def family_delete(self, handle_list):
        if self.active:
            person = self.get_active()
            if person:
                while not self.change_object(person):
                    pass
            else:
                self.change_object(None)
        else:
            self.dirty = True

    def family_rebuild(self):
        if self.active:
            person = self.get_active()
            if person:
                while not self.change_object(person):
                    pass
            else:
                self.change_object(None)
        else:
            self.dirty = True

    def change_page(self):
        NavigationView.change_page(self)
        self.uistate.clear_filter_results()

    def get_stock(self):
        """
        Return the name of the stock icon to use for the display.
        This assumes that this icon has already been registered with
        GNOME as a stock icon.
        """
        return 'gramps-relation'

    def get_viewtype_stock(self):
        """Type of view in category
        """
        return 'gramps-relation'

    def build_widget(self):
        """
        Build the widget that contains the view, see
        :class:`~gui.views.pageview.PageView
        """
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        container.set_border_width(12)

        self.header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.header.show()

        self.stack = Gtk.Stack()
        ss = Gtk.StackSwitcher()
        ss.set_stack(self.stack)
        self.stack.show()
        ss.show()

        container.set_spacing(6)
        container.pack_start(self.header, False, False, 0)
        container.pack_start(Gtk.Separator(), False, False, 0)
        container.pack_start(ss, False, False, 0)
        container.pack_start(self.stack, True, True, 0)
        container.show_all()

        return container

    additional_ui = [  # Defines the UI string for UIManager
        '''
      <placeholder id="CommonGo">
      <section>
        <item>
          <attribute name="action">win.Back</attribute>
          <attribute name="label" translatable="yes">_Add Bookmark</attribute>
        </item>
        <item>
          <attribute name="action">win.Forward</attribute>
          <attribute name="label" translatable="yes">'''
        '''Organize Bookmarks...</attribute>
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
      <placeholder id='otheredit'>
        <item>
          <attribute name="action">win.Edit</attribute>
          <attribute name="label" translatable="yes">Edit...</attribute>
        </item>
        <item>
          <attribute name="action">win.AddParents</attribute>
          <attribute name="label" translatable="yes">'''
        '''Add New Parents...</attribute>
        </item>
        <item>
          <attribute name="action">win.ShareFamily</attribute>
          <attribute name="label" translatable="yes">'''
        '''Add Existing Parents...</attribute>
        </item>
        <item>
          <attribute name="action">win.AddSpouse</attribute>
          <attribute name="label" translatable="yes">Add Partner...</attribute>
        </item>
        <item>
          <attribute name="action">win.ChangeOrder</attribute>
          <attribute name="label" translatable="yes">_Reorder</attribute>
        </item>
        <item>
          <attribute name="action">win.FilterEdit</attribute>
          <attribute name="label" translatable="yes">'''
        '''Person Filter Editor</attribute>
        </item>
      </placeholder>
''',
        '''
      <section id="AddEditBook">
        <item>
          <attribute name="action">win.AddBook</attribute>
          <attribute name="label" translatable="yes">_Add Bookmark</attribute>
        </item>
        <item>
          <attribute name="action">win.EditBook</attribute>
          <attribute name="label" translatable="no">%s...</attribute>
        </item>
      </section>
''' % _('Organize Bookmarks'),  # Following are the Toolbar items
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
    <child groups='RW'>
      <object class="GtkToolButton">
        <property name="icon-name">gtk-edit</property>
        <property name="action-name">win.Edit</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Edit the active person</property>
        <property name="label" translatable="yes">Edit...</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RW'>
      <object class="GtkToolButton">
        <property name="icon-name">gramps-parents-add</property>
        <property name="action-name">win.AddParents</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Add a new set of parents</property>
        <property name="label" translatable="yes">Add</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RW'>
      <object class="GtkToolButton">
        <property name="icon-name">gramps-parents-open</property>
        <property name="action-name">win.ShareFamily</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Add person as child to an existing family</property>
        <property name="label" translatable="yes">Share</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RW'>
      <object class="GtkToolButton">
        <property name="icon-name">gramps-spouse</property>
        <property name="action-name">win.AddSpouse</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Add a new family with person as parent</property>
        <property name="label" translatable="yes">Partner</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RW'>
      <object class="GtkToolButton">
        <property name="icon-name">view-sort-ascending</property>
        <property name="action-name">win.ChangeOrder</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Change order of parents and families</property>
        <property name="label" translatable="yes">_Reorder</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
     ''']

    def define_actions(self):
        NavigationView.define_actions(self)

        self.order_action = ActionGroup(name=self.title + '/ChangeOrder')
        self.order_action.add_actions([
            ('ChangeOrder', self.reorder)])

        self.family_action = ActionGroup(name=self.title + '/Family')
        self.family_action.add_actions([
            ('Edit', self.edit_active, "<PRIMARY>Return"),
            ('AddSpouse', self.add_spouse),
            ('AddParents', self.add_parents),
            ('ShareFamily', self.select_parents)])

        self._add_action('FilterEdit', callback=self.filter_editor)
        self._add_action('PRIMARY-J', self.jump, '<PRIMARY>J')

        self._add_action_group(self.order_action)
        self._add_action_group(self.family_action)

        self.uimanager.set_actions_sensitive(self.order_action,
                                             self.reorder_sensitive)
        self.uimanager.set_actions_sensitive(self.family_action, False)

    def filter_editor(self, *obj):
        try:
            FilterEditor('Person', CUSTOM_FILTERS,
                         self.dbstate, self.uistate)
        except WindowActiveError:
            return

    def change_db(self, db):
        #reset the connects
        self._change_db(db)
        if self.child:
            list(map(self.vbox.remove, self.vbox.get_children()))
            list(map(self.header.remove, self.header.get_children()))
            self.child = None
        if self.active:
                self.bookmarks.redraw()
        self.history.clear()
        self.redraw()

    def redraw(self, *obj):
        active_person = self.get_active()
        if active_person:
            self.change_object(active_person)
        else:
            self.change_object(None)

    def change_object(self, obj):

        list(map(self.header.remove, self.header.get_children()))
        list(map(self.stack.remove, self.stack.get_children()))

        if obj is None:
            return

        self.change_active(obj)
        if obj[0] == 'Person':
            return self._change_person(obj[1])
        elif obj[0] == 'Event':
            return self._change_event(obj[1])

    def _change_person(self, handle):

        if self.redrawing:
            return False
        self.redrawing = True

        person = self.dbstate.db.get_person_from_handle(handle)
        if not person:
            self.uimanager.set_actions_sensitive(self.family_action, False)
            self.uimanager.set_actions_sensitive(self.order_action, False)
            self.redrawing = False
            return

        self.uimanager.set_actions_visible(self.family_action, True)
        self.uimanager.set_actions_visible(self.order_action, True)

        self.write_person_title(person)
        self.write_families(person)
        self.write_events(person)
        self.write_album(person)
        self.write_timeline(person)
        self.write_associations(person)

        #self.stack.set_visible_child_name(self.person_tab)

        self.redrawing = False
        self.uistate.modify_statusbar(self.dbstate)

        self.uimanager.set_actions_sensitive(self.order_action, self.reorder_sensitive)
        self.dirty = False

        return True

    def _change_event(self, handle):

        if self.redrawing:
            return False
        self.redrawing = True

        self.uimanager.set_actions_visible(self.family_action, False)
        self.uimanager.set_actions_visible(self.order_action, False)

        event = self.dbstate.db.get_event_from_handle(handle)
        self.write_event_title(event)
        self.write_participants(event)
        self.write_citations(event)

        #self.stack.set_visible_child_name(self.event_tab)

        self.redrawing = False
        self.uistate.modify_statusbar(self.dbstate)

        self.dirty = False

        return True

    def write_event_title(self, event):

        list(map(self.header.remove, self.header.get_children()))
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(0)

        # event title and edit button
        etype = str(event.get_type())
        desc = event.get_description()
        if desc:
            title = '%s (%s)' % (etype, desc)
        else:
            title = etype
        fmt = '<span size="larger" weight="bold">%s</span>'
        text = fmt % escape(title)
        label = widgets.MarkupLabel(text, halign=Gtk.Align.END)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_event, event.handle)
            button.set_tooltip_text(_('Edit %s') % title)
        else:
            button = None

        hbox = widgets.LinkBox(label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(event))
            hbox.pack_start(tag_list, False, False, 0)
        eventbox = self.make_dragbox(hbox, 'Event', event.get_handle())
        grid.attach(eventbox, 0, 0, 2, 1)

        subgrid = Gtk.Grid()
        subgrid.set_column_spacing(12)
        subgrid.set_row_spacing(0)
        eventbox = self.make_dragbox(subgrid, 'Event', event.get_handle())
        grid.attach(eventbox, 1, 1, 1, 1)

        # Gramps ID
        subgrid.attach(widgets.BasicLabel("%s:" % _('ID')), 1, 0, 1, 1)
        label = widgets.BasicLabel(event.gramps_id)
        label.set_hexpand(True)
        subgrid.attach(label, 2, 0, 1, 1)

        # Date
        subgrid.attach(widgets.BasicLabel("%s:" % 'Date'), 1, 1, 1, 1)
        subgrid.attach(widgets.BasicLabel(get_date(event)), 2, 1, 1, 1)

        # Place
        place = place_displayer.display_event(self.dbstate.db, event)
        subgrid.attach(widgets.BasicLabel("%s:" % 'Place'), 1, 2, 1, 1)
        subgrid.attach(widgets.BasicLabel(place), 2, 2, 1, 1)

        grid.show_all()
        self.header.pack_start(grid, False, True, 0)

        # Attributes
        attrs = event.get_attribute_list()
        if len(attrs):
            ex = Gtk.Expander(label='%s:' % _('Attributes'))
            attr_grid = self.get_attribute_grid(attrs)
            ex.set_margin_start(24)
            ex.add(attr_grid)
            ex.show()
            self.header.pack_start(ex, False, True, 0)

    def write_person_title(self, person):

        list(map(self.header.remove, self.header.get_children()))
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(0)

        # name and edit button
        name = name_displayer.display(person)
        fmt = '<span size="larger" weight="bold">%s</span>'
        text = fmt % escape(name)
        label = widgets.DualMarkupLabel(text, _GenderCode[person.gender],
                                        halign=Gtk.Align.END)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_button_press,
                                        person.handle)
            button.set_tooltip_text(_('Edit %s') % name)
        else:
            button = None


        hbox = widgets.LinkBox(label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(person))
            hbox.pack_start(tag_list, False, False, 0)
        eventbox = self.make_dragbox(hbox, 'Person', person.get_handle())
        grid.attach(eventbox, 0, 0, 2, 1)

        subgrid = Gtk.Grid()
        subgrid.set_column_spacing(12)
        subgrid.set_row_spacing(0)
        eventbox = self.make_dragbox(subgrid, 'Person', person.get_handle())
        grid.attach(eventbox, 1, 1, 1, 1)

        # GRAMPS ID
        subgrid.attach(widgets.BasicLabel("%s:" % _('ID')), 1, 0, 1, 1)
        label = widgets.BasicLabel(person.gramps_id)
        label.set_hexpand(True)
        subgrid.attach(label, 2, 0, 1, 1)

        # Birth event.
        birth = get_birth_or_fallback(self.dbstate.db, person)
        if birth:
            birth_title = birth.get_type()
        else:
            birth_title = _("Birth")

        subgrid.attach(widgets.BasicLabel("%s:" % birth_title), 1, 1, 1, 1)
        subgrid.attach(widgets.BasicLabel(self.format_event(birth)), 2, 1, 1, 1)

        death = get_death_or_fallback(self.dbstate.db, person)
        if death:
            death_title = death.get_type()
        else:
            death_title = _("Death")

        showed_death = False
        if birth:
            birth_date = birth.get_date_object()
            if (birth_date and birth_date.get_valid()):
                if death:
                    death_date = death.get_date_object()
                    if (death_date and death_date.get_valid()):
                        age = death_date - birth_date
                        subgrid.attach(widgets.BasicLabel("%s:" % death_title),
                                      1, 2, 1, 1)
                        subgrid.attach(widgets.BasicLabel("%s (%s)" %
                                                         (self.format_event(death), age),
                                                         Pango.EllipsizeMode.END),
                                      2, 2, 1, 1)
                        showed_death = True
                if not showed_death:
                    age = Today() - birth_date
                    if probably_alive(person, self.dbstate.db):
                        subgrid.attach(widgets.BasicLabel("%s:" % _("Alive")),
                                      1, 2, 1, 1)
                        subgrid.attach(widgets.BasicLabel("(%s)" % age, Pango.EllipsizeMode.END),
                                      2, 2, 1, 1)
                    else:
                        subgrid.attach(widgets.BasicLabel("%s:" % _("Death")),
                                      1, 2, 1, 1)
                        subgrid.attach(widgets.BasicLabel("%s (%s)" % (_("unknown"), age),
                                                         Pango.EllipsizeMode.END),
                                      2, 2, 1, 1)
                    showed_death = True

        if not showed_death:
            subgrid.attach(widgets.BasicLabel("%s:" % death_title),
                          1, 2, 1, 1)
            subgrid.attach(widgets.BasicLabel(self.format_event(death)),
                          2, 2, 1, 1)

        mbox = Gtk.Box()
        mbox.add(grid)

        # image
        image_list = person.get_media_list()
        if image_list:
            button = self.get_thumbnail(image_list[0], size=SIZE_NORMAL)
            if button:
                mbox.pack_end(button, False, True, 0)
        mbox.show_all()
        self.header.pack_start(mbox, False, True, 0)

    def get_thumbnail(self, media_ref, size):
        mobj = self.dbstate.db.get_media_from_handle(media_ref.ref)
        if mobj and mobj.get_mime_type()[0:5] == "image":
            pixbuf = get_thumbnail_image(
                            media_path_full(self.dbstate.db,
                                            mobj.get_path()),
                            rectangle=media_ref.get_rectangle(),
                            size=size)
            image = Gtk.Image()
            image.set_from_pixbuf(pixbuf)
            button = Gtk.Button()
            button.add(image)
            button.connect("clicked", lambda obj: self.view_photo(mobj))
            button.show_all()
            return button
        return None

    def view_photo(self, photo):
        """
        Open this picture in the default picture viewer.
        """
        photo_path = media_path_full(self.dbstate.db, photo.get_path())
        open_file_with_default_application(photo_path, self.uistate)

    def format_event(self, event):
        if event:
            dobj = event.get_date_object()
            phandle = event.get_place_handle()
            if phandle:
                pname = place_displayer.display_event(self.dbstate.db, event)
            else:
                pname = None

            value = {
                'date' : displayer.display(dobj),
                'place' : pname,
                }
        else:
            pname = None
            dobj = None

        if dobj:
            if pname:
                return _('%(date)s in %(place)s') % value
            else:
                return '%(date)s' % value
        elif pname:
            return pname
        else:
            return ''

    def get_name(self, handle, use_gender=False):
        if handle:
            person = self.dbstate.db.get_person_from_handle(handle)
            name = name_displayer.display(person)
            if use_gender:
                gender = _GenderCode[person.gender]
            else:
                gender = ""
            return (name, gender)
        else:
            return (_("Unknown"), "")

    def make_dragbox(self, box, dragtype, handle):
        eventbox = ShadeBox(self.use_shade)
        eventbox.add(box)

        if handle is not None:
            if dragtype == 'Person':
                self._set_draggable(eventbox, handle, DdTargets.PERSON_LINK, 'gramps-person')
            elif dragtype == 'Family':
                self._set_draggable(eventbox, handle, DdTargets.FAMILY_LINK, 'gramps-family')
            elif dragtype == 'Event':
                self._set_draggable(eventbox, handle, DdTargets.EVENT, 'gramps-event')
            elif dragtype == 'Citation':
                self._set_draggable(eventbox, handle, DdTargets.CITATION_LINK, 'gramps-citation')

        return eventbox

    def _set_draggable(self, eventbox, object_h, dnd_type, stock_icon):
        """
        Register the given eventbox as a drag_source with given object_h
        """
        eventbox.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                                 [], Gdk.DragAction.COPY)
        tglist = Gtk.TargetList.new([])
        tglist.add(dnd_type.atom_drag_type,
                   dnd_type.target_flags,
                   dnd_type.app_id)
        eventbox.drag_source_set_target_list(tglist)
        eventbox.drag_source_set_icon_name(stock_icon)
        eventbox.connect('drag_data_get',
                         self._make_drag_data_get_func(object_h, dnd_type))

    def _make_drag_data_get_func(self, object_h, dnd_type):
        """
        Generate at runtime a drag_data_get function returning the given dnd_type and object_h
        """
        def drag_data_get(widget, context, sel_data, info, time):
            if info == dnd_type.app_id:
                data = (dnd_type.drag_type, id(self), object_h, 0)
                sel_data.set(dnd_type.atom_drag_type, 8, pickle.dumps(data))
        return drag_data_get

    def info_box(self, handle):
        if self.vertical:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        else:
            box = Gtk.Box()
            box.set_spacing(6)

        person = self.dbstate.db.get_person_from_handle(handle)
        if not person:
            return box

        birth = get_birth_or_fallback(self.dbstate.db, person)
        label1 = widgets.MarkupLabel(self.format_box(birth, EventType.BIRTH))
        box.pack_start(label1, False, False, 0)

        death = get_death_or_fallback(self.dbstate.db, person)
        label2 = widgets.MarkupLabel(self.format_box(death, EventType.DEATH))
        box.pack_start(label2, False, False, 0)

        return box

    def format_box(self, event, main_type):
        if event:
            dobj = event.get_date_object()
            pname = place_displayer.display_event(self.dbstate.db, event)
            value = {
                'abbrev': event.type.get_abbreviation(),
                'date' : displayer.display(dobj),
                'place' : pname
                }
        else:
            return ''

        if pname and not dobj.is_empty():
            info = _('%(abbrev)s %(date)s in %(place)s') % value
        else:
            info = _('%(abbrev)s %(date)s%(place)s') % value

        if event.type != main_type:
            return '<i>%s</i>' % escape(info)
        else:
            return escape(info)

    def info_string(self, handle):
        person = self.dbstate.db.get_person_from_handle(handle)
        if not person:
            return None

        birth = get_birth_or_fallback(self.dbstate.db, person)
        if birth and birth.get_type() != EventType.BIRTH:
            sdate = get_date(birth)
            if sdate:
                bdate = "<i>%s</i>" % escape(sdate)
            else:
                bdate = ""
        elif birth:
            bdate = escape(get_date(birth))
        else:
            bdate = ""

        death = get_death_or_fallback(self.dbstate.db, person)
        if death and death.get_type() != EventType.DEATH:
            sdate = get_date(death)
            if sdate:
                ddate = "<i>%s</i>" % escape(sdate)
            else:
                ddate = ""
        elif death:
            ddate = escape(get_date(death))
        else:
            ddate = ""

        if bdate and ddate:
            value = _("%(birthabbrev)s %(birthdate)s, %(deathabbrev)s %(deathdate)s") % {
                'birthabbrev': birth.type.get_abbreviation(),
                'deathabbrev': death.type.get_abbreviation(),
                'birthdate' : bdate,
                'deathdate' : ddate
                }
        elif bdate:
            value = _("%(event)s %(date)s") % {'event': birth.type.get_abbreviation(), 'date': bdate}
        elif ddate:
            value = _("%(event)s %(date)s") % {'event': death.type.get_abbreviation(), 'date': ddate}
        else:
            value = ""
        return value

    def _person_link(self, obj, event, handle):
        self._link(event, 'Person', handle)

    def _event_link(self, obj, event, handle):
        self._link(event, 'Event', handle)

    def _link(self, event, obj_type, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.change_active((obj_type, handle))
        elif button_activated(event, _RIGHT_BUTTON):
            self.my_menu = Gtk.Menu()
            self.my_menu.append(self.build_menu_item(obj_type, handle))
            if Gtk.get_minor_version() >= 22:
                self.my_menu.popup_at_pointer(event)
            else:
                self.my_menu.popup(None, None, None, None,
                                   event.button, event.time)

    def build_menu_item(self, obj_type, handle):

        if obj_type == 'Person':
            person = self.dbstate.db.get_person_from_handle(handle)
            name = name_displayer.display(person)
        elif obj_type == 'Event':
            event = self.dbstate.db.get_event_from_handle(handle)
            name = str(event.get_type())

        item = Gtk.ImageMenuItem(None)
        image = Gtk.Image.new_from_icon_name('gtk-edit', Gtk.IconSize.MENU)
        image.show()
        label = Gtk.Label(label=_("Edit %s") % name)
        label.show()
        label.set_halign(Gtk.Align.START)

        item.set_image(image)
        item.add(label)

        item.connect('activate', self.edit_menu, handle, obj_type)
        item.show()
        return item

    def edit_menu(self, obj, handle, obj_type):
        if obj_type == 'Person':
            person = self.dbstate.db.get_person_from_handle(handle)
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
        elif obj_type == 'Event':
            event = self.dbstate.db.get_event_from_handle(handle)
            try:
                EditEvent(self.dbstate, self.uistate, [], event)
            except WindowActiveError:
                pass

    def write_relationship(self, box, family):
        msg = _('Relationship type: %s') % escape(str(family.get_relationship()))
        box.add(widgets.MarkupLabel(msg))

    def write_relationship_events(self, vbox, family):
        value = False
        for event_ref in family.get_event_ref_list():
            handle = event_ref.ref
            event = self.dbstate.db.get_event_from_handle(handle)
            if (event and event.get_type().is_relationship_event() and
                (event_ref.get_role() == EventRoleType.FAMILY or
                 event_ref.get_role() == EventRoleType.PRIMARY)):
                self.write_event_ref(vbox, event.get_type().string, event)
                value = True
        return value

    def write_event_ref(self, vbox, ename, event):
        if event:
            dobj = event.get_date_object()
            phandle = event.get_place_handle()
            if phandle:
                pname = place_displayer.display_event(self.dbstate.db, event)
            else:
                pname = None

            value = {
                'date' : displayer.display(dobj),
                'place' : pname,
                'event_type' : ename,
                }
        else:
            pname = None
            dobj = None
            value = { 'event_type' : ename, }

        if dobj:
            if pname:
                self.write_data(
                    vbox, _('%(event_type)s: %(date)s in %(place)s') %
                    value)
            else:
                self.write_data(
                    vbox, _('%(event_type)s: %(date)s') % value)
        elif pname:
            self.write_data(
                vbox, _('%(event_type)s: %(place)s') % value)
        else:
            self.write_data(
                vbox, '%(event_type)s:' % value)

    def write_data(self, box, title):
        box.add(widgets.BasicLabel(title))

##############################################################################
#
# Timeline
#
##############################################################################

    def write_timeline(self, person):

        grid = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(grid)
        scroll.show_all()
        self.stack.add_titled(scroll, 'timeline', _('Timeline'))

        events = []
        start_date = None
        # Personal events
        for index, event_ref in enumerate(person.get_event_ref_list()):
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            date = event.get_date_object()
            if (start_date is None and event_ref.role.is_primary() and
                (event.type.is_birth_fallback() or
                 event.type == EventType.BIRTH)):
                start_date = date
            sortval = date.get_sort_value()
            events.append(((sortval, index), event_ref, None))

        # Family events
        for family_handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            spouse = None
            if father_handle == person.handle:
                if mother_handle:
                    spouse = self.dbstate.db.get_person_from_handle(mother_handle)
            else:
                if father_handle:
                    spouse = self.dbstate.db.get_person_from_handle(father_handle)
            for event_ref in family.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(event_ref.ref)
                sortval = event.get_date_object().get_sort_value()
                events.append(((sortval, 0), event_ref, spouse))

        # Write all events sorted by date
        for index, event in enumerate(sorted(events, key=itemgetter(0))):
            self.write_node(grid, event[1], event[2], index+1, start_date)

        grid.show_all()

    def write_node(self, grid, event_ref, spouse, index, start_date):
        handle = event_ref.ref
        event = self.dbstate.db.get_event_from_handle(handle)
        etype = str(event.get_type())
        desc = event.get_description()
        who = get_participant_from_event(self.dbstate.db, handle)

        title = etype
        if desc:
            title = '%s (%s)' % (title, desc)
        if spouse:
            spouse_name = name_displayer.display(spouse)
            title = '%s - %s' % (title, spouse_name)

        role = event_ref.get_role()
        if role in (EventRoleType.PRIMARY, EventRoleType.FAMILY):
            emph = True
        else:
            emph = False
            title = '%s of %s' % (title, who)

        vbox1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        link_func = self._event_link
        name = (title, None)
        handle = event_ref.ref
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        link_label.set_tooltip_text(_('Click to make this event active'))
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_event, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = widgets.LinkBox(link_label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(event))
            hbox.pack_start(tag_list, False, False, 0)
        vbox1.pack_start(hbox, False, False, 0)

        pname = place_displayer.display_event(self.dbstate.db, event)
        vbox1.pack_start(widgets.BasicLabel(pname), False, False, 0)
        vbox1.set_vexpand(False)
        vbox1.set_valign(Gtk.Align.CENTER)
        vbox1.show_all()

        eventbox = self.make_dragbox(vbox1, 'Event', handle)
        eventbox.set_hexpand(True)
        eventbox.set_vexpand(False)
        eventbox.set_valign(Gtk.Align.CENTER)
        eventbox.set_margin_top(1)
        eventbox.set_margin_bottom(1)
        eventbox.show_all()

        vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dobj = event.get_date_object()
        date = widgets.BasicLabel(displayer.display(dobj))
        vbox2.pack_start(date, False, False, 0)
        if start_date is not None:
            age_precision = config.get('preferences.age-display-precision')
            diff = (dobj - start_date).format(precision=age_precision)
            age = widgets.BasicLabel(diff)
            vbox2.pack_start(age, False, False, 0)
        vbox2.set_valign(Gtk.Align.CENTER)
        grid.add(vbox2)

        tl = Timeline()
        grid.attach_next_to(tl, vbox2, Gtk.PositionType.RIGHT, 1, 1)

        grid.attach_next_to(eventbox, tl, Gtk.PositionType.RIGHT, 1, 1)

##############################################################################
#
# Events list
#
##############################################################################

    def write_events(self, person):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        self.stack.add_titled(scroll, 'event', _('Events'))

        events = []
        # Personal events
        for index, event_ref in enumerate(person.get_event_ref_list()):
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            sortval = event.get_date_object().get_sort_value()
            events.append(((sortval, index), event_ref, None))

        # Family events
        for family_handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)
            father_handle = family.get_father_handle()
            mother_handle = family.get_mother_handle()
            spouse = None
            if father_handle == person.handle:
                if mother_handle:
                    spouse = self.dbstate.db.get_person_from_handle(mother_handle)
            else:
                if father_handle:
                    spouse = self.dbstate.db.get_person_from_handle(father_handle)
            for event_ref in family.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(event_ref.ref)
                sortval = event.get_date_object().get_sort_value()
                events.append(((sortval, 0), event_ref, spouse))

        # Write all events sorted by date
        for index, event in enumerate(sorted(events, key=itemgetter(0))):
            self.write_event(event[1], event[2], index+1)

    def write_event(self, event_ref, spouse, index):
        handle = event_ref.ref
        event = self.dbstate.db.get_event_from_handle(handle)
        etype = str(event.get_type())
        desc = event.get_description()
        who = get_participant_from_event(self.dbstate.db, handle)

        title = etype
        if desc:
            title = '%s (%s)' % (title, desc)
        if spouse:
            spouse_name = name_displayer.display(spouse)
            title = '%s - %s' % (title, spouse_name)

        role = event_ref.get_role()
        if role in (EventRoleType.PRIMARY, EventRoleType.FAMILY):
            emph = True
        else:
            emph = False
            title = '%s of %s' % (title, who)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        link_func = self._event_link
        name = (title, None)
        handle = event_ref.ref
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        link_label.set_tooltip_text(_('Click to make this event active'))
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_event, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = widgets.LinkBox(link_label, button)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(event))
            hbox.pack_start(tag_list, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        line2 = self.format_event(event)
        vbox.pack_start(widgets.BasicLabel(line2), False, False, 0)

        for handle in event.get_citation_list():
            self.write_citation(vbox, handle)

        eventbox = self.make_dragbox(vbox, 'Event', handle)
        eventbox.show_all()
        self.vbox2.pack_start(eventbox, False, False, 1)

    def write_citation(self, vbox, chandle):
        citation = self.dbstate.db.get_citation_from_handle(chandle)
        shandle = citation.get_reference_handle()
        source = self.dbstate.db.get_source_from_handle(shandle)
        heading = source.get_title()
        page = citation.get_page()
        if page:
            heading += ' \u2022 ' + page

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        url_label = self.get_url(citation)
        if url_label:
            box.pack_start(url_label, False, False, 0)
        hbox = self.load_images(citation)
        box.pack_start(hbox, False, False, 0)

        if len(hbox.get_children()) > 0 or url_label:
            exp = Gtk.Expander(label=heading)
            exp.add(box)
            vbox.pack_start(exp, False, False, 0)
        else:
            label = widgets.BasicLabel(heading)
            vbox.pack_start(label, False, False, 0)

    def load_images(self, citation):
        """
        Load the primary image into the main form if it exists.
        """
        images = Gtk.Box(False, 3)

        media_list = citation.get_media_list()
        for media_ref in media_list:
            media_handle = media_ref.get_reference_handle()
            media = self.dbstate.db.get_media_from_handle(media_handle)
            full_path = media_path_full(self.dbstate.db, media.get_path())
            mime_type = media.get_mime_type()
            if mime_type and mime_type.startswith("image"):
                photo = widgets.Photo(self.uistate.screen_height() < 1000)
                photo.set_image(full_path, mime_type, media_ref.get_rectangle())
                photo.set_uistate(self.uistate, media_handle)
                images.pack_start(photo, False, False, 0)

        return images

    def get_url(self, citation):
        for handle in citation.get_note_list():
            note = self.dbstate.db.get_note_from_handle(handle)
            text = note.get()
            url_match = re.compile(r'https?://[^\s]+')
            result = URL_MATCH.search(text)
            if result:
                url = result.group(0)
                link_func = lambda x,y,z: display_url(url)
                name = (url, None)
                link_label = widgets.LinkLabel(name, link_func, None, False,
                                       theme=self.theme)
                link_label.set_tooltip_text(_('Click to visit this link'))
                return link_label
        return None


##############################################################################
#
# Album
#
##############################################################################

    def write_album(self, person):

        self.vbox2 = Gtk.Grid(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        self.stack.add_titled(scroll, 'album', _('Album'))

        self.write_media(person.get_media_list(), None)

        for event_ref in person.get_event_ref_list():
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)

            self.write_media(event.get_media_list(), event)

        for family_handle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(family_handle)

            self.write_media(family.get_media_list(), None)

            for event_ref in family.get_event_ref_list():
                event = self.dbstate.db.get_event_from_handle(event_ref.ref)

                self.write_media(event.get_media_list(), event)

    def write_media(self, media_list, event):
        for media_ref in media_list:

            mobj = self.dbstate.db.get_media_from_handle(media_ref.ref)
            button = self.get_thumbnail(media_ref, size=SIZE_LARGE)
            if button:

                self.vbox2.add(button)

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

                if event:
                    etype = str(event.get_type())
                    label = Gtk.Label(etype)
                    vbox.pack_start(label, False, False, 0)
                    who = get_participant_from_event(self.dbstate.db, event.handle)
                    label = Gtk.Label(who)
                    vbox.pack_start(label, False, False, 0)
                    date_place = self.format_event(event)
                    label = Gtk.Label(date_place)
                    vbox.pack_start(label, False, False, 0)

                notes = mobj.get_note_list()
                if len(notes) > 0:
                    note = self.dbstate.db.get_note_from_handle(notes[0])
                    texteditor = StyledTextEditor()
                    texteditor.set_editable(False)
                    texteditor.set_wrap_mode(Gtk.WrapMode.WORD)
                    texteditor.set_text(note.get_styledtext())
                    texteditor.set_hexpand(True)
                    texteditor.show()
                    vbox.pack_start(texteditor, True, True, 0)
                    vbox.show_all()

                self.vbox2.attach_next_to(vbox, button,
                                          Gtk.PositionType.RIGHT, 1, 1)

##############################################################################
#
# Associations
#
##############################################################################

    def write_associations(self, person):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        self.stack.add_titled(scroll, 'associations', _('Associations'))

        for person_ref in person.get_person_ref_list():
            self.write_association(person, person_ref)


    def write_association(self, person1, person_ref):

        vbox = self.write_person('assoc', person_ref.ref)

        assoc = Gtk.Label(_('Association') + _(': ') + person_ref.rel)
        assoc.set_halign(Gtk.Align.START)
        vbox.pack_start(assoc, False, False, 0)

        calc = get_relationship_calculator()
        person2 = self.dbstate.db.get_person_from_handle(person_ref.ref)
        rel_txt = calc.get_one_relationship(self.dbstate.db, person1, person2)
        rel = Gtk.Label(_('Relationship') + _(': ') + rel_txt)
        rel.set_halign(Gtk.Align.START)
        vbox.pack_start(rel, False, False, 0)

        eventbox = self.make_dragbox(vbox, 'Person', person_ref.ref)
        eventbox.show_all()
        self.vbox2.pack_start(eventbox, False, False, 1)


##############################################################################
#
# Participants list
#
##############################################################################

    def write_participants(self, event):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        self.stack.add_titled(scroll, 'participant', _('Participants'))

        roles = {}
        for item in self.dbstate.db.find_backlink_handles(event.handle,
                include_classes=['Person', 'Family']):

            handle = item[1]
            if item[0] == 'Person':
                obj = self.dbstate.db.get_person_from_handle(handle)
            elif item[0] == 'Family':
                obj = self.dbstate.db.get_family_from_handle(handle)

            for eventref in obj.get_event_ref_list():
                if eventref.ref == event.handle:
                    participant = (item[0], obj, eventref)
                    if str(eventref.role) not in roles:
                        roles[str(eventref.role)] = [participant]
                    else:
                        roles[str(eventref.role)].append(participant)

        for role in roles.keys():
            self.write_role(role, roles[role])

    def write_role(self, role, participant_list):

        title = '<span weight="bold">%s: </span>' % role
        label = widgets.MarkupLabel(title)
        self.vbox2.pack_start(label, False, False, 2)

        participants = []
        for participant in participant_list:
            obj_type, obj, eventref = participant
            order = 0
            attrs = eventref.get_attribute_list()
            for attr in attrs:
                if str(attr.get_type()) == _('Order'):
                    order = int(attr.get_value())
            if obj_type == 'Person':
                participants.append((order, obj, attrs))
            elif obj_type == 'Family':
                father_handle = obj.get_father_handle()
                if father_handle:
                    father = self.dbstate.db.get_person_from_handle(father_handle)
                    participants.append((order, father, []))
                mother_handle = obj.get_mother_handle()
                if mother_handle:
                    mother = self.dbstate.db.get_person_from_handle(mother_handle)
                    participants.append((order, mother, []))

        for person in sorted(participants, key=lambda x: x[0]):
            self.write_participant(person[1], person[2])

    def write_participant(self, person, attrs):

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        handle = person.handle
        name = self.get_name(handle, True)
        if has_children(self.dbstate.db, person):
            emph = True
        else:
            emph = False
        link_func = self._person_link
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_button_press, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = Gtk.Box()
        hbox.set_spacing(6)
        hbox.pack_start(link_label, False, False, 0)
        if self.show_details:
            box = self.info_box(handle)
            if box:
                hbox.pack_start(box, False, False, 0)
        if button is not None:
            hbox.pack_start(button, False, False, 0)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(person))
            hbox.pack_start(tag_list, False, False, 0)
        vbox.pack_start(hbox, False, False, 0)

        # Write attributes
        attr_grid = self.get_attribute_grid(attrs)
        attr_grid.set_margin_start(24)
        vbox.pack_start(attr_grid, False, False, 0)

        eventbox = self.make_dragbox(vbox, 'Person', handle)
        eventbox.show_all()

        self.vbox2.pack_start(eventbox, False, False, 1)

    def get_attribute_grid(self, attrs):
        grid = Gtk.Grid()
        row = 0
        for attr in attrs:
            if str(attr.get_type()) != _('Order'):
                label = widgets.BasicLabel('%s: ' % str(attr.get_type()))
                grid.attach(label, 0, row, 1, 1)
                label = widgets.BasicLabel(attr.get_value())
                grid.attach(label, 1, row, 1, 1)
                row += 1
        grid.show_all()
        return grid

##############################################################################
#
# Citations list
#
##############################################################################

    def write_citations(self, event):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        self.stack.add_titled(scroll, 'citation', _('Citations'))

        for handle in event.get_citation_list():
            self.write_full_citation(handle)

    def write_full_citation(self, chandle):

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        citation = self.dbstate.db.get_citation_from_handle(chandle)
        shandle = citation.get_reference_handle()
        source = self.dbstate.db.get_source_from_handle(shandle)
        heading = source.get_title() + ' ' + citation.get_page()

        vbox.pack_start(widgets.BasicLabel(heading), False, False, 0)

        hbox = self.load_images(citation)
        vbox.pack_start(hbox, False, False, 0)

        eventbox = self.make_dragbox(vbox, 'Citation', chandle)
        eventbox.show_all()

        self.vbox2.pack_start(eventbox, False, False, 1)

##############################################################################
#
# Families list
#
##############################################################################

    def write_families(self, person):

        self.vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scroll = Gtk.ScrolledWindow()
        scroll.add(self.vbox2)
        scroll.show_all()
        self.stack.add_titled(scroll, 'relationship', _('Relationships'))

        family_handle_list = person.get_parent_family_handle_list()

        self.reorder_sensitive = len(family_handle_list)> 1

        if family_handle_list:
            for family_handle in family_handle_list:
                if family_handle:
                    self.write_parents(family_handle, person)
        else:
            heading = self.write_label(_('Parents'), None, True)
            self.vbox2.pack_start(heading, False, True, 0)

        family_handle_list = person.get_family_handle_list()

        if not self.reorder_sensitive:
            self.reorder_sensitive = len(family_handle_list)> 1

        if family_handle_list:
            for family_handle in family_handle_list:
                if family_handle:
                    self.write_family(family_handle, person)

        self.vbox2.show_all()

    def write_parents(self, family_handle, person = None):
        family = self.dbstate.db.get_family_from_handle(family_handle)
        if not family:
            return

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        heading = self.write_label(_('Parents'), family, True)
        vbox.pack_start(heading, False, False, 1)
        f_handle = family.get_father_handle()
        box = self.write_person(_('Father'), f_handle)
        ebox = self.make_dragbox(box, 'Person', f_handle)
        vbox.pack_start(ebox, False, False, 1)
        m_handle = family.get_mother_handle()
        box = self.write_person(_('Mother'), m_handle)
        ebox = self.make_dragbox(box, 'Person', m_handle)
        vbox.pack_start(ebox, False, False, 1)

        if self.show_siblings:
            active = self.get_handle()

            count = len(family.get_child_ref_list())
            ex2 = Gtk.Expander(label='%s (%s):' % (_('Siblings'), count))
            ex2.set_margin_start(24)
            ex2.set_expanded(True)
            vbox.pack_start(ex2, False, False, 6)

            vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            hbox = Gtk.Box()
            addchild = widgets.IconButton(self.add_child_to_fam,
                                          family.handle,
                                          'list-add')
            addchild.set_tooltip_text(_('Add new child to family'))
            selchild = widgets.IconButton(self.sel_child_to_fam,
                                          family.handle,
                                          'gtk-index')
            selchild.set_tooltip_text(_('Add existing child to family'))
            hbox.pack_start(addchild, False, True, 0)
            hbox.pack_start(selchild, False, True, 0)

            vbox2.pack_start(hbox, False, False, 0)
            i = 1
            child_list = [ref.ref for ref in family.get_child_ref_list()]
            for child_handle in child_list:
                child_should_be_linked = (child_handle != active)
                widget = self.write_child(child_handle, i, child_should_be_linked)
                vbox2.pack_start(widget, True, True, 1)
                i += 1

            ex2.add(vbox2)

        self.vbox2.pack_start(vbox, False, True, 0)

    def write_family(self, family_handle, person = None):
        family = self.dbstate.db.get_family_from_handle(family_handle)
        if family is None:
            from gramps.gui.dialog import WarningDialog
            WarningDialog(
                _('Broken family detected'),
                _('Please run the Check and Repair Database tool'),
                parent=self.uistate.window)
            return

        father_handle = family.get_father_handle()
        mother_handle = family.get_mother_handle()
        if self.get_handle() == father_handle:
            handle = mother_handle
        else:
            handle = father_handle

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        heading = self.write_label(_('Family'), family, False)
        vbox.pack_start(heading, False, False, 1)

        if handle or family.get_relationship() != FamilyRelType.UNKNOWN:
            box = self.write_person(_('Spouse'), handle)
            if not self.write_relationship_events(box, family):
                self.write_relationship(box, family)
            ebox = self.make_dragbox(box, 'Person', handle)
            vbox.pack_start(ebox, False, False, 1)

        count = len(family.get_child_ref_list())
        ex2 = Gtk.Expander(label='%s (%s):' % (_('Children'), count))
        ex2.set_expanded(True)
        ex2.set_margin_start(24)
        vbox.pack_start(ex2, False, False, 6)

        vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        hbox = Gtk.Box()
        addchild = widgets.IconButton(self.add_child_to_fam,
                                      family.handle,
                                      'list-add')
        addchild.set_tooltip_text(_('Add new child to family'))
        selchild = widgets.IconButton(self.sel_child_to_fam,
                                      family.handle,
                                      'gtk-index')
        selchild.set_tooltip_text(_('Add existing child to family'))
        hbox.pack_start(addchild, False, True, 0)
        hbox.pack_start(selchild, False, True, 0)

        vbox2.pack_start(hbox, False, False, 0)

        i = 1
        child_list = family.get_child_ref_list()
        for child_ref in child_list:
            widget = self.write_child(child_ref.ref, i, True)
            vbox2.pack_start(widget, True, True, 1)
            i += 1

        ex2.add(vbox2)

        self.vbox2.pack_start(vbox, False, True, 0)

    def write_label(self, title, family, is_parent):
        """
        Write a Family header row
        Shows following elements:
        (Parents/Family title label, Family gramps_id, and add-choose-edit-delete buttons)
        """
        hbox = Gtk.Box()
        if family:
            msg = '<b>%s (%s):</b>' % (escape(title), escape(family.gramps_id))
        else:
            msg = '<b>%s:</b>' % escape(title)
        label = widgets.MarkupLabel(msg, halign=Gtk.Align.START)
        hbox.pack_start(label, False, True, 0)

        bbox = Gtk.Box()
        if is_parent:
            call_fcn = self.add_parent_family
            del_fcn = self.delete_parent_family
            add_msg = _('Add a new set of parents')
            sel_msg = _('Add person as child to an existing family')
            edit_msg = _('Edit parents')
            ord_msg = _('Reorder parents')
            del_msg = _('Remove person as child of these parents')
        else:
            add_msg = _('Add a new family with person as parent')
            sel_msg = None
            edit_msg = _('Edit family')
            ord_msg = _('Reorder families')
            del_msg = _('Remove person as parent in this family')
            call_fcn = self.add_family
            del_fcn = self.delete_family

        if not self.toolbar_visible and not self.dbstate.db.readonly:
            # Show edit-Buttons if toolbar is not visible
            if self.reorder_sensitive:
                add = widgets.IconButton(self.reorder_button_press, None,
                                         'view-sort-ascending')
                add.set_tooltip_text(ord_msg)
                bbox.pack_start(add, False, True, 0)

            add = widgets.IconButton(call_fcn, None, 'list-add')
            add.set_tooltip_text(add_msg)
            bbox.pack_start(add, False, True, 0)

            if is_parent:
                add = widgets.IconButton(self.select_family, None,
                                         'gtk-index')
                add.set_tooltip_text(sel_msg)
                bbox.pack_start(add, False, True, 0)

        if family:
            edit = widgets.IconButton(self.edit_family, family.handle,
                                      'gtk-edit')
            edit.set_tooltip_text(edit_msg)
            bbox.pack_start(edit, False, True, 0)
            if not self.dbstate.db.readonly:
                delete = widgets.IconButton(del_fcn, family.handle,
                                            'list-remove')
                delete.set_tooltip_text(del_msg)
                bbox.pack_start(delete, False, True, 0)

        hbox.pack_start(bbox, False, True, 6)

        if family:
            if self.show_tags:
                tag_list = TagList(self.get_tag_list(family))
                hbox.pack_start(tag_list, False, False, 3)
            eventbox = self.make_dragbox(hbox, 'Family', family.handle)
            return eventbox
        else:
            return hbox

    def get_tag_list(self, obj):
        tags_list = []
        for handle in obj.get_tag_list():
            tag = self.dbstate.db.get_tag_from_handle(handle)
            tags_list.append((tag.priority, tag.name, tag.color))
        tags_list.sort()
        return [(item[1], item[2]) for item in tags_list]

    def write_person(self, title, handle):
        """
        Create and show a person cell.
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        if handle:
            name = self.get_name(handle, True)
            person = self.dbstate.db.get_person_from_handle(handle)
            parent = len(person.get_parent_family_handle_list()) > 0
            if parent:
                emph = True
            else:
                emph = False
            link_label = widgets.LinkLabel(name, self._person_link,
                                           handle, emph, theme=self.theme)
            if self._config.get('preferences.releditbtn'):
                button = widgets.IconButton(self.edit_button_press, handle)
                button.set_tooltip_text(_('Edit %s') % name[0])
            else:
                button = None
            hbox = Gtk.Box()
            hbox.set_spacing(6)
            hbox.pack_start(link_label, False, False, 0)
            if self.show_details:
                box = self.info_box(handle)
                if box:
                    hbox.pack_start(box, False, False, 0)
            if button is not None:
                hbox.pack_start(button, False, False, 0)
            if self.show_tags:
                tag_list = TagList(self.get_tag_list(person))
                hbox.pack_start(tag_list, False, False, 0)
            vbox.pack_start(hbox, True, True, 0)
        else:
            link_label = Gtk.Label(label=_('Unknown'))
            link_label.set_halign(Gtk.Align.START)
            link_label.show()
            vbox.pack_start(link_label, True, True, 0)

        return vbox

    def write_child(self, handle, index, child_should_be_linked):
        """
        Write a child cell (used for children and siblings of active person)
        """
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        parent = has_children(self.dbstate.db,
                              self.dbstate.db.get_person_from_handle(handle))
        emph = False
        if child_should_be_linked and parent:
            emph = True
        elif child_should_be_linked and not parent:
            emph = False
        elif parent and not child_should_be_linked:
            emph = None

        if child_should_be_linked:
            link_func = self._person_link
        else:
            link_func = None

        name = self.get_name(handle, True)
        link_label = widgets.LinkLabel(name, link_func, handle, emph,
                                       theme=self.theme)
        link_label.set_padding(3, 0)
        if self._config.get('preferences.releditbtn'):
            button = widgets.IconButton(self.edit_button_press, handle)
            button.set_tooltip_text(_('Edit %s') % name[0])
        else:
            button = None

        hbox = Gtk.Box()
        hbox.set_spacing(6)
        l = widgets.BasicLabel("%d." % index)
        l.set_width_chars(3)
        l.set_halign(Gtk.Align.END)
        hbox.pack_start(l, False, False, 0)
        person = self.dbstate.db.get_person_from_handle(handle)
        hbox.pack_start(link_label, False, False, 0)
        if self.show_details:
            box = self.info_box(handle)
            if box:
                hbox.pack_start(box, False, False, 0)
        if button is not None:
            hbox.pack_start(button, False, False, 0)
        if self.show_tags:
            tag_list = TagList(self.get_tag_list(person))
            hbox.pack_start(tag_list, False, False, 0)
        hbox.show()
        vbox.pack_start(hbox, True, True, 0)

        ev = self.make_dragbox(vbox, 'Person', handle)

        if not child_should_be_linked:
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            frame.add(ev)
            return frame
        else:
            return ev


##############################################################################

    def get_handle(self):
        return self.get_active()[1]

    def edit_active(self, *obj):
        phandle = self.get_handle()
        self.edit_person(obj, phandle)

    def edit_button_press(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.edit_person(obj, handle)

    def edit_person(self, obj, handle):
        person = self.dbstate.db.get_person_from_handle(handle)
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def edit_event(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            event = self.dbstate.db.get_event_from_handle(handle)
            try:
                EditEvent(self.dbstate, self.uistate, [], event)
            except WindowActiveError:
                pass

    def edit_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            family = self.dbstate.db.get_family_from_handle(handle)
            try:
                EditFamily(self.dbstate, self.uistate, [], family)
            except WindowActiveError:
                pass

    def add_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            family = Family()
            person = self.dbstate.db.get_person_from_handle(self.get_handle())
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

    def add_spouse(self, *obj):
        family = Family()
        person = self.dbstate.db.get_person_from_handle(self.get_handle())

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

    def add_child_to_fam(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            callback = lambda x: self.callback_add_child(x, handle)
            person = Person()
            name = Name()
            #the editor requires a surname
            name.add_surname(Surname())
            name.set_primary_surname(0)
            family = self.dbstate.db.get_family_from_handle(handle)
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
        ref = ChildRef()
        ref.ref = person.get_handle()
        family = self.dbstate.db.get_family_from_handle(family_handle)
        family.add_child_ref(ref)

        with DbTxn(_("Add Child to Family"), self.dbstate.db) as trans:
            #add parentref to child
            person.add_parent_family_handle(family_handle)
            #default relationship is used
            self.dbstate.db.commit_person(person, trans)
            #add child to family
            self.dbstate.db.commit_family(family, trans)

    def sel_child_to_fam(self, obj, event, handle, surname=None):
        if button_activated(event, _LEFT_BUTTON):
            SelectPerson = SelectorFactory('Person')
            family = self.dbstate.db.get_family_from_handle(handle)
            # it only makes sense to skip those who are already in the family
            skip_list = [family.get_father_handle(),
                         family.get_mother_handle()]
            skip_list.extend(x.ref for x in family.get_child_ref_list())

            sel = SelectPerson(self.dbstate, self.uistate, [],
                               _("Select Child"), skip=skip_list)
            person = sel.run()

            if person:
                self.callback_add_child(person, handle)

    def select_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            SelectFamily = SelectorFactory('Family')

            phandle = self.get_handle()
            person = self.dbstate.db.get_person_from_handle(phandle)
            skip = set(person.get_family_handle_list())

            dialog = SelectFamily(self.dbstate, self.uistate, skip=skip)
            family = dialog.run()

            if family:
                child = self.dbstate.db.get_person_from_handle(self.get_handle())

                self.dbstate.db.add_child_to_family(family, child)

    def select_parents(self, *obj):
        SelectFamily = SelectorFactory('Family')

        phandle = self.get_handle()
        person = self.dbstate.db.get_person_from_handle(phandle)
        skip = set(person.get_family_handle_list()+
                   person.get_parent_family_handle_list())

        dialog = SelectFamily(self.dbstate, self.uistate, skip=skip)
        family = dialog.run()

        if family:
            child = self.dbstate.db.get_person_from_handle(self.get_handle())

            self.dbstate.db.add_child_to_family(family, child)

    def add_parents(self, *obj):
        family = Family()
        person = self.dbstate.db.get_person_from_handle(self.get_handle())

        if not person:
            return

        ref = ChildRef()
        ref.ref = person.handle
        family.add_child_ref(ref)

        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def add_parent_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            family = Family()
            person = self.dbstate.db.get_person_from_handle(self.get_handle())

            ref = ChildRef()
            ref.ref = person.handle
            family.add_child_ref(ref)

            try:
                EditFamily(self.dbstate, self.uistate, [], family)
            except WindowActiveError:
                pass

    def delete_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.dbstate.db.remove_parent_from_family(self.get_handle(), handle)

    def delete_parent_family(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.dbstate.db.remove_child_from_family(self.get_handle(), handle)

    def reorder_button_press(self, obj, event, handle):
        if button_activated(event, _LEFT_BUTTON):
            self.reorder(obj)

    def reorder(self, *obj):
        if self.get_handle():
            try:
                Reorder(self.dbstate, self.uistate, [], self.get_handle())
            except WindowActiveError:
                pass

    def config_connect(self):
        """
        Overwriten from  :class:`~gui.views.pageview.PageView method
        This method will be called after the ini file is initialized,
        use it to monitor changes in the ini file
        """
        self._config.connect("preferences.relation-shade",
                          self.shade_update)
        self._config.connect("preferences.releditbtn",
                          self.config_update)
        self._config.connect("preferences.relation-display-theme",
                          self.config_update)
        self._config.connect("preferences.family-siblings",
                          self.config_update)
        self._config.connect("preferences.family-details",
                          self.config_update)
        self._config.connect("preferences.show-tags",
                          self.config_update)
        self._config.connect("preferences.vertical-details",
                          self.config_update)
        config.connect("interface.toolbar-on",
                          self.shade_update)

    def config_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        configdialog.add_checkbox(grid,
                _('Use shading'),
                0, 'preferences.relation-shade')
        configdialog.add_checkbox(grid,
                _('Display edit buttons'),
                1, 'preferences.releditbtn')
        checkbox = Gtk.CheckButton(label=_('View links as website links'))
        theme = self._config.get('preferences.relation-display-theme')
        checkbox.set_active(theme == 'WEBPAGE')
        checkbox.connect('toggled', self._config_update_theme)
        grid.attach(checkbox, 1, 2, 8, 1)

        return _('Layout'), grid

    def content_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        configdialog.add_checkbox(grid,
                _('Show Details'),
                0, 'preferences.family-details')
        configdialog.add_checkbox(grid,
                _('Vertical Details'),
                1, 'preferences.vertical-details')
        configdialog.add_checkbox(grid,
                _('Show Siblings'),
                2, 'preferences.family-siblings')
        configdialog.add_checkbox(grid,
                _('Show Tags'),
                3, 'preferences.show-tags')

        return _('Content'), grid

    def _config_update_theme(self, obj):
        """
        callback from the theme checkbox
        """
        if obj.get_active():
            self.theme = 'WEBPAGE'
            self._config.set('preferences.relation-display-theme',
                              'WEBPAGE')
        else:
            self.theme = 'CLASSIC'
            self._config.set('preferences.relation-display-theme',
                              'CLASSIC')

    def _get_configure_page_funcs(self):
        """
        Return a list of functions that create gtk elements to use in the
        notebook pages of the Configure dialog

        :return: list of functions
        """
        return [self.content_panel, self.config_panel]

#-------------------------------------------------------------------------
#
# Function to return if person has children
#
#-------------------------------------------------------------------------
def has_children(db,p):
    """
    Return if a person has children.
    """
    for family_handle in p.get_family_handle_list():
        family = db.get_family_from_handle(family_handle)
        childlist = family.get_child_ref_list()
        if childlist and len(childlist) > 0:
            return True
    return False

def button_activated(event, mouse_button):
    if (event.type == Gdk.EventType.BUTTON_PRESS and
        event.button == mouse_button) or \
       (event.type == Gdk.EventType.KEY_PRESS and
        event.keyval in (_RETURN, _KP_ENTER, _SPACE)):
        return True
    else:
        return False
