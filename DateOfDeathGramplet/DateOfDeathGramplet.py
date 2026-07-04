#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Javad Razavian <javadr@gmail.com>
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

from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib.date import Today, Date, gregorian
import gramps.gen.datehandler
from gramps.gen.plug.menu import EnumeratedListOption
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class DateOfDeathGramplet(Gramplet):
    def init(self):
        self.set_text(_("No Family Tree loaded."))
        self.sort_mode = 'proximity'

    def build_options(self):
        name_sort = _("Sort dates of death by")
        self.opt_sort = EnumeratedListOption(name_sort, self.sort_mode)
        self.opt_sort.add_item("proximity", _("Proximity to current date"))
        self.opt_sort.add_item("month_day", _("Month and day"))

        self.add_option(self.opt_sort)

    def save_options(self):
        self.sort_mode = self.opt_sort.get_value()

    def save_update_options(self, obj):
        self.save_options()
        self.gui.data = [self.sort_mode]
        self.update()

    def on_load(self):
        if len(self.gui.data) >= 1:
            self.sort_mode = self.gui.data[0]
        else:
            self.sort_mode = 'proximity'

    def db_changed(self):
        self.connect(self.dbstate.db, 'person-add', self.update)
        self.connect(self.dbstate.db, 'person-delete', self.update)
        self.connect(self.dbstate.db, 'person-update', self.update)

    def main(self):
        self.set_text(_("Processing..."))
        database = self.dbstate.db
        self.result = []

        for person in database.iter_people():
            death_ref = person.get_death_ref()
            if not death_ref:
                continue
            death_event = database.get_event_from_handle(death_ref.ref)
            date_of_death = death_event.get_date_object()
            if not date_of_death.is_regular():
                continue

            self.__calculate(database, person)

        sort_by = self.opt_sort.get_value()
        if sort_by == "proximity":
            self.result.sort(key=lambda item: -item[0])
        else:
            self.result.sort(key=lambda item: (item[1].get_month(),
                                               item[1].get_day()))
        self.clear_text()

        for diff_days, date, person, age in self.result:
            name = person.get_primary_name()
            displayer = gramps.gen.datehandler.displayer
            self.append_text("{}: ".format(displayer.display(date)))
            self.link(name_displayer.display_name(name), "Person",
                      person.handle)
            if age:
                self.append_text(" ({})\n".format(age))
            else:
                self.append_text("\n")
        self.append_text("", scroll_to="begin")

    def __calculate(self, database, person):
        today = Today()
        death_ref = person.get_death_ref()
        if not death_ref:
            return
        death_event = database.get_event_from_handle(death_ref.ref)
        date_of_death = death_event.get_date_object()
        if not date_of_death.is_regular():
            return

        death_greg = gregorian(date_of_death)
        death_this_year = Date(today.get_year(),
                               death_greg.get_month(),
                               death_greg.get_day())
        diff = today - death_this_year
        diff_days = diff[1] * 30 + diff[2]

        birth_ref = person.get_birth_ref()
        age = ""
        if birth_ref:
            birth = database.get_event_from_handle(birth_ref.ref)
            birth_date = birth.get_date_object()
            if birth_date.is_regular():
                age = date_of_death - birth_date

        if diff_days <= 0:
            self.result.append((diff_days, date_of_death, person, age))
        else:
            self.result.append((diff_days - 365, date_of_death, person, age))
