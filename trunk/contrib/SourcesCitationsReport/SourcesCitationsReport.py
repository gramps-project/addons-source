#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
# Copyright (C) 2008       Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2012       Hans Ulrich Frink
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
# Version 3.4
# $Id: SourcesCitationsReport.py 2012-12-30 Frink hansulrich.frink@gmail.com $

"""
Reports/Text Report.

Developed for gramps 3.4.2.1 under win 7 64bit

This is my first contribution to gramps, as well as my first python module,
so the programming style may in some way be unusual. Thanks to Enno Borgsteede
and Tim Lyons as well as other members of gramps dev for help 

PLEASE FEEL FREE TO CORRECT AND TEST.

This report lists all the citations and their notes in the database. so it 
is possible to have all the copies made from e.g. parish books together grouped 
by source and ordered by citation.page.

I needed such a report after I changed recording notes and media with the
citations and no longer with the sources.

works well in pdf, text and odf Format. The latter contains TOC which are also
accepted by ms office 2012 

Changelog:

Version 2.5:
- sources are sorted by source.author+title+publ+abbrev
- no German non translatables
- added Filter cf. PlaceReport.py
- changed citasource from gramps_id to citation rsp. source

Version 3.3:
- constructing dic directly
- or function
- sorting direct 
- Stylesheet in Options

Version 3.4:
- added .lower to sortfunctions to sources and to citation

Version 3.5: 
- get translation work
- include Persons names and gramps_id cited in the notes.

next steps:

- have an index on Persons  
- have footer        

"""

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
#import posixpath
import time
from collections import defaultdict
from gen.ggettext import gettext as _

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
import gen.lib
from gen.plug.menu import StringOption, MediaOption, NumberOption
from gen.plug.menu import FilterOption, PlaceListOption, EnumeratedListOption, \
                          BooleanOption
from gen.plug.report import Report
from gen.plug.report import MenuReportOptions
from gen.plug.report import utils as ReportUtils

from gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle, TableStyle,
                            TableCellStyle, FONT_SANS_SERIF, FONT_SERIF, 
                            INDEX_TYPE_TOC, INDEX_TYPE_ALP, PARA_ALIGN_CENTER)                    
                    
from Utils import media_path_full
import DateHandler

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).gettext

#------------------------------------------------------------------------
#
# SourcesCitationsReport
#
#------------------------------------------------------------------------
class SourcesCitationsReport(Report):
    """
    This report produces a summary of the objects in the database.
    """
    def __init__(self, database, options, user):
        """
        Create the SourceReport object that produces the report.
        
        The arguments are:

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gen.user.User() instance

        This report needs the following parameters (class variables)
        that come in the options class.
        
        Sources          - List of places to report on.
        """

        Report.__init__(self, database, options, user)
        self.__db = database
       
        menu = options.menu
        self.title_string = menu.get_option_by_name('title').get_value()
        self.subtitle_string = menu.get_option_by_name('subtitle').get_value()
        self.footer_string = menu.get_option_by_name('footer').get_value()
        self.showperson = menu.get_option_by_name('showperson').get_value()

        
        filter_option = menu.get_option_by_name('filter')
        self.filter = filter_option.get_filter()
