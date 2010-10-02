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
	self.add_option(NumberOption(_("Number of days"), self.num_days, 0, 365))
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
        
	result = {}
	text = ''
        
	for cnt, person in enumerate(personList):
	    birth_ref = person.get_birth_ref()
	    death_ref = person.get_death_ref()
	    if (birth_ref and not death_ref):
		birth = database.get_event_from_handle(birth_ref.ref)
		birth_date = birth.get_date_object()
		if birth_date.is_regular():
		    birth_date.to_calendar('gregorian')
		    birth_date_array = birth_date.get_ymd()
		    today = datetime.date(time.localtime().tm_year, time.localtime().tm_mon, time.localtime().tm_mday)
		    birthday_date = datetime.date(time.localtime().tm_year, birth_date_array[1], birth_date_array[2])
		    diff = birthday_date - today
		    age = time.localtime().tm_year - birth_date_array[0]
		    #This deals with the birthdays of next year
		    if diff.days < 0:
			birthday_date = datetime.date(time.localtime().tm_year + 1, birth_date_array[1], birth_date_array[2])
			age += 1
		    diff = birthday_date - today
		    if age < self.max_age and diff.days <= self.num_days:
			primary_name = person.get_primary_name()
			name = name_displayer.display_name(primary_name)
			age = ngettext(' (%d year old)', ' (%d years old)', age ) % age
			line = name + age + '\n'
			#This allows several people to have the same birth date
			key = birthday_date.isoformat() + "." + str(cnt)
			result[key] = line
	
	dates = result.keys()
	dates.sort()
	for date in dates:
	    text += date[0:10] + ': ' + result[date]
	
	self.clear_text()
	self.set_text(_("%s") % text)
