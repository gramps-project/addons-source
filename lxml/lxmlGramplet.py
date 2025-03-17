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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# $Id: $

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
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
from gramps.gen.config import config
from gramps.gui.display import display_url
from gramps.gui.dialog import ErrorDialog
from gramps.plugins.lib.libhtml import Html, xml_lang
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
    LOG.error('No gzip')

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
    # LXML_VERSION (4, 3, 4)
    # LIBXML_VERSION (2, 9, 1))
    # LIBXSLT_VERSION (1, 1, 28))
    LXML_VERSION = etree.LXML_VERSION
    LIBXML_VERSION = etree.LIBXML_VERSION
    LIBXSLT_VERSION = etree.LIBXSLT_VERSION
except:
    LXML_OK = False
    ErrorDialog(_('Missing python3 lxml'), _('Please, try to install "python3 lxml" package.'))
    LOG.error('No lxml')

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
            LOG.error('Modules around time missing')
            return

        if t == None:
            LOG.warning(_('Invalid timestamp'))
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

NAMESPACE = '{http://gramps-project.org/xml/1.7.2/}'

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
            self.set_filename(dialog.get_filename())
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


    def run(self, obj):
        """
        Method that is run when you click the Run button.
        """

        entry = self.entry.get_text()
        if ' ' in entry:
            ErrorDialog(_('Space character on filename'), _('Please fix space on "%s"') % entry)
            LOG.error('Space on filename')
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
            except IOError:
                use_gzip = 0
            except ValueError:
                use_gzip = 1
        else:
            use_gzip = 0

        # lazy ...
        if os.name != 'posix' and os.name != 'nt':

            # GtkTextView

            self.text.set_text(_('Sorry, no support for your OS yet!'))
            LOG.error('Not tested under this OS')
            return

        filename = os.path.join(USER_PLUGINS, 'lxml', 'test.xml')

        if LXML_OK and use_gzip == 1:
            try:
                os.system('gunzip < %s > %s' % (entry, filename))
            except:
                ErrorDialog(_('Is it a compressed .gramps?'), _('Cannot uncompress "%s"') % entry)
                LOG.error('Cannot use gunzip command')
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
        elif LXML_OK and use_gzip == 0:
            try:
                copy(entry, filename)
            except:
                ErrorDialog('Is it a .gramps ?', _('Cannot copy "%s"') % entry)
                LOG.error('Cannot copy the file')
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
        else:
            LOG.error('lxml or gzip is missing')
            return

        # XSD structure via lxml

        xsd = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.xsd')
        try:
            self.xsd(xsd, filename)
            #pass
        except:
            ErrorDialog(_('XSD validation (lxml)'), _('Cannot validate "%(file)s" !') % {'file': entry})
            LOG.debug(self.xsd(xsd, filename))

        # DTD syntax via xmllint (libxml2-utils)

        try:
            self.check_valid(filename)
        except:
            LOG.info(_('xmllint: skip DTD validation for "%(file)s"') % {'file': entry})

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
            current = '<!DOCTYPE database PUBLIC "-//Gramps//DTD Gramps XML 1.7.2//EN" "http://gramps-project.org/xml/1.7.2/grampsxml.dtd">'
            if self.RNGValidation(tree, rng) == True:
                #self.ParseXML(tree, filename)  for debug 
                try:
                    self.ParseXML(tree, filename)
                except:
                    ErrorDialog(_('Parsing issue'), _('Cannot parse content of "%(file)s"') % {'file': filename})
                    LOG.error('Cannot parse the content of the XML copy or missing "query_html.xsl" file.')
                    return
            elif doctype != current:
                ErrorDialog(_('Gramps version'), _('Wrong namespace\nNeed: %s') % current)
                LOG.error('Namespace is wrong')
                return
            else:
                ErrorDialog(_('RelaxNG validation'), _('Cannot validate "%(file)s" via RelaxNG schema') % {'file': entry})
                LOG.error('RelaxNG validation failed')
                return
        except etree.XMLSyntaxError as e:
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

        #self.text.set_text(_('Parsing file...'))

        #LOG.info(etree.tostring(root, pretty_print=True))

        # namespace issues !

        namespace = root.nsmap

        surname_tag = etree.SubElement(root, NAMESPACE + 'surname')
        pname_tag = etree.SubElement(root, NAMESPACE + 'pname')
        private_surname = config.get('preferences.private-surname-text')
        private_record = config.get('preferences.private-record-text')

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

                # privacy

                if two.get('priv'): # XML: optional
                    text = private_record
                else:
                    text = ""

                # search ptitle and time log

                for three in two.iter():

                    # timestamp
                    if two.get('change'):
                        timestamp.append(two.get('change'))
                        
                    # with namespace ...
                    #print(desc(three))
                    (tag, items) = three.tag, three.items()

                    if three.tag == NAMESPACE + 'ptitle':
                        if text != private_record:
                            text = str(three.text)
                        if text not in places:
                            places.append(text) # temp display

                    if three.tag == NAMESPACE + 'pname':
                        if text != private_record:
                            text = str(three.attrib.get('value'))
                        translation = str(three.attrib.get('lang'))
                        if translation == 'None':
                            translation = xml_lang()[0:2]
                            text = text + _(' - (? or %(lang)s)') % {'lang':translation}
                        else:
                            text = text + _(' - (%(lang)s)') % {'lang':translation}
                        if text not in places:
                            places.append(text) # temp display
                    if three.tag == NAMESPACE + 'stitle' and three.text not in sources:
                        # need to add an exception
                        if not three.text:
                            three.text = ""
                        sources.append(three.text)
                    if three.tag == NAMESPACE + 'file' and three.items() not in thumbs:
                        thumbs.append(three.items())

                    # search last name

                    for four in three.iter():

                        # with namespace ...

                        if four.tag == NAMESPACE + 'surname' and four.text != None:
                            if text != private_record:
                                surnames.append(four.text)
                            else:
                                surnames.append(private_surname)

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
                                    'generated by Gramps 6.x.'))
            LOG.error('header missing')
            return

        # dirty XML write method ...
        # need to create a fake entry !

        if int(count_elements(root, name = 'surname')) > 1:
            nb_surnames = int(count_elements(root, name = 'surname'))
        else:
            nb_surnames = surnames = [_('0')]

        if int(count_elements(root, name = 'pname')) > 1:
            nb_pnames = int(count_elements(root, name = 'pname'))
        else:
            nb_pnames = places = [_('0')]

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
        p =  '\t' + str(nb_pnames) + '\t' + _(' entries for place(s)') + '\n'
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

        unique_surnames = list(set(surnames))
        unique_surnames.sort()

        self.WriteBackXML(filename, root, unique_surnames, places, sources)
        sys.stdout.write(_('3. Has written entries into "%(file)s".\n') % {'file': filename})


    def xsd(self, xsd, filename):
        """
        Look at schema, validation, conform, structure, content, etc...
        Code for 1.7.2
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
        Code for 1.7.2
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
        self.places_name = _('Places')
        self.sources_title = _('List of sources')
        time = date.Today()

        xml = etree.Element("query")
        xml.set("lang", self.lang)
        xml.set("title", self.title)
        xml.set("footer", self.footer)
        xml.set("date", gramps.gen.datehandler.displayer.display(time))
        xml.set("first", first)
        xml.set("last", last)

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
        self.name = _('Name')
        self.country = _('Country')
        c.set("pname", self.name)
        c.set("country", self.country)
        for country in countries:
            c1 = etree.SubElement(c, "country")
            c1.text = country

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
                s1.text = surname
                cnt.append(surname)

        p = etree.SubElement(xml, "places")
        p.set("pname", self.places_name)

        places.sort()
        for place in places:
            p1 = etree.SubElement(p, "place")
            p1.text = place

        src = etree.SubElement(xml, "sources")
        src.set("title", self.sources_title)

        sources.sort()
        for source in sources:
            src1 = etree.SubElement(src, "source")
            src1.text = source

        content = etree.XML(etree.tostring(xml, encoding="UTF-8"))

        # XSLT process

        xslt_doc = etree.parse(os.path.join(USER_PLUGINS, 'lxml', 'query_html.xsl'))
        transform = etree.XSLT(xslt_doc)
        outdoc = transform(content)
        #print(type(outdoc))
        html = os.path.join(USER_PLUGINS, 'lxml', 'query.html')
        outfile = open(html, 'w')

        outfile.write(str(outdoc))
        outfile.close()

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
        of = open(fname, "w")

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

        from gramps.gen.utils.thumbnails import get_thumbnail_path

        # full clear line for proper styling

        fullclear = Html("div", class_ = "fullclear", inline = True)

        LOG.info('Start to enumerate for gallery')
        #LOG.debug(thumbs)

        for i, thumb in enumerate(thumbs):

            # list of tuples [('',''),('','')]

            if (list(thumb)[0])[0] == 'src':
                src = (list(thumb)[0])[1]
            else:
                src = 'No src'
            #LOG.debug(src)

            if (list(thumb)[1])[0] == 'mime':
                mime = (list(thumb)[1])[1]
            else:
                mime = 'No mime'
            #LOG.debug(mime)

            if (list(thumb)[2])[0] == 'checksum':
                checksum = (list(thumb)[2])[1]
            else:
                checksum = 'No checksum'
            #LOG.debug(checksum)

            if (list(thumb)[2])[0] == 'description':
                description = (list(thumb)[2])[1]
            elif len(thumb) == 4:
                description = (list(thumb)[3])[1]
            else:
                description = 'No description'
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
        for i, txt in enumerate(self.text):
            #LOG.debug(txt)
            text.write(txt + '\n') # Html.write() ?
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

        # clear the etree

        root.clear()
        the_id = 0

        ## people/person/name/surname

        people = etree.SubElement(root, "people")
        for s in surnames:
            the_id += 1
            person = etree.SubElement(people, "person")
            person.set('id', str(the_id) + '_' + str(len(surnames)))
            name = etree.SubElement(person, "name")
            surname = etree.SubElement(name, "surname")
            surname.text = s

        surnames = []

        ## places/placeobj/pname

        pl = etree.SubElement(root, "places")
        for p in places:
            the_id += 1 
            place = etree.SubElement(pl, "placeobj")
            place.set('id', str(the_id) + '_' + str(len(places)))
            name = etree.SubElement(place, "pname")
            pname = name.set('value', p)

        places = []

        ## sources/source/stitle

        src = etree.SubElement(root, "sources")
        for s in sources:
            the_id += 1
            source = etree.SubElement(src, "source")
            source.set('id', str(the_id) + '_' + str(len(sources)))
            stitle = etree.SubElement(source, "stitle")
            stitle.text = s

        sources = []

        # write and close the etree

        out = etree.tostring(root, method='xml', pretty_print=True)
        str_out = out.decode('utf-8')

        outfile.write(str_out)
        outfile.close()

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
