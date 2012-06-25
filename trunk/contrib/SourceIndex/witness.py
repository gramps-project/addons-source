# -*- coding: utf-8 -*-
#!/usr/bin/env python
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
import gtk
import os

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------

from gui.glade import Glade
from gui.managedwindow import ManagedWindow
from gui.widgets import MonitoredEntry, MonitoredDate
from gui.plug import tool
import gen.datehandler

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).ugettext

# Handlers and signal class

class GtkHandlers:
    def on_quit_clicked(event):
        print('quit')
        gtk.main_quit()
        
    def on_ok_clicked(event):
        print('save')
        gtk.main_save()
        

class Witness(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        
        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate,[], self.__class__)
        
        #base = os.path.dirname(__file__)
        glade_file = "witness.glade"

        self.top = Glade()
        window = self.top.toplevel
        self.set_window(window, None, glade_file)
        
        self.ok_button = self.top.get_object('ok')
        self.quit_button = self.top.get_object('cancel')
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
               
        self.window.show()
                                
    def __getitem__(self, key):
        return self.glade.get_widget(key)

    def _setup_fields(self):
        self.wname   = MonitoredEntry(
            self.top.get_object("wname"),
            self.obj.set_rinfo,
            self.obj.get_rinfo,
            self.db.readonly)
        
        self.wfname  = MonitoredEntry(
            self.top.get_object("wfname"),
            self.obj.set_rdate,
            self.obj.get_rdate,
            self.db.readonly)
        
        self.wage  = MonitoredEntry(
            self.top.get_object("wage"),
            self.obj.set_rid,
            self.obj.get_rid,
            self.db.readonly)
        
        self.worig  = MonitoredEntry(
            self.top.get_object("worig"),
            self.obj.set_ba,
            self.obj.get_ba,
            self.db.readonly)
        
        self.woccu  = MonitoredEntry(
            self.top.get_object("woccu"),
            self.obj.set_bid,
            self.obj.get_bid,
            self.db.readonly)
        
        self.wlive  = MonitoredEntry(
            self.top.get_object("wlive"),
            self.obj.set_bref,
            self.obj.get_bref,
            self.db.readonly)
        
        self.wrelation  = MonitoredEntry(
            self.top.get_object("wrelation"),
            self.obj.set_bvol,
            self.obj.get_bvol,
            self.db.readonly)
        

class WitnessOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
