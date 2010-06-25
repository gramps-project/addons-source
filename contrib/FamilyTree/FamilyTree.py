#
# Gramps - a GTK+/GNOME based genealogy program - Family Tree plugin
#
# Copyright (C) 2008,2009,2010 Reinhard Mueller
# Copyright (C) 2010 lcc <lcc.mailaddress@gmail.com>
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

"""Reports/Graphical Reports/Family Tree"""

#------------------------------------------------------------------------
#
# GRAMPS modules
#
#------------------------------------------------------------------------
import gen.display.name
from gen.lib import Date, Event, EventType, FamilyRelType, Name
import gen.plug.docgen
import gen.plug.menu
import gen.plug.report
from gen.plug.report.utils import pt2cm
import gui.plug.report
import DateHandler
from TransUtils import get_addon_translator
_ = get_addon_translator().gettext


#------------------------------------------------------------------------
#
# Constants
#
#------------------------------------------------------------------------
empty_birth = Event()
empty_birth.set_type(EventType.BIRTH)

empty_marriage = Event()
empty_marriage.set_type(EventType.MARRIAGE)


#------------------------------------------------------------------------
#
# FamilyTree report
#
#------------------------------------------------------------------------
class FamilyTree(gen.plug.report.Report):

    def __init__(self, database, options_class):

        gen.plug.report.Report.__init__(self, database, options_class)

        menu = options_class.menu

        family_id = menu.get_option_by_name('family_id').get_value()
        self.center_family = database.get_family_from_gramps_id(family_id)

        self.max_ancestor_generations = menu.get_option_by_name('max_ancestor_generations').get_value()
        self.max_descendant_generations = menu.get_option_by_name('max_descendant_generations').get_value()
        self.fit_on_page = menu.get_option_by_name('fit_on_page').get_value()
        self.color = menu.get_option_by_name('color').get_value()
        self.shuffle_colors = menu.get_option_by_name('shuffle_colors').get_value()
        self.callname = menu.get_option_by_name('callname').get_value()
        self.include_occupation = menu.get_option_by_name('include_occupation').get_value()
        self.include_residence = menu.get_option_by_name('include_residence').get_value()
        self.eventstyle_dead = menu.get_option_by_name('eventstyle_dead').get_value()
        self.eventstyle_living = menu.get_option_by_name('eventstyle_living').get_value()
        self.fallback_birth = menu.get_option_by_name('fallback_birth').get_value()
        self.fallback_death = menu.get_option_by_name('fallback_death').get_value()
        self.missinginfo = menu.get_option_by_name('missinginfo').get_value()
        self.include_event_description = menu.get_option_by_name('include_event_description').get_value()
        self.title = menu.get_option_by_name('title').get_value()
        self.footer = menu.get_option_by_name('footer').get_value()

        if not self.title:
            name = self.__family_get_display_name(self.center_family)
            self.title = _("Family Tree for %s") % name

        style_sheet = self.doc.get_style_sheet()
        self.line_width = pt2cm(style_sheet.get_draw_style("FTR-box").get_line_width())

        # Size constants, all in unscaled cm:
        # Size of shadow around boxes
        self.shadow = style_sheet.get_draw_style("FTR-box").get_shadow_space()
        # Offset from left
        self.xoffset = self.line_width / 2
        # Offset from top
        tfont = style_sheet.get_paragraph_style("FTR-Title").get_font()
        tfont_height = pt2cm(tfont.get_size()) * 1.2
        self.yoffset = tfont_height * 2
        # Space for footer
        ffont = style_sheet.get_paragraph_style("FTR-Footer").get_font()
        ffont_height = pt2cm(ffont.get_size()) * 1.2
        self.ybottom = ffont_height
        # Padding inside box == half size of shadow
        self.box_pad = self.shadow / 2
        # Gap between boxes == 2 times size of shadow
        self.box_gap = 2 * self.shadow
        # Width of a box (calculated in __build_*_tree)
        self.box_width = 0

        # Number of generations used (calculated in __build_*_tree)
        self.ancestor_generations = 0
        self.descendant_generations = 0

        # Number of colors used so far
        self.ancestor_max_color = 0
        self.descendant_max_color = 0

        self.ancestors_tree = self.__build_ancestors_tree(self.center_family.get_handle(), 0, 0, 0, 0)
        (self.descendants_tree, descendants_space) = self.__build_descendants_tree(self.center_family.get_child_ref_list(), 0, 0, 0)

        needed_width = self.xoffset + (self.ancestor_generations + self.descendant_generations) * (self.box_width + 2 * self.box_gap) - 2 * self.box_gap + self.shadow
        needed_height = self.yoffset + max(self.ancestors_tree['space'], descendants_space) + self.shadow + self.ybottom * 2

        usable_width = self.doc.get_usable_width()
        usable_height = self.doc.get_usable_height()

        if self.fit_on_page:
            self.scale = min(
                    usable_height / needed_height,
                    usable_width / needed_width)
            self.__scale_styles()
            # Convert usable size into unscaled cm
            usable_width = usable_width / self.scale
            usable_height = usable_height / self.scale
        else:
            self.scale = 1

        # Center the whole tree on the usable page area
        self.xoffset += (usable_width - needed_width) / 2
        self.yoffset += (usable_height - needed_height) / 2

        # Since center person has an x of 0, add space needed by ancestors
        self.xoffset += (self.ancestor_generations - 1) * (self.box_width + 2 * self.box_gap)

        # Align ancestors part and descendants part vertically
        root_a = self.ancestors_tree['top'] + self.ancestors_tree['height'] / 2
        root_d = descendants_space / 2
        if root_a > root_d:
            self.yoffset_a = self.yoffset
            self.yoffset_d = self.yoffset + root_a - root_d
        else:
            self.yoffset_a = self.yoffset + root_d - root_a
            self.yoffset_d = self.yoffset


    def write_report(self):

        self.doc.start_page()

        self.doc.center_text('FTR-title',
                self.title,
                self.doc.get_usable_width() / 2,
                0)

        self.__print_ancestors_tree(self.ancestors_tree, 0)

        anchor = self.yoffset_a + self.ancestors_tree['top'] + self.ancestors_tree['height'] / 2
        self.__print_descendants_tree(self.descendants_tree, anchor, 1)

        self.doc.center_text('FTR-footer',
                self.footer,
                self.doc.get_usable_width() / 2,
                self.doc.get_usable_height() - self.ybottom * self.scale)

        self.doc.end_page()


    def __build_ancestors_tree(self, family_handle, generation, color, top, center):
        """Build an in-memory data structure containing all ancestors"""

        self.ancestor_generations = max(self.ancestor_generations, generation + 1)

        # This is a dictionary containing all interesting data for a box that
        # will be printed later:
        # text: text to be printed in the box, as a list of (style, text) tuples
        # top: top edge of the box in unscaled cm
        # height: height of the box in unscaled cm
        # space: total height that this box and all its ancestor boxes (left to
        #     it) need, in unscaled cm
        # anchor: y position to where the line right of this box should end
        # mother_node: dictionary representing the box with the mother's
        #     ancestors
        # father_node: dictionary representing the box with the father's
        #     ancestors
        family_node = {}

        family = self.database.get_family_from_handle(family_handle)
        if family.private:
            return None

        father_handle = family.get_father_handle()
        if father_handle:
            father = self.database.get_person_from_handle(father_handle)
            if father.private:
                father = None
        else:
            father = None
        if father:
            father_text = [('FTR-name', self.__person_get_display_name(father))] + [('FTR-data', p) for p in self.__person_get_display_data(father)]
            father_height = self.__make_space(father_text)
            father_family = father.get_main_parents_family_handle()
        else:
            father_text = []
            father_height = 0
            father_family = None

        mother_handle = family.get_mother_handle()
        if mother_handle:
            mother = self.database.get_person_from_handle(mother_handle)
            if mother.private:
                mother = None
        else:
            mother = None
        if mother:
            mother_text = [('FTR-name', self.__person_get_display_name(mother))] + [('FTR-data', p) for p in self.__person_get_display_data(mother)]
            mother_height = self.__make_space(mother_text)
            mother_family = mother.get_main_parents_family_handle()
        else:
            mother_text = []
            mother_height = 0
            mother_family = None

        family_node['text'] = father_text + [('FTR-data', p) for p in self.__family_get_display_data(family)] + mother_text
        family_node['color'] = color
        family_node['height'] = self.__make_space(family_node['text'])

        # If this box is small, align it centered, if it is too big for that,
        # align it to the top.
        family_node['top'] = max(top, center - family_node['height'] / 2)

        father_node = None
        if father_family and generation < self.max_ancestor_generations:
            if (self.color == FamilyTreeOptions.COLOR_FEMALE_LINE) or \
                    (self.color == FamilyTreeOptions.COLOR_FIRST_GEN and generation == 0) or \
                    (self.color == FamilyTreeOptions.COLOR_SECOND_GEN and generation == 1) or \
                    (self.color == FamilyTreeOptions.COLOR_THIRD_GEN and generation == 2):
                self.ancestor_max_color += 1
                father_color = self.ancestor_max_color
            else:
                father_color = color
            # Where should the father's box be placed?
            father_top = top
            father_center = family_node['top'] + father_height / 2
            # Create father's box.
            father_node = self.__build_ancestors_tree(father_family, generation + 1, father_color, father_top, father_center)
        if father_node:
            if mother_family and not self.database.get_family_from_handle(mother_family).private:
                # This box has father and mother: move it down so its center is
                # just at the end of the father's ancestors space.
                family_node['top'] = max(family_node['top'], top + father_node['space'] + self.box_gap / 2 - family_node['height'] / 2)
            else:
                # This box has only father: move it down to the center of the
                # father's parents.
                family_node['top'] = max(family_node['top'], father_node['top'] + father_node['height'] / 2 - father_height / 2)

        mother_node = None
        if mother_family and generation < self.max_ancestor_generations:
            if (self.color == FamilyTreeOptions.COLOR_MALE_LINE) or \
                    (self.color == FamilyTreeOptions.COLOR_MALE_LINE_WEAK and family.get_relationship() != FamilyRelType.UNMARRIED) or \
                    (self.color == FamilyTreeOptions.COLOR_FIRST_GEN and generation == 0) or \
                    (self.color == FamilyTreeOptions.COLOR_SECOND_GEN and generation == 1) or \
                    (self.color == FamilyTreeOptions.COLOR_THIRD_GEN and generation == 2):
                self.ancestor_max_color += 1
                mother_color = self.ancestor_max_color
            else:
                mother_color = color
            # Where should the mother's box be placed?
            if father_handle:
                # There is also a father: mother's box must be below the center
                # of this box.
                mother_top = family_node['top'] + family_node['height'] / 2 + self.box_gap / 2
            else:
                # There is no father: mother's box can use all the vertical
                # space of this box.
                mother_top = top
            mother_center = family_node['top'] + family_node['height'] - mother_height / 2
            # Create mother's box.
            mother_node = self.__build_ancestors_tree(mother_family, generation + 1, mother_color, mother_top, mother_center)
        if mother_node:
            # If this family is only a mother, move her down to the center of
            # her parents box.
            if not father_node:
                family_node['top'] = max(family_node['top'], mother_node['top'] + mother_node['height'] / 2 - (family_node['height'] - mother_height / 2))

        bottom = family_node['top'] + family_node['height']
        if father_node:
            bottom = max(bottom, father_top + father_node['space'])
        if mother_node:
            bottom = max(bottom, mother_top + mother_node['space'])
        family_node['space'] = bottom - top
        family_node['father_node'] = father_node
        family_node['mother_node'] = mother_node
        if father_node:
            father_node['anchor'] = family_node['top'] + father_height / 2
        if mother_node:
            mother_node['anchor'] = family_node['top'] + family_node['height'] - mother_height / 2

        return family_node


    def __build_descendants_tree(self, person_ref_list, generation, color, top):
        """Build an in-memory data structure containing all descendants"""

        if generation >= self.max_descendant_generations:
            return ([], 0)

        self.descendant_generations = max(self.descendant_generations, generation + 1)

        node_list = []
        space = 0
        for person_ref in person_ref_list:
            if person_ref.private:
                continue

            # This is a dictionary containing all interesting data for a box
            # that contains a single person.
            # text: text to be printed in the box, as a list of (style, text)
            #     tuples
            # color: background color to be used for this box
            # top: top edge of the box in unscaled cm
            # height: height of the box in unscaled cm
            # space: total height that this box, all the family boxes of this
            #      person and all its descendant boxes (right to it) need, in
            #      unscaled cm
            # family_list: list of family_node style dictionaries containing
            #     families in which this person is a parent.
            # If the person has at least one family in which it is parent, this
            # box will actually not be printed, but all the boxes in the
            # family_list.
            person_node = {}

            person = self.database.get_person_from_handle(person_ref.ref)
            if person.private:
                continue

            person_node['text'] = [('FTR-name', self.__person_get_display_name(person))] + [('FTR-data', p) for p in self.__person_get_display_data(person)]
            if (self.color == FamilyTreeOptions.COLOR_FIRST_GEN and generation == 0) or \
                    (self.color == FamilyTreeOptions.COLOR_SECOND_GEN and generation == 1) or \
                    (self.color == FamilyTreeOptions.COLOR_THIRD_GEN and generation == 2):
                self.descendant_max_color += 1
                person_node['color'] = self.descendant_max_color
            else:
                person_node['color'] = color
            person_node['top'] = top + space
            person_node['height'] = self.__make_space(person_node['text'])
            person_node['family_list'] = []
            person_node['space'] = 0
            family_top = person_node['top']
            family_handles = person.get_family_handle_list()
            for family_handle in family_handles:

                family = self.database.get_family_from_handle(family_handle)
                if family.private:
                    continue

                # This is a dictionary containing all interesting data for a
                # box that contains the parents of a family.
                # text: text to be printed in the box, as a list of (style,
                #     text) tuples
                # color: background color for this box
                # top: top edge of the box in unscaled cm
                # height: height of the box in unscaled cm
                # space: total height that this box and all the descendant
                #      boxes of this family (right to it) need, in unscaled cm
                # child_list: list of person_node style dictionaries containing
                #      the children of this family.
                family_node = {}
                family_node['text'] = [('FTR-data', p) for p in self.__family_get_display_data(family)]

                father_handle = family.get_father_handle()
                mother_handle = family.get_mother_handle()
                if person_ref.ref == father_handle:
                    spouse_handle = mother_handle
                else:
                    spouse_handle = father_handle

                if len(family_handles) > 1:
                    spouse_number = unichr(0x2160 + len(person_node['family_list'])) + ". "
                else:
                    spouse_number = ""
                if spouse_handle is not None:
                    spouse = self.database.get_person_from_handle(spouse_handle)
                    
                    family_node['text'] += [('FTR-name', spouse_number + self.__person_get_display_name(spouse))] + [('FTR-data', p) for p in self.__person_get_display_data(spouse)]
                elif spouse_number:
                    family_node['text'] += [('FTR-name', spouse_number)]
                # Include data of the actual person in the first family box.
                if not person_node['family_list']:
                    family_node['text'] = person_node['text'] + family_node['text']
                # Decide if a new color is needed.
                if (self.color == FamilyTreeOptions.COLOR_MALE_LINE and person_ref.ref == mother_handle) or \
                        (self.color == FamilyTreeOptions.COLOR_MALE_LINE_WEAK and person_ref.ref == mother_handle and family.get_relationship() != FamilyRelType.UNMARRIED) or \
                        (self.color == FamilyTreeOptions.COLOR_FEMALE_LINE and person_ref.ref == father_handle):
                    self.descendant_max_color += 1
                    family_node['color'] = self.descendant_max_color
                else:
                    family_node['color'] = person_node['color']
                family_node['top'] = family_top
                family_node['height'] = self.__make_space(family_node['text'])
                (family_node['child_list'], children_space) = self.__build_descendants_tree(family.get_child_ref_list(), generation + 1, family_node['color'], family_top)
                family_node['space'] = max(family_node['height'], children_space)
                # Vertically center parents within the space their descendants
                # use.
                family_node['top'] += (family_node['space'] - family_node['height']) / 2
                # This is where the next family will start
                family_top += family_node['space'] + self.box_gap

                person_node['family_list'].append(family_node)
                if person_node['space'] > 0:
                    person_node['space'] += self.box_gap
                person_node['space'] += family_node['space']

            if person_node['space'] == 0:
                person_node['space'] = person_node['height']
            if person_node['family_list']:
                person_node['top'] = person_node['family_list'][0]['top']

            node_list.append(person_node)
            space += person_node['space'] + self.box_gap

        return (node_list, space - self.box_gap)


    def __print_ancestors_tree(self, family_node, generation):

        self.__draw_box(family_node['text'], family_node['color'], self.ancestor_max_color + 1, generation, self.yoffset_a + family_node['top'], family_node['height'])

        for parent_node in [family_node['father_node'], family_node['mother_node']]:
            if not parent_node:
                continue

            self.__print_ancestors_tree(parent_node, generation - 1)

            y1 = self.yoffset_a + parent_node['anchor']
            y2 = self.yoffset_a + parent_node['top'] + parent_node['height'] / 2
            x1 = self.xoffset + generation * (self.box_width + 2 * self.box_gap)
            x2 = x1 - self.box_gap
            x3 = x2 - self.box_gap
            self.doc.draw_line("FTR-line",
                    self.scale * x1,
                    self.scale * y1,
                    self.scale * x2,
                    self.scale * y1)
            self.doc.draw_line("FTR-line",
                    self.scale * x2,
                    self.scale * y1,
                    self.scale * x2,
                    self.scale * y2)
            self.doc.draw_line("FTR-line",
                    self.scale * x2,
                    self.scale * y2,
                    self.scale * x3,
                    self.scale * y2)


    def __print_descendants_tree(self, person_node_list, anchor, generation):

        if not person_node_list:
            return

        x3 = self.xoffset + (generation) * (self.box_width + 2 * self.box_gap)
        x2 = x3 - self.box_gap
        x1 = x2 - self.box_gap
        self.doc.draw_line("FTR-line",
                self.scale * x1,
                self.scale * anchor,
                self.scale * x2,
                self.scale * anchor)
        self.doc.draw_line("FTR-line",
                self.scale * x2,
                self.scale * min(self.yoffset_d + person_node_list[0]['top'] + person_node_list[0]['height'] / 2, anchor),
                self.scale * x2,
                self.scale * max(self.yoffset_d + person_node_list[-1]['top'] + person_node_list[-1]['height'] / 2, anchor))

        for person_node in person_node_list:
            self.doc.draw_line("FTR-line",
                    self.scale * x2,
                    self.scale * (self.yoffset_d + person_node['top'] + person_node['height'] / 2),
                    self.scale * x3,
                    self.scale * (self.yoffset_d + person_node['top'] + person_node['height'] / 2))
            if person_node['family_list']:
                last_bottom = 0
                for family_node in person_node['family_list']:
                    if last_bottom > 0:
                        x = self.xoffset + generation * (self.box_width + 2 * self.box_gap) + self.box_width / 2
                        self.doc.draw_line("FTR-line",
                                self.scale * x,
                                self.scale * last_bottom,
                                self.scale * x,
                                self.scale * (self.yoffset_d + family_node['top']))
                    last_bottom = self.yoffset_d + family_node['top'] + family_node['height']
                    self.__draw_box(family_node['text'], family_node['color'], self.descendant_max_color + 1, generation, self.yoffset_d + family_node['top'], family_node['height'])
                    if family_node['child_list']:
                        self.__print_descendants_tree(
                                family_node['child_list'], 
                                self.yoffset_d + family_node['top'] + family_node['height'] / 2,
                                generation + 1)
            else:
                self.__draw_box(person_node['text'], person_node['color'], self.descendant_max_color + 1, generation, self.yoffset_d + person_node['top'], person_node['height'])


    # -------------------------------------------------------------------
    # Scaling methods
    # -------------------------------------------------------------------

    def __scale_styles(self):
        """
        Scale the styles for this report.
        """
        style_sheet = self.doc.get_style_sheet()

        self.__scale_font(style_sheet, "FTR-Title")
        self.__scale_font(style_sheet, "FTR-Name")
        self.__scale_font(style_sheet, "FTR-Data")
        self.__scale_font(style_sheet, "FTR-Footer")

        self.__scale_line_width(style_sheet, "FTR-box")
        self.__scale_line_width(style_sheet, "FTR-line")

        self.doc.set_style_sheet(style_sheet)


    def __scale_font(self, style_sheet, style_name):
        p = style_sheet.get_paragraph_style(style_name)
        font = p.get_font()
        font.set_size(font.get_size() * self.scale)
        p.set_font(font)
        style_sheet.add_paragraph_style(style_name, p)


    def __scale_line_width(self, style_sheet, style_name):
        g = style_sheet.get_draw_style(style_name)
        g.set_shadow(g.get_shadow(), g.get_shadow_space() * self.scale)
        g.set_line_width(g.get_line_width() * self.scale)
        style_sheet.add_draw_style(style_name, g)


    # -------------------------------------------------------------------
    # Drawing methods
    # -------------------------------------------------------------------

    def __make_space(self, text):

        h = 0
        for (style_name, line) in text:
            w = pt2cm(self.doc.string_width(self.__get_font(style_name), line.replace("<u>", "").replace("</u>", "")))
            self.box_width = max(self.box_width, w)
            h += self.__get_font_height(style_name) * 1.2
        return h + 2 * self.box_pad


    def __draw_box(self, text, color, color_count, generation, top, height):

        if self.color == FamilyTreeOptions.COLOR_GENERATION:
            col = self.descendant_generations - generation
            col_count = self.ancestor_generations + self.descendant_generations
        else:
            col = color
            col_count = color_count

        if self.color != FamilyTreeOptions.COLOR_NONE:
            self.__set_fill_color("FTR-box", col, col_count)

        box_x = self.xoffset + generation * (self.box_width + 2 * self.box_gap)
        box_y = top

        self.doc.draw_box("FTR-box",
                "",
                self.scale * box_x,
                self.scale * box_y,
                self.scale * self.box_width,
                self.scale * height)

        x = self.scale * (box_x + self.box_pad)
        y = self.scale * (box_y + self.box_pad)
        for (style_name, line) in text:
            self.doc.draw_text(style_name, line, x, y)
            y += self.__get_font_height(style_name) * 1.2


    def __get_font_height(self, style_name):

        return pt2cm(self.__get_font(style_name).get_size())


    def __get_font(self, style_name):

        style_sheet = self.doc.get_style_sheet()
        draw_style = style_sheet.get_draw_style(style_name)
        paragraph_style_name = draw_style.get_paragraph_style()
        paragraph_style = style_sheet.get_paragraph_style(paragraph_style_name)
        return paragraph_style.get_font()


    # -------------------------------------------------------------------
    # Person name and data formatting methods
    # -------------------------------------------------------------------

    def __family_get_display_name(self, family):

        father_handle = family.get_father_handle()
        mother_handle = family.get_mother_handle()

        father = self.database.get_person_from_handle(father_handle)
        mother = self.database.get_person_from_handle(mother_handle)

        if father:
            father_name = self.__person_get_display_name(father)
        else:
            father_name = _("Unknown")

        if mother:
            mother_name = self.__person_get_display_name(mother)
        else:
            mother_name = _("Unknown")

        return _("%(father)s and %(mother)s") % {
                'father': father_name,
                'mother': mother_name}


    def __person_get_display_name(self, person):

        if person.get_primary_name().private:
            return _("Anonymous")

        # Make a copy of the name object so we don't mess around with the real
        # data.
        n = Name(source=person.get_primary_name())

        if self.missinginfo:
            if not n.first_name:
                n.first_name = "____________"
            if not n.surname:
                n.surname = "____________"

        if n.call:
            if self.callname == FamilyTreeOptions.CALLNAME_REPLACE:
                n.first_name = n.call
            elif self.callname == FamilyTreeOptions.CALLNAME_UNDERLINE_ADD:
                if n.call in n.first_name:
                    (before, after) = n.first_name.split(n.call)
                    n.first_name = "%(before)s<u>%(call)s</u>%(after)s" % {
                            'before': before,
                            'call': n.call,
                            'after': after}
                else:
                    n.first_name = "\"%(call)s\" (%(first)s)" % {
                            'call':  n.call,
                            'first': n.first_name}

        return gen.display.name.displayer.display_name(n)


    def __person_get_display_data(self, person):

        result = []

        occupations = []
        baptism = None
        residences = []
        burial = None
        cremation = None

        for event_ref in person.get_event_ref_list():
            if event_ref.private:
                continue
            event = self.database.get_event_from_handle(event_ref.ref)
            if event.private:
                continue
            if event.get_type() == EventType.OCCUPATION:
                occupations.append(event.description)
            elif event.get_type() == EventType.BAPTISM:
                baptism = event
            elif event.get_type() == EventType.RESIDENCE:
                residences.append(event)
            elif event.get_type() == EventType.BURIAL:
                burial = event
            elif event.get_type() == EventType.CREMATION:
                cremation = event

        if self.include_occupation and occupations:
            result.append(', '.join(occupations))

        birth_ref = person.get_birth_ref()
        death_ref = person.get_death_ref()

        if birth_ref:
            if birth_ref.private:
                birth = None
            else:
                birth = self.database.get_event_from_handle(birth_ref.ref)
        elif not self.fallback_birth or baptism is None:
            birth = empty_birth
        else:
            birth = None
        if birth and birth.private:
            birth = None

        if death_ref and not death_ref.private:
            death = self.database.get_event_from_handle(death_ref.ref)
        else:
            death = None
        if death and death.private:
            death = None
        if death:
            eventstyle = self.eventstyle_dead
        else:
            eventstyle = self.eventstyle_living

        if eventstyle == FamilyTreeOptions.EVENTSTYLE_DATEPLACE:
            if birth is not None:
                result.extend(self.__event_get_display_data(birth))
            elif self.fallback_birth and baptism is not None:
                result.extend(self.__event_get_display_data(baptism))
            if self.include_residence:
                for residence in residences:
                    result.extend(self.__event_get_display_data(residence))
            if death:
                result.extend(self.__event_get_display_data(death))
            elif self.fallback_death and burial is not None:
                result.extend(self.__event_get_display_data(burial))
            elif self.fallback_death and cremation is not None:
                result.extend(self.__event_get_display_data(cremation))
        elif eventstyle != FamilyTreeOptions.EVENTSTYLE_NONE:
            if birth is None and self.fallback_birth:
                birth = baptism
            if death is None and self.fallback_death:
                death = burial
            if death is None and self.fallback_death:
                death = cremation
            if birth:
                birth_text = self.__date_get_display_text(birth.get_date_object(), eventstyle)
            else:
                birth_text = None
            if death:
                death_text = self.__date_get_display_text(death.get_date_object(), eventstyle)
            else:
                death_text = None
            if birth_text:
                if death_text:
                    result.append(u"%s - %s" % (birth_text, death_text))
                else:
                    result.append(u"* %s" % birth_text)
            else:
                if death_text:
                    result.append(u"\u271D %s" % death_text)

        return result


    def __family_get_display_data(self, family):

        marriage = None
        divorce = None
        residences = []

        for event_ref in family.get_event_ref_list():
            if event_ref.private:
                continue
            event = self.database.get_event_from_handle(event_ref.ref)
            if event.private:
                continue
            if event.get_type() == EventType.MARRIAGE:
                marriage = event
            elif event.get_type() == EventType.RESIDENCE:
                residences.append(event)
            elif event.get_type() == EventType.DIVORCE:
                divorce = event

        if family.get_relationship() == FamilyRelType.MARRIED and not marriage:
            marriage = empty_marriage

        eventstyle = self.eventstyle_dead
        father_handle = family.get_father_handle()
        if father_handle:
            father = self.database.get_person_from_handle(father_handle)
            if not father.get_death_ref():
                eventstyle = self.eventstyle_living
        mother_handle = family.get_mother_handle()
        if mother_handle:
            mother = self.database.get_person_from_handle(mother_handle)
            if not mother.get_death_ref():
                eventstyle = self.eventstyle_living

        if eventstyle == FamilyTreeOptions.EVENTSTYLE_NONE:
            return []
        elif eventstyle == FamilyTreeOptions.EVENTSTYLE_DATEPLACE:
            result = []
            if marriage:
                result.extend(self.__event_get_display_data(marriage))
            if self.include_residence:
                for residence in residences:
                    result.extend(self.__event_get_display_data(residence))
            if divorce:
                result.extend(self.__event_get_display_data(divorce))
            return result
        else:
            if marriage:
                marriage_text = self.__date_get_display_text(marriage.get_date_object(), eventstyle)
            else:
                marriage_text = None
            if divorce:
                divorce_text = self.__date_get_display_text(divorce.get_date_object(), eventstyle)
            else:
                divorce_text = None
            if marriage_text:
                if divorce_text:
                    return [u"\u26AD %s - %s" % (marriage_text, divorce_text)]
                else:
                    return [u"\u26AD %s" % marriage_text]
            else:
                if divorce_text:
                    return [u"\u26AE %s" % divorce_text]
                else:
                    return []


    def __event_get_display_data(self, event):

        if event.get_type() == EventType.BIRTH:
            event_text = _("born")
        elif event.get_type() == EventType.BAPTISM:
            event_text = _("baptised")
        elif event.get_type() == EventType.DEATH:
            event_text = _("died")
        elif event.get_type() == EventType.BURIAL:
            event_text = _("buried")
        elif event.get_type() == EventType.CREMATION:
            event_text = _("cremated")
        elif event.get_type() == EventType.MARRIAGE:
            event_text = _("married")
        elif event.get_type() == EventType.DIVORCE:
            event_text = _("divorced")
        elif event.get_type() == EventType.RESIDENCE:
            event_text = _("resident")

        date = event.get_date_object()
        date_text = DateHandler.displayer.display(date)

        if date.get_modifier() == Date.MOD_NONE and date.get_quality() == Date.QUAL_NONE:
            if date.get_day_valid():
                date_text = _("on %(ymd_date)s") % {'ymd_date': date_text}
            elif date.get_month_valid():
                date_text = _("in %(ym_date)s") % {'ym_date': date_text}
            elif date.get_year_valid():
                date_text = _("in %(y_date)s") % {'y_date': date_text}

        if self.missinginfo:
            if date.is_empty():
                date_text = _("on %(placeholder)s") % {
                        'placeholder': "__________"}
            elif not date.is_regular():
                date_text = _("on %(placeholder)s (%(partial)s)") % {
                        'placeholder': "__________",
                        'partial': date_text}

        place_handle = event.get_place_handle()
        if place_handle:
            place = self.database.get_place_from_handle(place_handle)
            if place.private:
                place_text = ""
            else:
                place_text = place.get_title()
        elif self.missinginfo:
            place_text = "____________"
        else:
            place_text = ""

        if place_text:
            place_text = _("in %(place)s") % {'place': place_text}

        if not date_text and not place_text:
            return []

        result = event_text
        if date_text:
            result += " " + date_text
        if place_text:
            result += " " + place_text
        if self.include_event_description and event.description:
            result += " " + _("(%(description)s)") % {
                    'description': event.description}
        return [result]


    def __date_get_display_text(self, date, eventstyle):

        if not date:
            return None
        elif eventstyle == FamilyTreeOptions.EVENTSTYLE_YEARONLY:
            year = date.get_year()
            if year:
                return str(year)
            else:
                return None
        else:
            return DateHandler.displayer.display(date)


    # -------------------------------------------------------------------
    # Person name and data formatting methods
    # -------------------------------------------------------------------

    def __set_fill_color(self, style_name, number, count):

        darkness = 32
        if self.shuffle_colors:
            number = int(number * (count + 1) / int(pow(count, 0.5))) % count
        index = (count / 2.0 + number) % count
        step = darkness * 3.0 / count
        r = min(index, abs(index - count))
        g = abs(index - (count / 3.0))
        b = abs(index - (2 * count / 3.0))
        r = 255 - (darkness - r * step)
        g = 255 - (darkness - g * step)
        b = 255 - (darkness - b * step) * 2

        style_sheet = self.doc.get_style_sheet()
        draw_style = style_sheet.get_draw_style(style_name)
        draw_style.set_fill_color((r, g, b))
        style_sheet.add_draw_style(style_name, draw_style)
        self.doc.set_style_sheet(style_sheet)


