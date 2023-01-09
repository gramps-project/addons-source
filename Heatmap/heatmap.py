#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2023    Matthias Kemmer
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
"""Heatmap web report."""


from multi_select import MultiSelectOption, HeatmapScrolled
from utils import MapTiles, HeatmapPlace
import os
from string import Template

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.lib import EventType
from gramps.gen.plug.report import Report, MenuReportOptions
from gramps.gen.plug.menu import (
    EnumeratedListOption, PersonOption, FilterOption,
    DestinationOption, StringOption, NumberOption, BooleanOption)
from gramps.gen.plug.docgen import ParagraphStyle
from gramps.gen.plug import BasePluginManager
from gramps.gui.dialog import ErrorDialog
from gramps.gen.plug.report import utils
from gramps.gen.plug.report import stdoptions
from gramps.gen.utils.place import conv_lat_lon
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ------------------------------------------------------------------------
#
# Heatmap Options Class
#
# ------------------------------------------------------------------------
class ReportOptions(MenuReportOptions):
    """Heatmap options class."""

    def __init__(self, name, dbase):
        self.db = dbase
        pmgr = BasePluginManager.get_instance()
        pmgr.register_option(MultiSelectOption, HeatmapScrolled)
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """Create menu options."""

        # -------------------
        # GENERAL options tab
        # -------------------
        self.filter = FilterOption(_("Filter"), 0)
        menu.add_option(_("General"), "fltr", self.filter)
        self.filter.connect('value-changed', self.filter_changed)

        self.pid = PersonOption(_("Filter Person"))
        menu.add_option(_("General"), "pid", self.pid)
        self.pid.connect('value-changed', self.update_filters)

        self.nf = stdoptions.add_name_format_option(menu, _("General"))
        self.nf.connect('value-changed', self.update_filters)
        self.update_filters()

        map_tiles_list = [(x[0], x[1]) for x in MapTiles._DATAMAP]
        tiles = EnumeratedListOption(_("Map tiles"), 0)
        tiles.set_items(map_tiles_list)
        menu.add_option(_("General"), "tiles", tiles)

        radius = NumberOption(_("Point size"), 15, 1, 50)
        radius.set_help(_("Set the size of the heatmap points.\nDefault: 15"))
        menu.add_option(_("General"), "radius", radius)

        path = DestinationOption(_("File path"), "")
        path.set_directory_entry(True)
        menu.add_option(_("General"), "path", path)

        txt = _(
            "For the file name only english letters A-Z, a-z and "
            "numbers 0-9 as well as the characters space, underline and "
            "hypen are allowed. The file name also has to "
            "start and end with an alphanumeric character."
            "The file extention '.html' is added by the report.")
        file_name = StringOption(_("File name"), "")
        file_name.set_help(txt)
        menu.add_option(_("General"), "name", file_name)

        # -------------------
        # EVENTS options tab
        # -------------------
        selected_rows = MultiSelectOption("", [])
        menu.add_option(_("Events"), "selected_rows", selected_rows)

        # -------------------
        # ADVANCED options tab
        # -------------------
        self.enable_start = BooleanOption(
            _("Enable custom start position"), False)
        self.enable_start.set_help(
            _("Enabling will force the map open at your custom "
              "start position and zoom."))
        menu.add_option(_("Advanced"), "enable_start", self.enable_start)
        self.enable_start.connect('value-changed', self.update_start_options)

        self.start_lat = NumberOption(_("Start latitude"), 50, -90, 90)
        self.start_lat.set_help(
            _("Set custom start position latitude\nDefault: 50.0"))
        menu.add_option(_("Advanced"), "start_lat", self.start_lat)

        self.start_lon = NumberOption(_("Start longitude"), 10, -180, 180)
        self.start_lon.set_help(
            _("Set custom start position longitude\nDefault: 10.0"))
        menu.add_option(_("Advanced"), "start_lon", self.start_lon)

        self.start_zoom = NumberOption(_("Start zoom"), 5, 1, 18)
        self.start_zoom.set_help(
            _("Set the value for the starting zoom\nDefault: 5"))
        menu.add_option(_("Advanced"), "start_zoom", self.start_zoom)

    def update_start_options(self):
        """Update menu options for start option tab."""
        self.start_zoom.set_available(False)
        self.start_lat.set_available(False)
        self.start_lon.set_available(False)
        if self.enable_start.get_value():
            self.start_zoom.set_available(True)
            self.start_lat.set_available(True)
            self.start_lon.set_available(True)

    def update_filters(self):
        """Update the filter list based on selected person"""
        gid = self.pid.get_value()
        person = self.db.get_person_from_gramps_id(gid)
        nfv = self.nf.get_value()
        filter_list = utils.get_person_filters(
            person, include_single=False, name_format=nfv)
        self.filter.set_filters(filter_list)

    def filter_changed(self):
        """Handle filter change."""
        filter_value = self.filter.get_value()
        if filter_value == 1:
            self.pid.set_available(False)
        else:
            self.pid.set_available(True)

    @staticmethod
    def make_default_style(default_style):
        """Define the default styling."""
        para = ParagraphStyle()
        default_style.add_paragraph_style("Default", para)


