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

# -------------------------------------------------------------------------
#
# GTK Modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk


# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
import os


# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.plug.report import Report, MenuReportOptions
from gramps.gen.lib import EventType
from gramps.gui.dialog import ErrorDialog
from gramps.gen.plug.menu import (
    EnumeratedListOption, PersonOption, DestinationOption, StringOption,
    NumberOption, BooleanOption)
from gramps.gen.plug.menu import Option as PlugOption
from gramps.gen.filters import GenericFilterFactory, rules, CustomFilters
from gramps.gen.plug.docgen import ParagraphStyle
from gramps.gen.plug import BasePluginManager
from gramps.gen.utils.place import conv_lat_lon
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


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

        filter_list2 = [
            (0, _("OpenStreetMap")),
            (1, _("Stamen Terrain")),
            (2, _("Stamen Toner")),
            (3, _("Stamen Watercolor")),
            (4, _("CartoDB Positron")),
            (5, _("CartoDB DarkMatter"))]
        tiles = EnumeratedListOption(_("Map tiles"), 0)
        tiles.set_items(filter_list2)
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

        # -------------------
        # LIMITS options tab
        # -------------------
        self.enable_limits = BooleanOption(_("Enable map limits"), False)
        self.enable_limits.set_help(
            _("Enabling map limits forces the user to stay in a predefined part"
              " of the map."))
        menu.add_option(_("Limits"), "enable_limits", self.enable_limits)
        self.enable_limits.connect('value-changed', self.update_limit_options)

        self.min_zoom = NumberOption(_("Min. zoom"), 1, 1, 18)
        self.min_zoom.set_help(_("Set minimal zoom value\nDefault: 1"))
        menu.add_option(_("Limits"), "min_zoom", self.min_zoom)

        self.max_zoom = NumberOption(_("Max. zoom"), 18, 1, 18)
        self.max_zoom.set_help(_("Set maximum zoom value.\nDefault: 18"))
        menu.add_option(_("Limits"), "max_zoom", self.max_zoom)

        self.lat1 = StringOption(_("Upper left corner latitude"), "")
        self.lat1.set_help(
            _("Set latitude for upper left corner map limit."))
        menu.add_option(_("Limits"), "lat1", self.lat1)

        self.lon1 = StringOption(_("Upper left corner longitude"), "")
        self.lon1.set_help(
            _("Set longitude for upper left corner map limit."))
        menu.add_option(_("Limits"), "lon1", self.lon1)

        self.lat2 = StringOption(_("Lower right corner latitude"), "")
        self.lat2.set_help(
            _("Set latitude for lower right corner map limit."))
        menu.add_option(_("Limits"), "lat2", self.lat2)

        self.lon2 = StringOption(_("Lower right corner longitude"), "")
        self.lon2.set_help(
            _("Set longitude for lower right corner map limit."))
        menu.add_option(_("Limits"), "lon2", self.lon2)

        self.render_border = BooleanOption(
            _("Render custom map limit border"), False)
        self.render_border.set_help(
            _("Enabling will render the map limit border"))
        menu.add_option(_("Limits"), "render_border", self.render_border)

    def update_limit_options(self):
        """Update menu options for limit option tab."""
        self.min_zoom.set_available(False)
        self.max_zoom.set_available(False)
        self.lat1.set_available(False)
        self.lon1.set_available(False)
        self.lat2.set_available(False)
        self.lon2.set_available(False)
        self.render_border.set_available(False)
        value = self.enable_limits.get_value()
        if value:
            self.min_zoom.set_available(True)
            self.max_zoom.set_available(True)
            self.lat1.set_available(True)
            self.lon1.set_available(True)
            self.lat2.set_available(True)
            self.lon2.set_available(True)
            self.render_border.set_available(True)

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
        menu.filter_list = [(0, _("Entire Database")),
                            (1, _("Ancestors of <selected person>")),
                            (2, _("Descendants of <selected person>")),
                            (3, _("Single Person"))]

        for item in enumerate([x.get_name() for x in custom], start=4):
            menu.filter_list.append(item)

    @staticmethod
    def make_default_style(default_style):
        """Define the default styling."""
        para = ParagraphStyle()
        default_style.add_paragraph_style("Default", para)