#------------------------------------------------------------------------
#
# FamilyTreeOptions
#
#------------------------------------------------------------------------
class FamilyTreeOptions(gui.plug.report.MenuReportOptions):

    CALLNAME_DONTUSE = 0
    CALLNAME_REPLACE = 1
    CALLNAME_UNDERLINE_ADD = 2

    EVENTSTYLE_NONE = 0
    EVENTSTYLE_YEARONLY = 1
    EVENTSTYLE_DATE = 2
    EVENTSTYLE_DATEPLACE = 3

    COLOR_NONE = 0
    COLOR_GENERATION = 1
    COLOR_FIRST_GEN = 2
    COLOR_SECOND_GEN = 3
    COLOR_THIRD_GEN = 4
    COLOR_MALE_LINE = 5
    COLOR_MALE_LINE_WEAK = 6
    COLOR_FEMALE_LINE = 7


    def __init__(self, name, dbase):
        gui.plug.report.MenuReportOptions.__init__(self, name, dbase)


    def add_menu_options(self, menu):
        """
        Add options to the menu for the descendant report.
        """
        category_name = _("Tree Options")

        family_id = gen.plug.menu.FamilyOption(_("Center Family"))
        family_id.set_help(_("The center family for the tree"))
        menu.add_option(category_name, "family_id", family_id)

        max_ancestor_generations = gen.plug.menu.NumberOption(_("Ancestor Generations"), 5, 0, 50)
        max_ancestor_generations.set_help(_("The number of ancestor generations to include in the tree"))
        menu.add_option(category_name, "max_ancestor_generations", max_ancestor_generations)

        max_descendant_generations = gen.plug.menu.NumberOption(_("Descendant Generations"), 10, 0, 50)
        max_descendant_generations.set_help(_("The number of descendant generations to include in the tree"))
        menu.add_option(category_name, "max_descendant_generations", max_descendant_generations)

        fit_on_page = gen.plug.menu.BooleanOption(_("Sc_ale to fit on a single page"), True)
        fit_on_page.set_help(_("Whether to scale to fit on a single page."))
        menu.add_option(category_name, 'fit_on_page', fit_on_page)

        color = gen.plug.menu.EnumeratedListOption(_("Color"), self.COLOR_NONE)
        color.set_items([
            (self.COLOR_NONE, _("No color")),
            (self.COLOR_GENERATION, _("Generations")),
            (self.COLOR_FIRST_GEN, _("First generation")),
            (self.COLOR_SECOND_GEN, _("Second generation")),
            (self.COLOR_THIRD_GEN, _("Third generation")),
            (self.COLOR_MALE_LINE, _("Male line")),
            (self.COLOR_MALE_LINE_WEAK, _("Male line and illegitimate children")),
            (self.COLOR_FEMALE_LINE, _("Female line"))])
        menu.add_option(category_name, "color", color)

        shuffle_colors = gen.plug.menu.BooleanOption(_("Shuffle colors"), False)
        shuffle_colors.set_help(_("Whether to shuffle colors or order them in rainbow fashion."))
        menu.add_option(category_name, "shuffle_colors", shuffle_colors)

        category_name = _("Content")

        callname = gen.plug.menu.EnumeratedListOption(_("Use call name"), self.CALLNAME_DONTUSE)
        callname.set_items([
            (self.CALLNAME_DONTUSE, _("Don't use call name")),
            (self.CALLNAME_REPLACE, _("Replace first name with call name")),
            (self.CALLNAME_UNDERLINE_ADD, _("Underline call name in first name / add call name to first name"))])
        menu.add_option(category_name, "callname", callname)

        include_occupation = gen.plug.menu.BooleanOption(_("Include Occupation"), True)
        menu.add_option(category_name, 'include_occupation', include_occupation)

        include_residence = gen.plug.menu.BooleanOption(_("Include Residence"), True)
        menu.add_option(category_name, 'include_residence', include_residence)

        eventstyle_dead = gen.plug.menu.EnumeratedListOption(_("Print event data (dead person)"), self.EVENTSTYLE_DATEPLACE)
        eventstyle_dead.set_items([
            (self.EVENTSTYLE_NONE, _("None")),
            (self.EVENTSTYLE_YEARONLY, _("Year only")),
            (self.EVENTSTYLE_DATE, _("Full date")),
            (self.EVENTSTYLE_DATEPLACE, _("Full date and place"))])
        menu.add_option(category_name, "eventstyle_dead", eventstyle_dead)

        eventstyle_living = gen.plug.menu.EnumeratedListOption(_("Print event data (living person)"), self.EVENTSTYLE_DATEPLACE)
        eventstyle_living.set_items([
            (self.EVENTSTYLE_NONE, _("None")),
            (self.EVENTSTYLE_YEARONLY, _("Year only")),
            (self.EVENTSTYLE_DATE, _("Full date")),
            (self.EVENTSTYLE_DATEPLACE, _("Full date and place"))])
        menu.add_option(category_name, "eventstyle_living", eventstyle_living)

        fallback_birth = gen.plug.menu.BooleanOption(_("Fall back to baptism if birth event missing"), True)
        menu.add_option(category_name, 'fallback_birth', fallback_birth)

        fallback_death = gen.plug.menu.BooleanOption(_("Fall back to burial or cremation if death event missing"), True)
        menu.add_option(category_name, 'fallback_death', fallback_death)

        # Fixme: the following 2 options should only be available if "Full date
        # and place" is selected above.
        missinginfo = gen.plug.menu.BooleanOption(_("Print fields for missing information"), True)
        missinginfo.set_help(_("Whether to include fields for missing information."))
        menu.add_option(category_name, "missinginfo", missinginfo)

        include_event_description = gen.plug.menu.BooleanOption(_("Include event description"), True)
        menu.add_option(category_name, 'include_event_description', include_event_description)

        category_name = _("Text Options")

        title = gen.plug.menu.StringOption(_("Title text"), "")
        menu.add_option(category_name, "title", title)

        footer = gen.plug.menu.StringOption(_("Footer text"), "")
        menu.add_option(category_name, "footer", footer)


    def make_default_style(self,default_style):
        """Make the default output style for the Ancestor Tree."""

        ## Paragraph Styles:
        f = gen.plug.docgen.FontStyle()
        f.set_size(13)
        f.set_type_face(gen.plug.docgen.FONT_SANS_SERIF)
        p = gen.plug.docgen.ParagraphStyle()
        p.set_font(f)
        p.set_alignment(gen.plug.docgen.PARA_ALIGN_CENTER)
        p.set_bottom_margin(pt2cm(8))
        p.set_description(_("The style used for the title."))
        default_style.add_paragraph_style("FTR-Title", p)

        f = gen.plug.docgen.FontStyle()
        f.set_size(9)
        f.set_type_face(gen.plug.docgen.FONT_SANS_SERIF)
        p = gen.plug.docgen.ParagraphStyle()
        p.set_font(f)
        p.set_description(_("The style used for names."))
        default_style.add_paragraph_style("FTR-Name", p)

        f = gen.plug.docgen.FontStyle()
        f.set_size(7)
        f.set_type_face(gen.plug.docgen.FONT_SANS_SERIF)
        p = gen.plug.docgen.ParagraphStyle()
        p.set_font(f)
        p.set_description(_("The style used for data (birth, death, marriage, divorce)."))
        default_style.add_paragraph_style("FTR-Data", p)

        f = gen.plug.docgen.FontStyle()
        f.set_size(7)
        f.set_type_face(gen.plug.docgen.FONT_SANS_SERIF)
        p = gen.plug.docgen.ParagraphStyle()
        p.set_font(f)
        p.set_alignment(gen.plug.docgen.PARA_ALIGN_CENTER)
        p.set_top_margin(pt2cm(8))
        p.set_description(_("The style used for the footer."))
        default_style.add_paragraph_style("FTR-Footer", p)

        ## Draw styles
        g = gen.plug.docgen.GraphicsStyle()
        g.set_paragraph_style("FTR-Title")
        g.set_color((0, 0, 0))
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)             # Workaround for a bug in ODFDoc
        default_style.add_draw_style("FTR-title", g)

        g = gen.plug.docgen.GraphicsStyle()
        g.set_shadow(1,0.15)
        g.set_fill_color((255,255,255))
        default_style.add_draw_style("FTR-box", g)

        g = gen.plug.docgen.GraphicsStyle()
        g.set_paragraph_style("FTR-Name")
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)             # Workaround for a bug in ODFDoc
        default_style.add_draw_style("FTR-name", g)

        g = gen.plug.docgen.GraphicsStyle()
        g.set_paragraph_style("FTR-Data")
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)             # Workaround for a bug in ODFDoc
        default_style.add_draw_style("FTR-data", g)

        g = gen.plug.docgen.GraphicsStyle()
        default_style.add_draw_style("FTR-line", g)

        g = gen.plug.docgen.GraphicsStyle()
        g.set_paragraph_style("FTR-Footer")
        g.set_color((0, 0, 0))
        g.set_fill_color((255, 255, 255))
        g.set_line_width(0)             # Workaround for a bug in ODFDoc
        default_style.add_draw_style("FTR-footer", g)
