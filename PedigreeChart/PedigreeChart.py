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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# $Id$

"""Reports/Graphical Reports/Pedigree Chart"""

# Based in part on the following ancestry charts:
# http://www.kbyu.org/ancestors
# http://www.legacyfamilytree.com/_images/GVPedChrt.gif

#------------------------------------------------------------------------
#
# standard python modules
#
#------------------------------------------------------------------------
from collections import deque

#------------------------------------------------------------------------
#
# gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.utils.symbols import Symbols
import gramps.gen.datehandler
from gramps.gen.lib import ChildRefType
from gramps.gen.plug import docgen
from gramps.gen.plug.report import Report, MenuReportOptions
from gramps.gen.plug.docgen import fontscale, IndexMark, INDEX_TYPE_TOC
from gramps.gen.plug.menu import BooleanOption, NumberOption, PersonOption
from gramps.gen.plug.report.utils import pt2cm, cm2pt
from gramps.gen.errors import ReportError
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

import _matrixops as np

# TODO: configurable page generation ?
_LINKS_BEGIN = 8
_PEOPLE_PER_PAGE = 15
_MIN_PERSON_LIMIT = 1
_GENERATIONS_PER_PAGE = 4
_MAX_INDEX_PER_PAGE = 2**_GENERATIONS_PER_PAGE
_MAX_PAGES = 1000
_PLACEHOLDER = ''
_OUTPUT_FORMATS = {"pdf": True, "ps": True}
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
_GUTTER_SIZE = 0.25 # cm

