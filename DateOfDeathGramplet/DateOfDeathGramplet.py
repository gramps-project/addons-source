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
import gramps.gen.datehandler
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class DateOfDeathGramplet(Gramplet):
    def init(self):
        self.set_text(_("No Family Tree loaded."))

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

            age = ""
            birth_ref = person.get_birth_ref()
            if birth_ref:
                birth = database.get_event_from_handle(birth_ref.ref)
                birth_date = birth.get_date_object()
                if birth_date.is_regular():
                    age = date_of_death - birth_date

            self.result.append((date_of_death, person, age))

        self.result.sort(key=lambda item: (item[0].get_month(),
                                           item[0].get_day()))
        self.clear_text()

        for date_of_death, person, age in self.result:
            name = person.get_primary_name()
            displayer = gramps.gen.datehandler.displayer
            self.append_text("{}: ".format(displayer.display(date_of_death)))
            self.link(name_displayer.display_name(name), "Person",
                      person.handle)
            if age:
                self.append_text(" ({})\n".format(age[0]))
            else:
                self.append_text("\n")
        self.append_text("", scroll_to="begin")
