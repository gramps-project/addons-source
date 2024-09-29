# -*- python -*-
# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011-2016  Serge Noiraud
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


#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import os
import operator
import time
import bisect
import random
from datetime import date as dt
from datetime import timedelta as td
import calendar
import math
# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import OsmGpsMap as osmgpsmap
from gi.repository import Gdk
from gi.repository import GLib

from gi.repository import GdkPixbuf
import cairo
#-------------------------------------------------------------------------
#
# set up logging
#
#-------------------------------------------------------------------------
import logging
_LOG = logging.getLogger("geotimelines")


#-------------------------------------------------------------------------
#
# Gramps Modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.lib import Date, EventRoleType, EventType#, PlaceType
from gramps.gen.config import config
from gramps.gen.datehandler import get_date_formats
from gramps.gen.datehandler import displayer
from gramps.gen.display.name import displayer as _nd
from gramps.gen.display.place import displayer as _pd
from gramps.gen.utils.place import conv_lat_lon
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gui.utils import ProgressMeter, Popup
from gramps.plugins.lib.maps import constants
from gramps.plugins.lib.maps.geography import GeoGraphyView

###todo
'''
don't use datetime—caps out at y=9999. Error if going above
'''

_UI_DEF = [
    """
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
""",
    """
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
"""
    % _("Organize Bookmarks"),  # Following are the Toolbar items
    """
    <placeholder id='CommonNavigation'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-previous</property>
        <property name="action-name">win.Back</property>
        <property name="tooltip_text" translatable="yes">"""
    """Go to the previous object in the history</property>
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
        <property name="tooltip_text" translatable="yes">"""
    """Go to the next object in the history</property>
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
        <property name="tooltip_text" translatable="yes">"""
    """Go to the home person</property>
        <property name="label" translatable="yes">_Home</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
""",
    """
    <placeholder id='BarCommonEdit'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">document-print</property>
        <property name="action-name">win.PrintView</property>
        <property name="tooltip_text" translatable="yes">"""
    """Print or save the Map</property>
        <property name="label" translatable="yes">Print...</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
    """,
]

