# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Peter Potrowl <peter017@gmail.com>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from gen.plug import Gramplet
from gen.ggettext import sgettext as _
from gen.display.name import displayer as name_displayer
from gen.ggettext import ngettext
from gen.lib.date import Today, Date
import DateHandler
import time
import datetime
import posixpath

"""
This Gramplet displays the birthdays of the next n days (n = 0 to 365).
"""

class BirthdaysGramplet(Gramplet):
    def init(self):
	self.set_text(_("No Family Tree loaded."))
	self.num_days = 7
	self.max_age = 110

    def post_init(self):
	self.disconnect("active-changed")

    def on_load(self):
	if len(self.gui.data) == 2:
	    self.num_days = int(self.gui.data[0])
            self.max_age = int(self.gui.data[1])

    def db_changed(self):
	self.dbstate.db.connect('person-add', self.update)
	self.dbstate.db.connect('person-delete', self.update)
	self.dbstate.db.connect('person-update', self.update)
	self.update

    def build_options(self):
	from gen.plug.menu import NumberOption
        # Consider removing this; why should the user think about it?
	self.add_option(NumberOption(_("Number of days"), self.num_days, 0, 365))
        # Consider using the system builtin maximum age:
        # config.get('behavior.max-age-prob-alive')
	self.add_option(NumberOption(_("Maximum age"), self.max_age, 0, 150))

    def save_options(self):
        self.num_days = int(self.get_option(_("Number of days")).get_value())
        self.max_age = int(self.get_option(_("Maximum age")).get_value())

    def save_update_options(self, widget=None):
        self.num_days = int(self.get_option(_("Number of days")).get_value())
        self.max_age = int(self.get_option(_("Maximum age")).get_value())
        self.gui.data = [self.num_days, self.max_age]
        self.update()

    def main(self):
	self.set_text(_("Processing..."))
	database = self.dbstate.db
	personList = database.iter_people()
	result = []
	text = ''
        today = Today()
	for cnt, person in enumerate(personList):
	    birth_ref = person.get_birth_ref()
	    death_ref = person.get_death_ref()
	    if (birth_ref and not death_ref):
		birth = database.get_event_from_handle(birth_ref.ref)
		birth_date = birth.get_date_object()
		if birth_date.is_regular():
                    birthday_this_year = Date(today.get_year(), birth_date.get_month(), birth_date.get_day())
                    age = birthday_this_year - birth_date
                    # returns (years, months, days), all negative if after
                    diff = today - birth_date
                    # about number of days since today, not counting year:
                    diff_days = abs(diff[1]) * 30 + abs(diff[2])
                    if abs(diff[0]) < self.max_age:
                        if diff[0] < 0: # missed for this year, next year:
                            result.append((diff_days + 365, age, birth_date, person))
                        elif diff_days == 0: # today
                            result.append((diff_days + 365, age, birth_date, person))
                        else:
                            result.append((diff_days, age, birth_date, person))
        # Reverse sort on number of days from now:
	result.sort(key=lambda item: -item[0])
	self.clear_text()
	for diff, age, date, person in result:
            name = person.get_primary_name()
            self.append_text("%s: " % DateHandler.displayer.display(date))
            self.link(name_displayer.display_name(name), 
                      "Person", person.handle)
            self.append_text(" (%s)\n" % age)
        self.append_text("", scroll_to="begin")
