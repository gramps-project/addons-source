#
# Copyright (C) 2011 Matt Keenan (matt.keenan@gmail.com)
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

"""
Reports/Books/Descendant Book.
Merged with Trunk Rev r18378
"""

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
import copy
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle,
                            FONT_SANS_SERIF, INDEX_TYPE_TOC, PARA_ALIGN_CENTER)
from gramps.gen.plug.menu import (NumberOption, PersonOption, BooleanOption,
                           EnumeratedListOption, FilterOption)
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.errors import ReportError
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
import gramps.gen.datehandler
from gramps.gen.sort import Sort
from gramps.gen.utils.db import (get_birth_or_fallback, get_death_or_fallback,
                       get_marriage_or_fallback, get_divorce_or_fallback)

from CollectAscendants import CollectAscendants
from RunReport import RunReport

report_person_ref = dict()
report_titles = dict()

#------------------------------------------------------------------------
#
# PrintSimple
#   Simple numbering system
#
#------------------------------------------------------------------------
class PrintSimple():
    def __init__(self, showdups):
        self.showdups = showdups
        self.num = {0:1}

    def number(self, level):
        if self.showdups:
            # Just show original simple numbering
            to_return = "%d." % level
        else:
            to_return = str(level)
            if level > 1:
                to_return += "-" + str(self.num[level-1])
            to_return += "."

            self.num[level] = 1
            self.num[level-1] = self.num[level-1] + 1

        return to_return
    
    
#------------------------------------------------------------------------
#
# PrintVlliers
#   de_Villiers_Pama numbering system
#
#------------------------------------------------------------------------
class PrintVilliers():
    def __init__(self):
        self.pama = 'abcdefghijklmnopqrstuvwxyz'
        self.num = {0:1}
    
    def number(self, level):
        to_return = self.pama[level-1]
        if level > 1:
            to_return += str(self.num[level-1])
        to_return += "."
        
        self.num[level] = 1
        self.num[level-1] = self.num[level-1] + 1

        return to_return
    

#------------------------------------------------------------------------
#
# class PrintMeurgey
#   Meurgey_de_Tupigny numbering system
#
#------------------------------------------------------------------------
class PrintMeurgey():
    def __init__(self):
        self.childnum = [""]
    
    def number(self, level):
        if level == 1:
            dash = ""
        else:
            dash = "-"
            if len(self.childnum) < level:
                self.childnum.append(1)
        
        to_return = (ReportUtils.roman(level) + dash +
                     str(self.childnum[level-1]) + ".")

        if level > 1:
            self.childnum[level-1] += 1
        
        return to_return
    

