#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021    Matthias Kemmer
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
"""Collection of classes creating a multi-select listbox for menu options."""


# -------------------------------------------------------------------------
#
# GTK Modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk  # type: ignore

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.lib import EventType  # type: ignore
from gramps.gen.plug.menu import Option as PlugOption  # type: ignore


# ------------------------------------------------------------------------
#
# MultiSelectListBoxOption Class
#
# ------------------------------------------------------------------------
class MultiSelectListBoxOption(PlugOption):
    """Extending gramps.gen.plug.menu._option.Option"""

    def __init__(self, label, value):
        PlugOption.__init__(self, label, value)


# ------------------------------------------------------------------------
#
# GuiScrollMultiSelect Class
#
# ------------------------------------------------------------------------
class GuiScrollMultiSelect(Gtk.ScrolledWindow):
    """Extending Gtk.ScrolledWindow."""

    def __init__(self, option, dbstate, uistate, track, override=False):
        Gtk.ScrolledWindow.__init__(self)
        self.__option = option
        self.list_box = MultiSelectListBox(dbstate)
        self.list_box.connect('selected-rows-changed', self.value_changed)
        self.add(self.list_box)
        self.set_min_content_height(300)
        self.load_last_rows()

    def load_last_rows(self):
        for event_type in self.__option.get_value():
            for row in self.list_box.rows:
                if int(row.index) == int(event_type):
                    self.list_box.select_row(row)

    def value_changed(self, _):
        values = [row.index for row in self.list_box.get_selected_rows()]
        self.__option.set_value(values)


# ------------------------------------------------------------------------
#
# MultiSelectListBox Class
#
# ------------------------------------------------------------------------
class MultiSelectListBox(Gtk.ListBox):
    """Extending Gtk.ListBox."""

    def __init__(self, dbstate):
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode(3))
        self.set_activate_on_single_click(False)
        self.rows = []

        # Get all event type names
        default_types = [name[1] for name in EventType._DATAMAP]
        custom_types = [name for name in dbstate.db.get_event_types()]
        event_types = sorted([*default_types, *custom_types])

        # Create rows
        for index, name in enumerate(event_types):
            self.add_row(index, name)

    def add_row(self, index, name):
        row = EventTypeRow(index, name)
        self.insert(row, index)
        self.rows.append(row)


# ------------------------------------------------------------------------
#
# EventTypeRow Class
#
# ------------------------------------------------------------------------
class EventTypeRow(Gtk.ListBoxRow):
    """Extending Gtk.ListBoxRow."""

    def __init__(self, index, name):
        Gtk.ListBoxRow.__init__(self)
        self.label = name
        self.index = index
        self.add(Gtk.Label(self.label))
