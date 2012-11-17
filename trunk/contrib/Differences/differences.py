# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2012       Doug Blank <doug.blank@gmail.com>
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
# $Id: $
#

#------------------------------------------------------------------------
#
# python modules
#
#------------------------------------------------------------------------
import copy
import datetime, time

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
from gramps.gen.ggettext import gettext as _
from gramps.gen.ggettext import ngettext
from gramps.gen.display.name import displayer as global_name_display
from gramps.gen.plug.docgen import (FontStyle, ParagraphStyle, GraphicsStyle,
                             FONT_SERIF, PARA_ALIGN_RIGHT,
                             PARA_ALIGN_LEFT, PARA_ALIGN_CENTER,
                             TableStyle, TableCellStyle, FONT_SANS_SERIF)
from gramps.gen.plug.menu import (BooleanOption, DestinationOption, StringOption)
from gramps.gen.plug.report import Report
from gramps.gen.plug.report import utils as ReportUtils
from gramps.gen.plug.report import MenuReportOptions
from gramps.gen.merge.diff import diff_dbs, import_as_dict
from gramps.gen.simple import SimpleAccess

#------------------------------------------------------------------------
#
# Local Functions
#
#------------------------------------------------------------------------
def start_list(doc, text, heading1, heading2):
    doc.start_row()
    doc.start_cell('DIFF-TableCell')
    doc.start_paragraph('DIFF-TableHeading')
    doc.write_text(text)
    doc.end_paragraph()
    doc.end_cell()
    if heading1:
        doc.start_cell('DIFF-TableCell')
        doc.start_paragraph('DIFF-TableHeading')
        doc.write_text(heading1)
        doc.end_paragraph()
        doc.end_cell()
    if heading2:
        doc.start_cell('DIFF-TableCell')
        doc.start_paragraph('DIFF-TableHeading')
        doc.write_text(heading2)
        doc.end_paragraph()
        doc.end_cell()
    doc.end_row()

def report_details(doc, path, diff1, diff2):
    if path.endswith(".change"):
        diff1 = todate(diff1)
        diff2 = todate(diff2)
    if diff1 == None:
        diff1 = "" # FIXME: use default
    else:
        diff1 = str(diff1)
    if diff2 == None:
        diff2 = "" # FIXME: use default
    else:
        diff2 = str(diff2)
    if diff1 == diff2:
        return
    doc.start_row()
    doc.start_cell('DIFF-TableCell')
    doc.start_paragraph('DIFF-TableHeading')
    doc.write_text(path)
    doc.end_paragraph()
    doc.end_cell()
    doc.start_cell('DIFF-TableCell')
    doc.start_paragraph('DIFF-Text')
    doc.write_text(diff1)
    doc.end_paragraph()
    doc.end_cell()
    doc.start_cell('DIFF-TableCell')
    doc.start_paragraph('DIFF-Text')
    doc.write_text(diff2)
    doc.end_paragraph()
    doc.end_cell()
    doc.end_row()

def report_diff(path, struct1, struct2, doc):
    """
    Compare two struct objects and report differences.
    """
    if struct1 == struct2:
        pass
    elif (isinstance(struct1, (list, tuple)) or 
          isinstance(struct2, (list, tuple))):
        len1 = len(struct1) if isinstance(struct1, (list, tuple)) else 0
        len2 = len(struct2) if isinstance(struct2, (list, tuple)) else 0
        for pos in range(max(len1, len2)):
            value1 = struct1[pos] if pos < len1 else None 
            value2 = struct2[pos] if pos < len2 else None 
            report_diff(path + ("[%d]" % pos), value1, value2, doc)
    elif isinstance(struct1, dict) or isinstance(struct2, dict):
        keys = struct1.keys() if isinstance(struct1, dict) else struct2.keys()
        for key in keys:
            value1 = struct1[key] if struct1 is not None else None
            value2 = struct2[key] if struct2 is not None else None
            if key == "dict": # a raw dict, not a struct
                report_details(path, value1, value2, doc)
            else:
                report_diff(path + "." + key, value1, value2, doc)
    else:
        report_details(doc, path, struct1, struct2)