# ------------------------------------------------------------------------
#
# Heatmap Report Class
#
# ------------------------------------------------------------------------
class ReportClass(Report):
    """Heatmap report class."""

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        self.user = user
        self.options = options
        self.opt = options.options_dict
        self.db = database
        self.places = list()
        self.filename = False
        if not self.check_file_path_and_name():
            return  # Stop if incorrect path or filename

        iter_persons = self.db.iter_person_handles()
        filter_option = options.menu.get_option_by_name('fltr')
        self.fltr = filter_option.get_filter()

        if not self.fltr:
            return # Stop if no filter found

        person_handles = self.fltr.apply(self.db, iter_persons, user=self.user)
        for person_h in person_handles:
            events = self.get_events(person_h)
            if len(events) > 0 and any(events):
                self.get_place(events)

    def check_file_path_and_name(self):
        """Check if file path exists and file name is alphanumeric."""
        path = self.opt["path"]
        name = self.opt["name"]
        txt = _("Path does not exist.")
        txt2 = _("Invalid filename.")

        # Check if path exists
        if not os.path.exists(path):
            ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)
            return False

        # Check if file name is alphanumeric
        if name.isalnum():
            self.filename = path + "/" + name + ".html"
            return True

        # Check if a non-alphanumeric file name is valid
        chars = [x for x in name if not x.isalnum()]
        for char in chars:
            if char not in ["_", "-", " "]:
                ErrorDialog(_("INFO"), txt2, parent=self.user.uistate.window)
                return False
        if name != "" and name[0].isalnum() and name[-1].isalnum():
            self.filename = path + "/" + name + ".html"
            return True

    def get_events(self, person_h):
        """Get all relevant events of a person."""
        selected_names = []
        default_types = [name[1] for name in EventType._DATAMAP]
        custom_types = [name for name in self.db.get_event_types()]
        event_types = sorted([*default_types, *custom_types])
        for index, name in enumerate(event_types):
            if str(index) in self.opt['selected_rows']:
                selected_names.append(name)

        # Use 'event type names' for comparison
        person = self.db.get_person_from_handle(person_h)
        event_list = []
        for event_ref in person.get_event_ref_list():
            event = self.db.get_event_from_handle(event_ref.ref)
            if event.type.value != EventType.CUSTOM:
                for item in EventType._DATAMAP:
                    if item[0] == event.type.value and item[1] in selected_names:
                        event_list.append(event_ref)
            if event.type.value == EventType.CUSTOM:
                if event.type.serialize()[1] in selected_names:
                    event_list.append(event_ref)
        return event_list

    def get_place(self, events):
        """Get an event places and call check_place."""
        for event_ref in events:
            event = self.db.get_event_from_handle(event_ref.ref)
            handle = event.get_place_handle()
            if handle:
                place = self.db.get_place_from_handle(handle)
                self.check_place(place)

    def check_place(self, place):
        """Check the place for latitude and longitude."""
        lat, lon = conv_lat_lon(
            place.get_latitude(), place.get_longitude(), "D.D8")
        name = place.get_gramps_id()

        if lat and lon:
            for place in self.places:
                if name == place.name:
                    place.count += 1
            self.places.append(HeatmapPlace(name, lat, lon, 1))
        else:
            for place_ref in place.get_placeref_list():
                place_new = self.db.get_place_from_handle(place_ref.ref)
                self.check_place(place_new)

    def write_report(self):
        """Write the text report."""
        if not self.filename:
            return  # Stop if incorrect path or filename

        # Define start position values (=Europe)
        # If enabled, overwrite with custom start values
        start_lat = 50.0
        start_lon = 10.0
        start_zoom = 5
        if self.opt["enable_start"]:
            start_lat = self.opt["start_lat"]
            start_lon = self.opt["start_lon"]
            start_zoom = self.opt["start_zoom"]

        # Load HTML template file
        source_code = ""
        res_path = os.path.dirname(__file__)
        with open(res_path + "/template.html", "r", encoding="utf-8") as file:
            for line in file:
                source_code += line

        # Set OpenStreetMap as default
        map_tiles_url = "'%s'" % MapTiles._DATAMAP[0][2]
        map_tiles_attribution = "'%s'" % MapTiles._DATAMAP[0][3]

        # Set map tiles url and attribution
        for entry in MapTiles._DATAMAP:
            if entry[0] == self.opt["tiles"]:
                map_tiles_url = "'%s'" % entry[2]
                map_tiles_attribution = "'%s'" % entry[3]

        # Collect heatmap coordinates
        heatmap_data = [place.to_list() for place in self.places]

        # Substitute the HTML template source code with heatmap report data
        radius = self.opt["radius"]
        source_code = Template(source_code)
        source_code = source_code.safe_substitute(
            start_lat=start_lat,
            start_lon=start_lon,
            start_zoom=start_zoom,
            map_tiles_url=map_tiles_url,
            map_tiles_attribution=map_tiles_attribution,
            heatmap_data=heatmap_data,
            heatmap_radius=radius
        )

        # Save the generated heatmap report HTML file
        with open(self.filename, "w", encoding="utf-8") as file:
            file.write(source_code)
