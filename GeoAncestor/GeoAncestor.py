# -*- python -*-
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020-      Serge Noiraud
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
Geography for one person
"""
#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import operator

#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging

from gi.repository import Gdk
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import EventRoleType, EventType, Family
from gramps.gen.config import config
from gramps.gen.datehandler import displayer
from gramps.gen.display.name import displayer as _nd
from gramps.gen.display.place import displayer as _pd
from gramps.gen.utils.place import conv_lat_lon
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.plugins.lib.maps import constants
from gramps.plugins.lib.maps.geography import GeoGraphyView
from gramps.gui.utils import ProgressMeter

#-------------------------------------------------------------------------
#
# Constants
#
#-------------------------------------------------------------------------
_ = glocale.translation.gettext
_LOG = logging.getLogger("GeoGraphy.geoperson")
KEY_TAB = Gdk.KEY_Tab

_UI_DEF = [
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
          <attribute name="label" translatable="yes">Print...</attribute>
        </item>
      </section>
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
      <object class="GtkToolButton">
        <property name="icon-name">document-print</property>
        <property name="action-name">win.PrintView</property>
        <property name="tooltip_text" translatable="yes">'''
    '''Print or save the Map</property>
        <property name="label" translatable="yes">reference _Family</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
    ''']

#-------------------------------------------------------------------------
#
# GeoView
#
#-------------------------------------------------------------------------
class GeoAncestor(GeoGraphyView):
    """
    The view used to render person map.
    """
    CONFIGSETTINGS = (
        ('geography.path', constants.GEOGRAPHY_PATH),

        ('geography.zoom', 10),
        ('geography.zoom_when_center', 12),
        ('geography.show_cross', True),
        ('geography.lock', False),
        ('geography.center-lat', 0.0),
        ('geography.center-lon', 0.0),
        ('geography.use-keypad', True),
        ('geography.map_service', constants.OPENSTREETMAP),
        ('geography.max_places', 5000),
        ('geography.other_map', 0),
        ('geography.personal-map', ""),
        )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        GeoGraphyView.__init__(self, _("Ancestors places on the map"),
                               pdata, dbstate, uistate, PersonBookmarks,
                               nav_group)
        self.dbstate = dbstate
        self.uistate = uistate
        self.place_list = []
        self.place_without_coordinates = []
        self.minlat = self.maxlat = self.minlon = self.maxlon = 0.0
        self.minyear = 9999
        self.maxyear = 0
        self.nbplaces = 0
        self.nbmarkers = 0
        self.sort = []
        self.additional_uis.append(self.additional_ui())
        self.no_show_places_in_status_bar = False
        self.already_started = False
        self.large_move = False
        self.cal = None
        self.menu = None
        self.itemoption = None
        self.event_list = []
        self.already_done = []
        self.nb_evts = 0

    def get_title(self):
        """
        Used to set the titlebar in the configuration window.
        """
        return _('GeoAncestor')

    def get_stock(self):
        """
        Returns the name of the stock icon to use for the display.
        This assumes that this icon has already been registered
        as a stock icon.
        """
        return 'geo-ancestor'

    def get_viewtype_stock(self):
        """Type of view in category
        """
        return 'geo-ancestor'

    def additional_ui(self):
        """
        Specifies the UIManager XML code that defines the menus and buttons
        associated with the interface.
        """
        return _UI_DEF

    def navigation_type(self):
        """
        Indicates the navigation type. Navigation type can be the string
        name of any of the primary objects.
        """
        return 'Person'

    def goto_handle(self, handle=None):
        """
        Rebuild the tree with the given person handle as the root.
        """
        self._createmap()
        self.uistate.modify_statusbar(self.dbstate)

    def build_tree(self):
        """
        This is called by the parent class when the view becomes visible. Since
        all handling of visibility is now in rebuild_trees, see that for more
        information.
        """
        self.uistate.modify_statusbar(self.dbstate)

    def _createmap(self):
        """
        Create all markers for each people's event in the database which has
        a lat/lon.
        """
        dbstate = self.dbstate
        self.cal = config.get('preferences.calendar-format-report')
        self.place_list = []
        self.event_list = []
        self.place_without_coordinates = []
        self.places_found = []
        self.minlat = self.maxlat = self.minlon = self.maxlon = 0.0
        self.minyear = 9999
        self.maxyear = 0
        self.already_done = []
        self.nbplaces = 0
        self.nbmarkers = 0
        self.message_layer.clear_messages()
        self.kml_layer.clear()
        person_handle = self.uistate.get_active('Person')
        person = None
        if person_handle:
            person = dbstate.db.get_person_from_handle(person_handle)
        if person is not None:
            # For each event, if we have a place, set a marker.
            self.window_name = _("Ancestors places for %s" %
                                 _nd.display(person))
            self.message_layer.add_message(self.window_name)
            self.nb_evts = 0
            self.progress = ProgressMeter(self.window_name,
                                          can_cancel=False,
                                          parent=self.uistate.window)
            self.progress.set_pass(_('Counting all places'), self.nb_evts)
            self.person_count(person)
            self.event_list = []
            self.progress.set_pass(_('Showing all places'), self.nb_evts)
            self.show_one_person(person)
            self.progress.close()

            self.sort = sorted(self.place_list,
                               key=operator.itemgetter(3, 4, 6)
                              )
            self._create_markers()

    def person_count(self, person):
        """
        Count the number of events associated to a place with coordinates
        """
        dbstate = self.dbstate
        for event_ref in person.get_event_ref_list():
            if not event_ref:
                continue
            event = dbstate.db.get_event_from_handle(event_ref.ref)
            place_handle = event.get_place_handle()
            if place_handle and event_ref.ref not in self.event_list:
                self.event_list.append(event_ref.ref)
                place = dbstate.db.get_place_from_handle(place_handle)
                if place:
                    longitude = place.get_longitude()
                    latitude = place.get_latitude()
                    latitude, longitude = conv_lat_lon(latitude,
                                                       longitude, "D.D8")
                    if longitude and latitude:
                        self.nb_evts += 1
        family_list = person.get_family_handle_list()
        for family_hdl in family_list:
            family = self.dbstate.db.get_family_from_handle(family_hdl)
            if family is not None:
                fhandle = family_list[0] # first is primary
                fam = dbstate.db.get_family_from_handle(fhandle)
                father = mother = None
                handle = fam.get_father_handle()
                if handle:
                    father = dbstate.db.get_person_from_handle(handle)
                if father:
                    self.already_done.append(handle)
                handle = fam.get_mother_handle()
                if handle:
                    self.already_done.append(handle)
                    mother = dbstate.db.get_person_from_handle(handle)
                for event_ref in family.get_event_ref_list():
                    if event_ref:
                        event = dbstate.db.get_event_from_handle(event_ref.ref)
                        if event.get_place_handle():
                            place_handle = event.get_place_handle()
                            if (place_handle and
                                    event_ref.ref not in self.event_list):
                                self.event_list.append(event_ref.ref)
                                place = dbstate.db.get_place_from_handle(
                                    place_handle)
                                if place:
                                    longitude = place.get_longitude()
                                    latitude = place.get_latitude()
                                    (latitude,
                                     longitude) = conv_lat_lon(latitude,
                                                               longitude,
                                                               "D.D8")
                                    if longitude and latitude:
                                        self.nb_evts += 1
        for pers in [self._get_parent(person, True),
                     self._get_parent(person, False)]:
            if pers:
                self.person_count(pers)

    def show_one_person(self, person):
        """
        Create all markers for each people's event in the database which has
        a lat/lon.
        """
        dbstate = self.dbstate
        self.load_kml_files(person)
        for event_ref in person.get_event_ref_list():
            if not event_ref:
                continue
            event = dbstate.db.get_event_from_handle(event_ref.ref)
            self.load_kml_files(event)
            role = event_ref.get_role()
            edate = event.get_date_object().to_calendar(self.cal)
            eyear = str("%04d" % edate.get_year()) + \
                        str("%02d" % edate.get_month()) + \
                        str("%02d" % edate.get_day())
            place_handle = event.get_place_handle()
            if place_handle and event_ref.ref not in self.event_list:
                self.event_list.append(event_ref.ref)
                place = dbstate.db.get_place_from_handle(place_handle)
                if place:
                    longitude = place.get_longitude()
                    latitude = place.get_latitude()
                    latitude, longitude = conv_lat_lon(latitude,
                                                       longitude, "D.D8")
                    descr = _pd.display(dbstate.db, place)
                    evt = EventType(event.get_type())
                    descr1 = _("%(eventtype)s : %(name)s") % {
                        'eventtype': evt,
                        'name': _nd.display(person)}
                    self.load_kml_files(place)
                    # place.get_longitude and place.get_latitude return
                    # one string. We have coordinates when the two values
                    # contains non null string.
                    if longitude and latitude:
                        self.progress.step()
                        self._append_to_places_list(descr, evt,
                                                    _nd.display(person),
                                                    latitude, longitude,
                                                    descr1, eyear,
                                                    event.get_type(),
                                                    person.gramps_id,
                                                    place.gramps_id,
                                                    event.gramps_id,
                                                    role
                                                   )
                    else:
                        self._append_to_places_without_coord(place.gramps_id,
                                                             descr)
        family_list = person.get_family_handle_list()
        for family_hdl in family_list:
            family = self.dbstate.db.get_family_from_handle(family_hdl)
            if family is not None:
                fhandle = family_list[0] # first is primary
                fam = dbstate.db.get_family_from_handle(fhandle)
                father = mother = None
                handle = fam.get_father_handle()
                if handle:
                    father = dbstate.db.get_person_from_handle(handle)
                descr1 = " - "
                if father:
                    self.already_done.append(handle)
                    descr1 = "%s - " % _nd.display(father)
                handle = fam.get_mother_handle()
                if handle:
                    self.already_done.append(handle)
                    mother = dbstate.db.get_person_from_handle(handle)
                if mother:
                    descr1 = "%s%s" % (descr1, _nd.display(mother))
                for event_ref in family.get_event_ref_list():
                    if event_ref:
                        event = dbstate.db.get_event_from_handle(event_ref.ref)
                        self.load_kml_files(event)
                        role = event_ref.get_role()
                        if event.get_place_handle():
                            place_handle = event.get_place_handle()
                            if (place_handle and
                                    event_ref.ref not in self.event_list):
                                self.event_list.append(event_ref.ref)
                                place = dbstate.db.get_place_from_handle(
                                    place_handle)
                                if place:
                                    longitude = place.get_longitude()
                                    latitude = place.get_latitude()
                                    (latitude,
                                     longitude) = conv_lat_lon(latitude,
                                                               longitude,
                                                               "D.D8")
                                    descr = _pd.display(dbstate.db, place)
                                    evt = EventType(event.get_type())
                                    edate = event.get_date_object()
                                    edate = edate.to_calendar(self.cal)
                                    eyear = str("%04d" % edate.get_year()) + \
                                                str("%02d" % edate.get_month())\
                                                + str("%02d" % edate.get_day())
                                    self.load_kml_files(place)
                                    if longitude and latitude:
                                        self.progress.step()
                                        self._append_to_places_list(descr, evt,
                                                                    _nd.display(person),
                                                                    latitude,
                                                                    longitude,
                                                                    descr1,
                                                                    eyear,
                                                                    event.get_type(),
                                                                    person.gramps_id,
                                                                    place.gramps_id,
                                                                    event.gramps_id,
                                                                    role
                                                                   )
                                    else:
                                        self._append_to_places_without_coord(place.gramps_id, descr)
        for pers in [self._get_parent(person, True),
                     self._get_parent(person, False)]:
            if pers:
                self.show_one_person(pers)

    def _get_parent(self, person, father):
        """
        Get the father of the family if father == True, otherwise mother
        """
        if person:
            parent_handle_list = person.get_parent_family_handle_list()
            if parent_handle_list:
                family_id = parent_handle_list[0]
                family = self.dbstate.db.get_family_from_handle(family_id)
                if family:
                    if father:
                        person_handle = Family.get_father_handle(family)
                    else:
                        person_handle = Family.get_mother_handle(family)
                    if person_handle:
                        fct = self.dbstate.db.get_person_from_handle
                        return fct(person_handle)
        return None

    def bubble_message(self, event, lat, lon, marks):
        self.menu = Gtk.Menu()
        menu = self.menu
        menu.set_title("person")
        message = ""
        oldplace = ""
        prevmark = None
        for mark in marks:
            if oldplace != "":
                add_item = Gtk.MenuItem(label=message)
                add_item.show()
                menu.append(add_item)
                self.itemoption = Gtk.Menu()
                itemoption = self.itemoption
                itemoption.set_title(message)
                itemoption.show()
                message = ""
                add_item.set_submenu(itemoption)
                modify = Gtk.MenuItem(label=_("Edit Event"))
                modify.show()
                modify.connect("activate", self.edit_event,
                               event, lat, lon, prevmark)
                itemoption.append(modify)
                center = Gtk.MenuItem(label=_("Center on this place"))
                center.show()
                center.connect("activate", self.center_here,
                               event, lat, lon, prevmark)
                itemoption.append(center)
            if mark[0] != oldplace:
                if message != "":
                    add_item = Gtk.MenuItem()
                    add_item.show()
                    menu.append(add_item)
                    self.itemoption = Gtk.Menu()
                    itemoption = self.itemoption
                    itemoption.set_title(message)
                    itemoption.show()
                    message = ""
                    add_item.set_submenu(itemoption)
                    modify = Gtk.MenuItem(label=_("Edit Event"))
                    modify.show()
                    modify.connect("activate", self.edit_event,
                                   event, lat, lon, mark)
                    itemoption.append(modify)
                    center = Gtk.MenuItem(label=_("Center on this place"))
                    center.show()
                    center.connect("activate", self.center_here,
                                   event, lat, lon, mark)
                    itemoption.append(center)
                message = "%s :" % mark[0]
                self.add_place_bubble_message(event, lat, lon,
                                              marks, menu, message, mark)
                oldplace = mark[0]
                message = ""
            evt = self.dbstate.db.get_event_from_gramps_id(mark[10])
            # format the date as described in preferences.
            date = displayer.display(evt.get_date_object())
            if date == "":
                date = _("Unknown")
            if mark[11] == EventRoleType.PRIMARY:
                message = "(%s) %s : %s" % (date, mark[2], mark[1])
            elif mark[11] == EventRoleType.FAMILY:
                (father_name,
                 mother_name) = self._get_father_and_mother_name(evt)
                message = "(%s) %s : %s - %s" % (date, mark[7],
                                                 father_name, mother_name)
            else:
                descr = evt.get_description()
                if descr == "":
                    descr = _('No description')
                message = "(%s) %s => %s" % (date, mark[11], descr)
            prevmark = mark
        add_item = Gtk.MenuItem(label=message)
        add_item.show()
        menu.append(add_item)
        self.itemoption = Gtk.Menu()
        itemoption = self.itemoption
        itemoption.set_title(message)
        itemoption.show()
        add_item.set_submenu(itemoption)
        modify = Gtk.MenuItem(label=_("Edit Event"))
        modify.show()
        modify.connect("activate", self.edit_event, event, lat, lon, prevmark)
        itemoption.append(modify)
        center = Gtk.MenuItem(label=_("Center on this place"))
        center.show()
        center.connect("activate", self.center_here, event, lat, lon, prevmark)
        itemoption.append(center)
        menu.show()
        menu.popup(None, None, None,
                   None, event.button, event.time)
        return 1

    def add_specific_menu(self, menu, event, lat, lon):
        """
        Add specific entry to the navigation menu.
        """
        add_item = Gtk.MenuItem()
        add_item.show()
        menu.append(add_item)
        add_item = Gtk.MenuItem(label=_("Show all places"))
        #add_item.connect("activate", self.show_all_places, event, lat, lon)
        add_item.show()
        menu.append(add_item)
        add_item = Gtk.MenuItem(label=_("Centering on Place"))
        add_item.show()
        menu.append(add_item)
        self.itemoption = Gtk.Menu()
        itemoption = self.itemoption
        itemoption.set_title(_("Centering on Place"))
        itemoption.show()
        add_item.set_submenu(itemoption)
        oldplace = ""
        for mark in self.sort:
            if mark[0] != oldplace:
                oldplace = mark[0]
                modify = Gtk.MenuItem(label=mark[0])
                modify.show()
                #modify.connect("activate", self.goto_place,
                #               float(mark[3]), float(mark[4]))
                itemoption.append(modify)

    def get_default_gramplets(self):
        """
        Define the default gramplets for the sidebar and bottombar.
        """
        return (("Person Filter",),
                ())
