#
# Lines of Descendency Report - a plugin for Gramps, the GTK+/GNOME based
#                               genealogy program.
#
# Copyright (c) 2010, 2012 lcc <lcc.mailaddres@gmail.com>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from TransUtils import get_addon_translator
_ = get_addon_translator().gettext

from gen.plug.docgen import FontStyle, ParagraphStyle, FONT_SANS_SERIF, \
        PARA_ALIGN_CENTER
from gen.plug.menu import PersonOption
from gen.lib import FamilyRelType
from gen.display.name import displayer as _nd

from gen.plug.report import Report
from gen.plug.report import CATEGORY_TEXT
from gen.plug.report import MenuReportOptions
import gen.plug.report.utils as ReportUtils


class LODOptions(MenuReportOptions):
    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):
        category = _('People')

        option = PersonOption(_('Ancestor'))
        option.set_help(_('The ancestor from which to start the line'))
        menu.add_option(category, 'ancestor', option)

        pid = PersonOption(_('Descendent'))
        pid.set_help(_('The descendent to which to build the line'))
        menu.add_option(category, 'pid', pid)

    def make_default_style(self, default_style):
        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=16, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set_header_level(1)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_alignment(PARA_ALIGN_CENTER)
        para.set_description(_('The style used for the title of the page.'))
        default_style.add_paragraph_style("LOD-Title", para)

        font = FontStyle()
        font.set(face=FONT_SANS_SERIF, size=15, bold=1)
        para = ParagraphStyle()
        para.set_font(font)
        para.set(lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The style used for the title of a line.'))
        default_style.add_paragraph_style("LOD-Line", para)

        para = ParagraphStyle()
        para.set(lmargin=1.5)
        para.set_top_margin(0.25)
        para.set_bottom_margin(0.25)
        para.set_description(_('The basic style used for the text display.'))
        default_style.add_paragraph_style("LOD-Entry", para)

class LinesOfDescendency(Report):
    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)

        menu = options.menu
        pid  = menu.get_option_by_name('pid').get_value()
        self.descendent = database.get_person_from_gramps_id(pid)
        self.descendent_handle = self.descendent.get_handle()
        ancestor = menu.get_option_by_name('ancestor').get_value()
        self.ancestor = database.get_person_from_gramps_id(ancestor)
        if (self.descendent == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )

    def write_path(self, path):
        gen = 1
        handle = path[0]
        next_person = self.database.get_person_from_handle(path[0])

        self.doc.start_paragraph('LOD-Line')
        self.doc.write_text('%(line)s. line:' % { 'line': self.line })
        self.doc.end_paragraph()
        self.line +=1

        for next_handle in path[1:]:
            person = next_person
            next_person = self.database.get_person_from_handle(next_handle)
            name = _nd.display(person)
            family_handle = next_person.get_main_parents_family_handle()
            family = self.database.get_family_from_handle(family_handle)
            mother = family.get_mother_handle()
            spouse_handle = \
                mother if mother != handle \
                    else family.get_father_handle()
            handle = next_handle
            spouse = self.database.get_person_from_handle(spouse_handle)
            if spouse:
                spouse_name = _nd.display(spouse)
            else:
                spouse_name = 'N.N.'
            if family.get_relationship() == FamilyRelType.MARRIED:
                abbrev = 'm.'
            else:
                abbrev = 'rw.'

            self.doc.start_paragraph("LOD-Entry")

            self.doc.write_text("%(gen)s. %(person)s %(abbrev)s %(spouse)s" % {
                'gen' : gen,
                'person' : name,
                'abbrev' : abbrev,
                'spouse' : spouse_name
                })

            self.doc.end_paragraph()

            gen += 1

        self.doc.start_paragraph("LOD-Entry")
        self.doc.write_text("%(gen)s. %(person)s" % {
            'gen' : gen,
            'person' : _nd.display(next_person)
            })
        self.doc.end_paragraph()

    def traverse(self, person_handle, person_path=[], cur_gen=1):
        if (not person_handle):
            return

        next_path = list(person_path)
        next_path.append(person_handle)

        if person_handle == self.descendent_handle:
            self.write_path(next_path)
            return

        person = self.database.get_person_from_handle(person_handle)
        index = 0
        for family_handle in person.get_family_handle_list():
            family = self.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                self.traverse(child_ref.ref, next_path, cur_gen+1)

    def write_report(self):
        self.doc.start_paragraph("LOD-Title")
        self.doc.write_text(_("Lines of Descendency from %(ancestor)s to"
        " %(descendent)s" % { 'ancestor' : _nd.display(self.ancestor),
                              'descendent' : _nd.display(self.descendent) }))
        self.doc.end_paragraph()

        self.line = 1

        self.traverse(self.ancestor.get_handle())
