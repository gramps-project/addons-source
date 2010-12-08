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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# $Id$

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import time

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.plug import Gramplet
from gen.lib.date import Date
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
import DateHandler

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------

_YIELD_INTERVAL = 5

class LastChangeGramplet(Gramplet):
    def init(self):
        self.set_tooltip(_("Double-click name for details"))
        self.set_text(_("No Family Tree loaded."))

    def main(self):
        """Search the database for the last person records changed."""
        self.set_text(_("Processing...") + "\n")
        counter = 0
        yield True
        handles = sorted(self.dbstate.db.get_person_handles(), key=self._getTimestamp)
        yield True
        self.clear_text()
        for handle in reversed(handles[-10:]):
            person = self.dbstate.db.get_person_from_handle(handle)
            self.append_text(" %d. " % (counter + 1, ))
            self.link(person.get_primary_name().get_name(), 'Person', handle)
            change_date = Date()
            change_date.set_yr_mon_day(*time.localtime(person.change)[0:3])
            self.append_text(" (%s %s)" % (_('changed on'), DateHandler.displayer.display(change_date)))
            self.append_text("\n")
            if (counter % _YIELD_INTERVAL):
                yield True
            counter += 1

    def _getTimestamp(self, person_handle):
        timestamp = self.dbstate.db.person_map.get(str(person_handle))[17]
        return timestamp

    def db_changed(self):
        """Connect the signals that trigger an update."""
        self.dbstate.db.connect('person-add', self.update)
        self.dbstate.db.connect('person-delete', self.update)
        self.dbstate.db.connect('person-update', self.update)
        self.dbstate.db.connect('family-add', self.update)
        self.dbstate.db.connect('family-delete', self.update)
        self.dbstate.db.connect('family-update', self.update)
