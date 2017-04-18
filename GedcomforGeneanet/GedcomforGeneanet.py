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
import gramps.plugins.lib.libgedcom as libgedcom

from gramps.plugins.export import exportgedcom
from gramps.gui.plug.export import WriterOptionBox
from gramps.gen.errors import DatabaseError
from gramps.gen.lib import (EventRoleType, FamilyRelType, EventType, Person, AttributeType)
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# sort_handles_by_id
#
#-------------------------------------------------------------------------
def sort_handles_by_id(handle_list, handle_to_object):
    """
    Sort a list of handles by the Gramps ID. 
    
    The function that returns the object from the handle needs to be supplied 
    so that we get the right object.
    
    """
    sorted_list = []
    for handle in handle_list:
        obj = handle_to_object(handle)
        if obj:
            data = (obj.get_gramps_id(), handle)
            sorted_list.append (data)
    sorted_list.sort()
    return sorted_list


class GedcomWriterforGeneanet(exportgedcom.GedcomWriter):
    """
    GedcomWriter forGeneanets.
    """
    def __init__(self, database, user, option_box=None):
        super(GedcomWriterforGeneanet, self).__init__(database, user, option_box)
        if option_box:
            # Already parsed in GedcomWriter
            self.include_witnesses = option_box.include_witnesses
            self.include_media = option_box.include_media
            self.include_depot = option_box.include_depot
        else:
            self.include_witnesses = 1
            self.include_media = 1
            self.include_depot = 1

    
    def _photo(self, photo, level):
        """
        Overloaded media-handling method to skip over media
        if not included.
        """
        if self.include_media:
            super(GedcomWriterforGeneanet, self)._photo(photo, level)

    def _family_events(self, family):
        super(GedcomWriterforGeneanet, self)._family_events(family)
        level = 1
#        self._writeln(level,"TEST")
        if (int(family.get_relationship()) == FamilyRelType.UNMARRIED or int(family.get_relationship()) == FamilyRelType.UNKNOWN):
            self._writeln(level, "_UST", "COHABITATION")
    
    def _process_family_event(self, event, event_ref):
        """
        Write the witnesses associated with the family event.
        based on http://www.geneanet.org/forum/index.php?topic=432352.0&lang=fr
        """
        super(GedcomWriterforGeneanet, self)._process_family_event(event,\
                                                                 event_ref)
        if self.include_witnesses:
            for (objclass, handle) in self.dbase.find_backlink_handles(
                event.handle, ['Person']):
                person = self.dbase.get_person_from_handle(handle)
                if person:
                    for ref in person.get_event_ref_list():
                        if ref.ref == event.handle:
                            if int(ref.get_role()) in [EventRoleType.WITNESS,EventRoleType.CELEBRANT,\
                        EventRoleType.INFORMANT,\
                             EventRoleType.CLERGY, EventRoleType.AIDE, EventRoleType.CUSTOM]:
                                level = 2
                                self._writeln(level, "ASSO", "@%s@" % person.get_gramps_id())
                                self._writeln(level+1, "TYPE", "INDI")
                                self._writeln(level+1, "RELA", "Witness")
                                self._note_references(ref.get_note_list(), level+1)

    def _sources(self):
        """
        Write out the list of sources, sorting by Gramps ID.
        """
        self.reset(_("Writing sources"))
        self.progress_cnt += 1
        self.update(self.progress_cnt)
        sorted_list = sort_handles_by_id(self.dbase.get_source_handles(),
                                         self.dbase.get_source_from_handle)

        for (source_id, handle) in sorted_list:
            source = self.dbase.get_source_from_handle(handle)
            if source is None: continue
            self._writeln(0, '@%s@' % source_id, 'SOUR')
            if source.get_title():
                self._writeln(1, 'TITL', source.get_title())

            if source.get_author():
                self._writeln(1, "AUTH", source.get_author())

            if source.get_publication_info():
                self._writeln(1, "PUBL", source.get_publication_info())

            if source.get_abbreviation():
                self._writeln(1, 'ABBR', source.get_abbreviation())

            self._photos(source.get_media_list(), 1)

            if self.include_depot:
                for reporef in source.get_reporef_list():
                    self._reporef(reporef, 1)
                    break

            self._note_references(source.get_note_list(), 1)
            self._change(source.get_change_time(), 1)

 
    def _person_event_ref(self, key, event_ref):
        """
        Write the witnesses associated with the birth and death event. 
        based on http://www.geneanet.org/forum/index.php?topic=432352.0&lang=fr
        """
        super(GedcomWriterforGeneanet, self)._person_event_ref(key,event_ref)
        if self.include_witnesses and event_ref:
            role = int(event_ref.get_role())
            if role != EventRoleType.PRIMARY:
                return
            event = self.dbase.get_event_from_handle(event_ref.ref)
            etype = int(event.get_type())
            devel = 2