#        self.sort = Sort.Sort(self.database)

        if self.filter.get_name() != '':
            # Use the selected filter to provide a list of source handles
            sourcefilterlist = self.__db.iter_source_handles()
            self.source_handles = self.filter.apply(self.__db, sourcefilterlist)
        else:
            self.source_handles = self.__db.get_source_handles()

    def write_report(self):
        """
        Overridden function to generate the report.
        """
        self.doc.start_paragraph("SRC-ReportTitle")
        title = self.title_string
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)  
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()
        
        self.doc.start_paragraph("SRC-ReportTitle")
        title = self.subtitle_string
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)  
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()
        
        self.listeventref()
        
        
    def _formatlocal_source_text(self, source):
        if not source: return
    
        src_txt = ""
        
        if source.get_author():
            src_txt += source.get_author()
        
        if source.get_title():
            if src_txt:
                src_txt += ", "
            src_txt += '"%s"' % source.get_title()
            
        if source.get_publication_info():
            if src_txt:
                src_txt += ", "
            src_txt += source.get_publication_info()
            
        if source.get_abbreviation():
            if src_txt:
                src_txt += ", "
            src_txt += "(%s)" % source.get_abbreviation()
            
        return src_txt
        
    def listeventref(self):
    
        sc = {'source': 'S_ID',
              'citalist': 'C_ID' }
        stc = {}      
        citation_without_notes = 0
        EMPTY = " "

        def toYear(date):
            yeartext = date.get_year()
            return yeartext
 
     # build citasource dictionary  and cl list 
        
        sc = defaultdict(list)
        cl = []
        i=1
        for ci in self.__db.iter_citations():
            if ci.source_handle in self.source_handles:
                sc[ci.source_handle].append(ci.handle)
                cl.append(ci.handle)

        # build citations - event dic                       xy
        #(a,b): set([('Citation', 'c4a8c46041e08799b17')]) 
        # event: c4a8c4f95b01e38564a event: Taufe
        ci = defaultdict(list)
        for ev in self.__db.iter_events():
            refhandlelist = ev.get_referenced_handles()   
            for (a,b) in refhandlelist:
                if a == 'Citation':
                    if b in cl:                    #!
                        ci[b].append(ev.handle)

        # build eventpersonrole dictionary
        # event: c4a8c4f95b01e38564a event: Taufe
        refhandlelist =[]
        pedic ={}
        pedic = defaultdict(set)

        for pe in self.__db.get_person_handles():
            for eventref in self.__db.get_person_from_handle(pe).event_ref_list:
                pedic[eventref.ref].add((eventref.get_role(),pe))


        # build eventfamily dictionary
        # event: c4a8c4f95b01e38564a event: Taufe
        refhandlelist =[]
        fedic ={}
        fedic = defaultdict(set)

        for fh in self.__db.get_family_handles():
            for eventref in self.__db.get_family_from_handle(fh).event_ref_list:
                family = self.__db.get_family_from_handle(eventref.ref)
                fedic[eventref.ref].add((self.__db.get_family_from_handle(fh).mother_handle,self.__db.get_family_from_handle(fh).father_handle,fh ))


        #source
        skeys = sc.keys()
        skeys.sort(key=str.lower)
        
        for s in skeys:
            self.doc.start_paragraph("SRC-SourceTitle")
            self.doc.write_text(self._formatlocal_source_text(self.__db.get_source_from_handle(s)))
            self.doc.end_paragraph()       
            
            self.doc.start_paragraph("SRC-SourceDetails")
            self.doc.write_text(_("   key: %s") %
                                self.__db.get_source_from_handle(s).gramps_id) 
            self.doc.end_paragraph()  
    
            i = 1
            ckeys = sc[s]
            ckeys.sort(key=lambda x:self.__db.get_citation_from_handle(x).page)
            for c in ckeys:                                     
                       # c contains citationhandles
                self.doc.start_paragraph("SRC-CitationTitle")
                self.doc.write_text(_("%d") %
                                    i)  
                self.doc.write_text(_("  %s") %
                                    self.__db.get_citation_from_handle(c).page)
                self.doc.write_text(_("   Anno %s - ") %
                                    toYear(self.__db.get_citation_from_handle(c).date))  
                self.doc.end_paragraph()
                # note
                for notehandle in self.__db.get_citation_from_handle(c).get_note_list():
                    self.doc.start_paragraph("SRC-SourceDetails")
                    self.doc.write_text(_("   Type: %s") %
                                        self.__db.get_note_from_handle(notehandle).type) 
                    self.doc.write_text(_("   N-ID: %s") %
                                        self.__db.get_note_from_handle(notehandle).gramps_id) 
                    self.doc.end_paragraph()

                    self.doc.start_paragraph("SRC-SourceDetails")
                    self.doc.end_paragraph()

                    self.doc.start_paragraph("SRC-SourceDetails")
                    self.doc.write_text(_("   %s") %
                                        self.__db.get_note_from_handle(notehandle).text) 
                    self.doc.end_paragraph()

                    # event as table
                    for e in ci[c]:
                        self.doc.start_paragraph("SRC-SourceDetails")
                        self.doc.end_paragraph()

                       # if it is a familyevent
                        for k in fedic.keys():                         
                            if e == k:
                                for (a,b,c) in fedic[k]:
                                    self.doc.start_paragraph("SRC-SourceDetails")
                                    self.doc.write_text(_("%s") %
                                    self.__db.get_event_from_handle(e).get_type())
                                    self.doc.write_text(_("   ( %s )") %
                                                        self.__db.get_event_from_handle(e).gramps_id)

                                    self.doc.write_text(_("   Eheleute: %s ") %  
                                                        self.__db.get_person_from_handle(b).primary_name.get_name()) 
                                    self.doc.write_text(_("and %s ") % 
                                                        self.__db.get_person_from_handle(a).primary_name.get_name())
                                    self.doc.end_paragraph()

                        for (a,b) in pedic[e]:
                            if a.is_primary():   
                                self.doc.start_paragraph("SRC-SourceDetails")
                                self.doc.write_text(_("%s") %
                                              self.__db.get_event_from_handle(e).get_type())
                                self.doc.write_text(_("   ( %s )") %
                                              self.__db.get_event_from_handle(e).gramps_id)
                                self.doc.write_text(_(" %s") %
                                                self.__db.get_person_from_handle(b).primary_name.get_name()) 
                                self.doc.end_paragraph()
                        
                        if self.showperson:
                            liste = pedic[e].copy() 
                            if len(liste)>0:
                                self.doc.start_table("EventTable", "SRC-EventTable")
                                column_titles = [_("Person"), _("ID"),
                                                 _("Role")] 
                                self.doc.start_row()
                                for title in column_titles:
                                    self.doc.start_cell("SRC-TableColumn")
                                    self.doc.start_paragraph("SRC-ColumnTitle")
                                    self.doc.write_text(title)
                                    self.doc.end_paragraph()
                                    self.doc.end_cell()
                                self.doc.end_row()                 
                      
                                for (a,b) in liste:
                                     self.doc.start_row()
                                     self.doc.start_cell("SRC-Cell")
                                     self.doc.start_paragraph("SRC-SourceDetails")
                                     self.doc.write_text(_("%s") %
                                                    self.__db.get_person_from_handle(b).primary_name.get_name())
                                     self.doc.end_paragraph()
                                     self.doc.end_cell()
                                     self.doc.start_cell("SRC-Cell")
                                     self.doc.start_paragraph("SRC-SourceDetails")
                                     self.doc.write_text(_("%s") %
                                                  self.__db.get_person_from_handle(b).gramps_id)
                                     self.doc.end_paragraph()
                                     self.doc.end_cell()
                                     self.doc.start_cell("SRC-Cell")
                                     self.doc.start_paragraph("SRC-SourceDetails")
                                     self.doc.write_text(_("%s") %
                                                         a)
                                     self.doc.end_paragraph()  
                                     self.doc.end_cell()
                                     self.doc.end_row()
                                self.doc.end_table()
                i+=1
                

