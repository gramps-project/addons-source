# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010       Jakim Friant
# Copyright (c) 2015       Douglas S. Blank <doug.blank@gmail.com>
# Copyright (c) 2020       Jan Sparreboom <jan@sparreboom.net>
# Copyright (c) 2024-2025  Steve Youngs <steve@youngs.cc>
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

"""
DateCalculator does date math.
"""

# ------------------------------------------------------------------------
#
# Python modules
#
# ------------------------------------------------------------------------
from gi.repository import Gdk, Gtk

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.datehandler import displayer
from gramps.gen.lib import Date
from gramps.gui.utils import no_match_primary_mask, text_to_clipboard

# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    trans = glocale.get_addon_translator(__file__)
except ValueError:
    trans = glocale.translation
_ = trans.gettext
ngettext = trans.ngettext

from gramps.gen.datehandler import parser

_RETURN = Gdk.keyval_from_name("Return")
_KP_ENTER = Gdk.keyval_from_name("KP_Enter")

# ------------------------------------------------------------------------
#
# Classes
#
# ------------------------------------------------------------------------
class DateCalculator(Gramplet):
    """
    Gramplet that computes date math.
    """

    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        self.top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.top.set_border_width(6)

        self.entry1 = self.__add_entry(
            _("Reference Date or Date Range"), _("a valid Gramps date")
        )
        self.entry1.connect("key-press-event", self.key_press)
        self.entry2 = self.__add_entry(
            _("Date or offset ±y or ±y, m, d"),
            _(
                "1. a Date\n2. a positive or negative number, representing years\n3. a positive or negative list of values, representing years, months, days"
            ),
        )
        self.entry2.connect("key-press-event", self.key_press)
        self.result = self.__add_entry(_("Result"))
        self.result.set_editable(False)

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.START)
        button_box.set_spacing(6)
        button_box.set_border_width(12)

        apply_button = Gtk.Button(label=_("Calculate"))
        apply_button.connect("clicked", self.apply_clicked)
        button_box.add(apply_button)
        copy_button = Gtk.Button(label=_("Copy"))
        copy_button.connect("clicked", self.copy_clicked)
        button_box.add(copy_button)
        clear_button = Gtk.Button(label=_("Clear"))
        clear_button.connect("clicked", self.clear_clicked)
        button_box.add(clear_button)
        self.top.pack_start(button_box, False, False, 6)

        self.top.show_all()
        self.clear_clicked(None)
        return self.top

    def __add_entry(self, name, tooltip=""):
        """
        Add a Entry widget to the interface.
        """
        label = Gtk.Label(halign=Gtk.Align.START)
        label.set_markup("<b>%s</b>" % name)
        self.top.pack_start(label, False, False, 6)
        entry = Gtk.Entry()
        entry.set_tooltip_text(tooltip)
        self.top.pack_start(entry, False, False, 6)
        return entry

    def key_press(self, obj, event):
        if no_match_primary_mask(event.get_state()):
            if event.keyval in (_RETURN, _KP_ENTER):
                self.apply_clicked(obj)
        return False

    def apply_clicked(self, obj):
        """
        Method that is run when you click the Calculate button.
        """
        text1 = str(self.entry1.get_text())
        text2 = str(self.entry2.get_text())
        neg1 = False
        neg2 = False
        if text1.startswith("-"):
            text1 = text1[1:].strip()
            neg1 = True
        if text2.startswith("-"):
            text2 = text2[1:].strip()
            neg2 = True
        try:
            val1 = eval(text1)
        except:
            try:
                val1 = parser.parse(text1)
                if not val1.is_valid():
                    raise Exception()
            except:
                self.result.set_text(_("Error: invalid date for first expression"))
                return
        try:
            val2 = eval(text2)
        except:
            try:
                val2 = parser.parse(text2)
                if not val2.is_valid():
                    raise Exception()
            except:
                self.result.set_text(_("Error: invalid offset for second expression"))
                return
        result = None
        if isinstance(val1, Date):
            if isinstance(val2, Date):
                if neg1:
                    result = val2 - val1
                else:
                    result = val1 - val2
            elif isinstance(val2, tuple):
                if neg2:
                    result = val1 - val2
                else:
                    result = val1 + val2
            elif isinstance(val2, int):
                if neg2:
                    result = val1 - val2
                else:
                    result = val1 + val2
        elif isinstance(val1, tuple):
            if isinstance(val2, Date):
                if neg1:
                    result = val2 - val1
                else:
                    result = val2 + val1
            elif isinstance(val2, tuple):
                result = _("Error: at least one expression must be a date")
            elif isinstance(val2, int):
                result = _("Error: at least one expression must be a date")
        elif isinstance(val1, int):
            if isinstance(val2, Date):
                if neg1:
                    result = val2 - val1
                else:
                    result = val2 + val1
            elif isinstance(val2, tuple):
                result = _("Error: at least one expression must be a date")
            elif isinstance(val2, int):
                result = _("Error: at least one expression must be a date")
        if result:
            if isinstance(result, Date):
                result.set_quality(Date.QUAL_CALCULATED)
                result = displayer.display(result)
            self.result.set_text(str(result))

    def copy_clicked(self, obj):
        text_to_clipboard(self.result.get_text())

    def clear_clicked(self, obj):
        self.entry1.set_text("")
        self.entry2.set_text("")
        self.result.set_text(
            _("Enter an expression in the entries above and click Calculate.")
        )
