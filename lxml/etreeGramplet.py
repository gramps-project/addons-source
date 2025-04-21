# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009        Brian G. Matherly
# Copyright (C) 2009        Michiel D. Nauta
# Copyright (C) 2010        Douglas S. Blank
# Copyright (C) 2010        Jakim Friant
# Copyright (C) 2012-2025   Jerome Rapinat
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
import codecs
import sys
import os
from shutil import copyfile
from gi.repository import Gtk
from xml.etree import ElementTree
import gzip
from pathlib import Path

desktop_session = os.environ.get("DESKTOP_SESSION")

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.lib import date
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.gen.const import USER_HOME, USER_PLUGINS
from gramps.gui.dialog import ErrorDialog

#from gen.merge.mergeevent import MergeEventQuery
#from gen.merge.mergeperson import MergePersonQuery
#from gen.merge.mergefamily import MergeFamilyQuery
#from gen.merge.mergesource import MergeSourceQuery
#from gen.merge.mergecitation import MergeCitationQuery
#from gen.merge.mergeplace import MergePlaceQuery
#from gen.merge.mergemedia import MergeMediaQuery
#from gen.merge.mergerepository import MergeRepoQuery
#from gen.merge.mergenote import MergeNoteQuery

NAMESPACE = '{http://gramps-project.org/xml/1.7.1/}'

#-------------------------------------------------------------------------
#
# Timestamp convertor
#
#-------------------------------------------------------------------------
def epoch(t):
    """
    Convert a timestamp to a human-readable date format.
    """
    try:
        from datetime import datetime
    except ImportError:
        return 'Unknown'
    if t is None:
        return _('Invalid timestamp')

    date = int(t)
    conv = datetime.fromtimestamp(date)
    return conv.strftime('%d %B %Y')

#-------------------------------------------------------------------------
#
# The gramplet
#
#-------------------------------------------------------------------------

