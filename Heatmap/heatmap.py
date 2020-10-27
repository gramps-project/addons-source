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
    BooleanOption)
from gramps.gen.filters import GenericFilterFactory, rules, CustomFilters
from gramps.gen.plug.docgen import ParagraphStyle
from gramps.gen.lib.eventtype import EventType
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
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """Create menu options."""
        self.get_filter_list(menu)
        fltr = EnumeratedListOption(_("Filter"), 0)
        fltr.set_items(menu.filter_list)
        menu.add_option(_("Options"), "fltr", fltr)

        pers_id = PersonOption(_("Person"))
        menu.add_option(_("Options"), "pers_id", pers_id)

        path = DestinationOption(_("Filepath"), "")
        path.set_directory_entry(True)
        menu.add_option(_("Options"), "path", path)

        file_name = StringOption(_("File name"), "")
        menu.add_option(_("Options"), "name", file_name)

        type1 = BooleanOption(_("Birth"), False)
        menu.add_option(_("Event Types"), "Birth", type1)
        type2 = BooleanOption(_("Death"), False)
        menu.add_option(_("Event Types"), "Death", type2)
        type3 = BooleanOption(_("Residence"), False)
        menu.add_option(_("Event Types"), "Residence", type3)
        type4 = BooleanOption(_("Occupation"), False)
        menu.add_option(_("Event Types"), "Occupation", type4)

    @staticmethod
    def get_filter_list(menu):
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

        if os.path.exists(path):
            if name.isalnum():
                self.filename = path + "/" + name + ".html"
                return True
            chars = [x for x in name if not x.isalnum()]
            for char in chars:
                if char not in ["_", "-"]:
                    txt = _("Filename is empty or contains "
                            "non-alphanumeric characters.")
                    ErrorDialog(_("INFO"), txt,
                                parent=self.user.uistate.window)
                    return False
            self.filename = path + "/" + name + ".html"
            return True
        txt = _("Path does not exist.")
        ErrorDialog(_("INFO"), txt, parent=self.user.uistate.window)
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
        # Get a list of translated event types selected in the menu
        all_types = self.options.menu.get_option_names("Event Types")
        types = [x for x in all_types if self.opt[x]]
        transl = [x[1] for x in EventType._DATAMAP if x[2] in types]

        for event_ref in events:
            event = self.db.get_event_from_handle(event_ref.ref)
            if event.get_type() in transl:
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

        lst = list()
        res_path = os.path.dirname(__file__) + "/template/map.html"
        counter = 1
        with open(res_path, "r", encoding="utf-8") as file:
            for line in file:
                if counter == 55:  # insert to line 55 in template/map.html
                    lst.append("[")
                    for key, value in self.place_dict.items():
                        try:
                            lat = float(value[0])
                            lon = float(value[1])
                            val = float(value[2])
                            lst.append("[%f, %f, %f]," % (lat, lon, val))
                        except ValueError:
                            # if place coords can't be changed to float
                            print("INFO: Place '%s' was ignored because of"
                                  " unsupported coordinates." % key)
                    lst.append("],\n")
                else:
                    lst.append(line)
                counter += 1

        with open(self.filename, "w", encoding="utf-8") as file:
            for item in lst:
                file.write(item)
