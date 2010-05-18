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

# $Id $

"""Reports/Graphical Reports/Pedigree Chart"""

# Based in part on:
# http://www.kbyu.org/ancestors
# http://www.legacyfamilytree.com/_images/GVPedChrt.gif

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
#import time
import math
import numpy as np
from collections import deque

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gen.display.name import displayer as name_displayer
import DateHandler
#from gen.lib.date import Date
from gen.plug import docgen
from gen.plug.menu import NumberOption, PersonOption
#from gen.plug.menu import BooleanOption, TextOption
from gettext import gettext as _
try:
    # v3.2
    from ReportBase import MenuReportOptions
    from ReportBase import Report
    from ReportBase import ReportUtils
    pt2cm = ReportUtils.pt2cm
except ImportError:
    # v3.3
    from gen.plug.report import Report
    from gen.plug.report.utils import pt2cm
    from gui.plug.report import MenuReportOptions

_LINKS_BEGIN = 8
_PEOPLE_PER_PAGE = 15
_GENERATIONS_PER_PAGE = 4
_MAX_INDEX_PER_PAGE = 2**_GENERATIONS_PER_PAGE
_MAX_PAGES = 1000
_PLACEHOLDER = "_" * 12
_ARROW = np.matrix([[-0.5 ,  0.55],
                    [ 0.0 ,  0.55],
                    [ 0.0 ,  0.75],
                    [ 0.5 ,  0.25],
                    [ 0.0 , -0.25],
                    [ 0.0 , -0.05],
                    [-0.5 , -0.05],
                    [-0.5 ,  0.55]])
_SOURCE_ARROW_OFFSET = 2 # cm
_LINE_X_OFFSET = 1 # cm

def PageCounter(initial_value=0):
    v = initial_value
    while v < initial_value + _MAX_PAGES:
        yield v
        v += 1
    return

#------------------------------------------------------------------------
#
# PageLinks class
#
#------------------------------------------------------------------------
class PageLinks:
    """
    Manages a two-way index for the person handle and a corrisponding page link
    that list the index where this person's tree resumes.

    """
    def __init__(self, depth):
        """
        Create the indexes for each person handle and page link.

        depth: used to track the number of subsequent pages to determine when
               we reach the generation limit.

        """
        self._index_by_handle = dict()
        self._index_by_page = dict()
        self.depth = depth

    def add(self, person_handle, current_page, link_to_page):
        """
        Add a new person and page link to the set of indexes.

        person_map: a list of person_handles that will be printed on this page
        page_link_counter: a generator that returns the next page number

        """
        self._index_by_handle[person_handle] = (current_page, link_to_page)
        self._index_by_page[link_to_page] = person_handle

    def __str__(self):
        """returns a string with the person handles sorted by page order"""
        links_out = self.handlesByPage()
        return repr(links_out)

    def empty(self):
        return (len(self._index_by_handle) > 0)

    def handlesByPage(self):
        """Return a list of person handles in the order of their page number"""
        return [self._index_by_page[k] for k in sorted(self._index_by_page.keys())]

    def getHandle(self, page):
        return self._index_by_page[page]

    def getSourcePage(self, p_handle):
        return self._index_by_handle[p_handle][0]

    def getSource(self, p_handle):
        if self._index_by_handle.has_key(p_handle):
            source_text = str(self._index_by_handle[p_handle][0])
        else:
            source_text = ""
        return source_text

    def getLinkPage(self, p_handle):
        return self._index_by_handle[p_handle][1]

    def getLink(self, p_handle):
        if self._index_by_handle.has_key(p_handle):
            link_text = str(self._index_by_handle[p_handle][1])
        else:
            link_text = ""
        return link_text

