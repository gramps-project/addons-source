# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009       Brian G. Matherly
# Copyright (C) 2010  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2011       Jerome Rapinat
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
#import subprocess

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

#-------------------------------------------------------------------------
#
# Try to detect the presence of gzip
#
#-------------------------------------------------------------------------
try:
    import gzip
    GZIP_OK = True
except:
    GZIP_OK = False
    ErrorDialog('Where is gzip?', _('"gzip" is missing'))
    
#-------------------------------------------------------------------------
#
# Try to detect the presence of lxml (only for using XPATH/XSLT)
# else import elementtree.ElementTree as etree (default python)
#
#-------------------------------------------------------------------------
try:
    from lxml import etree
    LXML_OK = True
except:
    LXML_OK = False
    ErrorDialog('Missing python lxml', _('Please, try to install "python lxml" package.'))
    
#-------------------------------------------------------------------------
#
# The gramplet
#
#-------------------------------------------------------------------------

class lxmlGramplet(Gramplet):
    """
    Gramplet for testing lxml
    """
    
    def init(self):
        """
        Constructs the GUI, consisting of an entry, and 
        a Run button.
        """  
             
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
        # button
        button = gtk.Button(_("Run"))
        button.connect("clicked", self.run)
        hbox.pack_start(self.entry, True)
        hbox.pack_end(self.button, False, False)
        vbox.pack_start(hbox, False)
        vbox.pack_start(button, False)
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
        
        if GZIP_OK:
            use_gzip = 1
            try:
                test = gzip.open(entry, "r")
                test.read(1)
                test.close()
            except IOError, msg:
                use_gzip = 0
            except ValueError, msg:
                use_gzip = 1
        else:
            use_gzip = 0
         
        # lazy ...
        if os.name != 'posix':
            ErrorDialog('For posix only ...', _('Sorry, no support for your OS yet!'))
            return
        
        filename = os.path.join(const.USER_PLUGINS, 'lxml', 'test.xml')
        
        if LXML_OK and use_gzip == 1:
            try:
                os.system('gunzip < %s > %s' % (entry, filename))
            except:
                ErrorDialog('Is it a compressed .gramps ?', _('Cannot uncompress "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%s"\n to:\n "%s"\n.') % (entry, filename))
        elif LXML_OK and use_gzip == 0:
            try:
                os.system('cp %s %s' % (entry, filename))
            except:
                ErrorDialog('Is it a .gramps ?', _('Cannot copy "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%s"\n to:\n "%s"\n.') % (entry, filename))
        else:
            return
        
        # DTD syntax
               
        try:
            self.check_valid(filename)
        except:
            ErrorDialog('DTD validation (xmllint)', _('Cannot validate "%s" !') % entry)
                       
        # RNG validation
        
        rng = os.path.join(const.USER_PLUGINS, 'lxml', 'grampsxml.rng')
        
        try:
            os.system('xmllint --relaxng file://%s --noout %s' % (rng, filename))
        except:
            print(_('xmllint: skip RelaxNG validation for "%s"') % entry)
                
        try:
            #tree = etree.ElementTree(file=filename)
            tree = etree.parse(filename)
            doctype = tree.docinfo.doctype
            if self.RNGValidation(tree, rng) == True:
                try:
                    self.ParseXML(tree, filename)
                except:
                    ErrorDialog('RelaxNG validation', _('Cannot validate "%s" via RelaxNG schema') % filename)
                    return
            else:
                ErrorDialog('Parsing issue', _('Cannot parse content of "%s"') % entry)
                return
        except:
            ErrorDialog('File issue', _('Cannot parse "%s" via etree') % entry)
            return
            
        
    def ParseXML(self, tree, filename):
        """
        Parse the validated .gramps
        """
        
        root = tree.getroot()

        # namespace issues and 'surname' only on 1.4.0!
        namespace = root.nsmap
        surname_tag = etree.SubElement(root, '{http://gramps-project.org/xml/1.4.0/}surname')
        ptitle_tag = etree.SubElement(root, '{http://gramps-project.org/xml/1.4.0/}ptitle')
        
        # variable
        expr = "//*[local-name() = $name]"

        # count function
        # float and seems to also count the parent tag: name[0] !
        count_elements = etree.XPath("count(//*[local-name() = $name])")
        
        # textual children strings function
        desc = etree.XPath('descendant-or-self::text()')
        
        # TODO: cleanup !
        # quick but not a nice method ...
        
        msg = []
        #tags = []
        places = []
        sources = []
        surnames = []
        for one in root.getchildren():
            #(tag, item) = one.tag, one.items()
            #print(tag, item)
            
            for two in one.getchildren():
                #tags.append(two.tag)  
                msg.append(two.items())
                
                # search ptitle
                for three in two.getchildren():
                    
                    # with namespace ...
                    if three.tag == '{http://gramps-project.org/xml/1.4.0/}ptitle':
                        places.append(three.text)
                    if three.tag == '{http://gramps-project.org/xml/1.4.0/}stitle':
                        sources.append(three.text)
                        
                    # search last name
                    for four in three.getchildren():
                        
                        # with namespace ...
                        if four.tag == '{http://gramps-project.org/xml/1.4.0/}surname':
                            surnames.append(four.text)
                            
                    
        #print(etree.tostring(root, pretty_print=True))

        # All tags
        #print(tags)
        
        # keys, values; no textual data; 
        # root child level items as keys for revision control ???
        #revision = msg
        
        #print(revision)
        
        log = msg[0]
        if not log:
            ErrorDialog('Missing header', _('Not a valid .gramps.\n'
                                    'Cannot run the gramplet...\n'
                                    'Please, try to use a .gramps\n'
                                    'generated by Gramps 3.3.x.'))
            return
        
        # dirty XML write method ...
        # need to create a fake entry !
        
        if count_elements(root, name = 'surname') > 1.0:
            nb_surnames = count_elements(root, name = 'surname') - float(1.0)
        else:
            nb_surnames = surnames = [_('No surname')]
            
        if count_elements(root, name = 'ptitle') > 1.0:
            nb_ptitles = count_elements(root, name = 'ptitle') - float(1.0)
        else:
            nb_ptitles = places = [_('No place title')]
            
        if count_elements(root, name = 'note') > 1.0:
            nb_notes = count_elements(root, name = 'note') - float(1.0)
        else:
            nb_notes = _('No note')
            
        if count_elements(root, name = 'stitle') > 1.0:
            nb_sources = count_elements(root, name = 'stitle') - float(1.0)
        else:
            nb_sources = _('No source')
            
        # Some print statements !
        
        print(_('log'), log)
        print(_('Surnames'), nb_surnames)
        print(_('Place titles'), nb_ptitles)
        print(_('Note objects'), nb_notes)
        print(_('Sources titles'), nb_sources)
                
        self.WriteXML(log, surnames, places, sources)
        self.WriteBackXML(filename, root, surnames, places, sources)
        
        
    def check_valid(self, filename):
        """
        Look at schema, validation, conform, etc...
        Code for 1.4.0 and later (previous versions 'surname' was 'last')
        """    
        
        # syntax check against DTD for file format
        # xmllint --loaddtd --dtdvalid --valid --shell --noout ...
        
        dtd = os.path.join(const.USER_PLUGINS, 'lxml', 'grampsxml.dtd')
        try:
            os.system('xmllint --dtdvalid file://%s --noout --dropdtd %s' % (dtd, filename))
        except:
            print(_('xmllint: skip DTD validation'))
            print('\n###################################################')
    
    
    def RNGValidation(self, tree, rng):
        """
        RNG Validation with ElementTree
        """    
        
        # validity check against scheme for file format
                
        valid = etree.ElementTree(file=rng)          
        schema = etree.RelaxNG(valid)
                
        if schema.error_log.last_error:
            sys.stdout.write(schema.error_log)
                
        return(schema.validate(tree))
                
                    
    def WriteXML(self, log, surnames, places, sources):
        """
        Write the result of the query for distributed, shared protocols
        """
        
        # Custom XML file in buffer
        
        self.lang = Utils.xml_lang()
        self.title = _('I am looking at ...')
        self.footer = _('Content generated by Gramps')
        self.surnames_title = _('Surnames')
        self.places_title = _('Places')
        self.sources_title = _('List of sources')
        time = date.Today()
                
        xml = etree.Element("query")
        xml.set("lang", self.lang)
        xml.set("title", self.title)
        xml.set("footer", self.footer)
        xml.set("date", DateHandler.displayer.display(time))

        # only for info
        doc = etree.ElementTree(xml)
        
        # custom countries list (re-use some Gramps translations ...) ;)
        
        countries = ['',
                    _('Australia'),
                    _('Brazil'),
                    _('Bulgaria'),
                    _('Canada'),
                    _('Chile'),
                    _('China'),
                    _('Croatia'),
                    _('Czech Republic'),
                    _('England'),
                    _('Finland'),
                    _('France'),
                    _('Germany'),
                    _('India'),
                    _('Japan'),
                    _('Norway'),
                    _('Portugal'),
                    _('Russia'),
                    _('Sweden'),
                    _('United States of America'),
                    ]
                    
        c = etree.SubElement(xml, "clist")
        self.ptitle = _('Title')
        self.city = _('City')
        self.county = _('County')
        self.state = _('State')
        self.country = _('Country')
        c.set("ptitle", self.ptitle)
        c.set("city", self.city)
        c.set("county", self.county)
        c.set("state", self.state)
        c.set("country", self.country)
        for country in countries:
            c1 = etree.SubElement(c, "country")
            c1.text = unicode(country)
        
        # data log
        
        [(k1, v1),(k2, v2)] = log
        l = etree.SubElement(xml, "log")
        l.set("date", v1)
        l.set("version", v2)
        
        s = etree.SubElement(xml, "surnames")
        s.set("title", self.surnames_title)
        
        surnames.sort()
        cnt = []
        for surname in surnames:
            if surname not in cnt:
                s1 = etree.SubElement(s, "surname")
                s1.text = unicode(surname)
                cnt.append(surname)      
        
        p = etree.SubElement(xml, "places")
        p.set("title", self.places_title)
        
        places.sort()
        for place in places:
            p1 = etree.SubElement(p, "place")
            p1.text = unicode(place)
            
        src = etree.SubElement(xml, "sources")
        src.set("title", self.sources_title)    
        
        sources.sort()
        for source in sources:
            src1 = etree.SubElement(src, "source")
            src1.text = unicode(source) 
        
        content = etree.XML(etree.tostring(xml, encoding="UTF-8"))
        
        # XSLT process
        
        xslt_doc = etree.parse(os.path.join(const.USER_PLUGINS, 'lxml', 'query_html.xsl'))
        transform = etree.XSLT(xslt_doc)
        outdoc = transform(content)
        html = os.path.join(const.USER_PLUGINS, 'lxml', 'query.html')
        outfile = open(html, 'w')
        self.outfile = codecs.getwriter("utf8")(outfile)
        outdoc.write(self.outfile)
        self.outfile.close()
                
        # clear the etree
        content.clear()
    
        # This is the end !
        
        sys.stdout.write(_('Generate:\n "%s".') % html)
        print('\n#######################################################')
        GrampsDisplay.url(html)
        print(_('Try to open\n "%s"\n into your prefered web navigator ...') % html)
        
        self.post(html)
        
        
    def WriteBackXML(self, filename, root, surnames, places, sources):
        """
        Write the result of the query back into the XML file (Gramps scheme)
        """
               
        # Modify the XML copy of the .gramps
        
        outfile = open(filename, 'w')
        self.outfile = codecs.getwriter("utf8")(outfile)
        
        # clear the etree
        root.clear()
               
        ## people/person/name/surname
        
        people = etree.SubElement(root, "people")
        for s in surnames:
            person = etree.SubElement(people, "person")
            name = etree.SubElement(person, "name")
            surname = etree.SubElement(name, "surname")
            surname.text = unicode(s)
            
        surnames = []
        
        ## places/placeobj/ptitle
        
        pl = etree.SubElement(root, "places")
        for p in places:
            place = etree.SubElement(pl, "placeobj")
            ptitle = etree.SubElement(place, "ptitle")
            ptitle.text = unicode(p)
            
        places = []
            
        ## sources/source/stitle
        
        src = etree.SubElement(root, "sources")
        for s in sources:
            source = etree.SubElement(src, "source")
            stitle = etree.SubElement(source, "stitle")
            stitle.text = unicode(s)
            
        sources = []

        # write and close the etree
        
        self.outfile.write(etree.tostring(root, encoding="UTF-8"))
        self.outfile.close()
        
        # clear the etree
        root.clear()
        
        
    def post(self, html):
        """
        Try to play with request ...
        """
        
        import urllib2
        
        response = urllib2.urlopen('file://%s' % html)
        data = response.read()
        
        post = etree.HTML(data)
        
        # find text function
        find_text = etree.XPath("//text()", smart_strings=False)
        
        print('#######################################################')
        print(_('HTML page content:'))
        print(find_text(post))
        
        post.clear()
