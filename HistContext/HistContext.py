#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024 Kaj Mikkelsen <kmi@vgdata.dk>
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

# ----------------------------------------------------------------------------
"""
    Historical Context - a plugin for showing historical events
    Will show the person in a historical context
    """

# File: HistContext.py
# from gramps.gen.plug import Gramplet

import os
import logging
import glob
import gi
import gramps.gen.utils.alive as est

# from gramps.gen.utils.alive import update_constants
from gramps.gen.utils.alive import probably_alive_range
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.version import VERSION as GRAMPSVERSION, VERSION_TUPLE
from gramps.gen.datehandler import parser
from gramps.gen.lib.date import Today

# from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.config import config as configman
from gramps.gui.display import display_url
from gramps.gui.dialog import ErrorDialog
from gramps.gen.plug.menu import (
    BooleanOption,
    StringOption,
    BooleanListOption,
    ColorOption,
)

# from gi.repository import Pango

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

# ------------------------------------------------------------------------
#
# GRAMPS modules
#
# ------------------------------------------------------------------------

local_log = logging.getLogger("HistContext")
_level = os.environ.get("GRAMPS_LOG_LEVEL", "WARNING")
if _level == "info":
    local_log.setLevel(logging.INFO)
else:
    local_log.setLevel(logging.WARNING)

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
lang = glocale.lang
local_log.info("Sprog = %s", lang)
show_error = True
# local_log.info("Maximum age = %s",_MAX_AGE_PROB_ALIVE);
_config_file = os.path.join(os.path.dirname(__file__), "HistContext")

config = configman.register_manager(_config_file)
config.register("myopt.filter_text", "Filter out")
config.register("myopt.use_filter", False)
config.register("myopt.show_outside_span", True)
config.register("myopt.files", "default_data_v1_0.txt")
config.register("myopt.fg_sel_col", "#000000")
config.register("myopt.bg_sel_col", "#ffffff")
config.register("myopt.fg_usel_col", "#000000")
config.register("myopt.bg_usel_col", "#ededed")
config.register("myopt.fl_ar", ["default_data_v1_0.txt"])
config.register("myopt.use_full_date", False)


