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
from gramps.gui.editors import EditPerson, EditPersonRef
from gramps.gen.config import config
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

#------------------------------------------------------------------------
#
# Configuration file
#
#------------------------------------------------------------------------
CONFIG = config.register_manager('DNAMatches')
CONFIG.register('hide-columns.id', False)
CONFIG.register('hide-columns.person', False)
CONFIG.register('hide-columns.relationship', False)
CONFIG.register('hide-columns.shared-dna', False)
CONFIG.register('hide-columns.shared-segments', False)
CONFIG.register('hide-columns.largest-segment', False)
CONFIG.register('hide-columns.sources', False)
CONFIG.register('short-names.person', False)
CONFIG.register('short-names.relationship', False)
CONFIG.register('short-names.shared-dna', False)
CONFIG.register('short-names.shared-segments', False)
CONFIG.register('short-names.largest-segment', False)
CONFIG.register('short-names.sources', False)
CONFIG.register('widths.id', 50)
CONFIG.register('widths.person', 150)
CONFIG.register('widths.relationship', 125)
CONFIG.register('widths.shared-dna', 125)
CONFIG.register('widths.shared-segments', 155)
CONFIG.register('widths.largest-segment', 150)
CONFIG.register('widths.sources', 200)

CONFIG.init()

class DNAMatches(Gramplet):
    """
    DNA Matches Gramplet class.
    """
    def __init__(self, gui, nav_group=0):
        Gramplet.__init__(self, gui, nav_group)

        self._config = config.get_manager('DNAMatches')

        self._hidden_columns = []
        self._hidden_columns.append(self._config.get('hide-columns.id'))
        self._hidden_columns.append(self._config.get('hide-columns.person'))
        self._hidden_columns.append(self._config.get('hide-columns.relationship'))
        self._hidden_columns.append(self._config.get('hide-columns.shared-dna'))
        self._hidden_columns.append(self._config.get('hide-columns.shared-segments'))
        self._hidden_columns.append(self._config.get('hide-columns.largest-segment'))
        self._hidden_columns.append(self._config.get('hide-columns.sources'))

        self._short_names = []
        self._short_names.append(self._config.get('short-names.person'))
        self._short_names.append(self._config.get('short-names.relationship'))
        self._short_names.append(self._config.get('short-names.shared-dna'))
        self._short_names.append(self._config.get('short-names.shared-segments'))
        self._short_names.append(self._config.get('short-names.largest-segment'))
        self._short_names.append(self._config.get('short-names.sources'))

        self._widths = []
        self._widths.append(self._config.get('widths.id'))
        self._widths.append(self._config.get('widths.person'))
        self._widths.append(self._config.get('widths.relationship'))
        self._widths.append(self._config.get('widths.shared-dna'))
        self._widths.append(self._config.get('widths.shared-segments'))
        self._widths.append(self._config.get('widths.largest-segment'))
        self._widths.append(self._config.get('widths.sources'))
        self._config.save()

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
        self.connect_signal('Person', self.update)

    def build_gui(self):
        """
        Build the GUI interface.
        """
        short_names = [_('Pers.'), _('Rel.'), _('S. DNA'), _('S. Leg.'), _('L. Seg'), _('Src(s)')]
        full_names = [_('Person'),
                      _('Relationship'),
                      _('Shared DNA'),
                      _('Shared Segments'),
                      _('Largest Segment'),
                      _('Source(s)')]

        self.set_tooltip(self.__create_tooltip(short_names, full_names))

        top = Gtk.TreeView()

        names = [_('ID'),
                 full_names[0] if not self._short_names[0] else short_names[0],
                 full_names[1] if not self._short_names[1] else short_names[1],
                 full_names[2] if not self._short_names[2] else short_names[2],
                 full_names[3] if not self._short_names[3] else short_names[3],
                 full_names[4] if not self._short_names[4] else short_names[4],
                 full_names[5] if not self._short_names[5] else short_names[5]]

        titles = [('', NOSORT, 50),
                  (names[0] if not self._hidden_columns[0] else '', 1, self._widths[0]),
                  (names[1] if not self._hidden_columns[1] else '', 2, self._widths[1]),
                  (names[2] if not self._hidden_columns[2] else '', 3, self._widths[2]),
                  ('', NOSORT, 50),
                  (names[3] if not self._hidden_columns[3] else '', 4, self._widths[3]),
                  (names[4] if not self._hidden_columns[4] else '', 6, self._widths[4], 4),
                  ('', NOSORT, 50),
                  (names[5] if not self._hidden_columns[5] else '', 7, self._widths[5]),
                  (names[6] if not self._hidden_columns[6] else '', 9, self._widths[6])]

        self.model = ListModel(top,
                               titles,
                               event_func=self.go_to_person,
                               right_click=self.edit_association)
        return top

    def __create_tooltip(self, short_names, full_names):
        """
        Create the tooltip based on the config.
        """
        tip1 = _('Double-click on a row to navigate to the matched person.') + '\n'
        tip2 = _('Right click to edit selected association.')

        name_tips = ['', '', '', '', '', '']
        processed_num = 0
        short_names_num = self.__get_short_names_num()

        for count, _name in enumerate(name_tips):
            if self._short_names[count] and not self._hidden_columns[count + 1]:
                processed_num += 1
                name_tips[count] = self.__explain_short_name(short_names[count],
                                                             full_names[count],
                                                             processed_num is short_names_num)

        tip3 = ""
        if True in self._short_names:
            tip3 = '\n\n' + _('LEGEND') + '\n'

        return tip1 + tip2 + tip3 + ''.join(name_tips)

    def __get_short_names_num(self):
        """
        Get the total number of short names (leaving out hidden columns).
        """
        number = 0
        for count, _name in enumerate(self._short_names):
            if self._short_names[count] and not self._hidden_columns[count + 1]:
                number += 1
        return number

    def __explain_short_name(self, short_name, full_name, is_last):
        """
        Creates an explanation of a short name for use in the tooltip.
        """
        return short_name + ' ' + _('=') + ' ' + full_name + ('\n' if not is_last else '')

    def main(self):
        """
        Gets all DNA matches for current person and displays them.
        """
        active_handle = self.get_active('Person')
        model = self.model
        model.clear()

        matches = []

        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)
            for assoc in active.get_person_ref_list():
                if assoc.get_relation() == 'DNA':
                    # Get Notes attached to Association
                    for handle in assoc.get_note_list():
                        note = self.dbstate.db.get_note_from_handle(handle)
                        match = self.__get_match_info(active, assoc, note, False)
                        self.__should_append(match, matches)
                    # Get Notes attached to Citation which is attached to the Association
                    for citation_handle in assoc.get_citation_list():
                        citation = self.dbstate.db.get_citation_from_handle(citation_handle)
                        for handle in citation.get_note_list():
                            note = self.dbstate.db.get_note_from_handle(handle)
                            match = self.__get_match_info(active, assoc, note, True)
                            self.__should_append(match, matches)

        # Merge duplicate match entries
        self.__resolve_duplicates(matches)

        # Add all matches to the model
        for match in matches:
            model.add(match)

        # Sort by shared DNA initially
        model.model.set_sort_column_id(self.model.cids[5], 1)
        model.sort()

    def __resolve_duplicates(self, matches):
        """
        Merge duplicate entries.
        """
        marked_for_deletion = []
        for i, match in  enumerate(matches):
            for j, match2 in enumerate(matches):
                not_marked = i not in marked_for_deletion
                if i != j and not_marked and self.__check_is_duplicate(match, match2):
                    resolved_sources = self.__resolve_sources(match[9], match2[9])
                    matches[i] = (match[0],
                                  match[1],
                                  match[2],
                                  match[3],
                                  match[4],
                                  match[5],
                                  match[6],
                                  match[7],
                                  match[8],
                                  resolved_sources)
                    marked_for_deletion.append(j)
        # Delete merged entries (from back to front)
        marked_for_deletion.sort(reverse=True)
        for marked in marked_for_deletion:
            matches.pop(marked)

    def __check_is_duplicate(self, match, match2):
        """
        Check if two matches are duplicates of each other (except for their source)
        """
        # Check Gramps IDs
        if match[1] != match2[1]:
            return False
        # Check DNA data
        if match[5] == match2[5] and match[6] == match2[6] and match[8] == match2[8]:
            return True
        return False

    def __resolve_sources(self, source, source2):
        """
        Merge sources for duplicate entries (if possible).
        """
        unspecified = _('Not specified')
        if source is source2:
            return source
        main_source = source if source != unspecified else source2
        other_source = source2 if main_source == source else source

        sources = other_source.split(', ')
        for split_source in sources:
            if split_source not in main_source and split_source != unspecified:
                main_source = ', '.join([main_source, split_source])
        return main_source

    def __should_append(self, match, matches):
        """
        Append the match only if it is populated.
        """
        if len(match) > 0:
            matches.append(match)

    def __get_match_info(self, active, assoc, note, is_citation_note):
        """
        Get and store all relevant DNA match information.
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
            return ()

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

        # Return DNA match data
        return (assoc.ref,
                associate.get_gramps_id(),
                _nd.display_name(associate.get_primary_name()),
                relationship,
                self.__sort_number_columns(total_cms_rounded),
                str(total_cms_rounded) + " " + _('cM'),
                segments,
                self.__sort_number_columns(largest_cms_rounded),
                str(largest_cms_rounded) + " " + _('cM'),
                self.__get_sources(assoc, note.get_handle(), is_citation_note))

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
                            EditPerson(self.dbstate, self.uistate, [], active)
                            EditPersonRef(self.dbstate, self.uistate, [0], assoc, None)
                        except WindowActiveError:
                            pass
