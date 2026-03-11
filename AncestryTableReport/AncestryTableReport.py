#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026      Bruno Forestier
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
# along with this program; if not, see <https://www.gnu.org/licenses/>.
#


"""Reports/Text Reports/Ancestry Table Report"""

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import math

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


from gramps.gen.errors import ReportError
from gramps.gen.lib import (ChildRefType, Person)
from gramps.gen.lib.date import Date
from gramps.gen.utils.db import (get_birth_or_fallback, get_marriage_or_fallback, get_death_or_fallback)
from gramps.gen.utils.symbols import Symbols
from gramps.gen.plug.menu import (BooleanOption, NumberOption, PersonOption)
from gramps.gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle,
                                    TableStyle, TableCellStyle,
                                    FONT_SANS_SERIF, INDEX_TYPE_TOC,
                                    PARA_ALIGN_CENTER, PARA_ALIGN_RIGHT,
                                    PAPER_LANDSCAPE)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.plug.report import stdoptions
from gramps.gen.proxy import CacheProxyDb
from gramps.gen.display.name import displayer as _nd
from gramps.gen.display.place import displayer as _pd

#------------------------------------------------------------------------
#
# log2val
#
#------------------------------------------------------------------------
def log2(val):
    """
    Calculate the log base 2 of a number
    """
    return int(math.log(val, 2))

