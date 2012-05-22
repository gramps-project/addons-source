# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009        Brian G. Matherly
# Copyright (C) 2010        Douglas S. Blank
# Copyright (C) 2012        Jerome Rapinat
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

# $Id: $

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import codecs
import sys
import os
import gtk
from xml.etree import ElementTree
import gzip

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.plug import Gramplet
from gen.lib import date
import DateHandler
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
import const
import Utils
import GrampsDisplay
from QuestionDialog import ErrorDialog



NAMESPACE = '{http://gramps-project.org/xml/1.5.0/}'

    
#-------------------------------------------------------------------------    

# name for getiterator / iter (ElementTree 1.2 vs 1.3)

if sys.version_info[1] != 6:
    raise ValueError('ITERATOR = iter(), not written for python 2.7 and greater!')

#-------------------------------------------------------------------------
#
# Timestamp convertor
#
#-------------------------------------------------------------------------
def epoch(t):
        """
        Try to convert timestamp
        """
        
        try:
            from datetime import datetime
            from time import strftime
        except:
            return
        
        if t == None:
            print(_('Invalid timestamp'))
            fmt = _('Unknown')
        else:
            date = int(t)
            conv = datetime.fromtimestamp(date)
            fmt = conv.strftime('%d %B %Y')
        
        return(fmt)

#-------------------------------------------------------------------------
#
# The gramplet
#
#-------------------------------------------------------------------------

