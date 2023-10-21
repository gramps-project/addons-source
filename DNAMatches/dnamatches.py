#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020        Nick Hall
# Copyright (C) 2020-2022   Gary Griffin
# Copyright (C) 2023        Milan Kurovsky
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

"""
DNA Matches Gramplet
This Gramplet lists a user's DNA matches.
"""
#-------------------------------------------------------------------------
#
# Non-Gramps Modules
#
#-------------------------------------------------------------------------
import re
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gui.listmodel import ListModel, NOSORT
from gramps.gui.editors import EditPersonRef
from gramps.gen.plug import Gramplet
from gramps.gen.lib import Date
from gramps.gen.errors import WindowActiveError
from gramps.gen.display.name import displayer as _nd
from gramps.gen.relationship import get_relationship_calculator

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


class DNAMatches(Gramplet):
    """
    DNA Matches Gramplet class.
    """
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)

        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def db_changed(self):
        """
        Update DNA matches when People, Family, Note or Source changes are made.
        """
        self.connect(self.dbstate.db, 'person-add', self.update)
        self.connect(self.dbstate.db, 'person-delete', self.update)
        self.connect(self.dbstate.db, 'person-update', self.update)
        self.connect(self.dbstate.db, 'family-update', self.update)
        self.connect(self.dbstate.db, 'family-add', self.update)
        self.connect(self.dbstate.db, 'family-delete', self.update)
        self.connect(self.dbstate.db, 'note-add', self.update)
        self.connect(self.dbstate.db, 'note-delete', self.update)
        self.connect(self.dbstate.db, 'note-update', self.update)
        self.connect(self.dbstate.db, 'source-update', self.update)
        self.connect(self.dbstate.db, 'source-add', self.update)
        self.connect(self.dbstate.db, 'source-delete', self.update)
        self.connect_signal('Person',self.update)


    def build_gui(self):
        """
        Build the GUI interface.
        """
        tip1 = _('Double-click on a row to navigate to the matched person.\n')
        tip2 = _('Right click to edit selected association.')
        tooltip = tip1 + tip2
        self.set_tooltip(tooltip)

        top = Gtk.TreeView()
        titles = [('', NOSORT, 50),
                  (_('Person'), 1, 200),
                  (_('Relationship'), 2, 250),
                  ('', NOSORT, 50),
                  (_('Shared DNA'), 3, 125),
                  (_('Shared segments'), 5, 150, 4),
                  ('', NOSORT, 50),
                  (_('Largest segment'), 6, 150),
                  (_('Source(s)'), 8, 200)]

        self.model = ListModel(top,
                               titles,
                               event_func=self.go_to_person,
                               right_click=self.edit_association)
        return top

    def main(self):
        """
        Gets all DNA matches for current person and displays them.
        """
        active_handle = self.get_active('Person')
        model = self.model
        model.clear()

        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)
            for assoc in active.get_person_ref_list():
                if assoc.get_relation() == 'DNA':
                    # Get Notes attached to Association
                    for handle in assoc.get_note_list():
                        note = self.dbstate.db.get_note_from_handle(handle)
                        self.__get_match_info(active, assoc, note, False)
                    # Get Notes attached to Citation which is attached to the Association
                    for citation_handle in assoc.get_citation_list():
                        citation = self.dbstate.db.get_citation_from_handle(citation_handle)
                        for handle in citation.get_note_list():
                            note = self.dbstate.db.get_note_from_handle(handle)
                            self.__get_match_info(active, assoc, note, True)

        # Sort by shared DNA initially
        model.model.set_sort_column_id(self.model.cids[4], 1)
        model.sort()

    def __get_match_info(self, active, assoc, note, is_citation_note):
        """
        Get and display all relevant DNA match information.
        """
        # DNA
        segments = 0
        total_cms = 0
        largest_cms = 0

        lines = note.get().split('\n')
        for line in lines:
            segments, total_cms, largest_cms = self.__process_line(line,
                                                                   segments,
                                                                   total_cms,
                                                                   largest_cms)
        if segments == 0 or total_cms == 0 or largest_cms == 0:
            return

        # Relationship
        relationship = _('unknown')
        associate = self.dbstate.db.get_person_from_handle(assoc.ref)
        rel_strings = get_relationship_calculator(glocale).get_all_relationships(self.dbstate.db,
                                                                                 active,
                                                                                 associate)[0]
        if len(rel_strings) > 0 :
            relationship = rel_strings[0]

        # Rounding floats
        total_cms_rounded = round(total_cms, 1)
        largest_cms_rounded = round (largest_cms, 1)

        # Adding a row of DNA match data
        self.model.add((assoc.ref,
                       _nd.display_name(associate.get_primary_name()),
                       relationship,
                       self.__sort_number_columns(total_cms_rounded),
                       str(total_cms_rounded) + " " + _('cM'),
                       segments,
                       self.__sort_number_columns(largest_cms_rounded),
                       str(largest_cms_rounded) + " " + _('cM'),
                       self.__get_sources(assoc, note.get_handle(), is_citation_note)))

    def __process_line(self, line, segments, total_cms, largest_cms):
        """
        Process a line in a DNA association note.
        """
        fail = (segments, total_cms, largest_cms)
        if re.search('\t',line) is not None:
            line2 = re.sub(',','',line)
            line = re.sub('\t',',',line2)

        field = line.split(',')
        if len(field) >= 4:
            try:
                cms = float(field[3].strip())
            except ValueError:
                return fail
            segments += 1
            total_cms += cms
            if cms > largest_cms:
                largest_cms = cms
        elif len(field) == 3:
            try:
                total_cms = float(field[0].strip())
                segments = int(field[1].strip())
                largest_cms = float(field[2].strip())
            except ValueError:
                return fail
        else:
            return fail

        return (segments, total_cms, largest_cms)

    def __get_sources(self, assoc, note, is_citation_note):
        """
        Get sources for the association.
        """
        db = self.dbstate.db
        found_note = False
        sources = _('Not specified')
        for citation_handle in assoc.get_citation_list():
            citation = db.get_citation_from_handle(citation_handle)
            if is_citation_note and not found_note:
                for note_handle in citation.get_note_list():
                    if note_handle == note:
                        found_note = True
                        break
                    found_note = False
            if (is_citation_note and found_note) or not is_citation_note:
                source = db.get_source_from_handle(citation.get_reference_handle())
                if sources == _('Not specified'):
                    sources = ""
                    sources += source.get_title()
                else:
                    sources += ", " + source.get_title()
            found_note = False
        return sources

    def __sort_number_columns(self, number):
        """
        Hacky way to sort the number columns.
        """
        return str(Date(int(number)).get_sort_value())

    def go_to_person(self, treeview):
        """
        Make the DNA match the active person.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            self.set_active('Person', handle)

    def edit_association(self, treeview, _event):
        """
        Edit the association.
        """
        model, iter_ = treeview.get_selection().get_selected()
        if iter_:
            handle = model.get_value(iter_, 0)
            active_handle = self.get_active('Person')
            if active_handle:
                active = self.dbstate.db.get_person_from_handle(active_handle)
                for assoc in active.get_person_ref_list():
                    if assoc.ref == handle:
                        try:
                            EditPersonRef(self.dbstate, self.uistate, [], assoc, None)
                        except WindowActiveError:
                            pass
