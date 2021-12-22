#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019 Matthias Kemmer
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
1.0 Matthias Kemmer
1.1 George Baynes (baynes@ntlworld.com) adapted to give .odt .ps output
    it still fails .rtf .txt .html and print due to attempt to find available
    width or height. Unable to check latex output.
"""

# ----------------------------------------------------------------------------
#
# Python module
#
# ----------------------------------------------------------------------------
import os
import time
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
from gramps.gen.plug.menu import (MediaOption, NoteOption, BooleanOption,
                                  StringOption, NumberOption)
from gramps.gen.plug.docgen import (ParagraphStyle, FontStyle, PARA_ALIGN_CENTER,
                                    IndexMark, FONT_SERIF,
                                    FONT_SANS_SERIF, INDEX_TYPE_TOC, TableStyle,
                                    TableCellStyle)
from gramps.gen.plug.report.utils import pt2cm

# Old:
#from gramps.gen.const import GRAMPS_LOCALE as glocale
#_ = glocale.translation.gettext

# New:
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
        self.options = options
        self._db = self.database
        self._opt = self.get_opt_dict()
        self.user = user
        self.window = self.user.uistate.window
        self.filename = None

    def get_opt_dict(self):
        """
        Get the values of the menu options
        :return: dictionary e.g. {opt_name:value}
        """
        dct = dict()
        for name in self.menu.get_all_option_names():
            opt = self.menu.get_option_by_name(name)
            dct[name] = opt.get_value()
        return dct

    def __media_is_img(self, mid):
        if mid != "":
            media = self._db.get_media_from_gramps_id(mid)
            media_type = media.get_mime_type()
            return "image" in media_type
        return False

    def __valid_options(self):
        """Check if all menu options are valid for report generation."""
        dct = self._opt
        mid = dct["mid"]
        is_img = self.__media_is_img(mid)

        # no media file selected
        if not mid or mid == "":
            OkDialog(_("INFO"), _("You have to select an image to generate "
                                  "this report."), parent=self.window)
            return False

        # 'include custom note' checked, but no custom note selected
        if dct["incl_note"] and dct["note"] == "":
            OkDialog(_("INFO"), _("You have to select a custom note or uncheck"
                                  " the option 'include custom note' to "
                                  "generate this report."), parent=self.window)
            return False

        # incorrect media file, not an image
        if not is_img:
            OkDialog(_("INFO"), _("You have to select an image to "
                                  "generate this report."), parent=self.window)
            return False

        # if everything is valid
        return True

    def write_report(self):
        """
        Inherited method; called by Report() in _ReportDialog.py
        """
        # check if an image is selected and a note, if include note is checked
        # stop report generation if one is missing
        if not self.__valid_options():
            print("Invalid options. Stop report generation.")
            return

        dct = self._opt
        mid = dct["mid"]
        media = self._db.get_media_from_gramps_id(mid)
        path = media.get_text_data_list()[0]

        # Heading
        if dct["head"] != "" or dct["head"] is not None:
            self.doc.start_paragraph("MMR-Title")
            mark = IndexMark(self._opt["head"], INDEX_TYPE_TOC, 1)
            self.doc.write_text(self._opt["head"], mark)
            self.doc.end_paragraph()

        # Media File
        self.write_media(path)

        # Custom Note
        if self._opt["incl_note"]:
            self.write_note()

        # Add all media data
        if dct["incl_data"]:
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
        if dct["incl_pers"]:
            self.write_person_reference(media)

        self.doc.start_paragraph("MMR-Footer")
        footer = self.menu.get_option_by_name('footer').get_value()
        self.doc.write_text(footer)
        self.doc.end_paragraph()


    def __write_media_notes(self, handles):
        self.write_heading("Notes:")
        for handle in handles:
            note = self._db.get_note_from_handle(handle)
            self.doc.write_styled_note(note.get_styledtext(),
                                       note.get_format(), "MMR-Details")

    def __write_media_tags(self, handles):
        self.write_heading("Tags:")
        for handle in handles:
            tag = self._db.get_tag_from_handle(handle)
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(tag.get_name())
            self.doc.end_paragraph()

    def __write_media_citations(self, handles):
        self.write_heading("Citations:")
        for handle in handles:
            cit = self._db.get_citation_from_handle(handle)
            for entry in cit.get_referenced_handles():
                if entry[0] == "Source":
                    src_handle = entry[1]
            if src_handle:
                source = self._db.get_source_from_handle(src_handle)
                txt = ""
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
        # General info
        self.write_heading("General:")


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
            self.write_heading("Attributes:")
            for attr in media.get_attribute_list():
                self.doc.start_paragraph("MMR-Details")
                self.doc.write_text(attr.get_type().type2base())
#                self.doc.end_paragraph()
                self.doc.write_text(": ")
#                self.doc.start_paragraph("MMR-Details")
                self.doc.write_text(attr.get_value())
                self.doc.end_paragraph()

    def pers_ref_lst(self, media_handle):
        """
        Get a person reference list with image rectangle information.

        :param media_handle: handle of the media file
        :type media_handle: string
        :return lst: list of reference tuples
        :rtype lst: list
        :example lst: (:class Person: object, (0, 0, 100, 100))
        """
        lst = list()
        backrefs = self._db.find_backlink_handles(media_handle)
        for (reftype, ref) in backrefs:
            if reftype == "Person":
                person = self._db.get_person_from_handle(ref)
                gallery = person.get_media_list()
                for mediaref in gallery:
                    referenced_handles = mediaref.get_referenced_handles()
                    if len(referenced_handles) == 1:
                        handle_type, handle = referenced_handles[0]
                        if handle_type == "Media" and handle == media_handle:
                            rect = mediaref.get_rectangle()
                            if rect is None:
                                rect = (0, 0, 100, 100)
                            lst.append((person, rect))
        return lst

    def write_heading(self, txt):
        """Write a report heading"""
        self.doc.start_paragraph("MMR-Heading")
        self.doc.write_text(txt)
        self.doc.end_paragraph()

    def write_media(self, path):
        """
        Add the image to the report

        :param path: gramps media path
        :type path: string
        """
        self.filename = media_path_full(self._db, path)
        if os.path.exists(self.filename):
            width = floor(self.doc.get_usable_width() *
                          self._opt["media_w"] * 0.01)
            height = floor(self.doc.get_usable_height() *
                           self._opt["media_h"] * 0.009)
            # height is capped to 90% to save some space for report heading
            self.doc.add_media(self.filename, 'center', width, height)
            self.doc.page_break()
            self.write_heading(self.filename)
        else:
            no_file = _('File does not exist')
            self.user.warn(_("Could not add photo to page"),
                           _("%(str1)s: %(str2)s") % {'str1': self.filename,
                                                      'str2': no_file})

    def write_person_reference(self, media):
        """
        Add a table that list all referenced people in the image

        :param media: the media object used in this report
        :type media: :class Media: object
        """
        # Add person references
        handle = media.serialize()[0]
        ref_lst = self.pers_ref_lst(handle)
        self.write_heading('Referenced Persons')
        self.doc.start_table('Referenced Persons', 'tbl')
        for i in range((len(ref_lst)//2)):
            ref1 = ref_lst[2*i]
            ref2 = ref_lst[2*i + 1]
            pers_name1 = name_displayer.display(ref1[0])
            pers_name2 = name_displayer.display(ref2[0])

            self.doc.start_row()
            self.doc.start_cell("cell")
            self.doc.add_media(self.filename, 'center', 2.0, 2.0, crop=ref1[1])
            self.doc.end_cell()

            self.doc.start_cell("cell")
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(pers_name1)
            self.doc.end_paragraph()
            self.doc.end_cell()

            self.doc.start_cell("cell")
            self.doc.add_media(self.filename, 'center', 2.0, 2.0, crop=ref2[1])
            self.doc.end_cell()

            self.doc.start_cell("cell")
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(pers_name2)
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.end_row()
        if len(ref_lst) % 2 != 0:
            pers_name = name_displayer.display(ref_lst[-1][0])
            self.doc.start_row()
            self.doc.start_cell("cell")
            self.doc.add_media(self.filename, 'center', 2.0, 2.0,
                               crop=ref_lst[-1][1])
            self.doc.end_cell()

            self.doc.start_cell("cell")
            self.doc.start_paragraph("MMR-Details")
            self.doc.write_text(pers_name)
            self.doc.end_paragraph()
            self.doc.end_cell()
            self.doc.end_row()
        self.doc.end_table()

    def write_note(self):
        """Write a note, if included."""

        nid = self._opt["note"]  # note id
        note = self._db.get_note_from_gramps_id(nid)
        self.doc.write_styled_note(note.get_styledtext(), note.get_format(),
                                   'MMR-Details')


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
        """Add the options to the report option menu"""
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

        dateinfo = time.localtime(time.time())
        rname = _("researcher name")

        footer_string = _('Copyright %(year)d %(name)s') % {
            'year' : dateinfo[0], 'name' : rname}
        footer = StringOption(_('Footer'), footer_string)
        footer.set_help(_("Footer string for the report."))
        menu.add_option(_("Report Options"), "footer", footer)


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
        font.set(face=FONT_SANS_SERIF, size=10, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_top_border(True)
        para.set_top_margin(pt2cm(6))
        para.set_description(_('The style used for the report footer.'))
        default_style.add_paragraph_style("MMR-Footer", para)

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
        default_style.add_cell_style("cell", cell)