class HistContext(Gramplet):
    """
    class for showing a timeline
    """

    # pylint: disable=too-many-instance-attributes

    def init(self):
        local_log.info("--> dette var init")
        # local_log.info("version: %s",HistContext.)
        #        self.gui.model = Gtk.ListStore(str, str, str, str, str)
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()
        self.model.clear()
        config.load()

    def build_options(self):
        """
        Build the configuration options.
        """

        files = []
        self.opts = []

        name = _("Rows starting with this in the text column will be hidden ")
        opt = StringOption(name, self.__start_filter_st)
        self.opts.append(opt)
        name = _("Use filter ")
        opt = BooleanOption(name, self.__use_filter)
        self.opts.append(opt)
        name = _("Show outside life span ")
        opt = BooleanOption(name, self.__show_it)
        self.opts.append(opt)
        name = _("Use full dates")
        opt = BooleanOption(name, self.__use_full_date)
        self.opts.append(opt)
        name = _("Foreground color items in lifespan")
        opt = ColorOption(name, self.__fg_sel)
        self.opts.append(opt)
        name = _("Background color items in lifespan")
        opt = ColorOption(name, self.__bg_sel)
        self.opts.append(opt)
        name = _("Foreground color items outside lifespan")
        opt = ColorOption(name, self.__fg_not_sel)
        self.opts.append(opt)
        name = _("Background color items outside lifespan")
        opt = ColorOption(name, self.__bg_not_sel)
        self.opts.append(opt)
        flnam = os.path.join(os.path.dirname(__file__), "*.txt")
        files = [f for f in glob.glob(flnam)]
        opt = BooleanListOption(_("Select from files"))
        for filnm in files:
            short_fil_name = os.path.basename(filnm)
            bol_val = short_fil_name in self.__fl_ar
            opt.add_button(os.path.basename(filnm), bol_val)
        self.opts.append(opt)
        list(map(self.add_option, self.opts))

    def save_options(self):
        """
        Save gramplet configuration data.
        """
        # pylint: disable=attribute-defined-outside-init
        self.__start_filter_st = self.opts[0].get_value()
        self.__use_filter = self.opts[1].get_value()
        self.__show_it = self.opts[2].get_value()
        self.__use_full_date = self.opts[3].get_value()
        self.__use_year = not self.__use_full_date
        self.__fg_sel = self.opts[4].get_value()
        self.__bg_sel = self.opts[5].get_value()
        self.__fg_not_sel = self.opts[6].get_value()
        self.__bg_not_sel = self.opts[7].get_value()
        self.__fl_ar = self.opts[8].get_selected()
        config.set("myopt.filter_text", self.__start_filter_st)
        config.set("myopt.use_filter", self.__use_filter)
        config.set("myopt.show_outside_span", self.__show_it)
        config.set("myopt.use_full_date", self.__use_full_date)
        config.set("myopt.fg_sel_col", self.__fg_sel)
        config.set("myopt.bg_sel_col", self.__bg_sel)
        config.set("myopt.fg_usel_col", self.__fg_not_sel)
        config.set("myopt.bg_usel_col", self.__bg_not_sel)
        config.set("myopt.fl_ar", self.__fl_ar)
        config.save()

    def save_update_options(self, obj):
        """
        Save a gramplet's options to file.
        """
        self.save_options()
        self.update()

    def on_load(self):
        """
        Load stored configuration data.
        """
        self.__show_error = True
        local_log.info("Antal = %d", len(self.gui.data))
        self.__start_filter_st = config.get("myopt.filter_text")
        self.__use_filter = config.get("myopt.use_filter")
        self.__show_it = config.get("myopt.show_outside_span")
        self.__use_full_date = config.get("myopt.use_full_date")
        self.__use_year = not self.__use_full_date
        self.__fg_sel = config.get("myopt.fg_sel_col")
        self.__bg_sel = config.get("myopt.bg_sel_col")
        self.__fg_not_sel = config.get("myopt.fg_usel_col")
        self.__bg_not_sel = config.get("myopt.bg_usel_col")
        self.__fl_ar = config.get("myopt.fl_ar")

    #        if self.__fl_ar[0] == "None":
    #           self.__fl_ar[0] = os.path.basename(self.__sel_file)

    def get_birth_year(self):
        """
        returning the years of birth and death of the active person
        """
        birthyear = 0
        deathyear = 0
        active_person = self.get_active_object("Person")
        date1, date2, dummy1, dummy2 = probably_alive_range(
            active_person,
            self.dbstate.db,
            est._MAX_SIB_AGE_DIFF,
            est._MAX_AGE_PROB_ALIVE,
            est._AVG_GENERATION_GAP,
        )

        if date1:
            if self.__use_year:
                birthyear = date1.to_calendar("gregorian").get_year()
            else:
                birthyear = str(date1).replace("-", "")
                if not birthyear[0].isdigit():
                    mydate = birthyear
                    birthyear = date1.to_calendar("gregorian").get_year() * 10000 + 101
                    local_log.info("1 Special date %s %s", birthyear, mydate)
        if date2:
            if self.__use_year:
                deathyear = date2.to_calendar("gregorian").get_year()
            else:
                deathyear = str(date2).replace("-", "")
                if not deathyear[0].isdigit():
                    mydate = deathyear
                    deathyear = date2.to_calendar("gregorian").get_year() * 10000 + 1231
                    local_log.info("2 Special date %s %s", deathyear, mydate)
        local_log.info("Født: %s", birthyear)
        local_log.info("Død: %s", deathyear)
        return birthyear, deathyear

    def find_last_day(self, year_month):
        """ "
        Function wwhich returns the last day of a specific month.
        """
        day = year_month + "-31"
        tst_date = parser.parse(day)
        if not tst_date.is_valid():
            day = year_month + "-30"
            tst_date = parser.parse(day)
            if not tst_date.is_valid():
                day = year_month + "-29"
                tst_date = parser.parse(day)
                if not tst_date.is_valid():
                    day = year_month + "-28"
        return day

    def normalize_date(self, datest, dont_change_valid_dates, start_date):
        """
        function that returns a date in the format we want
        displays an error and sets today as day, if datest is not valid
        also used for returning a date in a sortable fasion
        """
        if len(datest) == 4 and not self.__use_year:
            if start_date:
                datest = datest + "-01-01"
            else:
                datest = datest + "-12-31"
        if len(datest) == 7 and not self.__use_year:
            if start_date:
                datest = datest + "-01"
            else:
                datest = self.find_last_day(datest)
                local_log.info("====> 4 %s ", datest)
        if datest.upper() == "TODAY":
            date1 = Today()
            datest = str(date1)
        else:
            date1 = parser.parse(datest)
        if not date1.is_valid():
            if self.__show_error:
                errormessage = _("Invalid date " + datest)
                errormessage = errormessage + (_(" in line: ")) + str(self.linenbr)
                ErrorDialog(_("Error:"), errormessage)
            self.__show_error = False
            date1 = Today()
            if self.__use_year:
                datest = str(date1.to_calendar("gregorian").get_year())
            else:
                datest = str(date1)

        if self.__use_year:
            new_datest = str(date1.to_calendar("gregorian").get_year())
        else:
            if dont_change_valid_dates:
                new_datest = datest
            else:
                new_datest = parser.parse(datest)
        self.sort_date = str(new_datest).replace("-", "")
        if dont_change_valid_dates and not self.__use_year:
            return datest
        else:
            return new_datest

    def load_file(self, flnm):
        """
        loading the file into the treeview
        """
        local_log.info("FILENANME %s", flnm)
        self.sort_date = ""
        birthyear, deathyear = self.get_birth_year()

        self.linenbr = 0
        with open(flnm, encoding="utf-8") as myfile:
            for line in myfile:
                self.linenbr += 1
                line = line.rstrip() + ";"
                words = line.split(";")
                if len(words) != 5:
                    if len(line) > 10:
                        errormessage = (
                            _(': line does not contain four sections separated by semicolons in : "')
                            + line
                            + 'i" File: '
                            + flnm
                        )
                        errormessage = str(self.linenbr) + errormessage
                        ErrorDialog(_("Error:"), errormessage)
                else:
                    words[0] = self.normalize_date(words[0], True, True)
                    local_sort_date = self.sort_date
                    words[1] = self.normalize_date(words[1], True, False)
                    if words[1] == "0":
                        words[1] = ""
                    words[2] = words[2].replace('"', "")
                    begin_year = str(self.normalize_date(words[0], False, True))
                    local_sort_date = self.sort_date

                    if words[1] == "":
                        end_year = str(self.normalize_date(words[0], False, False))
                    else:
                        end_year = str(self.normalize_date(words[1], False, False))
                    begin_year = begin_year.replace("-", "")
                    end_year = end_year.replace("-", "")

                    if (
                        (int(begin_year) >= int(birthyear))
                        and (int(begin_year) <= int(deathyear))
                    ) or (
                        (int(end_year) >= int(birthyear))
                        and (int(end_year) <= int(deathyear))
                    ):
                        mytupple = (
                            words[0],
                            words[1],
                            words[2],
                            local_sort_date,
                            words[3],
                            self.__fg_sel,
                            self.__bg_sel,
                        )
                        hide_this = False
                    else:
                        hide_this = not self.__show_it
                        mytupple = (
                            words[0],
                            words[1],
                            words[2],
                            local_sort_date,
                            words[3],
                            self.__fg_not_sel,
                            self.__bg_not_sel,
                        )
                    if not hide_this:
                        if self.__use_filter:
                            if not words[2].startswith(self.__start_filter_st):
                                self.model.append(mytupple)
                        else:
                            self.model.append(mytupple)

    def main(self):
        self.model.clear()
        local_log.info("Main kaldet")
        for flnm in self.__fl_ar:
            flnm = os.path.join(os.path.dirname(__file__), flnm)
            if not os.path.exists(flnm):
                flnm = os.path.join(
                    os.path.dirname(__file__), "default" + "_data_v1_0.txt"
                )
            if os.path.exists(flnm):
                if os.path.isfile(flnm):
                    self.load_file(flnm)
                else:
                    self.set_text("No file " + flnm)
            else:
                self.set_text("No path " + flnm)

    def active_changed(self, handle):
        """
        Called when the active person is changed.
        """
        local_log.info("Active changed")
        self.update()

    def act(self, _tree_view, path, _column):
        """
        Called when the user double-click a row
        """
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, 4)
        if url.startswith("https://"):
            display_url(url)
        else:
            errormessage = _("Cannot open URL: ") + url
            ErrorDialog(_("Error:"), errormessage)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        local_log.info("-->build gui")
        tip = _("Double click row to follow link")
        self.set_tooltip(tip)
        # pylint: disable=attribute-defined-outside-init
        # define array from_date, to_date, Eventsdescription, link to internet, sort_date, foreground_colour, backgroud_colour
        # Only first three comlumns are visible
        self.model = Gtk.ListStore(str, str, str, str, str, str, str)
        top = Gtk.TreeView()
        top.connect("row-activated", self.act)
        renderer = Gtk.CellRendererText()

        column = Gtk.TreeViewColumn(
            _("From"), renderer, text=0, foreground=5, background=6
        )
        #        column.set_expand(False)
        #        column.set_resizable(True)
        #        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        #        column.set_fixed_width(50)
        column.set_sort_column_id(0)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        top.append_column(column)

        column = Gtk.TreeViewColumn(
            _("To"), renderer, text=1, foreground=5, background=6
        )
        column.set_sort_column_id(1)
        #        column.set_fixed_width(50)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)

        top.append_column(column)

        column = Gtk.TreeViewColumn(
            _("Text"), renderer, text=2, foreground=5, background=6
        )
        column.set_sort_column_id(2)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        top.append_column(column)

        # column = Gtk.TreeViewColumn(
        #    _("Dato"), renderer, text=3, foreground=5, background=6
        # )
        #        column.set_sort_column_id(3)
        #        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        #        top.append_column(column)

        #        column = Gtk.TreeViewColumn(_('Link'), renderer, text=3,foreground=4,background=5)
        #        column.set_sort_column_id(3)
        #        column.set_fixed_width(150)
        #        top.append_column(column)
        self.model.set_sort_column_id(3, Gtk.SortType.ASCENDING)
        top.set_model(self.model)
        return top
