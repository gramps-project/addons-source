# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010       Jakim Friant
# Copyright (c) 2015       Douglas S. Blank <doug.blank@gmail.com>
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

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.lib import Date
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.sgettext
from gramps.gen.datehandler import parser

#------------------------------------------------------------------------
#
# Classes
#
#------------------------------------------------------------------------
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

        self.entry1 = self.__add_text_view(_("Expression 1"))
        self.entry2 = self.__add_text_view(_("Expression 2"))
        self.result = self.__add_text_view(_("Result"))

        bbox = Gtk.ButtonBox()
        apply_button = Gtk.Button(label=_("Calculate"))
        apply_button.connect('clicked', self.apply_clicked)
        bbox.pack_start(apply_button, False, False, 6)
        clear_button = Gtk.Button(label=_("Clear"))
        clear_button.connect('clicked', self.clear_clicked)
        bbox.pack_start(clear_button, False, False, 6)
        self.top.pack_start(bbox, False, False, 6)

        self.top.show_all()
        self.clear_clicked(None)
        return self.top

    def __add_text_view(self, name):
        """
        Add a text view to the interface.
        """
        label = Gtk.Label(halign=Gtk.Align.START)
        label.set_markup('<b>%s</b>' % name)
        self.top.pack_start(label, False, False, 6)
        swin = Gtk.ScrolledWindow()
        swin.set_shadow_type(Gtk.ShadowType.IN)
        tview = Gtk.TextView()
        swin.add(tview)
        self.top.pack_start(swin, True, True, 6)
        return tview.get_buffer()

    def apply_clicked(self, obj):
        """
        Method that is run when you click the Calculate button.
        """
        text1 = str(self.entry1.get_text(self.entry1.get_start_iter(),
                                         self.entry1.get_end_iter(), False))
        text2 = str(self.entry2.get_text(self.entry2.get_start_iter(),
                                         self.entry2.get_end_iter(), False))
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
                self.result.set_text(_("Error: invalid entry for expression 1"))
                return
        try:
            val2 = eval(text2)
        except:
            try:
                val2 = parser.parse(text2)
                if not val2.is_valid():
                    raise Exception()
            except:
                self.result.set_text(_("Error: invalid entry for expression 2"))
                return
        if isinstance(val1, Date):
            if isinstance(val2, Date):
                if neg1:
                    self.result.set_text(str(val2 - val1))
                else:
                    self.result.set_text(str(val1 - val2))
            elif isinstance(val2, tuple):
                if neg2:
                    self.result.set_text(str(val1 - val2))
                else:
                    self.result.set_text(str(val1 + val2))
            elif isinstance(val2, int):
                if neg2:
                    self.result.set_text(str(val1 - val2))
                else:
                    self.result.set_text(str(val1 + val2))
        elif isinstance(val1, tuple):
            if isinstance(val2, Date):
                if neg1:
                    self.result.set_text(str(val2 - val1))
                else:
                    self.result.set_text(str(val2 + val1))
            elif isinstance(val2, tuple):
                self.result.set_text(_("Error: at least one expression must be a date"))
            elif isinstance(val2, int):
                self.result.set_text(_("Error: at least one expression must be a date"))
        elif isinstance(val1, int):
            if isinstance(val2, Date):
                if neg1:
                    self.result.set_text(str(val2 - val1))
                else:
                    self.result.set_text(str(val2 + val1))
            elif isinstance(val2, tuple):
                self.result.set_text(_("Error: at least one expression must be a date"))
            elif isinstance(val2, int):
                self.result.set_text(_("Error: at least one expression must be a date"))

    def clear_clicked(self, obj):
        self.entry1.set_text("")
        self.entry2.set_text("")
        self.result.set_text(
            _("Enter an expression in the entries above and click Calculate.\n\n"
              "An expression can be:\n\n"
              "1. a valid Gramps date\n"
              "2. a positive or negative number, representing years\n"
              "3. a positive or negative tuple, representing (years, months, days)\n\n"
              "Note that at least one expression must be a date."
          ))