#------------------------------------------------------------------------
#
# AncestryTable
#
#------------------------------------------------------------------------
class AncestryTable(Report):

    """
    AncestryTable class
    """

    def __init__(self, database, options, user):
        """
        Create the AncestryTable object that produces the report.

        The arguments are:

        database        - the Gramps database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.

        pid              - ID of the central person
        gen              - Maximum number of generations to include
        pagebbg          - Whether to include page breaks between generations
        add_nb_ancestors - Add a page with the number of ancestors per generation
        name_format      - Preferred format to display names
        place_format     - Preferred format to display places
        incl_private     - Whether to include private data
        inc_id           - Whether to include Gramps IDs
        living_people    - How to handle living people
        years_past_death - Consider as living this many years after death
        trans            - the translation language
        date_format      - Preferred format to display dates
        mask_calendar    - Whether to mask the name of the calendar in the dates
        """
        Report.__init__(self, database, options, user)

        self.map = {}
        menu = options.menu

        self.set_locale(menu.get_option_by_name('trans').get_value())

        stdoptions.run_date_format_option(self, menu)

        stdoptions.run_private_data_option(self, menu)
        stdoptions.run_living_people_option(self, menu, self._locale)
        self.database = CacheProxyDb(self.database)

        self.max_generations = menu.get_option_by_name('maxgen').get_value()
        self.pgbrk = menu.get_option_by_name('pagebbg').get_value()
        self.want_stat = menu.get_option_by_name('add_nb_ancestors').get_value()
        self.want_ids = menu.get_option_by_name('inc_id').get_value()
        self.mask_cal = menu.get_option_by_name('mask_calendar').get_value()

        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = self.database.get_person_from_gramps_id(pid)
        if self.center_person is None:
            raise ReportError(_("Person %(name)s is not in the Database") % {'name' : pid})

        stdoptions.run_name_format_option(self, menu)

        self.place_format = menu.get_option_by_name("place_format").get_value()

    def apply_filter(self, person_handle, person_handle2=None, index=1, family_handle=None, generation=1):
        """
        Recursive function to walk back all parents of the current person.
        When max_generations are hit, we stop the traversal.
        """

        # check for end of the current recursion level. This happens
        # if the persons handle are None, or if the max_generations is hit
        if (not person_handle and not person_handle2) or generation > self.max_generations:
            return

        # store the persons and the family in the map based off their index number
        # which is passed to the routine.
        self.map[index] = (person_handle, person_handle2, family_handle)

        # retrieve the Person instance from the database from the
        # passed person_handle and find the parents.
        if person_handle:
            person = self.database.get_person_from_handle(person_handle)
            father_handle = None
            mother_handle = None
            fam_handle = person.get_main_parents_family_handle()
            if fam_handle:
                family = self.database.get_family_from_handle(fam_handle)
                father_handle = family.get_father_handle()
                mother_handle = family.get_mother_handle()

            # Recursively call the function. It is okay if the handle is None,
            # since routine handles a handle of None
            self.apply_filter(father_handle, mother_handle, index*2, fam_handle, generation+1)

        # retrieve the Person instance from the database from the
        # passed person_handle2 and find the parents.
        if person_handle2:
            person = self.database.get_person_from_handle(person_handle2)
            father_handle = None
            mother_handle = None
            fam_handle = person.get_main_parents_family_handle()
            if fam_handle:
                family = self.database.get_family_from_handle(fam_handle)
                father_handle = family.get_father_handle()
                mother_handle = family.get_mother_handle()

            # Recursively call the function. It is okay if the handle is None,
            # since routine handles a handle of None
            self.apply_filter(father_handle, mother_handle, (index+1)*2, fam_handle, generation+1)

    def date_place(self, event):
        """
        return the date and the place of the event in the "date - place" format
        """

        if event:
            date_obj = event.get_date_object()
            date_text = self._get_date(date_obj)
            if self.mask_cal:
                # match_calendar removed the name of the calendar in the date
                date_text, cal = self._locale.date_parser.match_calendar(date_text, date_obj.get_calendar())

            place_handle = event.get_place_handle()
            if place_handle:
                place_text = _pd.display_event(self.database, event, self.place_format)
                return "%(date)s - %(place)s" % {
                    'date' : date_text,
                    'place' : place_text
                    }
            else:
                return date_text
        return ""


    def write_report(self):
        """
        The routine that actually creates the report. At this point, the document
        is opened and ready for writing.
        """

        def write_person(generation, n_sosa, person_handle):

            # Retrieve the Person instance from the database from the passed person_handle
            person = self.database.get_person_from_handle(person_handle)

            self.doc.start_row()

            # Write the Sosa number
            # The Sosa number has a style for the paternal branch of the center person
            # and a different style for the maternal branch of the center person
            self.doc.start_cell("ATR-EntryCell")
            if n_sosa >= (2 ** generation + 2 ** (generation - 1)) / 2:
                para_style = "ATR-SosaNumberMaternalBranch"
            else:
                para_style = "ATR-SosaNumberPaternalBranch"
            self.doc.start_paragraph(para_style)
            self.doc.write_text("%d" % n_sosa)
            self.doc.end_paragraph()
            self.doc.end_cell()

            # The data of men and the data of the women have a different style.
            para_style = "ATR-Female" if person.get_gender() == Person.FEMALE else "ATR-Male"

            # Write the name
            name = self._name_display.display(person)
            mark = utils.get_person_mark(self.database, person)
            self.doc.start_cell("ATR-EntryCell")
            self.doc.start_paragraph(para_style)
            self.doc.start_bold()
            self.doc.write_text(name, mark)
            self.doc.end_bold()
            if self.want_ids:
                self.doc.write_text(' (%s)' % person.get_gramps_id())
            self.doc.end_paragraph()
            self.doc.end_cell()

            # Write the birth (date and place if available)
            self.doc.start_cell("ATR-EntryCell")
            self.doc.start_paragraph(para_style)
            self.doc.write_text(self.date_place(get_birth_or_fallback(self.database, person)))
            self.doc.end_paragraph()
            self.doc.end_cell()

            # Write the death (date and place if available)
            self.doc.start_cell("ATR-EntryCell")
            self.doc.start_paragraph(para_style)
            self.doc.write_text(self.date_place(get_death_or_fallback(self.database, person)))
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.end_row()


        # Call apply_filter to build the self.map array of people in the
        # database that match the ancestry
        self.apply_filter(self.center_person.get_handle())

        # Write the title line. Set an INDEX mark so that this section will be
        # identified as a major category if this is included in a Book report
        name_center = self._name_display.display_formal(self.center_person)
        # feature request 2356: avoid genitive form
        title = self._("Ancestry Table Report for %(name)s") % {'name' : name_center}
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)
        self.doc.start_paragraph("ATR-Title")
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()

        # Get the symbol for the marriage
        symbols = Symbols()
        symbol_marr = symbols.get_symbol_for_string(symbols.SYMBOL_MARRIAGE)

        generation = 0
        ancestors_per_gen = []
        ancestors_in_gen = 0
        self.doc.start_table("AncestryTable", "ATR-Table")

        # get the entries out of the map, and sort them.
        for key in sorted(self.map):

            # check the index number to see if we need to start a new generation
            if generation == log2(key):

                # generate a page break if requested
                if self.pgbrk and generation > 0:
                    self.doc.end_table()
                    self.doc.page_break()
                    self.doc.start_table("AncestryTable", "ATR-Table")
                if generation > 0:
                    ancestors_per_gen.append(ancestors_in_gen)
                    ancestors_in_gen = 0
                generation += 1

                # Create the Generation title, set an index marker
                self.doc.start_row()
                self.doc.start_cell("ATR-GenerationCell", 4)
                gen_text = self._("Generation %(gen_number)d") % {'gen_number' : generation}
                mark = IndexMark(gen_text, INDEX_TYPE_TOC, 2)
                self.doc.start_paragraph("ATR-Generation")
                self.doc.write_text(gen_text, mark)
                self.doc.end_paragraph()
                self.doc.end_cell()
                self.doc.end_row()

            father_handle, mother_handle, family_handle = self.map[key]

            # Write the informations about the father
            if father_handle:
                write_person(generation, key, father_handle)
                ancestors_in_gen += 1

            # Write the marriage (date and place if available)
            if family_handle:
                marriage_text = self.date_place(get_marriage_or_fallback(self.database, self.database.get_family_from_handle(family_handle)))
                if marriage_text:
                    self.doc.start_row()
                    self.doc.start_cell("ATR-EntryCell", 4)
                    self.doc.start_paragraph("ATR-Marriage")
                    self.doc.write_text("%(symbol)s %(marr)s" % {'symbol' : symbol_marr,
                                                                 'marr' : marriage_text})
                    self.doc.end_paragraph()
                    self.doc.end_cell()
                    self.doc.end_row()

            # Write the informations about the mother
            if mother_handle:
                write_person(generation, key+1, mother_handle)
                ancestors_in_gen += 1

            # Create an empty row to separate the families
            self.doc.start_row()
            self.doc.start_cell("ATR-EmptyCell", 4)
            self.doc.start_paragraph("ATR-Empty")
            self.doc.write_text(" ")
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.end_row()

        ancestors_per_gen.append(ancestors_in_gen)
        self.doc.end_table()

        # Write the number of ancestors per generation in a table on a new page
        if self.want_stat:
            self.doc.page_break()
            # Write the title of the page
            title = self._("Number of Ancestors for %(name)s") % {'name' : name_center}
            mark = IndexMark(title, INDEX_TYPE_TOC, 1)
            self.doc.start_paragraph("ATR-Title")
            self.doc.write_text(title+"\n", mark)
            self.doc.end_paragraph()

            # Write the header of the table
            self.doc.start_table("AncestryTable", "ATR-StatTable")
            self.doc.start_row()
            cols_header = [("ATR-EmptyCell","ATR-Empty"," "),
                           ("ATR-StatCell","ATR-StatHeader",self._("Generation")),
                           ("ATR-StatCell","ATR-StatHeader",self._("Ancestors")),
                           ("ATR-StatCell","ATR-StatHeader",self._("Maximum")),
                           ("ATR-EmptyCell","ATR-Empty"," ")]
            for cell_style, para_style, text in cols_header:
                self.doc.start_cell(cell_style)
                self.doc.start_paragraph(para_style)
                self.doc.write_text(text)
                self.doc.end_paragraph()
                self.doc.end_cell()
            self.doc.end_row()

            # Write the number of ancestors per generation
            n_gen = 1
            max_ancestors = 0
            for ancestors_in_gen in ancestors_per_gen:
                self.doc.start_row()
                self.doc.start_cell("ATR-EmptyCell")
                self.doc.end_cell()
                self.doc.start_cell("ATR-StatCell")
                self.doc.start_paragraph("ATR-StatEntry")
                self.doc.write_text("%d" % n_gen )
                self.doc.end_paragraph()
                self.doc.end_cell()
                self.doc.start_cell("ATR-StatCell")
                self.doc.start_paragraph("ATR-StatEntry")
                self.doc.write_text("%d" % ancestors_in_gen)
                self.doc.end_paragraph()
                self.doc.end_cell()
                self.doc.start_cell("ATR-StatCell")
                self.doc.start_paragraph("ATR-StatEntry")
                self.doc.write_text("%d" % 2 ** (n_gen-1))
                max_ancestors += 2 ** (n_gen-1)
                self.doc.end_paragraph()
                self.doc.end_cell()
                self.doc.start_cell("ATR-EmptyCell")
                self.doc.end_cell()
                self.doc.end_row()
                n_gen += 1

            #  Write the total
            self.doc.start_row()
            self.doc.start_cell("ATR-EmptyCell")
            self.doc.end_cell()
            self.doc.start_cell("ATR-StatCell")
            self.doc.start_paragraph("ATR-StatTotal")
            self.doc.write_text(_("Total"))
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.start_cell("ATR-StatCell")
            self.doc.start_paragraph("ATR-StatTotal")
            self.doc.write_text("%(total)d" % {'total' : sum(ancestors_per_gen)-1})
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.start_cell("ATR-StatCell")
            self.doc.start_paragraph("ATR-StatTotal")
            self.doc.write_text("%(max)d" % {'max' : max_ancestors-1})
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.start_cell("ATR-EmptyCell")
            self.doc.end_cell()
            self.doc.end_row()

            self.doc.end_table()

