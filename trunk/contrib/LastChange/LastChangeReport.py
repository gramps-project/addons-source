#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010      Jakim Friant
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

# $Id$

"""Reports/Text Reports/Last Change Report"""

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
import time

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
import gen.datehandler
from gen.errors import ReportError
from gen.plug import docgen
from gen.plug.menu import BooleanListOption
from gen.plug.report import Report
from gen.plug.report import utils as ReportUtils
from gen.plug.report import MenuReportOptions
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
from gen.lib import Date

_UNKNOWN_FAMILY = "*unknown*"

class LastChangeReport(Report):
    """
    Generate a list of the last records to be changed in the current database.

    The arguments are:
    
        database        - the GRAMPS database instance
        options_class   - instance of the Options class for this report
        user            - a gen.user.User() instance
    
    """

    def __init__(self, database, options_class, user):
        Report.__init__(self, database, options_class, user)
        menu_option = options_class.menu.get_option_by_name('what_types')
        self.what_types = menu_option.get_selected()
        # TODO: handle an empty selection of what_types
        if len(self.what_types) == 0:
            raise ReportError(_('Last Change Report'),
                              _('You must select at least one type of record.'))


    def _getTimestamp(self, person_handle):
        timestamp = self.database.person_map.get(str(person_handle))[17]
        return timestamp

    def _getFamilyTimestamp(self, family_handle):
        timestamp = self.database.get_family_from_handle(family_handle).change
        return timestamp

    def _getEventTimestamp(self, event_handle):
        timestamp = self.database.get_event_from_handle(event_handle).change
        return timestamp

    def _getPlaceTimestamp(self, place_handle):
        timestamp = self.database.get_place_from_handle(place_handle).change
        return timestamp

    def _getMediaTimestamp(self, media_handle):
        timestamp = self.database.get_object_from_handle(media_handle).change
        return timestamp

    def _getSourceTimestamp(self, source_handle):
        timestamp = self.database.get_source_from_handle(source_handle).change
        return timestamp

    def write_report(self):
         self.doc.start_paragraph("LCR-Title")
         self.doc.write_text(_("Last Change Report"))
         self.doc.end_paragraph()

         if _('People') in self.what_types:
             self.write_person()
         if _('Families') in self.what_types:
             self.write_family()
         if _('Events') in self.what_types:
             self.write_event()
         if _('Places') in self.what_types:
             self.write_place()
         if _('Media') in self.what_types:
             self.write_media()
         if _('Sources') in self.what_types:
             self.write_sources()
    
    def _table_begin(self, title, table_name):
            self.doc.start_paragraph('LCR-SecHeader')
            self.doc.write_text(title)
            self.doc.end_paragraph()

            self.doc.start_table(table_name, 'LCR-Table')
            self.counter = 0

    def _table_header(self, *args):
        """Create a header row with a column for each string argument."""
        self.doc.start_row()
        columns = ("",) + args
        for header_text in columns:
            self.doc.start_cell('LCR-TableCell')
            self.doc.start_paragraph('LCR-Normal-Bold')
            self.doc.write_text(header_text)
            self.doc.end_paragraph()
            self.doc.end_cell()
        self.doc.end_row()

    def _table_row(self, *args):
        """Create a row with a table cell for each argument passed in.

        A counter is automatically included.

        """
        self.counter += 1
        columns = ("%d" % self.counter,) + args
        self.doc.start_row()
        for text_out in columns:
            self.doc.start_cell('LCR-TableCell')
            self.doc.start_paragraph('LCR-Normal')
            self.doc.write_text(text_out)
            self.doc.end_paragraph()
            self.doc.end_cell()
        self.doc.end_row()

    def _table_end(self):
        """For now this simply closes the table"""
        self.doc.end_table()

    def _convert_date(self, date_in):
        """Convert the change date to the preferred date format and return a string"""
        change_date = Date()
        change_date.set_yr_mon_day(*time.localtime(date_in)[0:3])
        return gen.datehandler.displayer.display(change_date)

    def write_person(self):
        handles = sorted(self.database.get_person_handles(), key=self._getTimestamp)

        if len(handles) > 0:
            self._table_begin(_('People Changed'), 'PersonTable')
            self._table_header(_('ID'), _('Person'), _('Changed On'))

            for handle in reversed(handles[-10:]):
                person = self.database.get_person_from_handle(handle)
                if person is not None:
                    self._table_row("%s" % person.gramps_id,
                                    person.get_primary_name().get_name(),
                                    self._convert_date(person.change))
            self._table_end()

    def write_family(self):
        handles = sorted(self.database.get_family_handles(), key=self._getFamilyTimestamp)

        if len(handles) > 0:
            self._table_begin(_('Families Changed'), 'FamilyTable')
            self._table_header(_('ID'), _('Family Surname'), _('Changed On'))

            for handle in reversed(handles[-10:]):
                family = self.database.get_family_from_handle(handle)
                if family is not None:
                    father_handle = family.get_father_handle()
                    if father_handle is not None:
                        father = self.database.get_person_from_handle(father_handle)
                        father_surname = father.get_primary_name().get_surname()
                    else:
                        father_surname = _UNKNOWN_FAMILY
                    mother_handle = family.get_mother_handle()
                    if mother_handle is not None:
                        mother = self.database.get_person_from_handle(mother_handle)
                        mother_surname = mother.get_primary_name().get_surname()
                    else:
                        mother_surname = _UNKNOWN_FAMILY
                    family_name = _("%s and %s") % (father_surname, mother_surname)

                    self._table_row(family.gramps_id,
                                    family_name,
                                    self._convert_date(family.change))
            self._table_end()

    def write_event(self):
        handles = sorted(self.database.get_event_handles(), key=self._getEventTimestamp)

        # TODO: need the event date and type to be included in the description line
        
        if len(handles) > 0:
            self._table_begin(_('Events Changed'), 'EventTable')
            self._table_header(_('ID'), _('Event'), _('Changed On'))

            for handle in reversed(handles[-10:]):
                event = self.database.get_event_from_handle(handle)
                if event is not None:
                    evt_type = event.get_type()
                    if event.description != "":
                        desc_out = "%s, %s" % (evt_type, event.description)
                    else:
                        desc_out = str(evt_type)
                    self._table_row(event.gramps_id,
                                    desc_out,
                                    self._convert_date(event.change))
            self._table_end()

    def write_place(self):
        handles = sorted(self.database.get_place_handles(), key=self._getPlaceTimestamp)

        if len(handles) > 0:
            self._table_begin(_("Places Changed"), "PlaceTable")
            self._table_header(_('ID'), _('Place'), _('Changed On'))

            for handle in reversed(handles[-10:]):
                place = self.database.get_place_from_handle(handle)
                if place is not None:
                    self._table_row(place.gramps_id,
                                    place.get_title(),
                                    self._convert_date(place.change))
            self._table_end()

    def write_media(self):
        handles = sorted(self.database.get_media_object_handles(), key=self._getMediaTimestamp)

        if len(handles) > 0:
            self._table_begin(_("Media Changed"), "MediaTable")
            self._table_header(_('ID'), _('Path'), _('Changed On'))

            for handle in reversed(handles[-10:]):
                media = self.database.get_object_from_handle(handle)
                if media is not None:
                    self._table_row(media.gramps_id,
                                    media.get_description(),
                                    #media.get_path(),
                                    self._convert_date(media.change))
            self._table_end()

    def write_sources(self):
        handles = sorted(self.database.get_source_handles(), key=self._getSourceTimestamp)

        if len(handles) > 0:
            self._table_begin(_("Sources Changed"), "SourcesTable")
            self._table_header(_('ID'), _('Title'), _('Changed On'))

            for handle in reversed(handles[-10:]):
                source_obj = self.database.get_source_from_handle(handle)
                if source_obj is not None:
                    self._table_row(source_obj.gramps_id,
                                    source_obj.get_title(),
                                    self._convert_date(source_obj.change))
            self._table_end()
            

