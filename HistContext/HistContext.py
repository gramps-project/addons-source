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

#----------------------------------------------------------------------------
"""
    Historical Context - a plugin for showing historical events
    Will show the person in a historical context
    """

# File: HistContext.py
#from gramps.gen.plug import Gramplet

import os
import logging
import glob
import gi
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback)
from gramps.gen.config import config as configman
from gramps.gui.display import display_url
from gramps.gui.dialog import ErrorDialog
from gramps.gen.plug.menu import EnumeratedListOption,BooleanOption,StringOption
from gi.repository import  Pango
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------

local_log = logging.getLogger('HistContext')
local_log.setLevel(logging.WARNING)

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
lang = glocale.lang
local_log.info('Sprog = %s',lang)
config = configman.register_manager("HistContext/HistContext")
config.register("myopt.filter_text" ,"String in beginning of text")
config.register("myopt.use_filter",False);
config.register("myopt.hide_outside_span",True)
config.register("myopt.files", 'custom_v1_0.txt')
config.register("myopt.fg_sel_col", '#000000')
config.register("myopt.bg_sel_col", '#ffffff')
config.register("myopt.fg_usel_col", '#000000')
config.register("myopt.bg_usel_col", '#ededed')

class HistContext(Gramplet):
    """
    class for showing a timeline
    """
    def init(self):
        self.model = Gtk.ListStore(str, str, str,str,str)
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()
        self.model.clear()
        config.load();


    def build_options(self):
        """
        Build the configuration options.
        """
        files = []

        self.opts = []

        name = _("Filter string ")
        opt = StringOption(name, self.__start_filter_st)
        self.opts.append(opt)
        name = _("Use filter ")
        opt = BooleanOption(name,self.__use_filter)
        self.opts.append(opt)
        name =_("Hide outside life span ")
        opt = BooleanOption(name,self.__hide_it)
        self.opts.append(opt)
        name = _("Files")
        flnam = os.path.join(os.path.dirname(__file__), '*.txt')
        files = [f for f in glob.glob(flnam)]
        opt = EnumeratedListOption(name,self.__sel_file)
        for filnm in files:
            opt.add_item(filnm,os.path.basename(filnm))
        self.opts.append(opt)
        name =_("Foreground color items in lifespan")
        opt = StringOption(name,self.__fg_sel)
        self.opts.append(opt)
        name =_("Background color items in lifespan")
        opt = StringOption(name,self.__bg_sel)
        self.opts.append(opt)
        name =_("Foreground color items outside lifespan")
        opt = StringOption(name,self.__fg_not_sel)
        self.opts.append(opt)
        name =_("Background color items outside lifespan")
        opt = StringOption(name,self.__bg_not_sel)
        self.opts.append(opt)
        if self.dbstate.db.is_open():
            for tag_handle in self.dbstate.db.get_tag_handles(sort_handles=True):
                tag = self.dbstate.db.get_tag_from_handle(tag_handle)
                tag_name = tag.get_name()
        list(map(self.add_option, self.opts))

    def save_options(self):
        """
        Save gramplet configuration data.
        """
        self.__start_filter_st = self.opts[0].get_value()
        self.__use_filter = self.opts[1].get_value()
        self.__hide_it = self.opts[2].get_value()
        self.__sel_file = self.opts[3].get_value()
        self.__fg_sel = self.opts[4].get_value()
        self.__bg_sel = self.opts[5].get_value()
        self.__fg_not_sel = self.opts[6].get_value()
        self.__bg_not_sel = self.opts[7].get_value()
        local_log.info('1 stored Filename = %s',self.__sel_file)
        config.set("myopt.filter_text",self.__start_filter_st)
        config.set("myopt.use_filter",self.__use_filter)
        config.set("myopt.hide_outside_span",self.__hide_it)
        config.set("myopt.files",self.__sel_file)
        config.set("myopt.fg_sel_col",self.__fg_sel)
        config.set("myopt.bg_sel_col",self.__bg_sel)
        config.set("myopt.fg_usel_col",self.__fg_not_sel)
        config.set("myopt.bg_usel_col",self.__bg_not_sel)
        config.save()

    def save_update_options(self, obj):
        """
        Save a gramplet's options to file.
        """
        self.save_options()
        local_log.info('3 stored Filename = %s',self.__sel_file)
        self.update()

    def on_load(self):
        """
        Load stored configuration data.
        """
        local_log.info('Antal = %d',len(self.gui.data))
        self.__start_filter_st = config.get("myopt.filter_text")
        self.__use_filter =  config.get("myopt.use_filter")
        self.__hide_it =  config.get("myopt.hide_outside_span")
        self.__sel_file =  config.get("myopt.files")
        self.__fg_sel =  config.get("myopt.fg_sel_col")
        self.__bg_sel = config.get("myopt.bg_sel_col")
        self.__fg_not_sel = config.get("myopt.fg_usel_col")
        self.__bg_not_sel = config.get("myopt.bg_usel_col")
        local_log.info('2 stored Filename = %s',self.__sel_file)


    def get_birth_year(self):
        """
        returning the years of birth and death of the active person
        """
        birthyear = 0
        deathyear = 0
        active_person = self.get_active_object("Person")
        if active_person:
#            navn = active_person.get_primary_name().get_name()
            birth = get_birth_or_fallback(self.dbstate.db, active_person)
            if birth:
                birthdate = birth.get_date_object()
                if birthdate:
                    birthyear = birthdate.to_calendar("gregorian").get_year()
                local_log.info ("Født: %s",birthyear)
            death = get_death_or_fallback(self.dbstate.db, active_person)
            if death:
                deathdate = death.get_date_object()
                if deathdate:
                    deathyear = deathdate.to_calendar("gregorian").get_year()
                    local_log.info ("Død: %s",deathyear)

        else:
            local_log.info ("no active person")
        if (birthyear > 0) and (deathyear == 0):
            deathyear = birthyear+100
        if (deathyear > 0) and (birthyear == 0):
            birthyear = deathyear - 100
        return birthyear, deathyear

    def load_file(self,flnm):
        """
        loading the file into the treeview
        """
        local_log.info('FILENANME %s',flnm)
        birthyear,deathyear = self.get_birth_year()
        linenbr = 0
        with open(flnm,encoding='utf-8') as myfile:
            for line in myfile:
                linenbr += 1
                line = line.rstrip()+';'
                words = line.split(';')
                if len(words) != 5:
                    if len(line) > 10:
                        errormessage = _(': not four semicolons in : "')+line+'i" File: '+flnm
                        errormessage = str(linenbr)+errormessage
                        ErrorDialog(_('Error:'),errormessage)
                else:
                    words[2] = words[2].replace('"','')
                    if words[1] == '':
                        end_year = words[0]
                    else:
                        end_year = words[1]

                    if ((int(words[0]) >= int(birthyear)) and (int(words[0]) <= int(deathyear))) or \
                     ((int(end_year) >= int(birthyear)) and (int(end_year) <= int(deathyear))):
                        mytupple = (words[0],words[1],words[2],words[3],self.__fg_sel,self.__bg_sel)
                        hide_this = False
                    else:
                        hide_this = self.__hide_it
                        mytupple = (words[0],words[1],words[2],words[3],self.__fg_not_sel,self.__bg_not_sel)
                    if not hide_this:
                        if  self.__use_filter:
                            if not words[2].startswith(self.__start_filter_st):
                                local_log.info('appending %s',words[2])
                                self.model.append(mytupple)
                        else:
                            local_log.info('appending %s',words[2])
                            self.model.append(mytupple)



    def main(self):
        local_log.info('testing string %s ',self.__start_filter_st)
        local_log.info('testing boolean %r ',self.__use_filter)
        self.model.clear()
        flnm = self.__sel_file
        if not os.path.exists(flnm):
            flnm =  os.path.join(os.path.dirname(__file__), 'default'+'_data_v1_0.txt')

        if os.path.exists(flnm):
            if os.path.isfile(flnm):
                self.load_file(flnm)
            else:
                self.set_text('No file '+flnm)
        else:
            self.set_text('No path '+flnm)
        def_flnm = os.path.join(os.path.dirname(__file__), 'custom_v1_0.txt')
        if flnm != def_flnm:
            if os.path.exists(def_flnm):
                if os.path.isfile(def_flnm):
                    self.load_file(def_flnm)

    def active_changed(self, handle):
        """
        Called when the active person is changed.
        """
        local_log.info('Active changed')
        self.update()

    def act(self,tree_view,path, column):
        """
        Called when the user double-click a row
        """
        tree_iter = self.model.get_iter(path)
        url = self.model.get_value(tree_iter, 3)
        if url.startswith("https://"):
            display_url(url)
        else:
            errormessage = _('Cannot open URL: ')+url
            ErrorDialog(_('Error:'),errormessage)




    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip = _("Double click row to follow link")
        self.set_tooltip(tip)
        self.model = Gtk.ListStore(str,str,str,str,str,str)
        top = Gtk.TreeView()
        top.connect("row-activated", self.act)
        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)

        column = Gtk.TreeViewColumn(_('From'), renderer, text=0,foreground=4,background=5)
        column.set_expand(False)
        column.set_resizable(True)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(50)
        column.set_sort_column_id(0)
        top.append_column(column)
        renderer = Gtk.CellRendererText()

        column = Gtk.TreeViewColumn(_('To'), renderer, text=1,foreground=4,background=5)
        column.set_sort_column_id(1)
        column.set_fixed_width(50)
        top.append_column(column)

        column = Gtk.TreeViewColumn(_('Text'), renderer, text=2,foreground=4,background=5)
        column.set_sort_column_id(2)
        column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
        top.append_column(column)

#        column = Gtk.TreeViewColumn(_('Link'), renderer, text=3,foreground=4,background=5)
#        column.set_sort_column_id(3)
#        column.set_fixed_width(150)
#        top.append_column(column)
        self.model.set_sort_column_id(0,Gtk.SortType.ASCENDING)
        top.set_model(self.model)
        return top
