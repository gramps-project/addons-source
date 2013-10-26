# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009        Brian G. Matherly
# Copyright (C) 2010        Douglas S. Blank
# Copyright (C) 2011-2012   Jerome Rapinat
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
from shutil import copy
from gi.repository import Gtk
#import subprocess

import logging

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.lib import date
import gramps.gen.datehandler
from gramps.gen.const import USER_HOME, USER_PLUGINS
from gramps.gen.utils.file import get_unicode_path_from_file_chooser
from gramps.gui.display import display_url
from gramps.gui.dialog import ErrorDialog
from gramps.plugins.lib.libhtml import Html, xml_lang
from gramps.gen.constfunc import cuni
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

LOG = logging.getLogger("lxml")

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
    ErrorDialog(_('Where is gzip?'), _('"gzip" is missing'))
    
#-------------------------------------------------------------------------
#
# Try to detect the presence of lxml (only for using XPATH/XSLT)
# 
# from xml.etree import ElementTree from default python default python has a basic XPATH/XSLT API
#
#-------------------------------------------------------------------------
try:
    from lxml import etree, objectify
    LXML_OK = True
    # current code is working with:
    # LXML_VERSION (2, 3, 2)
    # LIBXML_VERSION (2, 7, 8))
    # LIBXSLT_VERSION (1, 1, 26))
    LXML_VERSION = etree.LXML_VERSION
    LIBXML_VERSION = etree.LIBXML_VERSION
    LIBXSLT_VERSION = etree.LIBXSLT_VERSION
except:
    LXML_OK = False
    ErrorDialog(_('Missing python lxml'), _('Please, try to install "python lxml" package.'))
    
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
            LOG.warning(_('Invalid timestamp'))
            fmt = _('Unknown')
        else:
            date = int(t)
            conv = datetime.fromtimestamp(date)
            fmt = conv.strftime('%d %B %Y')
        
        if os.name == 'nt':
            return(fmt).decode('mbcs').encode("utf-8")
        else:
            return(fmt)
    
#-------------------------------------------------------------------------
#
# The gramplet
#
#-------------------------------------------------------------------------

NAMESPACE = '{http://gramps-project.org/xml/1.6.0/}'

