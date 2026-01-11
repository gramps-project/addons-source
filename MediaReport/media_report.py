#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019-2021 Matthias Kemmer
# Copyright (C) 2021 George Baynes
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
"""Create a Media Report containing images, image data and notes."""


# ----------------------------------------------------------------------------
#
# Python module
#
# ----------------------------------------------------------------------------
import os
from math import floor

# ----------------------------------------------------------------------------
#
# Gramps module
#
# ----------------------------------------------------------------------------
from gramps.gui.dialog import OkDialog
from gramps.gen.utils.file import media_path_full
from gramps.gen.plug.report import Report, MenuReportOptions
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.plug.menu import (
    MediaOption, NoteOption, BooleanOption, StringOption, NumberOption)
from gramps.gen.plug.docgen import (
    ParagraphStyle, FontStyle, PARA_ALIGN_CENTER, IndexMark, FONT_SERIF,
    FONT_SANS_SERIF, INDEX_TYPE_TOC, TableStyle, TableCellStyle)


# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# ----------------------------------------------------------------------------
#
# Media Report
#
# ----------------------------------------------------------------------------
class MediaReport(Report):
    """Create a Media Report containing images, image data and notes."""

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)

        self.menu = options.menu
        self.db = self.database
        self.opt = options.options_dict
        self.user = user
        self.window = self.user.uistate.window
        self.filename = None

    def write_report(self):
        """Report generation."""

        if not self.__valid_options():
            return False

        mid = self.opt["mid"]
        media = self.db.get_media_from_gramps_id(mid)
        path = media.get_text_data_list()[0]

        # Heading
        if self.opt["head"] != "" or self.opt["head"] is not None:
            self.doc.start_paragraph("MMR-Title")
            mark = IndexMark(self.opt["head"], INDEX_TYPE_TOC, 1)
            self.doc.write_text(self.opt["head"], mark)
            self.doc.end_paragraph()

        # Media File
        self.__write_media(path)

        # Custom Note
        if self.opt["incl_note"]:
            self.__write_note()

        # Add all media data
        if self.opt["incl_data"]:
            self.__write_general_data(media)
            self.__write_media_attributes(media)
            ref_dct = self.__get_ref_list(media)
            if "Tag" in ref_dct:
                self.__write_media_tags(ref_dct["Tag"])
            if "Note" in ref_dct:
                self.__write_media_notes(ref_dct["Note"])
            if "Citation" in ref_dct:
                self.__write_media_citations(ref_dct["Citation"])

        # Person references
        if self.opt["incl_pers"]:
            self.__write_person_reference(media)

    def __is_image(self, mid):
        if mid == "":
            return False
        media = self.db.get_media_from_gramps_id(mid)
        if not media:
            return False
        media_type = media.get_mime_type()
        return "image" in media_type

    def __valid_options(self):
        # Check if all report options are valid:
        # 1. A media file is selected
        # 2. Media file is an image
        # 3. A note is selected (if note option is checked)
        include_note = self.opt["incl_note"]
        note = self.opt["note"]
        mid = self.opt["mid"]

        # no media file selected
        if self.window and (not mid or mid == ""):
            OkDialog(
                _("INFO"),
                _("You have to select an image to generate this report."),
                parent=self.window)
            return False

        # 'include custom note' checked, but no custom note selected
        if self.window and include_note and note == "":
            OkDialog(
                _("INFO"),
                _("You have to select a custom note or uncheck"
                  " the option 'include custom note' to "
                  "generate this report."),
                parent=self.window)
            return False

        # incorrect media file, not an image
        if self.window and not self.__is_image(mid):
            OkDialog(
                _("INFO"),
                _("You have to select an image to generate this report."),
                parent=self.window)
            return False

        # if everything is valid
        return True

    def __write_media_notes(self, handles):
        self.__write_heading("Notes:")
        for handle in handles:
            note = self.db.get_note_from_handle(handle)
            self.doc.write_styled_note(
                note.get_styledtext(), note.get_format(), "MMR-Details")

    def __write_media_tags(self, handles):
        self.__write_heading("Tags:")
        for handle in handles:
            tag = self.db.get_tag_from_handle(handle)
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(tag.get_name())
            self.doc.end_paragraph()

    def __write_media_citations(self, handles):
        self.__write_heading("Citations:")
        for handle in handles:
            cit = self.db.get_citation_from_handle(handle)
            src_handle = ""
            txt = ""
            for entry in cit.get_referenced_handles():
                if entry[0] == "Source":
                    src_handle = entry[1]
            if src_handle != "":
                source = self.db.get_source_from_handle(src_handle)
                if source.get_author():
                    txt += "%s: " % source.get_author()
                if source.get_title():
                    txt += '"%s", ' % source.get_title()
                if source.get_publication_info():
                    txt += "%s, " % source.get_publication_info()
                if cit.get_page():
                    txt += cit.get_page()
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(txt)
            self.doc.end_paragraph()

    def __write_general_data(self, media):
        self.__write_heading("General:")

        self.doc.start_paragraph("MMR-Details")
        self.doc.write_text("Description: ")
        self.doc.write_text(media.get_description())
        self.doc.end_paragraph()

        self.doc.start_paragraph("MMR-Details")
        self.doc.write_text("Image type: ")
        self.doc.write_text(media.get_mime_type())
        self.doc.end_paragraph()

    def __get_ref_list(self, media):
        dct = dict()
        for category in media.get_referenced_handles():
            name, handle = category
            if name in dct:
                dct[name].append(handle)
            else:
                dct[name] = [handle]
        return dct

    def __write_media_attributes(self, media):
        if media.get_attribute_list():
            self.__write_heading("Attributes:")
            for attr in media.get_attribute_list():
                self.doc.start_paragraph("MMR-Details")
                self.doc.write_text(attr.get_type().type2base())
                self.doc.write_text(": ")
                self.doc.write_text(attr.get_value())
                self.doc.end_paragraph()

    def __get_pers_ref_lst(self, media_handle):
        lst = list()
        backrefs = self.db.find_backlink_handles(media_handle)
        for (reftype, ref) in backrefs:
            if reftype != "Person":
                continue
            person = self.db.get_person_from_handle(ref)
            if not person:
                continue
            gallery = person.get_media_list()
            if not gallery:
                continue
            for mediaref in gallery:
                referenced_handles = mediaref.get_referenced_handles()
                if not referenced_handles:
                    continue
                handle_type, handle = referenced_handles[0]
                if handle_type == "Media" and handle == media_handle:
                    rect = mediaref.get_rectangle()
                    if not rect:
                        rect = (0, 0, 100, 100)
                    lst.append((person, rect))
        return lst  # [(class:Person, (0, 0, 100, 100))]

    def __write_heading(self, txt):
        self.doc.start_paragraph("MMR-Heading")
        self.doc.write_text(txt)
        self.doc.end_paragraph()

    def __write_media(self, path):
        self.filename = media_path_full(self.db, path)
        if os.path.exists(self.filename):
            try:
                width = floor(self.doc.get_usable_width() *
                              self.opt["media_w"] * 0.01)
                height = floor(self.doc.get_usable_height() *
                               self.opt["media_h"] * 0.009)
                # height is capped to 90% to save some space for report heading
                self.doc.add_media(self.filename, 'center', width, height)
            except AttributeError:
                # AttributeError, because some docgens don't support the
                # methods 'get_usable_width' and 'get_usable_height'
                self.doc.add_media(self.filename, 'center', 1.0, 1.0)
            self.doc.page_break()
        else:
            no_file = _('File does not exist')
            self.user.warn(_("Could not add photo to page"),
                           _("%(str1)s: %(str2)s") % {'str1': self.filename,
                                                      'str2': no_file})

    def __write_person_reference(self, media):
        handle = media.serialize()[0]
        ref_lst = self.__get_pers_ref_lst(handle)
        self.__write_heading('Referenced Persons')
        self.doc.start_table('Referenced Persons', 'tbl')
        new_row = True
        for entry in ref_lst:
            name = name_displayer.display(entry[0])
            border = entry[1]

            if new_row:
                self.doc.start_row()
            self.doc.start_cell("cell")
            self.doc.add_media(self.filename, 'center', 2.0, 2.0, crop=border)
            self.doc.end_cell()

            self.doc.start_cell("cell")
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(name)
            self.doc.end_paragraph()
            self.doc.end_cell()
            if not new_row:
                self.doc.end_row()
            new_row = not new_row
        self.doc.end_table()

    def __write_note(self):
        nid = self.opt["note"]  # note id
        note = self.db.get_note_from_gramps_id(nid)
        self.doc.write_styled_note(
            note.get_styledtext(), note.get_format(), 'MMR-Details')


