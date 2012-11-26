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
from gi.repository import Gtk
import sys
import os
from xml.etree import ElementTree

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------

from gramps.gen.const import USER_PLUGINS
from gramps.gui.glade import Glade
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.widgets import MonitoredEntry, MonitoredDate, MonitoredText, MonitoredType
from gramps.gui.editors.objectentries import ObjEntry, PlaceEntry, MediaEntry, NoteEntry
from gramps.gui.plug import tool
from gramps.gen.lib import date
import gramps.gen.datehandler

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).gettext

import gramps.gen.constfunc

# code cherrytree

class GladeWidgetsWrapper:
    """
    Handles the retrieval of glade widgets
    """

    def __init__(self, glade_file_path, gui_instance):
        try:
            self.glade_widgets = Gtk.Builder()
            self.glade_widgets.set_translation_domain('gramps')
            self.glade_widgets.add_from_file(glade_file_path)
            self.glade_widgets.connect_signals(gui_instance)
        except: print("Failed to load the glade file")

    def __getitem__(self, key):
        """Gives us the ability to do: wrapper['widget_name'].action()"""
        return self.glade_widgets.get_object(key)

    def __getattr__(self, attr):
        """Gives us the ability to do: wrapper.widget_name.action()"""
        new_widget = self.glade_widgets.get_object(attr)
        if new_widget is None: raise AttributeError, 'Widget %r not found' % attr
        setattr(self, attr, new_widget)
        return new_widget

# Handlers and signal class

class GtkHandlers:
    """
    Experimental try for event functions via python and .glade files
    """
    def on_quit_clicked(widget, data=None):
        print('quit')
        Gtk.main_quit()
        
    def on_ok_clicked(widget, data=None):
        print('save')
        Gtk.main_save()
        
    def on_witness_clicked( widget, data=None):
        print(event)
        #from witness import Witness
        #Witness.window.show()
        
    def on_date_clicked(widget, data=None):
        pass
        
    def on_note_clicked(widget, data=None):
        pass
        
    def on_name_clicked(self, widget, data=None):
        pass
        

def words_from_note(self):
    """
    Experimental import (semantic, ontology, etc ...) via note editors
    """
    pass
    