# ------------------------------------------------------------------------
#
# Report Class
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
        self.place_dict = dict()
        self.filename = False
        if not self.check_file_path_and_name():
            return  # stop if incorrect path or filename

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
        if index == 0:
            fltr.add_rule(rules.person.Everyone([pers_id, True]))
        elif index == 1:
            fltr.add_rule(rules.person.IsAncestorOf([pers_id, True]))
        elif index == 2:
            fltr.add_rule(rules.person.IsDescendantOf([pers_id, True]))
        elif index == 3:
            fltr.add_rule(rules.person.HasIdOf([pers_id, True]))
        else:
            for num, item in list(custom):
                if num == index:
                    fltr = item
        return fltr

    def get_events(self, person_h):
        """Get all events of a person."""
        person = self.db.get_person_from_handle(person_h)
        event_list = []
        for event_ref in person.get_event_ref_list():
            event = self.db.get_event_from_handle(event_ref.ref)
            if event.type.value in self.opt['multi_events']:
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
        coords = conv_lat_lon(place.get_latitude(), place.get_longitude(), "D.D8")
        lat = coords[0]
        lon = coords[1]
        name = place.get_gramps_id()
        # self.place_dict example:
        #     {place_id(str): [lat(str), lon(str), num(int)]
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
            return  # stop if incorrect path or filename

        # define start position values (=Europe)
        # overwrite later with custom start values if enabled
        start_lat = 50.0
        start_lon = 10.0
        start_zoom = 5

        # check if lat, lng are convertable to floats and within range
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
                return  # stop if lat/lng aren't convertabe to floats

        # check zoom and limit values
        if self.opt["enable_limits"]:
            valid_limits, limit_args = self.check_limit_values()
            if not valid_limits:
                return  # stop if limit values are invalid
            start_zoom = limit_args["start_zoom"]
            min_zoom = limit_args["min_zoom"]
            max_zoom = limit_args["max_zoom"]
            bounds = [
                [limit_args["lat1"], limit_args["lon1"]],
                [limit_args["lat2"], limit_args["lon2"]]]

        # Leaflet and folium header html
        lst = list()
        res_path = os.path.dirname(__file__) + "/template/"
        with open(res_path + "map_header.txt", "r", encoding="utf-8") as file:
            for line in file:
                lst.append(line)

        # Add the map + map options
        lst.append("    var GrampsHeatmap = L.map(\n")
        lst.append("        'GrampsHeatmap',\n")
        lst.append("        {\n")
        lst.append("            center: [%f, %f],\n" % (start_lat, start_lon))
        lst.append("            crs: L.CRS.EPSG3857,\n")
        lst.append("            zoom: %d,\n" % start_zoom)
        if self.opt["enable_limits"]:
            lst.append("            minZoom: %d,\n" % min_zoom)
            lst.append("            maxZoom: %d,\n" % max_zoom)
            lst.append("            maxBounds: %s,\n" % bounds)
        lst.append("            zoomControl: true,\n")
        lst.append("            preferCanvas: false,\n")
        lst.append("        }\n")
        lst.append("    );\n")

        # render map limit if enabled
        if self.opt["enable_limits"] and self.opt["render_border"]:
            lst.append(" L.rectangle(%s).addTo(GrampsHeatmap);\n" %
                       str(bounds))

        # Add map tiles and attribution
        tiles = "tiles" + str(self.opt["tiles"]) + ".txt"
        with open(res_path + tiles, "r", encoding="utf-8") as file:
            for line in file:
                lst.append(line)

        # Add the place data from user's Gramps database as a heatmap layer
        lst.append("    var heat_map_data ")
        lst.append("= L.heatLayer(")
        lst.append("[")
        for key, value in self.place_dict.items():
            try:
                lat = float(value[0])
                lon = float(value[1])
                val = float(value[2])
                lst.append("[%f, %f, %f]," % (lat, lon, val))
            except ValueError:
                # if place coords can't be converted to float
                print(_("[INFO]: Place '%s' was ignored because of"
                        " unsupported coordinate values." % key))
        lst.append("],\n")

        # Add heatmap Layer options
        radius = self.opt["radius"]
        lst.append('        {"blur": 15, "max": 43.0, "maxZoom": 18,')
        lst.append(' "minOpacity": 0.5, "radius": %s}\n' % radius)
        lst.append("        ).addTo(GrampsHeatmap);\n")
        lst.append("</script>")

        # Save the generated heatmap report file
        with open(self.filename, "w", encoding="utf-8") as file:
            for item in lst:
                file.write(item)

    def check_limit_values(self):
        """Check if limit values are valid for report generation."""
        args = {
            "start_zoom": None,
            "min_zoom": None,
            "max_zoom": None,
            "lat1": None,
            "lon1": None,
            "lat2": None,
            "lon2": None,
        }
        # make sure user entered zoom levels do not exceed min/max values
        # inconclusive zoom raises a mesg, but doesn'o't stop report generation
        start_zoom = self.opt["start_zoom"]
        min_zoom = self.opt["min_zoom"]
        max_zoom = self.opt["max_zoom"]
        zoom_error = False
        if min_zoom > max_zoom:
            args["min_zoom"] = max_zoom
            zoom_error = True
        if max_zoom < min_zoom:
            args["max_zoom"] = min_zoom
            zoom_error = True
        if start_zoom < min_zoom:
            args["start_zoom"] = min_zoom
            zoom_error = True
        if start_zoom > max_zoom:
            args["start_zoom"] = max_zoom
            zoom_error = True
        if zoom_error:
            txt = _(
                "Your zoom settings were inconclusive and therefore "
                "changed for this report generation.")
            ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)

        # Set empty dict values
        if not args["min_zoom"]:
            args["min_zoom"] = min_zoom
        if not args["max_zoom"]:
            args["max_zoom"] = max_zoom
        if not args["start_zoom"]:
            args["start_zoom"] = start_zoom

        # check if limt lat, lng are convertable to floats and within range
        try:
            lat1 = float(self.opt["lat1"])
            lon1 = float(self.opt["lon1"])
            lat2 = float(self.opt["lat2"])
            lon2 = float(self.opt["lon2"])

            if lat1 < -90 or lat1 > 90:
                raise ValueError
            if lat2 < -90 or lat2 > 90:
                raise ValueError
            if lon1 < -180 or lon1 > 180:
                raise ValueError
            if lon2 < -180 or lon2 > 180:
                raise ValueError

            args["lat1"] = lat1
            args["lon1"] = lon1
            args["lat2"] = lat2
            args["lon2"] = lon2

        except ValueError:
            txt = _(
                "Report generation failed.\n"
                "Please check the values for limits latitude and longitude."
                "\nLatitude: -90 to 90\nLongitude: -180 to 180")
            ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)
            return False, None  # Not convertabe to floats or outside range
        return True, args  # convertable to floats and within range