def PageCounter(initial_value=0):
    """A generator to return sequential page numbers."""
    v = initial_value
    while v < initial_value + _MAX_PAGES:
        yield v
        v += 1

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
    def __init__(self, depth, max_generations):
        """
        Create the indexes for each person handle and page link.

        depth: used to track the number of subsequent pages to determine when
               we reach the generation limit.

        """
        self._index_by_handle = dict()
        self._index_by_page = dict()
        self.depth = depth
        self.gen_limit = max_generations - (depth * _GENERATIONS_PER_PAGE)

    def add(self, person_handle, current_page, link_to_page):
        """
        Add a new person and page link to the set of indexes.

        person_map: a list of person_handles that will be printed on this page
        page_link_counter: a generator that returns the next page number

        """
        self._index_by_handle[person_handle] = (current_page, link_to_page)
        self._index_by_page[link_to_page] = person_handle

    def __str__(self):
        """Return a string with the person handles sorted by page order."""
        links_out = self.handlesByPage()
        return repr(links_out)

    def empty(self):
        """Return true if the length of the primary index is 0."""
        return len(self._index_by_handle) > 0

    def handlesByPage(self):
        """Return a list of person handles in the order of their page number."""
        return [self._index_by_page[k] for k in sorted(self._index_by_page.keys())]

    def getHandle(self, page):
        """Return a person handle for the given page number."""
        return self._index_by_page[page]

    def getSourcePage(self, p_handle):
        """Return the source page number for the given handle."""
        return self._index_by_handle[p_handle][0]

    def getSource(self, p_handle):
        """Return a string with the page number for the given person handle."""
        if p_handle in self._index_by_handle:
            source_text = str(self._index_by_handle[p_handle][0])
        else:
            source_text = ""
        return source_text

    def getLinkPage(self, p_handle):
        """Return the page number that this person handle is linked to"""
        return self._index_by_handle[p_handle][1]

    def getLink(self, p_handle):
        """Return a string with the link page number if the page limit has not been reached"""
        if self.gen_limit > _MIN_PERSON_LIMIT and p_handle in self._index_by_handle:
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
    """Represents an entry on the pedigree chart"""
    def __init__(self, index, person_handle, report, page_link = None):
        """Initialize the class members.

        index - the person's place in the chart (1-15)
        person_handle - the database identifier
        report - a reference to the report object (used to find page dimentions)
        page_link - NOT USED

        """
        self.index = index
        self.person_handle = person_handle
        self.report = report
        self.birth_symbol, self.marriage_symbol, self.death_symbol = report.bmd_symbols
        self.page_link = page_link

        self.title_style = 'PC-box_title' if _OUTPUT_FORMATS.get(report.format_name) else 'PC-box'
        self.content_style = 'PC-box'

        self.relationship_style = 'PC-line'

        self.person = None

        self.name = self.content = None

    def getPersonRecord(self):
        """Return the person record if we have a valid handle"""
        if self.person is None:
            self.person = self.report.database.get_person_from_handle(self.person_handle)
        return self.person

    def familyContinues(self, get_parents_handle):
        """Return true if this person has a primary family with at least a father or a mother"""
        family_handle = self.getPersonRecord().get_main_parents_family_handle()
        father_handle = mother_handle = None
        if family_handle:
            father_handle, mother_handle = get_parents_handle(family_handle)
        return family_handle is not None and (father_handle is not None or mother_handle is not None)

    def _getName(self):
        """Return the name formatted according to the user preferences.

        The length of the name is checked, and it will be trimmed if necessary.

        """
        name = name_displayer.display(self.person)
        width = cm2pt(self.report.max_box_size)
        name = fontscale.string_trim(self.report.get_font(self.title_style), name, width)
        return name

    def _getDateAndPlace(self, handle, event = None):
        date = place = None
        if handle is not None:
            event = self.report.database.get_event_from_handle(handle)
        if event is not None:
            date = gramps.gen.datehandler.get_date(event)
            place_handle = event.get_place_handle()
            if place_handle:
                place = place_displayer.display_event(self.report.database, event)
        return date, place

    def _makeContent(self, prefix, date, place):
        """Return a string formatted according to the user preferences.

        The length of the text is checked, and it will be trimmed if necessary.

        """
        separator1 = ' ' if date is not None or place is not None else ''
        separator2 = ' ' if date is not None and place is not None else ''
        text = prefix + separator1 + (date or _PLACEHOLDER) + separator2 + (place or _PLACEHOLDER)
        width = cm2pt(self.report.max_box_size)
        text = fontscale.string_trim(self.report.get_font(self.content_style), text, width)
        return text

    def getInformation(self, refresh=False):
        """Return a tuple with the name and content for this person.

        refresh - don't reuse cached information, re-read from the database
        """
        if self.name is None or self.content is None or refresh:
            person = self.getPersonRecord()
            if person is None: return "ERROR", ""

            self.name = self._getName()

            date = place = None
            birth_ref = person.get_birth_ref()
            if birth_ref is not None:
                for e_type, handle in birth_ref.get_referenced_handles():
                    if e_type == 'Event':
                        date, place = self._getDateAndPlace(handle)
            self.content = self._makeContent(self.birth_symbol, date, place)

            date = place = None
            if not self.isMother():
                # we don't repeat this information for the mother
                all_families = person.get_family_handle_list()
                if len(all_families) > 0:
                    family = self.report.database.get_family_from_handle(all_families[0])
                    for evt_ref in family.get_event_ref_list():
                        evt_handle = evt_ref.get_reference_handle()
                        evt = self.report.database.get_event_from_handle(evt_handle)
                        # Check for a marriage event
                        evt_t = evt.get_type()
                        if evt_t.is_marriage() or evt_t.is_marriage_fallback():
                            date, place = self._getDateAndPlace(None, evt)
                self.content += "\n" + self._makeContent(self.marriage_symbol, date, place)

            date = place = None
            death_ref = person.get_death_ref()
            if death_ref is not None:
                for e_type, handle in death_ref.get_referenced_handles():
                    if e_type == 'Event':
                        date, place = self._getDateAndPlace(handle)
            self.content += "\n" + self._makeContent(self.death_symbol, date, place)

        return self.name, self.content

    def getPos(self):
        """Return precalculated coordinates that are determined by the person's index"""
        # person's index determines which box they occupy on the page
        if self.index in self.report.coordinates:
            coord = self.report.coordinates[self.index]
        else:
            coord = None
        return coord

    def getSize(self, style, text):
        """
        Return a tuple with the height and width this person will occupy on the page
        """
        w = self.report.max_box_size
        lines = len(text.split("\n"))
        h = self.report.get_font_height(style) * 1.4 * lines
        return (w, h)

    def getDescendant(self):
        """
        Return the index of this person's descendant (one level up).
        """
        if self.isMother():
            descendant_index = (self.index - 1) / 2
        else:
            descendant_index = self.index / 2
        return descendant_index

    def isMother(self):
        """Return true if the previously generated index number is odd.

        Used to determine which way to draw lines and how to get back
        to the descendant.

        """
        result = self.index % 2 != 0
        return result

    def getRelationshipStyle(self, descendant_handle):
        """Returns a line style based on the birth status of this person.

        The check for birth status is based on the code from the
        GraphView add-on.
        """
        rel_style = 'PC-line'
        if self.person is None: return rel_style
        rel = None
        for family_handle in self.person.get_family_handle_list():
            family = self.report.database.get_family_from_handle(family_handle)
            for child_ref in family.get_child_ref_list():
                if child_ref.ref == descendant_handle:
                    if self.isMother():
                        rel = child_ref.mrel
                    else:
                        rel = child_ref.frel
                    break
        if rel is not None:
            if rel != ChildRefType.BIRTH:
                rel_style = 'PC-adopted_line'
        return rel_style