#            self._writeln(devel , "DEBUG NAISS OR DEATH TYPE", "@%s@" % etype)
#            self._writeln(devel , "DEBUG NAISS OR DEATH ROLE", "@%s@" % role)
            for (objclass, handle) in self.dbase.find_backlink_handles(
                event.handle, ['Person']):
                person = self.dbase.get_person_from_handle(handle)
                if person:
                    for ref in person.get_event_ref_list():
                        devel = 2
#                        self._writeln(devel , "DEBUG  ", "@%s@" % int(ref.get_role()))
                        if (ref.ref == event.handle): 
                            if int(ref.get_role()) in [EventRoleType.WITNESS,EventRoleType.CELEBRANT, EventRoleType.INFORMANT, EventRoleType.AIDE ,EventRoleType.CLERGY, EventRoleType.AIDE,EventRoleType.CUSTOM]:
                                level = 2
                                self._writeln(level, "ASSO", "@%s@" % person.get_gramps_id())
                                self._writeln(level+1, "TYPE", "INDI")
                                self._writeln(level+1, "RELA", "Witness")
                                self._note_references(ref.get_note_list(), level+1)

    def _process_person_event(self, person ,event ,event_ref):
        """
        Write the witnesses associated with other personnal event. 
        """
        super(GedcomWriterforGeneanet, self)._process_person_event(person , event , event_ref)
        etype = int(event.get_type())
        # if the event is a birth or death, skip it.
        if etype in (EventType.BIRTH, EventType.DEATH, EventType.MARRIAGE):
            return
        role = int(event_ref.get_role())
        if role != EventRoleType.PRIMARY:
            return
#        devel = 2
#        self._writeln(devel, "DEBUG EVEN TYPE", "@%s@" % etype)
#        self._writeln(devel, "DEBUG EVEN ROLE", "@%s@" % role)
        if self.include_witnesses:
            if etype in (EventType.BAPTISM, EventType.CHRISTEN):
#                self._writeln(devel , "DEBUG BAPT ROLE", "@%s@" % role)
                for (objclass, handle) in self.dbase.find_backlink_handles(
                    event.handle, ['Person']):
                    person2 = self.dbase.get_person_from_handle(handle)
                    if person2 and person2 != person:
                        for ref in person2.get_event_ref_list():
                            if (ref.ref == event.handle):
                                if (int(ref.get_role()) == EventRoleType.CUSTOM):
                                    level = 1
                                    self._writeln(level, "ASSO", "@%s@" % person2.get_gramps_id())
                                    self._writeln(level+1, "TYPE", "INDI")
                                    if person2.get_gender() == Person.MALE:
                                        self._writeln(level+1, "RELA", "Godfather")
                                    elif person2.get_gender() == Person.FEMALE:
                                        self._writeln(level+1, "RELA", "Godmother")
                                    else:
                                        self._writeln(level+1, "RELA", "Unknown")

                                    self._note_references(ref.get_note_list(), level+1)
                                else:
                                    level = 2
                                    self._writeln(level, "ASSO", "@%s@" % person2.get_gramps_id())
                                    self._writeln(level+1, "TYPE", "INDI")
                                    self._writeln(level+1, "RELA", "Witness")
                                    self._note_references(ref.get_note_list(), level+1)
            else:
                devel = 2