#------------------------------------------------------------------------
#
# Printinfo
#
#------------------------------------------------------------------------
class Printinfo():
    """
    A base class used to help make the individual numbering system classes.
    This class must first be initialized with set_class_vars
    """
    def __init__(self, doc, database, numbering, showmarriage, showdivorce,\
                 name_display):
        #classes
        self._name_display = name_display
        self.doc = doc
        self.database = database
        self.numbering = numbering
        #variables
        self.showmarriage = showmarriage
        self.showdivorce = showdivorce

    def __date_place(self,event):
        if event:
            date = gramps.gen.datehandler.get_date(event)
            place_handle = event.get_place_handle()
            if place_handle:
                place = self.database.get_place_from_handle(
                    place_handle).get_title()
                return("%(event_abbrev)s %(date)s - %(place)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date,
                    'place' : place,
                    })
            else:
                return("%(event_abbrev)s %(date)s" % {
                    'event_abbrev': event.type.get_abbreviation(),
                    'date' : date
                    })
        return ""

    def dump_string(self, person, family=None):
        string = self.__date_place(
                    get_birth_or_fallback(self.database, person)
                    )

        tmp = self.__date_place(get_death_or_fallback(self.database, person))
        if string and tmp:
            string += ", "
        string += tmp
        
        if string:
            string = " (" + string + ")"

        if family and self.showmarriage:
            tmp = self.__date_place(get_marriage_or_fallback(self.database,
                                                              family))
            if tmp:
                string += ", " + tmp

        if family and self.showdivorce:
            tmp = self.__date_place(get_divorce_or_fallback(self.database,
                                                              family))
            if tmp:
                string += ", " + tmp

        self.doc.write_text(string)

    def print_person(self, level, person):
        display_num = self.numbering.number(level)
        self.doc.start_paragraph("DR-Level%d" % min(level, 32), display_num)
        mark = ReportUtils.get_person_mark(self.database, person)
        self.doc.write_text(self._name_display.display(person), mark)
        self.dump_string(person)
        self.doc.end_paragraph()
        return display_num
    
    def print_spouse(self, level, spouse_handle, family_handle):
        #Currently print_spouses is the same for all numbering systems.
        if spouse_handle:
            spouse = self.database.get_person_from_handle(spouse_handle)
            mark = ReportUtils.get_person_mark(self.database, spouse)
            self.doc.start_paragraph("DR-Spouse%d" % min(level, 32))
            name = self._name_display.display(spouse)
            self.doc.write_text(_("sp. %(spouse)s") % {'spouse':name}, mark)
            self.dump_string(spouse, family_handle)
            self.doc.end_paragraph()
        else:
            self.doc.start_paragraph("DR-Spouse%d" % min(level, 32))
            self.doc.write_text(_("sp. %(spouse)s") % {'spouse':'Unknown'})
            self.doc.end_paragraph()

    def print_reference(self, level, person, display_num):
        #Person and their family have already been printed so
        #print reference here
        if person:
            mark = ReportUtils.get_person_mark(self.database, person)
            self.doc.start_paragraph("DR-Spouse%d" % min(level, 32))
            name = self._name_display.display(person)
            self.doc.write_text(_("sp. see  %(reference)s : %(spouse)s") %
                {'reference':display_num, 'spouse':name}, mark)
            self.doc.end_paragraph()

    def print_report_reference(self, level, person, spouse, display_num):
        if person and spouse:
            mark = ReportUtils.get_person_mark(self.database, person)
            self.doc.start_paragraph("DR-Level%d" % min(level, 32))
            pname = self._name_display.display(person)
            sname = self._name_display.display(spouse)
            self.doc.write_text(
                _("see report: %(report)s, ref: %(reference)s : "
                  "%(person)s & %(spouse)s") % \
                 {'report':report_titles[display_num[0]], \
                  'reference':display_num[1], \
                  'person':pname, \
                  'spouse':sname}, mark)
            self.doc.end_paragraph()

#------------------------------------------------------------------------
#
# RecurseDown
#
#------------------------------------------------------------------------
class RecurseDown():
    """
    A simple object to recurse from a person down through their descendants
    
    The arguments are:
    
    max_generations: The max number of generations
    database:  The database object
    objPrint:  A Printinfo derived class that prints person
               information on the report
    """
    def __init__(self, max_generations, database, objPrint, showdups,
                 report_count):
        self.max_generations = max_generations
        self.database = database
        self.objPrint = objPrint
        self.showdups = showdups
        self.report_count = report_count
        self.person_printed = {}
    
    def recurse(self, level, person, curdepth):

        person_handle = person.get_handle()
        display_num = self.objPrint.print_person(level, person)

        if curdepth is None:
            ref_str = display_num
        else:
            ref_str = curdepth + " " + display_num

        if person_handle not in self.person_printed:
            self.person_printed[person_handle] = ref_str
            report_person_ref[person_handle] = (self.report_count, ref_str)

        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)

            spouse_handle = ReportUtils.find_spouse(person, family)

            if not self.showdups and spouse_handle in self.person_printed:
                # Just print a reference
                spouse = self.database.get_person_from_handle(spouse_handle)
                self.objPrint.print_reference(level, spouse,
                        self.person_printed[person_handle])

            else:
                if not self.showdups and self.report_count > 1:
                    if spouse_handle in report_person_ref:
                        self.objPrint.print_spouse(level, spouse_handle, family)
                        childlist = family.get_child_ref_list()[:]
                        if len(childlist) > 0:
                            spouse = \
                                self.database.get_person_from_handle(
                                                                spouse_handle)
                            self.objPrint.print_report_reference(
                                level+1, person,
                                spouse, report_person_ref[spouse_handle])
                        return

                self.objPrint.print_spouse(level, spouse_handle, family)

                if spouse_handle:
                    spouse_num = _("%s sp." % (ref_str))
                    self.person_printed[spouse_handle] = spouse_num
                    report_person_ref[spouse_handle] = \
                        (self.report_count, spouse_num)

                if level >= self.max_generations:
                    continue

                childlist = family.get_child_ref_list()[:]
                for child_ref in childlist:
                    child = self.database.get_person_from_handle(child_ref.ref)
                    self.recurse(level+1, child, ref_str)