class etreeGramplet(Gramplet):
    """
    Gramplet for testing etree (python 2.6) and Gramps XML parsing
    """
    
    def init(self):
        """
        Constructs the GUI, consisting of an entry, a text view and 
        a Run button.
        """  
        
        self.last = 4
                     
        # filename and selector
        
        self.__base_path = const.USER_HOME
        self.__file_name = "test.gramps"
        self.entry = gtk.Entry()
        self.entry.set_text(os.path.join(self.__base_path, self.__file_name))
        
        self.button = gtk.Button()
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
        self.button.add(image)
        self.button.connect('clicked', self.__select_file)
        
        # GUI setup:
        
        vbox = gtk.VBox()
        hbox = gtk.HBox()
        
        # area
        
        self.import_text = gtk.TextView()
        
        self.import_text.set_wrap_mode(gtk.WRAP_WORD)
        self.import_text.set_editable(False)
        
        self.text = gtk.TextBuffer()
        self.text.set_text(_('No file parsed...'))
        self.import_text.set_buffer(self.text)
        
        vbox.pack_start(self.import_text, True) # v1
        
        # button
        
        button = gtk.Button(_("Run"))
        button.connect("clicked", self.run)
        vbox.pack_start(button, False) # v2
        
        # build
        
        hbox.pack_start(self.entry, True)
        hbox.pack_end(self.button, False, False)
        
        vbox.pack_end(hbox, False) # v3
        
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)
        
        vbox.show_all()
        
        
    def __select_file(self, obj):
        """
        Call back function to handle the open button press
        """
        
        my_action = gtk.FILE_CHOOSER_ACTION_SAVE
        
        dialog = gtk.FileChooserDialog('lxml',
                                       action=my_action,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))

        name = os.path.basename(self.entry.get_text())
        dialog.set_current_name(name)
        dialog.set_current_folder(self.__base_path)
        dialog.present()
        status = dialog.run()
        if status == gtk.RESPONSE_OK:
            self.set_filename(Utils.get_unicode_path_from_file_chooser(dialog.get_filename()))
        dialog.destroy()
        

    def set_filename(self, path):
        """ 
        Set the currently selected dialog.
        """
        
        if not path:
            return
        if os.path.dirname(path):
            self.__base_path = os.path.dirname(path)
            self.__file_name = os.path.basename(path)
        else:
            self.__base_path = os.getcwd()
            self.__file_name = path
        self.entry.set_text(os.path.join(self.__base_path, self.__file_name))
        

    def post_init(self):
        self.disconnect("active-changed")
        
        
    def build_options(self):
        from gen.plug.menu import NumberOption
        self.add_option(NumberOption(_("Number of dates back"), 
                                     self.last, 1, 5000))
                                     
                                     
    def save_options(self):
        self.last = int(self.get_option(_("Number of dates back")).get_value())


    def run(self, obj):
        """
        Method that is run when you click the Run button.
        """
        
        entry = self.entry.get_text()
        self.ReadXML(entry)
                                                       
        
    def ReadXML(self, entry):
        """
        Read the .gramps
        """
        
        self.text.set_text('Reading the file...')    
        use_gzip = 1
        try:
            test = gzip.open(entry, "r")
            test.read(1)
            test.close()
        except IOError, msg:
            use_gzip = 0
         
        # lazy ...
        if os.name != 'posix':
            
            # GtkTextView
            
            self.text.set_text(_('Sorry, no support for your OS yet!'))
            return
        
        filename = os.path.join(const.USER_PLUGINS, 'lxml', 'etree.xml')
                
        if use_gzip == 1:
            try:
                os.system('gunzip < %s > %s' % (entry, filename))
            except:
                ErrorDialog(_('Is it a compressed .gramps?'), _('Cannot uncompress "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
        else:
            try:
                os.system('cp %s %s' % (entry, filename))
            except:
                ErrorDialog('Is it a .gramps ?', _('Cannot copy "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
          
        tree = ElementTree.parse(filename)
        self.ParseXML(tree, filename)
                     
        
    def ParseXML(self, tree, filename):
        """
        Parse the .gramps
        """
        
        root = tree.getroot()
        
        # GtkTextView ; buffer limitation ...
                      
        #self.text.set_text(ElementTree.tostring(root))
        
        # timestamp
        
        timestamp = []
        
        # XML attributes
        
        # CVS, RCS like
        keys = []
        
        # counters
        tags = []
        events = [] 
        people = []
        families = []
        sources = []
        citations = []
        places = []
        objects = []
        repositories = []
        notes = []
        
        # Family Tree loaded
        # see gen/plug/_gramplet.py and gen/bb/read.py
        print('events', self.dbstate.db.get_number_of_events())
        print('people', self.dbstate.db.get_number_of_people())
        print('families', self.dbstate.db.get_number_of_families())
        print('sources', self.dbstate.db.get_number_of_sources())
        print('citations', self.dbstate.db.get_number_of_citations())
        print('places', self.dbstate.db.get_number_of_places())
        print('objects', self.dbstate.db.get_number_of_media_objects())
        print('repositories', self.dbstate.db.get_number_of_repositories())
        print('notes', self.dbstate.db.get_number_of_notes())
        
        for one in root.getchildren():
            
            #primary objects (samples)
            
            # find() needs memory - /!\ large files
            if one.find(NAMESPACE + 'event'):
                print('Find all "event" records: %s' % len(one.findall(NAMESPACE + 'event')))
            
            # easier and faster match
            if one.get('home'):
                print(one.attrib)
            
            # iter() for python 2.7 and greater versions
            for two in one.getiterator():
                
                timestamp.append(two.get('change'))
                
                (tag, item) = two.tag, two.items()
                #print(tag)
                #print(two.attrib)
                keys.append((two, item))
                tags.append(tag)
                if tag == NAMESPACE + 'event':
                    events.append(two)
                if tag == NAMESPACE + 'person':
                    people.append(two)
                if tag == NAMESPACE + 'family':
                    families.append(two)
                if tag == NAMESPACE + 'source':
                    sources.append(two)
                if tag == NAMESPACE + 'citation':
                    citations.append(two)
                if tag == NAMESPACE + 'place':
                    places.append(two)
                if tag == NAMESPACE + 'object':
                    objects.append(two)
                if tag == NAMESPACE + 'repository':
                    repositories.append(two)
                if tag == NAMESPACE + 'note':
                    notes.append(two)
                                    
        # to see changes and match existing handles (Family Tree loaded)
        
        #for key in keys:
            #print(key)
        
        timestamp.sort()
        
        last = []
        for i in range(self.last):
            if i == 0:
                start = epoch(i)
                last.append(timestamp[-1])
            else:
                last.append(timestamp[-i])
        
        root.clear()
        
        time = _('Last %s editions since %s, were at/on :\n' % (int(self.last), start))
        for i in last:
            time +=  '\t * %s\n' % epoch(i)       
        
        # GtkTextView
        
        total = _('\nNumber of records and relations : \t%s\n\n') % len(tags)
        
        event = _('Number of  events : \t%s\t(%s)*\n') % (len(events), self.dbstate.db.get_number_of_events())
        person = _('Number of persons : \t%s\t(%s)*\n') % (len(people), self.dbstate.db.get_number_of_people())
        family = _('Number of families : \t%s\t(%s)*\n') % (len(families), self.dbstate.db.get_number_of_families())
        source = _('Number of sources : \t%s\t(%s)*\n') % (len(sources), self.dbstate.db.get_number_of_sources())
        citation = _('Number of citations : \t%s\t(%s)*\n') % (len(citations), self.dbstate.db.get_number_of_citations())
        place = _('Number of places : \t%s\t(%s)*\n') % (len(places), self.dbstate.db.get_number_of_places())
        media_object = _('Number of media objects : \t%s\t(%s)*\n') % (len(objects), self.dbstate.db.get_number_of_media_objects())
        repository = _('Number of repositories : \t%s\t(%s)*\n') % (len(repositories), self.dbstate.db.get_number_of_repositories())
        note = _('Number of notes : \t%s\t(%s)*\n') % (len(notes), self.dbstate.db.get_number_of_notes())
        
        others = len(tags) - (len(events) + len(people) + len(families) + len(sources) + \
        len(citations) + len(places) + len(objects) + len(repositories) + len(notes))
        
        other = _('\nNumber of additional records and relations: \t%s\n') % others
        
        nb  = _('* loaded Family Tree base\n')
        
        preview = time + total + event + person + family + source + citation + \
        place + media_object + repository + note + nb + other
           
        self.text.set_text(preview)
