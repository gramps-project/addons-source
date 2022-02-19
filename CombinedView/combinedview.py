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
from navigationview import NavigationView
from personpage import PersonPage
from eventpage import EventPage
from gramps.gen.config import config
from gramps.gen.lib import Family, ChildRef, Person
from gramps.gui.uimanager import ActionGroup
from gramps.gui.selectors import SelectorFactory
from gramps.gen.errors import WindowActiveError
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gui.editors import FilterEditor
from gramps.gen.const import CUSTOM_FILTERS
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext

_LOG = logging.getLogger("plugin.relview")

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

        self.pages = {}
        self._add_page(PersonPage(self.dbstate, self.uistate, self._config))
        self._add_page(EventPage(self.dbstate, self.uistate, self._config))
        self.active_page = None

        self.additional_uis.append(self.additional_ui)

    def _add_page(self, page):
        page.connect('object-changed', self.object_changed)
        self.pages[page.obj_type()] = page

    def _connect_db_signals(self):
        """
        implement from base class DbGUIElement
        Register the callbacks we need.
        """
        # Add a signal to pick up event changes, bug #1416
        self.callman.add_db_signal('event-update', self.family_update)

        self.callman.add_db_signal('person-add', self.person_update)
        self.callman.add_db_signal('person-update', self.person_update)
        self.callman.add_db_signal('person-rebuild', self.person_rebuild)
        self.callman.add_db_signal('family-update', self.family_update)
        self.callman.add_db_signal('family-add',    self.family_add)
        self.callman.add_db_signal('family-delete', self.family_delete)
        self.callman.add_db_signal('family-rebuild', self.family_rebuild)

        self.callman.add_db_signal('person-delete', self.redraw)

    def navigation_type(self):
        return 'Person'

    def can_configure(self):
        """
        See :class:`~gui.views.pageview.PageView
        :return: bool
        """
        return True

    def goto_handle(self, handle):
        self.change_object(handle)

    def config_update(self, client, cnxn_id, entry, data):
        for page in self.pages.values():
            page.config_update()
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
          <attribute name="action">win.AddParticipant</attribute>
          <attribute name="label" translatable="yes">Add Participant...</attribute>
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
    <child groups='RO'>
      <object class="GtkToolButton" id="EditButton">
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
    <child groups='Family'>
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
    <child groups='Family'>
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
    <child groups='Family'>
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
    <child groups='ChangeOrder'>
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
    <child groups='Event'>
      <object class="GtkToolButton">
        <property name="icon-name">gramps-parents-add</property>
        <property name="action-name">win.AddParticipant</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Add a new participant to the event</property>
        <property name="label" translatable="yes">_Reorder</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='Event'>
      <object class="GtkToolButton">
        <property name="icon-name">gramps-parents-open</property>
        <property name="action-name">win.ShareParticipant</property>
        <property name="tooltip_text" translatable="yes">'''
        '''Add an existing participant to the event</property>
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
        for page in self.pages.values():
            page.define_actions(self)

        self._add_action('Edit', self.edit_active, '<PRIMARY>Return')
        self._add_action('FilterEdit', callback=self.filter_editor)
        self._add_action('PRIMARY-J', self.jump, '<PRIMARY>J')

    def filter_editor(self, *obj):
        try:
            FilterEditor('Person', CUSTOM_FILTERS,
                         self.dbstate, self.uistate)
        except WindowActiveError:
            return

    def edit_active(self, *obj):
        self.active_page.edit_active()

    def change_db(self, db):
        #reset the connects
        self._change_db(db)
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

    def object_changed(self, obj_type, handle):
        self.change_active((obj_type, handle))
        self.change_object((obj_type, handle))

    def change_object(self, obj_tuple):

        if obj_tuple is None:
            return


        if self.redrawing:
            return False
        self.redrawing = True

        obj_type, handle, = obj_tuple
        if obj_type == 'Person':
            obj = self.dbstate.db.get_person_from_handle(handle)
        elif obj_type == 'Event':
            obj = self.dbstate.db.get_event_from_handle(handle)

        for page in self.pages.values():
            page.disable_actions(self.uimanager)

        page = self.pages[obj_type]

        page.enable_actions(self.uimanager, obj)
        self.uimanager.update_menu()

        edit_button = self.uimanager.get_widget("EditButton")
        if edit_button:
            if obj_type == 'Person':
                tooltip = _('Edit the active person')
            elif obj_type == 'Event':
                tooltip = _('Edit the active event')
            edit_button.set_tooltip_text(tooltip)

        list(map(self.header.remove, self.header.get_children()))
        list(map(self.stack.remove, self.stack.get_children()))
        mbox = page.write_title(obj)
        self.header.pack_start(mbox, False, True, 0)

        page.write_stack(obj, self.stack)

        self.redrawing = False
        self.uistate.modify_statusbar(self.dbstate)

        self.dirty = False

        self.active_page = page

        return True

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

    def config_connect(self):
        """
        Overwriten from  :class:`~gui.views.pageview.PageView method
        This method will be called after the ini file is initialized,
        use it to monitor changes in the ini file
        """
        self._config.connect("preferences.relation-shade",
                          self.config_update)
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
                          self.config_update)

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
        configdialog.add_checkbox(grid,
                _('Show Tags'),
                2, 'preferences.show-tags')
        checkbox = Gtk.CheckButton(label=_('View links as website links'))
        theme = self._config.get('preferences.relation-display-theme')
        checkbox.set_active(theme == 'WEBPAGE')
        checkbox.connect('toggled', self._config_update_theme)
        grid.attach(checkbox, 1, 3, 8, 1)

        return _('Layout'), grid

    def person_panel(self, configdialog):
        """
        Function that builds the widget in the configuration dialog
        """
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        grid.set_column_homogeneous(False)
        configdialog.add_text(grid,
                _('Relationships'),
                0, bold=True)
        configdialog.add_checkbox(grid,
                _('Show Details'),
                1, 'preferences.family-details')
        configdialog.add_checkbox(grid,
                _('Vertical Details'),
                2, 'preferences.vertical-details')
        configdialog.add_checkbox(grid,
                _('Show Siblings'),
                3, 'preferences.family-siblings')

        return _('Person'), grid

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
        return [self.config_panel, self.person_panel]

    def set_active(self):
        """
        Called when the page is displayed.
        """
        NavigationView.set_active(self)
        self.uistate.viewmanager.tags.tag_enable(update_menu=False)

    def set_inactive(self):
        """
        Called when the page is no longer displayed.
        """
        NavigationView.set_inactive(self)
        self.uistate.viewmanager.tags.tag_disable()

    def selected_handles(self):
        return [self.get_active()[1]]

    def add_tag(self, trans, object_handle, tag_handle):
        """
        Add the given tag to the active object.
        """
        self.active_page.add_tag(trans, object_handle, tag_handle)
