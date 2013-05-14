# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Douglas S. Blank <doug.blank@gmail.com>
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

from __future__ import print_function

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import time
import sys
if sys.version_info[0] < 3:
    from cStringIO import StringIO
else:
    from io import StringIO
from xml.parsers.expat import ParserCreate

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.db import DbTxn
from gramps.gen.plug import Gramplet
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.plugins.importer.importcsv import CSVParser
from gramps.plugins.importer.importvcard import VCardParser
from gramps.plugins.importer.importxml import GrampsParser, PERSON_RE
from gramps.gui.dialog import ErrorDialog

#------------------------------------------------------------------------
#
# AtomicCSVParser class
#
#------------------------------------------------------------------------
class AtomicCSVParser(CSVParser):
    """
    Class that imports CSV files with an ordinary transaction so that the
    import is atomic and can be undone.
    """
    def __init__(self, database, callback=None):
        CSVParser.__init__(self, database, callback)

    def parse(self, filehandle):
        """
        Parse the csv file
        :param filehandle: must be a file handle that is already open, with
                      position at the start of the file
        """
        data = self.read_csv(filehandle)
        with DbTxn(_("CSV import"), self.db, batch=False) as self.trans:
            self._parse_csv_data(data)

#------------------------------------------------------------------------
#
# AtomicVCardParser class
#
#------------------------------------------------------------------------
class AtomicVCardParser(VCardParser):
    """
    Class that imports VCard files with an ordinary transaction so that the
    import is atomic and can be undone.
    """
    def __init__(self, database):
        VCardParser.__init__(self, database)

    def parse(self, filehandle):
        """
        Parse the vcard file
        :param filehandle: must be a file handle that is already open, with
                      position at the start of the file
        """
        self.person = None
        with DbTxn(_("VCard import"), self.database, batch=False) as self.trans:
            self._parse_vCard_file(filehandle)

#------------------------------------------------------------------------
#
# AtomicGrampsParser class
#
#------------------------------------------------------------------------
class AtomicGrampsParser(GrampsParser):
    """
    Class that imports XML files with an ordinary transaction so that the
    import is atomic and can be undone.
    """
    def __init__(self, database, callback, change):
        GrampsParser.__init__(self, database, callback, change)

    def parse(self, ifile, linecount=0, personcount=0):
        """
        Parse the xml file
        :param ifile: must be a file handle that is already open, with position
                      at the start of the file
        """
        with DbTxn(_("Gramps XML import"), self.db, batch=False) as self.trans:
            self.set_total(linecount)

            self.p = ParserCreate()
            self.p.StartElementHandler = self.startElement
            self.p.EndElementHandler = self.endElement
            self.p.CharacterDataHandler = self.characters
            self.p.ParseFile(ifile)

            if len(self.name_formats) > 0:
                # add new name formats to the existing table
                self.db.name_formats += self.name_formats
                # Register new formats
                name_displayer.set_name_format(self.db.name_formats)
    
            self.db.set_researcher(self.owner)
            if self.home is not None:
                person = self.db.get_person_from_handle(self.home)
                self.db.set_default_person_handle(person.handle)
    
            #set media path, this should really do some parsing to convert eg
            # windows path to unix ?
            if self.mediapath:
                oldpath = self.db.get_mediapath()
                if not oldpath:
                    self.db.set_mediapath(self.mediapath)
                elif not oldpath == self.mediapath:
                    ErrorDialog(_("Could not change media path"), 
                        _("The opened file has media path %s, which conflicts "
                          "with the media path of the family tree you import "
                          "into. The original media path has been retained. "
                          "Copy the files to a correct directory or change the "
                          "media path in the Preferences."
                         ) % self.mediapath )

            for key in self.func_map.keys():
                del self.func_map[key]
            del self.func_map
            del self.func_list
            del self.p
        return self.info

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class ImportGramplet(Gramplet):
    """
    Gramplet creating a window on which strings can be dropped for import.
    """
    def init(self):
        """
        Constructs the GUI, consisting of a text area, and 
        an Import and Clear buttons.
        """
        from gi.repository import Gtk
        # GUI setup:
        self.set_tooltip(_("Enter text to import and then click\n"
                           "the Import button at bottom"))
        # create
        self.import_text = Gtk.TextView()
        self.import_text.set_wrap_mode(Gtk.WrapMode.NONE)
        self.import_text.set_editable(True)
        import_button = Gtk.Button()
        clear_button = Gtk.Button()
        # layout
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.add(self.import_text)
        buttonbox = Gtk.HButtonBox()
        buttonbox.set_layout(Gtk.ButtonBoxStyle.SPREAD)
        buttonbox.pack_start(clear_button, False, False, 0)
        buttonbox.pack_start(import_button, False, False, 0)
        vbox = Gtk.VBox()
        vbox.pack_start(scrolled_window, True, True, 0)
        vbox.pack_start(buttonbox, False, False, 0)
        scrolled_window = self.gui.get_container_widget()
        for widget in scrolled_window.get_children():
            widget.destroy()
        scrolled_window.add_with_viewport(vbox)
        scrolled_window.get_children()[0].set_shadow_type(Gtk.ShadowType.NONE)
        # bindings
        actiongroup = Gtk.ActionGroup('GrampletImportActions')
        actiongroup.add_actions([
            ('import', None, _("_Import"), '<Alt>i', None, self.run),
            ('clear', Gtk.STOCK_CLEAR, None, None, None, self.clear)])
        import_button.set_related_action(actiongroup.get_action('import'))
        clear_button.set_related_action(actiongroup.get_action('clear'))
        # show
        vbox.show_all()

    def post_init(self):
        self.disconnect("active-changed")

    def run(self, obj):
        """
        Method that is run when you click the Run button.
        The date is retrieved from the entry box, parsed as a date,
        and then handed to the quick report.
        """
        message = _("Import done")
        buffer = self.import_text.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end, True).strip()
        if not text:
            return
        print(text)
        self.uistate.set_busy_cursor(1)
        self.uistate.progress.show()
        self.uistate.push_message(self.dbstate, _("Importing Text..."))
        database = self.dbstate.db
        ifile = StringIO(text)
        if text.startswith(("Person,Surname,Given", "%s,%s,%s" %
                            (_("Person"), _("Surname"), _("Given")))):
            parser = AtomicCSVParser(database)
            parser.parse(ifile)
        elif text.startswith("0 HEAD"):
            raise NotImplementedError
        elif text.startswith("BEGIN:VCARD"):
            parser = AtomicVCardParser(database)
            parser.parse(ifile)
        elif text.find("""<!DOCTYPE database PUBLIC "-//Gramps//""") > 0:
            ofile = StringIO(text)
            person_count = 0
            line_count = 0
            for line in ofile:
                line_count += 1
                if PERSON_RE.match(line):
                    person_count += 1
            change = int(time.time())
            parser = AtomicGrampsParser(database, None, change)
            try:
                info = parser.parse(ifile, line_count, person_count)
                print(info.info_text())
            except:
                import traceback
                traceback.print_exc()
        else:
            ErrorDialog(_("Can't determine type of import"))
            message = _("Import failed")
        # FIXME: allow file:/// imports as well
        self.uistate.set_busy_cursor(0)
        self.uistate.progress.hide()
        self.uistate.push_message(self.dbstate, message)

    def clear(self, dummy):
        """
        Remove the text in the textview.
        """
        buffer_ = self.import_text.get_buffer()
        start = buffer_.get_start_iter()
        end = buffer_.get_end_iter()
        buffer_.delete(start, end)
