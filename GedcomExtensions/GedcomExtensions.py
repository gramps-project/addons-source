#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012  Bastien Jacquet
# Copyright (C) 2012  Doug Blank <doug.blank@gmail.com>
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

# $Id: $

""" 
Extends GedcomWriter to include common non-compliant GEDCOM additions.
"""
#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

from gramps.plugins.export import exportgedcom
from gramps.gui.plug.export import WriterOptionBox
from gramps.gen.errors import DatabaseError
from gramps.gen.lib import EventRoleType
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

class GedcomWriterExtension(exportgedcom.GedcomWriter):
    """
    GedcomWriter Extensions.
    """
    def __init__(self, database, user, option_box=None):
        super(GedcomWriterExtension, self).__init__(database, user, option_box)
        if option_box:
            # Already parsed in GedcomWriter
            self.include_witnesses = option_box.include_witnesses
            self.include_media = option_box.include_media
        else:
            self.include_witnesses = 1
            self.include_media = 1

    def _photo(self, photo, level):
        """
        Overloaded media-handling method to skip over media
        if not included.
        """
        if self.include_media:
            super(GedcomWriterExtension, self)._photo(photo, level)

    def _process_family_event(self, event, event_ref):
        """
        Write the witnesses associated with the family event. 
        based on http://www.geneanet.org/forum/index.php?topic=432352.0&lang=fr
        """
        super(GedcomWriterExtension, self)._process_family_event(event, 
                                                                 event_ref)
        if self.include_witnesses:
            for (objclass, handle) in self.dbase.find_backlink_handles(
                event.handle, ['Person']):
                person = self.dbase.get_person_from_handle(handle)
                for ref in person.get_event_ref_list():
                    if (ref.ref == event.handle and 
                        int(ref.get_role()) == EventRoleType.WITNESS):
                        level = 1
                        self._writeln(level, "ASSO", "@%s@" % person.get_gramps_id())
                        self._writeln(level+1, "TYPE", "INDI")
                        self._writeln(level+1, "RELA", "Witness")
                        self._note_references(ref.get_note_list(), level+1)

#-------------------------------------------------------------------------
#
# GedcomWriter Options
#
#-------------------------------------------------------------------------
class GedcomWriterOptionBox(WriterOptionBox):
    """
    Create a VBox with the option widgets and define methods to retrieve
    the options. 
    
    """
    def __init__(self, person, dbstate, uistate):
        """
        Initialize the local options.
        """
        super(GedcomWriterOptionBox, self).__init__(person, dbstate, uistate)
        self.include_witnesses = 1
        self.include_witnesses_check = None
        self.include_media = 1
        self.include_media_check = None

    def get_option_box(self):
        option_box = super(GedcomWriterOptionBox, self).get_option_box()
        # Make options:
        self.include_witnesses_check = Gtk.CheckButton(_("Include witnesses"))
        self.include_media_check = Gtk.CheckButton(_("Include media"))
        # Set defaults:
        self.include_witnesses_check.set_active(1) 
        self.include_media_check.set_active(1) 
        # Add to gui:
        option_box.pack_start(self.include_witnesses_check, False, False, 0)
        option_box.pack_start(self.include_media_check, False, False, 0)
        # Return option box:
        return option_box

    def parse_options(self):
        """
        Get the options and store locally.
        """
        super(GedcomWriterOptionBox, self).parse_options()
        if self.include_witnesses_check:
            self.include_witnesses = self.include_witnesses_check.get_active()
        if self.include_media_check:
            self.include_media = self.include_media_check.get_active()

def export_data(database, filename, user, option_box=None):
    """
    External interface used to register with the plugin system.
    """
    ret = False
    try:
        ged_write = GedcomWriterExtension(database, user, option_box)
        ret = ged_write.write_gedcom_file(filename)
    except IOError as msg:
        msg2 = _("Could not create %s") % filename
        user.notify_error(msg2, msg)
    except DatabaseError as msg:
        user.notify_db_error(_("Export failed"), msg)
    return ret