#------------------------------------------------------------------------
#
# PersonBox class
#
#------------------------------------------------------------------------
class PersonBox:
    def __init__(self, index, person_handle, report, page_link = None):
        self.index = index
        self.person_handle = person_handle
        self.report = report
        self.page_link = page_link

        self.style_name = 'PC-box'

        self.person = None

        self.line = None

    def familyContinues(self):
        """Return true if this person has a primary family"""
        person = self.report.database.get_person_from_handle(self.person_handle)
        family_handle = person.get_main_parents_family_handle()
        return (family_handle is not None)

    def _getPersonRecord(self):
        if self.person is None:
            self.person = self.report.database.get_person_from_handle(self.person_handle)

    def getName(self):
        self._getPersonRecord()
        if self.person is not None:
            name = name_displayer.display(self.person)
        else:
            name = "ERROR"
        width = pt2cm(self.report.doc.string_width(self.report.get_font(self.style_name), name))
        if width > self.report.max_box_size:
            letter_size = width / len(name)
            end_pos = len(name) - int(math.ceil((width - self.report.max_box_size) / letter_size))
            try:
                cut_off = name.rindex(' ', 0, end_pos)
            except ValueError, val:
                print "[EXCEPTION]", str(val)
                cut_off = 10
            #print "[DEBUG]", name, letter_size, end_pos, name[:cut_off]
            name = name[:cut_off]
        return name

    def getLine(self, refresh=False):
        # TODO: The name should be distinguished from the rest of the information.
        #   name
        #     birth date (location?)
        #     death date (location?)
        #     marriage date? (location?)
        if self.line is None or refresh:
            self.line = self.getName()

            birth_date = _PLACEHOLDER
            birth_ref = self.person.get_birth_ref()
            if birth_ref is not None:
                for type, handle in birth_ref.get_referenced_handles():
                    if type == 'Event':
                        birth_event = self.report.database.get_event_from_handle(handle)
                        birth_date = DateHandler.get_date(birth_event)
            self.line += "\nb. " + str(birth_date)

            # we don't repeat this information for the mother
            if not self.isMother():
                relationship_date = _PLACEHOLDER
                all_families = self.person.get_family_handle_list()
                if len(all_families) > 0:
                    family = self.report.database.get_family_from_handle(all_families[0])
                    for evt_ref in family.get_event_ref_list():
                        evt_handle = evt_ref.get_reference_handle()
                        evt = self.report.database.get_event_from_handle(evt_handle)
                        # FIXME: where are the event types defined in Gramps,
                        # and are these the only important ones?
                        #print repr(evt.get_type().string)
                        if evt.get_type().string in ["Marriage", "Civil Union"]:
                            relationship_date = DateHandler.get_date(evt)
                self.line += "\nm. " + str(relationship_date)

            death_date = _PLACEHOLDER
            death_ref = self.person.get_death_ref()
            if death_ref is not None:
                for type, handle in death_ref.get_referenced_handles():
                    if type == 'Event':
                        death_event = self.report.database.get_event_from_handle(handle)
                        death_date = DateHandler.get_date(death_event)
            self.line += "\nd. " + str(death_date)

        return self.line

    def getLongestLine(self):
        which = 0
        parts = self.getLine().split('\n')
        for i in range(len(parts)):
            if len(parts[i]) >= len(parts[which]):
                which = i
        return parts[which]

    def getPos(self):
        # person's index determines which box they occupy on the page
        if self.report.coordinates.has_key(self.index):
            coord = self.report.coordinates[self.index]
        return coord

    def getSize(self):
        line = self.getLongestLine()
        lines = len(self.getLine().split("\n"))
        w = pt2cm(self.report.doc.string_width(self.report.get_font(self.style_name), line.replace("<u>", "").replace("</u>", "")))
        h = self.report.get_font_height(self.style_name) * 1.4 * lines
        #print "[DEBUG]", line, w, h
        return (w, h)

    def getDescendant(self):
        if self.isMother():
            descendant_index = (self.index - 1) / 2
        else:
            descendant_index = self.index / 2
        return descendant_index

    def isMother(self):
        """Used to determine which way to draw lines and how to get back to the descendant."""
        result = self.index % 2 != 0
        return result

