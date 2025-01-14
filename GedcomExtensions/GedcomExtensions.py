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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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
from gramps.gen.lib import EventRoleType, NameOriginType
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

CHECK_OFF = 0
CHECK_ON = 1
PATRONYMIC_NOOP = 0
PATRONYMIC_ADD = 1
PATRONYMIC_IGNORE = 2
SURNAME_FILTER_NOOP = 0
# the rest of surname types come from NameOriginType

def normalize(name):
    return name.strip().replace("/", "?")


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
            self.process_patronymic = option_box.process_patronymic
            self.filter_surname = option_box.filter_surname
        else:
            self.include_witnesses = CHECK_ON
            self.include_media = CHECK_ON
            self.process_patronymic = PATRONYMIC_NOOP
            self.filter_surname = SURNAME_FILTER_NOOP

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
                if not person:
                    continue
                for ref in person.get_event_ref_list():
                    if (ref.ref == event.handle):
                        if int(ref.get_role()) in [EventRoleType.WITNESS, EventRoleType.CELEBRANT, \
                                                   EventRoleType.INFORMANT, EventRoleType.CLERGY, \
                                                   EventRoleType.AIDE, EventRoleType.CUSTOM]:
                            relation = str(ref.get_role())
                            level = 2
                            self._writeln(level, "ASSO", "@%s@" % person.get_gramps_id())
                            self._writeln(level+1, "TYPE", "INDI")
                            self._writeln(level+1, "RELA", relation)
                            self._note_references(ref.get_note_list(), level+1)

    def move_patronymic_name_to_given_name(self, name):
        """
        Remove patronymic name from surnames and add it to the given name.
        Example:  Fyodor (given), Dostoevsky(inherited surname) Mikhailovich (patronymic surname)
                  => Fyodor Mikhailovich (given),  Dostoevsky (inherited surname)
        """
        surnames = []
        givens = [name.first_name]
        for surname in name.get_surname_list():
            if surname.get_origintype() == NameOriginType.PATRONYMIC:
                givens.append(normalize(surname.get_surname()))
            else:
                surnames.append(surname)

        name.first_name = " ".join(givens)
        name.set_surname_list(surnames)
        return name

    def remove_patronymic_name(self, name):
        """
        Remove patronymic name from surnames and add it to the given name.
        Example:  Fyodor (given), Dostoevsky(inherited surname) Mikhailovich (patronymic surname)
                  => Fyodor,  Dostoevsky (inherited surname)
        """
        surnames = [s for s in name.get_surname_list() if s.get_origintype() != NameOriginType.PATRONYMIC]
        name.set_surname_list(surnames)
        return name

    def keep_one_type_of_surname(self, name, type_to_keep):
        """
        Keep only one type of surnames.

        Example:  Maria (given) Skłodowska (inherited) Curie (taken)
                  => noop => Maria (given) Skłodowska (inherited) Curie (taken)
                  => keep inherited => Maria (given) Skłodowska (inherited)
                  => keep taken => Maria (given) Curie (taken)
        """
        surnames = [s for s in name.get_surname_list() if s.get_origintype() == type_to_keep]
        name.set_surname_list(surnames)
        return name

    def _person_name(self, name, attr_nick):
        """
        Overloaded name-handling method to handle patronymic names.
        """
        # TODO: Should Matronymic names be handled similarly?
        if self.process_patronymic == PATRONYMIC_IGNORE:
            name = self.remove_patronymic_name(name)
        elif self.process_patronymic == PATRONYMIC_ADD:
            name = self.move_patronymic_name_to_given_name(name)

        # surname filtering must happen after the patronymic processing
        # as "patronymic" is a type of surname
        if self.filter_surname != SURNAME_FILTER_NOOP:
            name = self.keep_one_type_of_surname(name, self.filter_surname)

        super(GedcomWriterExtension, self)._person_name(name, attr_nick)

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
    def __init__(self, person, dbstate, uistate, track=None, window=None):
        """
        Initialize the local options.
        """
        super(GedcomWriterOptionBox, self).__init__(person, dbstate, uistate,
                                                    track=track, window=window)
        self.include_witnesses = CHECK_ON
        self.include_witnesses_check = None
        self.include_media = CHECK_ON
        self.include_media_check = None
        self.process_patronymic = PATRONYMIC_NOOP
        self.process_patronymic_list = None
        self.filter_surname = SURNAME_FILTER_NOOP
        self.filter_surname_list = None

    def get_option_box(self):
        option_box = super(GedcomWriterOptionBox, self).get_option_box()

        # Make options:
        self.include_witnesses_check = Gtk.CheckButton(_("Include witnesses"))
        self.include_media_check = Gtk.CheckButton(_("Include media"))

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        label = Gtk.Label(label=_("Patronymic names:"))
        self.process_patronymic_list = Gtk.ComboBoxText()
        self.process_patronymic_list.append_text(_("Don't change"))
        self.process_patronymic_list.append_text(_("Add Patronymic name after Given name"))
        self.process_patronymic_list.append_text(_("Ignore Patronymic name"))

        hbox2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        label2 = Gtk.Label(label=_("Keep one type of surnames:"))
        self.filter_surname_list = Gtk.ComboBoxText()
        self.filter_surname_list.append_text(_("Don't change"))
        type_names = NameOriginType().get_standard_names()
        for name in type_names:
            self.filter_surname_list.append_text(name)

        # Set defaults:
        self.include_witnesses_check.set_active(CHECK_ON)
        self.include_media_check.set_active(CHECK_ON)
        self.process_patronymic_list.set_active(PATRONYMIC_NOOP)
        self.filter_surname_list.set_active(SURNAME_FILTER_NOOP)

        # Add to gui:
        option_box.pack_start(self.include_witnesses_check, False, False, 0)
        option_box.pack_start(self.include_media_check, False, False, 0)

        hbox.pack_start(label, False, False, 0)
        hbox.pack_start(self.process_patronymic_list, False, False, 0)
        option_box.pack_start(hbox, False, False, 0)

        hbox2.pack_start(label2, False, False, 0)
        hbox2.pack_start(self.filter_surname_list, False, False, 0)
        option_box.pack_start(hbox2, False, False, 0)

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
        if self.process_patronymic_list:
            self.process_patronymic = self.process_patronymic_list.get_active()
        if self.filter_surname_list:
            self.filter_surname = self.filter_surname_list.get_active()

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