class GeoTimeLines(GeoGraphyView):
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

        ('geotimelines.separate_markers', True),
        ('geotimelines.default_show_lines', True),
        ('geotimelines.default_show_ticks', True),
        ('geotimelines.persist_drawn_lines_days', 730),
        #('geotimelines.date-format', config.get("preferences.date-format")),
        
        ('geotimelines.animation_step_interval', 4),
        ('geotimelines.animation_step_type', 1),
        ('geotimelines.animation_step_time', 200),
        
        ('geotimelines.use_custom_icons', True),
        ('geotimelines.initial_view_type', 1),
        ('geotimelines.active_view_type', 1),
        ('geotimelines.default_icon', 'geo-timelines-dot'),
        ('geotimelines.generalplace', [
                "Country",
                "State",
                "County",
                "Province",
                "Region",
                "Department",
            ]
        ),
        ('geotimelines.assumeage', 30),
        ('geotimelines.assumedeath', 100),
        ('geotimelines.show_missing_gen', 0),
        ('geotimelines.show_missing_gen_radius', 10),
    )
    #probably better to use the following, but trouble converting
    #the int into a str
    '''
            PlaceType.COUNTRY,
            PlaceType.STATE,
            PlaceType.COUNTY,
            PlaceType.PROVINCE,
            PlaceType.REGION,
            PlaceType.DEPARTMENT,
    '''
    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        self.window_name = _("TimeLines Map")
        GeoGraphyView.__init__(
            self, self.window_name, pdata, dbstate, uistate, PersonBookmarks, nav_group
        )
        self.initial_view = True
        self.dialog = False
        self.dbstate = dbstate
        self.uistate = uistate
        self.active_db_phandle = (None, None)
        self.place_list = []
        self.place_list_lines = []
        self.place_without_coordinates = []
        self.minlat = self.maxlat = self.minlon = self.maxlon = 0.0
        self.minyear = 9999
        self.maxyear = 0
        self.nbplaces = 0
        self.nbmarkers = 0
        self.sort = []
        self.generic_filter = None
        self.additional_uis.append(self.additional_ui())
        self.no_show_places_in_status_bar = False
        self.already_started = False
        self.large_move = False
        self.cal = None
        self.didtree = False
        
        #from geography
        self.mapservice = config.get('geography.map_service')
        self.default_marker = None
        self._set_default_marker()
        
        theme = Gtk.IconTheme.get_default()

        self.geo_othermap = {}
        self.geo_person = theme.load_surface("gramps-person", 48, 1, None, 0)
        
        
        self.DB_CHOICE_POPUP = 0
        self.DB_CHOICE_ACTIVE = 1
        self.DB_CHOICE_ANC = 2
        self.DB_CHOICE_DESC = 3
        self.DB_CHOICE_ANCDES = 4
        self.DB_CHOICE_REL = 5
        self.DB_CHOICE_DB = 6
        self.DB_CHOICE_FILTER = 7
        self.DB_CHOICES_INITIAL = {
            self.DB_CHOICE_POPUP : 'Ask in Popup',
            self.DB_CHOICE_ACTIVE : 'Active Person',
            self.DB_CHOICE_ANC : 'Ancestors',
            self.DB_CHOICE_DESC : 'Descendants',
            self.DB_CHOICE_ANCDES : 'Ancestors and Descendants',
            self.DB_CHOICE_REL : 'All Relatives',
            self.DB_CHOICE_DB : 'Entire Database',
            self.DB_CHOICE_FILTER : 'From Filter'
        }
        
        self.DB_CHOICE_SAME = 2
        self.DB_CHOICES_SWITCH = {
            self.DB_CHOICE_POPUP : 'Ask in Popup',
            self.DB_CHOICE_ACTIVE : 'Active Person',
            self.DB_CHOICE_SAME : 'Same as Initial Map View'
        }
        self.show_startup_dialog = False
        self.database_choice = self._config.get('geotimelines.initial_view_type')
        self.all_sort = []
        self.all_sort_lines_dict = {}
        self.all_person_duration = {} # gramps_id : [[firstdate,birth?],[deaddate,dead?]]
        self.all_person_icons = {}    # draw and store all possible custom icons for each person
        self.all_selected_persons = []
        
        self.missingparents = {} #[[place,year,gen,numbermissing]]
        self.missingparent_icon = None
        #bottom gui
        self.hbox_control = None
        self.show_all = True
        self.show_lines = self._config.get('geotimelines.default_show_lines')
        self.btn_showall = None
        
        #slider values
        self.slider = None   
        self.minslider = None
        self.maxslider = None
        self.slider_marks = []
        self.mindt = None
        self.maxdt = None
        
        self.ymdindex = [(0,"Years"), (1,"Months"), (2,"Days")]
        
        #animation
        self.play = False
        self.animation_step_interval = self._config.get("geotimelines.animation_step_interval")
        self.animation_step_type = self._config.get("geotimelines.animation_step_type")
        self.animation_step_time = self._config.get("geotimelines.animation_step_time")
        self.animate_calc_time_list = [0]
        #for lines
        self.person_colour_dict = {}
        self.separate_event_locations_offset = {}
        self.lines_marks_dict = {} # gramps_id : marks

    def build_tree(self):
        self.didtree = False

    def get_title(self):
        """
        Used to set the titlebar in the configuration window.
        """
        return _('TimeLines Map')

    def get_stock(self):
        """
        Returns the name of the stock icon to use for the display.
        This assumes that this icon has already been registered
        as a stock icon.
        """
        return 'geo-show-ancestors'

    def get_viewtype_stock(self):
        """
        Type of view in category
        """
        return 'geo-show-ancestors'

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

    def get_default_gramplets(self):
        """
        Define the default gramplets for the sidebar and bottombar.
        """
        return (("Person Filter",), ())

    def goto_handle(self, handle=None):
        """
        Rebuild the tree with the given person handle as the root.
        """
        active = self.get_active()
        if self.active_db_phandle != (self.dbstate.db.get_dbid, handle):
            #behaviour if you switched persons
            if(not self.initial_view and not self.dialog):
                if self._config.get('geotimelines.active_view_type') == self.DB_CHOICE_SAME:
                    self.database_choice = self._config.get('geotimelines.initial_view_type')
                else:
                    self.database_choice = self._config.get('geotimelines.active_view_type')
            #### these need to be cleared on switching active person
            self._cleardata()
            self._createmap(None)
            if self.slider:
                self._buildsliderrange()

        #else:
        #    self._createmap(None)
        self.uistate.modify_statusbar(self.dbstate)

    def _cleardata(self):
        self.place_list = []
        self.place_list_lines = []
        self.place_without_coordinates = []
        self.sort = []
        self.all_sort = []
        self.all_sort_lines_dict = {}
        self.all_person_duration = {}
        self.all_person_icons = {}
        self.all_selected_persons = []
        self.missingparents = {}
        self.person_colour_dict = {}
        self.separate_event_locations_offset = {}
        self.lines_marks_dict = {}
        self.active_db_phandle = (None,None)
        if self.slider:
            self.slider.set_value(0)
            self.slider.set_range(0,0)

    def build_tree(self):
        """
        This is called by the parent class when the view becomes visible. Since
        all handling of visibility is now in rebuild_trees, see that for more
        information.
        """
        pass

    def _set_default_marker(self):
        theme = Gtk.IconTheme.get_default()
        if self._config.get("geotimelines.use_custom_icons"): #setting to use what markers
            self.default_marker = theme.load_surface(self._config.get("geotimelines.default_icon"), 48, 1, None, 0)
        else:
            if (config.get('geography.map_service') in
                (constants.OPENSTREETMAP,
                 constants.OPENSTREETMAP_RENDERER,
                 )):
                self.default_marker = theme.load_surface('gramps-geo-mainmap', 48, 1, None, 0)
            else:
                self.default_marker = theme.load_surface('gramps-geo-altmap', 48, 1, None, 0)

    def add_marker(
        self, menu, event, lat, lon, event_type, differtype, count, gramps_id=None, placeid=None
    ):
        """
        Add a new marker
        the "color" argument orginally passed to marker_layer, and was
        a string object being a hexcode starting with # and having an
        equal amount of r g b values.
        markerlayer handles having a colour poorly. If it is not None,
        then it will draw a large, ugly, marker. 
        See markerlayer.py lines 161, 191-238
        
        I've forced markerlayer to have color=None, and instead use it for
        my own purposes now.
        """
        dummy_menu = menu
        dummy_event = event
        
        if gramps_id and self._config.get("geotimelines.use_custom_icons"):
            default = self._draw_cairo_surface(gramps_id, placeid=placeid, event_type=event_type)
        else:
            default = self.default_marker
        value = default
        
        if differtype:  # in case multiple evts
            value = default  # we use default icon.

        self.marker_layer.add_marker(
            (float(lat), float(lon)), value, count, color=None
        )
    def _append_to_places_list(
        self,
        place_list,
        place,
        evttype,
        name,
        lat,
        longit,
        descr,
        year,
        icontype,
        gramps_id,
        place_id,
        event_id,
        family_id,
        color=None,
    ):
        """
        Create a list of places with coordinates.
        --added places_list to argument—
        """
        found = any(p[0] == place for p in self.places_found)
        if not found and (self.nbplaces < self._config.get("geography.max_places")):
            # We only show the first "geography.max_places".
            # over 3000 or 4000 places, the geography become unusable.
            # In this case, filter the places ...
            self.nbplaces += 1
            self.places_found.append([place, lat, longit])
        place_list.append(
            [
                place,
                name,
                evttype,
                lat,
                longit,
                descr,
                year,
                icontype,
                gramps_id,
                place_id,
                event_id,
                family_id,
                color,
            ]
        )
        self.nbmarkers += 1
        tfa = float(lat)
        tfb = float(longit)
        if year is not None:
            tfc = int(year)
            if tfc != 0:
                if tfc < self.minyear:
                    self.minyear = tfc
                if tfc > self.maxyear:
                    self.maxyear = tfc
        tfa += 0.00000001 if tfa >= 0 else -0.00000001
        tfb += 0.00000001 if tfb >= 0 else -0.00000001
        if self.minlat == 0.0 or tfa < self.minlat:
            self.minlat = tfa
        if self.maxlat == 0.0 or tfa > self.maxlat:
            self.maxlat = tfa
        if self.minlon == 0.0 or tfb < self.minlon:
            self.minlon = tfb
        if self.maxlon == 0.0 or tfb > self.maxlon:
            self.maxlon = tfb

    def _create_markers(self):
        """
        Create all markers for the specified person.
        —removed self._set_center_and_zoom() from this method
        -trimmed unneeded part??
        """
        if self.marker_layer is None:
            return
        self.remove_all_markers()
        self.remove_all_gps()
        self.remove_all_tracks()
        if self.current_map is not None and self.current_map != config.get(
            "geography.map_service"
        ):
            self.change_map(self.osm, config.get("geography.map_service"))
        last = ""
        current = ""
        differtype = False
        lat = 0.0
        lon = 0.0
        icon = None
        count = 0
        colour = None
        self.uistate.set_busy_cursor(True)
        _LOG.debug(
            "%s",
            time.strftime(
                "start create_marker : " "%a %d %b %Y %H:%M:%S", time.gmtime()
            ),
        )
        for mark in self.sort:
            if self._config.get("geotimelines.separate_markers"):
                lat_1 = float(mark[3])/180*math.pi
                r=self.separate_event_locations_offset[mark[10]][0]*self._config.get("geotimelines.show_missing_gen_radius")*math.pi/3189
                y=r*math.sin(self.separate_event_locations_offset[mark[10]][1])
                x=r*self.separate_event_locations_offset[mark[10]][0]*math.cos(self.separate_event_locations_offset[mark[10]][1])
                lat = str(float(mark[3]) + y/(1+math.log(math.tan(math.pi/4+abs(lat_1/2)))))
                lon = str(float(mark[4]) + x)
            else:
                lat = mark[3]
                lon = mark[4]
            icon = mark[7]
            gramps_id = mark[8]
            differtype = False
            count = 1
            self.add_marker(None, None, lat, lon, icon, differtype, count, gramps_id=gramps_id, placeid=mark[9])
            #self._set_center_and_zoom()
        _LOG.debug(
            "%s",
            time.strftime(
                " stop create_marker : " "%a %d %b %Y %H:%M:%S", time.gmtime()
            ),
        )
        self.uistate.set_busy_cursor(False)
        
    def bubble_message(self, event, lat, lon, marks):
        #from geoperson.py
        '''
        This is called when you click a location. This defines the popup menu
        #called by geography.py
            is_there_a_marker_here(self, event, lat, lon)
        #called by osmgps.py
            map_clicked(self, osm, event)
        #event  -   mouse click
        #marks  -   list of markers at lat, lon
        #           taken from self.sort    
        '''
        places = {}
        #from all selected marks, sort them first by place:
        for mark in marks:
            if mark[9] not in places:
                places[mark[9]] = []
            places[mark[9]].append(mark)
        #then sort places by person, then date
        for places_id in places:
            places[places_id] = sorted(places[places_id],
                   key=operator.itemgetter(8,6)
                  )
            
        self.menu = Gtk.Menu()
        menu = self.menu
        currentdt = self._discretedaytodatetime(self.slider.get_value())
        for places_id in places:
            marks = places[places_id]
            old_gramps_id = None
            
            '''
            add_item = Gtk.MenuItem()
            add_item.show()
            menu.append(add_item)
            self.itemoption = Gtk.Menu()
            itemoption = self.itemoption
            itemoption.show()
            add_item.set_submenu(itemoption)
            '''
            if self.show_all:
                place = marks[0][0]
            else:
                place = _pd.display(self.dbstate.db, self.dbstate.db.get_place_from_gramps_id(places_id), date=Date(currentdt.year,currentdt.month,currentdt.day))
            self.add_place_bubble_message(
                event, lat, lon, marks, menu, place, marks[0]
            )
            for mark in marks:
                place = mark[0]
                name = mark[1]
                event_type = mark[2]
                gramps_id = mark[8]
                event_id = mark[10]
                role = mark[11]
                if gramps_id != old_gramps_id:
                    old_gramps_id = gramps_id
                    self.add_person_bubble_message(event, lat, lon, menu, mark)
            
                #make bubble message
                evt = self.dbstate.db.get_event_from_gramps_id(event_id)
                #descr = evt.get_description().replace("&","\u0026")
                descr = evt.get_description()
                descr = f" : \"{descr}\""
                if descr == " : \"\"":
                    descr = ""
                date = displayer.display(evt.get_date_object())
                if date == "":
                    date = _("Unknown")
                message = ""
                if role == EventRoleType.PRIMARY:
                    message += "(%s) %s %s" % (date, event_type, descr)
                elif role == "Parent":
                    message += "(%s) Child's Birth : %s" % (date, name)
                elif role == EventRoleType.FAMILY:
                    (father_name, mother_name) = self._get_father_and_mother_name(evt)
                    message += "(%s) %s : %s - %s" % (
                        date,
                        mark[7],
                        father_name,
                        mother_name,
                    )
                else:
                    message += "(%s) [%s], %s %s" % (date, event_type, role, descr)
                
                if (self._eyeartodatetime(mark[6]) - currentdt).days > 0 and not self.show_all:
                    message = "<span foreground='grey'><i>%s</i></span>" % message
                
                #do bubble logic
                add_item = Gtk.MenuItem(label=message)
                add_item.get_children()[0].set_use_markup(True)
                add_item.show()
                menu.append(add_item)
                self.itemoption = Gtk.Menu()
                itemoption = self.itemoption
                itemoption.show()
                add_item.set_submenu(itemoption)
                modify = Gtk.MenuItem(label=_("Edit Event"))
                modify.show()
                modify.connect("activate", self.edit_event, event, lat, lon, mark)
                itemoption.append(modify)
                center = Gtk.MenuItem(label=_("Center on this place"))
                center.show()
                center.connect("activate", self.center_here, event, lat, lon, mark)
                itemoption.append(center)
        menu.show()
        menu.popup_at_pointer(event)
        return 1

    def add_place_bubble_message(self, event, lat, lon, marks, menu, place, mark):
        """
        Create the place menu of a marker
        """
        separator = Gtk.SeparatorMenuItem()
        separator.show()
        menu.append(separator)
        add_item = Gtk.MenuItem(label="<b>%s :</b>" % place)
        add_item.get_children()[0].set_use_markup(True)
        add_item.show()
        menu.append(add_item)
        self.itemoption = Gtk.Menu()
        itemoption = self.itemoption
        itemoption.show()
        add_item.set_submenu(itemoption)
        modify = Gtk.MenuItem(label=_("Edit Place"))
        modify.show()
        modify.connect("activate", self.edit_place, event, lat, lon, mark)
        itemoption.append(modify)
        center = Gtk.MenuItem(label=_("Center on this place"))
        center.show()
        center.connect("activate", self.center_here, event, lat, lon, mark)
        itemoption.append(center)
        separator = Gtk.SeparatorMenuItem()
        separator.show()
        menu.append(separator)

    def add_person_bubble_message(self, event, lat, lon, menu, mark):
        """
        Create the person menu of a marker
        """
        #mark[1] is the child's name on child-birth event markers
        name = _nd.display(self.dbstate.db.get_person_from_gramps_id(mark[8]))
        #add_item = Gtk.MenuItem()
        image = Gtk.Image.new_from_surface(self.all_person_icons[mark[8]]["square"])
        #image.show()
        add_item = Gtk.ImageMenuItem(label="%s :" % name,image=image)
        add_item.set_always_show_image(True)
        #add_item.add(image)
        add_item.show()
        menu.append(add_item)
        self.itemoption = Gtk.Menu()
        itemoption = self.itemoption
        itemoption.show()
        add_item.set_submenu(itemoption)
        modify = Gtk.MenuItem(label=_("Edit Person"))
        modify.show()
        modify.connect("activate", self.edit_person, event, lat, lon, mark)
        itemoption.append(modify)
        center = Gtk.MenuItem(label=_("Center on this place"))
        center.show()
        center.connect("activate", self.center_here, event, lat, lon, mark)
        itemoption.append(center)

    def add_specific_menu(self, menu, event, lat, lon): 
        """ 
        Add specific entry to the navigation (right click) menu.
        """ 
        menu.append(Gtk.SeparatorMenuItem())
        add_item = Gtk.MenuItem(label=_("Choose View Format"))
        add_item.connect("activate", lambda s : self._startupdialog())
        add_item.show()
        menu.append(add_item)
        #add_item = Gtk.MenuItem(label=_("_debug"))
        #add_item.connect("activate", self._mapdebug)
        #add_item.show()
        #menu.append(add_item)

    def _createmap(self, active):
        """
        Create all markers for each people's event in the database which has
        a lat/lon.
        @param: active is mandatory but unused in this view. Fix : 10088
        """
        person_handle = self.uistate.get_active('Person')
        self.message_layer.clear_messages()
        self.kml_layer.clear()
        self.remove_all_gps()
        self.remove_all_markers()
        self.lifeway_layer.clear_ways()
        self.date_layer.clear_dates()
        self.dialog = False
        
        if self.database_choice == self.DB_CHOICE_POPUP and not self.show_startup_dialog:
            self.show_startup_dialog = True
            self._startupdialog()
            return
        elif self.database_choice == self.DB_CHOICE_POPUP:
            return
        person = None
        if self.database_choice in self.DB_CHOICES_INITIAL.keys():
            if person_handle:
                person = self.dbstate.db.get_person_from_handle(person_handle)
            if self.active_db_phandle != (self.dbstate.db.get_dbid, person_handle):
                self.active_db_phandle = (self.dbstate.db.get_dbid, person_handle)
                #build data
                if person is not None:
                    self.initial_view = False
                    self._datacollection(person)
                    self.all_sort = sorted(self.place_list,
                                       key=operator.itemgetter(6)
                                      ) #sorted earliest date first

                    progress = ProgressMeter(self.window_name, can_cancel=False, parent=self.uistate.window)
                    progress.set_pass(_('Almost done'), 5)
                    #add truncated list containing locations of children births for drawing lines
                    temp_all_sort = self.all_sort.copy()
                    temp_all_sort.extend(self.place_list_lines) 
                    progress.step()
                    progress.set_header("Sorting Data")
                    temp_all_sort = sorted(temp_all_sort,
                                       key=operator.itemgetter(6)
                                      )
                    progress.step()
                    progress.set_header("Figuring out lines")
                    for data in temp_all_sort:
                        self.all_sort_lines_dict[data[8]].append(data)
                        self.separate_event_locations_offset[data[10]] = [random.uniform(0, 1),random.uniform(0, 2*math.pi)]
                    progress.step()
                    progress.set_header("Finding Missing Parents")
                    self._calculateMissingParents()
                    progress.step()
                    progress.set_header("Generating Icons")
                    self._generateIcons()
                    progress.step()
                    progress.close()
                    self.message_layer.add_message("Welcome to TimeLines Map!")
                    
                    self._calculateminmax()
                    
                    #make bottom control box
                    if not self.hbox_control:
                        self._buildhboxcontrol()
                    else:
                        self._slideraction(self.slider)
                    #set current list of data to all data
                    #this (sort) is the data first shown when person clicked
                    #as opposed to a specific slider value
                    if self.show_all:
                        self.sort = self.all_sort

            # Show map!
            self._refreshdisplay()
        
    def _calculateMissingParents(self):
        for person_id in self.missingparents:
            #earliest place mentioned
            try:
                d = self.all_sort_lines_dict[person_id][0].copy()
                d[7] = EventType((0,"MissingAncestor"))
                #Colour is assigned here but no longer necessary
                #as eventtype "MissingAncestor" now points to drawing the specific icon.
                d[12] = Gdk.RGBA(0.5,0.5,0.5,0.50)
                self.missingparents[person_id][0] = d
                #year to stop displaying
                if self.all_person_duration[person_id][0][1]: #birthrecorded
                    self.missingparents[person_id][1] = self.all_person_duration[person_id][0][0] #birthdate
                else:
                    self.missingparents[person_id][1] = self.all_person_duration[person_id][0][0] - td(days=self._config.get("geotimelines.assumeage")*365) #est year
            except:
                self.missingparents[person_id] = None
                #probably as a individual as parent to an individual with no events
                #ideally would find the most recent individual with events
                pass

    def _datacollection(self, activeperson):
        dbc = self.database_choice
        if dbc == self.DB_CHOICE_ACTIVE: #only active
            self.all_selected_persons = [activeperson]
        elif dbc == self.DB_CHOICE_DB: #all
            for person in self.dbstate.db.iter_people():
                self.all_selected_persons.append(person)
        elif dbc == self.DB_CHOICE_ANCDES:
            self._perperson(activeperson, generation=0, activeperson=activeperson)
        elif dbc == self.DB_CHOICE_FILTER:
            if self.generic_filter:
                for person_handle in self.generic_filter.apply(self.dbstate.db, user=self.uistate.viewmanager.user):
                    self.all_selected_persons.append(self.dbstate.db.get_person_from_handle(person_handle))
                if len(self.all_selected_persons) == 0:
                    pop = Gtk.Dialog()
                    pop.set_title(self.window_name)
                    pop.set_transient_for(self.uistate.window)
                    pop.set_modal(True)
                    pop.vbox.set_spacing(10)
                    pop.vbox.set_border_width(24)
                    pop.vbox.add(Gtk.Label(label="Filter selected no persons"))
                    btn = Gtk.Button()
                    btn.show()
                    btn.set_label("Okay")
                    btn.connect('released', lambda x : pop.destroy())
                    pop.vbox.add(btn)
                    pop.show_all()
                    #load something
                    self.all_selected_persons = [activeperson]
            else:
                pop = Gtk.Dialog()
                pop.set_title(self.window_name)
                pop.set_transient_for(self.uistate.window)
                pop.set_modal(True)
                pop.vbox.set_spacing(10)
                pop.vbox.set_border_width(24)
                pop.vbox.add(Gtk.Label(label="Create a Filter and try again!"))
                btn = Gtk.Button()
                btn.show()
                btn.set_label("Okay")
                btn.connect('released', lambda x : pop.destroy())
                pop.vbox.add(btn)
                pop.show_all()
                #load something
                self.all_selected_persons = [activeperson]
        else:   
            self._perperson(activeperson, generation=0)
            
        #fallback
        if len(self.all_selected_persons) == 0:
            self.all_selected_persons = [activeperson]

        #get events from selected person
        progress = ProgressMeter(self.window_name, can_cancel=False, parent=self.uistate.window)
        num_persons = len(self.all_selected_persons)
        progress.set_pass(_('Gathering data'), num_persons)
        for i, person in enumerate(self.all_selected_persons):
            progress.set_header(f"Persons processed: {i}/{num_persons}")
            random.seed(person.gramps_id)
            self.all_person_duration[person.gramps_id] = None
            self.person_colour_dict[person.gramps_id] = Gdk.RGBA(random.uniform(0.08,1.0),random.uniform(0.08,1.0),random.uniform(0.08,1.0), 1.0)
            self.all_sort_lines_dict[person.gramps_id] = []
            self._getdata(person)
            progress.step()
        progress.close()

    def _perperson(self, person, generation=None, direction=None, activeperson=None):
        '''
            First person is the active person
            then recursively call all ancestors
        '''
        dbc = self.database_choice

        #don't double count
        if person not in self.all_selected_persons:
            self.all_selected_persons.append(person)
        else:
            return  
        #call this method again for all parents in this person's family
        #if dbc = ancestors or both
        if ((dbc == self.DB_CHOICE_ANC or 
            dbc == self.DB_CHOICE_ANCDES or
            dbc == self.DB_CHOICE_REL) and
            (direction == None or direction == 'up')):
            if dbc == self.DB_CHOICE_ANCDES: 
                if activeperson == person:
                    direction = 'up'
            if len(person.get_parent_family_handle_list()) >0:
                for family_handle in person.get_parent_family_handle_list():
                    family = self.dbstate.db.get_family_from_handle(family_handle)
                    if family is not None:
                        handle = family.get_father_handle()
                        if handle:
                            self._perperson(self.dbstate.db.get_person_from_handle(handle), generation=generation+1, direction=direction)
                        else:
                            self.missingparents[person.gramps_id] = [None,None,generation,1]
                        handle = family.get_mother_handle()
                        if handle:
                            self._perperson(self.dbstate.db.get_person_from_handle(handle), generation=generation+1, direction=direction)
                        else:
                            self.missingparents[person.gramps_id] = [None,None,generation,1]
            else:
                self.missingparents[person.gramps_id] = [None,None,generation,2]
        if activeperson == person:
            direction = None
        #if dbc = descendants or both
        if ((dbc == self.DB_CHOICE_DESC or 
            dbc == self.DB_CHOICE_ANCDES or
            dbc == self.DB_CHOICE_REL) and
            (direction == None or direction == 'down')):
            if dbc == self.DB_CHOICE_ANCDES: 
                if activeperson == person:
                    direction = 'down'
            for family_handle in person.get_family_handle_list():
                family = self.dbstate.db.get_family_from_handle(family_handle)
                child_ref_list = family.get_child_ref_list()
                if child_ref_list:
                    for child_ref in child_ref_list:
                            child = self.dbstate.db.get_person_from_handle(child_ref.ref)
                            if child:
                                self._perperson(child, direction=direction, generation=generation+1)
        
    def _isbirthevent(self, event_type):
        return (event_type == EventType.BIRTH or event_type == EventType.BAPTISM)
    def _isdeathevent(self, event_type):
        return (event_type == EventType.DEATH or event_type == EventType.BURIAL or event_type == EventType.CAUSE_DEATH or event_type == EventType.CREMATION)

    def _getdata(self, person):
        person_single_event_types = []
        for event_ref in person.get_event_ref_list():
            if not event_ref:
                continue
            event = self.dbstate.db.get_event_from_handle(event_ref.ref)
            event_type = EventType(event.get_type())
            # note: Only grab the first listed birth/death for each of those types
            # why?: If there are multiple say birth events, GRAMPS displays 
            #       the top entry when viewing the person—display only this event
            #       as opposed to displaying all of them in this geography view
            if self._isbirthevent(event_type) or self._isdeathevent(event_type):
                if event_type in person_single_event_types:
                    continue
                else:
                    person_single_event_types.append(event_type)
            role = event_ref.get_role()
            y = event.get_date_object().to_calendar(self.cal).get_year()
            m = event.get_date_object().to_calendar(self.cal).get_month()
            d = event.get_date_object().to_calendar(self.cal).get_day()
            eyear = str("%04d" % y) + str("%02d" % m) + str("%02d" % d)
            #note: if no year is defined then ignore - don't know where it goes!
            if eyear == "00000000":
                continue
            place_handle = event.get_place_handle()
            if place_handle:
                place = self.dbstate.db.get_place_from_handle(place_handle)
                if place:
                    longitude = place.get_longitude()
                    latitude = place.get_latitude()
                    latitude, longitude = conv_lat_lon(latitude,
                                                       longitude, "D.D8")
                    descr = _pd.display(self.dbstate.db, place)
                    descr1 = _("%(eventtype)s : %(name)s") % {
                                    'eventtype': event_type,
                                    'name': _nd.display(person)}
                    if longitude and latitude:
                        self._append_to_places_list(self.place_list,
                                                    descr, event_type,
                                                    _nd.display(person),
                                                    latitude, longitude,
                                                    descr1, eyear,
                                                    event.get_type(),
                                                    person.gramps_id,
                                                    place.gramps_id,
                                                    event.gramps_id,
                                                    role,
                                                    self.person_colour_dict[person.gramps_id]
                                                    )
                    else:
                        self._append_to_places_without_coord(
                                                    place.gramps_id, descr)
                    
            '''
                find the interval a person is living
                store it as:
                self.all_person_duration[person.gramps_id] = [[date,bool],[date,bool]]
                where   bool : True if actually a birth/death type event; index=0 birth, index=1 death
            '''
            if y>0:
                datadt = self._eyeartodatetime(eyear)
                #this is the first entry
                if self.all_person_duration[person.gramps_id] == None:
                    foundbirth = self._isbirthevent(event_type)
                    founddeath = self._isdeathevent(event_type)
                    self.all_person_duration[person.gramps_id] = [[datadt, foundbirth],[datadt, founddeath]]
                else:
                    #find the interval a person is living
                    #need to be a bit careful about this
                    if self._isbirthevent(event_type):
                        if self.all_person_duration[person.gramps_id][0][1] == True: #already have a b/bp
                            pass
                        else:
                            self.all_person_duration[person.gramps_id][0] = [datadt, True]
                    elif self._isdeathevent(event_type):
                        if self.all_person_duration[person.gramps_id][1][1] == True: #already have a death
                            pass
                        else:
                            self.all_person_duration[person.gramps_id][1] = [datadt, True]
                    else:
                        if self.all_person_duration[person.gramps_id][0][1] == False: #no b event yet
                            if datadt < self.all_person_duration[person.gramps_id][0][0]:
                                self.all_person_duration[person.gramps_id][0][0] = datadt
                        if self.all_person_duration[person.gramps_id][1][1] == False: #no d event yet
                            if datadt > self.all_person_duration[person.gramps_id][1][0]:
                                self.all_person_duration[person.gramps_id][1][0] = datadt
        '''
            Find child birth events and add that location to the parent.
            This is helpful in cases where few events may exist for the
            parent—especially for women—and helps track them on the map.
            Technically this should just be for the mothers.
            
            This won't add events, but will add "places" for drawing lines
        '''
        #all_sort_lines_dict
        family_list = person.get_family_handle_list()
        for family_hdl in family_list:
            family = self.dbstate.db.get_family_from_handle(family_hdl)
            child_ref_list = family.get_child_ref_list()
            if child_ref_list:
                for child_ref in child_ref_list:
                    #should probably be checking against datamap
                    father = mother = None
                    if family.get_father_handle():
                        father = self.dbstate.db.get_person_from_handle(family.get_father_handle())
                    if family.get_mother_handle():
                        mother = self.dbstate.db.get_person_from_handle(family.get_mother_handle())
                    if ((child_ref.get_father_relation() != "Birth" and father == person) or
                        (child_ref.get_mother_relation() != "Birth" and mother == person) ):
                        continue
                    child = self.dbstate.db.get_person_from_handle(child_ref.ref)
                    for event_ref in child.get_event_ref_list():
                        event = self.dbstate.db.get_event_from_handle(event_ref.ref)
                        event_type = EventType(event.get_type())
                        if not self._isbirthevent(event_type):
                            continue
                        role = event_ref.get_role()
                        y = event.get_date_object().to_calendar(self.cal).get_year()
                        m = event.get_date_object().to_calendar(self.cal).get_month()
                        d = event.get_date_object().to_calendar(self.cal).get_day()
                        eyear = str("%04d" % y) + str("%02d" % m) + str("%02d" % d)
                        #note: if no year is defined then ignore - don't know where it goes!
                        if eyear == "00000000":
                            continue
                        place_handle = event.get_place_handle()
                        if place_handle:
                            place = self.dbstate.db.get_place_from_handle(place_handle)
                            if place:
                                longitude = place.get_longitude()
                                latitude = place.get_latitude()
                                latitude, longitude = conv_lat_lon(latitude,
                                                                   longitude, "D.D8")
                                descr = _pd.display(self.dbstate.db, place)
                                descr1 = _("%(eventtype)s : %(name)s") % {
                                                'eventtype': event_type,
                                                'name': _nd.display(person)}
                                if longitude and latitude:
                                    self._append_to_places_list(self.place_list_lines,
                                                                descr, event_type,
                                                                _nd.display(child),
                                                                latitude, longitude,
                                                                descr1, eyear,
                                                                event.get_type(),
                                                                person.gramps_id,
                                                                place.gramps_id,
                                                                event.gramps_id,
                                                                "Parent",
                                                                self.person_colour_dict[person.gramps_id]
                                                                )
                                    break
                            
    def _drawlines(self, lines):
        """
        Create all displacements for one person's events.
        """
        self.lifeway_layer.clear_ways()
        for gramps_id in lines:
            marks = lines[gramps_id]
            color = self.person_colour_dict[gramps_id]
            reducedcolor = Gdk.Color(int(60535*color.red),int(60535*color.green),int(60535*color.blue))
            points = []
            mark = None
            for mark in marks:
                if self._config.get("geotimelines.separate_markers"):
                    lat_1 = float(mark[3])/180*math.pi
                    r=self.separate_event_locations_offset[mark[10]][0]*self._config.get("geotimelines.show_missing_gen_radius")*math.pi/3189
                    y=r*math.sin(self.separate_event_locations_offset[mark[10]][1])
                    x=r*self.separate_event_locations_offset[mark[10]][0]*math.cos(self.separate_event_locations_offset[mark[10]][1])
                    startlat = float(mark[3])+y/(1+math.log(math.tan(math.pi/4+abs(lat_1/2))))
                    startlon = float(mark[4])+x
                else:
                    startlat = float(mark[3])
                    startlon = float(mark[4])
                not_stored = True
                #for idx in range(0, len(points)):
                #    if points[idx][0] == startlat and points[idx][1] == startlon:
                #        not_stored = False
                #if not_stored:
                points.append((startlat, startlon))
            if len(points) > 1:
                self.lifeway_layer.add_way(points, reducedcolor)
        return False
        
    def _calculateminmax(self):
        self.mindt = dt(9999,12,31)
        self.maxdt = dt(1,1,1)
        if len(self.place_list) == 0:
            pop = Gtk.Dialog()
            pop.set_title(self.window_name)
            pop.set_transient_for(self.uistate.window)
            pop.set_modal(True)
            pop.vbox.set_spacing(10)
            pop.vbox.set_border_width(24)
            pop.vbox.add(Gtk.Label(label="No time-place data associated with selected person(s)\n\nPlease try again with a different selection"))
            btn = Gtk.Button()
            btn.show()
            btn.set_label("Okay")
            btn.connect('released', lambda x : pop.destroy())
            pop.vbox.add(btn)
            pop.show_all()
        else:
            for place in self.place_list:
                try:
                    date = self._eyeartodatetime(place[6])
                    if date < self.mindt: self.mindt = date
                    if date > self.maxdt: 
                        self.maxdt = date
                except:
                    #probably an event with no date—skip
                    pass
        self.minslider = 0
        self.maxslider = (self.maxdt-self.mindt).days

    '''#############################
        Time stuff
    #############################'''
    
    def _eyeartodatetime(self, eyear):
        y = int(eyear[0:4])
        m = max(1,int(eyear[4:6]))
        d = max(1,int(eyear[6:8]))
        return dt(y,m,d)

    def _datetimetoeyear(self,date):
        y = date.year
        m = date.month
        d = date.day
        return str("%04d" % y) + str("%02d" % m) + str("%02d" % d)
        
    def _datetimetoiso(self,date):
        y = date.year
        m = date.month
        d = date.day
        return str("%04d" % y) + "-" + str("%02d" % m) + "-" + str("%02d" % d)

    def _datetimetodiscreteday(self, indate):
        return self.minslider + (indate-self.mindt).days

    def _discretedaytodatetime(self, d):
        return self.mindt + td(days=d)

    def _discretedaytoeyear(self, d):
        return self._datetimetoeyear(self._discretedaytodatetime(d))
    
    def _discretedaytoiso(self, d):
        return self._datetimetoiso(self._discretedaytodatetime(d))

    def _addmonth(self, indate, months):
        returndt = indate
        direction = 1
        if months < 0:
            direction = -1
        for m in range(abs(months)):
            daysinmonth = calendar.monthrange(returndt.year,returndt.month)[1]
            returndt += td(daysinmonth*direction)
        return returndt
        '''
        monthstoadd = months
        daystoadd = indate.day-1
        indate.replace(day=1)
        if monthstoadd+indate.month <= 12:
            return indate.replace(month=indate.month+monthstoadd)+td(daystoadd)
        else:
            addedyears = (monthstoadd+indate.month)//12
            addedmonths = (monthstoadd+indate.month)%12
            return indate.replace(year=indate.year+addedyears,month=addedmonths)+td(daystoadd)
        '''
        
    '''#############################
        gui stuff
    #############################'''
    
    def _animate_step_interval(self, spinbutton):
        self.animation_step_interval = int(spinbutton.get_value())
    def _animate_step_type(self, comboboxtext):
        self.animation_step_type = comboboxtext.get_active()
    def _animate_step_time(self, spinbutton):
        self.animation_step_time = int(spinbutton.get_value())

    def _animate(self, button):
        if not self.play:
            return
        start_t = time.time()
        currentdt = self._discretedaytodatetime(self.slider.get_value())
        targetdt = None
        if self.animation_step_type == 0: # year
            targetdt = currentdt.replace(year=currentdt.year+self.animation_step_interval)
        elif self.animation_step_type == 1: # month
            targetdt = self._addmonth(currentdt,self.animation_step_interval)
        else: #day
            targetdt = currentdt + td(self.animation_step_interval)
        
        self.slider.set_value(self._datetimetodiscreteday(targetdt))

        if self.slider.get_value() == self.maxslider:
            self.play = False
            button.set_label("Play")
        if self.slider.get_value() == self.minslider:
            self.play = False
            button.set_label("Play")
        end_t = time.time()
        animate_calc_time = (end_t - start_t)*1000
        self.animate_calc_time_list.append(animate_calc_time)
        if len(self.animate_calc_time_list)>100:
            self.animate_calc_time_list.pop(0)
        GLib.timeout_add(
            max(1, self.animation_step_time - animate_calc_time), #time between calls to the function; discludes calc time
            self._animate,
            button,
        )

    def _animate_start(self, button):
        self.play = not self.play
        if self.play: 
            button.set_label("Pause")
        else: 
            button.set_label("Play")
        self._animate(button)

    def _slider_formatvalue(self,scale,pos):
        return self._discretedaytoiso(pos)

    def _button_showall(self, button, playbutton):
        self.show_all = button.get_active()
        if self.show_all: 
            if self.play:
                self.play = not self.play
                playbutton.set_label("Play")

        self._refreshdisplay()


    def _checkbutton_lines(self, checkbutton):
        self.show_lines = checkbutton.get_active()
        if self.show_lines:
            if self.show_all:
                self._drawlines(self.all_sort_lines_dict)
            else: #using slider
                self._drawlines(self.lines_marks_dict)
        else:
            self.lifeway_layer.clear_ways()
        self.osm.grab_focus()

    def _buildhboxcontrol(self):
        # pack_start(child, bool expand, bool fill, int padding)
        
        #########################################
        # Widgets                               #
        #########################################
        
        self.hbox_control = Gtk.Box(
            homogeneous=False, 
            spacing=3,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.hbox_control.show()
        
        leftbox = Gtk.Box(
            homogeneous=False, 
            spacing=3,
            orientation=Gtk.Orientation.VERTICAL
        )
        leftbox.set_margin_start(7)
        leftbox.set_margin_end(4)
        leftbox.set_margin_top(4)
        leftbox.set_margin_bottom(4)
        leftbox.show()
        
        animatebox = Gtk.Box(
            homogeneous=False, 
            spacing=3,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        animatebox.show()
        
        rightbox = Gtk.Box(
            homogeneous=False, 
            spacing=3,
            orientation=Gtk.Orientation.VERTICAL
        )
        rightbox.set_margin_start(4)
        rightbox.set_margin_end(7)
        rightbox.set_margin_top(4)
        rightbox.set_margin_bottom(4)
        rightbox.show()
        
        rightboxgrid = Gtk.Grid()
        rightboxgrid.set_border_width(0)  #width around?
        rightboxgrid.set_column_spacing(4) #space between col
        rightboxgrid.set_row_spacing(0)
        rightboxgrid.show()
        
        rightbox.pack_start(rightboxgrid, True, False, 1)
        
        '''
            animation control
        '''
        playbtn = Gtk.Button()
        playbtn.show()
        playbtn.set_label("Play")
        playbtn.connect('clicked', self._animate_start)
        animatebox.pack_start(playbtn, False, False, 1)

        lbl = Gtk.Label()
        lbl.show()
        lbl.set_label("Advance")
        animatebox.pack_start(lbl, False, False, 1)
        
        #value, lower, upper, step_inc, page_inc, page_size
        ad = Gtk.Adjustment(self.animation_step_interval, -1000, 1000, 1, 0, 0)
        spnbtn = Gtk.SpinButton(adjustment=ad, climb_rate=1, digits=0)
        spnbtn.show()
        spnbtn.connect('value-changed',self._animate_step_interval)
        animatebox.pack_start(spnbtn, False, False, 1)

        store = Gtk.ListStore(int, str)
        for item in self.ymdindex:
            store.append(item)
        cmbbxtxt = Gtk.ComboBox(model=store)
        cell = Gtk.CellRendererText()
        cmbbxtxt.pack_start(cell, True)
        cmbbxtxt.add_attribute(cell, "text", 1)
        cmbbxtxt.set_active(self.animation_step_type)
        cmbbxtxt.connect('changed', self._animate_step_type )
        cmbbxtxt.show()
        animatebox.pack_start(cmbbxtxt, False, False, 1)
        
        lbl = Gtk.Label()
        lbl.show()
        lbl.set_label("every")
        animatebox.pack_start(lbl, False, False, 1)

        ad = Gtk.Adjustment(self.animation_step_time, 1, 1000, 10, 0, 0)
        spnbtn = Gtk.SpinButton(adjustment=ad, climb_rate=1, digits=0)
        spnbtn.show()
        spnbtn.connect('value-changed',self._animate_step_time)
        animatebox.pack_start(spnbtn, False, False, 1)
        
        lbl = Gtk.Label()
        lbl.show()
        lbl.set_label("ms")
        animatebox.pack_start(lbl, False, False, 1)
        
        '''
            done animation control
        '''
        self.btn_showall = Gtk.ToggleButton()
        self.btn_showall.show()
        self.btn_showall.set_label("Show All")
        self.btn_showall.set_active(True)
        self.btn_showall.connect('clicked', self._button_showall, playbtn)
        rightboxgrid.attach(self.btn_showall, 1, 1, 1, 1)
        
        self.btn_setview = Gtk.Button()
        self.btn_setview.show()
        self.btn_setview.set_label("Set View")
        self.btn_setview.connect('clicked', lambda s : self._startupdialog())
        rightboxgrid.attach(self.btn_setview, 2, 1, 1, 1)
        
        ckbtn = Gtk.CheckButton()
        ckbtn.show()
        ckbtn.set_label("Show Lines")
        ckbtn.set_active(self._config.get("geotimelines.default_show_lines"))
        ckbtn.connect('toggled', self._checkbutton_lines )
        rightboxgrid.attach(ckbtn, 2, 2, 1, 1)
        
        ckbtn = Gtk.CheckButton()
        ckbtn.show()
        ckbtn.set_label("Show Ticks")
        ckbtn.set_active(self._config.get("geotimelines.default_show_ticks"))
        ckbtn.connect('clicked', lambda s : self._buildslidermarks(s.get_active()))
        rightboxgrid.attach(ckbtn, 1, 2, 1, 1)
        
        #########################################
        # Slider                                #
        #########################################
        
        adj = Gtk.Adjustment(value=int(self.maxslider/2), 
                             lower=self.minslider, 
                             upper=self.maxslider,
                             step_increment=1, 
                             page_increment=0, 
                             page_size=0)
        self.slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                           adjustment=adj)
        self.slider.set_size_request(-1,64)
        self.slider.set_margin_start(0)
        self.slider.set_margin_end(0)
        self.slider.connect('value-changed', self._slideraction)
        self.slider.connect('format-value', self._slider_formatvalue)
        self.slider.show()
        self._calculateminmax()
        self._buildsliderrange()
        
        #########################################
        # Pack                                  #
        #########################################
        
        #leftbox.pack_start(Gtk.Separator(), False, False, 1)
        #f = Gtk.Frame()
        #f.add(animatebox)
        leftbox.pack_start(animatebox, True, False, 1)
        #leftbox.pack_start(f, False, False, 1)
        

        self.hbox_control.pack_start(leftbox, False, False, 1)
        separator = Gtk.Separator()
        separator.set_margin_top(6)
        separator.set_margin_bottom(6)
        separator.show()
        self.hbox_control.pack_start(separator, False, False, 1)
        self.hbox_control.pack_start(self.slider, True, True, 1)
        separator = Gtk.Separator()
        separator.set_margin_top(6)
        separator.set_margin_bottom(6)
        separator.show()
        self.hbox_control.pack_start(separator, False, False, 1)
        self.hbox_control.pack_start(rightbox, False, False, 1)
        
        self.vbox.pack_start(self.hbox_control, False, False, 1)
        
        '''
        btn = Gtk.Button()
        btn.show()
        btn.set_label("hi")
        btn.connect('released', lambda s : print('released'))
        self.hbox_control.pack_start(btn, False, False, 1)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label("hi")
        btn.connect('released', lambda s : print('released'))
        self.hbox_control.pack_start(btn, False, False, 1)
        '''
        

    def _buildsliderrange(self):  
        self.slider.clear_marks()
        self.slider_marks = []
        self.slider.set_range(self.minslider, self.maxslider)
        #make marks
        #every x years make a mark
        earliestdt = self._discretedaytodatetime(self.minslider)
        latestdt = self._discretedaytodatetime(self.maxslider)
        x = 10 #years for minor mark
        x_start = x-self.mindt.year%x + self.mindt.year
        x_end   = self.maxdt.year - self.maxdt.year%x
        majormark = 100 #years for a major mark
        for i in range((x_end-x_start)//x+1):
            year = int(x_start+(i*x))
            day = self._datetimetodiscreteday(dt(year,1,1))
            if year%majormark == 0:
                self.slider_marks.append([day,str(year)])
                self.slider.add_mark(day,Gtk.PositionType.BOTTOM,str(year))
            else:
                self.slider_marks.append([day,None])
                self.slider.add_mark(day,Gtk.PositionType.BOTTOM,None)
        self._buildslidermarks(self._config.get("geotimelines.default_show_ticks"))

    def _buildslidermarks(self, showmarks):
        self.slider.clear_marks()
        if showmarks:
            for mark in self.slider_marks:
                self.slider.add_mark(mark[0],Gtk.PositionType.BOTTOM,mark[1])

    def _slideraction(self, scale):
        if self.show_all:
            self.btn_showall.set_active(False)

        pos = int(scale.get_value()) #in discrete days
        currentdt = self.mindt + td(days=pos)
        #currenteyear = self._datetimetoeyear(currentdt)
        
        #days to put proper events on the map—these use custom icons
        daysextra = self._config.get("geotimelines.persist_drawn_lines_days")
        #
        #grab only those dates fitting in [A,B] from self.all_sort and put into self.sort
        #slider position is in discrete days
        #data is listed in eyear
        #A and B are eyears
        #
        #!!This grabs all the data within a time interval (daysextra)
        #
        
        Adt = self.mindt + td(days=pos)
        A = self._datetimetoeyear(Adt)
        Bdt = self.mindt + td(days=pos-daysextra)
        B = self._datetimetoeyear(Bdt)
        i1 = bisect.bisect(self.all_sort, B, key=lambda i: i[6])
        i2 = bisect.bisect(self.all_sort, A, key=lambda i: i[6])
        self.sort = self.all_sort[i1:i2]

        if self._config.get("geotimelines.show_missing_gen") > 0:
            for person_id in self.missingparents:
                if self.missingparents[person_id] == None:
                    continue
                if self.missingparents[person_id][3] == 1 and self._config.get("geotimelines.show_missing_gen") == 2:
                    continue
                last_time = self.missingparents[person_id][1]
                placedata = self.missingparents[person_id][0]
                if (currentdt - last_time).days < 0:
                    self.sort.append(placedata)
                    
        #self.sort = []
        
        '''
            drawing lines
        '''
        #
        #!!This grabs the most recent data, 
        #!!and all the data within a time interval (showlineslastdays) for drawing lines!
        #
        showlineslastdays = self._config.get("geotimelines.persist_drawn_lines_days") #days
        self.lines_marks_dict = {}
        currentpeople = 0
        for person_id in self.all_person_duration:
            if self.all_person_duration[person_id]:
                deathrecorded = self.all_person_duration[person_id][1][1]
                birthrecorded = self.all_person_duration[person_id][0][1]
                earliestestimate = self._config.get("geotimelines.assumeage")*365 #days old
                oldestage = self._config.get("geotimelines.assumedeath")*365 #days old
                dayssinceearliestevent = (currentdt - self.all_person_duration[person_id][0][0]).days
                dayssincelastevent = (currentdt - self.all_person_duration[person_id][1][0]).days
                wasborn = birthrecorded and dayssinceearliestevent > 0
                wasprobablyborn = not birthrecorded and dayssinceearliestevent > -earliestestimate
                dead = deathrecorded and dayssincelastevent > 0
                probablydead = (
                    birthrecorded and not deathrecorded and (dayssinceearliestevent > oldestage) or
                    not birthrecorded and not deathrecorded and (dayssinceearliestevent > oldestage - earliestestimate)
                    )
                living = (wasborn or wasprobablyborn) and not dead and not probablydead
                if living:
                    currentpeople+=1
                    numevents = 0
                    try:
                        olddata = self.all_sort_lines_dict[person_id][0]
                    except:
                        olddata = None
                    for d in self.all_sort_lines_dict[person_id]:
                        data = d
                        days_since_data = (currentdt - self._eyeartodatetime(data[6])).days
                        if self.show_lines:
                            if person_id not in self.lines_marks_dict:
                                self.lines_marks_dict[person_id] = []
                            '''
                                drawing lines
                            '''
                            #Grab the olddata if the current data within "showlineslastdays" days
                            #of the current date and store for purposes of drawing lines.
                            #
                            #Since "self.all_sort_lines_dict" is sorted by dategrab the 
                            #previously indexed event.
                            if (days_since_data < showlineslastdays and 
                                days_since_data >= 0):
                                self.lines_marks_dict[person_id].append(olddata)
                            
                        '''
                            add most recent event for all living persons
                        '''
                        #get latest event
                        #if person_id == "I8983":
                        #    print(currentdt, data)
                        if days_since_data > 0:
                            olddata = data
                            numevents+=1
                        else:
                            if self.show_lines:
                                self.lines_marks_dict[person_id].append(olddata) 
                            break

                    if olddata:
                        t = olddata.copy()
                        if numevents == 0: #no events yet, but they are living
                            t[7] = EventType.UNKNOWN #used in drawing a "?"
                        elif numevents == len(self.all_sort_lines_dict[person_id]):# and (self.maxdt - currentdt).days > 4380: #no further events, not yet declared dead
                            t[7] = EventType((0,"NoFurtherData")) #used in drawing an "X"
                        else:
                            t[7] = EventType((0,"NoData"))
                        self.sort.append(t)
                    #if data:
                        #self.sort.append(data)
                        #self._add_person_marker(tempplace[3],tempplace[4],tempplace[8])


        
        

        self.lifeway_layer.clear_ways()
        if self.show_lines:
            self._drawlines(self.lines_marks_dict)

        #self.sort = sorted(self.sort, key=operator.itemgetter(6) )
        self._create_markers()
        self.date_layer.clear_dates()
        self.date_layer.add_date(self._datetimetoiso(currentdt))
        self.date_layer.last = ""
        self.message_layer.clear_messages()
        #self.message_layer.add_message(_("d: %s") % scale.get_value())
        self.message_layer.add_message(_("Number of Persons: %s") % currentpeople)
        


    #def animate(

    def _add_person_marker(self, lat, lon, gramps_id):
        """
        Add a new marker
        """
        default_image = self.geo_person
        #value = default_image
        #if event_type is not None:
        #    value = self.geo_othermap.get(int(event_type), default_image)
        #if differtype:  # in case multiple evts
        value = default_image  # we use default icon.
        self.marker_layer.add_marker(
            (float(lat), float(lon)), value, 0, gramps_id=gramps_id#Gdk.Color.to_string(self.person_colour_dict[gramps_id])
        )
    
    #def _mapdebug(self, menu):
        #pass
        #self.slider.set_value(74796)
        #self._startupdialog()
        #self.add_marker(
        #    None, None, 49, -100, None, True, 10, color="#FF0000"
        #)
        #markerlayer.py line 161 should be marker[3]?
        #self.osm.image_add(49,-100,GdkPixbuf.Pixbuf.new_from_file('gramps/plugins/view/sunflower.png'))
        #self.osm.gps_add(49,-100,0)
        #self.osm.gps_add(59,-100,0)
 

    def _get_configure_page_funcs(self):
        """
        The function which is used to create the configuration window.
        """
        return [self.map_options, self.specific_options]

    def specific_options(self, configdialog):
        """
        Add specific entry to the preference menu.
        Must be done in the associated view.
        """
        topframemargin = 10
        
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)

        rightgrid = Gtk.Grid()
        rightgrid.set_border_width(2)
        rightgrid.set_column_spacing(2)
        rightgrid.set_row_spacing(2)

        leftgrid = Gtk.Grid()
        leftgrid.set_border_width(2)
        leftgrid.set_column_spacing(2)
        leftgrid.set_row_spacing(2)

        ####.attach(child, column, row, width, height)
        grid.attach(leftgrid, 1, 1, 2, 1)
        grid.attach(rightgrid, 3, 1, 2, 1)
        
        #########################################
        # Left Grid                             #
        #########################################
            
        preferenceoptions = Gtk.Grid()
        preferenceoptions.set_border_width(12)
        preferenceoptions.set_column_spacing(6)
        preferenceoptions.set_row_spacing(6)
        preferenceoptions.set_margin_top(topframemargin)
        
        leftgrid.attach(preferenceoptions, 1, 2, 2, 1)
        f = Gtk.Frame.new("Preferences")
        f.set_label_align(0.5, 0.5)
        leftgrid.attach(f, 1, 2, 2, 1)
        


        staggerrow=1
        f = Gtk.Frame.new()
        preferenceoptions.attach(f,1,staggerrow,2,1)
        staggergrid = Gtk.Grid()
        staggergrid.set_border_width(6)
        preferenceoptions.attach(staggergrid, 1, staggerrow, 1, 1)
        configdialog.add_checkbox(
            staggergrid,
            _('Stagger the map markers\n'
              'to differentiate different\n'
              'markers at the same location'),
            1, 
            'geotimelines.separate_markers')
        staggergrid2 = Gtk.Grid()
        staggergrid2.set_border_width(6)
        preferenceoptions.attach(staggergrid2, 2, staggerrow, 1, 1)
        configdialog.add_spinner(
            staggergrid2,
            _("Stagger Radius (hectometers)\nas measured along the equator\n(includes latitude distortion)"),
            1,
            'geotimelines.show_missing_gen_radius',
            (1, 100),
        )
        
        configdialog.add_combo(
            preferenceoptions,
            _("Display markers for unknown ancestors\nbased on earliest descendant location"),
            2,
            'geotimelines.show_missing_gen',
            [(0,"Do Not Show"), (1,"If Missing Any Parent"), (2,"If Missing Both Parents")],
            #callback=self.cb_update_font,
            #valueactive=True, #store value or position
        )
        configdialog.add_spinner(
            preferenceoptions,
            _("Days to keep lines on the map after\nan event"),
            3,
            'geotimelines.persist_drawn_lines_days',
            (1, 36500),
        )
            
        mapiconoptions = Gtk.Grid()
        mapiconoptions.set_border_width(12)
        mapiconoptions.set_column_spacing(6)
        mapiconoptions.set_row_spacing(6)
        mapiconoptions.set_margin_top(topframemargin)
        
        leftgrid.attach(mapiconoptions, 1, 3, 2, 1)
        f = Gtk.Frame.new("Map Icon Options")
        f.set_label_align(0.5, 0.5)
        leftgrid.attach(f, 1, 3, 2, 1)   
            
        configdialog.add_checkbox(
            mapiconoptions,
            _('Use custom map icons'),
            1, 
            'geotimelines.use_custom_icons',
            extra_callback = self._config_use_custom_icons
            )
        configdialog.add_spinner(
            mapiconoptions,
            _("If there is no birth event for a person, their age\nis assumed to be this at their first event"),
            2,
            'geotimelines.assumeage',
            (1, 120),
        ) 
        configdialog.add_spinner(
            mapiconoptions,
            _("If there is no death event for a person, they will\nbe assumed dead at this age"),
            3,
            'geotimelines.assumedeath',
            (1, 120),
        ) 
            
        # Date format:
        '''
        obox = Gtk.ComboBoxText()
        formats = get_date_formats()
        list(map(obox.append_text, formats))
        active = self._config.get("geotimelines.date-format")
        if active >= len(formats):
            active = 0
        obox.set_active(active)
        obox.connect("changed", self._date_format_changed)
        preferenceoptions.attach(Gtk.Label("Date Format: "), 1, 3, 1, 1)
        preferenceoptions.attach(obox, 2, 3, 1, 1)
        '''
            
        #########################################
        # Right Grid                            #
        #########################################

        animationgrid = Gtk.Grid()
        animationgrid.set_border_width(12)
        animationgrid.set_column_spacing(6)
        animationgrid.set_row_spacing(6)
        animationgrid.set_margin_top(topframemargin)
        
        rightgrid.attach(animationgrid, 1, 1, 2, 1)
        f = Gtk.Frame.new("Default Animation Options")
        f.set_label_align(0.5, 0.5)
        rightgrid.attach(f, 1, 1, 2, 1)
        #animation options
        #animationgrid.attach(Gtk.Label(""), 1,10,2,1)

        configdialog.add_spinner(
            animationgrid,
            _("Number of steps"),
            1,
            "geotimelines.animation_step_interval",
            (-1000, 1000),
            #callback=self.cb_update_maxgen,
        )
        configdialog.add_combo(
            animationgrid,
            _("Type of steps"),
            2,
            "geotimelines.animation_step_type",
            self.ymdindex,
            #callback=self.cb_update_font,
            #valueactive=True, #store value or position
        )
        configdialog.add_spinner(
            animationgrid,
            _("Steps per millisecond"),
            3,
            "geotimelines.animation_step_time",
            (1, 1000),
            #callback=self.cb_update_maxgen,
        )
        
        defaultoptions = Gtk.Grid()
        defaultoptions.set_border_width(12)
        defaultoptions.set_column_spacing(6)
        defaultoptions.set_row_spacing(6)
        defaultoptions.set_margin_top(topframemargin)
        
        rightgrid.attach(defaultoptions, 1, 2, 2, 1)
        f = Gtk.Frame.new("Default Behaviour Options")
        f.set_label_align(0.5, 0.5)
        rightgrid.attach(f, 1, 2, 2, 1)
        
        startupreflist = []
        for c in self.DB_CHOICES_INITIAL.values():
            startupreflist.append((len(startupreflist), c))
        configdialog.add_combo(
            defaultoptions,
            _("Initial map view on Gramps startup"),
            1,
            "geotimelines.initial_view_type",
            startupreflist,
            #callback=self.cb_update_font,
            #valueactive=True, #store value or position
        )
        onchangereflist = []
        for c in self.DB_CHOICES_SWITCH.values():
            onchangereflist.append((len(onchangereflist), c))
        configdialog.add_combo(
            defaultoptions,
            _("Initial map view after startup and\nafter changing the active person"),
            2,
            "geotimelines.active_view_type",
            onchangereflist,
            #callback=self.cb_update_font,
            #valueactive=True, #store value or position
        )        
        configdialog.add_checkbox(
            defaultoptions,
            _('Show map travel lines on startup'),
            3, 
            'geotimelines.default_show_lines',
            )
        configdialog.add_checkbox(
            defaultoptions,
                _('Show time ticks on navigation bar on startup'),
            4, 
            'geotimelines.default_show_ticks',
            )
        
        
        notesgrid = Gtk.Grid()
        notesgrid.set_border_width(12)
        notesgrid.set_column_spacing(6)
        notesgrid.set_row_spacing(6)
        notesgrid.set_margin_top(topframemargin)
        
        #col row w h
        rightgrid.attach(notesgrid, 1, 3, 2, 1)
        f = Gtk.Frame.new("Other")
        f.set_label_align(0.5, 0.5)
        rightgrid.attach(f, 1, 3, 2, 1)
        avg_animate_calc_time = 0
        for k in self.animate_calc_time_list:
            avg_animate_calc_time+=k
        avg_animate_calc_time = avg_animate_calc_time/len(self.animate_calc_time_list)
        lbl = Gtk.Label()
        lbl.show()
        lbl.set_label("Average time in ms to animate one step:\n(This is the minimum effective ms)")
        notesgrid.attach(lbl, 1, 1, 1, 1)
        lbl = Gtk.Label()
        lbl.show()
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_size_request(70,-1)
        lbl.set_label(str(int(avg_animate_calc_time)))
        notesgrid.attach(lbl, 2, 1, 1, 1)
        
        return _('TimeLines Map options'), grid

    def _refreshdisplay(self):
        self._set_default_marker()
        self._create_markers()
        
        if self.show_all:
            self.sort = self.all_sort
            self._create_markers()

            self.message_layer.clear_messages()
            if self.database_choice == self.DB_CHOICE_ACTIVE:
                self.message_layer.add_message(f"TimeLines for {_nd.display(self.dbstate.db.get_person_from_handle(self.uistate.get_active('Person')))}")
            else:
                self.message_layer.add_message(_("Number of Persons: %s") % len(self.all_sort_lines_dict))
        else:
            self._slideraction(self.slider)
        
        self.lifeway_layer.clear_ways() #removes lines
        if self.show_lines:
            if self.show_all:
                self._drawlines(self.all_sort_lines_dict)
            else: #using slider
                self._drawlines(self.lines_marks_dict)
        self._set_center_and_zoom()
        
        #self.clear_view()
        #self.build_widget()
        #self._buildslider()

    def _config_use_custom_icons(self, checkbox):
        self._refreshdisplay()

    def _startupdialog(self):
        self.dialog = True
        dialog = Gtk.Dialog()
        dialog.set_title("Choose how to draw the map!")
        dialog.set_size_request(400, 100)
        dialog.vbox.set_spacing(10)
        dialog.vbox.set_border_width(24)
        text = Gtk.Label(label="Choose one of the following to construct this mapview. This can be\nchanged later by right-clicking and selecting \"Choose View Format\"")
        text.set_use_markup(True)
        dialog.vbox.add(text)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"<b>Only</b> \"{_nd.display(self.dbstate.db.get_person_from_handle(self.uistate.get_active('Person')))}\"")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_ACTIVE)
        dialog.vbox.add(btn)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"\"{_nd.display(self.dbstate.db.get_person_from_handle(self.uistate.get_active('Person')))}\" and their <b>Ancestors</b>")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_ANC)
        dialog.vbox.add(btn)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"\"{_nd.display(self.dbstate.db.get_person_from_handle(self.uistate.get_active('Person')))}\" and their <b>Descendants</b>")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_DESC)
        dialog.vbox.add(btn)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"\"{_nd.display(self.dbstate.db.get_person_from_handle(self.uistate.get_active('Person')))}\" and both their <b>Ancestors and Descendants</b>")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_ANCDES)
        dialog.vbox.add(btn)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"<b>All Connections</b> to \"{_nd.display(self.dbstate.db.get_person_from_handle(self.uistate.get_active('Person')))}\"")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_REL)
        dialog.vbox.add(btn)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"<b>Entire Database</b>")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_DB)
        dialog.vbox.add(btn)
        
        btn = Gtk.Button()
        btn.show()
        btn.set_label(f"Selection from <b>Filter</b>")
        btn.get_children()[0].set_use_markup(True)
        btn.connect('released', self._startupdialogbutton, dialog, self.DB_CHOICE_FILTER)
        dialog.vbox.add(btn)
        
        
        parent = None
        if not parent:  # if we don't have an explicit parent,
            # try to find one
            for win in Gtk.Window.list_toplevels():
                if win.is_active():
                    parent = win
                    break
        # if we still don't have a parent, give up
        if parent:
            dialog.set_transient_for(parent)
            dialog.set_modal(True)
        dialog.show_all()

    def _startupdialogbutton(self, button, dialog, option):
        self.database_choice = option
        dialog.destroy()
        self._cleardata()
        self.show_startup_dialog = False
        self.goto_handle()

        
    '''
    def _date_format_changed(self, obj):
        self._config.set("geotimelines.date-format", obj.get_active())
    '''


    def _draw_cairo_surface(self, gramps_id, placeid=None, event_type=None):
        '''
        this is not drawing directly to the map. It's giving
        an image to the markerlayer and so is still subject
        to translations made by markerlayer.do_draw.
        '''

        placetype = self.dbstate.db.get_place_from_gramps_id(placeid).get_type()
        if event_type == EventType.UNKNOWN:
            return self.all_person_icons[gramps_id]["?"]
        elif str(event_type) == "NoFurtherData":   #no further record
            return self.all_person_icons[gramps_id]["x"]
        elif str(event_type) == "MissingAncestor": #unknown ancestor placeholders
            return self.missingparent_icon
        elif event_type == EventType.RESIDENCE:
            return self.all_person_icons[gramps_id]["house"]
        elif event_type == EventType.BAPTISM:
            return self.all_person_icons[gramps_id]["+"]
        elif event_type == EventType.BIRTH:
            return self.all_person_icons[gramps_id]["+"]
        elif event_type == EventType.DEATH:
            return self.all_person_icons[gramps_id]["—"]
        elif event_type == EventType.BURIAL:
            return self.all_person_icons[gramps_id]["gravestone"]
        elif placetype == 'Country':
            return self.all_person_icons[gramps_id]["ring_large"]
        elif placetype == 'State' or placetype == 'Province' :
            return self.all_person_icons[gramps_id]["ring_medium"]
        elif placetype in self._config.get('geotimelines.generalplace'):
            return self.all_person_icons[gramps_id]["ring_small"]
        else:
            return self.all_person_icons[gramps_id]["circle"]
                
    def _generateIcons(self):
        self.missingparent_icon = self._draw_text(Gdk.RGBA(0.5,0.5,0.5,0.50), 20.0, "?")
        for gramps_id in self.person_colour_dict:
            colour = self.person_colour_dict[gramps_id]
            self.all_person_icons[gramps_id] = {
                "square" : self._draw_square(colour),
                "circle" : self._draw_circle(colour),
                "house" : self._draw_house(colour),
                "gravestone" : self._draw_gravestone(colour),
                "ring_small" : self._draw_cut_ring(colour, 10),
                "ring_medium" : self._draw_cut_ring(colour, 15),
                "ring_large" : self._draw_cut_ring(colour, 20),
                "?" : self._draw_text(colour, 30.0, "?"),
                "?small" : self._draw_text(colour, 20.0, "?"),
                "x" : self._draw_text(colour, 30.0, "x"),
                "+" : self._draw_text(colour, 40.0, "+"),
                "—" : self._draw_text(colour, 40.0, "-"),            
            }

    def _draw_circle(self, colour):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 48, 48)
        ctx = cairo.Context(surface)
        
        ctx.set_line_width(4.0)
        radius = 8
        
        ctx.set_line_width(6.0)
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.arc(24,24, radius, 0, 2*math.pi)
        ctx.stroke()
        
        ctx.set_line_width(4.0)
        ctx.set_source_rgba(
            colour.red,
            colour.green,
            colour.blue,
            colour.alpha
        )
        ctx.arc(24,24, radius, 0, 2*math.pi)
        ctx.fill()
        ctx.arc(24,24, radius, 0, 2*math.pi)
        ctx.stroke()

        #ctx.set_source_surface(surface, -24, -24)
        ctx.save()
        return surface
        
    def _draw_house(self, colour):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 48, 48)
        ctx = cairo.Context(surface)
        
        ctx.set_line_width(3.5)
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.move_to(16,32)
        ctx.line_to(16,22)
        ctx.line_to(24,16)
        ctx.line_to(32,22)
        ctx.line_to(32,32)
        ctx.line_to(16,32)
        ctx.stroke()
        
        ctx.set_line_width(4.0)
        ctx.set_source_rgba(
            colour.red,
            colour.green,
            colour.blue,
            colour.alpha
        )
        ctx.move_to(16,32)
        ctx.line_to(16,22)
        ctx.line_to(24,16)
        ctx.line_to(32,22)
        ctx.line_to(32,32)
        ctx.line_to(16,32)
        ctx.fill()

        #ctx.set_source_surface(surface, -24, -24)
        ctx.save()
        return surface

    def _draw_gravestone(self, colour):
        imgwdth = 48
        imghght = 48
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, imgwdth, imghght)
        ctx = cairo.Context(surface)
        
        
        height = 10 #less arc
        width = 18
        arcradius = 28
        arcadditionalheight = 8 #arc reaches over height
        angle = math.asin((width/2)/arcradius)
        
        ctx.set_line_width(3.5)
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.move_to(imgwdth/2-width/2,imghght/2+height/2+arcadditionalheight/2)
        #ctx.line_to(imgwdth/2-width/2,imghght/2-height/2+arcadditionalheight/2)
        ctx.arc(imgwdth/2,arcradius+imghght/2-height/2-arcadditionalheight/2,arcradius,3/2*math.pi-angle,3/2*math.pi+angle)
        ctx.line_to(imgwdth/2+width/2,imghght/2+height/2+arcadditionalheight/2)
        ctx.line_to(imgwdth/2-width/2,imghght/2+height/2+arcadditionalheight/2)
        ctx.stroke()
        
        ctx.set_line_width(4.0)
        ctx.set_source_rgba(
            0.65,
            0.65,
            0.65,
            colour.alpha,
        )
        ctx.move_to(imgwdth/2-width/2,imghght/2+height/2+arcadditionalheight/2)
        #ctx.line_to(imgwdth/2-width/2,imghght/2-height/2+arcadditionalheight/2)
        ctx.arc(imgwdth/2,arcradius+imghght/2-height/2-arcadditionalheight/2,arcradius,3/2*math.pi-angle,3/2*math.pi+angle)
        ctx.line_to(imgwdth/2+width/2,imghght/2+height/2+arcadditionalheight/2)
        ctx.line_to(imgwdth/2-width/2,imghght/2+height/2+arcadditionalheight/2)
        ctx.fill()

        ctx.set_line_width(6.5)
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.move_to(imgwdth/2-2*width/5,imghght/2-(height+arcadditionalheight)/8)
        ctx.line_to(imgwdth/2+2*width/5,imghght/2-(height+arcadditionalheight)/8)
        ctx.stroke()
        
        ctx.set_line_width(6.0)
        ctx.set_source_rgba(
            colour.red,
            colour.green,
            colour.blue,
            colour.alpha
        )
        ctx.move_to(imgwdth/2-2*width/5,imghght/2-(height+arcadditionalheight)/8)
        ctx.line_to(imgwdth/2+2*width/5,imghght/2-(height+arcadditionalheight)/8)
        ctx.stroke()
    
        ctx.save()
        return surface
        
    def _draw_text(self, colour, fontsize, text):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 48, 48)
        ctx = cairo.Context(surface)

        ctx.set_line_width(4.0)
        radius = 4
        
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.set_font_size(fontsize)
        ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD) 
        extents = ctx.text_extents(text)
        x = 24-(extents.width/2 + extents.x_bearing);
        y = 24-(extents.height/2 + extents.y_bearing);
        ctx.move_to(x, y) 
        ctx.text_path(text)
        ctx.set_line_width(2)
        ctx.stroke()
        
        ctx.set_source_rgba(
            colour.red,
            colour.green,
            colour.blue,
            colour.alpha
        )
        ctx.set_font_size(fontsize)
        ctx.select_font_face("Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD) 
        extents = ctx.text_extents(text)
        x = 24-(extents.width/2 + extents.x_bearing);
        y = 24-(extents.height/2 + extents.y_bearing);
        ctx.move_to(x, y) 
        ctx.text_path(text)
        ctx.set_line_width(2)
        ctx.fill()
        
        
        #ctx.set_source_surface(surface, -24, -24)
        ctx.save()
        return surface

    def _draw_cut_ring(self, colour, radius):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 48, 48)
        ctx = cairo.Context(surface)
        
        number_of_segments = 7

        pathlength=2*radius*math.pi
        
        ctx.set_line_width(6.2)
        ctx.set_dash([1.6*pathlength/38.5, 1.9*pathlength/38.5], 1)
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.arc(24,24, radius, 0, 2*math.pi)
        ctx.stroke()
                
        ctx.set_line_width(6.0)
        ctx.set_dash([1.4*pathlength/38.5, 2.1*pathlength/38.5], 1)
        ctx.set_source_rgba(
            colour.red,
            colour.green,
            colour.blue,
            colour.alpha
        )
        ctx.arc(24,24, radius, 0, 2*math.pi)
        ctx.stroke()
        #ctx.set_source_surface(surface, -24, -24)
        ctx.save()
        return surface

    def _draw_square(self, colour):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 16)
        ctx = cairo.Context(surface)
        
        ctx.set_line_width(3.5)
        ctx.set_source_rgba(
            0,
            0,
            0,
            colour.alpha,
        )
        ctx.move_to(1,1)
        ctx.line_to(1,15)
        ctx.line_to(15,15)
        ctx.line_to(15,1)
        ctx.line_to(1,1)
        ctx.fill()
        
        ctx.set_line_width(4.0)
        ctx.set_source_rgba(
            colour.red,
            colour.green,
            colour.blue,
            colour.alpha
        )
        ctx.move_to(1,1)
        ctx.line_to(1,15)
        ctx.line_to(15,15)
        ctx.line_to(15,1)
        ctx.line_to(1,1)
        ctx.fill()

        #ctx.set_source_surface(surface, -24, -24)
        ctx.save()
        return surface



