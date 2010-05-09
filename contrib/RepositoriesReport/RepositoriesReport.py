#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2006-2007  Alex Roitman
# Copyright (C) 2007-2009  Jerome Rapinat
# Copyright (C) 2008-2009  Gary Burton
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
Display Sources related to repositories
"""

#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------

from gen.plug.report import Report
from gen.plug.report import CATEGORY_TEXT
from gui.plug.report import MenuReportOptions
import gen.plug.report.utils as ReportUtils

from TransUtils import get_addon_translator
from gen.plug.docgen import (IndexMark, FontStyle, ParagraphStyle, 
                             FONT_SANS_SERIF, FONT_SERIF, 
                             INDEX_TYPE_TOC, PARA_ALIGN_CENTER)

_ = get_addon_translator(__file__).ugettext

class RepositoryReport(Report):
    """
    Repository Report class
    """
    def __init__(self, database, options_class):
        """
        Create the RepositoryReport object produces the Repositories report.
        
        The arguments are:

        database        - the GRAMPS database instance
        options_class   - instance of the Options class for this report

        This report needs the following parameters (class variables)
        that come in the options class.
        
        repositories          - List of repositories to report on.

        """

        Report.__init__(self, database, options_class)

    def write_report(self):
        """
        The routine the actually creates the report. At this point, the document
        is opened and ready for writing.
        """
        # Write the title line. Set in INDEX marker so that this section will be
        # identified as a major category if this is included in a Book report.

        title = _("Repositories Report")
        mark = IndexMark(title, INDEX_TYPE_TOC, 1)
        self.doc.start_paragraph("REPO-ReportTitle")
        self.doc.write_text(title, mark)
        self.doc.end_paragraph()
        self.__write_all_repositories()
        
    def __write_all_repositories(self):
        """
        This procedure writes out all repositories.
        """
        rlist = self.database.get_repository_handles()
        for handle in rlist:
            self.__write_repository(handle)
            self.__write_referenced_sources(handle)

    def __write_repository(self, handle):
        """
        This procedure writes out the details of a single repository
        """
        repository = self.database.get_repository_from_handle(handle)
        self.doc.start_paragraph("REPO-RepositoryTitle")
        self.doc.write_text(("%(repository)s (%(type)s)") % 
                                {'repository' : repository.get_name(),
                                'type' : repository.get_type()})
        self.doc.end_paragraph()

    def __write_referenced_sources(self, handle):
        """
        This procedure writes out each of the sources related to the repository
        """
        repository = self.database.get_repository_from_handle(handle)
        repository_handles = [handle for (object_type, handle) in \
                         self.database.find_backlink_handles(handle,['Source'])]

        source_nbr = 0

        for source_handle in repository_handles:
            src = self.database.get_source_from_handle(source_handle)
            # Get the list of references from this source to our repo
            # (can be more than one, technically)
            for reporef in src.get_reporef_list():
                if reporef.ref == repository.handle:
                    source_nbr += 1
                    self.doc.start_paragraph("REPO-Section")
                    title = (("%(nbr)s. %(name)s (%(type)s) : %(call)s") % 
                                {'nbr' : source_nbr,
                                 'name' : src.get_title(),
                                 'type' : str(reporef.get_media_type()),
                                 'call' : reporef.get_call_number()})
                    self.doc.write_text(title)
                    self.doc.end_paragraph()
    
#------------------------------------------------------------------------
#
# RepositoryOptions
#
#------------------------------------------------------------------------
class RepositoryOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)
        
    def add_menu_options(self, menu):
        """
        Add options to the menu for the place report.
        """
        category_name = _("Report Options")

    def make_default_style(self, default_style):
        """
        Make the default output style for the Place report.
        """
        self.default_style = default_style
        self.__report_title_style()
        self.__repository_title_style()
        self.__section_style()

    def __report_title_style(self):
        """
        Define the style used for the report title
        """
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=20, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_bottom_border(1)
        para.set_top_margin(ReportUtils.pt2cm(12))
        para.set_bottom_margin(ReportUtils.pt2cm(12))
        para.set_alignment(PARA_ALIGN_CENTER)       
        para.set_description(_('The style used for the title of the report.'))
        self.default_style.add_paragraph_style("REPO-ReportTitle", para)

    def __repository_title_style(self):
        """
        Define the style used for the repository title
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=14, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=-1.5, lmargin=1.5)
        para.set_top_margin(ReportUtils.pt2cm(10))
        para.set_bottom_margin(ReportUtils.pt2cm(10))        
        para.set_description(_('The style used for repository title.'))
        self.default_style.add_paragraph_style("REPO-RepositoryTitle", para)

    def __section_style(self):
        """
        Define the style used for each section
        """
        font = FontStyle()
        font.set(face=FONT_SERIF, size=10, italic=0, bold=0)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=-1.5, lmargin=1.5)
        para.set_top_margin(ReportUtils.pt2cm(10))
        para.set_bottom_margin(ReportUtils.pt2cm(10))       
        para.set_description(_('The style used for each section.'))
        self.default_style.add_paragraph_style("REPO-Section", para)
