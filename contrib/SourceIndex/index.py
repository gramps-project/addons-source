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

"""
Provide the dialog and the menu for handling indexes.
"""

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------

import codecs
from gi.repository import Gtk
import sys
import os
from xml.etree import ElementTree
import csv

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------

from gramps.gen.const import USER_PLUGINS
from gramps.gui.glade import Glade
from gramps.gui.managedwindow import GrampsWindowManager, ManagedWindow
from gramps.gui.plug import tool

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).ugettext

# Handlers and signal class

class GladeHandlers():
    """
    Experimental try for event functions via python and .glade files
    """
    
    def on_quit_clicked():
        Gtk.main_quit()
    def on_search_clicked():
        Gtk.main_search()
    def on_remove_clicked():
        Gtk.main_remove()	

#    def search(self,obj):
#        if self.callback:
#            self.callback(self.obj)
#       self.close()
#    def remove(self,obj):
#        if self.callback:
#            self.callback(self.obj)
#       self.close()    


class Index(tool.Tool, ManagedWindow):
    """
    Class for indexes
    """
    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        
        tool.Tool.__init__(self, dbstate, options_class, name)
        ManagedWindow.__init__(self, uistate,[], self.__class__)
        
        #base = os.path.dirname(__file__)
        glade_file = os.path.join(USER_PLUGINS, "SourceIndex", "index.glade")

        self.define_glade('edit_index', glade_file)
        self.set_window(self._gladeobj.toplevel, None, text=None, msg='Index')
        
        self.connect_button('add_b', self.birth_editor)
        self.connect_button('add_m', self.marriage_editor)
        self.connect_button('add_d', self.death_editor)
        self.connect_button('add_c', self.census_editor)
               
        
        #self.window.connect('delete-event', GladeHandlers.on_quit_clicked)
        
        self.window.show()
        
    # happy mixture !
    
    def birth_editor(self, widget, data=None):
        """
        Experimental call of the birth editor (see rather 'birth.py')
        """
        
        glade_file = "birth.glade"
        top = Glade(glade_file)
        b = top.toplevel
        self.set_window(b, title=None, text=glade_file)
        
        self.wit_button = top.get_object('add_wit')
        self.ok_button = top.get_object('ok')
        self.quit_button = top.get_object('cancel')
        #self.wit_button.connect('clicked', GtkHandlers.on_witness_clicked)
        
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
        
        #add_item()
        #close_item()
        #close_track()
        
        #b.connect('delete-event', GladeHandlers.on_quit_clicked)
    
        #b.hide()
        b.show()
        
    def death_editor(self, widget, data=None):
        """
        Experimental call of the death editor (see rather 'death.py')
        """
        
        glade_file = "death.glade"
        top = Glade(glade_file)
        d = top.toplevel
        self.set_window(d, title=None, text=glade_file)
        
        self.wit_button = top.get_object('add_wit')
        self.ok_button = top.get_object('ok')
        self.quit_button = top.get_object('cancel')
        #self.wit_button.connect('clicked', GtkHandlers.on_witness_clicked)
        
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
    
        d.hide()
        #d.show()
        #d.connect("destroy", self.close)
    
    def marriage_editor(self, widget, data=None):
        """
        Experimental call of the marriage editor (see rather 'marriage.py')
        """
        
        glade_file = "marriage.glade"
        top = Glade(glade_file)
        m = top.toplevel
        self.set_window(m, title=None, text=glade_file)
        
        self.wit_button = top.get_object('add_wit')
        self.ok_button = top.get_object('ok')
        self.quit_button = top.get_object('cancel')
        #self.wit_button.connect('clicked', GtkHandlers.on_witness_clicked)
        
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
    
        m.hide()
        #m.show()
        #m.connect("destroy", self.close)
    
    def census_editor(self, widget, data=None):
        """
        Experimental call of the census editor (see rather 'census.py')
        """
        
        glade_file = "census.glade"
        top = Glade(glade_file)
        c = top.toplevel
        self.set_window(c, title=None, text=glade_file)
        
        self.ok_button = top.get_object('ok')
        self.quit_button = top.get_object('cancel')
        
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
    
        c.hide()
        #c.show()
        #c.connect("destroy", self.close)
                

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

    
    def read_xml(self, filename):
        """
        Load and parse the XML filename
        """
              
        tree = ElementTree.parse(filename)
        root = tree.getroot()
        
        self.walk_tree(root, 0)
        
        # others parsers and xml stuff
        
        #from libgrampsxml import GRAMPS_XML_VERSION
        
        #import libxml2
        #import libxslt
        
        #from xml.parsers.expat
        
        #from xml.dom
        
        #from xml.sax
        #from _xmlplus.sax
    
    
    def open_indexes(self):
        """
        etree provided by python (default)
        lxml for performances (if present)
        """
        
        try:
            from lxml import etree as ElementTree
        except ImportError, e:
            try:
                from xml.etree import ElementTree
            except ImportError, e:
                print '***'
                print _('*** Error: Must install either ElementTree or lxml.')
                print '***'
                raise ImportError, _('must install either ElementTree or lxml')

        self.indexes()
        
    
    def indexes(self):
        """
        Indexes could be an addition of XML files.
        We can imagine ('birth.xml' + 'death.xml' + 'marriage.xml' 
        + census.xml), 'witness.xml' could be an other table/file 
        (relation) or content could be included into above files!
        
        'Load indexes' means to load ordered tables, search environment
        """
        
        files = f.endswith('.xml')
        parent_path = os.path.join(USER_PLUGINS, 'SourceIndex')
        
    
    def save_indexes(self):
        """
        Save into one file (indexes collection) with its extension
        """
        pass
        
        
    def load_indexes(self):
        """
        Load an indexes collection
        """
        pass
        

class CSV:
    """
    Import indexes via the CSV file format
    """
    pass
        

class IndexOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