#                self._writeln(devel , "DEBUG NON BAPT ", "@%s@" % etype)
                for (objclass, handle) in self.dbase.find_backlink_handles(
                    event.handle, ['Person']):
                    person2 = self.dbase.get_person_from_handle(handle)
                    if person2 and person != person2:
                        for ref in person2.get_event_ref_list():
                            if (ref.ref == event.handle):  
                                if int(ref.get_role()) in [EventRoleType.WITNESS, EventRoleType.CELEBRANT, EventRoleType.INFORMANT, EventRoleType.AIDE, EventRoleType.CLERGY, EventRoleType.AIDE, EventRoleType.CUSTOM]:
#                                self._writeln(devel , "DEBUG NON BAPT 2 ", "@%s@" % int(ref.get_role()))
                                    level = 2
#pylint: disable=maybe-no-member
                                    self._writeln(level, "ASSO", "@%s@" % person2.get_gramps_id())
                                    self._writeln(level+1, "TYPE", "INDI")
                                    self._writeln(level+1, "RELA", "Witness")
                                    self._note_references(ref.get_note_list(), level+1)

    def _attributes(self, person):
        """
        Write out the attributes to the GEDCOM file.
        
        Since we have already looked at nicknames when we generated the names,
        we filter them out here.

        We use the GEDCOM 5.5.1 FACT command to write out attributes not
        built in to GEDCOM.

        """

        # filter out the nicknames
        attr_list = [attr for attr in person.get_attribute_list()
                      if attr.get_type() != AttributeType.NICKNAME]

        for attr in attr_list:

            attr_type = int(attr.get_type())
            name = libgedcom.PERSONALCONSTANTATTRIBUTES.get(attr_type)
            key = str(attr.get_type())
            value = attr.get_value().strip().replace('\r', ' ')

            if key in ("AFN", "RFN", "REFN", "_UID", "_FSFTID"):
#pylint: disable=maybe-no-member
                self._writeln(1, key, value)
                continue

            if key == "RESN":
                self._writeln(1, 'RESN')
                continue

            if name and name.strip():
                self._writeln(1, name, value)
            elif value:
                if not value.find("ID Gramps"):
#pylint: disable=maybe-no-member
                    self._writeln(1, 'FACT', value)
                    self._writeln(2, 'TYPE', key)
            else:
                continue
            self._note_references(attr.get_note_list(), 2)
            self._source_references(attr.get_citation_list(), 2)


#-------------------------------------------------------------------------
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
        self.include_depot = 1
        self.include_depot_check = None

    def get_option_box(self):
        option_box = super(GedcomWriterOptionBox, self).get_option_box()
        # Make options:
        self.include_witnesses_check = Gtk.CheckButton(_("Include witnesses"))
        self.include_media_check = Gtk.CheckButton(_("Include media"))
        self.include_depot_check = Gtk.CheckButton(_("Include depot in sources"))
        # Set defaults:
        self.include_witnesses_check.set_active(1)
        self.include_media_check.set_active(1)
        self.include_depot_check.set_active(1)
        # Add to gui:
        option_box.pack_start(self.include_witnesses_check, False, False, 0)
        option_box.pack_start(self.include_media_check, False, False, 0)
        option_box.pack_start(self.include_depot_check, False, False, 0)
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
        if self.include_depot_check:
            self.include_depot = self.include_depot_check.get_active()

def export_data(database, filename, user, option_box=None):
    """
    External interface used to register with the plugin system.
    """
    ret = False
    try:
        ged_write = GedcomWriterforGeneanet(database, user, option_box)
#pylint: disable=maybe-no-member
        ret = ged_write.write_gedcom_file(filename)
    except IOError as msg:
        msg2 = _("Could not create %s") % filename
        user.notify_error(msg2, msg)
    except DatabaseError as msg:
        user.notify_db_error(_("Export failed"), msg)
    return ret
