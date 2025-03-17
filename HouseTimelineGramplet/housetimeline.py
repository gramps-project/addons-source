# Copyright (C) 2018 Andrew Vitu <a.p.vitu@gmail.com>
# Copyright (C) 2025 Brian McCullough
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

from gramps.gen.plug import Gramplet
from collections import defaultdict

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

class HouseTimelineGramplet(Gramplet):
    def init(self):
        self.house_width = 40
        self.set_tooltip(_("Double-click name for details"))
        # self.set_text(_("No Family Tree loaded."))

    def on_load(self):
        self.no_wrap()
        tag = self.gui.buffer.create_tag("fixed")
        tag.set_property("font", "Courier 12")
        if len(self.gui.data) != 1:
            self.gui.data[:] = ["004", None]

    def db_changed(self):
        self.connect(self.dbstate.db,'person-add', self.update)
        self.connect(self.dbstate.db,'person-update', self.update)
        self.connect(self.dbstate.db,'person-delete', self.update)

    def save_update_options(self, widget=None):
        style = self.get_option(_("House Icon Style"))
        self.gui.data[:] = [style.get_value()]
        self.update()

    def build_options(self):
        from gramps.gen.plug.menu import EnumeratedListOption
        # Add types:
        style_list = EnumeratedListOption(_("House Icon Style"), self.gui.data[0])
        for item in [("001", _("Standard")),
                     ("002", _("Small")),
                     ("003", _("Unicode")),
                     ("004", _("Emoji")),
                     ("005", _("None")),
                     ]:
            style_list.add_item(item[0], item[1])
        self.add_option(style_list)

    def main(self):
        self.set_text(_("Processing...") + "\n")
        yield True
        self.sorted_residents = {}
        self.clear_text()
        address_count = 0
        self.residents_range = []
        # get details of people dbhandle, name, address
        for p in self.dbstate.db.iter_people():
            person_handle = p.handle
            primary_name = p.get_primary_name()
            person_name = primary_name.get_name()
            person_addr = p.get_address_list()
            if person_addr:
                address_count += 1
                for item in person_addr:
                    # address format from db is:
                    # [0] street, [1] locality, [2] city, [3] pcode, [4] state/county, [5] country, [6] phone
                    address = item.get_text_data_list()
                    date = item.get_date_object()
                    self.build_parent_address_dict(address,date,person_handle,person_name)

        if address_count == 0:
            self.set_text(_("There are no individuals with Address data. Please add Address data to people."))
        self.build_house()
        start, end = self.gui.buffer.get_bounds()
        self.gui.buffer.apply_tag_by_name("fixed", start, end)
        self.append_text("", scroll_to="begin")
        yield False

    def build_parent_address_dict(self, address, date, person_handle, person_name):
        """
        Builds self.sorted_residents, The address + person_handle object.
        The collection is grouped by locality/city (group_key) and sub key (address_key)
        """
        # group key represents a group of similar locality/city.
        group_key = address[1] + address[2]
        # address key is the actual property address.
        address_key = self.format_address_key(address)
        if group_key not in self.sorted_residents:
            self.sorted_residents[group_key] = {address_key: [[date.get_ymd(),person_handle,person_name]]}
        elif group_key in self.sorted_residents:
            if address_key not in self.sorted_residents[group_key]:
                self.sorted_residents[group_key][address_key] = [[date.get_ymd(),person_handle,person_name]]
            elif address_key in self.sorted_residents[group_key]:
                self.sorted_residents[group_key][address_key] += [[date.get_ymd(),person_handle,person_name]]

    def format_address_key(self, address):
        """
        Builds a formatted Address string that can be used as a Key.
        """
        key = ""
        for k in address:
            if len(k) > 0:
                key += k + " "
        return key

    def build_house(self):
        """
        Outputs sorted details from self.sorted_residents.
        """
        gl_location = _("Location")
        gl_time = _("Time In Family")
        gl_first_resident = _("First Resident")
        gl_last_resident = _("Last Resident")
        gl_timeline = _("Timeline")
        gl_unknown = _("Unknown")
        gl_total_residents = _("Total Known Residents")

        for resident in self.sorted_residents.items():
            # sort by house number
            for item in sorted(resident[1].items()):
                # sort residents of an address by date.
                sorted_dates = sorted(item[1],key=lambda k: k[0][0])
                residents_reversed = sorted(sorted_dates, reverse=True)
                # we need a list of distinct handles to get the correct resident count per address.
                distinct_handles = []
                for h in sorted_dates:
                    if h[1] not in distinct_handles:
                        distinct_handles.append(h[1])
                first_year = int(sorted_dates[0][0][0])
                last_year = int(sorted_dates[-1][0][0])
                time_in_family = last_year - first_year if first_year != 0 else gl_unknown
                self.append_text("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                self.render_house(self.gui.data[0])
                self.append_text("{0}: {1}\n".format(gl_location,item[0]) +
                ("{0}: {1} years\n".format(gl_time,time_in_family)) +
                ("{0}: {1} - {2}\n".format(gl_first_resident,sorted_dates[0][0][0],sorted_dates[0][2])) +
                ("{0}: {1} - {2}\n".format(gl_last_resident,sorted_dates[-1][0][0],sorted_dates[-1][2])) +
                ("{0}: {1}\n".format(gl_total_residents,len(distinct_handles))) +
                "                        \n")
                self.append_text("{0}:\n".format(gl_timeline))
                # for each person that is a resident, display the date and name with link.
                for detail in sorted_dates:
                    # if a person has two address details, display the person living there as a range between two dates.
                    first_handle = detail
                    last_handle = next(handle for handle in residents_reversed if handle[1] == first_handle[1])
                    if (detail[0][0] != last_handle[0][0] and detail[1] not in self.residents_range):
                        self.append_text("{0} -> {1} - ".format(first_handle[0][0],last_handle[0][0]))
                        self.link(detail[2],"Person",detail[1])
                        self.append_text("\n")
                        self.residents_range.append(first_handle[1])
                    elif detail[1] not in self.residents_range:
                        self.append_text("{0} - ".format(detail[0][0]))
                        self.link(detail[2],"Person",detail[1])
                        self.append_text("\n")

    def render_house(self,house_type):
        """
        Renders various types of ASCII houses.
        """
        if house_type == "001":
            self.append_text(
                "      ~~~\n" +
                "  __[]________\n" +
                " /____________\\ \n" +
                " |            | \n" +
                " | [)(]  [)(] | \n" +
                " |     __     | \n" +
                " |    |  |    | \n" +
                " |____|__|____| \n" +
                "                         \n"
            )
        elif house_type == "002":
            self.append_text(
                "  .___. \n" +
                " / \___\\ \n" +
                " |_|_#_| \n" +
                "                        \n"
            )
        elif house_type == "003":
            self.append_text(
                " ⌂ \n"
            )
        elif house_type == "004":
            self.append_text(
                " 🏠 \n"
            )
