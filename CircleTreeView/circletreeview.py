# -*- coding: utf-8 -*-
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026 vadim Verenich
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
Circle Tree View (Charts category): descendant tree with circular nodes.
"""

# -------------------------------------------------------------------------
#
# Python modules
#
# -------------------------------------------------------------------------
import itertools
import math
import re

# -------------------------------------------------------------------------
#
# GTK modules
#
# -------------------------------------------------------------------------
import cairo
from gi.repository import Gtk, Gdk, Pango, PangoCairo

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gui.views.navigationview import NavigationView
from gramps.gui.views.bookmarks import PersonBookmarks

CFG = {
    "node_r": 36.0,
    "h_gap": 28.0,
    "fam_gap": 56.0,  # extra space between the children of different partners
    "v_gap": 64.0,
    "spouse_gap": 32.0,
    "bus_pad": 10.0,  # clearance used to decide whether two buses collide
    "pad": 40.0,
    "font_size": 11,
    "title_size": 16,
    "line_width": 1.3,
    "bg": (0.969, 0.953, 0.922),
    "circle_fill": (1.0, 0.996, 0.976),
    "circle_stroke": (0.24, 0.22, 0.19),
    "line": (0.29, 0.27, 0.24),
    "text": (0.16, 0.15, 0.13),
    "title": (0.24, 0.22, 0.19),
    "active_fill": (0.90, 0.85, 0.70),
}

# Left to right order of the partner groups around a person.
_SIDE_ORDER = {"L": 0, "M": 1, "R": 2}


class Union:
    """
    The children a person has with one partner.

    side is "R" (partner drawn to the right of the person), "L" (partner drawn
    to the left) or "M" (no partner drawn: unknown/missing partner, or
    partners that could not be shown; children hang from the person).
    """

    __slots__ = ("side", "spouse_name", "children", "_spouse", "_ax", "_ay")

    def __init__(self, side, spouse_name=None, children=None):
        self.side = side
        self.spouse_name = spouse_name
        self.children = children if children is not None else []
        self._spouse = None  # layout node of the partner circle
        self._ax = 0.0  # x where the line down to the children starts
        self._ay = 0.0  # y where the line down to the children starts

    @property
    def has_partner(self):
        return self.spouse_name is not None and self.side in ("L", "R")


class TNode:
    """Mutable tree node for layout."""

    __slots__ = (
        "handle",
        "name",
        "unions",
        "_sub_w",
        "_x",
        "_y",
        "_gen",
        "_is_spouse",
    )

    def __init__(self, handle, name, unions=None):
        self.handle = handle
        self.name = name or ""
        self.unions = unions if unions is not None else []
        self._sub_w = 0.0
        self._x = 0.0
        self._y = 0.0
        self._gen = 0
        self._is_spouse = False

    @property
    def children(self):
        return [c for u in self.unions for c in u.children]


def ordered_unions(node):
    return sorted(node.unions, key=lambda u: _SIDE_ORDER[u.side])


def strip_patronymic(name):
    if not name:
        return name
    suffix = ""
    trail = re.search(
        r"(\s*(?:\([^)]*\)|\*\d{4}))\s*$",
        name,
        re.I,
    )
    if trail:
        suffix = trail.group(1)
        name = name[: trail.start()].strip()

    def is_pat(w):
        clean = re.sub(r"[.,;:]", "", w)
        return bool(re.search(r"(?:ович|евич|овна|евна|ична|инична)$", clean, re.I))

    parts = [p for p in name.split() if p]
    if len(parts) <= 1:
        return (name + suffix).strip()
    filtered = []
    for i, w in enumerate(parts):
        if i == 0 or re.match(r"^\(.*\)$", w) or not is_pat(w):
            filtered.append(w)
    return ((" ".join(filtered) if filtered else parts[0]) + suffix).strip()


def count_nodes(node):
    if not node:
        return 0
    return 1 + sum(count_nodes(c) for c in node.children)


def tree_depth(node):
    if not node or not node.children:
        return 1
    return 1 + max(tree_depth(c) for c in node.children)


def auto_max_generations(total, depth):
    if total <= 20:
        max_g = 6
    elif total <= 35:
        max_g = 5
    elif total <= 55:
        max_g = 4
    elif total <= 200:
        max_g = 3
    else:
        max_g = 2
    return min(6, max_g, max(1, depth - 1))


def trim_tree(node, max_gen, current=0):
    if not node:
        return None
    unions = []
    for u in node.unions:
        kids = []
        if max_gen <= 0 or current < max_gen:
            kids = [trim_tree(c, max_gen, current + 1) for c in u.children]
            kids = [k for k in kids if k]
        unions.append(Union(u.side, u.spouse_name, kids))
    return TNode(node.handle, node.name, unions)


class LayoutEngine:
    """
    Three-phase layout with orthogonal parent-child routing:
      Phase 1 - position every node circle.
      Phase 2 - shift coordinates to ensure positive padding.
      Phase 3 - build orthogonal connectors.

    A person can have several partner groups (one per partner, plus one for
    children without a known partner).  Each group gets its own block of
    children, separated from the next by CFG["fam_gap"], and its own line
    down from the person/partner.  If the horizontal "bus" lines of two groups
    would run into each other they are drawn at different heights.
    """

    # ---- measuring ------------------------------------------------------

    def _own_width(self, node):
        r = CFG["node_r"]
        partners = sum(1 for u in node.unions if u.has_partner)
        return 2 * r + partners * (CFG["spouse_gap"] + 2 * r)

    def _kids_width(self, union):
        if not union.children:
            return 0.0
        total = sum(c._sub_w for c in union.children)
        return total + CFG["h_gap"] * (len(union.children) - 1)

    def _blocks_width(self, node):
        widths = [self._kids_width(u) for u in node.unions if u.children]
        if not widths:
            return 0.0
        return sum(widths) + CFG["fam_gap"] * (len(widths) - 1)

    def measure(self, node):
        for ch in node.children:
            self.measure(ch)
        node._sub_w = max(self._own_width(node), self._blocks_width(node))
        return node._sub_w

    # ---- bus heights ----------------------------------------------------

    def _assign_levels(self, unions):
        """
        Choose a height level (0 = nearest the parents) for the bus line of
        each union so that lines of different unions do not merge or cross.
        """
        n = len(unions)
        if n < 2:
            return [0] * n
        pad = CFG["bus_pad"]
        info = []
        for u in unions:
            xs = [c._x for c in u.children]
            lo = min(xs + [u._ax]) - pad
            hi = max(xs + [u._ax]) + pad
            info.append((u._ax, xs, lo, hi))

        def penalty(levels):
            total = 0
            for i in range(n):
                for j in range(i + 1, n):
                    if not (info[i][2] < info[j][3] and info[j][2] < info[i][3]):
                        continue  # horizontal extents do not meet
                    if levels[i] == levels[j]:
                        total += 100  # buses would merge
                        continue
                    shallow, deep = (i, j) if levels[i] < levels[j] else (j, i)
                    a_s, xs_s, lo_s, hi_s = info[shallow]
                    a_d, xs_d, lo_d, hi_d = info[deep]
                    # children verticals of the shallow bus cross the deep bus
                    total += sum(1 for x in xs_s if lo_d < x < hi_d)
                    # anchor vertical of the deep bus crosses the shallow bus
                    if lo_s < a_d < hi_s:
                        total += 1
            return total

        best = None
        best_levels = [0] * n
        for levels in itertools.product(range(n), repeat=n):
            p = penalty(levels)
            if best is None or p < best:
                best = p
                best_levels = list(levels)
        return best_levels

    # ---- layout ---------------------------------------------------------

    def layout(self, root):
        if not root:
            return [], [], 100.0, 100.0
        self.measure(root)
        nodes = []
        blood = []
        pad = CFG["pad"]
        r = CFG["node_r"]
        v_step = 2 * r + CFG["v_gap"]
        step = 2 * r + CFG["spouse_gap"]

        def place(node, x_left, gen):
            y = pad + 40 + gen * v_step
            own = self._own_width(node)
            block_w = node._sub_w
            unions = ordered_unions(node)

            # the row of circles: [left partner] person [right partner]
            cursor = x_left + (block_w - own) / 2.0 + r
            partner_x = {}
            if any(u.side == "L" and u.has_partner for u in unions):
                partner_x["L"] = cursor
                cursor += step
            node._x = cursor
            node._y = y
            node._gen = gen
            if any(u.side == "R" and u.has_partner for u in unions):
                partner_x["R"] = cursor + step
            nodes.append(node)
            blood.append(node)

            for u in unions:
                if u.has_partner:
                    sp = TNode(None, u.spouse_name)
                    sp._x = partner_x[u.side]
                    sp._y = y
                    sp._gen = gen
                    sp._is_spouse = True
                    u._spouse = sp
                    u._ax = (node._x + sp._x) / 2.0
                    u._ay = y
                    nodes.append(sp)
                else:
                    u._spouse = None
                    u._ax = node._x
                    u._ay = y + r

            # children blocks, one per union, left to right
            k_left = x_left + (block_w - self._blocks_width(node)) / 2.0
            for u in unions:
                if not u.children:
                    continue
                for ch in u.children:
                    place(ch, k_left, gen + 1)
                    k_left += ch._sub_w + CFG["h_gap"]
                k_left += CFG["fam_gap"] - CFG["h_gap"]

        place(root, 0.0, 0)

        min_x = min(n._x - r for n in nodes)
        max_x = max(n._x + r for n in nodes)
        max_y = max(n._y + r for n in nodes)
        width = max_x - min_x + pad * 2
        height = max_y + pad + 20
        shift = pad - min_x
        for n in nodes:
            n._x += shift
        for n in blood:
            for u in n.unions:
                u._ax += shift

        links = []
        for node in blood:
            unions = ordered_unions(node)
            for u in unions:
                if u._spouse is not None:
                    a, b = sorted((node._x, u._spouse._x))
                    links.append(("spouse", a + r, node._y, b - r, node._y))

            active = [u for u in unions if u.children]
            if not active:
                continue
            levels = self._assign_levels(active)
            ranks = sorted(set(levels))
            for u, lv in zip(active, levels):
                rank = ranks.index(lv)
                mid_y = (
                    node._y + r + CFG["v_gap"] * (rank + 1) / (len(ranks) + 1.0)
                )
                links.append(("v", u._ax, u._ay, u._ax, mid_y))
                child_xs = [ch._x for ch in u.children]
                left = min(child_xs + [u._ax])
                right = max(child_xs + [u._ax])
                if abs(right - left) > 0.5:
                    links.append(("h", left, mid_y, right, mid_y))
                for ch in u.children:
                    links.append(("v", ch._x, mid_y, ch._x, ch._y - r))

        clean = []
        for t, x1, y1, x2, y2 in links:
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            if dx <= 0.5 or dy <= 0.5:
                clean.append((t, x1, y1, x2, y2))

        return nodes, clean, width, height


class CircleTreeCanvas(Gtk.DrawingArea):
    def __init__(self, view):
        Gtk.DrawingArea.__init__(self)
        self.view = view
        self.nodes = []
        self.links = []
        self.canvas_w = 400.0
        self.canvas_h = 300.0
        self.title = ""
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self._drag = None
        self._needs_center = True
        self.set_can_focus(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_button_press)
        self.connect("button-release-event", self.on_button_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("scroll-event", self.on_scroll)

    def set_scene(self, nodes, links, width, height, title=""):
        self.nodes = nodes or []
        self.links = links or []
        self.canvas_w = max(float(width), 100.0)
        self.canvas_h = max(float(height), 100.0)
        self.title = title or ""
        # A new scene (new tree, new active person) is always brought into
        # view; this is done at draw time, when the widget size is known.
        self._needs_center = True
        self.queue_draw()

    def _compute_center(self):
        """Center the chart in the visible area; False if size not known."""
        aw = self.get_allocated_width()
        ah = self.get_allocated_height()
        if aw <= 1 or ah <= 1:
            return False
        self.offset_x = (aw - self.canvas_w * self.scale) / 2.0
        # keep the top of a tall chart visible instead of cutting it off
        self.offset_y = max(0.0, (ah - self.canvas_h * self.scale) / 2.0)
        self._needs_center = False
        return True

    def center(self, *_args):
        """Bring the chart back to the middle of the window."""
        if not self._compute_center():
            self._needs_center = True
        self.queue_draw()

    def on_draw(self, _widget, cr):
        if self._needs_center:
            self._compute_center()
        cr.set_source_rgb(*CFG["bg"])
        cr.paint()
        cr.save()
        cr.translate(self.offset_x, self.offset_y)
        cr.scale(self.scale, self.scale)
        self._paint_scene(cr)
        cr.restore()
        return False

    def _paint_scene(self, cr):
        """Draw title, links and nodes in scene coordinates."""
        if self.title:
            cr.set_source_rgb(*CFG["title"])
            layout = self.create_pango_layout(self.title)
            layout.set_font_description(
                Pango.FontDescription("Serif Italic %d" % CFG["title_size"])
            )
            tw, th = layout.get_pixel_size()
            cr.move_to(self.canvas_w / 2 - tw / 2, 8)
            PangoCairo.show_layout(cr, layout)

        cr.set_line_width(CFG["line_width"])
        cr.set_line_cap(cairo.LineCap.SQUARE)
        cr.set_source_rgb(*CFG["line"])

        for kind, x1, y1, x2, y2 in self.links:
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            if dx > 0.5 and dy > 0.5:
                continue
            cr.new_path()
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()
            if kind == "spouse":
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                layout = self.create_pango_layout("∞")
                layout.set_font_description(Pango.FontDescription("Serif 14"))
                tw, th = layout.get_pixel_size()

                cr.new_path()
                cr.set_source_rgb(*CFG["bg"])
                cr.rectangle(mx - tw / 2.0 - 2, my - th / 2.0 - 1, tw + 4, th + 2)
                cr.fill()

                cr.set_source_rgb(*CFG["line"])
                cr.move_to(mx - tw / 2.0, my - th / 2.0)
                PangoCairo.show_layout(cr, layout)

        r = CFG["node_r"]
        active = self.view.get_active()

        for n in self.nodes:
            cr.new_path()
            is_active = bool(n.handle) and n.handle == active
            cr.arc(n._x, n._y, r, 0, 2 * math.pi)
            cr.set_source_rgb(
                *(CFG["active_fill"] if is_active else CFG["circle_fill"])
            )
            cr.fill_preserve()
            cr.set_source_rgb(*CFG["circle_stroke"])
            cr.set_line_width(1.5)
            cr.stroke()

            self._draw_node_label(cr, n._x, n._y, r, n.name or "")

    def _to_scene(self, x, y):
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def on_button_press(self, _widget, event):
        if event.button == 1:
            sx, sy = self._to_scene(event.x, event.y)
            r = CFG["node_r"]
            for n in self.nodes:
                if n._is_spouse or not n.handle:
                    continue
                if (n._x - sx) ** 2 + (n._y - sy) ** 2 <= r * r:
                    self.view.change_active(n.handle)
                    return True
            self._drag = (event.x, event.y, self.offset_x, self.offset_y)
        return False

    def on_button_release(self, _widget, _event):
        self._drag = None
        return False

    def on_motion(self, _widget, event):
        if self._drag and (event.state & Gdk.ModifierType.BUTTON1_MASK):
            dx = event.x - self._drag[0]
            dy = event.y - self._drag[1]
            self.offset_x = self._drag[2] + dx
            self.offset_y = self._drag[3] + dy
            self.queue_draw()
            return True
        return False

    def on_scroll(self, _widget, event):
        if event.direction == Gdk.ScrollDirection.UP:
            factor = 1.1
        elif event.direction == Gdk.ScrollDirection.DOWN:
            factor = 1 / 1.1
        else:
            return False
        # zoom around the pointer so the chart does not drift out of view
        sx, sy = self._to_scene(event.x, event.y)
        self.scale = min(2.5, max(0.3, self.scale * factor))
        self.offset_x = event.x - sx * self.scale
        self.offset_y = event.y - sy * self.scale
        self._needs_center = False
        self.queue_draw()
        return True

    def _draw_node_label(self, cr, cx, cy, radius, label):
        """Fit multi-line label inside the circle with automatic font sizing."""
        if not label:
            return

        raw_lines = label.split("\n")
        max_w = radius * 1.6
        max_h = radius * 1.6

        cr.set_source_rgb(*CFG["text"])
        base = CFG["font_size"]
        chosen = None

        for fsize in range(base, 5, -1):
            font = Pango.FontDescription("Serif Italic %d" % fsize)
            line_h = fsize + 3
            layouts = []
            widest = 0
            total_h = 0
            for line in raw_lines:
                layout = self.create_pango_layout(line)
                layout.set_font_description(font)
                tw, th = layout.get_pixel_size()
                layouts.append((layout, tw, th))
                widest = max(widest, tw)
                total_h += line_h
            if widest <= max_w and total_h <= max_h:
                chosen = (layouts, line_h, fsize)
                break

        if chosen is None:
            fsize = 6
            font = Pango.FontDescription("Serif Italic %d" % fsize)
            line_h = fsize + 2
            layouts = []
            for line in raw_lines:
                layout = self.create_pango_layout(line)
                layout.set_font_description(font)
                layout.set_ellipsize(Pango.EllipsizeMode.END)
                layout.set_width(int(max_w * Pango.SCALE))
                tw, th = layout.get_pixel_size()
                layouts.append((layout, tw, th))
            chosen = (layouts, line_h, fsize)

        layouts, line_h, fsize = chosen
        n = len(layouts)
        start_y = cy - ((n - 1) * line_h) / 2.0
        for i, (layout, tw, th) in enumerate(layouts):
            cr.new_path()
            cr.move_to(cx - tw / 2.0, start_y + i * line_h - th / 2.0)
            PangoCairo.show_layout(cr, layout)

    def export_svg(self, path):
        """Write SVG as plain XML."""
        w = int(self.canvas_w)
        h = int(self.canvas_h)
        r = CFG["node_r"]
        bg = CFG["bg"]
        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append(
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">' % (w, h, w, h)
        )
        lines.append(
            '<rect width="100%%" height="100%%" fill="rgb(%d,%d,%d)"/>'
            % (int(bg[0] * 255), int(bg[1] * 255), int(bg[2] * 255))
        )
        if self.title:
            lines.append(
                '<text x="%d" y="28" text-anchor="middle" '
                'font-family="Times New Roman, serif" font-style="italic" '
                'font-size="%d" fill="rgb(%d,%d,%d)">%s</text>'
                % (
                    w // 2,
                    CFG["title_size"],
                    int(CFG["title"][0] * 255),
                    int(CFG["title"][1] * 255),
                    int(CFG["title"][2] * 255),
                    self._xml_escape(self.title),
                )
            )
        lc = CFG["line"]
        stroke = "rgb(%d,%d,%d)" % (
            int(lc[0] * 255),
            int(lc[1] * 255),
            int(lc[2] * 255),
        )
        for kind, x1, y1, x2, y2 in self.links:
            if abs(x1 - x2) > 0.5 and abs(y1 - y2) > 0.5:
                continue
            lines.append(
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                'stroke="%s" stroke-width="%.1f"/>'
                % (x1, y1, x2, y2, stroke, CFG["line_width"])
            )
            if kind == "spouse":
                mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                lines.append(
                    '<rect x="%.1f" y="%.1f" width="18" height="14" '
                    'fill="rgb(%d,%d,%d)"/>'
                    % (
                        mx - 9,
                        my - 7,
                        int(bg[0] * 255),
                        int(bg[1] * 255),
                        int(bg[2] * 255),
                    )
                )
                lines.append(
                    '<text x="%.1f" y="%.1f" text-anchor="middle" '
                    'dominant-baseline="middle" font-family="serif" '
                    'font-size="14" fill="%s">∞</text>' % (mx, my + 1, stroke)
                )
        fill = "rgb(%d,%d,%d)" % (
            int(CFG["circle_fill"][0] * 255),
            int(CFG["circle_fill"][1] * 255),
            int(CFG["circle_fill"][2] * 255),
        )
        cstroke = "rgb(%d,%d,%d)" % (
            int(CFG["circle_stroke"][0] * 255),
            int(CFG["circle_stroke"][1] * 255),
            int(CFG["circle_stroke"][2] * 255),
        )
        tcol = "rgb(%d,%d,%d)" % (
            int(CFG["text"][0] * 255),
            int(CFG["text"][1] * 255),
            int(CFG["text"][2] * 255),
        )
        active = self.view.get_active()
        for n in self.nodes:
            is_act = bool(n.handle) and n.handle == active
            f = (
                "rgb(%d,%d,%d)"
                % (
                    int(CFG["active_fill"][0] * 255),
                    int(CFG["active_fill"][1] * 255),
                    int(CFG["active_fill"][2] * 255),
                )
                if is_act
                else fill
            )
            lines.append(
                '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" '
                'stroke="%s" stroke-width="1.5"/>' % (n._x, n._y, r, f, cstroke)
            )

            wrapped = (n.name or "").split("\n")
            line_h = 12
            start_y = n._y - ((len(wrapped) - 1) * line_h) / 2.0 + 4
            for i, ln in enumerate(wrapped):
                lines.append(
                    '<text x="%.1f" y="%.1f" text-anchor="middle" '
                    'font-family="Times New Roman, serif" font-style="italic" '
                    'font-size="11" fill="%s">%s</text>'
                    % (n._x, start_y + i * line_h, tcol, self._xml_escape(ln))
                )
        lines.append("</svg>")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    @staticmethod
    def _xml_escape(s):
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def export_png(self, path, scale=2):
        """Render the whole chart (independent of pan/zoom) to a PNG file."""
        w = max(1, int(self.canvas_w * scale))
        h = max(1, int(self.canvas_h * scale))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surface)
        cr.scale(scale, scale)
        cr.set_source_rgb(*CFG["bg"])
        cr.paint()
        self._paint_scene(cr)
        surface.write_to_png(path)


class CircleTreeView(NavigationView):
    """Charts view: circular-node descendant tree of the active person."""

    CONFIGSETTINGS = (
        ("interface.circletree-show-dates", True),
        ("interface.circletree-strip-patronymic", True),
        ("interface.circletree-show-spouses", True),
    )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(
            self,
            _("Circle Tree"),
            pdata,
            dbstate,
            uistate,
            PersonBookmarks,
            nav_group,
        )
        self.dbstate = dbstate
        self.uistate = uistate
        self.canvas = None
        self.status = None
        self.gen_combo = None
        self.strip_patronymics = True
        self.show_dates = True
        self.show_spouses = True
        self.dbstate.connect("database-changed", self.change_db)
        self.additional_uis.append(self.additional_ui)

    def change_db(self, _db):
        self._change_db(_db)
        if self.active:
            self.build_tree()
        else:
            self.dirty = True

    def get_stock(self):
        return "gramps-pedigree"

    def get_viewtype_stock(self):
        return "gramps-pedigree"

    def navigation_type(self):
        return "Person"

    def build_widget(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.set_margin_top(4)
        bar.set_margin_bottom(4)
        bar.set_margin_start(6)
        bar.set_margin_end(6)
        bar.pack_start(Gtk.Label(label=_("Generations:")), False, False, 0)
        self.gen_combo = Gtk.ComboBoxText()
        for val, label in [
            ("0", _("Auto (<=6)")),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("-1", _("Unlimited")),
        ]:
            self.gen_combo.append(val, label)
        self.gen_combo.set_active_id("0")
        self.gen_combo.connect("changed", lambda *_: self.build_tree())
        bar.pack_start(self.gen_combo, False, False, 0)
        self.status = Gtk.Label(label="")
        self.status.set_halign(Gtk.Align.START)
        bar.pack_start(self.status, True, True, 8)
        btn_png = Gtk.Button(label=_("Export PNG"))
        btn_png.connect("clicked", self.on_export_png)
        bar.pack_end(btn_png, False, False, 0)
        btn_svg = Gtk.Button(label=_("Export SVG"))
        btn_svg.connect("clicked", self.on_export_svg)
        bar.pack_end(btn_svg, False, False, 0)
        btn_ref = Gtk.Button(label=_("Refresh"))
        btn_ref.connect("clicked", lambda *_: self.build_tree())
        bar.pack_end(btn_ref, False, False, 0)
        btn_center = Gtk.Button(label=_("Center"))
        btn_center.set_tooltip_text(_("Move the chart back to the middle"))
        btn_center.connect("clicked", self.on_center)
        bar.pack_end(btn_center, False, False, 0)
        vbox.pack_start(bar, False, False, 0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.canvas = CircleTreeCanvas(self)
        scrolled.add(self.canvas)
        vbox.pack_start(scrolled, True, True, 0)
        vbox.show_all()
        return vbox

    def on_center(self, *_args):
        if self.canvas:
            self.canvas.center()

    def build_tree(self):
        if self.canvas is None:
            return
        if not self.dbstate.is_open():
            self.canvas.set_scene([], [], 400, 200, _("No database"))
            if self.status:
                self.status.set_text("")
            return
        self.strip_patronymics = self._config.get(
            "interface.circletree-strip-patronymic"
        )
        self.show_dates = self._config.get("interface.circletree-show-dates")
        self.show_spouses = self._config.get("interface.circletree-show-spouses")
        try:
            max_gen_setting = int(self.gen_combo.get_active_id() or "0")
        except (TypeError, ValueError, AttributeError):
            max_gen_setting = 0
        handle = self.get_active()
        if not handle:
            self.canvas.set_scene([], [], 400, 200, _("No active person"))
            if self.status:
                self.status.set_text(_("Select a person"))
            return
        person = self.dbstate.db.get_person_from_handle(handle)
        if not person:
            return
        root = self._build_descendants(person)
        total = count_nodes(root)
        depth = tree_depth(root)
        if max_gen_setting == 0:
            max_gen = auto_max_generations(total, depth)
            gen_label = "auto->%d" % max_gen
        elif max_gen_setting < 0:
            max_gen = 0
            gen_label = _("all")
        else:
            max_gen = min(6, max_gen_setting)
            gen_label = str(max_gen)
        display = trim_tree(root, max_gen) if max_gen > 0 else root
        shown = count_nodes(display)
        nodes, links, w, h = LayoutEngine().layout(display)
        title = _("Descendants of %s") % strip_patronymic(
            name_displayer.display(person)
        )
        self.canvas.set_scene(nodes, links, w, h, title)
        if self.status:
            self.status.set_text(
                _("People: %(s)d / %(t)d · gen: %(g)s · %(w)d×%(h)d")
                % {"s": shown, "t": total, "g": gen_label, "w": int(w), "h": int(h)}
            )

    def _person_label(self, person):
        raw_name = name_displayer.display(person)

        if self.strip_patronymics:
            raw_name = strip_patronymic(raw_name)

        first_name = ""
        last_name = ""

        if ", " in raw_name:
            # Format "Surname (incl. von), Given [Patronymic]"
            parts = raw_name.split(", ", 1)
            last_name = parts[0].strip()
            given_part = parts[1].strip()
            given_words = given_part.split()
            first_name = given_words[0] if given_words else ""
        else:
            # Format "Given [Middle] [von] Surname"
            words = raw_name.strip().split()
            if len(words) == 1:
                first_name = words[0]
            elif len(words) >= 2:
                first_name = words[0]
                last_name = " ".join(words[1:])

        date_str = ""
        if self.show_dates:
            db = self.dbstate.db
            birth = get_birth_or_fallback(db, person)
            death = get_death_or_fallback(db, person)
            by = dy = None
            if birth and birth.get_date_object():
                by = birth.get_date_object().get_year()
            if death and death.get_date_object():
                dy = death.get_date_object().get_year()
            if by and dy and by > 0 and dy > 0:
                date_str = "(%s-%s)" % (by, dy)
            elif by and by > 0:
                date_str = "(*%s)" % by
            elif dy and dy > 0:
                date_str = "(+%s)" % dy

        lines = []
        if first_name:
            lines.append(first_name)
        if last_name:
            lines.append(last_name)
        if date_str:
            lines.append(date_str)

        return "\n".join(lines) if lines else raw_name

    @staticmethod
    def _other_parent(family, handle):
        """Handle of the parent in this family who is not 'handle'."""
        if family.get_father_handle() == handle:
            return family.get_mother_handle()
        return family.get_father_handle()

    def _build_descendants(self, person, visited=None):
        """
        Build the descendant tree of person, covering all of the person's
        families.  Families with the same partner are merged.  The first two
        partners are drawn (right, then left of the person); children of
        families without a known partner, and of any further partners, hang
        from the person without a partner circle.
        """
        if visited is None:
            visited = set()
        handle = person.handle
        if handle in visited:
            return None
        visited.add(handle)
        db = self.dbstate.db

        partner_groups = []  # [partner handle, label, children]
        by_partner = {}
        loose = []  # children without a partner circle

        for fhandle in person.get_family_handle_list():
            family = db.get_family_from_handle(fhandle)
            if not family:
                continue
            kids = []
            for child_ref in family.get_child_ref_list():
                child = db.get_person_from_handle(child_ref.get_reference_handle())
                if child:
                    cn = self._build_descendants(child, visited)
                    if cn:
                        kids.append(cn)

            spouse = None
            sp_handle = None
            if self.show_spouses:
                sp_handle = self._other_parent(family, handle)
                if sp_handle:
                    spouse = db.get_person_from_handle(sp_handle)
            if spouse is None:
                loose.extend(kids)
                continue
            group = by_partner.get(sp_handle)
            if group is None:
                group = [sp_handle, self._person_label(spouse), []]
                by_partner[sp_handle] = group
                partner_groups.append(group)
            group[2].extend(kids)

        unions = []
        for group, side in zip(partner_groups[:2], ("R", "L")):
            unions.append(Union(side, group[1], group[2]))
        for group in partner_groups[2:]:
            loose.extend(group[2])
        if loose:
            unions.append(Union("M", None, loose))
        return TNode(handle, self._person_label(person), unions)

    def goto_handle(self, handle):
        self.dirty = True
        if self.active:
            self.build_tree()

    def on_export_svg(self, *_args):
        self._export("svg")

    def on_export_png(self, *_args):
        self._export("png")

    def _export(self, kind):
        if not self.canvas:
            return
        chooser = Gtk.FileChooserDialog(
            title=_("Export %s") % kind.upper(),
            transient_for=self.uistate.window,
            action=Gtk.FileChooserAction.SAVE,
        )
        chooser.add_buttons(
            _("_Cancel"),
            Gtk.ResponseType.CANCEL,
            _("_Save"),
            Gtk.ResponseType.OK,
        )
        chooser.set_current_name("circle-tree." + kind)
        response = chooser.run()
        path = chooser.get_filename() if response == Gtk.ResponseType.OK else None
        chooser.destroy()
        if not path:
            return
        try:
            if kind == "svg":
                self.canvas.export_svg(path)
            else:
                self.canvas.export_png(path)
        except Exception as err:
            from gramps.gui.dialog import ErrorDialog

            ErrorDialog(_("Export failed"), str(err), parent=self.uistate.window)

    additional_ui = [
        """
  <placeholder id="CommonGo">
  <section>
    <item>
      <attribute name="action">win.Back</attribute>
      <attribute name="label" translatable="yes">_Back</attribute>
    </item>
    <item>
      <attribute name="action">win.Forward</attribute>
      <attribute name="label" translatable="yes">_Forward</attribute>
    </item>
  </section>
  <section>
    <item>
      <attribute name="action">win.HomePerson</attribute>
      <attribute name="label" translatable="yes">_Home</attribute>
    </item>
  </section>
  </placeholder>
