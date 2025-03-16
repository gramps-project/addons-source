# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009        Brian G. Matherly
# Copyright (C) 2009        Michiel D. Nauta
# Copyright (C) 2010        Douglas S. Blank
# Copyright (C) 2010        Jakim Friant
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
from shutil import copy
from gi.repository import Gtk
from xml.etree import ElementTree
import gzip

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



NAMESPACE = '{http://gramps-project.org/xml/1.7.2/}'

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
    Gramplet for testing etree (python 2.7) and Gramps XML parsing
    """

    def init(self):
        """
        Constructs the GUI, consisting of an entry, a text view and
        a Run button.
        """

        self.last = 5

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
        self.text.set_text(_('No file parsed...'))
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
        if ' ' in entry:
            ErrorDialog(_('Space character on filename'), _('Please fix space on "%s"') % entry)
            return

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
        except IOError:
            use_gzip = 0

        # lazy ...
        if os.name != 'posix' and os.name != 'nt':

            # GtkTextView

            self.text.set_text(_('Sorry, no support for your OS yet!'))
            return

        filename = os.path.join(USER_PLUGINS, 'lxml', 'etree.xml')

        if use_gzip == 1:
            try:
                os.system('gunzip < %s > %s' % (entry, filename))
            except:
                ErrorDialog(_('Is it a compressed .gramps?'), _('Cannot uncompress "%s"') % entry)
                return
            sys.stdout.write(_('From:\n "%(file1)s"\n to:\n "%(file2)s".\n') % {'file1': entry, 'file2': filename})
        else:
            try:
                copy(entry, filename)
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

        for one in root.getchildren():

            # iter() for python 2.7 and greater versions
            ITERATION = one.iter()

            # Primary objects (samples)

            # find() needs memory - /!\ large files

            # FutureWarning:
            # The behavior of this method will change in future versions.
            # Use specific 'len(elem)' or 'elem is not None' test instead.

            if one.find(NAMESPACE + 'event'):
                print('XML: Find all "event" records: %s' % len(one.findall(NAMESPACE + 'event')))

            # easier and faster match (do not forget upercase on handle into .gramps...)
            if one.get('home'):
                if self.dbstate.db.db_is_open:
                    if self.dbstate.db.has_person_handle("%s" % one.attrib.get('home')[1:]):
                        person = self.dbstate.db.get_person_from_handle(one.attrib.get('home')[1:])
                        print('Home:', person.get_primary_name().get_name())

            for two in ITERATION:

                if two.get('change') != None:
                    timestamp.append(two.get('change'))

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

        #for key in keys:
            #print(key)

        # XML

        timestamp.sort()

        if len(timestamp) < self.last:
            self.last = len(timestamp)

        last = []
        for i in range(self.last):
            if i == 0:
                last.append(timestamp[-1])
            else:
                last.append(timestamp[-i])

        last.sort()
        start = epoch(last[1])

        time = _('XML: Last %s editions since %s, were at/on :\n' % (int(self.last), start))
        for i in last:
            time +=  '\t * %s\n' % epoch(i)

        # GtkTextView

        self.counters(time, entries, tags, events, people, families, sources, citations, places, objects, repositories, notes)

        # DB

        if self.dbstate.db.db_is_open:
            self.change()


    def change(self):
        """
        obj.get_change_time(); Family Tree loaded
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
        Set of counters for parsed Gramps XML and loaded family tree
        """

        total = _('\nXML: Number of records and relations : \t%s\n\n') % len(entries)

        if self.dbstate.db.db_is_open:
            tag = _('Number of tags : \n\t\t\t%s\t|\t(%s)*\n') % (len(tags), self.dbstate.db.get_number_of_tags())
        else:
            tag = _('Number of tags : \n\t\t\t%s\n' % len(tags))

        event = _('Number of  events : \n\t\t\t%s\t|\t(%s)*\n') % (len(events), self.dbstate.db.get_number_of_events())
        #DummyDB
        if self.dbstate.db.db_is_open:
            person = _('Number of persons : \n\t\t\t%s\t|\t(%s) and (%s)* surnames\n') % (len(people), self.dbstate.db.get_number_of_people(), len(self.dbstate.db.surname_list))
        else:
            person = _('Number of persons : \n\t\t\t%s\t|\t(%s)*\n') % (len(people), self.dbstate.db.get_number_of_people())
        family = _('Number of families : \n\t\t\t%s\t|\t(%s)*\n') % (len(families), self.dbstate.db.get_number_of_families())
        source = _('Number of sources : \n\t\t\t%s\t|\t(%s)*\n') % (len(sources), self.dbstate.db.get_number_of_sources())
        if self.dbstate.db.db_is_open:
            citation = _('Number of citations : \n\t\t\t%s\t|\t(%s)*\n') % (len(citations), self.dbstate.db.get_number_of_citations())
        else:
            citation = ''
        place = _('Number of places : \n\t\t\t%s\t|\t(%s)*\n') % (len(places), self.dbstate.db.get_number_of_places())
        media = _('Number of media objects : \n\t\t\t%s\t|\t(%s)*\n') % (len(objects), self.dbstate.db.get_number_of_media())
        repository = _('Number of repositories : \n\t\t\t%s\t|\t(%s)*\n') % (len(repositories), self.dbstate.db.get_number_of_repositories())
        note = _('Number of notes : \n\t\t\t%s\t|\t(%s)*\n') % (len(notes), self.dbstate.db.get_number_of_notes())

        others = len(entries) - (len(tags) + len(events) + len(people) + len(families) + len(sources) + \
        len(citations) + len(places) + len(objects) + len(repositories) + len(notes))

        other = _('\nXML: Number of additional records and relations: \t%s\n') % others

        #DummyDB
        if self.dbstate.db.db_is_open:
            nb  = _('* loaded Family Tree base:\n "%s"\n' % self.dbstate.db.path)
        else:
            nb = ''

        preview = time + total + tag + event + person + family + source + citation\
        + place + media + repository + note + nb + other

        self.text.set_text(preview)