#------------------------------------------------------------------------
#
# PedigreeChart report
#
#------------------------------------------------------------------------
class PedigreeChart(Report):
    """Create an ancestor tree suitable for printing"""

    def __init__(self, database, options, user):
        """
        Initialize the report class.

        database        - the GRAMPS database instance
        options         - instance of the Options class for this report
        user            - a gramps.gen.user.User() instance

        """

        Report.__init__(self, database, options, user)

        menu = options.menu

        # BUG: somehow when calculating if we've reached the max
        # generations limit the report is stopping at one generation
        # before the max requested, so I'm bumping this up by one to
        # compensate until I find where the calculation is wrong.
        self.max_generations = menu.get_option_by_name('maxgen').get_value() + 1

        pid = menu.get_option_by_name('pid').get_value()
        self.center_person = database.get_person_from_gramps_id(pid)
        if self.center_person is None:
            raise ReportError(_("Person %s is not in the Database") % pid )

        self.show_parent_tags = menu.get_option_by_name('showcaptions').get_value()
        self.show_footer = menu.get_option_by_name('showfooter').get_value()

        # These now get calculated when the report is generated
        self.parent_tag_len = 0
        self.parent_tag_height = 0

        name = name_displayer.display_formal(self.center_person)
        self.title = _("Pedigree Chart for %s") % name

        self.map = {}
        self.page_number = PageCounter(1)
        self.page_link_counter = PageCounter(2)
        self.generation_index = 1

        page_width = self.doc.get_usable_width()
        page_height = self.doc.get_usable_height()

        self.columns = [_GUTTER_SIZE,
            page_width *  6 / 40,
            page_width * 12 / 40,
            page_width * 25 / 40,
            page_width * 32 / 40
            ]

        self.format_name = options.handler.format_name
        self.source_arrow_link_x = 0.3 if self.format_name == "odt" else 0.5

        #print "[DEBUG] page_width = %s, columns = %s" % (page_width, self.columns)

        # The third column (index 2) has the smallest space available, so I
        # base the box sizes on it.
        self.max_box_size = self.columns[3] - self.columns[2] - _GUTTER_SIZE

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

        self._prepare_symbols()

    def _prepare_symbols(self):
        symbols = Symbols()
        get_symbol_fallback = symbols.get_symbol_fallback
        birth = get_symbol_fallback(symbols.SYMBOL_BIRTH)
        marriage = get_symbol_fallback(symbols.SYMBOL_MARRIAGE)
        death = symbols.get_death_symbol_fallback(symbols.DEATH_SYMBOL_LATIN_CROSS)
        self.bmd_symbols = birth, marriage, death

    def write_report(self):
        """
        Create the report for the selected person
          1) start with the center person and generate the first page

          2) go through the map on the first page and select indexes 8-15 for
             the next pages

          3) continue with each subsequent page and generate lists there too

        """
        # Calculate the base size for locating each set of parents on the page
        self.parent_tag_len = pt2cm(self.doc.string_width(self.get_font('PC-box'), _("Mother")))
        self.parent_tag_height = self.get_font_height('PC-box')

        page_queue = deque([])
        # Generate the first page
        page_links = self._fill_page(self.center_person.get_handle())
        page_queue.append(page_links)
        while len(page_queue) > 0:
            page_links = page_queue.popleft()
            for person_handle in page_links.handlesByPage():
                new_links = self._fill_page(person_handle, page_links.depth, page_links.getSourcePage(person_handle))
                page_queue.append(new_links)

    def _fill_page(self, person_handle, depth = 0, source_page = None):
        """Create a tree of up to 15 people for this page

        person_handle - the base person for this page
        depth - the current generation depth, used to figure out when to stop
        source_page - the previous page where person_handle is listed

        """
        current_page = next(self.page_number)
        self.map = {}
        gen_limit = self.max_generations - (depth * _GENERATIONS_PER_PAGE)
        self._get_parents(person_handle, 1, gen_limit)
        # create links to subsequent pages, if we haven't reached the generation limit
        # TODO: need to check the generation limit before creating the links!
        #print '[DEBUG] depth = %2d, gen_limit = %2d, max_gen = %2d' % (depth, gen_limit, self.max_generations)
        # TODO: don't add duplicated pages when several ascendants share the same ancestors (typically marriage between cousins)
        # TODO: clickable page links for PDF document ?
        page_links = PageLinks(depth + 1, self.max_generations)
        # we only want to print the page if it shows more than one person
        if gen_limit > _MIN_PERSON_LIMIT:
            for i in range(_LINKS_BEGIN, _PEOPLE_PER_PAGE + 1):
                if i in self.map:
                    if self.map[i].familyContinues(self.get_parents_handle):
                        page_links.add(self.map[i].person_handle, current_page, next(self.page_link_counter))

            # generate the page
            self.doc.start_page()
            if current_page == 1:
                mark = IndexMark(self.title, INDEX_TYPE_TOC, 1)
                self.doc.center_text('PC-title', self.title,
                                     self.doc.get_usable_width() / 2, 0, mark=mark)
            else:
                self.doc.center_text('PC-title', self.title,
                                     self.doc.get_usable_width() / 2, 0)

            # print a link back to the source page (if any)
            if source_page is not None:
                self._draw_source_arrow(str(source_page))

            is_format_valid = _OUTPUT_FORMATS.get(self.format_name)
            for index in sorted(self.map.keys()):
                person_box = self.map[index]

                (x, y) = person_box.getPos()
                h = None

                # TODO: somehow extend this to all output formats allowing distinct style for names line
                if is_format_valid:
                    person_name, person_content = person_box.getInformation()
                    title_style, content_style = person_box.title_style, person_box.content_style

                    (tw, th) = person_box.getSize(title_style, person_name)
                    (w, h) = person_box.getSize(content_style, person_content)
                    # w = tw if tw > w else w
                    h = th + h

                    self.doc.draw_box(content_style, '', x, y, w, h)
                    self.doc.draw_text(title_style, person_name, x + 0.1, y + 0.07)
                    self.doc.draw_text(content_style, person_content, x + 0.2, y + th + 0.06)
                else:
                    person_name, person_content = person_box.getInformation()
                    content_style = person_box.content_style

                    text = person_name + "\n" + person_content
                    (w, h) = person_box.getSize(content_style, text)

                    self.doc.draw_box(content_style, text, x, y, w, h)

                # show a page link if it's there
                link_text = page_links.getLink(person_box.person_handle)
                if link_text != "":
                    self._draw_link_arrow(link_text, y, h)

                # draw the line back to the descendant box
                if x > self.columns[0]:
                    descendant = self.map[person_box.getDescendant()]
                    (dx, dy) = descendant.getPos()
                    dh = None
                    if is_format_valid:
                        descendant_name, descendant_content = descendant.getInformation()
                        (dtw, dth) = descendant.getSize(descendant.title_style, descendant_name)
                        (dw, dh) = descendant.getSize(descendant.content_style, descendant_content)
                        dh = dth + dh
                    else:
                        descendant_name, descendant_content = descendant.getInformation()
                        text = descendant_name + "\n" + descendant_content
                        (dw, dh) = descendant.getSize(descendant.content_style, text)
                    x1 = x
                    y1 = y + h / 2
                    x2 = dx + _LINE_X_OFFSET
                    if person_box.isMother():
                        y2 = dy + dh
                    else:
                        y2 = dy
                    # determine if this person is adopted and draw a
                    # dashed line if that is the case
                    line_style = person_box.getRelationshipStyle(descendant.person_handle)
                    self.doc.draw_line(line_style, x1, y1, x2, y1)
                    self.doc.draw_line(line_style, x2, y2, x2, y1)

                    if self.show_parent_tags:
                        if person_box.isMother():
                            tx = x - self.parent_tag_len
                            ty = y + (self.parent_tag_height * 3)
                            self.doc.draw_text('PC-caption', _('Mother'), tx, ty)
                        else:
                            tx = x - self.parent_tag_len
                            self.doc.draw_text('PC-caption', _('Father'), tx, y)
            # write out the footer
            if self.show_footer:
                footer = _("Page %d") % current_page
                footer_top = self.doc.get_usable_height() - self.get_font_height('PC-box') * 1.2
                self.doc.draw_text('PC-box', footer, 0, footer_top)

            self.doc.end_page()
        # return the list of links
        return page_links

    def get_parents_handle(self, family_handle):
        """Return father handle and mother handle"""
        family = self.database.get_family_from_handle(family_handle)
        return family.get_father_handle(), family.get_mother_handle()

    def _get_parents(self, person_handle, index, gen_limit):
        """
        Generate a list of the person's parents and their parents
        recursively up to max_generations.

        person_handle: the center person
        index: the current index position of this person
        gen_limit: maximum number of generations for this page

        This function is based on AncestorTree.apply_filter().

        """
        if (not person_handle) or (index >= _MAX_INDEX_PER_PAGE) or (index >= 2**gen_limit):
            return

        self.map[index] = PersonBox(index, person_handle, self)

        person = self.map[index].getPersonRecord()
        family_handle = person.get_main_parents_family_handle()
        if family_handle:
            father_handle, mother_handle = self.get_parents_handle(family_handle)
            self._get_parents(father_handle, index * 2, gen_limit)
            self._get_parents(mother_handle, index * 2 + 1, gen_limit)

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

    def _draw_source_arrow(self, link_text):
        """Draw a path on the document that 'points' back to the source page.

        link_text - a string with the page number.

        The position for this arrow is the same on every page.

        """
        # TODO: fix arrow position for SVG document
        link_x = self.source_arrow_link_x
        link_y = self.doc.get_usable_height() / 2 + _SOURCE_ARROW_OFFSET + self.get_font_height('PC-box')
        # reverse the direction of the arrow
        flip = np.matrix([[-1,  0], [ 0,  1]])
        left_arrow = _ARROW * flip
        # calculate the position of the arrow
        loc = np.matrix([link_x, link_y])
        path = left_arrow + loc
        self.doc.draw_path('PC-line', path.A)
        # write the text inside the arrow
        w = round(pt2cm(self.doc.string_width(self.get_font('PC-box'), link_text)), 1)
        link_x = link_x + 0.75 - w
        self.doc.draw_text('PC-box', link_text, link_x - 0.01, link_y + 0.06)

    def _draw_link_arrow(self, link_text, y, h):
        """Draw a path on the document that points to the next page
        where the ancestors continue.

        link_text - a string with the page number
        y - the vertical position of the referenced person box
        h - the height of the person box, used to calculate the arrows position

        """
        # TODO: fix arrow position for SVG document
        # calculate the size of the link text
        link_x = self.doc.get_usable_width() - 0.5
        link_y = y + h / 2
        # calculate the position of the arrow
        loc = np.matrix([link_x, link_y])
        path = _ARROW + loc
        self.doc.draw_path('PC-line', path.A)
        # write the text inside the arrow
        self.doc.draw_text('PC-box', link_text, link_x - 0.45, link_y + 0.06)

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
        self.__db = dbase
        self.__pid = None
        MenuReportOptions.__init__(self, name, dbase)

    def get_subject(self):
        """Return a string that describes the subject of the report."""
        if self.__pid is not None:
            gid = self.__pid.get_value()
            person = self.__db.get_person_from_gramps_id(gid)
            return name_displayer.display(person)
        else:
            return ""

    def add_menu_options(self, menu):
        """Add the menu options to the report dialog"""

        category_name = _("Tree Options")

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the tree"))
        menu.add_option(category_name, "pid", self.__pid)

        max_gen = NumberOption(_("Generations"), 10, 1, 50)
        max_gen.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "maxgen", max_gen)

        show_captions = BooleanOption(_("Show Mother/Father captions"), False)
        show_captions.set_help(_("Show the title of mother or father beside each ancestor's box."))
        menu.add_option(category_name, "showcaptions", show_captions)

        show_footer = BooleanOption(_("Show page numbers"), True)
        show_footer.set_help(_("Add a footer on every page with the page number and date printed."))
        menu.add_option(category_name, "showfooter", show_footer)

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

        f = docgen.FontStyle()
        f.set_size(9)
        f.set_type_face(docgen.FONT_SANS_SERIF)
        f.set_bold(1)
        p = docgen.ParagraphStyle()
        p.set_font(f)
        p.set_description(_('Style used for names (only for PDF document and PostScript).'))
        default_style.add_paragraph_style("PC-Name", p)

        f = docgen.FontStyle()
        f.set_size(8)
        f.set_type_face(docgen.FONT_SANS_SERIF)
        f.set_italic(1)
        p = docgen.ParagraphStyle()
        p.set_font(f)
        p.set_description(_('Style used for labels and captions.'))
        default_style.add_paragraph_style("PC-Caption", p)

        g = docgen.GraphicsStyle()
        g.set_paragraph_style("PC-Name")
        g.set_color((0, 0, 0))
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)
        default_style.add_draw_style("PC-box_title", g)

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
        g.set_paragraph_style("PC-Caption")
        g.set_color((0, 0, 0))
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)
        default_style.add_draw_style("PC-caption", g)

        g = docgen.GraphicsStyle()
        default_style.add_draw_style("PC-line", g)

        g = docgen.GraphicsStyle()
        g.set_line_style(docgen.DOTTED)
        default_style.add_draw_style("PC-adopted_line", g)
