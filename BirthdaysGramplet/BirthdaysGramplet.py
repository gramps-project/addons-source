#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Peter Potrowl <peter017@gmail.com>
# Copyright (C) 2019  Matthias Kemmer <matt.familienforschung@gmail.com>
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
from gramps.gen.lib.date import Today, Date
import gramps.gen.datehandler
from gramps.gen.config import config
from gramps.gen.plug.menu import EnumeratedListOption
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class BirthdaysGramplet(Gramplet):
    def init(self):
        self.set_text(_("No Family Tree loaded."))
        self.max_age = config.get('behavior.max-age-prob-alive')

    def build_options(self):
        """Build the configuration options"""
        db = self.dbstate.db

        name_ignore = _("Ignore birthdays with tag")
        name_only = _("Only show birthdays with tag")
        self.opt_ignore = EnumeratedListOption(name_ignore, self.ignore_tag)
        self.opt_only = EnumeratedListOption(name_only, self.only_tag)

        self.opt_ignore.add_item('', '')  # No ignore tag
        self.opt_only.add_item('', '')
        if db.is_open():
            for tag_handle in db.get_tag_handles(sort_handles=True):
                tag = db.get_tag_from_handle(tag_handle)
                tag_name = tag.get_name()
                self.opt_ignore.add_item(tag_name, tag_name)
                self.opt_only.add_item(tag_name, tag_name)

        self.add_option(self.opt_ignore)
        self.add_option(self.opt_only)

    def save_options(self):
        """Save gramplet configuration data"""
        self.ignore_tag = self.opt_ignore.get_value()
        self.only_tag = self.opt_only.get_value()

    def save_update_options(self, obj):
        """Save a gramplet's options to file"""
        self.save_options()
        self.gui.data = [self.ignore_tag, self.only_tag]
        self.update()

    def on_load(self):
        """Load stored configuration data"""
        if len(self.gui.data) == 2:
            self.ignore_tag = self.gui.data[0]
            self.only_tag = self.gui.data[1]
        else:
            self.ignore_tag = ''
            self.only_tag = ''

    def db_changed(self):
        """Update gramplet when database was changed"""
        self.connect(self.dbstate.db, 'person-add', self.update)
        self.connect(self.dbstate.db, 'person-delete', self.update)
        self.connect(self.dbstate.db, 'person-update', self.update)

    def main(self):
        """Main function of the Birthdays gramplet"""
        self.set_text(_("Processing..."))
        database = self.dbstate.db
        person_list = database.iter_people()
        self.result = []

        ignore_tag_handle = ""
        only_tag_handle = ""
        tag_name_ignore = self.opt_ignore.get_value()
        tag_name_only = self.opt_only.get_value()
        tag_handles = database.get_tag_handles()
        for handle in tag_handles:
            tag = database.get_tag_from_handle(handle)
            # overwrite ignore_handle and only_handle to user selection
            # if a handle is selected
            if tag_name_ignore == tag.get_name():
                ignore_tag_handle = tag.get_handle()
            if tag_name_only == tag.get_name():
                only_tag_handle = tag.get_handle()

        for person in list(person_list):
            pers_tag_handles = person.get_tag_list()
            if ignore_tag_handle in pers_tag_handles:
                pass  # ignore person
            elif only_tag_handle in pers_tag_handles or only_tag_handle == "":
                # calculate age and days until birthday
                self.__calculate(database, person)

        # Reverse sort on number of days from now:
        self.result.sort(key=lambda item: -item[0])
        self.clear_text()

        # handle text shown in gramplet
        for diff, age, date, person in self.result:
            name = person.get_primary_name()
            displayer = gramps.gen.datehandler.displayer
            self.append_text("{}: ".format(displayer.display(date)))
            self.link(name_displayer.display_name(name), "Person",
                      person.handle)
            self.append_text(" ({})\n".format(age))
        self.append_text("", scroll_to="begin")

    def __calculate(self, database, person):
        """Calculate the age and days until birthday"""
        today = Today()
        birth_ref = person.get_birth_ref()
        death_ref = person.get_death_ref()
        if (birth_ref and not death_ref):
            birth = database.get_event_from_handle(birth_ref.ref)
            birth_date = birth.get_date_object()
            if birth_date.is_regular():
                birthday_this_year = Date(today.get_year(),
                                          birth_date.get_month(),
                                          birth_date.get_day())
                next_age = birthday_this_year - birth_date
                # (0 year, months, days) between now and birthday of this
                # year (positive if passed):
                diff = today - birthday_this_year
                # about number of days the diff is:
                diff_days = diff[1] * 30 + diff[2]
                if next_age[0] < self.max_age:
                    if diff_days <= 0:  # not yet passed
                        self.result.append((diff_days, next_age, birth_date,
                                           person))
                    else:  # passed; add it for next year's birthday
                        self.result.append((diff_days - 365,
                                            next_age[0] + 1,
                                            birth_date, person))
