#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2023  Nick Hall
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

from gi.repository import Gtk

from gramps.gen.plug import Gramplet
from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gen.lib.date import Today
from gramps.gen.utils.db import get_participant_from_event
from gramps.gen.datehandler import get_date
from gramps.gen.config import config
from gramps.gui.editors import EditEvent

from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class AnniversariesGramplet(Gramplet):
    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip = _("Double-click on a row to edit the event.")
        self.set_tooltip(tip)
        top = Gtk.TreeView()
        titles = [
            ("", NOSORT, 50),
            (_("Date"), 2, 100),
            ("", 2, 100),
            (_("Participant"), 3, 300),
            (_("Age"), 5, 75),
            ("", 5, 75),
            (_("Event Type"), 6, 150),
        ]
        self.model = ListModel(top, titles, event_func=self.edit_event)
        return top

    def db_changed(self):
        self.connect(self.dbstate.db, "event-update", self.update)

    def main(self):
        """
        Display the events with an anniversary today.
        """
        self.model.clear()
        today = Today()
        today_y, today_m, today_d = today.get_ymd()
        for handle in self.dbstate.db.get_event_handles():
            event = self.dbstate.db.get_event_from_handle(handle)
            date = event.get_date_object()
            if date.get_month() == today_m and date.get_day() == today_d:
                partcipant = get_participant_from_event(self.dbstate.db, handle)
                self.model.add(
                    [
                        handle,
                        get_date(event),
                        "%012d" % date.get_sort_value(),
                        partcipant,
                        (today - date).format(as_age=False),
                        "%06d" % (today_y - date.get_year()),
                        str(event.get_type()),
                    ]
                )

    def edit_event(self, treeview):
        """
        Edit the selected event.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            try:
                event = self.dbstate.db.get_event_from_handle(handle)
                EditEvent(self.dbstate, self.uistate, [], event)
            except WindowActiveError:
                pass