# ------------------------------------------------------------------------
#
# MultiSelectListBoxOption Class
#
# ------------------------------------------------------------------------
class MultiSelectListBoxOption(PlugOption):
    """Extending gramps.gen.plug.menu._option.Option"""

    def __init__(self, label, value):
        PlugOption.__init__(self, label, value)


# ------------------------------------------------------------------------
#
# GuiScrollMultiSelect Class
#
# ------------------------------------------------------------------------
class GuiScrollMultiSelect(Gtk.ScrolledWindow):
    """Extending Gtk.ScrolledWindow."""

    def __init__(self, option, dbstate, uistate, track, override=False):
        Gtk.ScrolledWindow.__init__(self)
        self.__option = option
        self.list_box = MultiSelectListBox()
        self.list_box.connect('selected-rows-changed', self.value_changed)
        self.add(self.list_box)
        self.set_min_content_height(300)
        self.load_last_rows()

    def load_last_rows(self):
        for event_type in self.__option.get_value():
            for row in self.list_box.rows:
                if int(row.event_type) == int(event_type):
                    self.list_box.select_row(row)

    def value_changed(self, obj):
        values = []
        for row in self.list_box.get_selected_rows():
            values.append(row.event_type)
        self.__option.set_value(values)

# ------------------------------------------------------------------------
#
# MultiSelectListBox Class
#
# ------------------------------------------------------------------------


class MultiSelectListBox(Gtk.ListBox):
    """Extending Gtk.ListBox."""

    def __init__(self):
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode(3))
        self.set_activate_on_single_click(False)
        self.__row_counter = 0
        self.rows = []
        for event_type in EventType._DATAMAP:
            self.add_row(event_type[0])

    def add_row(self, event_type):
        row = EventTypeRow(event_type)
        self.insert(row, self.__row_counter)
        self.rows.append(row)
        self.__row_counter += 1


# ------------------------------------------------------------------------
#
# EventTypeRow Class
#
# ------------------------------------------------------------------------
class EventTypeRow(Gtk.ListBoxRow):
    """Extending Gtk.ListBoxRow."""

    def __init__(self, event_type):
        Gtk.ListBoxRow.__init__(self)
        self.label = ""
        for entry in EventType._DATAMAP:
            if entry[0] == event_type:
                self.label = entry[1]
        self.event_type = event_type
        self.add(Gtk.Label(self.label))