class lxmlGramplet(Gramplet):
    """
    Gramplet for testing lxml
    """
    
    def init(self):
        """
        Constructs the GUI, consisting of an entry, a text view and 
        a Run button.
        """  
             
        # filename and selector
        
        self.__base_path = USER_HOME
        self.__file_name = "test.gramps"
        self.entry = Gtk.Entry()
        self.entry.set_text(os.path.join(self.__base_path, self.__file_name))
        
        self.button = Gtk.Button()
        image = Gtk.Image()
        image.set_from_stock(Gtk.STOCK_OPEN, Gtk.IconSize.BUTTON)
        self.button.add(image)
        self.button.connect('clicked', self.__select_file)
        
        # GUI setup:
        
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        
        # area
        
        self.import_text = Gtk.TextView()
        
        self.import_text.set_wrap_mode(Gtk.WrapMode.WORD)
        self.import_text.set_editable(False)
        
        self.text = Gtk.TextBuffer()
        self.text.set_text(_('No file loaded...'))
        self.import_text.set_buffer(self.text)
        
        vbox.pack_start(self.import_text, True, True, 0) # v1
        
        # button
        
        button = Gtk.Button(_("Run"))
        button.connect("clicked", self.run)
        vbox.pack_start(button, False, False, 0) # v2
        
        # build
        
        hbox.pack_start(self.entry, True, True, 0)
        hbox.pack_end(self.button, False, False, 0)
        
        vbox.pack_end(hbox, False, False, 0) # v3
        
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)
        
        vbox.show_all()
        
        
    def __select_file(self, obj):
        """
        Call back function to handle the open button press
        """
        
        my_action = Gtk.FileChooserAction.SAVE
        
        dialog = Gtk.FileChooserDialog('lxml',
                                       action=my_action,
                                       buttons=(Gtk.STOCK_CANCEL,
                                                Gtk.ResponseType.CANCEL,
                                                Gtk.STOCK_OPEN,
                                                Gtk.ResponseType.OK))

        name = os.path.basename(self.entry.get_text())
        dialog.set_current_name(name)
        dialog.set_current_folder(self.__base_path)
        dialog.present()
        status = dialog.run()
        if status == Gtk.ResponseType.OK:
            self.set_filename(get_unicode_path_from_file_chooser(dialog.get_filename()))
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
        if ' ' in entry:
            ErrorDialog(_('Space character on filename'), _('Please fix space on "%s"') % entry)
            return
        
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
        if os.name != 'posix' and os.name != 'nt':
            
            # GtkTextView
            
            self.text.set_text(_('Sorry, no support for your OS yet!'))
            return

        filename = os.path.join(USER_PLUGINS, 'lxml', 'test.xml')
                
        if LXML_OK and use_gzip == 1:
            try:
                os.system('gunzip < %s > %s' % (entry, filename))
            except:
                ErrorDialog(_('Is it a compressed .gramps?'), _('Cannot uncompress "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
        elif LXML_OK and use_gzip == 0:
            try:
                copy(entry, filename)
            except:
                ErrorDialog('Is it a .gramps ?', _('Cannot copy "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
        else:
            return
        
        # XSD structure via lxml
        
        xsd = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.xsd')
        try:
            self.xsd(xsd, filename)
        except:
            ErrorDialog(_('XSD validation (lxml)'), _('Cannot validate "%(file)s" !') % {'file': entry})
            LOG.debug(self.xsd(xsd, filename))
            
        # DTD syntax via xmllint (libxml2-utils)
        
        try:
            self.check_valid(filename)
        except:
            ErrorDialog(_('DTD validation (xmllint)'), _('Cannot validate "%(file)s" !') % {'file': entry})
            LOG.debug(_('xmllint: skip DTD validation for "%(file)s"') % {'file': entry})
                    
        # RNG validation via xmllint (libxml2-utils)
        
        rng = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.rng')
        
        try:
            if os.name == 'nt':
                os.system('xmllint --relaxng %s --noout %s' % (rng, filename))
            else:
                os.system('xmllint --relaxng file://%s --noout %s' % (rng, filename))
        except:
            LOG.info(_('xmllint: skip RelaxNG validation for "%(file)s"') % {'file': entry})
                
        try:
            #tree = etree.ElementTree(file=filename)
            tree = etree.parse(filename)
            doctype = tree.docinfo.doctype
            current = '<!DOCTYPE database PUBLIC "-//Gramps//DTD Gramps XML 1.6.0//EN" "http://gramps-project.org/xml/1.6.0/grampsxml.dtd">'
            if self.RNGValidation(tree, rng) == True:
                try:
                    self.ParseXML(tree, filename)
                except:
                    ErrorDialog(_('Parsing issue'), _('Cannot parse content of "%(file)s"') % {'file': filename})
                    return
            elif doctype != current:
                ErrorDialog(_('Gramps version'), _('Wrong namespace\nNeed: %s') % current)
                return
            else:
                ErrorDialog(_('RelaxNG validation'), _('Cannot validate "%(file)s" via RelaxNG schema') % {'file': entry})
                return
        except etree.XMLSyntaxError, e:
            ErrorDialog(_('File issue'), _('Cannot parse "%(file)s" via etree') % {'file': entry})
            log = e.error_log.filter_from_level(etree.ErrorLevels.FATAL)
            LOG.debug(log)
            debug = e.error_log.last_error
            LOG.debug(debug.domain_name)
            LOG.debug(debug.type_name)
            LOG.debug(debug.filename)
            return
            
        
    def ParseXML(self, tree, filename):
        """
        Parse the validated .gramps
        """
        root = tree.getroot()
        
        # GtkTextView ; buffer limitation ...
                      
        self.text.set_text(_('Parsing file...'))
        
        #LOG.info(etree.tostring(root, pretty_print=True))

        # namespace issues !
        
        namespace = root.nsmap

        surname_tag = etree.SubElement(root, NAMESPACE + 'surname')
        ptitle_tag = etree.SubElement(root, NAMESPACE + 'ptitle')
        
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
        timestamp = []
        thumbs = []
        
        LOG.info('start iteration')
        
        for one in root.iter():
            
            #(tag, item) = one.tag, one.items()
            #print(tag, item)
            
            for two in one.iter():
                
                #tags.append(two.tag)
                                
                msg.append(two.items())
                
                if two.tag == NAMESPACE + 'mediapath':
                    mediapath = two.text
                else:
                    mediapath = ''
                
                # search ptitle and time log
                
                for three in two.iter():
                                                            
                    # timestamp
                    if two.get('change'):
                        timestamp.append(two.get('change'))
                        
                    # with namespace ...              
                                   
                    if three.tag == NAMESPACE + 'ptitle' and three.text not in places:
                        places.append(three.text)
                    if three.tag == NAMESPACE + 'stitle' and three.text not in sources:
                        sources.append(three.text)
                    if three.tag == NAMESPACE + 'file' and three.items() not in thumbs:
                        thumbs.append(three.items())
                        
                    # search last name
                    
                    for four in three.iter():
                        
                        # with namespace ...
                        
                        if four.tag == NAMESPACE + 'surname':
                            surnames.append(four.text)
        
        LOG.info('end of loops')
                            
                    
        # All tags
        #print(tags)
        
        # keys, values; no textual data; 
        # root child level items as keys for revision control ???
        #revision = msg
        
        #print(revision)
                
        log = msg[2]
        if not log:
            ErrorDialog(_('Missing header'), _('Not a valid .gramps.\n'
                                    'Cannot run the gramplet...\n'
                                    'Please, try to use a .gramps\n'
                                    'generated by Gramps 4.x.'))
            LOG.debug('header missing')
            return
        
        # dirty XML write method ...
        # need to create a fake entry !
        
        if int(count_elements(root, name = 'surname')) > 1:
            nb_surnames = int(count_elements(root, name = 'surname'))
        else:
            nb_surnames = surnames = [_('0')]
            
        if int(count_elements(root, name = 'ptitle')) > 1:
            nb_ptitles = int(count_elements(root, name = 'ptitle'))
        else:
            nb_ptitles = places = [_('0')]
            
        if int(count_elements(root, name = 'note')) > 1:
            nb_notes = int(count_elements(root, name = 'note'))
        else:
            nb_notes = _('0')
            
        if int(count_elements(root, name = 'stitle')) > 1:
            nb_sources = int(count_elements(root, name = 'stitle'))
        else:
            nb_sources = _('0')
            
        # time logs
        
        timestamp.sort()
        start = timestamp[0]
        end = timestamp[-1]
        timestamp = []
        first = epoch(start)
        last = epoch(end)

        header = _('File parsed with') + ' LXML' + str(LXML_VERSION) + '\n\n'
        
        [(k1, v1),(k2, v2)] = log
        file_info = _('File was generated on ') + v1 + '\n\t' + _(' by Gramps ') + v2 + '\n\n'
        
        period = _('Period: ') +  first + ' => ' + last + '\n\n'
        
        su =  '\t' + str(nb_surnames) + '\t' + _(' entries for surname(s); no frequency yet') + '\n'
        p =  '\t' + str(nb_ptitles) + '\t' + _(' entries for place(s)') + '\n'
        n =  '\t' + str(nb_notes) + '\t' + _(' note(s)')  + '\n'
        so =  '\t' + str(nb_sources) + '\t' + _(' source(s)') + '\n\n'
        
        counters = su + p + n + so
        
        libs = 'LIBXML' + str(LIBXML_VERSION) + '\tLIBXSLT' + str(LIBXSLT_VERSION)
        
        # GtkTextView
        
        self.text.set_text(header + file_info + period + counters + libs)
                
        LOG.info('### NEW FILES ###')
        LOG.info('content parsed and copied')
        
        self.WriteXML(log, first, last, surnames, places, sources)
        
        self.PrintMedia(thumbs, mediapath)
        images = os.path.join(USER_PLUGINS, 'lxml', _('Gallery.html'))
        sys.stdout.write(_('2. Has generated a media index on "%(file)s".\n') % {'file': images})
        
        self.WriteBackXML(filename, root, surnames, places, sources)
        sys.stdout.write(_('3. Has written entries into "%(file)s".\n') % {'file': filename})
        

    def xsd(self, xsd, filename):
        """
        Look at schema, validation, conform, structure, content, etc...
        Code for 1.5.0 and +
        """    
        
        # syntax check against XSD for file format
        
        schema = etree.XMLSchema(file=xsd)
        
        parser = objectify.makeparser(schema = schema)
        
        tree = etree.parse(filename)
        root = tree.getroot()
        
        database = objectify.fromstring(etree.tostring(root, encoding="UTF-8"), parser)
        LOG.info(_('Matches XSD schema.'))
        
        #dump = objectify.dump(database)
        #print(dump)

    def check_valid(self, filename):
        """
        Look at schema, validation, conform, etc...
        Code for 1.5.0 and +
        """    
        
        # syntax check against DTD for file format
        # xmllint --loaddtd --dtdvalid --valid --shell --noout ...
        
        dtd = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.dtd')
        try:
            if os.name == 'nt':
                os.system('xmllint --dtdvalid %(dtd)s --noout --dropdtd %(file)s' % {'dtd': dtd, 'file': filename})
            else:
                os.system('xmllint --dtdvalid file://%(dtd)s --noout --dropdtd %(file)s' % {'dtd': dtd, 'file': filename})
        except:
            LOG.info(_('xmllint: skip DTD validation'))
    
    
    def RNGValidation(self, tree, rng):
        """
        RNG Validation with ElementTree
        """    
        
        # validity check against scheme for file format
                
        valid = etree.ElementTree(file=rng)          
        schema = etree.RelaxNG(valid)
                
        return(schema.validate(tree))
        
                    
    def WriteXML(self, log, first, last, surnames, places, sources):
        """
        Write the result of the query for distributed, shared protocols
        """
        
        # Custom XML file in buffer
        
        self.lang = xml_lang()
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
        xml.set("date", gramps.gen.datehandler.displayer.display(time))
        xml.set("first", cuni(first))
        xml.set("last", cuni(last))

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
            c1.text = cuni(country)
        
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
                s1.text = cuni(surname)
                cnt.append(surname)      
        
        p = etree.SubElement(xml, "places")
        p.set("title", self.places_title)
        
        places.sort()
        for place in places:
            p1 = etree.SubElement(p, "place")
            p1.text = cuni(place)
            
        src = etree.SubElement(xml, "sources")
        src.set("title", self.sources_title)    
        
        sources.sort()
        for source in sources:
            src1 = etree.SubElement(src, "source")
            src1.text = cuni(source) 
        
        content = etree.XML(etree.tostring(xml, encoding="UTF-8"))
        
        # XSLT process
        
        xslt_doc = etree.parse(os.path.join(USER_PLUGINS, 'lxml', 'query_html.xsl'))
        transform = etree.XSLT(xslt_doc)
        outdoc = transform(content)
        html = os.path.join(USER_PLUGINS, 'lxml', 'query.html')
        outfile = open(html, 'w')
        self.outfile = codecs.getwriter("utf8")(outfile)
        outdoc.write(self.outfile)
        self.outfile.close()
                
        # clear the etree
        
        content.clear()
    
        # This is the end !
        
        sys.stdout.write(_('1. Has generated "%s".\n') % html)
        LOG.info(_('Try to open\n "%s"\n into your prefered web navigator ...') % html)
        display_url(html)
        
        #self.post(html)
        
        
    def PrintMedia(self, thumbs, mediapath):
        """
        Print some media infos via HTML class (Gramps)
        """
        
        LOG.info('Looking at media...')

        # Web page filename extensions
        
        _WEB_EXT = ['.html', '.htm', '.shtml', '.php', '.php3', '.cgi']
        
        # page title 
        
        title = _('Gallery')
        
        fname = os.path.join(USER_PLUGINS, 'lxml', _('Gallery.html'))
        of = codecs.EncodedFile(open(fname, "w"), 'utf-8',
                                    file_encoding=None, errors='strict')
                                    
        LOG.info('Empty "Gallery.hml" file created')
        
        # htmlinstance = page
        # ignored by current code...
        
        lang = xml_lang()
        page, head, body = Html.page(title, encoding='utf-8', lang=str(lang))
        head = body = ""
        
        self.text = []
        
        self.XHTMLWriter(fname, page, head, body, of, thumbs, mediapath)
    
        LOG.info('End (Media)')
    
    def __write_gallery(self, thumbs, mediapath):
        """
        This procedure writes out the media
        """
        
        LOG.info('Looking at gallery')
               
        from gramps.gui.thumbnails import get_thumbnail_path
        
        # full clear line for proper styling
        
        fullclear = Html("div", class_ = "fullclear", inline = True)
        
        # ugly ...
        
        LOG.info('Start to enumerate for gallery')
        #LOG.debug(thumbs)
        
        for i in range(len(thumbs)):
            
            # list of tuples [('',''),('','')]
            
            src = (list(thumbs[i])[0])[1]
            #LOG.debug(src)
            mime = (list(thumbs[i])[1])[1]
            #LOG.debug(mime)
            checksum = (list(thumbs[i])[2])[1]
            #LOG.debug(checksum)
            description = (list(thumbs[i])[3])[1]
            #LOG.debug(description)
            
            # relative and absolute paths
            
            src = os.path.join(mediapath, src)
            
            # windows OS ???
            if not src.startswith("/"):
                src = os.path.join(USER_HOME, src)
                
            #LOG.debug(src)
                        
            # only images
            
            if mime.startswith("image"):
                thumb = get_thumbnail_path(str(src), mtype=None, rectangle=None)
                #LOG.debug(thumb)
                self.text += Html('img', src=str(thumb), mtype=str(mime))
                self.text += fullclear
                self.text += Html('a', str(description), href=str(src), target='blank', title=str(mime))
                self.text += fullclear
        
        return self.text
    
    
    def close_file(self, of):
        """ will close whatever filename is passed to it """
        of.close()
        
    
    def XHTMLWriter(self, fname, page, head, body, of, thumbs, mediapath):
        """
        Will format, write, and close the file

        of -- open file that is being written to
        htmlinstance -- web page created with libhtml
            src/plugins/lib/libhtml.py
        """
        
        self.__write_gallery(thumbs, mediapath)
        
        #LOG.debug(self.text)
            
        text = open(fname, 'w')
        text.write(head)
        for i in range(len(self.text)):
            #LOG.debug(self.text[i])
            text.write(self.text[i] + '\n') # Html.write() ?
        text.close()

        # closes the file
        
        self.close_file(of)
        
        LOG.info('Gallery generated')
        
        
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
            surname.text = cuni(s)
            
        surnames = []
        
        ## places/placeobj/ptitle
        
        pl = etree.SubElement(root, "places")
        for p in places:
            place = etree.SubElement(pl, "placeobj")
            ptitle = etree.SubElement(place, "ptitle")
            ptitle.text = cuni(p)
            
        places = []
            
        ## sources/source/stitle
        
        src = etree.SubElement(root, "sources")
        for s in sources:
            source = etree.SubElement(src, "source")
            stitle = etree.SubElement(source, "stitle")
            stitle.text = cuni(s)
            
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
        
        LOG.info(find_text(post))
        
        post.clear()