def todate(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

#------------------------------------------------------------------------
#
# DifferencesReport
#
#------------------------------------------------------------------------
class DifferencesReport(Report):
    """
    Create the DifferencesReport object that produces the report.
    """
    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        self._user = user
        menu = options.menu
        mgobn = lambda name:options.menu.get_option_by_name(name).get_value()
        self.filename = mgobn('filename')
        self.show_diff = mgobn('show_diff')
        self.show_deleted = mgobn('show_deleted')
        self.show_added = mgobn('show_added')
        self.ignore = mgobn('ignore')

    def write_report(self):
        """ The short method that runs through each month and creates a page. """
        self._user.begin_progress(_('Differences Report'), 
                                  _('Looking for differences...'), 100)
        self.doc.start_paragraph('DIFF-Title') 
        self.doc.write_text("Database Differences Report")
        self.doc.end_paragraph()

        self.doc.start_table('DiffTable','DIFF-Table2')
        self.doc.start_row()
        self.doc.start_cell('DIFF-TableCellNoBorder')
        self.doc.start_paragraph('DIFF-TableHeading')
        self.doc.write_text("Database:")
        self.doc.end_paragraph()
        self.doc.end_cell()
        self.doc.start_cell('DIFF-TableCellNoBorder')
        self.doc.start_paragraph('DIFF-Text')
        self.doc.write_text(str(self.database.get_dbname()))
        self.doc.end_paragraph()
        self.doc.end_cell()
        self.doc.end_row()
        self.doc.start_row()
        self.doc.start_cell('DIFF-TableCellNoBorder')
        self.doc.start_paragraph('DIFF-TableHeading')
        self.doc.write_text("File:")
        self.doc.end_paragraph()
        self.doc.end_cell()
        self.doc.start_cell('DIFF-TableCellNoBorder')
        self.doc.start_paragraph('DIFF-Text')
        self.doc.write_text(self.filename)
        self.doc.end_paragraph()
        self.doc.end_cell()
        self.doc.end_row()
        self.doc.end_table()
        self.doc.start_paragraph('DIFF-Heading') 
        self.doc.write_text("")
        self.doc.end_paragraph()
        self.database2 = import_as_dict(self.filename)
        ignore_list = self.ignore.split(",")
        self.sa = [SimpleAccess(self.database), SimpleAccess(self.database2)]
        diffs, added, deleted = diff_dbs(self.database, self.database2)
        #ignore_list)
        if self.show_diff:
            self.doc.start_paragraph('DIFF-Heading') 
            self.doc.write_text("Differences between Database and File")
            self.doc.end_paragraph()
            last_object = None
            if diffs:
                for diff in diffs:
                    obj_type, item1, item2 = diff
                    if last_object != item1:
                        if last_object != None:
                            self.doc.end_table()
                            self.doc.start_paragraph('DIFF-Heading') 
                            self.doc.write_text("")
                            self.doc.end_paragraph()
                        self.doc.start_table('DiffTable','DIFF-Table3')
                    last_object = item1
                    if hasattr(item1, "gramps_id"):
                        start_list(self.doc, "%s: %s" % (obj_type, item1.gramps_id), 
                                   "Database", "File")
                    else:
                        start_list(self.doc, "%s: %s" % (obj_type, item1.get_name()), 
                                   "Database", "File")
                    report_diff(obj_type, item1.to_struct(), item2.to_struct(), self.doc)
                self.doc.end_table()
            else:
                self.doc.start_table('DiffTable','DIFF-Table3')
                start_list(self.doc, "No differences", "", "") 
                self.doc.end_table()
            self.doc.start_paragraph('DIFF-Heading') 
            self.doc.write_text("")
            self.doc.end_paragraph()
        if self.show_deleted:
            self.doc.start_paragraph('DIFF-Heading') 
            self.doc.write_text("Deleted items in File")
            self.doc.end_paragraph()
            if deleted:
                for pair in deleted:
                    obj_type, item = pair
                    self.doc.start_paragraph('DIFF-Text') 
                    self.doc.write_text("Deleted %s: %s" % (obj_type, self.sa[0].describe(item)))
                    self.doc.end_paragraph()
            else:
                self.doc.start_paragraph('DIFF-Text') 
                self.doc.write_text("Nothing deleted")
                self.doc.end_paragraph()
            self.doc.start_paragraph('DIFF-Heading') 
            self.doc.write_text("")
            self.doc.end_paragraph()
        if self.show_added:
            self.doc.start_paragraph('DIFF-Heading') 
            self.doc.write_text("Added items in File")
            self.doc.end_paragraph()
            if added:
                for pair in added:
                    obj_type, item = pair
                    self.doc.start_paragraph('DIFF-Text') 
                    self.doc.write_text("Added %s: %s " % (obj_type, self.sa[1].describe(item)))
                    self.doc.end_paragraph()
            else:
                self.doc.start_paragraph('DIFF-Text') 
                self.doc.write_text("Nothing added")
                self.doc.end_paragraph()
            self.doc.start_paragraph('DIFF-Heading') 
            self.doc.write_text("")
            self.doc.end_paragraph()
        self._user.end_progress()

#------------------------------------------------------------------------
#
# DifferencesOptions
#
#------------------------------------------------------------------------
class DifferencesOptions(MenuReportOptions):
    """ Options for the Differences Report """

    def add_menu_options(self, menu):
        """ Add the options for the text differences report """
        category_name = _("Report Options")
        filename = DestinationOption(_("Family Tree file"), "data.gramps")
        filename.set_help(_("Select a .gpkg or .gramps file"))
        menu.add_option(category_name, "filename", filename)

        show_diff = BooleanOption(_("Show items that are different"), True)
        show_diff.set_help(_("Include items that are different"))
        menu.add_option(category_name, "show_diff", show_diff)

        show_deleted = BooleanOption(_("Show deleted items"), True)
        show_deleted.set_help(_("Include items not in file but in database"))
        menu.add_option(category_name, "show_deleted", show_deleted)

        show_added = BooleanOption(_("Show added items"), True)
        show_added.set_help(_("Include items in file but not in database"))
        menu.add_option(category_name, "show_added", show_added)

        ignore = StringOption(_("Comma-separated items to ignore"), "")
        ignore.set_help(_("Ignore these parts"))
        menu.add_option(category_name, "ignore", ignore)

    def make_my_style(self, default_style, name, description, 
                      size=9, font=FONT_SERIF, justified ="left", 
                      color=None, align=PARA_ALIGN_CENTER, 
                      shadow = None, italic=0, bold=0, borders=0, indent=None):
        """ Create paragraph and graphic styles of the same name """
        # Paragraph:
        f = FontStyle()
        f.set_size(size)
        f.set_type_face(font)
        f.set_italic(italic)
        f.set_bold(bold)
        p = ParagraphStyle()
        p.set_font(f)
        p.set_alignment(align)
        p.set_description(description)
        p.set_top_border(borders)
        p.set_left_border(borders)
        p.set_bottom_border(borders)
        p.set_right_border(borders)
        if indent:
            p.set(first_indent=indent)
        if justified == "left":
            p.set_alignment(PARA_ALIGN_LEFT)       
        elif justified == "right":
            p.set_alignment(PARA_ALIGN_RIGHT)       
        elif justified == "center":
            p.set_alignment(PARA_ALIGN_CENTER)       
        default_style.add_paragraph_style(name, p)
        # Graphics:
        g = GraphicsStyle()
        g.set_paragraph_style(name)
        if shadow:
            g.set_shadow(*shadow)
        if color is not None:
            g.set_fill_color(color)
        if not borders:
            g.set_line_width(0)
        default_style.add_draw_style(name, g)
        
    def make_default_style(self, default_style):
        """ Add the styles used in this report """
        self.make_my_style(default_style, "DIFF-Text", 
                           _('Text'), 12, justified="left")
        self.make_my_style(default_style, "DIFF-Title", 
                           _('Text'), 16, justified="left", 
                           bold=1)
        self.make_my_style(default_style, "DIFF-Heading", 
                           _('Text'), 14, justified="left", 
                           bold=1, italic=1)
        self.make_my_style(default_style, "DIFF-TableHeading", 
                           _('Text'), 12, justified="left", 
                           bold=1)

        #Table Styles
        cell = TableCellStyle()
        cell.set_borders(1)
        default_style.add_cell_style('DIFF-TableCell', cell)

        cell = TableCellStyle()
        default_style.add_cell_style('DIFF-TableCellNoBorder', cell)

        table = TableStyle()
        table.set_width(100)
        table.set_columns(3)
        table.set_column_width(0, 50)
        table.set_column_width(1, 25)
        table.set_column_width(2, 25)
        default_style.add_table_style('DIFF-Table3',table)

        table = TableStyle()
        table.set_width(100)
        table.set_columns(2)
        table.set_column_width(0, 15)
        table.set_column_width(1, 85)
        default_style.add_table_style('DIFF-Table2',table)