class BirthIndex(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        
        self.label = _('Sources Index')
        self.base = os.path.dirname(__file__)
        
        ManagedWindow.__init__(self, uistate,[], self.__class__)
        self.set_window(Gtk.Window(),Gtk.Label(),'')
        
        tool.Tool.__init__(self, dbstate, options_class, name)
        
        glade_file = os.path.join(USER_PLUGINS, "SourceIndex", "birth.glade")
        
        if gramps.gen.constfunc.lin():
            import locale
            locale.setlocale(locale.LC_ALL, '')
            # This is needed to make gtk.Builder work by specifying the
            # translations directory
            locale.bindtextdomain("addon", self.base + "/locale")
            
            self.glade = Gtk.Builder()
            self.glade.set_translation_domain("addon")
            
            #self.glade = GladeWidgetsWrapper(glade_file, self)
            self.glade.add_from_file(glade_file)
            
            from gi.repository import GObject
            GObject.GObject.__init__(self.glade)
                      
            window = self.glade.get_object('edit_birth')
                
            self.set_window(window, self.glade.get_object('title'), self.label)
            
            #self.wit_button = self.glade.get_object('add_wit')
            self.ok_button = self.glade.get_object('ok')
            self.quit_button = self.glade.get_object('cancel')
                        
        else:

            # Glade class from gui/glade.py and gui/managedwindow.py
            self.glade = Glade(glade_file)
            #self.glade = GladeWidgetsWrapper(glade_file, self)
       
            self.top = Glade()
            window = self.top.toplevel
            self.set_window(window, None, glade_file)
        
            #self.wit_button = self.top.get_object('add_wit')
            self.ok_button = self.top.get_object('ok')
            self.quit_button = self.top.get_object('cancel')
            
        #self.wit_button.connect('clicked', GtkHandlers.on_witness_clicked)
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
        
        #GObject.__init__() takes exactly 0 arguments
        #self.text = Gtk.EntryBuffer('Gtk.Entry._get...', 5)
               
        # tests
        path = os.path.join(USER_PLUGINS, 'SourceIndex')
        self.rinfo = 'Library of usercity'
        callnumber = 'BX42_xzertra58364' # inherited or seizure
        source_handle = '_123456789' # or call the source title
        citation_handle = '_987654321'  # or call any id
        self.avol = 'Page 105 n°56'
        self.aname = 'Civil book (Birth 1650)'
        separator = 'ↄ'
        name = self.rinfo + separator + callnumber +  separator \
        + source_handle + separator + citation_handle + separator \
        + self.avol + separator + self.aname + '.xml'
        filename = os.path.join(path, name)
        self.write_xml(
            filename,
            'B0001',
            'DATE', 
            'PRÉNOM'
            )
            
        #self._setup_fields()
        
        self.window.show()
            
        self.parse_xml(filename)
        
                        
    def _setup_fields(self):
        '''
        Gramps XML storage means ability to also import/manage alone records
        /!\ some attributes are translated keys
        see data_item keys and eventref types of attribute
        '''
        
        #/database/repositories/repository/rname/text()
        self.rinfo   = MonitoredText(
            self.top.get_object("rinfo"),
            self.top.get_object("rinfo").set_text(self.rinfo),
            self.top.get_object("rinfo").get_text,
            True)
                    
        # date of transcription/search
        self.rdate = MonitoredText(
            self.top.get_object("rdate"),
            self.top.get_object("rdate").set_text(str(date.Today())),
            #self.top.get_object("rdate").get_date_object(),
            #uistate,
            #track,
            True)
        
        #/database/repositories/repository/@handle
        self.rid  = MonitoredEntry(
            self.top.get_object("rid"),
            self.top.get_object("rid").set_text,
            self.top.get_object("rid").get_text,
            True)
        
        #/database/sources/source/stitle/text()
        self.aname  = MonitoredText(
            self.top.get_object("aname"),
            self.top.get_object("aname").set_text(self.aname),
            self.top.get_object("aname").get_text,
            True)
        
        #/database/sources/source/@handle
        self.aid  = MonitoredEntry(
            self.top.get_object("aid"),
            self.top.get_object("aid").set_text,
            self.top.get_object("aid").get_text,
            True)
        
        #/database/citations/citation/@handle
        self.aref  = MonitoredEntry(
            self.top.get_object("aref"),
            self.top.get_object("aref").set_text,
            self.top.get_object("aref").get_text,
            True)
            
        #/database/citations/citation/dateval/@val
        #self.adate = MonitoredDate(
            #self.top.get_object("adate"),
            #self.top.get_object("adate").set_text,
            #self.top.get_object("adate").get_date_object(),
            #uistate,
            #track,
            #True)
        
        #/database/citations/citation/page
        # hardcoded /database/citations/citation/confidence
        self.avol  = MonitoredEntry(
            self.top.get_object("avol"),
            self.top.get_object("avol").set_text(self.avol),
            self.top.get_object("avol").get_text,
            True)
        
        #/database/people/person/gender
        #self.gen  = MonitoredType(
            #self.top.get_object("gen"),
            #self.top.get_object("gen").set_text,
            #self.top.get_object("gen").get_text,
            #True)
            
        #/database/people/person/childof/@hlink
        #/database/people/person/name/surname/surname/text()
        self.pname  = MonitoredEntry(
            self.top.get_object("pname"),
            self.top.get_object("pname").set_text,
            self.top.get_object("pname").get_text,
            True)
        
        #/database/people/person/name/first/text()
        self.pfname  = MonitoredText(
            self.top.get_object("pfname"),
            self.top.get_object("pfname").set_text,
            self.top.get_object("pfname").get_text,
            True)
                    
        #/database/people/person/eventref/@hlink
        #/database/events/event/dateval/@val 
        #self.pdate = MonitoredDate(
            #self.top.get_object("pdate"),
            #self.top.get_object("pdate_stat"), 
            #self.top.get_object("pdate").get_date_object(),
            #uistate,
            #track,
            #True)
            
        #/database/people/person/eventref/@hlink
        #/database/events/event/place/@hlink
        #/database/places/placeobj/ptitle/text()
        #self.pplace  = PlaceEntry(
            #dbstate, uistate, track,
            #self.top.get_object("pplace"),
            #self.top.get_object("pplace").set_place_handle,
            #self.top.get_object("pplace").get_place_handle,
            #self.top.get_object('add_del_place'),
            #self.top.get_object('select_place'))
        
        #/database/people/person/eventref/noteref/@hlink
        #/database/notes/note/text/text()
        #self.pnote  = NoteEntry(
            #dbstate, uistate, track,
            #self.top.get_object("pnote"),
            #self.top.get_object("pnote").set_note_handle,
            #self.top.get_object("pnote").get_note_handle,
            #self.top.get_object('add_del_note'),
            #self.top.get_object('select_note'))
        
        #/database/objects/object/file/@src
        #self.fname  = MediaEntry(
            #dbstate, uistate, track,
            #self.top.get_object("fname"),
            #self.top.get_object("fname").set_media_path,
            #self.top.get_object("fname").get_media_path,
            #self.top.get_object('add_del_path'),
            #self.top.get_object('select_path'))
        
        #/database/people/person/parentin/@hlink
        #/database/people/person/name/first/text()
        self.ffname  = MonitoredText(
            self.top.get_object("ffname"),
            self.top.get_object("ffname").set_text,
            self.top.get_object("ffname").get_text,
            True)
        
        #/database/people/person/eventref/attribute/@type
        #/database/people/person/eventref/attribute/@value
        self.fage = MonitoredEntry(
            self.top.get_object("fage"),
            self.top.get_object("fage").set_text,
            self.top.get_object("fage").get_text,
            True)
        
        #/database/people/person/eventref/@hlink
        #/database/events/event/place/@hlink
        #/database/places/placeobj/ptitle/text()
        #self.forig  = PlaceEntry(
            #dbstate, uistate, track,
            #self.top.get_object("forig"),
            #self.top.get_object("forig").set_place_handle,
            #self.top.get_object("forig").get_place_handle,
            #self.top.get_object('add_del_place'),
            #self.top.get_object('select_place'))
        
        #/database/people/person/eventref/@hlink
        #/database/events/event/description/text()
        self.foccu  = MonitoredEntry(
            self.top.get_object("foccu"),
            self.top.get_object("foccu").set_text,
            self.top.get_object("foccu").get_text,
            True)
        
        #/database/people/person/eventref/@hlink
        #/database/events/event/dateval/@val
        #/database/events/event/description/text()
        self.flive  = MonitoredEntry(
            self.top.get_object("flive"),
            self.top.get_object("flive").set_text,
            self.top.get_object("flive").get_text,
            True)
        
        #/database/people/person/parentin/@hlink
        #/database/people/person/name/first/text()
        self.mname  = MonitoredText(
            self.top.get_object("mname"),
            self.top.get_object("mname").set_text,
            self.top.get_object("mname").get_text,
            True)
        
        self.mfname  = MonitoredText(
            self.top.get_object("mfname"),
            self.top.get_object("mfname").set_text,
            self.top.get_object("mfname").get_text,
            True)
        
        self.mage  = MonitoredText(
            self.top.get_object("mage"),
            self.top.get_object("mage").set_text,
            self.top.get_object("mage").get_text,
            True)
        
        #self.morigin  = PlaceEntry(
            #dbstate, uistate, track,
            #self.top.get_object("morigin"),
            #self.top.get_object("morigin").set_place_handle,
            #self.top.get_object("morigin").get_place_handle,
            #self.top.get_object('add_del_place'),
            #self.top.get_object('select_place'))
        
        self.moccu  = MonitoredText(
            self.top.get_object("moccu"),
            self.top.get_object("moccu").set_text,
            self.top.get_object("moccu").get_text,
            True)
        
        self.mlive  = MonitoredEntry(
            self.top.get_object("mlive"),
            self.top.get_object("mlive").set_text,
            self.top.get_object("mlive").get_text,
            True)
        
        self.msname  = MonitoredText(
            self.top.get_object("msname"),
            self.top.get_object("msname").set_text,
            self.top.get_object("msname").get_text,
            True)
                    
        #self.mdpdate = MonitoredDate(
            #self.top.get_object("mdpdate"),
            #self.top.get_object("mdpdate_stat"), 
            #self.top.get_object("mdpdate").get_date_object(),
            #uistate,
            #track,
            #True)
                    
        #self.mmdate = MonitoredDate(
            #self.top.get_object("mmdate"),
            #self.top.get_object("mmdate_stat"), 
            #self.top.get_object("mmdate").get_date_object(),
            #uistate,
            #track,
            #True)
        
        #self.mdplace  = PlaceEntry(
            #dbstate, uistate, track,
            #self.top.get_object("mdplace"),
            #self.top.get_object("mdplace").set_place_handle,
            #self.top.get_object("mdplace").get_place_handle,
            #self.top.get_object('add_del_place'),
            #self.top.get_object('select_place'))
        
        #self.mmplace  = PlaceEntry(
            #dbstate, uistate, track,
            #self.top.get_object("mmplace"),
            #self.top.get_object("mmplace").set_place_handle,
            #self.top.get_object("mmplace").get_place_handle,
            #self.top.get_object('add_del_place'),
            #self.top.get_object('select_place'))
            
        #self.mnote  = NoteEntry(
            #dbstate, uistate, track,
            #self.top.get_object("mnote"),
            #self.top.get_object("mnote").set_note_handle,
            #self.top.get_object("mnote").get_note_handle,
            #self.top.get_object('add_del_note'),
            #self.top.get_object('select_note'))
        
        #/database/people/person/parentin/@hlink
        #/database/families/family/mother
        #/database/families/family/father
        #self.spname  = MonitoredText(
            #self.top.get_object("spname"),
            #self.top.get_object("spname").set_text,
            #self.top.get_object("spname").get_text,
            #True)
        
        #/database/families/family/eventref/@hlink
        #/database/events/event/dateval/@val 
        #self.spmdate  = MonitoredEntry(
            #self.top.get_object("spmdate"),
            #self.top.get_object("spmdate").set_text,
            #self.top.get_object("spmdate").get_text,
            #True)
            
        #/database/families/family/eventref/@hlink
        #/database/events/event/place/@hlink
        #/database/places/placeobj/ptitle/text()
        #self.spmplace  = PlaceEntry(
            #dbstate, uistate, track,
            #self.top.get_object("spmplace"),
            #self.top.get_object("spmplace").set_place_handle,
            #self.top.get_object("spmplace").get_place_handle,
            #self.top.get_object('add_del_place'),
            #self.top.get_object('select_place'))
            
            
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
        """
        Load and parse the XML filename
        """
        
        tree = ElementTree.parse(filename)
        root = tree.getroot()
        
        self.walk_tree(root, 0)

                
    def write_xml(self, filename, id , date, given):
        """
        Write the content of data filled into the form
        (currently only a test; no levels)
        """
        
        '''
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE database PUBLIC "-//Gramps//DTD Gramps XML 1.5.0//EN"
        "http://gramps-project.org/xml/1.5.0/grampsxml.dtd">
        <database xmlns="http://gramps-project.org/xml/1.5.0/">
        <header>
          <created date="2012-07-04" version="3.5.0-0.SVNexported"/>
          <researcher>
          </researcher>
        </header>
        ...
        '''

        node = ElementTree.Element('birth')
        node.set('id', id)
        node.set('collection', filename)
        node.set('uri', 'file://..')
        
        gramps = ElementTree.SubElement(node, 'database')
        gramps.set('xmlns', 'http://gramps-project.org/xml/1.5.0/')
        
        #/database/people/person/eventref/@hlink
        #/database/events/event/dateval/@val
        events = ElementTree.SubElement(gramps, 'events')
        event = ElementTree.SubElement(events, 'event')
        dateval = ElementTree.SubElement(event, 'dateval')
        dateval.set('val', date)
        
        #/database/people/person/name/first/text()
        people = ElementTree.SubElement(gramps, 'people')
        person = ElementTree.SubElement(people, 'person')
        name = ElementTree.SubElement(person, 'name')
        first = ElementTree.SubElement(name, 'first')
        first.text = given
        
        outfile = open(filename, 'w')
        self.outfile = codecs.getwriter("utf8")(outfile)
        
        self.outfile.write(ElementTree.tostring(node, encoding="UTF-8"))
        self.outfile.close()
        

class BirthIndexOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