#------------------------------------------------------------------------
#
# DescendantBook
#
#------------------------------------------------------------------------
class DescendantBook():
    def __init__(self, dbstate, uistate):
        RunReport(dbstate, uistate, "DescendantBookReport",
            "descendant_book", "Descendant Book",
            "DescendantBookReport", "DescendantBookOptions")

class DescendantBookReport(Report):

    def __init__(self, database, options, user):
        """
        Create the DescendantBook object that produces the report.
        
        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.
        
        gen       - Maximum number of generations to include.
        name_format   - Preferred format to display names
        dups    - Whether to include duplicate descendant trees
        filter_option - Specific report filter to use.
        """

        Report.__init__(self, database, options, user)

        menu = options.menu
        self.user = user
        self.title = _('Descendants Report')
        self.max_generations = menu.get_option_by_name('gen').get_value()
        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = database.get_person_from_gramps_id(pid)
        if (self.center_person == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )
        
        sort = Sort(self.database)
        self.by_birthdate_key = sort.by_birthdate_key
    
        #Initialize the Printinfo class    
        self._showdups = menu.get_option_by_name('dups').get_value()
        numbering = menu.get_option_by_name('numbering').get_value()
        if numbering == "Simple":
            obj = PrintSimple(self._showdups)
        elif numbering == "de Villiers/Pama":
            obj = PrintVilliers()
        elif numbering == "Meurgey de Tupigny":
            obj = PrintMeurgey()
        else:
            raise AttributeError("no such numbering: '%s'" % self.numbering)

        marrs = menu.get_option_by_name('marrs').get_value()
        divs = menu.get_option_by_name('divs').get_value()
        self.filter_option =  menu.get_option_by_name('filter')
        self.filter = self.filter_option.get_filter()

        # Copy the global NameDisplay so that we don't change application defaults.
        self._name_display = copy.deepcopy(global_name_display)
        name_format = menu.get_option_by_name("name_format").get_value()
        if name_format != 0:
            self._name_display.set_default_format(name_format)

        self.objPrint = Printinfo(self.doc, database, obj, marrs, divs,
                                  self._name_display)

    def write_report(self):

        if len(report_titles) > 0:
            report_titles.clear()

        if len(report_person_ref) > 0:
            report_person_ref.clear()

        self.ca = CollectAscendants(self.database, self.user, self.title)
        self.ascendants = self.ca.collect_data(self.filter, self.center_person)

        if len(self.ascendants) > 1:
            self.user.begin_progress(self.title,
                                 _('Writing %s reports...') % \
                                 (len(self.ascendants)), len(self.ascendants))

            # If there is only one item, then no need for a table
            # of contents, however if we have more than one lets generate one
            self.write_toc()

        report_count = 0
        for person_handle in self.ascendants:
            if len(self.ascendants) > 1:
                self.user.step_progress()

            person = self.database.get_person_from_handle(person_handle)

            self.doc.start_paragraph("DR-Title")
            name = self._name_display.display(person)
            if len(self.ascendants) > 1:
                report_count = report_count + 1
                report_titles[report_count] = \
                    _("%s. Descendants of %s") % (report_count, name)
            else:
                report_titles[report_count] = _("Descendants of %s") % name
            mark = IndexMark(report_titles[report_count], INDEX_TYPE_TOC, 1)
            self.doc.write_text(report_titles[report_count], mark)
            self.doc.end_paragraph()

            recurse = RecurseDown(self.max_generations, self.database,
                                self.objPrint, self._showdups, report_count)
            recurse.recurse(1, person, None)

            self.doc.page_break()


        if len(self.ascendants) > 1:
            self.user.end_progress()

    def write_toc(self):
        if len(self.ascendants) <= 1:
            return

        self.doc.start_paragraph("DR-Title")
        title = _("Descendant Report")
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()

        self.doc.start_paragraph("DR-TOC-Title")
        title = _("Table Of Contents")
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()

        report_count = 0
        for asc_handle in self.ascendants:
            person = self.database.get_person_from_handle(asc_handle)
            name = self._name_display.display_name(person.get_primary_name())
            report_count = report_count + 1
            self.doc.start_paragraph("DR-TOC-Detail")
            text = _("%d. %s") % (report_count, name)
            mark = IndexMark(text, INDEX_TYPE_TOC, 2)
            self.doc.write_text(text, mark)
            self.doc.end_paragraph()

        self.doc.page_break()

