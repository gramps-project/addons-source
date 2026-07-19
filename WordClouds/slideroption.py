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
#
"""
A NumberOption rendered as a horizontal slider with a text entry, and the
matching GTK widget. Registered with the plugin manager as an external
option so it does not require any change to Gramps core.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import math

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import Gtk

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.plug.menu import NumberOption


# -------------------------------------------------------------------------
#
# SliderOption class
#
# -------------------------------------------------------------------------
class SliderOption(NumberOption):
    """
    A NumberOption rendered as a horizontal slider + text entry widget.
    Saves only on mouse-up or entry commit, not on every drag tick.
    All min/max/step/value logic is inherited from NumberOption.
    """


# -------------------------------------------------------------------------
#
# GuiSliderOption class
#
# -------------------------------------------------------------------------
class GuiSliderOption(Gtk.Box):
    """
    Displays a number option as a horizontal slider alongside a text entry.
    The option value is only committed on mouse-up or entry activation,
    not on every drag tick.
    """

    def __init__(self, option, dbstate, uistate, track, override):
        self.__option = option

        step = self.__option.get_step()
        self.__decimals = 0
        if step < 1:
            self.__decimals = int(math.log10(step) * -1)

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        adj = Gtk.Adjustment(
            value=self.__option.get_value(),
            lower=self.__option.get_min(),
            upper=self.__option.get_max(),
            step_increment=step,
        )
        self.__scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        self.__scale.set_digits(self.__decimals)
        self.__scale.set_hexpand(True)
        self.__scale.set_draw_value(False)

        self.__entry = Gtk.Entry()
        self.__entry.set_width_chars(6)
        self.__entry.set_max_width_chars(8)
        self.__entry.set_text(self.__format(self.__option.get_value()))

        self.pack_start(self.__scale, True, True, 0)
        self.pack_start(self.__entry, False, False, 0)

        # Live sync: update entry text while dragging, but do not commit yet.
        self.scalekey = self.__scale.connect("value-changed", self.__scale_moved)
        # Commit on mouse-up only.
        self.__scale.connect("button-release-event", self.__scale_released)
        # Commit entry on Enter or focus-out.
        self.entrykey = self.__entry.connect("activate", self.__entry_activated)
        self.__entry.connect("focus-out-event", self.__entry_activated)

        # Programmatic option change -> update both widgets.
        self.valuekey = self.__option.connect("value-changed", self.__value_changed)
        self.conkey = self.__option.connect("avail-changed", self.__update_avail)
        self.__update_avail()

        self.set_tooltip_text(self.__option.get_help())

    def __format(self, value):
        if self.__decimals == 0:
            return str(int(value))
        return "{:.{}f}".format(value, self.__decimals)

    def __scale_moved(self, obj):
        """Update entry text live during drag without committing to the option."""
        self.__entry.handler_block(self.entrykey)
        self.__entry.set_text(self.__format(self.__scale.get_value()))
        self.__entry.handler_unblock(self.entrykey)

    def __scale_released(self, obj, event):
        """Commit the slider value to the option on mouse-up."""
        vtype = type(self.__option.get_value())
        self.__scale.handler_block(self.scalekey)
        self.__option.set_value(vtype(self.__scale.get_value()))
        self.__scale.handler_unblock(self.scalekey)

    def __entry_activated(self, obj, event=None):
        """Commit a typed value from the entry to the option."""
        try:
            vtype = type(self.__option.get_value())
            value = vtype(float(self.__entry.get_text()))
            value = max(self.__option.get_min(), min(self.__option.get_max(), value))
        except (ValueError, TypeError):
            self.__entry.set_text(self.__format(self.__option.get_value()))
            return
        if value == self.__option.get_value():
            return
        self.__scale.handler_block(self.scalekey)
        self.__scale.set_value(value)
        self.__scale.handler_unblock(self.scalekey)
        self.__option.set_value(value)

    def __value_changed(self):
        """Handle a programmatic change to the option value."""
        value = self.__option.get_value()
        self.__scale.handler_block(self.scalekey)
        self.__entry.handler_block(self.entrykey)
        self.__scale.set_value(value)
        self.__entry.set_text(self.__format(value))
        self.__entry.handler_unblock(self.entrykey)
        self.__scale.handler_unblock(self.scalekey)

    def __update_avail(self):
        avail = self.__option.get_available()
        self.set_sensitive(avail)

    def clean_up(self):
        self.__option.disconnect(self.valuekey)
        self.__option.disconnect(self.conkey)
        self.__option = None