# ----------------------------------------------------------------------------
#
# Report Options
#
# ----------------------------------------------------------------------------
class ReportOptions(MenuReportOptions):
    """Report options for Media Report"""

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        """Add the options to the report option menu."""
        head = StringOption(_("Heading"), "")
        menu.add_option(_("Report Options"), "head", head)

        media = MediaOption(_("Media"))
        media.set_help(_("Select a media file for this report"))
        menu.add_option(_("Report Options"), "mid", media)

        self.note = NoteOption(_("Custom note"))
        self.note.set_help(_("Select a note for this report"))
        menu.add_option(_("Report Options"), "note", self.note)

        self.incl_note = BooleanOption(_("Include custom note"), False)
        self.incl_note.set_help(_("The custom note will be included"))
        menu.add_option(_("Report Options"), "incl_note", self.incl_note)
        self.incl_note.connect('value-changed', self.__update_custom_note_opt)

        incl_pers = BooleanOption(_("Include referenced people"), False)
        incl_pers.set_help(_("Referenced people will be included"))
        menu.add_option(_("Report Options"), "incl_pers", incl_pers)

        incl_data = BooleanOption(_("Include media data"), False)
        incl_data.set_help(_("Tags, notes and attributes will be included"))
        menu.add_option(_("Report Options"), "incl_data", incl_data)

        media_w = NumberOption(_("Media width"), 100, 10, 100, 10)
        media_w.set_help(_("Maximum media width in % of available "
                           "page width."))
        menu.add_option(_("Report Options"), "media_w", media_w)

        media_h = NumberOption(_("Media height"), 100, 10, 100, 10)
        media_h.set_help(_("Maximum media height in % of available page "
                           "height."))
        menu.add_option(_("Report Options"), "media_h", media_h)

    def __update_custom_note_opt(self):
        self.note.set_available(False)
        if self.incl_note.get_value():
            self.note.set_available(True)

    def make_default_style(self, default_style):
        """Define the default styling."""
        para = ParagraphStyle()
        default_style.add_paragraph_style("default_style", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=18, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_description(_('The style used for the title of the report.'))
        default_style.add_paragraph_style("MMR-Title", para)

        font = FontStyle()
        font.set(face=FONT_SERIF, size=12, italic=0, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(2)
        para.set(first_indent=0.0, lmargin=1.0)
        para.set_top_margin(0.50)
        para.set_bottom_margin(0.0)
        para.set_description(_('The style used for headings.'))
        default_style.add_paragraph_style("MMR-Heading", para)

        font = FontStyle()
        font.set(face=FONT_SERIF, size=10)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(first_indent=0.0, lmargin=1.0)
        para.set_description(_('The style used for details.'))
        default_style.add_paragraph_style("MMR-Details", para)

        tbl = TableStyle()
        tbl.set_width(100)
        tbl.set_columns(4)
        tbl.set_column_width(0, 20)
        tbl.set_column_width(1, 30)
        tbl.set_column_width(2, 20)
        tbl.set_column_width(3, 30)
        default_style.add_table_style('tbl', tbl)

        cell = TableCellStyle()
        cell.set_padding(0.2)
        default_style.add_cell_style("cell", cell)
