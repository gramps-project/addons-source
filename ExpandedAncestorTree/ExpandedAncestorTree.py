# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2007-2012  Brian G. Matherly
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2014       Paul Franklin
# Copyright (C) 2010-2015  Craig J. Anderson
# Copyright (C) 2026       Bartok Szabolcs (kotrabdev)
#
# MODIFICATION NOTICE:
# This file is a heavily modified version of the original "Ancestor Tree" report.
# Modifications by Bartok Szabolcs (2026) include:
# - Replaced AscendPerson traversal with a custom engine to include siblings and cousins.
# - Replaced LineBase with TreeConnectionLine for smart-routing and bridged intersections.
# - Added dynamic color-coding for family branch lines.
# - Flattened UI design (removed shadows) and implemented bold typography for names.
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""Reports/Graphical Reports/Expanded Ancestor Tree"""

from __future__ import annotations
from typing import Any

from gramps.gen.const import GRAMPS_LOCALE as glocale

# Prefer the addon-specific translation catalogue; fall back to the core
# Gramps translation when this file is loaded outside the addon framework.
try:
    _trans = glocale.get_addon_translator(__file__)
except (ValueError, AttributeError):
    _trans = glocale.translation
_ = _trans.gettext

from gramps.gen.errors import ReportError
from gramps.gen.plug.menu import (
    TextOption,
    NumberOption,
    BooleanOption,
    EnumeratedListOption,
    StringOption,
    PersonOption,
)
from gramps.gen.plug.report import Report, MenuReportOptions, stdoptions, utils
from gramps.gen.plug.docgen import (
    FontStyle,
    ParagraphStyle,
    GraphicsStyle,
    FONT_SANS_SERIF,
    PARA_ALIGN_CENTER,
)
from gramps.plugins.lib.libtreebase import (
    BoxBase,
    CalcLines,
    Canvas,
    LineBase,
    NoteBox,
    NoteType,
    PageNumberBox,
    ReportOptions,
    SubstKeywords,
    TitleBox,
    TitleNoDisplay,
)
from gramps.gen.proxy import CacheProxyDb
from gramps.gen.display.name import displayer as _nd

# Small point-to-centimetre helper
PT2CM = utils.pt2cm

_BORN = (_("b.", "birth abbreviation"),)
_DIED = (_("d.", "death abbreviation"),)
_MARR = (_("m.", "marriage abbreviation"),)

# Indexes into the "level" tuple attached to every box:
#   [LVL_GEN]  generation depth (0 = centre person, grows towards ancestors)
#   [LVL_INDX] slot inside the generation (even -> "father" display format,
#              odd -> "mother" display format, see CalcItems.calc_person)
#   [LVL_Y]    vertical row order (smaller value = drawn higher on the page)
LVL_GEN, LVL_INDX, LVL_Y = range(3)


class PersonBox(BoxBase):
    """Graphical box representing one person on the canvas.
    Drawing rules:
      * the frame uses the "AC2-box" style (or a role-specific variant),
      * line 0 of the text (the name) uses the bold "AC2-Name" style,
      * every following line falls back to the normal text style,
      * optionally a running person index is printed above the frame
        (controlled by the "Show Index" option).
    """

    def __init__(self, level):
        BoxBase.__init__(self)
        self.boxstr = "AC2-box"
        self.level = level
        self.idx = 0

    # Sort support: boxes are ordered vertically by their row coordinate.
    def __lt__(self, other):
        return self.level[LVL_Y] < other.level[LVL_Y]

    # Render the frame plus all text lines onto the current page.
    def display(self):
        doc = self.page.canvas.doc
        x = self.x_cm - self.page.page_x_offset
        y = self.y_cm - self.page.page_y_offset

        if isinstance(self.text, str):
            lines = self.text.split('\n')
        else:
            lines = self.text

        text_str = '\n'.join([line for line in lines if line.strip()])

        doc_type_str = str(type(doc)).lower()
        is_vector = any(v in doc_type_str for v in ['pdf', 'svg', 'cairo', 'psdoc', 'image'])

        if is_vector:
            style_sheet = doc.get_style_sheet()
            base_font_pt = style_sheet.get_paragraph_style("AC2-Normal").get_font().get_size()
            lh = PT2CM(base_font_pt)

            doc.draw_box(self.boxstr, "", x, y, self.width, self.height)

            y_off = lh * 0.95
            for i, line_text in enumerate(lines):
                if not line_text.strip():
                    continue
                style = "AC2-Name" if i == 0 else "AC2-Normal-Text"
                doc.draw_text(style, line_text, x + lh * 0.6, y + y_off)
                y_off += lh * 1.2

            if self.idx > 0:
                doc.draw_text(self.boxstr, "%d" % self.idx, x, y - lh * 1.4)
        else:
            if self.idx > 0:
                text_str = f"[{self.idx}] {text_str}"
            doc.draw_box(self.boxstr, text_str, x, y, self.width, self.height)

class FamilyBox(BoxBase):
    """Marriage/family box inherited from the original report.
    """

    def __init__(self, level):
        BoxBase.__init__(self)
        self.boxstr = "AC2-fam-box"
        self.level = level

    def __lt__(self, other):
        return self.level[LVL_Y] < other.level[LVL_Y]


class TitleN(TitleNoDisplay):
    """Silent title variant: reserves the title area but draws nothing."""

    def __init__(self, doc, locale):
        TitleNoDisplay.__init__(self, doc, "AC2-Title-box")
        self._ = locale.translation.sgettext

    def calc_title(self, center):
        self.mark_text = self._("Ancestor Tree Expanded")
        self.text = ""


class TitleA(TitleBox):
    """Visible title box: "Expanded Ancestor Graph for <center person>"."""

    def __init__(self, doc, locale, name_displayer):
        self._nd = name_displayer
        TitleBox.__init__(self, doc, "AC2-Title-box")
        self._ = locale.translation.sgettext

    def calc_title(self, center):
        name = ""
        if center is not None:
            name = self._nd.display(center)
        self.text = self._("Ancestor Tree Expanded for %s") % name
        self.set_box_height_width()


class TreeConnectionLine(LineBase):
    """Smart connector between child boxes and parent boxes."""

    def __init__(self, start_boxes, end_boxes, is_main=True, family_index=0):
        LineBase.__init__(self, start_boxes[0])
        if end_boxes:
            self.end = end_boxes[0]
        self.start_boxes = start_boxes
        self.end_boxes = end_boxes
        self.is_main = is_main
        self.family_index = family_index

        all_boxes = start_boxes + (end_boxes if end_boxes else [])
        if all_boxes:
            top_box = min(all_boxes, key=lambda b: b.level[2])
            bottom_box = max(all_boxes, key=lambda b: b.level[2])
            LineBase.__init__(self, top_box)
            self.end = bottom_box
        else:
            LineBase.__init__(self, start_boxes[0] if start_boxes else None)

    def get_vertical_trunk(self, page):
        if not self.start_boxes:
            return None

        col_w = page.canvas.report_opts.col_width

        if self.end_boxes:
            e_box = self.end_boxes[0]
            base_end_x = e_box.x_cm - page.page_x_offset
            c_offset = getattr(e_box, 'collateral_offset', 0)
            if c_offset > 0:
                base_end_x -= c_offset * 0.6

            if self.is_main:
                my_x = base_end_x - col_w * 0.8
            else:
                my_x = base_end_x - col_w * (0.6 - (self.family_index % 4) * 0.15)
        else:
            s_box = self.start_boxes[0]
            my_x = s_box.x_cm + s_box.width - page.page_x_offset + col_w * 0.2

        min_y = 9999999
        max_y = -9999999
        for b in self.start_boxes + self.end_boxes:
            y = b.y_cm + b.height / 2.0 - page.page_y_offset
            min_y = min(min_y, y)
            max_y = max(max_y, y)

        return (my_x, min_y, max_y)

    def display(self, page):
        if not self.start_boxes:
            return

        doc = page.canvas.doc
        color_opt = GUIConnect().color_lines()
        line_style = f"AC2-line-color-{self.family_index % 15}" if color_opt else "AC2-line"

        my_trunk = self.get_vertical_trunk(page)
        if not my_trunk:
            return
        my_x, min_y, max_y = my_trunk

        vertical_trunks = []
        if hasattr(page.canvas, 'lines'):
            for line in page.canvas.lines:
                if isinstance(line, TreeConnectionLine) and line != self:
                    trunk = line.get_vertical_trunk(page)
                    if trunk:
                        vertical_trunks.append(trunk)

        hw = 0.1
        h = 0.15

        def draw_horizontal_with_bridges(x1, x2, y_pos):
            x_start = min(x1, x2)
            x_end = max(x1, x2)

            intersections = []
            for Tx, Tmin_y, Tmax_y in vertical_trunks:
                if x_start + 0.1 < Tx < x_end - 0.1:
                    if Tmin_y + 0.05 < y_pos < Tmax_y - 0.05:
                        intersections.append(Tx)

            intersections.sort()

            current_x = x_start
            for Tx in intersections:
                doc.draw_line(line_style, current_x, y_pos, Tx - hw, y_pos)
                doc.draw_line(line_style, Tx - hw, y_pos, Tx - hw/2, y_pos - h)
                doc.draw_line(line_style, Tx - hw/2, y_pos - h, Tx + hw/2, y_pos - h)
                doc.draw_line(line_style, Tx + hw/2, y_pos - h, Tx + hw, y_pos)
                current_x = Tx + hw

            doc.draw_line(line_style, current_x, y_pos, x_end, y_pos)

        for b in self.start_boxes:
            if b not in page.boxes:
                continue
            y = b.y_cm + b.height / 2.0 - page.page_y_offset
            x1 = b.x_cm + b.width - page.page_x_offset
            draw_horizontal_with_bridges(x1, my_x, y)

        for b in self.end_boxes:
            if b not in page.boxes:
                continue
            y = b.y_cm + b.height / 2.0 - page.page_y_offset
            x2 = b.x_cm - page.page_x_offset
            draw_horizontal_with_bridges(my_x, x2, y)

        if min_y < max_y:
            doc.draw_line(line_style, my_x, min_y, my_x, max_y)


class CalcItems:
    """Produces the display strings shown inside each box.
    Wraps CalcLines, which applies substitution keywords ($n, $b, $d, ...)
    and the user-defined replace list.
    """

    def __init__(self, dbase):
        _gui = GUIConnect()
        self._gui = _gui
        display_repl = _gui.get_val("replace_list")
        self.__calc_l = CalcLines(dbase, display_repl, _gui.locale, _gui.n_d)

        self.__blank_father = self.__calc_l.calc_lines(None, None, _gui.get_val("father_disp"))
        self.__blank_mother = self.__calc_l.calc_lines(None, None, _gui.get_val("mother_disp"))

        self.center_use = _gui.get_val("center_uses")
        self.disp_father = _gui.get_val("father_disp")
        self.disp_mother = _gui.get_val("mother_disp")
        self.disp_marr = [_gui.get_val("marr_disp")]
        self.__blank_marriage = self.__calc_l.calc_lines(None, None, self.disp_marr)

    def calc_person(self, index, indi_handle, fams_handle):
        """Return the formatted text lines for one person box.

        """
        working_lines = ""
        if index[1] % 2 == 0 or (index[1] == 1 and self.center_use == 0):
            if indi_handle == fams_handle is None:
                working_lines = self.__calc_l.calc_lines(None, None, self._gui.get_val("father_disp"))
            else:
                working_lines = self.disp_father
        else:
            if indi_handle == fams_handle is None:
                working_lines = self.__calc_l.calc_lines(None, None, self._gui.get_val("mother_disp"))
            else:
                working_lines = self.disp_mother

        if indi_handle == fams_handle is None:
            # Chained comparison: true only when BOTH handles are None,
            # i.e. we are building the placeholder text of an empty box.
            return working_lines
        else:
            return self.__calc_l.calc_lines(indi_handle, fams_handle, working_lines)


class NodeData:
    """Lightweight tree node produced by :class:`MakeExpandedTree`.
    Attributes:
        handle         Gramps handle of the person this node represents.
        gen            Generation distance from the centre person (1 = centre).
        is_center      True for the root/centre node.
        is_sibling     True for a sibling of a direct-line person.
        is_cousin      True for a descendant of an ancestor's sibling.
        is_spouse      True for a spouse attached to a sibling/cousin branch.
        father/mother  NodeData links pointing towards the ancestors.
        siblings       Sibling nodes sharing a parent with this node.
        family_groups  [{spouse, children}] groups used for cousin branches.
        y              Row number assigned later by calculate_order().
        box            PersonBox instance; filled during start(), else None.
    """

    def __init__(self, handle, gen, is_center=False, is_sibling=False, is_cousin=False, is_spouse=False):
        self.handle = handle
        self.gen = gen
        self.is_center = is_center
        self.is_sibling = is_sibling
        self.is_cousin = is_cousin
        self.is_spouse = is_spouse
        self.father = None
        self.mother = None
        self.siblings = []
        self.family_groups = []
        self.y = 0.0
        self.box = None
        self.collateral_offset = 0


class MakeExpandedTree:
    """Custom ancestry builder replacing the stock AscendPerson walker.
    Compared with the original Ancestor Tree report this engine also collects:
      * siblings of the centre person and/or of every direct ancestor,
      * cousins, i.e. descendants of those siblings (fetch_descendants),
      * spouses belonging to those sibling/cousin branches.
    The result is a graph of NodeData objects flattened into a strict
    top-to-bottom order (flat_nodes) which directly defines the row (Y
    coordinate) of every box on the canvas.
    """

    def __init__(self, dbase, canvas,user=None):
        self.database = dbase
        self.canvas = canvas
        self.user = user
        self.limit_warned = False
        _gui = GUIConnect()

        self.max_gen = _gui.maxgen()
        self.inc_center_siblings = _gui.get_val("inc_siblings")
        self.inc_center_descendants = _gui.get_val("inc_children")
        anc_sibs = _gui.get_val("inc_anc_siblings")
        self.inc_anc_siblings = True if anc_sibs is None else anc_sibs
        cuz = _gui.get_val("inc_cousins")
        self.inc_cousins = False if cuz is None else cuz
        desc_val = _gui.get_val("desc_gen")
        self.desc_gen = int(desc_val) if desc_val else 3

        self.calc_items = CalcItems(self.database)
        self.visited = set()
        self.max_generation = 0
        self.flat_nodes = []

    def get_siblings(self, person_handle):
        """Return handles of all full/half siblings by walking the person's
        parent families; the person itself is skipped."""
        siblings = []
        person = self.database.get_person_from_handle(person_handle)
        if not person:
            return siblings
        for fam_handle in person.get_parent_family_handle_list():
            family = self.database.get_family_from_handle(fam_handle)
            if family:
                for child_ref in family.get_child_ref_list():
                    child_handle = child_ref.get_reference_handle()
                    if child_handle != person_handle and child_handle not in siblings:
                        siblings.append(child_handle)
        return siblings

    def fetch_descendants(self, node, current_gen, offset=1, is_center_line=False):
        """Attach spouses and children (= cousins) to a sibling/cousin node.
        """

        if not is_center_line and current_gen < 1:
            return
        if not is_center_line and current_gen == 1 and not node.is_center:
            return

        if current_gen < (1 - self.desc_gen):
            return

        if len(self.visited) > 250:
            if not self.limit_warned and self.user:
                self.limit_warned = True
                self.user.warn(
                    _("Tree Truncated"),
                    _("The generated tree reached the 250 people safety limit and has been truncated.\n\nPlease reduce the number of generations or disable some options to see all branches.")
                )
            return

        person = self.database.get_person_from_handle(node.handle)
        if not person:
            return

        for fam_h in person.get_family_handle_list():
            fam = self.database.get_family_from_handle(fam_h)
            if not fam:
                continue

            children_handles = [c.get_reference_handle() for c in fam.get_child_ref_list()]
            if not children_handles:
                continue

            f_h = fam.get_father_handle()
            m_h = fam.get_mother_handle()
            spouse_h = f_h if m_h == node.handle else m_h
            if spouse_h == node.handle:
                spouse_h = None

            spouse_node = None
            if spouse_h and spouse_h not in self.visited:
                self.visited.add(spouse_h)
                spouse_node = NodeData(spouse_h, current_gen, is_spouse=True)
                spouse_node.collateral_offset = node.collateral_offset

            # Recurse one generation down so grandchildren of the common
            children_nodes = []
            for child_h in children_handles:
                if child_h not in self.visited:
                    self.visited.add(child_h)
                    c_node = NodeData(child_h, current_gen - 1, is_cousin=True)
                    c_node.collateral_offset = offset
                    self.fetch_descendants(c_node, current_gen - 1, offset, is_center_line=is_center_line)
                    children_nodes.append(c_node)

            if children_nodes:
                node.family_groups.append({
                    'spouse': spouse_node,
                    'children': children_nodes
                })

    def build_tree(self, person_handle, gen=1, is_center=False):
        """Recursively build the ancestor graph around the centre person.
        Per-person expansion order:
          1. optional siblings (own toggle for the centre person, shared
             toggle for ancestors), plus their descendants when cousins
             are enabled and gen >= 2,
          2. the father, then the mother (gen + 1), until max_gen.

        Returns the created NodeData, or None when the generation budget
        is exhausted or the handle was already visited elsewhere.
        """

        if len(self.visited) > 250:
            if not self.limit_warned and self.user:
                self.limit_warned = True
                self.user.warn(
                    _("Tree Truncated"),
                    _("The generated tree reached the 250 people safety limit and has been truncated.\n\nPlease reduce the number of generations or disable some options to see all branches.")
                )
            return None

        if gen > self.max_gen or person_handle in self.visited:
            return None

        self.visited.add(person_handle)
        if gen > self.max_generation:
            self.max_generation = gen

        node = NodeData(person_handle, gen, is_center=is_center)


        if is_center:
            self.fetch_descendants(node, gen, offset=0, is_center_line=self.inc_center_descendants)

        # Sibling policy: the centre person has its own toggle while all
        # ancestors share a single "include ancestor siblings" toggle.
        should_add_sibs = self.inc_center_siblings if is_center else self.inc_anc_siblings
        if should_add_sibs:
            for sib_h in self.get_siblings(person_handle):
                if sib_h not in self.visited:
                    self.visited.add(sib_h)
                    sib_node = NodeData(sib_h, gen, is_sibling=True)
                    node.siblings.append(sib_node)

                    if self.inc_cousins and gen >= 2:
                        self.fetch_descendants(sib_node, gen)

        # Climb one generation up: attach the father, then the mother,
        # recursively until max_gen is reached.
        if gen < self.max_gen:
            person = self.database.get_person_from_handle(person_handle)
            if person:
                for fam_h in person.get_parent_family_handle_list():
                    family = self.database.get_family_from_handle(fam_h)
                    if family:
                        f_h = family.get_father_handle()
                        m_h = family.get_mother_handle()
                        if f_h:
                            node.father = self.build_tree(f_h, gen + 1)
                        if m_h:
                            node.mother = self.build_tree(m_h, gen + 1)
        return node

    # Flatten a cousin sub-tree in drawing order: spouses first, then the
    # branch owner itself, then every child recursively.
    def append_descendants(self, c_node):
        for fg in c_node.family_groups:
            if fg['spouse']: self.flat_nodes.append(fg['spouse'])

        self.flat_nodes.append(c_node)

        for fg in c_node.family_groups:
            for child in fg['children']:
                self.append_descendants(child)

    def calculate_order(self, node):
        """In-order walk of the built graph producing ``flat_nodes``.

        Visit order per person: father subtree -> the node itself ->
        siblings (each with spouse and descendants) -> mother subtree.
        Because flat_nodes order equals final top-to-bottom placement,
        the caller afterwards assigns ``node.y = position`` for each entry.
        """
        if not node:
            return

        if node.father:
            self.calculate_order(node.father)

        self.flat_nodes.append(node)

        if node.is_center:
            for fg in node.family_groups:
                if fg['spouse']: self.flat_nodes.append(fg['spouse'])
            for fg in node.family_groups:
                for child in fg['children']:
                    self.append_descendants(child)

        for sib in node.siblings:
            for fg in sib.family_groups:
                if fg['spouse']: self.flat_nodes.append(fg['spouse'])

            self.flat_nodes.append(sib)

            for fg in sib.family_groups:
                for child in fg['children']:
                    self.append_descendants(child)

        if node.mother:
            self.calculate_order(node.mother)

    def start(self, person_id):
        """Entry point: resolve the centre Gramps ID, build the graph and
        materialise boxes plus connector lines on the canvas."""
        center = self.database.get_person_from_gramps_id(person_id)
        if center is None:
            raise ReportError(_("Person %s is not in the Database") % person_id)

        root = self.build_tree(center.get_handle(), gen=1, is_center=True)
        if root:
            self.calculate_order(root)

            for i, n in enumerate(self.flat_nodes):
                n.y = i

            _gui = GUIConnect()
            show_idx = _gui.get_val("show_idx")
            curr_idx = _gui.get_val("start_idx") if show_idx else 0

            #  create one box per node -------------------------
            for n in self.flat_nodes:
                box = PersonBox((n.gen - 1, 1, n.y))
                if show_idx and not n.is_spouse:
                    box.idx = curr_idx
                    curr_idx += 1
                box.text = self.calc_items.calc_person((n.gen, 1, n.y), n.handle, None)
                person = self.database.get_person_from_handle(n.handle)
                if person:
                    box.add_mark(self.database, person)

                if n.is_center:
                    box.boxstr = "AC2-center-box"
                elif n.is_spouse:
                    box.boxstr = "AC2-spouse-box"
                elif n.is_sibling or n.is_cousin:
                    box.boxstr = "AC2-sibling-box"

                self.canvas.add_box(box)
                n.box = box
                box.collateral_offset = getattr(n, 'collateral_offset', 0)


            #  create the connecting lines ---------------------
            family_index = 0
            for n in self.flat_nodes:
                if n.is_spouse:
                    continue

                if n.family_groups:
                    for fg in n.family_groups:
                        children = fg['children']
                        spouse = fg['spouse']
                        if not children:
                            continue

                        start_boxes = [c.box for c in children]
                        end_boxes = [n.box]
                        if spouse:
                            end_boxes.append(spouse.box)

                        cline = TreeConnectionLine(start_boxes, end_boxes, is_main=False, family_index=family_index)
                        self.canvas.add_line(cline)
                        family_index += 1

                if not (n.is_sibling or n.is_cousin):
                    if n.father or n.mother:
                        start_boxes = [n.box]
                        for sib in n.siblings:
                            start_boxes.append(sib.box)

                        end_boxes = []
                        if n.father:
                            end_boxes.append(n.father.box)
                        if n.mother:
                            end_boxes.append(n.mother.box)

                        mline = TreeConnectionLine(start_boxes, end_boxes, is_main=True, family_index=family_index)
                        self.canvas.add_line(mline)
                        family_index += 1


class LRTransform:
    """Left-to-right placement transform."""

    def __init__(self, canvas, max_generations, gen_shift=0):
        self.canvas = canvas
        self.rept_opts = canvas.report_opts

        top_margin = 0.8 if GUIConnect().get_val("show_idx") else 0.0
        self.y_offset = self.rept_opts.littleoffset * 2 + self.canvas.title.height + top_margin

        self.gen_shift = gen_shift

        max_offset = max([getattr(b, 'collateral_offset', 0) for b in self.canvas.boxes] + [0])
        self.cascade_pad = max_offset * 0.6

    def _place(self, box):
        box.x_cm = self.rept_opts.littleoffset
        display_gen = box.level[LVL_GEN] + self.gen_shift
        box.x_cm += display_gen * (self.rept_opts.col_width + self.rept_opts.max_box_width + self.cascade_pad)

        # cascade
        c_offset = getattr(box, 'collateral_offset', 0)
        if c_offset > 0:
            box.x_cm += c_offset * 0.6

        box.y_cm = self.rept_opts.max_box_height + self.rept_opts.box_pgap
        box.y_cm *= box.level[LVL_Y]
        box.y_cm += self.y_offset

    def place(self):
        if not self.canvas.boxes: return
        self.__last_y_level = self.canvas.boxes[0].level[LVL_Y]
        for box in self.canvas.boxes:
            self._place(box)


class MakeReport:
    """Second layout stage: measures real box sizes and finalises geometry."""

    def __init__(self, dbase, doc, canvas, font_normal):
        self.database = dbase
        self.doc = doc
        self.canvas = canvas
        self.font_normal = font_normal

        _gui = GUIConnect()
        self.compress_tree = _gui.compress_tree()
        self.mother_ht = self.father_ht = 0
        self.max_generations = 0

    def get_height_width(self, box):
        self.canvas.set_box_height_width(box)
        box.width += 0.6
        box.height += 0.6

        if box.width > self.canvas.report_opts.max_box_width:
            self.canvas.report_opts.max_box_width = box.width

        if box.level[LVL_Y] > 0:
            if box.level[LVL_INDX] % 2 == 0 and box.height > self.father_ht:
                self.father_ht = box.height
            elif box.level[LVL_INDX] % 2 == 1 and box.height > self.mother_ht:
                self.mother_ht = box.height

        if box.level[LVL_GEN] > self.max_generations:
            self.max_generations = box.level[LVL_GEN]

    def get_generations(self):
        return self.max_generations

    def start(self):
        self.father_ht = 0.0
        self.mother_ht = 0.0
        for box in self.canvas.boxes:
            self.get_height_width(box)

        self.canvas.report_opts.max_box_height = max(self.father_ht, self.mother_ht)

        if GUIConnect().get_val("show_idx"):
            self.canvas.report_opts.box_pgap += 1.0

        for box in self.canvas.boxes:
            box.width = self.canvas.report_opts.max_box_width

        min_gen = min([b.level[LVL_GEN] for b in self.canvas.boxes] + [0])
        gen_shift = abs(min_gen) if min_gen < 0 else 0
        self.max_generations += gen_shift

        if gen_shift > 0:
            for box in self.canvas.boxes:
                box.level = (box.level[LVL_GEN] + gen_shift, box.level[1], box.level[2])

        transform = LRTransform(self.canvas, self.max_generations, 0)
        transform.place()


class GUIConnect:
    """Shared access point to the report options (Borg/singleton pattern).
    """

    __shared_state: dict[str, Any] = {}

    def __init__(self):
        self.__dict__ = self.__shared_state

    def set__opts(self, options, locale, name_displayer):
        self.__opts = options
        self.locale = locale
        self.n_d = name_displayer

    def get_val(self, val):
        value = self.__opts.get_option_by_name(val)
        if value:
            return value.get_value()
        else:
            return False

    def title_class(self, doc):
        title_type = self.get_val("report_title")
        if title_type:
            return TitleA(doc, self.locale, self.n_d)
        else:
            return TitleN(doc, self.locale)

    def inc_marr(self):
        return self.get_val("inc_marr")

    def inc_sib(self):
        return self.get_val("inc_siblings")

    def inc_cousins(self):
        return self.get_val("inc_cousins")

    def color_lines(self):
        return self.get_val("color_lines")

    def maxgen(self):
        return self.get_val("maxgen")

    def fill_out(self):
        return self.get_val("fill_out")

    def compress_tree(self):
        return self.get_val("compress_tree")


class ExpandedAncestorTree(Report):
    """Main report orchestrator.
    """

    def __init__(self, database, options, user):
        Report.__init__(self, database, options, user)
        self.options = options
        self._user = user

        trans_opt = options.menu.get_option_by_name("trans")
        if trans_opt and trans_opt.get_value():
            self.set_locale(trans_opt.get_value())
        else:
            self.set_locale(glocale.translation)

        # Apply standard date / private-data / living-people filters, then
        # wrap the DB in a cache proxy because the tree walks it very heavily.
        stdoptions.run_date_format_option(self, options.menu)
        stdoptions.run_private_data_option(self, options.menu)
        stdoptions.run_living_people_option(self, options.menu, self._locale)
        self.database = CacheProxyDb(self.database)
        stdoptions.run_name_format_option(self, options.menu)
        self._nd = self._name_display

    def begin_report(self):
        """Build the complete chart structure (no page output yet)."""
        database = self.database

        self.connect = GUIConnect()
        self.connect.set__opts(self.options.menu, self._locale, self._nd)

        style_sheet = self.doc.get_style_sheet()
        font_normal = style_sheet.get_paragraph_style("AC2-Normal").get_font()
        self.canvas = Canvas(self.doc, ReportOptions(self.doc, font_normal, "AC2-line"))

        if self.connect.get_val("show_idx"):
            self.canvas.report_opts.littleoffset += 1.0

        self.canvas.report_opts.box_shadow *= self.connect.get_val("shadowscale")
        self.canvas.report_opts.box_pgap *= self.connect.get_val("box_Yscale")
        self.canvas.report_opts.box_mgap *= self.connect.get_val("box_Yscale")

        with self._user.progress(_("Ancestor Tree Expanded"), _("Making the Tree..."), 4) as step:
            #  traverse the DB.
            self.max_generations = self.connect.get_val("maxgen")
            tree = MakeExpandedTree(database, self.canvas, self._user)
            tree.start(self.connect.get_val("pid"))
            tree = None
            step()

            # render/reserve the title above the chart.
            title = self.connect.title_class(self.doc)
            center = self.database.get_person_from_gramps_id(self.connect.get_val("pid"))
            title.calc_title(center)
            self.canvas.add_title(title)

            # measure boxes and compute final coordinates.
            report = MakeReport(database, self.doc, self.canvas, font_normal)
            report.start()
            self.max_generations = report.get_generations()
            report = None
            step()

            # free-text note supporting substitution keywords ($T etc.).
            if self.connect.get_val("inc_note"):
                note_box = NoteBox(self.doc, "AC2-note-box", self.connect.get_val("note_place"))
                subst = SubstKeywords(self.database, self._locale, self._nd, None, None)
                note_box.text = subst.replace_and_clean(self.connect.get_val("note_disp"))
                self.canvas.add_note(note_box)

            #  fit the chart to the requested page strategy.
            one_page = self.connect.get_val("resize_page")
            scale_report = self.connect.get_val("scale_tree")

            if "Svg" in self.doc.__class__.__name__ or "svg" in str(type(self.doc)).lower():
                one_page = True
                scale_report = 0

            if scale_report == 2 and not ("Svg" in self.doc.__class__.__name__ or "svg" in str(type(self.doc)).lower()):
                scale_report = 1

            scale = self.canvas.scale_report(one_page, scale_report != 0, scale_report == 2)
            step()

            if scale != 1 or self.connect.get_val("shadowscale") != 1.0:
                self.scale_styles(scale)

    def write_report(self):
        """Paginate the finished canvas and draw every page."""
        one_page = self.connect.get_val("resize_page")
        inc_border = self.connect.get_val("inc_border")
        incblank = self.connect.get_val("inc_blank")
        prnnum = self.connect.get_val("inc_pagenum")

        doc_type_str = str(type(self.doc)).lower()
        is_vector = any(v in doc_type_str for v in ['pdf', 'svg', 'cairo', 'psdoc', 'image'])

        if "svg" in doc_type_str:
            one_page = True
            incblank = True

        colsperpage = self.doc.get_usable_width()
        colsperpage += self.canvas.report_opts.col_width
        colsperpage = int(
            colsperpage / (self.canvas.report_opts.max_box_width + self.canvas.report_opts.col_width)
        )

        colsperpage = colsperpage or 1

        if prnnum:
            page_num_box = PageNumberBox(self.doc, "AC2-box", self._locale)

        self.canvas.paginate(colsperpage, one_page)

        if is_vector:
            try:
                for page in self.canvas.page_iter_gen(True):
                    page.lines = self.canvas.lines
            except Exception:
                pass

        pages = self.canvas.page_count(incblank)
        with self._user.progress(_("Ancestor Tree Expanded"), _("Printing the Tree..."), pages) as step:
            for page in self.canvas.page_iter_gen(incblank):
                self.doc.start_page()
                if inc_border:
                    page.draw_border("AC2-line")
                if prnnum:
                    page_num_box.display(page)
                page.display()
                step()
                self.doc.end_page()

    def scale_styles(self, scale):
        """Shrink/grow shadows, line widths and fonts by ``scale`` so that a
        scaled chart keeps its proportions on paper."""
        style_sheet = self.doc.get_style_sheet()

        # Box frames: shadow offset and border width follow the scale.
        graph_style = style_sheet.get_draw_style("AC2-box")
        graph_style.set_shadow(graph_style.get_shadow(), self.canvas.report_opts.box_shadow * scale)
        graph_style.set_line_width(graph_style.get_line_width() * scale)
        style_sheet.add_draw_style("AC2-box", graph_style)

        try:
            graph_style_center = style_sheet.get_draw_style("AC2-center-box")
            if graph_style_center:
                graph_style_center.set_shadow(graph_style_center.get_shadow(), self.canvas.report_opts.box_shadow * scale)
                graph_style_center.set_line_width(graph_style_center.get_line_width() * scale)
                style_sheet.add_draw_style("AC2-center-box", graph_style_center)
        except (AttributeError, KeyError):
            pass

        graph_style = style_sheet.get_draw_style("AC2-sibling-box")
        graph_style.set_shadow(graph_style.get_shadow(), self.canvas.report_opts.box_shadow * scale)
        graph_style.set_line_width(graph_style.get_line_width() * scale)
        style_sheet.add_draw_style("AC2-sibling-box", graph_style)

        graph_style = style_sheet.get_draw_style("AC2-spouse-box")
        graph_style.set_shadow(graph_style.get_shadow(), self.canvas.report_opts.box_shadow * scale)
        graph_style.set_line_width(graph_style.get_line_width() * scale)
        style_sheet.add_draw_style("AC2-spouse-box", graph_style)

        graph_style = style_sheet.get_draw_style("AC2-fam-box")
        graph_style.set_shadow(graph_style.get_shadow(), self.canvas.report_opts.box_shadow * scale)
        graph_style.set_line_width(graph_style.get_line_width() * scale)
        style_sheet.add_draw_style("AC2-fam-box", graph_style)

        graph_style = style_sheet.get_draw_style("AC2-note-box")
        graph_style.set_line_width(graph_style.get_line_width() * scale)
        style_sheet.add_draw_style("AC2-note-box", graph_style)

        # Paragraph styles: font sizes follow the scale too.
        para_style = style_sheet.get_paragraph_style("AC2-Normal")
        if para_style:
            font = para_style.get_font()
            font.set_size(font.get_size() * scale)
            para_style.set_font(font)
            style_sheet.add_paragraph_style("AC2-Normal", para_style)

        para_style = style_sheet.get_paragraph_style("AC2-Name-Para")
        if para_style:
            font = para_style.get_font()
            font.set_size(font.get_size() * scale)
            para_style.set_font(font)
            style_sheet.add_paragraph_style("AC2-Name-Para", para_style)

        para_style = style_sheet.get_paragraph_style("AC2-Note")
        if para_style:
            font = para_style.get_font()
            font.set_size(font.get_size() * scale)
            para_style.set_font(font)
            style_sheet.add_paragraph_style("AC2-Note", para_style)

        para_style = style_sheet.get_paragraph_style("AC2-Title")
        if para_style:
            font = para_style.get_font()
            font.set_size(font.get_size() * scale)
            para_style.set_font(font)
            style_sheet.add_paragraph_style("AC2-Title", para_style)

        graph_style = GraphicsStyle()
        graph_style.set_line_width(1.0 * scale)
        graph_style.set_color((0, 0, 0))
        style_sheet.add_draw_style("AC2-line", graph_style)

        for i in range(15):
            style_name = f"AC2-line-color-{i}"
            try:
                gs = style_sheet.get_draw_style(style_name)
                if gs:
                    current_width = gs.get_line_width()
                    base_w = current_width if current_width > 0 else 1.0
                    gs.set_line_width(base_w * scale)
                    style_sheet.add_draw_style(style_name, gs)
            except (AttributeError, KeyError):
                pass

        self.doc.set_style_sheet(style_sheet)


class ExpandedAncestorTreeOptions(MenuReportOptions):
    """Menu definition shown in the report dialog.
    Categories:
      Tree Options       - what to include (centre person, siblings, cousins,
                           generations, index numbering)
      Report Options     - title, border, page numbers, tree scaling
      Report Options (2) - name format, living people, private data, locale
      Display            - per-role display formats, marriage box, line colours
      Advanced           - replace list, note box, spacing/shadow factors
    """

    def __init__(self, name, dbase):
        self.__db = dbase
        self.__pid = None
        self.box_Y_sf = None
        self.box_shadow_sf = None
        MenuReportOptions.__init__(self, name, dbase)

    def get_subject(self):
        gid = self.__pid.get_value()
        person = self.__db.get_person_from_gramps_id(gid)
        return _nd.display(person)

    def add_menu_options(self, menu):
        category_name = _("Tree Options")

        self.__pid = PersonOption(_("Center Person"))
        self.__pid.set_help(_("The center person for the tree"))
        menu.add_option(category_name, "pid", self.__pid)

        descendants = BooleanOption(_("Include descendants of the center person"), False)
        descendants.set_help(_("Whether to display the children and full descending lines of the center person"))
        menu.add_option(category_name, "inc_children", descendants)

        siblings = BooleanOption(_("Include siblings of the center person"), False)
        siblings.set_help(_("Whether to only display the center person or all of his/her siblings too"))
        menu.add_option(category_name, "inc_siblings", siblings)

        anc_sibs = BooleanOption(_("Include siblings of ancestors"), True)
        anc_sibs.set_help(_("Whether to display the siblings of direct ancestors"))
        menu.add_option(category_name, "inc_anc_siblings", anc_sibs)

        cousins = BooleanOption(_("Include cousins (collateral descendants)"), False)
        cousins.set_help(_("Whether to display the cousins and descendants of the ancestors' siblings"))
        menu.add_option(category_name, "inc_cousins", cousins)

        self.max_gen = NumberOption(_("Generations"), 10, 1, 50)
        self.max_gen.set_help(_("The number of generations to include in the tree"))
        menu.add_option(category_name, "maxgen", self.max_gen)

        self.desc_gen = NumberOption(_("Descendant Generations"), 3, 1, 50)
        self.desc_gen.set_help(_("The number of descendant generations to include"))
        menu.add_option(category_name, "desc_gen", self.desc_gen)

        self.show_idx = BooleanOption(_("Show Index"), False)
        self.show_idx.set_help(_("Display index of each person"))
        menu.add_option(category_name, "show_idx", self.show_idx)
        self.show_idx.connect("value-changed", self._showidx_changed)

        self.start_idx = NumberOption(_("Start Index"), 1, 1, 50)
        self.start_idx.set_help(_("The start index"))
        menu.add_option(category_name, "start_idx", self.start_idx)

        category_name = _("Report Options")
        self.title = EnumeratedListOption(_("Report Title"), 0)
        self.title.add_item(0, _("Do not include a title"))
        self.title.add_item(1, _("Include Report Title"))
        self.title.set_help(_("Choose a title for the report"))
        menu.add_option(category_name, "report_title", self.title)

        border = BooleanOption(_("Include a border"), False)
        border.set_help(_("Whether to make a border around the report."))
        menu.add_option(category_name, "inc_border", border)

        prnnum = BooleanOption(_("Include Page Numbers"), False)
        prnnum.set_help(_("Whether to print page numbers on each page."))
        menu.add_option(category_name, "inc_pagenum", prnnum)

        self.scale = EnumeratedListOption(_("Scale tree to fit"), 0)
        self.scale.add_item(0, _("Do not scale tree"))
        self.scale.add_item(1, _("Scale tree to fit page width only"))
        self.scale.add_item(2, _("Scale tree to fit the size of the page"))
        self.scale.set_help(_("Whether to scale the tree to fit a specific paper size"))
        menu.add_option(category_name, "scale_tree", self.scale)
        self.scale.connect("value-changed", self.__check_blank)

        if "BKI" not in self.name.split(","):
            self.__onepage = BooleanOption(
                _("Resize Page to Fit Tree size\n\nNote: Overrides options in the 'Paper Option' tab"), False
            )
            self.__onepage.set_help(_("Whether to resize the page to fit the size of the tree."))
            menu.add_option(category_name, "resize_page", self.__onepage)
            self.__onepage.connect("value-changed", self.__check_blank)
        else:
            self.__onepage = None

        self.__blank = BooleanOption(_("Include Blank Pages"), True)
        self.__blank.set_help(_("Whether to include pages that are blank."))
        menu.add_option(category_name, "inc_blank", self.__blank)
        self.__check_blank()

        category_name = _("Report Options (2)")
        stdoptions.add_name_format_option(menu, category_name)
        stdoptions.add_living_people_option(menu, category_name)
        stdoptions.add_private_data_option(menu, category_name)
        locale_opt = stdoptions.add_localization_option(menu, category_name)
        stdoptions.add_date_format_option(menu, category_name, locale_opt)

        category_name = _("Display")

        color_lines = BooleanOption(_("Use random colors for family lines"), False)
        color_lines.set_help(_("Draw each family's connecting lines with a distinct color."))
        menu.add_option(category_name, "color_lines", color_lines)

        disp = TextOption(_("Father\nDisplay Format"), ["$n", "%s $b" % _BORN, "-{%s $d}" % _DIED])
        disp.set_help(_("Display format for the fathers box."))
        menu.add_option(category_name, "father_disp", disp)

        disp_mom = TextOption(_("Mother\nDisplay Format"), ["$n", "%s $b" % _BORN, "%s $m" % _MARR, "-{%s $d}" % _DIED])
        disp_mom.set_help(_("Display format for the mothers box."))
        menu.add_option(category_name, "mother_disp", disp_mom)

        center_disp = EnumeratedListOption(_("Center person uses\nwhich format"), 0)
        center_disp.add_item(0, _("Use Fathers Display format"))
        center_disp.add_item(1, _("Use Mothers display format"))
        center_disp.set_help(_("The display format for the center person"))
        menu.add_option(category_name, "center_uses", center_disp)

        self.incmarr = BooleanOption(_("Include Marriage box"), False)
        self.incmarr.set_help(_("Whether to include a separate marital box in the report"))
        menu.add_option(category_name, "inc_marr", self.incmarr)
        self.incmarr.connect("value-changed", self._incmarr_changed)

        self.marrdisp = StringOption(_("Marriage\nDisplay Format"), "%s $m" % _MARR)
        self.marrdisp.set_help(_("Display format for the marital box."))
        menu.add_option(category_name, "marr_disp", self.marrdisp)
        self._incmarr_changed()

        category_name = _("Advanced")
        repldisp = TextOption(_("Replace Display Format:\n'Replace this'/' with this'"), [])
        repldisp.set_help(_("i.e.\nUnited States of America/U.S.A."))
        menu.add_option(category_name, "replace_list", repldisp)

        self.usenote = BooleanOption(_("Include a note"), False)
        self.usenote.set_help(_("Whether to include a note on the report."))
        menu.add_option(category_name, "inc_note", self.usenote)
        self.usenote.connect("value-changed", self._usenote_changed)

        self.notedisp = TextOption(_("Note"), [])
        self.notedisp.set_help(_("Add a note\n\n$T inserts today's date"))
        menu.add_option(category_name, "note_disp", self.notedisp)

        locales = NoteType(0, 1)
        self.notelocal = EnumeratedListOption(_("Note Location"), 0)
        for num, text in locales.note_locals():
            self.notelocal.add_item(num, text)
        self.notelocal.set_help(_("Where to place the note."))
        menu.add_option(category_name, "note_place", self.notelocal)
        self._usenote_changed()

        self.box_Y_sf = NumberOption(_("inter-box scale factor"), 1.00, 0.10, 2.00, 0.01)
        self.box_Y_sf.set_help(_("Make the inter-box spacing bigger or smaller"))
        menu.add_option(category_name, "box_Yscale", self.box_Y_sf)

        self.box_shadow_sf = NumberOption(_("box shadow scale factor"), 1.00, 0.00, 2.00, 0.01)
        self.box_shadow_sf.set_help(_("Make the box shadow bigger or smaller"))
        menu.add_option(category_name, "shadowscale", self.box_shadow_sf)

    def _incmarr_changed(self):
        value = self.incmarr.get_value()
        self.marrdisp.set_available(value)

    def _usenote_changed(self):
        value = self.usenote.get_value()
        self.notelocal.set_available(value)

    def _showidx_changed(self):
        value = self.show_idx.get_value()
        self.start_idx.set_available(value)

    def __check_blank(self):
        if self.__onepage:
            value = not self.__onepage.get_value()
        else:
            value = True
        off = value and (self.scale.get_value() != 2)
        self.__blank.set_available(off)

    def __fillout_vals(self):

        max_gen = self.max_gen.get_value()
        old_val = self.fillout.get_value()
        item_list = []
        item_list.append([0, _("No generations of empty boxes for unknown ancestors")])
        if max_gen > 1:
            item_list.append([1, _("One Generation of empty boxes for unknown ancestors")])
        item_list.extend([itr, str(itr) + _(" Generations of empty boxes for unknown ancestors")] for itr in range(2, max_gen))
        self.fillout.set_items(item_list)
        if old_val + 2 > len(item_list):
            self.fillout.set_value(len(item_list) - 2)

    def make_default_style(self, default_style):
        """Register every named style used by the drawing code.
        """
        # Base 9pt sans-serif used for regular box text.
        font = FontStyle()
        font.set_size(9)
        font.set_type_face(FONT_SANS_SERIF)
        para_style = ParagraphStyle()
        para_style.set_font(font)
        para_style.set_description(_("The basic style used for the text display."))
        default_style.add_paragraph_style("AC2-Normal", para_style)

        # Bold variant rendered on the first (name) line of every box.
        font_name = FontStyle()
        font_name.set_size(9)
        font_name.set_type_face(FONT_SANS_SERIF)
        font_name.set_bold(1)
        para_name_style = ParagraphStyle()
        para_name_style.set_font(font_name)
        para_name_style.set_description(_("The bold style used for the names."))
        default_style.add_paragraph_style("AC2-Name-Para", para_name_style)

        # Shadow width is 0 (flat design); only a small drop offset remains.
        box_shadow = 0.4

        font = FontStyle()
        font.set_size(9)
        font.set_type_face(FONT_SANS_SERIF)
        para_style = ParagraphStyle()
        para_style.set_font(font)
        para_style.set_description(_("The basic style used for the note display."))
        default_style.add_paragraph_style("AC2-Note", para_style)

        font = FontStyle()
        font.set_size(16)
        font.set_type_face(FONT_SANS_SERIF)
        para_style = ParagraphStyle()
        para_style.set_font(font)
        para_style.set_alignment(PARA_ALIGN_CENTER)
        para_style.set_description(_("The style used for the title."))
        default_style.add_paragraph_style("AC2-Title", para_style)

        gs_text_bold = GraphicsStyle()
        gs_text_bold.set_paragraph_style("AC2-Name-Para")
        default_style.add_draw_style("AC2-Name", gs_text_bold)

        gs_text_normal = GraphicsStyle()
        gs_text_normal.set_paragraph_style("AC2-Normal")
        default_style.add_draw_style("AC2-Normal-Text", gs_text_normal)

        graph_style = GraphicsStyle()
        graph_style.set_paragraph_style("AC2-Normal")
        graph_style.set_shadow(0, box_shadow)
        graph_style.set_fill_color((255, 255, 255))
        default_style.add_draw_style("AC2-box", graph_style)

        graph_style_sib = GraphicsStyle()
        graph_style_sib.set_paragraph_style("AC2-Normal")
        graph_style_sib.set_shadow(0, box_shadow)
        graph_style_sib.set_fill_color((255, 255, 255))
        default_style.add_draw_style("AC2-sibling-box", graph_style_sib)

        graph_style_spouse = GraphicsStyle()
        graph_style_spouse.set_paragraph_style("AC2-Normal")
        graph_style_spouse.set_shadow(0, box_shadow)
        graph_style_spouse.set_fill_color((240, 240, 240))
        default_style.add_draw_style("AC2-spouse-box", graph_style_spouse)

        graph_style = GraphicsStyle()
        graph_style.set_paragraph_style("AC2-Normal")
        graph_style.set_fill_color((255, 255, 255))
        default_style.add_draw_style("AC2-fam-box", graph_style)

        graph_style = GraphicsStyle()
        graph_style.set_paragraph_style("AC2-Note")
        graph_style.set_fill_color((255, 255, 255))
        default_style.add_draw_style("AC2-note-box", graph_style)

        graph_style_center = GraphicsStyle()
        graph_style_center.set_paragraph_style("AC2-Normal")
        graph_style_center.set_shadow(0, box_shadow)
        graph_style_center.set_fill_color((255, 255, 255))
        graph_style_center.set_line_width(3.0)
        default_style.add_draw_style("AC2-center-box", graph_style_center)

        graph_style = GraphicsStyle()
        graph_style.set_paragraph_style("AC2-Title")
        graph_style.set_color((0, 0, 0))
        graph_style.set_fill_color((255, 255, 255))
        graph_style.set_line_width(0)
        graph_style.set_description(_("Cannot edit this reference"))
        default_style.add_draw_style("AC2-Title-box", graph_style)

        graph_style = GraphicsStyle()
        graph_style.set_line_width(1.0)
        graph_style.set_color((0, 0, 0))
        default_style.add_draw_style("AC2-line", graph_style)

        # Palette behind the "Use random colors for family lines" option:
        # family connection N picks AC2-line-color-{N % 15}.
        colors = [
            (220, 20, 60),   # Crimson
            (0, 100, 0),     # DarkGreen
            (0, 0, 205),     # MediumBlue
            (255, 140, 0),   # DarkOrange
            (139, 0, 139),   # DarkMagenta
            (0, 139, 139),   # DarkCyan
            (178, 34, 34),   # FireBrick
            (75, 0, 130),    # Indigo
            (34, 139, 34),   # ForestGreen
            (205, 92, 92),   # IndianRed
            (0, 0, 128),     # Navy
            (218, 165, 32),  # GoldenRod
            (46, 139, 87),   # SeaGreen
            (139, 69, 19),   # SaddleBrown
            (199, 21, 133),  # MediumVioletRed
        ]
        for i, col in enumerate(colors):
            line_style = GraphicsStyle()
            line_style.set_line_width(1)
            line_style.set_color(col)
            default_style.add_draw_style(f"AC2-line-color-{i}", line_style)

