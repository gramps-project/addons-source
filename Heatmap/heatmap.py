#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021    Matthias Kemmer
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
"""Create a heatmap web report."""


# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
from utils import PersonFilterEnum, MapTiles
from multi_select_listbox import MultiSelectListBoxOption, GuiScrollMultiSelect
import os
from string import Template

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.lib import EventType  # type: ignore
from gramps.gen.plug.report import Report, MenuReportOptions   # type: ignore
from gramps.gen.plug.menu import (  # type: ignore
    EnumeratedListOption, PersonOption,
    DestinationOption, StringOption, NumberOption, BooleanOption)
from gramps.gen.filters import CustomFilters, GenericFilterFactory, rules  # type: ignore
from gramps.gen.plug.docgen import ParagraphStyle  # type: ignore
from gramps.gen.plug import BasePluginManager  # type: ignore
from gramps.gui.dialog import ErrorDialog  # type: ignore
from gramps.gen.utils.place import conv_lat_lon  # type: ignore
from gramps.gen.const import GRAMPS_LOCALE as glocale  # type: ignore
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ------------------------------------------------------------------------
#
# Heatmap modules
#
# ------------------------------------------------------------------------

# ------------------------------------------------------------------------
#
# Report Options
#
# ------------------------------------------------------------------------

class ReportOptions(MenuReportOptions):
    """Heatmap report options."""

    def __init__(self, name, dbase):
        pmgr = BasePluginManager.get_instance()
        pmgr.register_option(MultiSelectListBoxOption, GuiScrollMultiSelect)
        self.db = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """Create menu options."""

        # -------------------
        # GENERAL options tab
        # -------------------
        self.get_person_filters(menu)
        fltr = EnumeratedListOption(_("Filter"), 0)
        fltr.set_items(menu.filter_list)
        menu.add_option(_("General"), "fltr", fltr)

        pers_id = PersonOption(_("Person"))
        menu.add_option(_("General"), "pers_id", pers_id)

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

        txt = _("For the file name only english letters A-Z, a-z and "
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
        multi_events = MultiSelectListBoxOption(_("Select Events"), [])
        menu.add_option(_("Events"), "multi_events", multi_events)

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

        self.start_lat = StringOption(_("Start latitude"), "50.0")
        self.start_lat.set_help(
            _("Set custom start position latitude\nDefault: 50.0"))
        menu.add_option(_("Advanced"), "start_lat", self.start_lat)

        self.start_lon = StringOption(_("Start longitude"), "10.0")
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
        value = self.enable_start.get_value()
        if value:
            self.start_zoom.set_available(True)
            self.start_lat.set_available(True)
            self.start_lon.set_available(True)

    @staticmethod
    def get_person_filters(menu):
        """Get menu option filter list of custon and generic filters."""
        custom = CustomFilters.get_filters("Person")
        menu.filter_list = [
            (PersonFilterEnum.ALL, _("Entire Database")),
            (PersonFilterEnum.ANCESTORS, _("Ancestors of <selected person>")),
            (PersonFilterEnum.DESCENDANTS, _("Descendants of <selected person>")),
            (PersonFilterEnum.SINGLE, _("Single Person"))]

        for item in enumerate([x.get_name() for x in custom], start=4):
            menu.filter_list.append(item)

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

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        self.user = user
        self.options = options
        self.opt = options.options_dict
        self.db = database
        self.place_dict = dict()
        self.filename = False
        if not self.check_file_path_and_name():
            return  # Stop if incorrect path or filename

        iter_persons = self.db.iter_person_handles()
        fltr = self.get_filter(self.opt["fltr"], self.opt["pers_id"])
        person_handles = fltr.apply(self.db, iter_persons)
        for person_h in person_handles:
            events = self.get_events(person_h)
            if len(events) > 0 and any(events):
                self.get_place(events)

    def check_file_path_and_name(self):
        """Check if file path exists and file name is alphanumeric."""
        path = self.opt["path"]
        name = self.opt["name"]
        txt = _("Invalid filename.")
        txt2 = _("Path does not exist.")

        if os.path.exists(path):
            if name.isalnum():
                self.filename = path + "/" + name + ".html"
                return True
            chars = [x for x in name if not x.isalnum()]
            for char in chars:
                if char not in ["_", "-", " "]:
                    ErrorDialog(_("INFO"), txt,
                                parent=self.user.uistate.window)
                    return False
            if name != "" and name[0].isalnum() and name[-1].isalnum():
                self.filename = path + "/" + name + ".html"
                return True
            ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)
            return False
        ErrorDialog(_("INFO"), txt2, parent=self.user.uistate.window)
        return False

    @staticmethod
    def get_filter(index, pers_id):
        """Create a filter."""
        fltr = GenericFilterFactory("Person")()
        custom = enumerate(CustomFilters.get_filters("Person"), start=2)
        if index == PersonFilterEnum.ALL:
            fltr.add_rule(rules.person.Everyone([pers_id, True]))
        elif index == PersonFilterEnum.ANCESTORS:
            fltr.add_rule(rules.person.IsAncestorOf([pers_id, True]))
        elif index == PersonFilterEnum.DESCENDANTS:
            fltr.add_rule(rules.person.IsDescendantOf([pers_id, True]))
        elif index == PersonFilterEnum.SINGLE:
            fltr.add_rule(rules.person.HasIdOf([pers_id, True]))
        else:
            for num, item in list(custom):
                if num == index:
                    fltr = item
        return fltr

    def get_events(self, person_h):
        """Get all relevant events of a person."""
        # References to selected rows
        event_types = []
        selected_names = []
        for event_type_tuple in EventType._DATAMAP:
            event_type_name = event_type_tuple[1]
            event_types.append(event_type_name)
        for event_type in self.db.get_event_types():
            event_types.append(event_type)
        event_types = enumerate(sorted(event_types))
        for item in event_types:
            if item[0] in self.opt['multi_events']:
                selected_names.append(item[1])

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
        """Get an event place and add it to the event dict."""
        for event_ref in events:
            event = self.db.get_event_from_handle(event_ref.ref)
            handle = event.get_place_handle()
            if handle:
                place = self.db.get_place_from_handle(handle)
                self.check_place(place)

    def check_place(self, place):
        """Check the place for latitude and longitude."""
        coords = conv_lat_lon(place.get_latitude(),
                              place.get_longitude(), "D.D8")
        lat = coords[0]
        lon = coords[1]
        name = place.get_gramps_id()
        # Example for self.place_dict:
        #     {place_id (str): [lat: str, lon: str, num: int]}
        if lat and lon:
            if name in self.place_dict.keys():
                self.place_dict[name][2] += 1
            else:
                self.place_dict[name] = [lat, lon, 1]
        else:
            ref_list = place.get_placeref_list()
            for place_ref in ref_list:
                place_new = self.db.get_place_from_handle(place_ref.ref)
                self.check_place(place_new)

    def write_report(self):
        """Write the text report."""
        if not self.filename:
            return  # Stop if incorrect path or filename

        # Define start position values (=Europe)
        # Overwrite later with custom start values if enabled
        start_lat = 50.0
        start_lon = 10.0
        start_zoom = 5

        # Check if lat, lng are convertable to floats and within range
        if self.opt["enable_start"]:
            try:
                start_lat = float(self.opt["start_lat"])
                start_lon = float(self.opt["start_lon"])
                if start_lat < -90 or start_lat > 90:
                    raise ValueError
                if start_lon < -180 or start_lon > 180:
                    raise ValueError
            except ValueError:
                txt = _(
                    "Report generation failed.\n"
                    "Please check the values for start latitude and longitude."
                    "\nLatitude: -90 to 90\nLongitude: -180 to 180")
                ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)
                return  # Stop if lat/lng aren't convertabe to floats

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

        # Collect heatmap data
        heatmap_data = list()
        for key, value in self.place_dict.items():
            try:
                lat = float(value[0])
                lon = float(value[1])
                val = float(value[2])
                heatmap_data.append([lat, lon, val])
            except ValueError:
                # if place coords can't be converted to float
                print(_("[INFO]: Place '%s' was ignored because of"
                        " unsupported coordinate values." % key))

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