#------------------------------------------------------------------------
#
# AncestryTableOptions
#
#------------------------------------------------------------------------
class AncestryTableOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        self.__db = dbase
        self.__pid = None
        MenuReportOptions.__init__(self, name, dbase)

    def get_subject(self):
        """ Return a string that describes the subject of the report. """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        return _nd.display(person)

    def add_menu_options(self, menu):
        """
        Add options to the menu for the ancestor report.
        """

        category_name = _("Report Options")

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the report"))
        menu.add_option(category_name, "pid", self.__pid)

        maxgen = NumberOption(_("Generations"), 10, 1, 100)
        maxgen.set_help(_("The number of generations to include in the report"))
        menu.add_option(category_name, "maxgen", maxgen)

        pagebbg = BooleanOption(_("Page break between generations"), False)
        pagebbg.set_help(_("To start a new page after each generation."))
        menu.add_option(category_name, "pagebbg", pagebbg)

        add_nb_ancestors = BooleanOption(_("Number of ancestors per generation"), True)
        add_nb_ancestors.set_help(_("Add a page with tne number of ancestors per generation."))
        menu.add_option(category_name, "add_nb_ancestors", add_nb_ancestors)

        stdoptions.add_gramps_id_option(menu, category_name)

        stdoptions.add_private_data_option(menu, category_name)

        stdoptions.add_living_people_option(menu, category_name)

        category_name = _("Report Options (2)")

        locale_opt = stdoptions.add_localization_option(menu, category_name)

        stdoptions.add_name_format_option(menu, category_name)

        stdoptions.add_place_format_option(menu, category_name)

        stdoptions.add_date_format_option(menu, category_name, locale_opt)

        mask_calendar = BooleanOption(_("Mask the name of the calendar in the dates"), True)
        mask_calendar.set_help(_("By default, except for gregorian dates, Gramps shows the name of the calendar in the dates."))
        menu.add_option(category_name, "mask_calendar", mask_calendar)


    def make_default_style(self, default_style):
        """
        Make the default output style for the ancestry table report.
        """

        # Set the paper orientation to landscape
        self.handler.set_orientation(PAPER_LANDSCAPE)

        #
        # ATR-Title
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=16, bold=1, color=(64,64,64))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_description(_('The style used for the title of the report.'))
        default_style.add_paragraph_style("ATR-Title", para)

        #
        # ATR-Generation
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=14, italic=1, bold=1, color=(64,64,64))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set_description(_('The style used for the generation header.'))
        default_style.add_paragraph_style("ATR-Generation", para)

        #
        # ATR-SosaNumberPaternalBranch
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=9, color=(96,119,163))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_RIGHT)
        para.set_description(_('The style used for the Sosa number of the paternal branch.'))
        default_style.add_paragraph_style("ATR-SosaNumberPaternalBranch", para)

        #
        # ATR-SosaNumberMaternalBranch
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=9, color=(216,98,98))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_RIGHT)
        para.set_description(_('The style used for the Sosa number of the maternal branch.'))
        default_style.add_paragraph_style("ATR-SosaNumberMaternalBranch", para)

        #
        # ATR-Male
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=9, color=(96,119,163))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The style used for the data of the males.'))
        default_style.add_paragraph_style("ATR-Male", para)

        #
        # ATR-Female
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=9, color=(216,98,98))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The style used for the data of the females.'))
        default_style.add_paragraph_style("ATR-Female", para)

        #
        # ATR-Marriage
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=9, color=(64,64,64))
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_description(_('The style used for the marriage.'))
        default_style.add_paragraph_style("ATR-Marriage", para)

        #
        # ATR-Empty
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The style used for an empty row.\nTo enlarge the height of the empty row, just increse the size of the police.'))
        default_style.add_paragraph_style("ATR-Empty", para)

        #
        # ATR-Table
        #
        table = TableStyle()
        table.set_width(100)
        table.set_columns(4)
        table.set_column_width(0, 7)
        table.set_column_width(1, 33)
        table.set_column_width(2, 30)
        table.set_column_width(3, 30)
        default_style.add_table_style('ATR-Table', table)

        #
        # ATR-GenerationCell
        #
        cell = TableCellStyle()
        cell.set_padding(0.1)
        cell.set_borders(0)
        default_style.add_cell_style('ATR-GenerationCell', cell)

        #
        # ATR-EntryCell
        #
        cell = TableCellStyle()
        cell.set_padding(0.1)
        cell.set_borders(1)
        default_style.add_cell_style('ATR-EntryCell', cell)

        #
        # ATR-StatHeader
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=11, bold=True)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_RIGHT)
        para.set_description(_('The style used for the header table of the number of ancestors per generation.'))
        default_style.add_paragraph_style("ATR-StatHeader", para)

        #
        # ATR-StatEntry
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=11)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_RIGHT)
        para.set_description(_('The style used for the number of ancestors per generation.'))
        default_style.add_paragraph_style("ATR-StatEntry", para)

        #
        # ATR-StatTotal
        #
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=11, bold=True)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_RIGHT)
        para.set_description(_('The style used for the total line of the number of ancestors per generation.'))
        default_style.add_paragraph_style("ATR-StatTotal", para)

        #
        # ATR-StatTable
        #
        table = TableStyle()
        table.set_width(100)
        table.set_columns(5)
        table.set_column_width(0, 25)
        table.set_column_width(1, 14)
        table.set_column_width(2, 18)
        table.set_column_width(3, 18)
        table.set_column_width(0, 25)
        default_style.add_table_style('ATR-StatTable', table)

        #
        # ATR-StatCell
        #
        cell = TableCellStyle()
        cell.set_padding(0.1)
        cell.set_borders(1)
        default_style.add_cell_style('ATR-StatCell', cell)

        #
        # ATR-EmptyCell
        #
        cell = TableCellStyle()
        cell.set_borders(0)
        default_style.add_cell_style('ATR-EmptyCell', cell)