#------------------------------------------------------------------------
#
# Descendant Book Options
#
#------------------------------------------------------------------------
class DescendantBookOptions(MenuReportOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):

        self.__db = dbase
        self.__pid = None
        self.__filter = None
        MenuReportOptions.__init__(self, name, dbase)
        
    def add_menu_options(self, menu):
        category_name = _("Report Options")

        self.__filter = FilterOption(_("Filter"), 0)
        self.__filter.set_help(
               _("Select filter to restrict people that appear in the report"))
        menu.add_option(category_name, "filter", self.__filter)
        
        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the report"))
        menu.add_option(category_name, "pid", self.__pid)
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
        menu.add_option(category_name, "name_format", name_format)

        numbering = EnumeratedListOption(_("Numbering system"), "Simple")
        numbering.set_items([
                ("Simple",      _("Simple numbering")), 
                ("de Villiers/Pama", _("de Villiers/Pama numbering")), 
                ("Meurgey de Tupigny", _("Meurgey de Tupigny numbering"))])
        numbering.set_help(_("The numbering system to be used"))
        menu.add_option(category_name, "numbering", numbering)
        
        gen = NumberOption(_("Generations"), 10, 1, 15)
        gen.set_help(_("The number of generations to include in the report"))
        menu.add_option(category_name, "gen", gen)

        marrs = BooleanOption(_('Show marriage info'), False)
        marrs.set_help(_("Whether to show marriage information in the report."))
        menu.add_option(category_name, "marrs", marrs)

        divs = BooleanOption(_('Show divorce info'), False)
        divs.set_help(_("Whether to show divorce information in the report."))
        menu.add_option(category_name, "divs", divs)

        dups = BooleanOption(_('Show duplicate trees'), True)
        dups.set_help(_("Whether to show duplicate family trees in the report."))
        menu.add_option(category_name, "dups", dups)

    def __update_filters(self):
        """
        Update the filter list based on the selected person
        """
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        filter_list = ReportUtils.get_person_filters(person, False)
        self.__filter.set_filters(filter_list)


    def make_default_style(self, default_style):
        """Make the default output style for the Descendant Report."""
        f = FontStyle()
        f.set(face=FONT_SANS_SERIF, size=12, bold=1)
        p = ParagraphStyle()
        p.set_header_level(1)
        p.set_bottom_border(1)
        p.set_top_margin(ReportUtils.pt2cm(3))
        p.set_bottom_margin(ReportUtils.pt2cm(3))
        p.set_font(f)
        p.set_description(_("The style used for the title of the page."))
        default_style.add_paragraph_style("DR-Title", p)

        f = FontStyle()
        f.set(face=FONT_SANS_SERIF, size=12, italic=1)
        p = ParagraphStyle()
        p.set_font(f)
        p.set_header_level(2)
        p.set_top_margin(ReportUtils.pt2cm(3))
        p.set_bottom_margin(ReportUtils.pt2cm(3))
        p.set_description(_('The style used for the table of contents header.'))
        default_style.add_paragraph_style("DR-TOC-Title", p)

        f = FontStyle()
        f.set_size(10)
        p = ParagraphStyle()
        p.set_font(f)
        p.set_top_margin(0.25)
        p.set_bottom_margin(0.25)
        p.set_first_indent(1.0)
        p.set_description(_("The style used for the table of contents detail."))
        default_style.add_paragraph_style("DR-TOC-Detail", p)

        f = FontStyle()
        f.set_size(10)
        for i in range(1, 33):
            p = ParagraphStyle()
            p.set_font(f)
            p.set_top_margin(ReportUtils.pt2cm(f.get_size()*0.125))
            p.set_bottom_margin(ReportUtils.pt2cm(f.get_size()*0.125))
            p.set_first_indent(-0.8)
            p.set_left_margin(min(10.0, float(i-0.5)))
            p.set_description(_("The style used for the "
                                "level %d display.") % i)
            default_style.add_paragraph_style("DR-Level%d" % min(i, 32), p)

            p = ParagraphStyle()
            p.set_font(f)
            p.set_top_margin(ReportUtils.pt2cm(f.get_size()*0.125))
            p.set_bottom_margin(ReportUtils.pt2cm(f.get_size()*0.125))
            p.set_left_margin(min(10.0, float(i-0.5)))
            p.set_description(_("The style used for the "
                                "spouse level %d display.") % i)
            default_style.add_paragraph_style("DR-Spouse%d" % min(i, 32), p)
