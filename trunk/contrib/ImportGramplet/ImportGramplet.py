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

#------------------------------------------------------------------------
#
# Python modules
#
#------------------------------------------------------------------------
import StringIO

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gen.plug import Gramplet
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
from ImportXml import GrampsParser, PERSON_RE, DbMixin

#------------------------------------------------------------------------
#
# Gramplet class
#
#------------------------------------------------------------------------
class ImportGramplet(Gramplet):
    """
    """
    def init(self):
        """
        Constructs the GUI, consisting of a text area, and 
        an Import button.
        """
        import gtk
        # GUI setup:
        self.set_tooltip(_("Enter text to import and then click\nthe Import button at bottom"))
        vbox = gtk.VBox()
        self.import_text = gtk.TextView()
        self.import_text.set_wrap_mode(gtk.WRAP_WORD)
        self.import_text.set_editable(True)
        button = gtk.Button(_("Import"))
        button.connect("clicked", self.run)
        vbox.pack_start(self.import_text, True)
        vbox.pack_start(button, False)
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(vbox)
        vbox.show_all()

    def post_init(self):
        self.disconnect("active-changed")

    def run(self, obj):
        """
        Method that is run when you click the Run button.
        The date is retrieved from the entry box, parsed as a date,
        and then handed to the quick report.
        """
        buffer = self.import_text.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        text = buffer.get_text(start, end)
        print text
        self.uistate.set_busy_cursor(1)
        self.uistate.progress.show()
        self.uistate.push_message(self.dbstate, _("Importing Text..."))
        # FIXME: allow file:/// and csv imports as well
        mode = "xml"
        if mode == "xml":
            database = self.dbstate.db
            if DbMixin not in database.__class__.__bases__:
                database.__class__.__bases__ = (DbMixin,) +  \
                    database.__class__.__bases__
            ofile = StringIO.StringIO(text)
            person_count = 0
            line_count = 0
            for line in ofile:
                line_count += 1
                if PERSON_RE.match(line):
                    person_count += 1
            parser = GrampsParser(database, None, 0)
            xml_file = StringIO.StringIO(text)
            try:
                info = parser.parse(xml_file, line_count, person_count)
                print info.info_text()
            except:
                import traceback
                traceback.print_exc()
        elif mode == "csv":
            pass
        elif mode == "file":
            pass
        self.uistate.set_busy_cursor(0)
        self.uistate.progress.hide()
        self.uistate.push_message(self.dbstate, _("Import done"))
