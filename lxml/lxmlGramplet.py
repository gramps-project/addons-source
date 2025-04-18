# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009        Brian G. Matherly
# Copyright (C) 2010        Douglas S. Blank
# Copyright (C) 2011-2025   Jerome Rapinat
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
from shutil import copyfile
from gi.repository import Gtk
#import subprocess
from pathlib import Path

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

ngettext = _trans.ngettext

LOG = logging.getLogger("lxml")
desktop_session = os.environ.get("DESKTOP_SESSION")

#-------------------------------------------------------------------------
#
# Try to detect the presence of gzip
#
#-------------------------------------------------------------------------
try:
    import gzip
    GZIP_OK = True
except ImportError:
    GZIP_OK = False
    ErrorDialog(_('Where is gzip?'), _('"gzip" is missing'), parent=self.uistate.window)
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
except ImportError:
    LXML_OK = False
    ErrorDialog(_('Missing python3 lxml'), _('Please, try to install "python3 lxml" package.'), parent=self.uistate.window)
    LOG.debug('No lxml')

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
        except ImportError:
            LOG.debug('Modules around time missing')
            return

        if t is None:
            LOG.warning(_('Invalid timestamp'))
            return _('Unknown')

        date = int(t)
        conv = datetime.fromtimestamp(date)
        return conv.strftime('%d %B %Y')

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
        self.__file_name = str(Path.home())
        self.entry = Gtk.Entry()
        self.entry.set_text(self.__file_name)

        self.button = Gtk.Button()
        if os.name == 'nt' or sys.platform == "darwin":
            self.button = Gtk.Button(_("Select file"))
            #self.button.set_size_request(40, 40)
        else:
            LOG.debug(desktop_session) # works on pantheon
            image = Gtk.Image.new_from_icon_name(Gtk.STOCK_FIND, 6)
            self.button.add(image)
        #self.button.set_size_request(40, 40)
        self.button.connect('clicked', self.__select_file)

        # GUI setup:

        self.set_tooltip(_("Select a Gramps XML file and\n click on the Run button."))

        hbox = Gtk.Box()
        hbox.pack_start(self.entry, True, True, 0)
        hbox.pack_start(self.button, False, False, 0)

        # button

        if os.name == 'nt' or sys.platform == "darwin":
            button = Gtk.Button(_("Run"))
        else:
            LOG.debug(desktop_session) # works on pantheon
            button = Gtk.Button()
            exe = Gtk.Image.new_from_icon_name(Gtk.STOCK_EXECUTE, 6)
            button.add(exe)
        button.connect("clicked", self.run)
        hbox.pack_end(button, False, False, 0) # v2

        # area

        self.import_text = Gtk.TextView()
        self.import_text.set_wrap_mode(Gtk.WrapMode.WORD)
        self.import_text.set_editable(False)
        self.text = Gtk.TextBuffer()
        self.text.set_text(_('No file loaded...'))
        self.import_text.set_buffer(self.text)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.pack_start(hbox, False, True, 0) # v1
        vbox.pack_end(self.import_text, True, True, 0) # v3

        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)

        vbox.show_all()


    def __select_file(self, obj):
        """
        Callback function to handle the open button press
        """

        my_action = Gtk.FileChooserAction.SAVE

        dialog = Gtk.FileChooserDialog('lxml',
                                       action=my_action,
                                       buttons=(Gtk.STOCK_CANCEL,
                                                Gtk.ResponseType.CANCEL,
                                                Gtk.STOCK_OPEN,
                                                Gtk.ResponseType.OK),
                                                parent=self.uistate.window)

        dialog.set_current_name(self.__file_name)
        dialog.present()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            self.set_filename(dialog.get_filename())
        dialog.destroy()


    def set_filename(self, path):
        """
        Set the currently selected file.
        """
        if not path:
            return
        self.__base_path = str(Path(path).parent) or os.getcwd()  # pathlib
        self.__file_name = Path(path).name  # pathlib
        self.entry.set_text(str(Path(os.path.join(self.__base_path, self.__file_name))))  #  pathlib


    def run(self, obj):
        """
        Method that is run when you click the Run button.
        """
        entry = self.entry.get_text()
        if ' ' in entry:
            #ErrorDialog(_('Space character in filename or path'), _('Please fix space in "%s"') % entry, parent=self.uistate.window)
            LOG.info('Space on filename or path')
            #return

        #if Path(os.path.join(USER_PLUGINS, 'lxml', 'test.xml')).exists():
            #Path.unlink(os.path.join(USER_PLUGINS, 'lxml', 'test.xml'))

        if not self.__file_name.endswith('.gramps'):
            return
        LOG.info(self.__base_path)
        LOG.info(self.__file_name)
        LOG.info(entry)

        if self.__file_name != "":
            sys.excepthook = self.read_xml(entry)


    def is_gzip(self, entry):
        """
        Check if the file is gzip compressed.
        """
        if GZIP_OK:
            LOG.debug(gzip.open(entry, "r"))
            try:
                with gzip.open(entry, "r") as test:
                    test.read(1)
                self.close_file(test)
                return True
            except (IOError, ValueError):
                return False
        return False


    def uncompress_file(self, entry, filename):
        """
        Uncompress the gzip file.
        """
        self.text.set_text('gunzip the file...')
        try:
            os.system(f'gunzip < "{entry}" > {filename}')
        except Exception as e:
            ErrorDialog(_('Is it a compressed .gramps?'), _(f'Cannot uncompress "{entry}"'),parent=self.uistate.window)
            LOG.error('Cannot use gunzip command')
            raise e


    def copy_file(self, filename):
        """
        Copy the file to the destination.
        """
        self.text.set_text('copy the file...')
        try:
            copyfile(os.path.join(self.__base_path, self.__file_name), filename)
        except FileNotFoundError or IsADirectoryError:
            entry = str(self.__file_name)
            ErrorDialog(_('Is it a .gramps?'), _(f'Cannot copy "{entry}"'),parent=self.uistate.window)
            LOG.error('Cannot copy the file')
        except Exception as e:
            raise e


    def read_xml(self, entry):
        """
        Read the .gramps
        """
        self.text.set_text('read the file...')

        use_gzip = self.is_gzip(entry)

        filename = os.path.join(USER_PLUGINS, 'lxml', 'test.xml')
        with open(Path(filename), "w") as temp:
            temp.write('')
        self.close_file(temp)

        if LXML_OK and use_gzip:
            self.uncompress_file(entry, filename)
        elif LXML_OK:
            self.copy_file(Path(filename))

        # XSD structure via lxml

        xsd = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.xsd')
        try:
            if Path(filename).exists():
                LOG.debug('%s' % filename)
                self.xsd(xsd, filename)
            else:
                pass
        except:
            ErrorDialog(_('XSD validation (lxml)'), _(f'Cannot validate "{entry}" !'),parent=self.uistate.window)

        # DTD syntax via xmllint (libxml2-utils)

        try:
            self.check_valid(filename)
            LOG.debug('check validity for %s' % filename)
        except Exception as e:
            LOG.info(_('xmllint: skip DTD validation for "%(file)s"') % {'file': entry})

        # RNG validation via xmllint (libxml2-utils)

        rng = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.rng')

        try:
            if os.name is 'nt':
                os.system(f'xmllint --relaxng {rng} --noout {filename}')
                LOG.debug('xmllint (relaxng) : %s' % filename)
            else:
                LOG.debug('xmllint (relaxng) : %s' % filename)
                os.system(f'xmllint --relaxng file://{rng} --noout {filename}')
        except Exception as e:
            LOG.info(_('xmllint: skip RelaxNG validation for "%(file)s"') % {'file': entry})

        try:
            #etree.ElementTree(file=filename)
            tree = etree.parse(filename)
            doctype = tree.docinfo.doctype
            current = '<!DOCTYPE database PUBLIC "-//Gramps//DTD Gramps XML 1.7.2//EN" "http://gramps-project.org/xml/1.7.2/grampsxml.dtd">'
            if self.rng_validation(tree, rng):
                try:
                    self.xmltodict(Path(filename))
                    self.parse_xml(tree)
                except:
                    ErrorDialog(_('Parsing issue'), _('Cannot parse content of "%(file)s"') % {'file': filename}, parent=self.uistate.window)
                    LOG.debug('Cannot parse the content of the XML copy or missing "query_html.xsl" file.')
            elif doctype == '':
                ErrorDialog(_('Custom "test.xml" file'), _('Please try to fix "test.xml"'), parent=self.uistate.window)
                LOG.debug('Need to find "test.xml"')
                LOG.debug('Filename: %s' % self.__file_name)
                LOG.debug('Base path: %s' % self.__base_path)
                LOG.debug('Temp file: %s' % tree.docinfo.URL)
                LOG.debug('xml version: %s' % tree.docinfo.xml_version)
            elif doctype != current:
                LOG.debug('Namespace is wrong', doctype, current)
            else:
                ErrorDialog(_('RelaxNG validation'), _('Cannot validate "%(file)s" via RelaxNG schema') % {'file': filename}, parent=self.uistate.window)
                LOG.debug('RelaxNG validation failed')
        except TypeError as e:
            LOG.debug('"NoneType" object is not callable')
            LOG.debug(e)
        except OSError:
            if not Path(filename).exists():
                LOG.debug(f'Failed to find {filename}')
                self.copy_file(Path(filename))
            else:
                LOG.debug(etree.parse(filename))
            return
        except etree.XMLSyntaxError as e:
            ErrorDialog(_('File issue'), _('Cannot parse "%(file)s" via etree') % {'file': entry}, parent=self.uistate.window)
            log = e.error_log.filter_from_level(etree.ErrorLevels.FATAL)
            LOG.debug(log)
            debug = e.error_log.last_error
            LOG.debug(debug.domain_name)
            LOG.debug(debug.type_name)
            LOG.debug(debug.filename)
            return


    def xmltodict(self, filename):
        """
        xmltodict python 3rd-party lib
        """
        try:
            import xmltodict, json
            with open(Path(filename), "rb") as file:
                self.text.set_text('xmltodict')
                document = xmltodict.parse(file, dict_constructor=dict)
                LOG.info(xmltodict.unparse(document, pretty=True))
            self.close_file(file)
        except:
            LOG.debug('cannot use xmltodict')
            return


    def parse_xml(self, tree):
        """
        Parse the validated .gramps file
        """
        self.text.set_text('parse...')

        root = tree.getroot()

        # GtkTextView ; buffer limitation ...

        if isinstance(self.text, list):
            pass
        else:
            self.text.set_text(_('Parsing file...'))

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

                if two.tag == (NAMESPACE + 'mediapath'):
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

                    if three.tag == (NAMESPACE + 'ptitle'):
                        if text != private_record:
                            text = str(three.text)
                        if text not in places:
                            places.append(text) # temp display

                    if three.tag == (NAMESPACE + 'pname'):
                        if text != private_record:
                            text = str(three.attrib.get('value'))
                        translation = str(three.attrib.get('lang'))
                        if translation != 'None':
                            text += _(' - (%(lang)s)') % {'lang':translation}
                        else:
                            translation = xml_lang()[0:2]
                            where = text + _(' - (? or %(lang)s)') % {'lang':translation}
                            LOG.info(where)
                        if text not in places:
                            places.append(text) # temp display
                    if three.tag == (NAMESPACE + 'stitle') and three.text not in sources:
                        # need to add an exception
                        sources.append(three.text or "")
                    if three.tag == (NAMESPACE + 'file') and three.items() not in thumbs:
                        thumbs.append(three.items())

                    # search last name

                    for four in three.iter():

                        # with namespace ...

                        if four.tag == (NAMESPACE + 'surname') and four.text != None:
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
                                    'generated by Gramps 6.x.'), parent=self.uistate.window)
            LOG.debug('header missing')
            return

        # dirty XML write method ...
        # need to create a fake entry !

        if int(count_elements(root, name='surname')) > 1:
            nb_surnames = int(count_elements(root, name='surname'))
        else:
            nb_surnames = surnames = [_('0')]

        if int(count_elements(root, name='pname')) > 1:
            nb_pnames = int(count_elements(root, name='pname'))
        else:
            nb_pnames = places = [_('0')]

        if int(count_elements(root, name='note')) > 1:
            nb_notes = int(count_elements(root, name='note'))
        else:
            nb_notes = _('0')

        if int(count_elements(root, name='stitle')) > 1:
            nb_sources = int(count_elements(root, name='stitle'))
        else:
            nb_sources = _('0')

        # time logs

        timestamp.sort()
        if len(timestamp) > 0:
            start = timestamp[0]
            end = timestamp[-1]
            first = epoch(start)
            last = epoch(end)
        else:
            return
        timestamp = []


        header = _('File parsed with') + ' LXML' + str(LXML_VERSION) + '\n\n'
        [(k1, v1),(k2, v2)] = log
        file_info = _('File was generated on ') + v1 + '\n\t' + _(' by Gramps ') + v2 + '\n\n'

        period = _('Period: ') +  first + ' => ' + last + '\n\n'

        # for addons translators ? template .pot ?
        _('\t{number} surname'), _('\t{number} surname; no frequency yet'),
        _('\t{number} place'), _('\t{number} place'),
        _('\t{number} note'), _('\t{number} note')
        surnames_string = ngettext(
                    '\t{number} surname',
                    '\t{number} surnames; no frequency yet\n',
                    nb_surnames).format(number=nb_surnames)
        places_string = ngettext(
                    '\t{number} place',
                    '\t{number} places\n',
                    nb_pnames).format(number=nb_pnames)
        notes_string = ngettext(
                    '\t{number} note',
                    '\t{number} notes\n',
                    nb_notes).format(number=nb_notes)
        sources_string = ngettext(
                    '\t{number} source',
                    '\t{number} sources\n',
                    nb_sources).format(number=nb_sources)

        counters = surnames_string + places_string + notes_string + sources_string 

        libs = '\nLIBXML' + str(LIBXML_VERSION) + '\tLIBXSLT' + str(LIBXSLT_VERSION)

        # GtkTextView

        if isinstance(self.text, list):
            pass
        else:
            self.text.set_text(header + file_info + period + counters + libs)

        LOG.info('### NEW FILES ###')
        LOG.info('content parsed and copied')

        self.print_media(thumbs, mediapath)
        images = os.path.join(USER_PLUGINS, 'lxml', _('Gallery.html'))
        sys.stdout.write(_('1. Has generated a media index on "%(file)s".\n') % {'file': images})

        unique_surnames = list(set(surnames))
        unique_surnames.sort()

        self.write_xml(log, first, last, unique_surnames, places, sources)

    def xsd(self, xsd, filename):
        """
        Validate the XML file against the XSD schema.
        """
        self.text.set_text('validating (XSD)...')

        # syntax check against XSD for file format

        schema = etree.XMLSchema(file=xsd)
        parser = objectify.makeparser(schema = schema)

        if Path(filename).exists():
            try:
                valid = etree.parse(filename)
                root = valid.getroot()
                database = objectify.fromstring(etree.tostring(root, encoding="UTF-8"), parser)
            except:
                ErrorDialog(_('XML SyntaxError'), _('Not a valid .gramps.\n'
                                    'Cannot run the gramplet...\n'
                                    'Please, try to use a .gramps\n'
                                    'generated by Gramps 6.x.'), parent=self.uistate.window)
            LOG.info(_('Matches XSD schema.'))
        else:
            return

        #dump = objectify.dump(database)
        #print(dump)

    def check_valid(self, filename):
        """
        Validate the XML file against the DTD schema.
        """
        self.text.set_text('validating DTD')

        # syntax check against DTD for file format
        # xmllint --loaddtd --dtdvalid --valid --shell --noout ...

        dtd = os.path.join(USER_PLUGINS, 'lxml', 'grampsxml.dtd')
        try:
            if os.name is 'nt':
                os.system(f'xmllint --dtdvalid {dtd} --noout --dropdtd {filename}')
            else:
                os.system(f'xmllint --dtdvalid file://{dtd} --noout --dropdtd {filename}')
        except Exception as e:
            LOG.info(_('xmllint: skip DTD validation'))


    def rng_validation(self, tree, rng):
        """
        Validate the XML file against the RNG schema.
        """
        self.text.set_text('validating rng')

        # validity check against scheme for file format

        valid = etree.ElementTree(file=rng)
        schema = etree.RelaxNG(valid)
        return(schema.validate(tree))


    def write_xml(self, log, first, last, surnames, places, sources):
        """
        Write the result of the query for distributed, shared protocols.
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
        self.jsonl(content)

        # XSLT process

        xslt_doc = etree.parse(os.path.join(USER_PLUGINS, 'lxml', 'query_html.xsl'))
        transform = etree.XSLT(xslt_doc)
        outdoc = transform(content)
        #print(type(outdoc))
        html = os.path.join(USER_PLUGINS, 'lxml', 'query.html')
        with open(html, 'w') as outfile:
            outfile.write(str(outdoc))
        self.close_file(outfile)

        self.write_back_xml(content)

        # clear the etree

        content.clear()

        # This is the end !

        sys.stdout.write(_('2. Has generated "%s".\n') % html)

        LOG.info(_('Try to open\n "%s"\n into your preferred web navigator ...') % html)
        display_url(html)

        self.post(html)


    def print_media(self, thumbs, mediapath):
        """
        Print some media infos via HTML class (Gramps).
        """

        LOG.info('Looking at media...')

        # Web page filename extensions

        _WEB_EXT = ['.html', '.htm', '.shtml', '.php', '.php3', '.cgi']

        # page title

        title = _('Gallery')

        fname = os.path.join(USER_PLUGINS, 'lxml', _('Gallery.html'))
        with open(fname, "w") as of:
            LOG.info('Empty "Gallery.html" file created')

            lang = xml_lang()
            page, head, body = Html.page(title, encoding='utf-8', lang=str(lang))
            head = body = ""

            self.text_page = []

        self.xhtml_writer(fname, page, head, body, of, thumbs, mediapath)

        LOG.info('End (Media)')
        #return self.text

    def __write_gallery(self, thumbs, mediapath):
        """
        This procedure writes out the media.
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
                self.text_page += Html('img', src=str(thumb), mtype=str(mime))
                self.text_page += fullclear
                self.text_page += Html('a', str(description), href=str(src), target='blank', title=str(mime))
                self.text_page += fullclear

        LOG.info(self.text_page)


    def close_file(self, of):
        """Close the file."""
        of.close()


    def xhtml_writer(self, fname, page, head, body, of, thumbs, mediapath):
        """
        Format, write, and close the file.

        of -- open file that is being written to
        htmlinstance -- web page created with libhtml
            plugins/lib/libhtml.py
        """

        self.__write_gallery(thumbs, mediapath)

        #LOG.debug(self.text)

        with open(fname, 'w') as text:
            text.write(head)
            for txt in self.text_page:
                text.write(txt + '\n')

        # closes the file

        self.close_file(of)

        LOG.info('Gallery generated')


    def write_back_xml(self, content):
        """
        Write the result of the query back into the XML file (Gramps scheme).
        """
        outfile = os.path.join(USER_PLUGINS, 'lxml', 'test.xml')

        # Extract elements from the content
        surnames = content.findall(".//surname")
        places = content.findall(".//place")
        sources = content.findall(".//source")

        # Convert elements to strings
        #surnames_strings = etree.tostring(content.find(".//surnames"), method='xml', encoding='utf-8', pretty_print=True).decode('utf-8')
        #places_strings = etree.tostring(content.find(".//places"), method='xml', encoding='utf-8', pretty_print=True).decode('utf-8')
        #sources_strings = etree.tostring(content.find(".//sources"), method='xml', encoding='utf-8', pretty_print=True).decode('utf-8')

        header = b'''<?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE database PUBLIC "-//Gramps//DTD Gramps XML 1.7.2//EN" "http://gramps-project.org/xml/1.7.2/grampsxml.dtd">
        <database xmlns="http://gramps-project.org/xml/1.7.2/">
            <header>
                <created date="2025-03-18" version="6.0.0"/>
                <researcher>
                    <resname></resname>
                </researcher>
                <mediapath>{GRAMPS_RESOURCES}/example/gramps</mediapath>
            </header>
        </database>'''

        # Create the root element
        root = etree.fromstring(header)

        # Add people, places, and sources to the root
        the_id = 0

        # Modify the XML copy of the .gramps

        content.clear()

        ## people/person/name/surname
        people = etree.SubElement(content, "people")
        for s in surnames:
            the_id += 1
            person = etree.SubElement(people, "person")
            person.set('id', f'{the_id}_{len(surnames)}')
            gender = etree.SubElement(person, "gender")
            name = etree.SubElement(person, "name")
            surname = etree.SubElement(name, "surname")
            surname.text = etree.tostring(s, method='xml', pretty_print=True, encoding='utf-8').decode('utf-8')

        ## places/placeobj/pname
        pl = etree.SubElement(content, "places")
        for p in places:
            the_id += 1
            place = etree.SubElement(pl, "placeobj")
            place.set('id', f'{the_id}_{len(places)}')
            name = etree.SubElement(place, "pname")
            val = etree.tostring(p, method='xml', pretty_print=True, encoding='utf-8').decode('utf-8')
            name.set('value', val)

        ## sources/source/stitle
        src = etree.SubElement(content, "sources")
        for sc in sources:
            the_id += 1
            source = etree.SubElement(src, "source")
            source.set('id', f'{the_id}_{len(sources)}')
            stitle = etree.SubElement(source, "stitle")
            stitle.text = etree.tostring(sc, method='xml', pretty_print=True, encoding='utf-8').decode('utf-8')

        # Merge the content into the new root
        for element in content:
            root.append(element)

        # Write the XML to the file
        with open(outfile, 'wb') as my_file:
            my_file.write(etree.tostring(root, method='xml', pretty_print=True, encoding='utf-8'))
        self.close_file(my_file)

        # clear the etree
        content.clear()


    def jsonl(self, content):
        """
        Generate a JSONL file from the custom XML file format
        """
        xslt_doc = etree.parse(os.path.join(USER_PLUGINS, 'lxml', 'JSONL.xsl'))
        transform = etree.XSLT(xslt_doc)
        outdoc = transform(content)

        custom_jsonl = str(outdoc)
        jsonl = os.path.join(USER_PLUGINS, 'lxml', 'text.jsonl')
        outfile = open(jsonl, 'w')

        outfile.write(custom_jsonl)
        outfile.close()

        if isinstance(self.text, list):
            LOG.info(self.text)
        else:
            start_iter = self.text.get_start_iter()
            end_iter = self.text.get_end_iter()
            format = self.text.register_serialize_tagset()
            text = self.text.serialize(self.text,
                                    format,
                                    start_iter,
                                    end_iter)
            LOG.info(text)
            info = self.text.get_text(start_iter, end_iter, True)
            self.text.set_text(custom_jsonl + info)

    def post(self, html):
        """
        Try to play with request and parse the HTML content.
        """
        try:
            # Open the HTML file
            import urllib
            with urllib.request.urlopen(f'file://{html}') as response:
                data = response.read()

            # Parse the HTML content
            post = etree.HTML(data)

            # Find text function
            find_text = etree.XPath("//text()", smart_strings=False)

            # Log the text content
            LOG.info(find_text(post))

            # Clear the parsed HTML content
            post.clear()

        except Exception as e:
            LOG.error(f"An error occurred while processing the HTML file: {e}")
