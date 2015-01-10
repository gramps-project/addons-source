# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank <doug.blank@gmail.com>
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

# $Id: WordleGramplet.py 13416 2009-10-25 20:29:45Z dsblank $


#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
from itertools import imap

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.plug import Gramplet
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).gettext
from gen.plug.report import utils as ReportUtils

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------

_YIELD_INTERVAL = 350

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------
def get_bin(n, counts, mins=8, maxs=20):
    diff = maxs - mins
    # based on counts (biggest to smallest)
    if len(counts) > 1:
        position = diff - (diff * (float(counts.index(n)) / (len(counts) - 1)))
    else:
        position = 0
    return int(position) + mins

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class WordleGramplet(Gramplet):
    def init(self):
        self.set_tooltip(_("Double-click surname for details"))
        self.top_size = 329 # 10 # will be overwritten in load
        self.set_text(_("No Family Tree loaded."))

    def db_changed(self):
        self.dbstate.db.connect('person-add', self.update)
        self.dbstate.db.connect('person-delete', self.update)
        self.dbstate.db.connect('person-update', self.update)
        self.dbstate.db.connect('person-rebuild', self.update)
        self.dbstate.db.connect('family-rebuild', self.update)

    def on_load(self):
        if len(self.gui.data) > 0:
            self.top_size = int(self.gui.data[0])

    def on_save(self):
        self.gui.data = [self.top_size]

    def main(self):
        self.set_text(_("Processing...") + "\n")
        surnames = {}
        iter_people = self.dbstate.db.iter_person_handles()
        self.filter = self.filter_list.get_filter()
    people = self.filter.apply(self.dbstate.db, iter_people)
        cnt = 0
        for person in imap(self.dbstate.db.get_person_from_handle, people):
            allnames = [person.get_primary_name()] + person.get_alternate_names()
            allnames = set([name.get_group_name().strip() for name in allnames])
            for surname in allnames:
                surnames[surname] = surnames.get(surname, 0) + 1
            cnt += 1
            if not cnt % _YIELD_INTERVAL:
                yield True

        total_people = cnt
        surname_sort = []
        total = 0

        cnt = 0
        for surname in surnames:
            surname_sort.append( (surnames[surname], surname) )
            total += surnames[surname]
            cnt += 1
            if not cnt % _YIELD_INTERVAL:
                yield True

        total_surnames = cnt
        surname_sort.sort(reverse=True)

        counts = list(set([pair[0] for pair in surname_sort]))
        counts.sort(reverse=True)
        line = 0
        ### All done!
        self.set_text("For Wordle:   \n\n")
        nosurname = _("[Missing]")
        for (count, surname) in surname_sort:
            bin = get_bin(count, counts, mins=1, maxs=self.bins.get_value())
            text = "%s: %d\n" % ((surname if surname else nosurname), bin)
            self.append_text(text)
            line += 1
            if line >= self.top_size:
                break
        self.append_text(("\n" + _("Total unique surnames") + ": %d\n") % 
                         total_surnames)
        self.append_text((_("Total people") + ": %d") % total_people, "begin")

    def build_options(self):
        from gen.plug.menu import FilterOption, PersonOption, NumberOption
        self.bins = NumberOption(_("Number of font sizes"), 5, 1, 10)
        self.add_option(self.bins)

        self.filter_list = FilterOption(_("Filter"), 0)
        self.filter_list.set_help(_("Select filter to restrict list"))
        self.filter_list.connect('value-changed', self.filter_changed)
        self.add_option(self.filter_list)

        self.pid_list = PersonOption(_("Filter Person"))
        self.pid_list.set_help(_("The center person for the filter"))
        self.pid_list.connect('value-changed', self.update_filters)
        self.add_option(self.pid_list)

        self.update_filters()

    def update_filters(self):
        """
        Update the filter list based on the selected person
        """
        gid = self.pid_list.get_value()
        try:
            person = self.dbstate.db.get_person_from_gramps_id(gid)
        except:
            return
        filters = ReportUtils.get_person_filters(person, False)
        self.filter_list.set_filters(filters)

    def filter_changed(self):
        """
        Handle filter change. If the filter is not specific to a person,
        disable the person option
        """
        filter_value = self.filter_list.get_value()
        if 1 <= filter_value <= 4:
            # Filters 1, 2, 3 and 4 rely on the center person
            self.pid_list.set_available(True)
        else:
            # The rest don't
            self.pid_list.set_available(False)