#------------------------------------------------------------------------
#
# PedigreeChart report
#
#------------------------------------------------------------------------
class PedigreeChart(Report):

    def __init__(self, database, options_class):

        Report.__init__(self, database, options_class)

        menu = options_class.menu

        self.max_generations = menu.get_option_by_name('maxgen').get_value()

        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = database.get_person_from_gramps_id(pid)
        if (self.center_person == None) :
            raise ReportError(_("Person %s is not in the Database") % pid )

        self.title = "Pedigree Chart"

        self.map = {}
        self.page_number = PageCounter(1)
        self.page_link_counter = PageCounter(2)
        self.generation_index = 1

        page_width = self.doc.get_usable_width()
        page_height = self.doc.get_usable_height()

        self.columns = [0.25,
            page_width *  3 / 20,
            page_width *  6 / 20,
            page_width * 12 / 20,
            page_width * 16 / 20
            ]

        # The third column (index 2) has the smallest space available, so I
        # base the box sizes on it.
        self.em_size = pt2cm(self.doc.string_width(self.get_font('PC-box'), 'm'))
        self.max_box_size = self.columns[3] - self.columns[2]
        self.name_max_len = self.max_box_size / self.em_size

        #print "[DEBUG] columns", repr(self.columns)
        #print "[DEBUG] em size: %s, max_box_size: %s, max_name_len: %s" % (self.em_size, self.max_box_size, self.name_max_len)

        self.coordinates = { 1: (self.columns[0], page_height * 32 / 64),
                        # second generation
                        2: (self.columns[1], page_height * 16 / 64),
                        3: (self.columns[1], page_height * 48 / 64),
                        # third generation
                        4: (self.columns[2], page_height * 8 / 64),
                        5: (self.columns[2], page_height * 24 / 64),
                        6: (self.columns[2], page_height * 40 / 64),
                        7: (self.columns[2], page_height * 56 / 64),
                        # fourth generation
                        8: (self.columns[3], page_height * 4 / 64),    #  3/64
                        9: (self.columns[3], page_height * 13 / 64),   # 15/64
                        10: (self.columns[3], page_height * 20 / 64),  # 20/64
                        11: (self.columns[3], page_height * 28 / 64),  # 30
                        12: (self.columns[3], page_height * 36 / 64),  # 35
                        13: (self.columns[3], page_height * 45 / 64),  # 47
                        14: (self.columns[3], page_height * 52 / 64),  # 51
                        15: (self.columns[3], page_height * 60 / 64)   # 60
        }

    def write_report(self):
        # steps:
        # 1) start with the center person and generate the first page
        # 2) go through the map on the first page and select indexes 8-15 for
        #    the next pages
        # 3) continue with each subsequent page and generate lists there too
        page_queue = deque([])
        # Generate the first page
        page_links = self._fillPage(self.center_person.get_handle())
        page_queue.append(page_links)
        while len(page_queue) > 0:
            page_links = page_queue.popleft()
            for person_handle in page_links.handlesByPage():
                new_links = self._fillPage(person_handle, page_links.depth, page_links.getSourcePage(person_handle))
                page_queue.append(new_links)

    def _fillPage(self, person_handle, depth = 0, source_page = None):
        """Create a tree of up to 15 people for this page"""
        current_page = self.page_number.next()
        self.map = {}
        gen_limit = self.max_generations - (depth * _GENERATIONS_PER_PAGE)
        ###### DEBUG #######
        #print "Depth=%d, gen_limit=%d" % (depth, gen_limit)
        ###### DEBUG #######
        self._getParents(person_handle, 1, gen_limit)
        # create links to subsequent pages
        page_links = PageLinks(depth + 1)
        for i in range(_LINKS_BEGIN, _PEOPLE_PER_PAGE + 1):
            if self.map.has_key(i):
                if self.map[i].familyContinues():
                    page_links.add(self.map[i].person_handle, current_page, self.page_link_counter.next())
        # generate the page
        self.doc.start_page()
        self.doc.center_text('PC-title', self.title,
                             self.doc.get_usable_width() / 2, 0)
        self.doc.center_text('PC-box', "Page %d" % current_page,
                            self.doc.get_usable_width() / 2, 0 + self.get_font_height('PC-box') * 2.2)

        # print a link back to the source page (if any)
        if source_page is not None:
            self.drawSourceArrow(str(source_page))

        for index in sorted(self.map.keys()):
            person_box = self.map[index]
            
            (x, y) = person_box.getPos()
            (w, h) = person_box.getSize()
            self.doc.draw_box(person_box.style_name, person_box.getLine(), x, y, w, h)

            # show a page link if it's there
            link_text = page_links.getLink(person_box.person_handle)
            if link_text != "":
                self.drawLinkArrow(link_text, y, w, h)

            # draw the line back to the descendant box
            if x > self.columns[0]:
                descendant = self.map[person_box.getDescendant()]
                (dx, dy) = descendant.getPos()
                (dw, dh) = descendant.getSize()
                x1 = x
                y1 = y + h / 2
                x2 = dx + _LINE_X_OFFSET
                if person_box.isMother():
                    y2 = dy + dh
                else:
                    y2 = dy
                self.doc.draw_line("PC-line", x1, y1, x2, y1)
                self.doc.draw_line("PC-line", x2, y2, x2, y1)
            ###### DEBUG #######
            # print index, person_box.getName(), link_text
            ###### DEBUG #######
        self.doc.end_page()
        # return the list of links
        return page_links

    def _getParents(self, person_handle, index, gen_limit):
        """
        Generate a list of the person's parents and their parents recursively up
        to max_generations.

        person_handle: the center person
        index: the current index position of this person
        gen_limit: maximum number of generations for this page

        This function is based on AncestorTree.apply_filter().

        """
        if (not person_handle) or (index >= _MAX_INDEX_PER_PAGE) or (index >= 2**gen_limit):
        #if (not person_handle) or (index >= 2**self.max_generations):
            return

        self.map[index] = PersonBox(index, person_handle, self)

        person = self.database.get_person_from_handle(person_handle)
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            family = self.database.get_family_from_handle(family_handle)
            self._getParents(family.get_father_handle(), index * 2, gen_limit)
            self._getParents(family.get_mother_handle(), index * 2 + 1, gen_limit)

    # helper function from FamilyTree by Reinhard Mueller
    def get_font_height(self, style_name):

        return pt2cm(self.get_font(style_name).get_size())

    # helper function from FamilyTree by Reinhard Mueller
    def get_font(self, style_name):

        style_sheet = self.doc.get_style_sheet()
        draw_style = style_sheet.get_draw_style(style_name)
        paragraph_style_name = draw_style.get_paragraph_style()
        paragraph_style = style_sheet.get_paragraph_style(paragraph_style_name)
        return paragraph_style.get_font()

    def drawSourceArrow(self, link_text):
        link_x = 0.5
        link_y = self.doc.get_usable_height() / 2 + _SOURCE_ARROW_OFFSET + self.get_font_height('PC-box')
        # reverse the direction of the arrow
        flip = np.matrix([[-1,  0], [ 0,  1]])
        left_arrow = _ARROW * flip
        # calculate the position of the arrow
        loc = np.array([link_x, link_y])
        path = left_arrow + loc
        self.doc.draw_path('PC-line', path.A)
        # write the text inside the arrow
        self.doc.draw_text('PC-box', link_text, link_x, link_y)

    def drawLinkArrow(self, link_text, y, w, h):
        # calculate the size of the link text
        w = pt2cm(self.doc.string_width(self.get_font('PC-box'), link_text))
        link_x = self.doc.get_usable_width() - w
        link_y = y + h / 2
        # calculate the position of the arrow
        loc = np.array([link_x, link_y])
        path = _ARROW + loc
        self.doc.draw_path('PC-line', path.A)
        # write the text inside the arrow
        self.doc.draw_text('PC-box', link_text, link_x, link_y)

