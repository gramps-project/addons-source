#
# Copyright (C) 2011 Matt Keenan <matt.keenan@gmail.com>
# Copyright (C) 2015, 2019 Giansalvo Gusinu <giansalvo.gusinu@gmail.com>
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
Reports/Books/Detailed Descendant Book
"""

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
import copy
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from functools import partial

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.errors import ReportError
from gramps.gen.lib import FamilyRelType, Person, NoteType
from gramps.gen.plug.menu import (BooleanOption, NumberOption, PersonOption,
                           EnumeratedListOption, FilterOption)
from gramps.gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle,
                             FONT_SANS_SERIF, FONT_SERIF,
                             INDEX_TYPE_TOC, PARA_ALIGN_CENTER)
from gramps.gen.plug.report import stdoptions
from gramps.gen.plug.report import (Report, Bibliography)
from gramps.gen.plug.report import endnotes
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions

import gramps.gen.datehandler
from CollectAscendants import CollectAscendants
from RunReport import RunReport

from gramps.plugins.lib.libnarrate import Narrator

#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------
EMPTY_ENTRY = "_____________"
HENRY = "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

#------------------------------------------------------------------------
#
# DetailedDescendantBook
#
#------------------------------------------------------------------------
class DetailedDescendantBook():
    def __init__(self, dbstate, uistate):
        RunReport(dbstate, uistate, "DetailedDescendantBookReport",
            "detailed_descendant_book", "Detailed Descendant Book",
            "DetailedDescendantBookReport", "DetailedDescendantBookOptions")

class DetailedDescendantBookReport(Report):

    def __init__(self, database, options, user):
        """
        Create the DetailedDescendantBook object that produces the report.

        The arguments are:

        database        - the GRAMPS database instance
        person          - currently selected person
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.

        gen           - Maximum number of generations to include.
        pagebgg       - Whether to include page breaks between generations.
        pageben       - Whether to include page break before End Notes.
        fulldates     - Whether to use full dates instead of just year.
        listc         - Whether to list children.
        incnotes      - Whether to include notes.
        usecall       - Whether to use the call name as the first name.
        repplace      - Whether to replace missing Places with ___________.
        repdate       - Whether to replace missing Dates with ___________.
        computeage    - Whether to compute age.
        omitda        - Whether to omit duplicate ancestors (e.g. when distant cousins marry).
        verbose       - Whether to use complete sentences.
        numbering     - The descendancy numbering system to be utilized.
        desref        - Whether to add descendant references in child list.
        incphotos     - Whether to include images.
        incnames      - Whether to include other names.
        incevents     - Whether to include events.
        incaddresses  - Whether to include addresses.
        incsrcnotes   - Whether to include source notes in the Endnotes section. Only works if Include sources is selected.
        incmates      - Whether to include information about spouses
        incattrs      - Whether to include attributes
        incpaths      - Whether to include the path of descendancy from the start-person to each descendant.
        incindexnames - Whether to include the index of names at the end of the report.
        incindexplaces- Whether to include the index of places at the end of the report.
        incindexdates - Whether to include the index of dates at the end of the report.
        incappearances- Whether to include Include the 'Report appearances' section with each person.
        incssign      - Whether to include a sign ('+') before the descendant number in the child-list to indicate a child has succession.
        pid           - The Gramps ID of the center person for the report.
        name_format   - Preferred format to display names
        incmateref    - Whether to print mate information or reference
        filter_option - Specific report filter to use.
        """
        Report.__init__(self, database, options, user)

        menu = options.menu
        self.user = user
        self.title = _('Detailed Descendants Report')
        get_option_by_name = menu.get_option_by_name
        get_value = lambda name: get_option_by_name(name).get_value()
        self.max_generations = get_value('gen')
        self.pgbrk         = get_value('pagebbg')
        self.pgbrkenotes   = get_value('pageben')
        self.fulldate      = get_value('fulldates')
        use_fulldate     = self.fulldate
        self.listchildren  = get_value('listc')
        self.inc_notes     = get_value('incnotes')
        use_call           = get_value('usecall')
        blankplace         = get_value('repplace')
        blankdate          = get_value('repdate')
        self.calcageflag   = get_value('computeage')
        self.dubperson     = get_value('omitda')
        self.verbose       = get_value('verbose')
        self.numbering     = get_value('numbering')
        self.childref      = get_value('desref')
        self.addimages     = get_value('incphotos')
        self.inc_names     = get_value('incnames')
        self.inc_events    = get_value('incevents')
        self.inc_addr      = get_value('incaddresses')
        self.inc_sources   = get_value('incsources')
        self.inc_srcnotes  = get_value('incsrcnotes')
        self.inc_mates     = get_value('incmates')
        self.inc_attrs     = get_value('incattrs')
        self.inc_paths     = get_value('incpaths')
        self.inc_index_names = get_value('incindexnames')
        self.inc_index_of_dates =get_value('incindexdates')
        self.inc_index_of_places =get_value('incindexplaces')
        self.inc_appearances = get_value('incappearances')
        self.inc_ssign     = get_value('incssign')
        self.inc_materef   = get_value('incmateref')
        self.filter_option =  menu.get_option_by_name('filter')
        self.filter = self.filter_option.get_filter()
        pid                = get_value('pid')
        self.center_person = database.get_person_from_gramps_id(pid)
        if (self.center_person == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )

        if blankdate:
            empty_date = EMPTY_ENTRY
        else:
            empty_date = ""

        if blankplace:
            empty_place = EMPTY_ENTRY
        else:
            empty_place = ""

        language = get_value('trans')
        # Set up to use the language from options
        self._locale = self.set_locale(language)
        # Normally this is enough,  at least enough for Narrator, but we have
        # some other local strings to add to the report.
        try:
            add_trans = self._locale.get_addon_translator(__file__)
        except ValueError:
            add_trans = glocale.translation
        self._ = add_trans.sgettext

        # Copy the global NameDisplay so that we don't change application
        # defaults.
        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

        self.__narrator = Narrator(self.database, self.verbose,
                                   use_call, use_fulldate,
                                   empty_date, empty_place,
                                   nlocale=self._locale,
                                   get_endnote_numbers=self.endnotes)

        #self.__get_date = translator.get_date
        #self.__get_type = translator.get_type

        self.bibli = Bibliography(Bibliography.MODE_DATE|Bibliography.MODE_PAGE)

    def __init_variables(self):
        self.map = {}
        self._user = self.user
        self.gen_keys = []
        self.dnumber = {}
        self.dmates = {}
        self.gen_handles = {}
        self.prev_gen_handles = {}

    def apply_henry_filter(self,person_handle, index, pid, cur_gen=1):
        if (not person_handle) or (cur_gen > self.max_generations):
            return
        self.dnumber[person_handle] = pid
        self.map[index] = person_handle

        if len(self.gen_keys) < cur_gen:
            self.gen_keys.append([index])
        else:
            self.gen_keys[cur_gen-1].append(index)

        person = self.database.get_person_from_handle(person_handle)
        index = 0
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                ix = max(self.map)
                self.apply_henry_filter(child_ref.ref, ix+1,
                                  pid+HENRY[index], cur_gen+1)
                index += 1

    # Filter for d'Aboville numbering
    def apply_daboville_filter(self,person_handle, index, pid, cur_gen=1):
        if (not person_handle) or (cur_gen > self.max_generations):
            return
        self.dnumber[person_handle] = pid
        self.map[index] = person_handle

        if len(self.gen_keys) < cur_gen:
            self.gen_keys.append([index])
        else:
            self.gen_keys[cur_gen-1].append(index)

        person = self.database.get_person_from_handle(person_handle)
        index = 1
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                ix = max(self.map)
                self.apply_daboville_filter(child_ref.ref, ix+1,
                                  pid+"."+str(index), cur_gen+1)
                index += 1

    # Filter for Record-style (Modified Register) numbering
    def apply_mod_reg_filter_aux(self, person_handle, index, cur_gen=1):
        if (not person_handle) or (cur_gen > self.max_generations):
            return
        self.map[index] = person_handle

        if len(self.gen_keys) < cur_gen:
            self.gen_keys.append([index])
        else:
            self.gen_keys[cur_gen-1].append(index)

        person = self.database.get_person_from_handle(person_handle)

        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                ix = max(self.map)
                self.apply_mod_reg_filter_aux(child_ref.ref, ix+1, cur_gen+1)

    def apply_mod_reg_filter(self, person_handle):
        self.apply_mod_reg_filter_aux(person_handle, 1, 1)
        mod_reg_number = 1
        for generation in range(len(self.gen_keys)):
            for key in self.gen_keys[generation]:
                person_handle = self.map[key]
                if person_handle not in self.dnumber:
                    self.dnumber[person_handle] = mod_reg_number
                    mod_reg_number += 1

    def __update_index_of_dates(self, date_object, event):
        """
        Update index_of_dates
        """
        if not event:
            return

        year = date_object.get_year()

        if year not in self.index_of_dates:
            self.index_of_dates[year] = {}

        date = "%s" % (date_object) # WARNING : using internal representation of date object, SHOULD USE accessor function
        self.index_of_dates[year][date] = event

    def __update_index_of_places(self, place, date_object, event):
        """
        Update index_of_places
        """
        if not event:
            return

        if place not in self.index_of_places:
            self.index_of_places[place] = {}

        date = "%s" % (date_object) # WARNING : using internal representation of date object, SHOULD USE accessor function
        self.index_of_places[place][date] = event

    def __update_report_app_ref(self, person_handle, main_handle=None):
        """
        Check main report reference index, add this person to the index
        if not already there. Every person printed (and mates if included)
        should appear in this reference at least once.
        """
        person = self.database.get_person_from_handle(person_handle)
        name = person.get_primary_name().get_name()

        ref_tup = None
        if person_handle in self.dnumber:
            # Main descendant in this report
            ref_tup = (self.report_count, self.generation+1, \
                       self.dnumber[person_handle], False, name)
        elif main_handle is not None:
            if main_handle in self.dnumber:
                main_person = self.database.get_person_from_handle(main_handle)
                main_name = main_person.get_primary_name().get_name()
                ref_tup = (self.report_count, self.generation+1, \
                           self.dnumber[main_handle], True, name)

        if person_handle not in self.report_app_ref:
            self.report_app_ref[person_handle] = []

        if ref_tup:
            self.report_app_ref[person_handle].append(ref_tup)

    def write_report(self):
        """
        This function is called by the report system and writes the report.
        """
        self.ca = CollectAscendants(self.database, self.user, self.title)
        self.ascendants = self.ca.collect_data(self.filter, self.center_person)

        if self.dubperson:
            if len(self.ascendants) > 1:
                self.user.begin_progress(self.title,
                                 _('Generating %s report references...') % \
                                 (len(self.ascendants)), len(self.ascendants))

            # Need to do two runs of generations,
            # 1st run gets references for all people/mates in report
            # 2nd run actually generates the report and includes the references
            self.report_app_ref = {}
            self.report_count = 0
            self.index_of_dates = {}
            self.index_of_places = {}
            self.phandle = 0 # person handle used by append_event to retrieve name and references to the current person
            for asc_handle in self.ascendants:
                if len(self.ascendants) > 1:
                    self.user.step_progress()
                    # Add item for table of contents page
                self.report_count += 1

                # in the list
                self.__init_variables()

                if self.numbering == "Henry":
                    self.apply_henry_filter(asc_handle, 1, "1")
                elif self.numbering == "d'Aboville":
                    self.apply_daboville_filter(asc_handle, 1, "1")
                elif self.numbering == "Record (Modified Register)":
                    self.apply_mod_reg_filter(asc_handle)
                else:
                    raise AttributeError("no such numbering: '%s'" %
                                        self.numbering)

                self.generation = 0
                for self.generation in range(len(self.gen_keys)):

                    if self.childref:
                        self.prev_gen_handles = self.gen_handles.copy()
                        self.gen_handles.clear()

                    for key in self.gen_keys[self.generation]:
                        person_handle = self.map[key]
                        person = \
                            self.database.get_person_from_handle(person_handle)
                        self.gen_handles[person_handle] = key
                        self.__update_report_app_ref(person_handle)

                        if self.inc_mates:
                            for fam_handle in person.get_family_handle_list():
                                family = \
                                    self.database.get_family_from_handle( \
                                        fam_handle)
                                if person.get_gender() == Person.MALE:
                                    mate_handle = family.get_mother_handle()
                                else:
                                    mate_handle = family.get_father_handle()

                                if mate_handle:
                                    self.__update_report_app_ref(mate_handle,
                                                                person_handle)
            if len(self.ascendants) > 1:
                self.user.end_progress()

        if len(self.ascendants) > 1:
            self.user.begin_progress(self.title,
                    _('Writing %s reports...') % \
                    (len(self.ascendants)), len(self.ascendants))
            # If there is only one item, then no need for a table
            # of contents, however if we have more than one lets generate one
            self.write_toc()

        self.report_count = 0
        self.persons_printed = dict()
        for asc_handle in self.ascendants:
            if len(self.ascendants) > 1:
                self.user.step_progress()
            # Simplest thing is to do a separate report for each person
            # in the list
            self.__init_variables()

            if self.numbering == "Henry":
                self.apply_henry_filter(asc_handle, 1, "1")
            elif self.numbering == "d'Aboville":
                self.apply_daboville_filter(asc_handle, 1, "1")
            elif self.numbering == "Record (Modified Register)":
                self.apply_mod_reg_filter(asc_handle)
            else:
                raise AttributeError("no such numbering: '%s'" % self.numbering)

            person = self.database.get_person_from_handle(asc_handle)
            name = self._name_display.display_name(person.get_primary_name())

            self.doc.start_paragraph("DDR-Title")

            self.report_count += 1
            if len(self.ascendants) > 1:
                self.title = \
                    self._("%(report_count)s. Descendant Report for " \
                    "%(person_name)s") % {'report_count' : self.report_count, \
                    'person_name' : name }
            else:
                self.title = self._("Descendant Report for " \
                                    "%(person_name)s") % {'person_name' : name }
            mark = IndexMark(self.title, INDEX_TYPE_TOC, 1)
            self.doc.write_text(self.title, mark)
            self.doc.end_paragraph()

            self.generation = 0

            self.numbers_printed = list()
            for self.generation in range(len(self.gen_keys)):
                if self.pgbrk and self.generation > 0:
                    self.doc.page_break()
                self.doc.start_paragraph("DDR-Generation")
                text = self._("Generation %d") % (self.generation+1)
                mark = IndexMark(text, INDEX_TYPE_TOC, 2)
                self.doc.write_text(text, mark)
                self.doc.end_paragraph()
                if self.childref:
                    self.prev_gen_handles = self.gen_handles.copy()
                    self.gen_handles.clear()

                for key in self.gen_keys[self.generation]:
                    person_handle = self.map[key]
                    self.gen_handles[person_handle] = key
                    self.write_person(key)

            # Put a page break between reports
            self.doc.page_break()


#TODO add user interface information

        if self.inc_index_names:
            self.write_index_of_names()
            self.doc.page_break()

        if self.inc_index_of_dates:
            self.write_index_of_dates()
            self.doc.page_break()

        if self.inc_index_of_places:
            self.write_index_of_places()
            self.doc.page_break()


        # Write endnotes at end of all reports
        if self.inc_sources:
            if self.pgbrkenotes:
                self.doc.page_break()
            # it ignores language set for Note type (use locale)
            endnotes.write_endnotes(self.bibli, self.database, self.doc,
                                    printnotes=self.inc_srcnotes)

        if len(self.ascendants) > 1:
            self.user.end_progress()


    def write_index_of_places(self):
        """
        This function prints the index of places.
        """
        self.doc.start_paragraph("DDR-Title")
        self.doc.write_text_citation(self._("Index of Places"))
        self.doc.end_paragraph()

        sorted_places = sorted(self.index_of_places.keys())
        for place in sorted_places:
            self.doc.start_paragraph("DDR-IndexPlacesPlace")
            ref_str = "%s" % (place)
            self.doc.write_text_citation(ref_str)
            self.doc.end_paragraph()

            sorted_dates = sorted(self.index_of_places[place].keys())
            for date in sorted_dates:
                self.doc.start_paragraph("DDR-IndexPlacesEntry")
                ref_str = "%s" % (self.index_of_places[place][date])
                self.doc.write_text_citation(ref_str)
                self.doc.end_paragraph()


    def write_index_of_dates(self):
        """
        This function prints the index of dates.
        """
        self.doc.start_paragraph("DDR-Title")
        self.doc.write_text_citation(self._("Index of Dates"))
        self.doc.end_paragraph()

        sorted_year = sorted(self.index_of_dates.keys())
        for year in sorted_year:
            self.doc.start_paragraph("DDR-IndexDatesYear")
            ref_str = "%s" % (year)
            self.doc.write_text_citation(ref_str)
            self.doc.end_paragraph()

            sorted_dates = sorted(self.index_of_dates[year].keys())
            for date in sorted_dates:
                self.doc.start_paragraph("DDR-IndexPlacesEntry")
                ref_str = "%s" % (self.index_of_dates[year][date])
                self.doc.write_text_citation(ref_str)
                self.doc.end_paragraph()

    def write_index_of_names(self):
        """
        This funciont writes the names in alfabetical order and give reference
        where the person appears in the reports.
        """
        self.doc.start_paragraph("DDR-Title")
        self.doc.write_text_citation(self._("Index of Names"))
        self.doc.end_paragraph()

        self.doc.start_paragraph("DDR-IndexNamesHeader")
        # TRANSLATORS: This is a column header; the word widths vary with font
        # so we just seperate the words with ", "
        ref_str = self._("Report, Generation, Person, Name")
        self.doc.write_text_citation(ref_str)
        self.doc.end_paragraph()

        sorted_phandles = sorted(self.report_app_ref.keys(), key=lambda k: self.report_app_ref[k][0][4])
        for person_handle in sorted_phandles:

            first_line_done = False
            for repno, gen, per, mate, name in self.report_app_ref[person_handle]:
                if not first_line_done:
                    self.doc.start_paragraph("DDR-IndexNamesEntry")
                    ref_str = ("%13s %13s %15s    \t%s") \
                              % (repno, gen, per, name)
                    self.doc.write_text_citation(ref_str)
                    self.doc.end_paragraph()
                elif self.inc_appearances:
                    self.doc.start_paragraph("DDR-IndexNamesEntry")
                    ref_str = ("%13s %13s %15s                 \"  ") \
                              % (repno, gen, per)
                    self.doc.write_text_citation(ref_str)
                    self.doc.end_paragraph()
                first_line_done = True

#BOOK start
    def write_toc(self):
        if len(self.ascendants) <= 1:
            return

        self.doc.start_paragraph("DDR-Title")
        title = self._("Detailed Descendant Report")
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()

        self.doc.start_paragraph("DDR-Generation")
        title = self._("Table Of Contents")
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()

        report_count = 0
        for asc_handle in self.ascendants:
            person = self.database.get_person_from_handle(asc_handle)
            name = self._name_display.display_name(person.get_primary_name())
            report_count = report_count + 1
            self.doc.start_paragraph("DDR-Entry")
            text = self._("{report_count:d}. {name}").format(report_count=report_count, name=name)
            mark = IndexMark(text, INDEX_TYPE_TOC, 2)
            self.doc.write_text(text, mark)
            self.doc.end_paragraph()

        self.doc.page_break()
#BOOK end

    def write_path(self, person):
        path = []
        while True:
            #person changes in the loop
            family_handle = person.get_main_parents_family_handle()
            if family_handle:
                family = self.database.get_family_from_handle(family_handle)
                mother_handle = family.get_mother_handle()
                father_handle = family.get_father_handle()
                if mother_handle and mother_handle in self.dnumber:
                    person = self.database.get_person_from_handle(mother_handle)
                    person_name = \
                        self._name_display.display_name(person.get_primary_name())
                    path.append(person_name)
                elif father_handle and father_handle in self.dnumber:
                    person = self.database.get_person_from_handle(father_handle)
                    person_name = \
                        self._name_display.display_name(person.get_primary_name())
                    path.append(person_name)
                else:
                    break
            else:
                break

        index = len(path)

        if index:
            self.doc.write_text("(")

        for name in path:
            if index == 1:
                self.doc.write_text(name + "-" + str(index) + ") ")
            else:
                self.doc.write_text(name + "-" + str(index) + "; ")
            index -= 1

    def write_person(self, key):
        """Output birth, death, parentage, marriage and notes information """

        person_handle = self.map[key]
        person = self.database.get_person_from_handle(person_handle)
        self.phandle = person_handle #used by append_event

        val = self.dnumber[person_handle]

        if val in self.numbers_printed:
            return
        else:
            self.numbers_printed.append(val)

        self.doc.start_paragraph("DDR-First-Entry","%s." % val)

        name = self._name_display.display_formal(person)
        mark = ReportUtils.get_person_mark(self.database, person)

        self.doc.start_bold()
        self.doc.write_text(name, mark)
        if name[-1:] == '.':
            self.doc.write_text_citation("%s " % self.endnotes(person))
        else:
            self.doc.write_text_citation("%s. " % self.endnotes(person))
        self.doc.end_bold()

        if self.inc_paths:
            self.write_path(person)

#BOOK start
        if self.dubperson and  self.report_count > 1:
            if person_handle in self.persons_printed:
                # Don't print duplicate people in second reports, simple reference them
                rep, gen, dnum = self.persons_printed[person_handle]
                self.doc.write_text(self._(
                    "See Report : {report}, Generation : {generation}, Person : {person}").format(report=rep, generation=gen, person=dnum))
                self.doc.end_paragraph()
                return

        self.persons_printed[person_handle] = (self.report_count, self.generation+1, val)
#BOOK end

        if self.dubperson:
            # Check for duplicate record (result of distant cousins marrying)
            for dkey in sorted(self.map):
                if dkey >= key:
                    break
                if self.map[key] == self.map[dkey]:
                    self.doc.write_text(self._(
                        "%(name)s is the same person as [%(id_str)s].") % {
                            'name' :'',
                            'id_str': self.dnumber[self.map[dkey]],
                            }
                        )
                    self.doc.end_paragraph()
                    return

        self.doc.end_paragraph()

        self.write_person_info(person, None) #BOOK

        if (self.inc_mates or self.listchildren or self.inc_notes or
            self.inc_events or self.inc_attrs):
            for family_handle in person.get_family_handle_list():
                family = self.database.get_family_from_handle(family_handle)
                if self.inc_mates:
                    self.__write_mate(person, family)
                if self.listchildren:
                    self.__write_children(family)
                if self.inc_notes:
                    self.__write_family_notes(family)
                first = True
                if self.inc_events:
                    first = self.__write_family_events(family)
                if self.inc_attrs:
                    self.__write_family_attrs(family, first)

#BOOK start
    def write_report_ref(self, person, main_person):
        name = self._name_display.display_formal(person)
        person_handle = person.get_handle()
        main_person_handle = "VOID"
        if main_person is not None:
            main_person_handle = main_person.get_handle()

        header_done = False

        if person_handle in self.dnumber:
            dnum = self.dnumber[person_handle]
        elif main_person_handle in self.dnumber:
            dnum = self.dnumber[main_person_handle]
        else:
            dnum = "0"

        if self.inc_appearances:
            for repno, gen, per, mate, name in self.report_app_ref[person_handle]:
                if (repno != self.report_count or gen != self.generation+1) or \
                    (repno == self.report_count and gen == self.generation+1 \
                    and per != dnum):
                    if mate:
                        if not header_done:
                            self.doc.start_paragraph("DDR-NoteHeader")
                            self.doc.write_text(
                                self._("Report appearances for %s") % name)
                            self.doc.end_paragraph()
                            header_done = True

                        self.doc.start_paragraph("DDR-Entry")
                        ref_str = self._("Spouse of: Report: {report}, Generation: {generation}, Person: {person}").format(report=repno, generation=gen, person=per)
                        self.doc.write_text_citation(ref_str)
                        self.doc.end_paragraph()
                    else:
                        if not header_done:
                            self.doc.start_paragraph("DDR-NoteHeader")
                            self.doc.write_text(
                                self._("Report appearances for %s") % name)
                            self.doc.end_paragraph()
                            header_done = True

                        self.doc.start_paragraph("DDR-Entry")
                        ref_str = self._("Report: {report}, Generation: {generation}, Person: {person}").format(report=repno, generation=gen, person=per)
                        self.doc.write_text_citation(ref_str)
                        self.doc.end_paragraph()
#BOOK end

    def append_event(self, event_ref, family = False):

        (repno, gen, per, mate, name) = self.report_app_ref[self.phandle][0] # get first reference to the person

        text = ""
        event = self.database.get_event_from_handle(event_ref.ref)

        date = self._get_date(event.get_date_object())

        ph = event.get_place_handle()
        if ph:
            place = self.database.get_place_from_handle(ph).get_title()
        else:
            place = ''

        event_name = self._get_type(event.get_type())

        # add mate's name in case of family events
        if family == False:
            text = self._('%(event_name)s of %(name)s ') % {
                            'event_name' : self._(event_name), 'name' : name }
        else:
            mother_name, father_name = self.__get_mate_names(family)
            text = self._('%(event_name)s of %(name)s and %(mate)s ') % {
                            'event_name' : self._(event_name), 'name' : father_name, 'mate' : mother_name }

        if date and place:
            text +=  self._('%(date)s, %(place)s') % {
                       'date' : date, 'place' : place }
        elif date:
            text += self._('%(date)s') % {'date' : date}
        elif place:
            text += self._('%(place)s') % { 'place' : place }

        text += self._('. Ref: %(repno)s %(gen)s %(per)s ') % {
                        'repno' : repno, 'gen' : gen, 'per' : per }

        if (event.get_date_object().get_year() and self.inc_index_of_dates):
            self.__update_index_of_dates(event.get_date_object(), text)
        if (place and self.inc_index_of_places):
            self.__update_index_of_places(place, event.get_date_object(), text)


    def write_event(self, event_ref):
        text = ""
        event = self.database.get_event_from_handle(event_ref.ref)

        if self.fulldate:
            date = self._get_date(event.get_date_object())
        else:
            date = event.get_date_object().get_year()

        ph = event.get_place_handle()
        if ph:
            place = self.database.get_place_from_handle(ph).get_title()
        else:
            place = ''

        self.doc.start_paragraph('DDR-EventHeader')    #BOOK
        event_name = self._get_type(event.get_type())

#BOOK start
        self.doc.start_bold()
        text = self._('%(event_name)s:') % {'event_name' : self._(event_name)}
        self.doc.write_text_citation(text)
        self.doc.end_bold()

        text = ""
#BOOK end

        if date and place:
            text +=  self._('%(date)s, %(place)s') % {
                       'date' : date, 'place' : place }
        elif date:
            text += self._('%(date)s') % {'date' : date}
        elif place:
            text += self._('%(place)s') % { 'place' : place }

        if event.get_description():
            if text:
                text += ". "
            text += event.get_description()

        text += self.endnotes(event)

        if text:
            text += ". "

        text = self._(' %(event_text)s') % {'event_text' : text} #BOOK

        self.doc.write_text_citation(text)

        if self.inc_attrs:
            text = ""
            attr_list = event.get_attribute_list()[:]  # we don't want to modify cached original
            attr_list.extend(event_ref.get_attribute_list())
            for attr in attr_list:
                if text:
                    text += "; "
                attrName = self._get_type(attr.get_type())
                text += self._("%(type)s: %(value)s%(endnotes)s") % {
                    'type'     : self._(attrName),
                    'value'    : attr.get_value(),
                    'endnotes' : self.endnotes(attr) }
            text = " " + text
            self.doc.write_text_citation(text)

        self.doc.end_paragraph()

        if self.inc_notes:
            # if the event or event reference has a note attached to it,
            # get the text and format it correctly
            notelist = event.get_note_list()[:]  # we don't want to modify cached original
            notelist.extend(event_ref.get_note_list())
            for notehandle in notelist:
                note = self.database.get_note_from_handle(notehandle)
                self.doc.write_styled_note(note.get_styledtext(),
                        note.get_format(),"DDR-EventDetails",   # BOOK
                        contains_html= note.get_type() == NoteType.HTML_CODE)

    def __write_parents(self, person):
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            mother_handle = family.get_mother_handle()
            father_handle = family.get_father_handle()
            if mother_handle:
                mother = self.database.get_person_from_handle(mother_handle)
                mother_name = \
                    self._name_display.display_name(mother.get_primary_name())
                mother_mark = ReportUtils.get_person_mark(self.database, mother)
            else:
                mother_name = ""
                mother_mark = ""
            if father_handle:
                father = self.database.get_person_from_handle(father_handle)
                father_name = \
                    self._name_display.display_name(father.get_primary_name())
                father_mark = ReportUtils.get_person_mark(self.database, father)
            else:
                father_name = ""
                father_mark = ""
            text = self.__narrator.get_child_string(father_name, mother_name)
            if text:
                self.doc.write_text(text)
                if father_mark:
                    self.doc.write_text("", father_mark)
                if mother_mark:
                    self.doc.write_text("", mother_mark)

    def write_marriage(self, person):
        """
        Output marriage sentence.
        """
        is_first = True
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            spouse_handle = ReportUtils.find_spouse(person, family)
            name = ""
            spouse = None
            if spouse_handle:
                spouse = self.database.get_person_from_handle(spouse_handle)
                if spouse:
                    name = self._name_display.display_formal(spouse)
            text = ""
            spouse_mark = ReportUtils.get_person_mark(self.database, spouse)

            text = self.__narrator.get_married_string(family, is_first, self._name_display)

            if text:
                self.doc.write_text_citation(text, spouse_mark)
                is_first = False

    def __write_mate(self, person, family):
        """
        Write information about the person's spouse/mate.
        """
        if person.get_gender() == Person.MALE:
            mate_handle = family.get_mother_handle()
        else:
            mate_handle = family.get_father_handle()

        if mate_handle:
            mate = self.database.get_person_from_handle(mate_handle)

            self.doc.start_paragraph("DDR-MoreHeader")
            name = self._name_display.display_formal(mate)
            mark = ReportUtils.get_person_mark(self.database, mate)
            if family.get_relationship() == FamilyRelType.MARRIED:
                self.doc.write_text(self._("Spouse: %s") % name, mark)
            else:
                self.doc.write_text(self._("Relationship with: %s") % name, mark)
            if name[-1:] != '.':
                self.doc.write_text(".")
            self.doc.write_text_citation(self.endnotes(mate))
            self.doc.end_paragraph()

            if not self.inc_materef:
                # Don't want to just print reference
                self.phandle = mate_handle
                self.write_person_info(mate, None)  #BOOK
            else:
                # Check to see if we've married a cousin
                if mate_handle in self.dnumber:
                    self.doc.start_paragraph('DDR-MoreDetails')
                    self.doc.write_text_citation(
                        self._("Ref: {number}. {name}").format(number=self.dnumber[mate_handle], name=name))
                    self.doc.end_paragraph()
                else:
                    self.dmates[mate_handle] = person.get_handle()
                    self.write_person_info(mate, person) #BOOK

    def __get_mate_names(self, family):
        mother_handle = family.get_mother_handle()
        if mother_handle:
            mother = self.database.get_person_from_handle(mother_handle)
            mother_name = self._name_display.display(mother)
        else:
            mother_name = self._("unknown")

        father_handle = family.get_father_handle()
        if father_handle:
            father = self.database.get_person_from_handle(father_handle)
            father_name = self._name_display.display(father)
        else:
            father_name = self._("unknown")

        return mother_name, father_name

    def __write_children(self, family):
        """
        List the children for the given family.
        """
        if not family.get_child_ref_list():
            return

        mother_name, father_name = self.__get_mate_names(family)

        self.doc.start_paragraph("DDR-ChildTitle")
        self.doc.write_text(
                        self._("Children of %(mother_name)s and %(father_name)s") %
                            {'father_name': father_name,
                             'mother_name': mother_name
                             } )
        self.doc.end_paragraph()

        cnt = 1
        for child_ref in family.get_child_ref_list():
            child_handle = child_ref.ref
            child = self.database.get_person_from_handle(child_handle)
            child_name = self._name_display.display(child)
            child_mark = ReportUtils.get_person_mark(self.database, child)

            if self.childref and self.prev_gen_handles.get(child_handle):
                value = str(self.prev_gen_handles.get(child_handle))
                child_name += " [%s]" % value

            if self.inc_ssign:
                prefix = " "
                for family_handle in child.get_family_handle_list():
                    family = self.database.get_family_from_handle(family_handle)
                    if family.get_child_ref_list():
                        prefix = "+ "
                        break
            else:
                prefix = ""

            if child_handle in self.dnumber:
                self.doc.start_paragraph("DDR-ChildList",
                        prefix
                        + str(self.dnumber[child_handle])
                        + " "
                        + ReportUtils.roman(cnt).lower()
                        + ".")
            else:
                self.doc.start_paragraph("DDR-ChildList",
                              prefix + ReportUtils.roman(cnt).lower() + ".")
            cnt += 1

            self.doc.write_text("%s. " % child_name, child_mark)
            self.__narrator.set_subject(child)
            self.doc.write_text_citation(self.__narrator.get_born_string() or
                                         self.__narrator.get_christened_string() or
                                         self.__narrator.get_baptised_string())
            self.doc.write_text_citation(self.__narrator.get_died_string() or
                                         self.__narrator.get_buried_string())
            self.doc.end_paragraph()

    def __write_family_notes(self, family):
        """
        Write the notes for the given family.
        """
        notelist = family.get_note_list()
        if len(notelist) > 0:
            mother_name, father_name = self.__get_mate_names(family)

            self.doc.start_paragraph("DDR-NoteHeader")
            self.doc.write_text(
                self._('Notes for %(mother_name)s and %(father_name)s:') % {
                'mother_name' : mother_name,
                'father_name' : father_name })
            self.doc.end_paragraph()
            for notehandle in notelist:
                note = self.database.get_note_from_handle(notehandle)
                self.doc.write_styled_note(note.get_styledtext(),
                                           note.get_format(),"DDR-Entry")

    def __write_family_events(self, family):
        """
        List the events for the given family.
        """
        if not family.get_event_ref_list():
            return

        mother_name, father_name = self.__get_mate_names(family)

        first = 1
        for event_ref in family.get_event_ref_list():
            if first:
                self.doc.start_paragraph('DDR-MoreHeader')
                self.doc.write_text(
                    self._('More about %(mother_name)s and %(father_name)s:') % {
                    'mother_name' : mother_name,
                    'father_name' : father_name })
                self.doc.end_paragraph()
                first = 0
            self.write_event(event_ref)

            if (self.inc_index_of_dates or self.inc_index_of_places):
                self.append_event(event_ref, family)

        return first

    def __write_family_attrs(self, family, first):
        """
        List the attributes for the given family.
        """
        attrs = family.get_attribute_list()

        if first and attrs:
            mother_name, father_name = self.__get_mate_names(family)

            self.doc.start_paragraph('DDR-MoreHeader')
            self.doc.write_text(
                self._('More about %(mother_name)s and %(father_name)s:') % {
                'mother_name' : mother_name,
                'father_name' : father_name })
            self.doc.end_paragraph()

        for attr in attrs:
            self.doc.start_paragraph('DDR-MoreDetails')
            attrName = self._get_type(attr.get_type())
            text = self._("%(type)s: %(value)s%(endnotes)s") % {
                'type'     : self._(attrName),
                'value'    : attr.get_value(),
                'endnotes' : self.endnotes(attr) }
            self.doc.write_text_citation( text )
            self.doc.end_paragraph()

            if self.inc_notes:
                # if the attr or attr reference has a note attached to it,
                # get the text and format it correctly
                notelist = attr.get_note_list()
                for notehandle in notelist:
                    note = self.database.get_note_from_handle(notehandle)
                    self.doc.write_styled_note(note.get_styledtext(),
                             note.get_format(),"DDR-EventDetails")  #BOOK


    def write_person_info(self, person, main_person = None): #BOOK
        name = self._name_display.display_formal(person)
        self.__narrator.set_subject(person)

#BOOK start
        person_handle = person.get_handle()
        main_person_handle = "VOID"
        if main_person is not None:
            main_person_handle = main_person.get_handle()
#BOOK end

        plist = person.get_media_list()
        if self.addimages and len(plist) > 0:
            photo = plist[0]
            ReportUtils.insert_image(self.database, self.doc, photo, self._user)

        self.doc.start_paragraph("DDR-Entry")

        if not self.verbose:
            self.__write_parents(person)

        text = self.__narrator.get_born_string()
        if text:
            self.doc.write_text_citation(text)

        text = self.__narrator.get_baptised_string()
        if text:
            self.doc.write_text_citation(text)

        text = self.__narrator.get_christened_string()
        if text:
            self.doc.write_text_citation(text)

        text = self.__narrator.get_died_string(self.calcageflag)
        if text:
            self.doc.write_text_citation(text)

        text = self.__narrator.get_buried_string()
        if text:
            self.doc.write_text_citation(text)

        if self.verbose:
            self.__write_parents(person)
        self.write_marriage(person)
        self.doc.end_paragraph()

#Book start
        if self.dubperson and \
           person_handle in self.report_app_ref:
                self.write_report_ref(person, main_person)
                # Person appears in another report
#Book end

        notelist = person.get_note_list()
        if len(notelist) > 0 and self.inc_notes:
            self.doc.start_paragraph("DDR-NoteHeader")
            # feature request 2356: avoid genitive form
            self.doc.write_text(self._("Notes for %s") % name)
            self.doc.end_paragraph()
            for notehandle in notelist:
                note = self.database.get_note_from_handle(notehandle)
                self.doc.write_styled_note(note.get_styledtext(),
                        note.get_format(),"DDR-Entry",
                        contains_html= note.get_type() == NoteType.HTML_CODE)

        first = True
        if self.inc_names:
            for alt_name in person.get_alternate_names():
                if first:
                    self.doc.start_paragraph('DDR-MoreHeader')
                    self.doc.write_text(self._('More about %(person_name)s:') % {
                        'person_name' : name })
                    self.doc.end_paragraph()
                    first = False
                self.doc.start_paragraph('DDR-MoreDetails')
                atype = self._get_type(alt_name.get_type())
                aname = alt_name.get_regular_name()
                self.doc.write_text_citation(self._('%(name_kind)s: %(name)s%(endnotes)s') % {
                    'name_kind' : self._(atype),
                    'name' : aname,
                    'endnotes' : self.endnotes(alt_name),
                    })
                self.doc.end_paragraph()

        if (self.inc_events or self.inc_index_of_dates or self.inc_index_of_places):
            for event_ref in person.get_primary_event_ref_list():
                if self.inc_events:
                    if first:
                        self.doc.start_paragraph('DDR-MoreHeader')
                        self.doc.write_text(self._('More about %(person_name)s:') % {
                            'person_name' : self._name_display.display(person) })
                        self.doc.end_paragraph()
                        first = 0

                    self.write_event(event_ref)

                if (self.inc_index_of_dates or self.inc_index_of_places):
                    self.append_event(event_ref)

        if self.inc_addr:
            for addr in person.get_address_list():
                if first:
                    self.doc.start_paragraph('DDR-MoreHeader')
                    self.doc.write_text(self._('More about %(person_name)s:') % {
                        'person_name' : name })
                    self.doc.end_paragraph()
                    first = False
                self.doc.start_paragraph('DDR-MoreDetails')

                text = ReportUtils.get_address_str(addr)

                if self.fulldate:
                    date = self._get_date(addr.get_date_object())
                else:
                    date = addr.get_date_object().get_year()

                self.doc.write_text(self._('Address: '))
                if date:
                    self.doc.write_text( '%s, ' % date )
                self.doc.write_text( text )
                self.doc.write_text_citation( self.endnotes(addr) )
                self.doc.end_paragraph()

        if self.inc_attrs:
            attrs = person.get_attribute_list()
            if first and attrs:
                self.doc.start_paragraph('DDR-MoreHeader')
                self.doc.write_text(self._('More about %(person_name)s:') % {
                    'person_name' : name })
                self.doc.end_paragraph()
                first = False

            for attr in attrs:
                self.doc.start_paragraph('DDR-EventHeader')  #BOOK
                attrName = self._get_type(attr.get_type())

#BOOK start
                self.doc.start_bold()
                text = self._('%(type)s:') % {'type' : self._(attrName)}
                self.doc.write_text_citation(text)
                self.doc.end_bold()
#BOOK end

                text = self._(" %(value)s%(endnotes)s") % {
                    'value'    : attr.get_value(),
                    'endnotes' : self.endnotes(attr) }
                self.doc.write_text_citation( text )
                self.doc.end_paragraph()

    def endnotes(self, obj):
        if not obj or not self.inc_sources:
            return ""

        txt = endnotes.cite_source(self.bibli, self.database, obj)
        if txt:
            txt = '<super>' + txt + '</super>'
        return txt

#------------------------------------------------------------------------
#
# DetailedDescendantBookOptions
#
#------------------------------------------------------------------------
class DetailedDescendantBookOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        self.__db = dbase
        self.__pid = None
        self.__filter = None
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the detailed descendant report.
        """

        # Report Options

        add_option = partial(menu.add_option, _("Report Options"))

        self.__filter = FilterOption(_("Filter"), 0)
        self.__filter.set_help(
               _("Select filter to restrict people that appear in the report"))
        add_option("filter", self.__filter)

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the report"))
        add_option("pid", self.__pid)
        self.__pid.connect('value-changed', self.__update_filters)

        self.__update_filters()

        # We must figure out the value of the first option before we can
        # create the EnumeratedListOption
        fmt_list = global_name_display.get_name_format()
        name_format = EnumeratedListOption(_("Name format"), 0)
        name_format.add_item(0, _("Default"))
        for num, name, fmt_str, act in fmt_list:
            name_format.add_item(num, name)
        name_format.set_help(_("Select the format to display names"))
        add_option("name_format", name_format)

        numbering = EnumeratedListOption(_("Numbering system"), "Henry")
        numbering.set_items([
                ("Henry",      _("Henry numbering")),
                ("d'Aboville", _("d'Aboville numbering")),
                ("Record (Modified Register)",
                               _("Record (Modified Register) numbering"))])
        numbering.set_help(_("The numbering system to be used"))
        add_option("numbering", numbering)

        generations = NumberOption(_("Generations"), 10, 1, 100)
        generations.set_help(
            _("The number of generations to include in the report")
            )
        add_option("gen", generations)

        pagebbg = BooleanOption(_("Page break between generations"), False)
        pagebbg.set_help(
                     _("Whether to start a new page after each generation."))
        add_option("pagebbg", pagebbg)

        pageben = BooleanOption(_("Page break before end notes"),False)
        pageben.set_help(
                     _("Whether to start a new page before the end notes."))
        add_option("pageben", pageben)

        stdoptions.add_localization_option(menu, "Report Options")

        # Content

        add_option = partial(menu.add_option, _("Content"))

        usecall = BooleanOption(_("Use callname for common name"), False)
        usecall.set_help(_("Whether to use the call name as the first name."))
        add_option("usecall", usecall)

        fulldates = BooleanOption(_("Use full dates instead of only the year"),
                                  True)
        fulldates.set_help(_("Whether to use full dates instead of just year."))
        add_option("fulldates", fulldates)

        listc = BooleanOption(_("List children"), True)
        listc.set_help(_("Whether to list children."))
        add_option("listc", listc)

        computeage = BooleanOption(_("Compute death age"),True)
        computeage.set_help(_("Whether to compute a person's age at death."))
        add_option("computeage", computeage)

        omitda = BooleanOption(_("Omit duplicate ancestors"), True)
        omitda.set_help(_("Whether to omit duplicate ancestors."))
        add_option("omitda", omitda)

        verbose = BooleanOption(_("Use complete sentences"), True)
        verbose.set_help(
                 _("Whether to use complete sentences or succinct language."))
        add_option("verbose", verbose)

        desref = BooleanOption(_("Add descendant reference in child list"),
                               True)
        desref.set_help(
                    _("Whether to add descendant references in child list."))
        add_option("desref", desref)

        category_name = _("Include")
        add_option = partial(menu.add_option, _("Include"))

        incnotes = BooleanOption(_("Include notes"), True)
        incnotes.set_help(_("Whether to include notes."))
        add_option("incnotes", incnotes)

        incattrs = BooleanOption(_("Include attributes"), False)
        incattrs.set_help(_("Whether to include attributes."))
        add_option("incattrs", incattrs)

        incphotos = BooleanOption(_("Include Photo/Images from Gallery"), False)
        incphotos.set_help(_("Whether to include images."))
        add_option("incphotos", incphotos)

        incnames = BooleanOption(_("Include alternative names"), False)
        incnames.set_help(_("Whether to include other names."))
        add_option("incnames", incnames)

        incevents = BooleanOption(_("Include events"), False)
        incevents.set_help(_("Whether to include events."))
        add_option("incevents", incevents)

        incaddresses = BooleanOption(_("Include addresses"), False)
        incaddresses.set_help(_("Whether to include addresses."))
        add_option("incaddresses", incaddresses)

        incsources = BooleanOption(_("Include sources"), False)
        incsources.set_help(_("Whether to include source references."))
        add_option("incsources", incsources)

        incsrcnotes = BooleanOption(_("Include sources notes"), False)
        incsrcnotes.set_help(_("Whether to include source notes in the "
            "Endnotes section. Only works if Include sources is selected."))
        add_option("incsrcnotes", incsrcnotes)

        add_option = partial(menu.add_option, _("Include (2)"))

        incmates = BooleanOption(_("Include spouses"), False)
        incmates.set_help(_("Whether to include detailed spouse information."))
        add_option("incmates", incmates)

        incmateref = BooleanOption(_("Include spouse reference"), False)
        incmateref.set_help(_("Whether to include reference to spouse."))
        add_option("incmateref", incmateref)

        incssign = BooleanOption(_("Include sign of succession ('+')"
                                   " in child-list"), True)
        incssign.set_help(_("Whether to include a sign ('+') before the"
                            " descendant number in the child-list to indicate"
                            " a child has succession."))
        add_option("incssign", incssign)

        incpaths = BooleanOption(_("Include path to start-person"), False)
        incpaths.set_help(_("Whether to include the path of descendancy "
                            "from the start-person to each descendant."))
        add_option("incpaths", incpaths)

        incindexnames = BooleanOption(_("Include Index of Names"), False)
        incindexnames.set_help(_("Whether to include the index of Names "
                            "at the end of the report."))
        add_option("incindexnames", incindexnames)

        incindexdates = BooleanOption(_("Include index of Dates"), False)
        incindexdates.set_help(_("Whether to include the index of Dates "
                            "at the end of the report."))
        add_option("incindexdates", incindexdates)

        incindexplaces = BooleanOption(_("Include index of Places"), False)
        incindexplaces.set_help(_("Whether to include the index of Places "
                            "at the end of the report."))
        add_option("incindexplaces", incindexplaces)

        incappearances = BooleanOption(_("Include the 'Report appearances' "
                                         "section with each person"), True)
        incappearances.set_help(_("The 'Report appearances' section shows "
                                  "other places in the report where the person"
                                  " is mentioned."))
        add_option("incappearances", incappearances)

        # Missing information

        add_option = partial(menu.add_option, _("Missing information"))

        repplace = BooleanOption(_("Replace missing places with ______"), False)
        repplace.set_help(_("Whether to replace missing Places with blanks."))
        add_option("repplace", repplace)

        repdate = BooleanOption(_("Replace missing dates with ______"), False)
        repdate.set_help(_("Whether to replace missing Dates with blanks."))
        add_option("repdate", repdate)

    def __update_filters(self):
        """
        Update the filter list based on the selected person
        """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        filter_list = ReportUtils.get_person_filters(person, False)
        self.__filter.set_filters(filter_list)

    def make_default_style(self, default_style):
        """Make the default output style for the Detailed Descendant Report"""
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=16, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_bottom_border(1)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_description(_('The style used for the title of the page.'))
        default_style.add_paragraph_style("DDR-Title", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=14, italic=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the generation header.'))
        default_style.add_paragraph_style("DDR-Generation", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=10, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_left_margin(1.5)   # in centimeters
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the children list title.'))
        default_style.add_paragraph_style("DDR-ChildTitle", para)

        font = FontStyle()
        font.set(size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=-0.75, lmargin=2.25)
        para.set_top_margin(0.125)
        para.set_bottom_margin(0.125)
        para.set_description(_('The style used for the children list.'))
        default_style.add_paragraph_style("DDR-ChildList", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=10, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The basic style used for Note header.'))
        default_style.add_paragraph_style("DDR-NoteHeader", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=10, italic=0, bold=0)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The basic style used for the text display.'))
        default_style.add_paragraph_style("DDR-Entry", para)

        para = ParagraphStyle()
        para.set(first_indent=-1.5, lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the first personal entry.'))
        default_style.add_paragraph_style("DDR-First-Entry", para)

        font = FontStyle()
        font.set(size=10, face=FONT_SANS_SERIF, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the More About header and '
            'for headers of mates.'))
        default_style.add_paragraph_style("DDR-MoreHeader", para)

        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for additional detail data.'))
        default_style.add_paragraph_style("DDR-MoreDetails", para)

        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=1.75)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for note detail data.'))
        default_style.add_paragraph_style("DDR-EventHeader", para)

        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=2.0)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for note detail data.'))
        default_style.add_paragraph_style("DDR-EventDetails", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the date in the Index of Dates.'))
        default_style.add_paragraph_style("DDR-IndexDatesYear", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=10, italic=0)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set(lmargin=1.00)
        para.set_description(_('The style used for the events in the Index of Dates.'))
        default_style.add_paragraph_style("DDR-IndexDatesEntry", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the header in the Index of Names.'))
        default_style.add_paragraph_style("DDR-IndexNamesHeader", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the references in the Index of Names.'))
        default_style.add_paragraph_style("DDR-IndexNamesEntry", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the header in the Index of Places.'))
        default_style.add_paragraph_style("DDR-IndexPlacesPlace", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set(lmargin=1.00)
        para.set_description(_('The style used for the references in the Index of Places.'))
        default_style.add_paragraph_style("DDR-IndexPlacesEntry", para)


        endnotes.add_endnote_styles(default_style)