class etreeGramplet(Gramplet):
    """
    Gramplet for testing etree (Python 2.7) and Gramps XML parsing
    """

    def init(self):
        """
        Constructs the GUI, consisting of an entry, a text view and a Run button.
        """

        self.last = 5

        # file selection

        self.__base_path = USER_HOME
        self.__file_name = str(Path.home())
        self.entry = Gtk.Entry()
        self.entry.set_text(self.__file_name)

        self.button = Gtk.Button()
        if os.name == 'nt'or sys.platform == "darwin":
            self.button = Gtk.Button(_("Select file"))
            #self.button.set_size_request(40, 40)
        else:
            print(desktop_session) # works on pantheon
            image = Gtk.Image.new_from_icon_name(Gtk.STOCK_FIND, 6)
            self.button.add(image)
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
            print(desktop_session) # works on pantheon
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

        dialog = Gtk.FileChooserDialog('etree',
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


    def build_options(self):
        from gramps.gen.plug.menu import NumberOption
        self.add_option(NumberOption(_("Number of editions back"),
                                     self.last, 2, 5000))


    def save_options(self):
        self.last = int(self.get_option(_("Number of editions back")).get_value())


    def run(self, obj):
        """
        Method that is run when you click the Run button.
        """

        entry = self.entry.get_text()

        #if Path(os.path.join(USER_PLUGINS, 'lxml', 'etree.xml')).exists():
            #Path.unlink(os.path.join(USER_PLUGINS, 'lxml', 'etree.xml'))

        if not self.__file_name.endswith('.gramps'):
            print(self.__file_name)
            return

        if self.__file_name != "":
            sys.excepthook = self.read_xml(entry)


    def is_gzip(self, entry):
        """
        Check if the file is gzip compressed.
        """
        try:
            with gzip.open(entry, "r") as test:
                test.read(1)
            return True
        except IOError:
            return False


    def uncompress_file(self, entry, filename):
        """
        Uncompress the gzip file.
        """
        try:
            os.system(f'gunzip < "{entry}" > "{filename}"')
        except Exception as e:
            ErrorDialog(_('Is it a compressed .gramps?'), _('Cannot uncompress "%s"') % entry)
            raise e


    def copy_file(self, entry, filename):
        """
        Copy the file to the destination.
        """
        try:
            copyfile(entry, filename)
        except FileNotFoundError or IsADirectoryError as e:
            ErrorDialog(_('Is it a .gramps?'), _('Cannot copy "%s"') % entry)
            raise e


    def read_xml(self, entry):
        """
        Read the .gramps
        """
        self.text.set_text('Reading the file...')

        use_gzip = self.is_gzip(entry)

        # lazy ...
        if os.name != 'posix' and os.name != 'nt':

            # GtkTextView

            self.text.set_text(_('Sorry, no support for your OS yet!'))
            return

        filename = os.path.join(USER_PLUGINS, 'lxml', 'etree.xml')

        if use_gzip:
            self.uncompress_file(entry, filename)
        else:
            self.copy_file(entry, filename)

        try:
            tree = ElementTree.parse(Path(filename))
            self.parse_xml(tree, Path(filename))
        except FileNotFoundError as e:
             ErrorDialog(_('Filenames issue on filename path'), '%s' % e)


    def parse_xml(self, tree, filename):
        """
        Parse the .gramps
        """

        root = tree.getroot()

        # GtkTextView ; buffer limitation ...

        #self.text.set_text(ElementTree.tostring(root))

        # timestamp

        timestamp = []
        timestamp_int = []

        # XML attributes

        # CVS, RCS like
        keys = []

        # counters
        entries = []
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

        # DB: Family Tree loaded
        # see gen/plug/_gramplet.py and gen/db/read.py

        if self.dbstate.db.db_is_open:
            print('tags', self.dbstate.db.get_number_of_tags())

        print('events', self.dbstate.db.get_number_of_events())
        print('people', self.dbstate.db.get_number_of_people())
        print('families', self.dbstate.db.get_number_of_families())
        print('sources', self.dbstate.db.get_number_of_sources())
        if self.dbstate.db.db_is_open:
            print('citations', self.dbstate.db.get_number_of_citations())
        print('places', self.dbstate.db.get_number_of_places())
        print('objects', self.dbstate.db.get_number_of_media())
        print('repositories', self.dbstate.db.get_number_of_repositories())
        print('notes', self.dbstate.db.get_number_of_notes())

        #print('emap', self.dbstate.db.emap_index)
        #print('pmap', self.dbstate.db.pmap_index)
        #print('fmap', self.dbstate.db.fmap_index)
        #print('smap', self.dbstate.db.smap_index)
        #print('cmap', self.dbstate.db.cmap_index)
        #print('lmap', self.dbstate.db.lmap_index)
        #print('omap', self.dbstate.db.omap_index)
        #print('rmap', self.dbstate.db.rmap_index)
        #print('nmap', self.dbstate.db.nmap_index)

        #print(self.dbstate.db.surname_list)

        # XML

        for one in root:

            # iter() for python 2.7 and greater versions
            ITERATION = one.iter()

            # Primary objects (samples)

            # find() needs memory - /!\ large files

            # FutureWarning:
            # The behavior of this method will change in future versions.
            # Use specific 'len(elem)' or 'elem is not None' test instead.

            lines = lazy = []
            if one.find(NAMESPACE + 'event'):
                print('XML: Find all "event" records: %s' % len(one.findall(NAMESPACE + 'event')))

            for i in range(0, len(one.findall(NAMESPACE + 'event'))):
                event = one.findall(NAMESPACE + 'event')[i]
                lines.append(event.items())
                print('Event:', ElementTree.tostring(event))
                lazy = list(lines)
            print(lazy)

            # easier and faster match (do not forget upercase on handle into .gramps...)
            if one.get('home'):
                if self.dbstate.db.db_is_open:
                    if self.dbstate.db.has_person_handle("%s" % one.attrib.get('home')[1:]):
                        person = self.dbstate.db.get_person_from_handle(one.attrib.get('home')[1:])
                        print('Home:', person.get_primary_name().get_name())

            for two in ITERATION:

                if two.get('change') != None:
                    timestamp.append(two.get('change'))
                    timestamp_int.append(int(two.get('change')))

                #if two.get('handle') != None:
                    #print('%s\n\t, %s'% (two.tag, two.items()))

                #if two.get('priv') != None:
                    #print('\tPrivate : %s, %s' % (two.tag, two.items()))

                #if two.find(NAMESPACE + 'dateval') != None:
                    #print('Date on event: %s' % two.items())

                #if two.find(NAMESPACE + 'place') != None:
                    #print('\tEvent record with places: %s' % two.items())

                #if two.find(NAMESPACE + 'citationref') != None:
                    #print('\t\tEvent record with citation/source: %s' % two.items())

                (tag, item) = two.tag, two.items()
                #print(tag)
                #print(two.attrib)

                entries.append(tag)

                # two for serialisation (complete data/sequence) and/or ElementTree
                keys.append((two, item))

                if tag == NAMESPACE + 'tag':
                    tags.append(two)
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
                if tag == NAMESPACE + 'placeobj':
                    places.append(two)
                if tag == NAMESPACE + 'object':
                    objects.append(two)
                if tag == NAMESPACE + 'repository':
                    repositories.append(two)
                if tag == NAMESPACE + 'note':
                    notes.append(two)

                #if tag == NAMESPACE + 'name':
                    #print('NAME', two, item)

        root.clear()

        # to see changes and match existing handles (Family Tree loaded)

        timestamp_control_like = sum(timestamp_int)
        print('Timestamp sum and control: %d' % timestamp_control_like)
        time = date.Today()
        try:
            from datetime import datetime
            from time import strftime
            from decimal import Decimal
            today_timestamp = datetime.strptime(str(time), "%Y-%m-%d").timestamp()
            today_no_float = f"{today_timestamp:.0f}"
            print('Today:', time, today_no_float)
        except ImportError:
            pass

        #for key in keys:
            #print(key)

        # lazy
        #jsonl_output = "\n".join(lines)
        #print('########JSONL#########\n%s' % jsonl_output)

        # XML

        timestamp.sort()

        if len(timestamp) < self.last:
            self.last = len(timestamp)

        last = [timestamp[-i] for i in range(1, self.last + 1)]

        last.sort()
        start = epoch(last[1])

        time = _('XML: Last %s additions and modifications since %s, were on :\n' % (int(self.last), start))
        for i in last:
            time += '\t * %s\n' % epoch(i)

        # GtkTextView

        self.counters(time, entries, tags, events, people, families, sources, citations, places, objects, repositories, notes)

        # DB

        if self.dbstate.db.db_is_open:
            self.change()


    def change(self):
        """
        obj.get_change_time(); Family Tree loaded
        Display changes in the database.
        """

        # event object

        tevent = []

        for handle in self.dbstate.db.get_event_handles():
            event = self.dbstate.db.get_event_from_handle(handle)
            tevent.append(event.get_change_time())

        tevent.sort()

        try:
            elast = epoch(tevent[-1])
            print('DB: Last event object edition on/at:', elast)
        except IndexError:
            pass

        handles = sorted(self.dbstate.db.get_person_handles(), key=self._getPersonTimestamp)

        print('DB: Last %s persons edited:' % int(self.last))
        for handle in reversed(handles[-self.last:]):
            person = self.dbstate.db.get_person_from_handle(handle)
            print(person.get_primary_name().get_name(), handle)


    def _getPersonTimestamp(self, person_handle):
        timestamp = self.dbstate.db.get_person_from_handle(person_handle).change
        return timestamp


    def counters(self, time, entries, tags, events, people, families, sources, citations, places, objects, repositories, notes):
        """
        Display counters for parsed Gramps XML and loaded family tree
        """

        total = _('\nXML: Number of records and relations : \t%s\n\n') % len(entries)

        if self.dbstate.db.db_is_open:
            tag = _('Number of tags : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(tags), self.dbstate.db.get_number_of_tags())
        else:
            tag = _('Number of tags : \n\t\t\t%06s\n' % len(tags))

        event = _('Number of  events : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(events), self.dbstate.db.get_number_of_events())
        #DummyDB
        if self.dbstate.db.db_is_open:
            person = _('Number of persons : \n\t\t\t%06s\t|\t(%06s) and (%06s)* surnames\n') % (len(people), self.dbstate.db.get_number_of_people(), len(self.dbstate.db.surname_list))
        else:
            person = _('Number of persons : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(people), self.dbstate.db.get_number_of_people())
        family = _('Number of families : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(families), self.dbstate.db.get_number_of_families())
        source = _('Number of sources : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(sources), self.dbstate.db.get_number_of_sources())
        if self.dbstate.db.db_is_open:
            citation = _('Number of citations : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(citations), self.dbstate.db.get_number_of_citations())
        else:
            citation = ''
        place = _('Number of places : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(places), self.dbstate.db.get_number_of_places())
        media = _('Number of media objects : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(objects), self.dbstate.db.get_number_of_media())
        repository = _('Number of repositories : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(repositories), self.dbstate.db.get_number_of_repositories())
        note = _('Number of notes : \n\t\t\t%06s\t|\t(%06s)*\n') % (len(notes), self.dbstate.db.get_number_of_notes())

        others = len(entries) - (len(tags) + len(events) + len(people) + len(families) + len(sources) + \
        len(citations) + len(places) + len(objects) + len(repositories) + len(notes))

        other = _('\nXML: Number of additional records and relations: \t%s\n') % others

        #DummyDB
        if self.dbstate.db.db_is_open:
            nb = _('* loaded Family Tree base:\n "%s"\n' % self.dbstate.db.path)
        else:
            nb = ''

        preview = time + total + tag + event + person + family + source + citation + place + media + repository + note + nb + other

        self.text.set_text(preview)
