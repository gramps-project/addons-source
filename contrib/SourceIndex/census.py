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
from gramps.gui.widgets import MonitoredEntry, MonitoredDate
from gramps.gui.plug import tool
import gramps.gen.datehandler

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.get_addon_translator(__file__).gettext

import gramps.gen.constfunc

# Handlers and signal class

class GtkHandlers:
    def on_quit_clicked(event):
        print('quit')
        Gtk.main_quit()
        
    def on_ok_clicked(event):
        print('save')
        Gtk.main_save()
        
    def on_date_clicked(event):
        pass
        
    def on_note_clicked(event):
        pass
        
    def on_name_clicked(event):
        pass

class CensusIndex(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        
        self.label = _('Sources Index')
        self.base = os.path.dirname(__file__)
        
        ManagedWindow.__init__(self, uistate,[], self.__class__)
        self.set_window(Gtk.Window(),Gtk.Label(),'')
        
        tool.Tool.__init__(self, dbstate, options_class, name)
        
        glade_file = os.path.join(USER_PLUGINS, "SourceIndex", "census.glade")
        
        if gramps.gen.constfunc.lin():
            import locale
            locale.setlocale(locale.LC_ALL, '')
            # This is needed to make gtk.Builder work by specifying the
            # translations directory
            locale.bindtextdomain("addon", self.base + "/locale")
            
            self.glade = Gtk.Builder()
            self.glade.set_translation_domain("addon")
                        
            self.glade.add_from_file(glade_file)
            
            from gi.repository import GObject
            GObject.GObject.__init__(self.glade)
                      
            window = self.glade.get_object('edit_census')
                
            self.set_window(window, self.glade.get_object('title'), self.label)
            
            self.ok_button = self.glade.get_object('ok')
            self.quit_button = self.glade.get_object('cancel')
            
        else:
            
            # Glade class from gui/glade.py and gui/managedwindow.py
            self.top = Glade()
            window = self.top.toplevel
            self.set_window(window, None, glade_file)
        
            self.ok_button = self.top.get_object('ok')
            self.quit_button = self.top.get_object('cancel')
            
        self.ok_button.connect('clicked', self.close)
        self.quit_button.connect('clicked', self.close)
    
        self.window.show()
        
        # tests
        filename = os.path.join(USER_PLUGINS, 'SourceIndex', 'test_census.xml')
        self.pname = self.pfname = 'éàèôÖàçèœ'
        self.write_xml(
            filename, 
            'C0001', 
            '',
            self.pfname,
            self.pname
            )
        self.parse_xml(filename)
                        
    def __getitem__(self, key):
        return self.glade.get_widget(key)

    def _setup_fields(self):
        '''
        Gramps XML storage means ability to also import/manage alone records
        /!\ some attributes are translated keys
        see data_item keys and eventref types of attribute
        '''
        
        #/database/repositories/repository/rname/text()
        self.rinfo   = MonitoredEntry(
            self.top.get_object("rinfo"),
            self.obj.set_rinfo,
            self.obj.get_rinfo,
            self.db.readonly)
        
        # date of transcription/search
        self.rdate  = MonitoredEntry(
            self.top.get_object("rdate"),
            self.obj.set_rdate,
            self.obj.get_rdate,
            self.db.readonly)
        
        #/database/repositories/repository/@handle
        self.rid  = MonitoredEntry(
            self.top.get_object("rid"),
            self.obj.set_rid,
            self.obj.get_rid,
            self.db.readonly)
        
        #/database/sources/source/stitle/text()
        self.aname  = MonitoredEntry(
            self.top.get_object("aname"),
            self.obj.set_aname,
            self.obj.get_aname,
            self.db.readonly)
        
        #/database/sources/source/@handle
        self.aid  = MonitoredEntry(
            self.top.get_object("aid"),
            self.obj.set_aid,
            self.obj.get_aid,
            self.db.readonly)
        
        #/database/citations/citation/@handle
        self.aref  = MonitoredEntry(
            self.top.get_object("aref"),
            self.obj.set_aref,
            self.obj.get_aref,
            self.db.readonly)
        
        #/database/citations/citation/page
        # hardcoded /database/citations/citation/confidence
        self.avol  = MonitoredEntry(
            self.top.get_object("avol"),
            self.obj.set_avol,
            self.obj.get_avol,
            self.db.readonly)
        
        #/database/people/person/gender
        self.gen  = MonitoredEntry(
            self.top.get_object("gen"),
            self.obj.set_gen,
            self.obj.get_gen,
            self.db.readonly)
        
        #/database/people/person/name/surname/surname/text()
        self.pname  = MonitoredEntry(
            self.top.get_object("pname"),
            self.obj.set_pname,
            self.obj.get_pname,
            self.db.readonly)

        #/database/people/person/eventref/@hlink
        #/database/events/event/dateval/@val        
        self.pbdate  = MonitoredEntry(
            self.top.get_object("pbdate"),
            self.obj.set_pbdate,
            self.obj.get_pbdate,
            self.db.readonly)
            
        #/database/people/person/eventref/@hlink
        #/database/places/placeobj/@handle        
        self.pbplace  = MonitoredEntry(
            self.top.get_object("pbplace"),
            self.obj.set_pbplace,
            self.obj.get_pbplace,
            self.db.readonly)
        
        #/database/people/person/name/first/text()
        self.pfname  = MonitoredEntry(
            self.top.get_object("pfname"),
            self.obj.set_pfname,
            self.obj.get_pfname,
            self.db.readonly)
                
        #/database/people/person/eventref/noteref/@hlink
        #/database/notes/note/text/text()
        self.pnote  = MonitoredEntry(
            self.top.get_object("pnote"),
            self.obj.set_pnote,
            self.obj.get_pnote,
            self.db.readonly)
        
        # Residence event
        #/database/people/person/eventref/@hlink
        #/database/events/event/description/text()
        self.address  = MonitoredEntry(
            self.top.get_object("address"),
            self.obj.set_address,
            self.obj.get_address,
            self.db.readonly)
            
        #/database/people/person/eventref/@hlink
        #/database/events/event/description/text()
        self.occupation  = MonitoredEntry(
            self.top.get_object("occupation"),
            self.obj.set_occupation,
            self.obj.get_occupation,
            self.db.readonly)
            
        #/database/people/person/eventref/attribute/@type
        #/database/people/person/eventref/attribute/@value
        self.age  = MonitoredEntry(
            self.top.get_object("age"),
            self.obj.set_age,
            self.obj.get_age,
            self.db.readonly)
        
            
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

                
    def write_xml(self, filename, id , status, first, surname):
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
        <events>
          <event handle="_abaa318b6d61a120c1b" change="1341403790" id="E0000">
            <type>Birth</type>
            <dateval val="1845" type="about"/>
            <place hlink="_abaa31688b11e7d1526"/>
            <citationref hlink="_c3332ee70e06bd6867c"/>
          </event>
          <event handle="_abaa342890d322922f7" change="1341403823" id="E0001">
            <type>Census</type>
            <dateval val="1871-04-02"/>
            <place hlink="_abaa340f64a3aa3010e"/>
            <citationref hlink="_c3332ee70e06bd6867c"/>
          </event>
        </events>
        <people>
          <person handle="_abaa31d494e56aba1c1" change="1341403686" id="I0000">
            <gender>M</gender>
            <name type="Birth Name">
              <first>Martin</first>
              <surname>John</surname>
            </name>
            <eventref hlink="_abaa318b6d61a120c1b" role="Primary"/>
            <eventref hlink="_abaa342890d322922f7" role="Primary">
              <attribute priv="1" type="Rang" value="1"/>
              <attribute type="Relation" value="Husband"/>
              <attribute type="Statut familial" value="Head"/>
              <attribute type="Age" value="25 years"/>
              <attribute type="Profession" value="Worker"/>
              <attribute type="Lieu de naissance" value="Wednesbury"/>
            </eventref>
          </person>
        </people>
        <citations>
          <citation handle="_c3332ee70e06bd6867c" change="1341403810" id="C0001">
            <dateval val="1871-04-02"/>
            <page>17/27</page>
            <confidence>2</confidence>
            <sourceref hlink="_abaa371c73f5a827b6f"/>
          </citation>
        </citations>
        <sources>
          <source handle="_abaa371c73f5a827b6f" change="1341403810" id="S0000">
            <stitle>Wednesbury Census between 1871 and 1881</stitle>
            <sauthor>UK Governement</sauthor>
            <spubinfo>www.ancestv.co.uk</spubinfo>
            <data_item key="Recensement" value="UK1871"/>
            <reporef hlink="_abaa3714e242ea05aee" callno="RG 11/2854" medium="Card"/>
          </source>
        </sources>
        <places>
          <placeobj handle="_abaa31688b11e7d1526" change="1179671725" id="P0000">
            <ptitle>Wednesbury Staffordshire</ptitle>
            <location city="Wednesbury" parish="Staffordshire" country="UK"/>
          </placeobj>
          <placeobj handle="_abaa340f64a3aa3010e" change="1179671913" id="P0001">
            <ptitle>Wednesbury Staffordshire, Hope Terrace 17</ptitle>
            <location street="Hope Terrace 17" city="Wednesbury" parish="Staffordshire" country="UK"/>
          </placeobj>
        </places>
        <repositories>
          <repository handle="_abaa3714e242ea05aee" change="1341402429" id="R0000">
            <rname>Civil Parish Wednesbury</rname>
            <type>Library</type>
          </repository>
        </repositories>
      </database>
      '''

        node = ElementTree.Element('census')
        node.set('id', id)
        node.set('collection', filename)
        node.set('uri', 'file://..')
        node1 = ElementTree.SubElement(node, 'status')
        node1.text = status
        
        #/database/people/person/name/first/text()
        node1 = ElementTree.SubElement(node, 'first')
        node1.text = first
        
        #/database/people/person/name/surname/surname/text()
        node1 = ElementTree.SubElement(node, 'surname')
        node1.text = surname
        
        outfile = open(filename, 'w')
        self.outfile = codecs.getwriter("utf8")(outfile)
        
        self.outfile.write(ElementTree.tostring(node, encoding="UTF-8"))
        self.outfile.close()

class CensusIndexOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self,name,person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
