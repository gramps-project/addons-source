#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020    Matthias Kemmer
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
import os


# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.plug.report import Report, MenuReportOptions
from gramps.gui.dialog import ErrorDialog
from gramps.gen.plug.menu import (
    EnumeratedListOption, PersonOption, DestinationOption, StringOption,
    NumberOption)
from gramps.gen.filters import GenericFilterFactory, rules, CustomFilters
from gramps.gen.plug.docgen import ParagraphStyle
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
        self.db = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """Create menu options."""
        self.get_person_filters(menu)
        fltr = EnumeratedListOption(_("Filter"), 0)
        fltr.set_items(menu.filter_list)
        menu.add_option(_("Options"), "fltr", fltr)

        pers_id = PersonOption(_("Person"))
        menu.add_option(_("Options"), "pers_id", pers_id)

        filter_list2 = [
            (0, _("OpenStreetMap")),
            (1, _("Stamen Terrain")),
            (2, _("Stamen Toner")),
            (3, _("Stamen Watercolor")),
            (4, _("CartoDB Positron")),
            (5, _("CartoDB DarkMatter"))]
        tiles = EnumeratedListOption(_("Map tiles"), 0)
        tiles.set_items(filter_list2)
        menu.add_option(_("Options"), "tiles", tiles)

        path = DestinationOption(_("File path"), "")
        path.set_directory_entry(True)
        menu.add_option(_("Options"), "path", path)

        txt = _("For the file name only english letters A-Z, a-z and "
                "numbers 0-9 as well as the characters space, underline and "
                "hypen are allowed. The file name also has to "
                "start and end with an alphanumeric character."
                "The file extention '.html' is added by the report.")
        file_name = StringOption(_("File name"), "")
        file_name.set_help(txt)
        menu.add_option(_("Options"), "name", file_name)

        start_lat = StringOption("Latitude", "48.0")
        start_lat.set_help(
            _("Set the starting latitude value\nDefault: 48.0"))
        menu.add_option(_("Advanced options"), "start_lat", start_lat)

        start_lon = StringOption("Longitude", "5.0")
        start_lon.set_help(
            _("Set the starting longitude value\nDefault: 5.0"))
        menu.add_option(_("Advanced options"), "start_lon", start_lon)

        start_zoom = NumberOption("Start zoom", 4, 1, 18)
        start_zoom.set_help(
            _("Set the value for the starting zoom\nDefault: 4"))
        menu.add_option(_("Advanced options"), "start_zoom", start_zoom)

        min_zoom = NumberOption("Min. zoom", 1, 1, 18)
        min_zoom.set_help(_("Set minimal zoom value\nDefault: 1"))
        menu.add_option(_("Advanced options"), "min_zoom", min_zoom)

        max_zoom = NumberOption("Max. zoom", 18, 1, 18)
        max_zoom.set_help(_("Set maximum zoom value.\nDefault: 18"))
        menu.add_option(_("Advanced options"), "max_zoom", max_zoom)

        radius = NumberOption("Radius", 15, 1, 50)
        radius.set_help(_("Set the radius of the points.\nDefault: 15"))
        menu.add_option(_("Advanced options"), "radius", radius)

    @staticmethod
    def get_person_filters(menu):
        """Get menu option filter list of custon and generic filters."""
        custom = CustomFilters.get_filters("Person")
        menu.filter_list = [(0, _("Ancestors of <selected person>")),
                            (1, _("Descendants of <selected person>"))]

        for item in enumerate([x.get_name() for x in custom], start=2):
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
            fltr.add_rule(rules.person.IsAncestorOf([pers_id, True]))
        elif index == 1:
            fltr.add_rule(rules.person.IsDescendantOf([pers_id, True]))
        else:
            for num, item in list(custom):
                if num == index:
                    fltr = item
        return fltr

    def get_events(self, person_h):
        """Get all events of a person."""
        person = self.db.get_person_from_handle(person_h)
        return person.get_event_ref_list()

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
        lat = place.get_latitude()
        lon = place.get_longitude()
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

        # check if lat, lng are convertable to floats
        try:
            start_lat = float(self.opt["start_lat"])
            start_lon = float(self.opt["start_lon"])
        except ValueError:
            txt = _(
                "Report generation failed.\n"
                "Please check the values for latitude and longitude.")
            ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)
            return  # stop if lat/lng aren't convertabe to floats

        # more advanced options tab values
        radius = self.opt["radius"]
        start_zoom = self.opt["start_zoom"]
        min_zoom = self.opt["min_zoom"]
        max_zoom = self.opt["max_zoom"]

        # make sure user entered zoom levels do not exceed min/max values
        zoom_error = False
        if min_zoom > max_zoom:
            min_zoom = max_zoom
            zoom_error = True
        if max_zoom < min_zoom:
            max_zoom = min_zoom
            zoom_error = True
        if start_zoom < min_zoom:
            start_zoom = min_zoom
            zoom_error = True
        if start_zoom > max_zoom:
            start_zoom = max_zoom
            zoom_error = True
        if zoom_error:
            txt = _(
                "Your zoom settings were inconclusive and therefore changed "
                "for this report generation.")
            ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)

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
        lst.append("            minZoom: %d,\n" % min_zoom)
        lst.append("            maxZoom: %d,\n" % max_zoom)
        lst.append("            zoomControl: true,\n")
        lst.append("            preferCanvas: false,\n")
        lst.append("        }\n")
        lst.append("    );\n")

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
        lst.append('        {"blur": 15, "max": 43.0, "maxZoom": 18,')
        lst.append(' "minOpacity": 0.5, "radius": %s}\n' % radius)
        lst.append("        ).addTo(GrampsHeatmap);\n")
        lst.append("</script>")

        # Save the generated heatmap report file
        with open(self.filename, "w", encoding="utf-8") as file:
            for item in lst:
                file.write(item)