class LastChangeOptions(MenuReportOptions):
    def __init__(self, name, database):
        """Initialize the parent class"""
        MenuReportOptions.__init__(self, name, database)

    def add_menu_options(self, menu):
        """
        Add options to the menu for this report.
        """
        category_name = _("Report Options")
        what_types = BooleanListOption(_('Select From'))
        what_types.add_button(_('People'), True)
        what_types.add_button(_('Families'), False)
        what_types.add_button(_('Places'), False)
        what_types.add_button(_('Events'), False)
        what_types.add_button(_('Media'), False)
        what_types.add_button(_('Sources'), False)
        menu.add_option(category_name, "what_types", what_types)

    def make_default_style(self, default_style):
        # this is for the page header
        font = docgen.FontStyle()
        font.set_size(18)
        font.set_type_face(docgen.FONT_SANS_SERIF)
        font.set_bold(True)

        para = docgen.ParagraphStyle()
        para.set_header_level(1)
        para.set_alignment(docgen.PARA_ALIGN_CENTER)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_font(font)
        para.set_description(_('The style used for the title of the page.'))

        default_style.add_paragraph_style('LCR-Title',para)

        # this is for the section headers
        font = docgen.FontStyle()
        font.set_size(14)
        font.set_type_face(docgen.FONT_SANS_SERIF)
        font.set_bold(True)

        para = docgen.ParagraphStyle()
        para.set_header_level(2)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_font(font)
        para.set_description(_('The style used for the section headers.'))

        default_style.add_paragraph_style('LCR-SecHeader',para)

        font = docgen.FontStyle()
        font.set_size(12)
        font.set_type_face(docgen.FONT_SERIF)

        para = docgen.ParagraphStyle()
        para.set_font(font)
        para.set_description(_('The style used for normal text'))

        default_style.add_paragraph_style('LCR-Normal',para)

        font = docgen.FontStyle()
        font.set_size(12)
        font.set_bold(True)
        para = docgen.ParagraphStyle()
        para.set(first_indent=-0.75, lmargin=.75)
        para.set_font(font)
        para.set_top_margin(ReportUtils.pt2cm(3))
        para.set_bottom_margin(ReportUtils.pt2cm(3))
        para.set_description(_('The basic style used for table headings.'))
        default_style.add_paragraph_style("LCR-Normal-Bold", para)

        #Table Styles
        cell = docgen.TableCellStyle()
        default_style.add_cell_style('LCR-TableCell', cell)

        cell = docgen.TableCellStyle()
        cell.set_bottom_border(1)
        default_style.add_cell_style('LCR-BorderCell', cell)

        table = docgen.TableStyle()
        table.set_width(100)
        table.set_columns(4)
        table.set_column_width(0, 5)
        table.set_column_width(1, 15)
        table.set_column_width(2, 50)
        table.set_column_width(3, 30)
        default_style.add_table_style('LCR-Table', table)
