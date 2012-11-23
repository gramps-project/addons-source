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

from gramps.gen.plug import Gramplet
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).gettext
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.lib.date import Today, Date
import gramps.gen.datehandler
import time
import datetime
import posixpath
from gramps.gen.config import config

"""
This Gramplet displays the incoming birthdays.
"""

class BirthdaysGramplet(Gramplet):
	def init(self):
		self.set_text(_("No Family Tree loaded."))
		self.max_age = config.get('behavior.max-age-prob-alive')

	def post_init(self):
		self.disconnect("active-changed")

	def db_changed(self):
		self.dbstate.db.connect('person-add', self.update)
		self.dbstate.db.connect('person-delete', self.update)
		self.dbstate.db.connect('person-update', self.update)
		self.update

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
					next_age = birthday_this_year - birth_date
					# (0 year, months, days) between now and birthday of this year (positive if passed):
					diff = today - birthday_this_year
					# about number of days the diff is:
					diff_days = diff[1] * 30 + diff[2]
					if next_age[0] < self.max_age:
						if diff_days <= 0: #not yet passed
							result.append((diff_days, next_age, birth_date, person))
						else: #passed; add it for next year's birthday
							result.append((diff_days - 365, next_age[0] + 1, birth_date, person))
		# Reverse sort on number of days from now:
		result.sort(key=lambda item: -item[0])
		self.clear_text()
		for diff, age, date, person in result:
			name = person.get_primary_name()
			self.append_text("%s: " % gramps.gen.datehandler.displayer.display(date))
			self.link(name_displayer.display_name(name), "Person", person.handle)
			self.append_text(" (%s)\n" % age)
		self.append_text("", scroll_to="begin")
