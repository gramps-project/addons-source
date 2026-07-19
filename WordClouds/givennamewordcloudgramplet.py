#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009  Pander Musubi
# Copyright (C) 2009  Douglas S. Blank
# Copyright (C) 2026  Douglas S. Blank <doug.blank@gmail.com>
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
# GivenNameWordCloudGramplet class
#
# -------------------------------------------------------------------------
class GivenNameWordCloudGramplet(CloudGramplet):
    """Implementation of a Cloud gramplet for given names."""

    def init(self):
        CloudGramplet.init(self)
        self.set_value_name("given name")
        self.set_preference_no_value("preferences.no-given-text")
        self.set_tooltip(_("Click given name to view people with that given name"))

    def on_item_clicked(self, word, linked_data):
        run_quick_report_by_name(
            self.dbstate, self.uistate, "samegivens_misc", linked_data
        )

    def db_changed(self):
        self.connect(self.dbstate.db, "person-add", self.update)
        self.connect(self.dbstate.db, "person-delete", self.update)
        self.connect(self.dbstate.db, "person-update", self.update)
        self.connect(self.dbstate.db, "person-rebuild", self.update)
        self.connect(self.dbstate.db, "family-rebuild", self.update)

    def get_items(self):
        counts = {}
        for person in self.dbstate.db.iter_people():
            allnames = [person.get_primary_name()] + person.get_alternate_names()
            for name in allnames:
                given_name = name.get_first_name().strip()
                if self.filter_missing and (not given_name or given_name == "?"):
                    continue
                counts[given_name] = counts.get(given_name, 0) + 1
        return [(given_name, given_name, counts[given_name]) for given_name in counts]
