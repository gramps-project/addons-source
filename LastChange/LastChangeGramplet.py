# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010       Jakim Friant
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

# $Id$

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from bisect import bisect

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import format_time
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------
_YIELD_INTERVAL = 100


class LastChangeGramplet(Gramplet):
    """ Scans for the last 10 changes among people and shows them """

    def init(self):
        """ Set up the GUI """
        self.set_tooltip(_("Double-click name for details"))
        self.set_text(_("No Family Tree loaded."))

    def main(self):
        """Search the database for the last person records changed."""
        self.set_text(_("Processing...") + "\n")
        counter = 0
        the_list = []  # sorted list of people with change times, newest first
        for handle in self.dbstate.db.iter_person_handles():
            change = -self.dbstate.db.get_raw_person_data(handle)[17]
            bsindex = bisect(KeyWrapper(the_list, key=lambda c: c[1]),
                             change)
            the_list.insert(bsindex, (handle, change))
            if len(the_list) > 10:  # only need 10 entries, so remove oldest
                the_list.pop(10)
            if counter % _YIELD_INTERVAL:  # let rest of GUI run
                yield True
            counter += 1
        yield True

        self.clear_text()
        counter = 1
        for handle, change in the_list:
            person = self.dbstate.db.get_person_from_handle(handle)
            self.append_text(" %d. " % (counter, ))
            self.link(person.get_primary_name().get_name(), 'Person',
                      person.handle)
            self.append_text(" (%s %s)" % (_('changed on'),
                                           format_time(person.change)))
            if counter < 10:
                self.append_text("\n")
            counter += 1

    def db_changed(self):
        """Connect the signals that trigger an update."""
        self.connect(self.dbstate.db, 'person-update', self.update)
        self.connect(self.dbstate.db, 'person-add', self.update)
        self.connect(self.dbstate.db, 'person-delete', self.update)
        self.connect(self.dbstate.db, 'person-rebuild', self.update)
        self.connect(self.dbstate.db, 'family-rebuild', self.update)
        self.connect(self.dbstate.db, 'family-add', self.update)
        self.connect(self.dbstate.db, 'family-delete', self.update)
        self.connect(self.dbstate.db, 'family-update', self.update)


class KeyWrapper:
    """ used to create an way for bisect to operate on an element of a tuple
        in the list."""
    def __init__(self, iterable, key):
        self.iter = iterable
        self.key = key

    def __getitem__(self, i):
        return self.key(self.iter[i])

    def __len__(self):
        return len(self.iter)