#------------------------------------------------------------------------
#
# SourcesCitationsOptions
#
#------------------------------------------------------------------------
class SourcesCitationsOptions(MenuReportOptions):
    """
    SourcesCitationsAndPersonsOptions provides the options 
    for the SourcesCitationsAndPersonsReport.
    """
    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

        
     
    def add_menu_options(self, menu):
        """ Add the options for this report """
        category_name = _("Report Options")
        
        title = StringOption(_('book|Title'), _('Title of the Book') )
        title.set_help(_("Title string for the book."))
        menu.add_option(category_name, "title", title)
        
        subtitle = StringOption(_('Subtitle'), _('Subtitle of the Book') )
        subtitle.set_help(_("Subtitle string for the book."))
        menu.add_option(category_name, "subtitle", subtitle)
        
        dateinfo = time.localtime(time.time())
        #rname = self.__db.get_researcher().get_name()
        rname = "researcher name"
 
        footer_string = _('Copyright %(year)d %(name)s') % {
            'year' : dateinfo[0], 'name' : rname }
        footer = StringOption(_('Footer'), footer_string )
        footer.set_help(_("Footer string for the page."))
        menu.add_option(category_name, "footer", footer)
        
        # Reload filters to pick any new ones
        CustomFilters = None
        from Filters import CustomFilters, GenericFilter

        opt = FilterOption(_("Select using filter"), 0)
        opt.set_help(_("Select places using a filter"))
        filter_list = []
        filter_list.append(GenericFilter())
        filter_list.extend(CustomFilters.get_filters('Source'))
        opt.set_filters(filter_list)
        menu.add_option(category_name, "filter", opt)
        
        showperson = BooleanOption(_("Show persons"), True)
        showperson.set_help(_("Whether to show events and persons mentioned in the note"))
        menu.add_option(category_name, "showperson", showperson)

    def make_default_style(self, default_style):
        """
        Make the default output style for the Place report.
        """
        self.default_style = default_style
        self.__report_title_style()
        self.__source_title_style()
        self.__source_details_style()
        self.__citation_title_style()
        self.__column_title_style()
        self.__section_style()
        self.__event_table_style()
        self.__details_style()
        self.__cell_style()
        self.__table_column_style()

    def __report_title_style(self):
        """
        Define the style used for the report title
        """
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=16, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(PARA_ALIGN_CENTER)       
        para.set_description(_('The style used for the title of the report.'))
        self.default_style.add_paragraph_style("SRC-ReportTitle", para)

    def __source_title_style(self):
        """
        Define the style used for the source title
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set(first_indent=0.0, lmargin=0.0)
        para.set_top_margin(0.75)
        para.set_bottom_margin(0.25)        
        para.set_description(_('The style used for source title.'))
        self.default_style.add_paragraph_style("SRC-SourceTitle", para)
        
    def __citation_title_style(self):
        """
        Define the style used for the citation title
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(3)
        para.set(first_indent=0.0, lmargin=0.0)
        para.set_top_margin(0.75)
        para.set_bottom_margin(0.0)        
        para.set_description(_('The style used for citation title.'))
        self.default_style.add_paragraph_style("SRC-CitationTitle", para)

    def __source_details_style(self):
        """
        Define the style used for the place details
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=0.0)
        para.set_description(_('The style used for Source details.'))
        self.default_style.add_paragraph_style("SRC-SourceDetails", para)

    def __column_title_style(self):
        """
        Define the style used for the event table column title
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=10, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=0.0)
        para.set_description(_('The style used for a column title.'))
        self.default_style.add_paragraph_style("SRC-ColumnTitle", para)

    def __section_style(self):
        """
        Define the style used for each section
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=10, italic=0, bold=0)
        para = ParagraphStyle()
        para.set_font(font)
#        para.set(first_indent=-1.5, lmargin=1.5)
        para.set(first_indent=0.0, lmargin=0.0)

        para.set_top_margin(0.5)
        para.set_bottom_margin(0.25)        
        para.set_description(_('The style used for each section.'))
        self.default_style.add_paragraph_style("SRC-Section", para)

    def __event_table_style(self):
        """
        Define the style used for event table
        """
        table = TableStyle()
        table.set_width(100)
        table.set_columns(3)
        table.set_column_width(0, 35)
        table.set_column_width(1, 15)
        table.set_column_width(2, 35)

        self.default_style.add_table_style("SRC-EventTable", table)
        table.set_width(100)
        table.set_columns(3)
        table.set_column_width(0, 35)
        table.set_column_width(1, 15)
        table.set_column_width(2, 35)

        self.default_style.add_table_style("SRC-PersonTable", table)

    def __details_style(self):
        """
        Define the style used for person and event details
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The style used for event and person details.'))
        self.default_style.add_paragraph_style("PLC-Details", para)

    def __cell_style(self):
        """
        Define the style used for cells in the event table
        """
        cell = TableCellStyle()
        self.default_style.add_cell_style("SRC-Cell", cell)

    def __table_column_style(self):
        """
        Define the style used for event table columns
        """
        cell = TableCellStyle()
        cell.set_bottom_border(1)
        self.default_style.add_cell_style('SRC-TableColumn', cell)

      