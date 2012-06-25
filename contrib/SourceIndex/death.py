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

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------

import codecs
import gtk
import sys
import os
from xml.etree import ElementTree

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------

import const
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
        
    def on_witness_clicked(event):
        print(event)
        from witness import Witness
        Witness.window.show()
        
    def on_date_clicked(event):
        pass
        
    def on_note_clicked(event):
        pass
        
    def on_name_clicked(event):
        pass

class DeathIndex(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        
        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate,[], self.__class__)
        
        #base = os.path.dirname(__file__)
        glade_file = "death.glade"

        self.top = Glade()
        window = self.top.toplevel
        self.set_window(window, None, glade_file)
        
        self.wit_button = self.top.get_object('add_wit')
        self.ok_button = self.top.get_object('ok')
        self.quit_button = self.top.get_object('cancel')
        #self.wit_button.connect('clicked', GtkHandlers.on_witness_clicked)
        
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
            
        self.window.show()
        
        # tests
        filename = os.path.join(const.USER_PLUGINS, 'SourceIndex', 'test_death.xml')
        self.write_xml(
            filename, 
            'D0001', 
            'DATE', 
            'NOM'
            )
        self.parse_xml(filename)
                        
    def __getitem__(self, key):
        return self.glade.get_widget(key)

    def _setup_fields(self):
        self.rinfo   = MonitoredEntry(
            self.top.get_object("rinfo"),
            self.obj.set_rinfo,
            self.obj.get_rinfo,
            self.db.readonly)
        
        self.rdate  = MonitoredEntry(
            self.top.get_object("rdate"),
            self.obj.set_rdate,
            self.obj.get_rdate,
            self.db.readonly)
        
        self.rid  = MonitoredEntry(
            self.top.get_object("rid"),
            self.obj.set_rid,
            self.obj.get_rid,
            self.db.readonly)
        
        self.aname  = MonitoredEntry(
            self.top.get_object("aname"),
            self.obj.set_aname,
            self.obj.get_aname,
            self.db.readonly)
        
        self.aid  = MonitoredEntry(
            self.top.get_object("aid"),
            self.obj.set_aid,
            self.obj.get_aid,
            self.db.readonly)
        
        self.aref  = MonitoredEntry(
            self.top.get_object("aref"),
            self.obj.set_aref,
            self.obj.get_aref,
            self.db.readonly)
        
        self.avol  = MonitoredEntry(
            self.top.get_object("avol"),
            self.obj.set_avol,
            self.obj.get_avol,
            self.db.readonly)
        
        self.gen  = MonitoredEntry(
            self.top.get_object("gen"),
            self.obj.set_gen,
            self.obj.get_gen,
            self.db.readonly)
            
        self.pname  = MonitoredEntry(
            self.top.get_object("pname"),
            self.obj.set_pname,
            self.obj.get_pname,
            self.db.readonly)
                
        self.pbdate  = MonitoredEntry(
            self.top.get_object("pbdate"),
            self.obj.set_pbdate,
            self.obj.get_pbdate,
            self.db.readonly)
        
        self.pfname  = MonitoredEntry(
            self.top.get_object("pfname"),
            self.obj.set_pfname,
            self.obj.get_pfname,
            self.db.readonly)
        
        self.pdate  = MonitoredEntry(
            self.top.get_object("pdate"),
            self.obj.set_pdate,
            self.obj.get_pdate,
            self.db.readonly)
        
        self.pnote  = MonitoredEntry(
            self.top.get_object("pnote"),
            self.obj.set_pnote,
            self.obj.get_pnote,
            self.db.readonly)
        
        self.fname  = MonitoredEntry(
            self.top.get_object("fname"),
            self.obj.set_fname,
            self.obj.get_fname,
            self.db.readonly)
        
        self.ffname  = MonitoredEntry(
            self.top.get_object("ffname"),
            self.obj.set_ffname,
            self.obj.get_ffname,
            self.db.readonly)
        
        self.fage = MonitoredEntry(
            self.top.get_object("fage"),
            self.obj.set_fage,
            self.obj.get_fage,
            self.db.readonly)
        
        self.forig  = MonitoredEntry(
            self.top.get_object("forig"),
            self.obj.set_forig,
            self.obj.get_forig,
            self.db.readonly)
        
        self.foccu  = MonitoredEntry(
            self.top.get_object("foccu"),
            self.obj.set_foccu,
            self.obj.get_foccu,
            self.db.readonly)
            
        self.flive  = MonitoredEntry(
            self.top.get_object("flive"),
            self.obj.set_flive,
            self.obj.get_flive,
            self.db.readonly)
        
        self.mname  = MonitoredEntry(
            self.top.get_object("mname"),
            self.obj.set_mname,
            self.obj.get_mname,
            self.db.readonly)
        
        self.mfname  = MonitoredEntry(
            self.top.get_object("mfname"),
            self.obj.set_mfname,
            self.obj.get_mfname,
            self.db.readonly)
        
        self.mage  = MonitoredEntry(
            self.top.get_object("mage"),
            self.obj.set_mage,
            self.obj.get_mage,
            self.db.readonly)
        
        self.morigin  = MonitoredEntry(
            self.top.get_object("morigin"),
            self.obj.set_morigin,
            self.obj.get_morigin,
            self.db.readonly)
        
        self.moccu  = MonitoredEntry(
            self.top.get_object("moccu"),
            self.obj.set_moccu,
            self.obj.get_moccu,
            self.db.readonly)
        
        self.mlive  = MonitoredEntry(
            self.top.get_object("mlive"),
            self.obj.set_mlive,
            self.obj.get_mlive,
            self.db.readonly)
        
        self.msname  = MonitoredEntry(
            self.top.get_object("msname"),
            self.obj.set_msname,
            self.obj.get_msname,
            self.db.readonly)
        
        self.mdpdate  = MonitoredEntry(
            self.top.get_object("mdpdate"),
            self.obj.set_mdpdate,
            self.obj.get_mdpdate,
            self.db.readonly)
        
        self.mmdate  = MonitoredEntry(
            self.top.get_object("mmdate"),
            self.obj.set_mmdate,
            self.obj.get_mmdate,
            self.db.readonly)
        
        self.mdplace  = MonitoredEntry(
            self.top.get_object("mdplace"),
            self.obj.set_mdplace,
            self.obj.get_mdplace,
            self.db.readonly)
        
        self.mmplace  = MonitoredEntry(
            self.top.get_object("mmplace"),
            self.obj.set_mmplace,
            self.obj.get_mmplace,
            self.db.readonly)
            
        self.mnote  = MonitoredEntry(
            self.top.get_object("mnote"),
            self.obj.set_mnote,
            self.obj.get_mnote,
            self.db.readonly)
            
        self.spname  = MonitoredEntry(
            self.top.get_object("spname"),
            self.obj.set_spname,
            self.obj.get_spname,
            self.db.readonly)
        
        self.spmdate  = MonitoredEntry(
            self.top.get_object("spmdate"),
            self.obj.set_spmdate,
            self.obj.get_spmdate,
            self.db.readonly)
            
        self.spmplace  = MonitoredEntry(
            self.top.get_object("spmplace"),
            self.obj.set_spmplace,
            self.obj.get_spmplace,
            self.db.readonly)
            
    def call_witness(self, obj):
        pass
        
        
    # PyXMLFAQ -- Python XML Frequently Asked Questions
    # Author: 	Dave Kuhlman
    # dkuhlman@rexx.com
    # http://www.rexx.com/~dkuhlman
           
    def walk_tree(self, node, level):
        fill = self.show_level(level)
        print '%sElement name: %s' % (fill, node.tag, )
        for (name, value) in node.attrib.items():
            print '%s    Attr -- Name: %s  Value: %s' % (fill, name, value,)
        if node.attrib.get('ID') is not None:
            print '%s    ID: %s' % (fill, node.attrib.get('ID').value, )
        children = node.getchildren()
        for child in children:
            self.walk_tree(child, level + 1)


    def show_level(self, level):
        s1 = '\t' * level
        return s1

        
    def parse_xml(self, filename):
        
        tree = ElementTree.parse(filename)
        root = tree.getroot()
        self.walk_tree(root, 0)

                
    def write_xml(self, filename, id , date, surname):

        node = ElementTree.Element('death')
        node.set('id', id)
        node.set('collection', filename)
        node.set('uri', 'file://..')
        node1 = ElementTree.SubElement(node, 'date')
        node1.text = date
        node1 = ElementTree.SubElement(node, 'surname')
        node1.text = surname
        
        outfile = open(filename, 'w')
        self.outfile = codecs.getwriter("utf8")(outfile)
        
        self.outfile.write(ElementTree.tostring(node, encoding="UTF-8"))
        self.outfile.close()

class DeathIndexOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
