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
from gramps.gen.display.place import displayer as place_displayer
from gramps.gui.plug.quick import run_quick_report_by_name

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.sgettext

from cloudgramplet import CloudGramplet


# -------------------------------------------------------------------------
#
# PlaceWordCloudGramplet class
#
# -------------------------------------------------------------------------
class PlaceWordCloudGramplet(CloudGramplet):
    """Implementation of a Cloud gramplet for place names.

    Word size reflects how many times each place is referenced in the database.
    """

    def init(self):
        CloudGramplet.init(self)
        self.set_value_name("place name")
        self.set_tooltip(_("Click place name to view references"))

    def on_item_clicked(self, word, linked_data):
        run_quick_report_by_name(
            self.dbstate, self.uistate, "placereferences", linked_data
        )

    def db_changed(self):
        self.connect(self.dbstate.db, "place-add", self.update)
        self.connect(self.dbstate.db, "place-delete", self.update)
        self.connect(self.dbstate.db, "place-update", self.update)
        self.connect(self.dbstate.db, "event-add", self.update)
        self.connect(self.dbstate.db, "event-update", self.update)
        self.connect(self.dbstate.db, "event-delete", self.update)

    def get_items(self) -> list:
        # Use the full hierarchical name so each place maps to a unique string,
        # and count by backlinks so word size reflects how often it is used.
        items = []
        for place in self.dbstate.db.iter_places():
            handle = place.handle
            count = len(list(self.dbstate.db.find_backlink_handles(handle)))
            if count > 0:
                placename = place_displayer.display(self.dbstate.db, place)
                if self.filter_missing and placename in (None, "", "?"):
                    continue
                items.append((placename, handle, count))
        return items