#------------------------------------------------------------------------
#
# PedigreeChartOptions
#
#------------------------------------------------------------------------
class PedigreeChartOptions(MenuReportOptions):

    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, dbase):
        MenuReportOptions.__init__(self, name, dbase)

    def add_menu_options(self, menu):

        category_name = _("Tree Options")

        pid = PersonOption(_("Center Person"))
        pid.set_help(_("The center person for the tree"))
        menu.add_option(category_name, "pid", pid)

        max_gen = NumberOption(_("Generations"), 10, 1, 50)
        max_gen.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "maxgen", max_gen)

    def make_default_style(self, default_style):
        """Make the default output style for the Ancestor Tree."""

        ## Paragraph Styles:
        f = docgen.FontStyle()
        f.set_size(9)
        f.set_type_face(docgen.FONT_SANS_SERIF)
        p = docgen.ParagraphStyle()
        p.set_font(f)
        p.set_description(_('The basic style used for the text display.'))
        default_style.add_paragraph_style("PC-Normal", p)

        f = docgen.FontStyle()
        f.set_size(16)
        f.set_type_face(docgen.FONT_SANS_SERIF)
        p = docgen.ParagraphStyle()
        p.set_font(f)
        p.set_alignment(docgen.PARA_ALIGN_CENTER)
        p.set_description(_('The basic style used for the title display.'))
        default_style.add_paragraph_style("PC-Title", p)

        g = docgen.GraphicsStyle()
        g.set_paragraph_style("PC-Normal")
        #g.set_shadow(1, 0.2)
        g.set_fill_color((255, 255, 255))
        default_style.add_draw_style("PC-box", g)

        g = docgen.GraphicsStyle()
        g.set_paragraph_style("PC-Title")
        g.set_color((0, 0, 0))
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)
        default_style.add_draw_style("PC-title", g)

        g = docgen.GraphicsStyle()
        default_style.add_draw_style("PC-line", g)
