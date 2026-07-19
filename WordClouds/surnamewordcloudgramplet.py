#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2026       Douglas S. Blank <doug.blank@gmail.com>
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gui.plug.quick import run_quick_report_by_name

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

from cloudgramplet import CloudGramplet


# -------------------------------------------------------------------------
#
# SurnameWordCloudGramplet class
#
# -------------------------------------------------------------------------
class SurnameWordCloudGramplet(CloudGramplet):
    """Implementation of a Cloud gramplet for surnames."""

    def init(self):
        CloudGramplet.init(self)
        self.set_value_name("surname")
        self.set_preference_no_value("preferences.no-surname-text")
        self.set_tooltip(_("Click surname to view people with that surname"))

    def on_item_clicked(self, word, linked_data):
        run_quick_report_by_name(
            self.dbstate, self.uistate, "samesurnames", linked_data
        )

    def db_changed(self):
        self.connect(self.dbstate.db, "person-add", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "person-rebuild", self.update)
        self.connect(self.dbstate.db, "family-rebuild", self.update)

    def get_items(self):
        counts = {}
        handles = {}
        for person in self.dbstate.db.iter_people():
            allnames = [person.get_primary_name()] + person.get_alternate_names()
            for name in allnames:
                surname = name.get_surname().strip()
                if self.filter_missing and (not surname or surname == "?"):
                    continue
                counts[surname] = counts.get(surname, 0) + 1
                if surname not in handles:
                    handles[surname] = person.handle
        return [(surname, handles[surname], counts[surname]) for surname in counts]
