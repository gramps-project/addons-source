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
"""Multi-select menu option."""


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
from gramps.gui.widgets.multitreeview import MultiTreeView  # type: ignore
from gramps.gen.const import GRAMPS_LOCALE as glocale  # type: ignore
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ------------------------------------------------------------------------
#
# MultiSelectOption Class
#
# ------------------------------------------------------------------------
class MultiSelectOption(PlugOption):
    """Extending gramps.gen.plug.menu._option.Option"""

    def __init__(self, label, value):
        PlugOption.__init__(self, label, value)


# ------------------------------------------------------------------------
#
# HeatmapScrolled Class
#
# ------------------------------------------------------------------------
class HeatmapScrolled(Gtk.ScrolledWindow):
    """Extending Gtk.ScrolledWindow."""

    def __init__(self, option, dbstate, uistate, track, override=False):
        Gtk.ScrolledWindow.__init__(self)
        self.set_min_content_height(300)
        self.add(HeatmapMultiTreeView(dbstate, option))


# ------------------------------------------------------------------------
#
# HeatmapMultiTreeView Class
#
# ------------------------------------------------------------------------
class HeatmapMultiTreeView(MultiTreeView):
    """Extending gramps.gui.widgets.multitreeview."""

    def __init__(self, dbstate, option):
        MultiTreeView.__init__(self)
        self.db = dbstate.db
        self.option = option
        self.get_selection().set_mode(Gtk.SelectionMode.NONE)
        self.selected_rows = list()

        # Event types data
        default_types = [name[1] for name in EventType._DATAMAP]
        custom_types = [name for name in self.db.get_event_types()]
        self.data = sorted([*default_types, *custom_types])

        # Setup columns
        model = Gtk.ListStore(bool, str)
        self.set_model(model)

        toggle_renderer = Gtk.CellRendererToggle()
        toggle_renderer.set_property('activatable', True)
        toggle_renderer.connect("toggled", self.toggle, 0)
        col_check = Gtk.TreeViewColumn("", toggle_renderer)
        col_check.add_attribute(toggle_renderer, "active", 0)
        self.append_column(col_check)

        col_name = Gtk.TreeViewColumn(
            _("Event type"), Gtk.CellRendererText(), text=1)
        self.append_column(col_name)

        # Fill columns with data
        for item in self.data:
            model.append([False, item])

        self.load_last_values()

    def load_last_values(self):
        for row in self.option.get_value():
            self.get_model()[row][0] = True

    def toggle(self, _, row, col):
        is_activated = self.get_model()[row][col]
        values = self.option.get_value()

        if is_activated:
            values.remove(row)
        else:
            values.append(row)

        self.option.set_value(values)

        # Invert the checkbox value
        self.get_model()[row][col] = not self.get_model()[row][col]