""",
        """
  <placeholder id='CommonNavigation'>
  <child groups='RO'>
    <object class="GtkToolButton">
      <property name="icon-name">go-previous</property>
      <property name="action-name">win.Back</property>
      <property name="tooltip_text" translatable="yes">Go to previous object</property>
      <property name="label" translatable="yes">_Back</property>
      <property name="use-underline">True</property>
    </object>
    <packing>
      <property name="homogeneous">False</property>
    </packing>
  </child>
  <child groups='RO'>
    <object class="GtkToolButton">
      <property name="icon-name">go-next</property>
      <property name="action-name">win.Forward</property>
      <property name="tooltip_text" translatable="yes">Go to next object</property>
      <property name="label" translatable="yes">_Forward</property>
    </object>
    <packing>
      <property name="homogeneous">False</property>
    </packing>
  </child>
  <child groups='RO'>
    <object class="GtkToolButton">
      <property name="icon-name">go-home</property>
      <property name="action-name">win.HomePerson</property>
      <property name="tooltip_text" translatable="yes">Go to the home person</property>
      <property name="label" translatable="yes">_Home</property>
    </object>
    <packing>
      <property name="homogeneous">False</property>
    </packing>
  </child>
  </placeholder>
""",
    ]

    def can_configure(self):
        return True

    def _get_configure_page_functions(self):
        def page(configdialog):
            grid = Gtk.Grid()
            grid.set_border_width(12)
            grid.set_row_spacing(6)
            grid.set_column_spacing(6)
            configdialog.add_checkbox(
                grid,
                _("Show dates in labels"),
                0,
                "interface.circletree-show-dates",
            )
            configdialog.add_checkbox(
                grid,
                _("Strip patronymics in labels"),
                1,
                "interface.circletree-strip-patronymic",
            )
            configdialog.add_checkbox(
                grid,
                _("Show spouses"),
                2,
                "interface.circletree-show-spouses",
            )
            return _("Circle Tree"), grid

        return [page]
