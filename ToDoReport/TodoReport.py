#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2008 Brian G. Matherly
# Copyright (C) 2009      Gary Burton
# Copyright (C) 2010      Jakim Friant
# Copyright (C) 2020      Jan Sparreboom
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

# $Id$

"""Reports/Text Reports/Todo Report"""

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.plug import docgen
import gramps.gen.datehandler
from gramps.gen.filters import GenericFilterFactory
from gramps.gen.filters import rules
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.report import Report
from gramps.gen.errors import ReportError
import gramps.gen.plug.report.utils as ReportUtils
from gramps.gen.plug.menu import EnumeratedListOption, BooleanOption
from gramps.gen.lib.eventtype import EventType
from gramps.gen.utils.file import media_path_full
from gramps.gen.db import dbconst

import os.path

from functools import total_ordering

#------------------------------------------------------------------------
# Internationalisation
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

_REF_HANDLE_POS = 0
_NOTE_HANDLE_POS = 1

_PLACEHOLDER = "_" * 12

#------------------------------------------------------------------------
#
# TodoReport
#
#------------------------------------------------------------------------
class TodoReport(Report):
    """Produce a report listing all notes with a given marker.

    Based on the Marker report, but starting with the notes flagged with a
    particular marker (chosen at run-time).  The records that the note
    references are included in the report so you do not have to duplicate
    that information in the note.

    """

    def __init__(self, database, options, user):
        """
        Create the Report object that produces the report.

        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gramps.gen.user.User() instance

        """
        Report.__init__(self, database, options, user)
        menu = options.menu
        self.tag = menu.get_option_by_name('tag').get_value()
        if not self.tag:
            raise ReportError(_('ToDo Report'),
                _('You must first create a tag before running this report.'))
        self.can_group = menu.get_option_by_name('can_group').get_value()

    def write_report(self):
        """
        Generate the report document
        """
        self.doc.start_paragraph(_("TR-Title"))
        title = _("Report on Notes Tagged '%s'") % self.tag
        mark = docgen.IndexMark(title, docgen.INDEX_TYPE_TOC, 1)
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()

        # get all the notes in the database tagged Todo
        nlist = self.database.get_note_handles()
        FilterClass = GenericFilterFactory('Note')
        my_filter = FilterClass()
        my_filter.add_rule(rules.note.HasTag([self.tag]))
        note_list = my_filter.apply(self.database, nlist)

        if self.can_group:
            self._write_grouped_notes(note_list)
        else:
            self._write_sorted_notes(note_list)

    def _write_grouped_notes(self, note_list):
        """
        Return a dictionary of notes keyed by the referenced object's class name
        """
        # now group the notes by type
        note_groups = dict()
        for note_handle in note_list:
            refs = self.database.find_backlink_handles(note_handle)
            try:
                # grouping by the first reference
                (class_name, r_handle) = list(refs)[0]
                if class_name in note_groups:
                    note_groups[class_name].append((r_handle, note_handle))
                else:
                    note_groups[class_name] = [(r_handle, note_handle)]
            except IndexError:
                # no back-links were found
                pass
        for k in sorted(note_groups.keys(), reverse=True):
            # now sort the handles based on the class name, if we don't find
            # a match, the data will not be sorted.
            if k == dbconst.KEY_TO_CLASS_MAP[dbconst.FAMILY_KEY]:
                note_list = sorted(note_groups[k], key=self.getFamilyKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.PERSON_KEY]:
                note_list = sorted(note_groups[k], key=self.getPersonKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.EVENT_KEY]:
                note_list = sorted(note_groups[k], key=self.getEventKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.PLACE_KEY]:
                note_list = sorted(note_groups[k], key=self.getPlaceKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.REPOSITORY_KEY]:
                note_list = sorted(note_groups[k], key=self.getRepositoryKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.SOURCE_KEY]:
                note_list = sorted(note_groups[k], key=self.getSourceKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.CITATION_KEY]:
                note_list = sorted(note_groups[k], key=self.getCitationKey)
            elif k == dbconst.KEY_TO_CLASS_MAP[dbconst.MEDIA_KEY]:
                note_list = sorted(note_groups[k], key=self.getMediaKey)
            else:
                note_list = note_groups[k]
            self._write_notes(note_list, k)

    def _write_sorted_notes(self, note_list):
        all_notes = []
        for note_handle in note_list:
            refs = self.database.find_backlink_handles(note_handle)
            # grouping by the first reference
            try:
                (class_name, r_handle) = list(refs)[0]
                if class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.FAMILY_KEY]:
                    key = self.getFamilyKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.PERSON_KEY]:
                    key = self.getPersonKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.EVENT_KEY]:
                    key = self.getEventKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.PLACE_KEY]:
                    key = self.getPlaceKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.REPOSITORY_KEY]:
                     key = self.getRepositoryKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.SOURCE_KEY]:
                    key = self.getSourceKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.CITATION_KEY]:
                    key = self.getCitationKey((r_handle,))
                elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.MEDIA_KEY]:
                    key = self.getMediaKey((r_handle,))
                else:
                    note = self.database.get_note_from_handle(note_handle)
                    key = note.get_gramps_id()
                all_notes.append((key, note_handle))
            except IndexError:
                # no back-link references were found, so we'll use the note ID
                # as the key
                note = self.database.get_note_from_handle(note_handle)
                key = note.get_gramps_id()
        self._write_notes(sorted(all_notes))

    def _write_references(self, note_handle):
        """
        Find the primary references attached the note and add them to the report
        """
        refs = self.database.find_backlink_handles(note_handle)
        for (class_name, r_handle) in refs:
            if class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.FAMILY_KEY]:
                self._write_family(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.PERSON_KEY]:
                self._write_person(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.EVENT_KEY]:
                self._write_event(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.PLACE_KEY]:
                self._write_place(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.REPOSITORY_KEY]:
                self._write_repository(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.SOURCE_KEY]:
                self._write_source(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.CITATION_KEY]:
                self._write_citation(r_handle)
            elif class_name == dbconst.KEY_TO_CLASS_MAP[dbconst.MEDIA_KEY]:
                self._write_media(r_handle)

    def _write_notes(self, note_list, title=None):
        """
        Generate a table for the list of notes
        """
        if not note_list:
            return

        if title is not None:
            self.doc.start_paragraph(_("TR-Heading"))
            header = _(title)
            mark = docgen.IndexMark(header, docgen.INDEX_TYPE_TOC, 2)
            self.doc.write_text(header, mark)
            self.doc.end_paragraph()

        self.doc.start_table(_('NoteTable'),_('TR-Table'))

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal-Bold'))
        self.doc.write_text(_("Id"))
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'), 3)
        self.doc.start_paragraph(_('TR-Normal-Bold'))
        self.doc.write_text(_("Text"))
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()

        for handles in note_list:
            note_handle = handles[_NOTE_HANDLE_POS]
            note = self.database.get_note_from_handle(note_handle)

            self.doc.start_row()

            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.write_text(note.get_gramps_id())
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell(_('TR-TableCell'), 3)
            self.doc.write_styled_note(note.get_styledtext(),
                                       note.get_format(), _('TR-Note'))
            self.doc.end_cell()

            self.doc.end_row()

            self._write_references(note_handle)

            self.doc.start_row()

            self.doc.start_cell(_('TR-BorderCell'), 4)
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.write_text('')
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.end_row()

        self.doc.end_table()

    def _write_person(self, person_handle):
        """
        Generate a table row for a person record
        """
        person = self.database.get_person_from_handle(person_handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(person.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        name = name_displayer.display(person)
        mark = ReportUtils.get_person_mark(self.database, person)
        self.doc.start_cell(_('TR-TableCell'), 3)
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(name, mark)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()

        alternate_names = person.get_alternate_names()
        if len(alternate_names) > 0:
            for alt_name in alternate_names:
                # blank first column
                self.doc.start_row()
                self.doc.start_cell(_('TR-TableCell'))
                self.doc.start_paragraph(_('TR-Normal'))
                self.doc.end_paragraph()
                self.doc.end_cell()

                alt_name_display = name_displayer.display_name(alt_name)
                self.doc.start_cell(_('TR-TableCell'), 3)
                self.doc.start_paragraph(_('TR-Normal'))
                self.doc.write_text(alt_name_display)
                self.doc.end_paragraph()
                self.doc.end_cell()
                self.doc.end_row()

        self._output_events(person)


    def _write_family(self, family_handle):
        """
        Generate a table row for this family record
        """
        family = self.database.get_family_from_handle(family_handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(family.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        father_handle = family.get_father_handle()
        if father_handle:
            father = self.database.get_person_from_handle(father_handle)
            mark = ReportUtils.get_person_mark(self.database, father)
            self.doc.write_text(name_displayer.display(father), mark)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        mother_handle = family.get_mother_handle()
        if mother_handle:
            mother = self.database.get_person_from_handle(mother_handle)
            mark = ReportUtils.get_person_mark(self.database, mother)
            self.doc.write_text(name_displayer.display(mother), mark)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(family.get_relationship().string)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()

        self._output_events(family)


    def _write_event(self, event_handle):
        """
        Generate a table row for this event record
        """
        event = self.database.get_event_from_handle(event_handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(event.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        type_date = event.get_type().string
        date = gramps.gen.datehandler.get_date(event)
        if date:
            type_date = type_date + " " + date
        else:
            type_date = type_date + " " + (_("date: ") + _PLACEHOLDER)
        self.doc.write_text(type_date)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        place_handle = event.get_place_handle()
        place = ReportUtils.place_name(self.database, place_handle)
        if place:
            self.doc.write_text(place)
        else:
            self.doc.write_text(_("place: ") + _PLACEHOLDER)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        descr = event.get_description()
        if descr:
            self.doc.write_text( descr )
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()

        # make smart use of space and put as many names in a row as possible
        # always skip the first column to show that this is part of the same object
        next_cell_index = 0
        for (class_name, r_handle) in self.database.find_backlink_handles(event_handle, include_classes=['Person']):
            if next_cell_index == 0:
                self.doc.start_row()
                self.doc.start_cell(_('TR-TableCell'))
                self.doc.start_paragraph(_('TR-Normal'))
                self.doc.end_paragraph()
                self.doc.end_cell()
                next_cell_index = next_cell_index + 1

            person = self.database.get_person_from_handle(r_handle)
            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.write_text(name_displayer.display(person))
            self.doc.end_paragraph()
            self.doc.end_cell()
            next_cell_index = next_cell_index + 1

            if next_cell_index > 3:
                # end of row
                self.doc.end_row()
                next_cell_index = 0

        # finish up empty cells
        if next_cell_index > 0:
            self.doc.start_cell(_('TR-TableCell'), (4 - next_cell_index))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.end_row()
            

        for (class_name, r_handle) in self.database.find_backlink_handles(event_handle, include_classes=['Family']):
            family = self.database.get_family_from_handle(r_handle)
            self.doc.start_row()

            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.write_text('Family')
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            father_handle = family.get_father_handle()
            if father_handle:
                father = self.database.get_person_from_handle(father_handle)
                mark = ReportUtils.get_person_mark(self.database, father)
                self.doc.write_text(name_displayer.display(father), mark)
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            mother_handle = family.get_mother_handle()
            if mother_handle:
                mother = self.database.get_person_from_handle(mother_handle)
                mark = ReportUtils.get_person_mark(self.database, mother)
                self.doc.write_text(name_displayer.display(mother), mark)
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.end_row()



    def _write_place(self, place_handle):
        """
        Generate a table row with the place record information.
        """
        place = self.database.get_place_from_handle(place_handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(place.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'), 3)
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(place_displayer.display(self.database, place))
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()


    def _write_repository(self, handle):
        """
        Generate a table row with the repository information.
        """
        repository = self.database.get_repository_from_handle(handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(repository.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'), 2)
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(repository.get_name())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(repository.get_type().string)
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()


    def _write_source(self, handle):
        """
        Generate a table row with the source information.
        """
        source = self.database.get_source_from_handle(handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(source.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(source.get_title())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(source.get_author())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(source.get_publication_info())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.end_row()


    def _write_citation(self, handle):
        """
        Generate a table row with the citation information.
        """
        citation = self.database.get_citation_from_handle(handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(citation.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        source_handle = citation.get_reference_handle()
        source = self.database.get_source_from_handle(source_handle)
        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(source.get_title())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(gramps.gen.datehandler.get_date(citation))
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(citation.get_page())
        self.doc.end_paragraph()
        self.doc.end_cell()
        
        self.doc.end_row()


    def _write_media(self, handle):
        """
        Generate a table row with the media information.
        """
        media = self.database.get_media_from_handle(handle)

        self.doc.start_row()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(media.get_gramps_id())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(media.get_description())
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        self.doc.start_paragraph(_('TR-Normal'))
        self.doc.write_text(gramps.gen.datehandler.get_date(media))
        self.doc.end_paragraph()
        self.doc.end_cell()

        self.doc.start_cell(_('TR-TableCell'))
        mime_type = media.get_mime_type()
        if mime_type and mime_type.startswith("image"):
            filename = media_path_full(self.database, media.get_path())
            if os.path.exists(filename):
                self.doc.add_media(filename, 'center', 5.0, 5.0)
        self.doc.end_cell()

        self.doc.end_row()
        

    def _output_events(self, event_base):
        """Write out all events for an object that subclasses EventBase"""
        event_keys = list()
        for event_ref in event_base.get_event_ref_list():
            event = self.database.get_event_from_handle(event_ref.ref)
            key = EventSortKey(event)
            event_keys.append(key)

        for event_key in sorted(event_keys):
            event = event_key.event
            self.doc.start_row()

            # blank the first column to do an indent
            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell(_('TR-TableCell'))
            self.doc.start_paragraph(_('TR-Normal'))
            self.doc.write_text(event.get_type().string)
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell(_('TR-TableCell'), 2)
            self.doc.start_paragraph(_('TR-Normal'))

            event_place_handle = event.get_place_handle()
            event_place_string = ''
            if event_place_handle:
                place = self.database.get_place_from_handle(event_place_handle)
                event_place_string = ' @ ' + place_displayer.display(self.database, place)
            self.doc.write_text(gramps.gen.datehandler.get_date(event) + event_place_string)

            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.end_row()


    #
    # Sort Functions
    #
    def getPersonKey(self, group_entry):
        """
        Return a string of the persons name (last, first) as the key
        """
        per_handle = group_entry[_REF_HANDLE_POS]
        person = self.database.get_person_from_handle(per_handle)
        sort_key = person.get_primary_name().get_name()
        return sort_key.upper()

    def getFamilyKey(self, group_entry):
        """
        Return a string with the father's or mother's name (in that order) as the key
        """
        sort_key = ""
        person = None
        family_handle = group_entry[_REF_HANDLE_POS]
        family = self.database.get_family_from_handle(family_handle)
        if family:
            father_handle = family.get_father_handle()
            if father_handle:
                person = self.database.get_person_from_handle(father_handle)
            else:
                mother_handle = family.get_mother_handle()
                if mother_handle:
                    person = self.database.get_person_from_handle(mother_handle)
        if person is not None:
            sort_key = person.get_primary_name().get_name()
        return sort_key.upper()

    def getEventKey(self, group_entry):
        """Return the event date as a string to use for sorting the events.

        I'm returning the date with 'zz' prefixed so it will sort at the bottom
        when not using grouping.

        """
        evt_handle = group_entry[_REF_HANDLE_POS]
        event = self.database.get_event_from_handle(evt_handle)
        date = event.get_date_object()
        return "zz" + str(date)

    def getPlaceKey(self, group_entry):
        """
        Return the place description to use when sorting the place records.
        """
        p_handle = group_entry[_REF_HANDLE_POS]
        place = self.database.get_place_from_handle(p_handle)
        title = place_displayer.display(self.database, place)
        return title.upper()


    def getRepositoryKey(self, group_entry):
        """
        Return the repository name to use when sorting the repository records.
        """
        p_handle = group_entry[_REF_HANDLE_POS]
        repo = self.database.get_repository_from_handle(p_handle)
        return (repo.get_name() or '').upper()


    def getSourceKey(self, group_entry):
        """
        Return the source abbreviation or title to use when sorting the source records.
        """
        p_handle = group_entry[_REF_HANDLE_POS]
        source = self.database.get_source_from_handle(p_handle)
        abbrev = source.get_abbreviation()
        if abbrev:
            return abbrev.upper()
        return (source.get_title() or '').upper()


    def getCitationKey(self, group_entry):
        """
        Return the citation page to use when sorting the citation records.
        """
        p_handle = group_entry[_REF_HANDLE_POS]
        citation = self.database.get_citation_from_handle(p_handle)
        return (citation.get_page() or '').upper()


    def getMediaKey(self, group_entry):
        """
        Return the media description to use when sorting the media records.
        """
        p_handle = group_entry[_REF_HANDLE_POS]
        media = self.database.get_media_from_handle(p_handle)
        return (media.get_description() or '').upper()


@total_ordering
class EventSortKey(object):
    """Class for sorting events by type and then date.
    1. Birth
    2. Other event types
    3. Death
    4. Burial
    """


    def __init__(self, event):
        self.event = event

    def __eq__(self, other):
        return self.event.are_equal(other.event)

    def __ne__(self, other):
        return not (self == other)

    def __lt__(self, other):
        self_type = self.event.get_type()
        other_type = other.event.get_type()

        if self_type.value == EventType.BIRTH and other_type.value != EventType.BIRTH:
            return True
        if self_type.value != EventType.BIRTH and other_type.value == EventType.BIRTH:
            return False

        if self_type.value == EventType.BURIAL and other_type.value != EventType.BURIAL:
            return False
        if self_type.value != EventType.BURIAL and other_type.value == EventType.BURIAL:
            return True

        if self_type.value == EventType.DEATH and other_type.value not in [EventType.DEATH, EventType.BURIAL]:
            return False
        if self_type.value not in [EventType.DEATH, EventType.BURIAL] and other_type.value == EventType.DEATH:
            return True

        # compare dates
        return self.event.get_date_object() < other.event.get_date_object()


#------------------------------------------------------------------------
# MarkerOptions
#------------------------------------------------------------------------
class TodoOptions(MenuReportOptions):
    """Set up the options dialog for this report"""

    def __init__(self, name, dbase):
        """Create the object and initialize the parent class"""
        self.__db = dbase
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the marker report.
        """
        category_name = _("Report Options")

        all_tags = []
        for handle in self.__db.get_tag_handles():
            tag = self.__db.get_tag_from_handle(handle)
            all_tags.append(tag.get_name())

        if len(all_tags) > 0:
            tag_option = EnumeratedListOption(_('Tag'), all_tags[0])
            for tag_name in all_tags:
                tag_option.add_item(tag_name, tag_name)
        else:
            tag_option = EnumeratedListOption(_('Tag'), '')
            tag_option.add_item('', '')

        tag_option.set_help( _("The tag to use for the report"))
        menu.add_option(category_name, "tag", tag_option)

        can_group = BooleanOption(_("Group by reference type"), False)
        can_group.set_help( _("Group notes by Family, Person, Place, etc."))
        menu.add_option(category_name, "can_group", can_group)

    def make_default_style(self, default_style):
        """Make the default output style for the Todo Report."""
        # Paragraph Styles
        font = docgen.FontStyle()
        font.set_size(16)
        font.set_type_face(docgen.FONT_SANS_SERIF)
        font.set_bold(1)
        para = docgen.ParagraphStyle()
        para.set_header_level(1)
        para.set_bottom_border(1)
        para.set_top_margin(ReportUtils.pt2cm(3))
        para.set_bottom_margin(ReportUtils.pt2cm(3))
        para.set_font(font)
        para.set_alignment(docgen.PARA_ALIGN_CENTER)
        para.set_description(_("The style used for the title of the page."))
        default_style.add_paragraph_style(_("TR-Title"), para)

        font = docgen.FontStyle()
        font.set(face=docgen.FONT_SANS_SERIF, size=14, italic=1)
        para = docgen.ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the section headers.'))
        default_style.add_paragraph_style(_("TR-Heading"), para)

        font = docgen.FontStyle()
        font.set_size(12)
        para = docgen.ParagraphStyle()
        para.set(first_indent=-0.75, lmargin=.75)
        para.set_font(font)
        para.set_top_margin(ReportUtils.pt2cm(3))
        para.set_bottom_margin(ReportUtils.pt2cm(3))
        para.set_description(_('The basic style used for the text display.'))
        default_style.add_paragraph_style(_("TR-Normal"), para)

        font = docgen.FontStyle()
        font.set_size(12)
        font.set_bold(True)
        para = docgen.ParagraphStyle()
        para.set(first_indent=-0.75, lmargin=.75)
        para.set_font(font)
        para.set_top_margin(ReportUtils.pt2cm(3))
        para.set_bottom_margin(ReportUtils.pt2cm(3))
        para.set_description(_('The basic style used for table headings.'))
        default_style.add_paragraph_style(_("TR-Normal-Bold"), para)

        para = docgen.ParagraphStyle()
        para.set(first_indent=-0.75, lmargin=.75)
        para.set_top_margin(ReportUtils.pt2cm(3))
        para.set_bottom_margin(ReportUtils.pt2cm(3))
        para.set_description(_('The basic style used for the note display.'))
        default_style.add_paragraph_style(_("TR-Note"), para)

        #Table Styles
        cell = docgen.TableCellStyle()
        cell.set_description(_('The basic style used for the table cell display.'))
        default_style.add_cell_style(_('TR-TableCell'), cell)

        cell = docgen.TableCellStyle()
        cell.set_bottom_border(1)
        cell.set_description(_('The basic style used for the table border cell display.'))
        default_style.add_cell_style(_('TR-BorderCell'), cell)

        table = docgen.TableStyle()
        table.set_width(100)
        table.set_columns(4)
        table.set_column_width(0, 10)
        table.set_column_width(1, 30)
        table.set_column_width(2, 30)
        table.set_column_width(3, 30)
        table.set_description(_('The basic style used for the table display.'))
        default_style.add_table_style(_('TR-Table'), table)
