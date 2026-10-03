# -*- coding: utf-8 -*-
"""
Gramps - a GTK+/GNOME based genealogy program
Circle Tree View — descendant tree with circular nodes
Compatible with Gramps 6.0.x
License: GNU GPL v2 or later

Version 1.4.0: Full support for multiple spouses/marriages per person.
Children are properly grouped under their respective marriage midpoints.
"""
"""
Circle Tree View (Charts category).
Install into:
  ~/.gramps/gramps60/plugins/CircleTreeView/
or
  %AppData%\gramps\gramps60\plugins\CircleTreeView\
"""
import math
import re
from gi.repository import Gtk, Gdk, cairo, Pango, PangoCairo
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.lib import Person
from gramps.gui.views.navigationview import NavigationView
from gramps.gui.views.bookmarks import PersonBookmarks

CFG = {
    "node_r": 36.0,
    "h_gap": 28.0,
    "v_gap": 64.0,
    "spouse_gap": 32.0,
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


class TNode:
    """Mutable tree node supporting multiple families."""
    __slots__ = (
        "handle",
        "name",
        "families",
        "_sub_w",
        "_x",
        "_y",
        "_cx",
        "_gen",
        "_is_spouse",
    )

    def __init__(self, handle, name, families=None):
        self.handle = handle
        self.name = name or ""
        self.families = families if families is not None else []
        self._sub_w = 0.0
        self._x = 0.0
        self._y = 0.0
        self._cx = 0.0
        self._gen = 0
        self._is_spouse = False


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
        name = name[:trail.start()].strip()

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
    total = 1
    for sp, children in node.families:
        if sp:
            total += 1
        total += sum(count_nodes(c) for c in children)
    return total


def tree_depth(node):
    if not node:
        return 0
    depths = [1]
    for sp, children in node.families:
        for c in children:
            depths.append(1 + tree_depth(c))
    return max(depths)


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
    trimmed_families = []
    if max_gen <= 0 or current < max_gen:
        for spouse_name, children in node.families:
            kids = [trim_tree(c, max_gen, current + 1) for c in children]
            kids = [k for k in kids if k]
            trimmed_families.append((spouse_name, kids))
    return TNode(node.handle, node.name, trimmed_families)


class LayoutEngine:
    """
    Multi-spouse Layout Engine:
    Handles 1, 2, or 3+ spouses per person by placing spouses left/right 
    and routing child lines from respective marriage midpoints.
    """

    def kids_width(self, children):
        if not children:
            return 0.0
        return sum(c._sub_w for c in children) + CFG["h_gap"] * (len(children) - 1)

    def measure_chunk(self, chunk):
        r = CFG["node_r"]
        spouse_gap = CFG["spouse_gap"]
        h_gap = CFG["h_gap"]

        if not chunk:
            return 2 * r, 0.0, spouse_gap, 0.0, 0.0

        f0 = chunk[0]
        sp0, kids0 = f0
        w0 = self.kids_width(kids0)

        if len(chunk) == 1:
            req_gap = spouse_gap
            m0_rel = (r + req_gap / 2.0) if sp0 else 0.0
            left_rel = -r
            right_rel = (2 * r + req_gap + r) if sp0 else r

            if kids0:
                left_rel = min(left_rel, m0_rel - w0 / 2.0)
                right_rel = max(right_rel, m0_rel + w0 / 2.0)

            chunk_w = right_rel - left_rel
            p_rel_x = -left_rel
            return chunk_w, p_rel_x, req_gap, w0, 0.0

        # Two families in a block (Spouse 1 left, Person center, Spouse 2 right)
        f1 = chunk[1]
        sp1, kids1 = f1
        w1 = self.kids_width(kids1)

        default_dist = 2 * r + spouse_gap
        req_dist = max(default_dist, (w0 + w1) / 2.0 + h_gap) if (kids0 and kids1) else default_dist
        req_gap = max(spouse_gap, req_dist - 2 * r)

        m0_rel = - (r + req_gap / 2.0) if sp0 else 0.0
        m1_rel = (r + req_gap / 2.0) if sp1 else 0.0

        left_rel = - (2 * r + req_gap + r) if sp0 else -r
        right_rel = (2 * r + req_gap + r) if sp1 else r

        if kids0:
            left_rel = min(left_rel, m0_rel - w0 / 2.0)
            right_rel = max(right_rel, m0_rel + w0 / 2.0)
        if kids1:
            left_rel = min(left_rel, m0_rel - w1 / 2.0)
            right_rel = max(right_rel, m1_rel + w1 / 2.0)

        chunk_w = right_rel - left_rel
        p_rel_x = -left_rel
        return chunk_w, p_rel_x, req_gap, w0, w1

    def measure(self, node):
        for sp, kids in node.families:
            for ch in kids:
                self.measure(ch)

        if not node.families:
            node._sub_w = 2 * CFG["node_r"]
            return node._sub_w

        chunks = [node.families[i:i+2] for i in range(0, len(node.families), 2)]
        total_w = 0.0
        for i, chunk in enumerate(chunks):
            cw, _, _, _, _ = self.measure_chunk(chunk)
            total_w += cw
            if i > 0:
                total_w += CFG["h_gap"]
        node._sub_w = total_w
        return node._sub_w

    def layout(self, root):
        if not root:
            return [], [], 100.0, 100.0
        self.measure(root)
        nodes = []
        pad = CFG["pad"]
        r = CFG["node_r"]
        v_step = 2 * r + CFG["v_gap"]
        links = []

        def place(node, x_left, gen):
            y = pad + 40 + gen * v_step

            if not node.families:
                cx = x_left + node._sub_w / 2.0
                node._x = cx
                node._y = y
                node._cx = cx
                node._gen = gen
                nodes.append(node)
                return

            chunks = [node.families[i:i+2] for i in range(0, len(node.families), 2)]
            cur_x = x_left

            for chunk in chunks:
                cw, p_rel_x, req_gap, w0, w1 = self.measure_chunk(chunk)
                px = cur_x + p_rel_x
                node._x = px
                node._y = y
                node._cx = px
                node._gen = gen
                nodes.append(node)

                # --- First family of the block ---
                sp0, kids0 = chunk[0]
                if len(chunk) == 1:
                    # Single marriage: spouse on the right
                    if sp0:
                        sx0 = px + (2 * r + req_gap)
                        sp_node = TNode(None, sp0, [])
                        sp_node._x = sx0
                        sp_node._y = y
                        sp_node._cx = px
                        sp_node._is_spouse = True
                        sp_node._gen = gen
                        nodes.append(sp_node)
                        m0 = (px + sx0) / 2.0
                        links.append(("spouse", px + r, y, sx0 - r, y))
                    else:
                        m0 = px
                else:
                    # Two marriages: first spouse on the left
                    if sp0:
                        sx0 = px - (2 * r + req_gap)
                        sp_node = TNode(None, sp0, [])
                        sp_node._x = sx0
                        sp_node._y = y
                        sp_node._cx = px
                        sp_node._is_spouse = True
                        sp_node._gen = gen
                        nodes.append(sp_node)
                        m0 = (sx0 + px) / 2.0
                        links.append(("spouse", sx0 + r, y, px - r, y))
                    else:
                        m0 = px

                if kids0:
                    k0_left = m0 - w0 / 2.0
                    for ch in kids0:
                        place(ch, k0_left, gen + 1)
                        k0_left += ch._sub_w + CFG["h_gap"]

                    mid_y = y + r + CFG["v_gap"] / 2.0
                    start_y = y if sp0 else y + r
                    links.append(("v", m0, start_y, m0, mid_y))
                    child_xs = [ch._x for ch in kids0]
                    left = min(child_xs + [m0])
                    right = max(child_xs + [m0])
                    if abs(right - left) > 0.5:
                        links.append(("h", left, mid_y, right, mid_y))
                    for ch in kids0:
                        links.append(("v", ch._x, mid_y, ch._x, ch._y - r))

                # --- Second family of the block (2nd spouse on the right) ---
                if len(chunk) > 1:
                    sp1, kids1 = chunk[1]
                    if sp1:
                        sx1 = px + (2 * r + req_gap)
                        sp_node = TNode(None, sp1, [])
                        sp_node._x = sx1
                        sp_node._y = y
                        sp_node._cx = px
                        sp_node._is_spouse = True
                        sp_node._gen = gen
                        nodes.append(sp_node)
                        m1 = (px + sx1) / 2.0
                        links.append(("spouse", px + r, y, sx1 - r, y))
                    else:
                        m1 = px

                    if kids1:
                        k1_left = m1 - w1 / 2.0
                        for ch in kids1:
                            place(ch, k1_left, gen + 1)
                            k1_left += ch._sub_w + CFG["h_gap"]

                        mid_y = y + r + CFG["v_gap"] / 2.0
                        start_y = y if sp1 else y + r
                        links.append(("v", m1, start_y, m1, mid_y))
                        child_xs = [ch._x for ch in kids1]
                        left = min(child_xs + [m1])
                        right = max(child_xs + [m1])
                        if abs(right - left) > 0.5:
                            links.append(("h", left, mid_y, right, mid_y))
                        for ch in kids1:
                            links.append(("v", ch._x, mid_y, ch._x, ch._y - r))

                cur_x += cw + CFG["h_gap"]

        place(root, 0.0, 0)

        min_x = min(n._x - r for n in nodes)
        max_x = max(n._x + r for n in nodes)
        max_y = max(n._y + r for n in nodes)
        width = max_x - min_x + pad * 2
        height = max_y + pad + 20
        shift = pad - min_x
        for n in nodes:
            n._x += shift
            n._cx += shift

        clean = []
        for t, x1, y1, x2, y2 in links:
            dx = abs(x1 - x2)
            dy = abs(y1 - y2)
            if dx <= 0.5 or dy <= 0.5:
                clean.append((t, x1 + shift, y1, x2 + shift, y2))

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
        self.queue_draw()

    def on_draw(self, _widget, cr):
        cr.set_source_rgb(*CFG["bg"])
        cr.paint()
        
        # Version stamp
        cr.set_source_rgb(0.6, 0.55, 0.5)
        vl = self.create_pango_layout("CircleTree 1.4.0 (multi-spouse)")
        vl.set_font_description(Pango.FontDescription("Sans 9"))
        cr.move_to(8, 6)
        PangoCairo.show_layout(cr, vl)
        
        cr.save()
        cr.translate(self.offset_x, self.offset_y)
        cr.scale(self.scale, self.scale)
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
            cr.set_source_rgb(*(CFG["active_fill"] if is_active else CFG["circle_fill"]))
            cr.fill_preserve()
            cr.set_source_rgb(*CFG["circle_stroke"])
            cr.set_line_width(1.5)
            cr.stroke()
            
            self._draw_node_label(cr, n._x, n._y, r, n.name or "")
            
        cr.restore()
        return False

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
            self.scale = min(2.5, self.scale * 1.1)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            self.scale = max(0.3, self.scale / 1.1)
        self.queue_draw()
        return True

    def _draw_node_label(self, cr, cx, cy, radius, label):
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
                    '<rect x="%.1f" y="%.1f" width="18" height="14" fill="rgb(%d,%d,%d)"/>'
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
        w = max(1, int(self.canvas_w * scale))
        h = max(1, int(self.canvas_h * scale))
        try:
            import cairo as pycairo  # type: ignore
            surface = pycairo.ImageSurface(pycairo.FORMAT_ARGB32, w, h)
            cr = pycairo.Context(surface)
            cr.scale(scale, scale)
            ox, oy, sc = self.offset_x, self.offset_y, self.scale
            self.offset_x = self.offset_y = 0.0
            self.scale = 1.0
            self.on_draw(self, cr)
            self.offset_x, self.offset_y, self.scale = ox, oy, sc
            surface.write_to_png(path)
            return
        except Exception:
            pass
        try:
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            cr = cairo.Context(surface)
            cr.scale(scale, scale)
            ox, oy, sc = self.offset_x, self.offset_y, self.scale
            self.offset_x = self.offset_y = 0.0
            self.scale = 1.0
            self.on_draw(self, cr)
            self.offset_x, self.offset_y, self.scale = ox, oy, sc
            if hasattr(surface, "write_to_png"):
                surface.write_to_png(path)
                return
        except Exception:
            pass
        svg_path = path if path.lower().endswith(".svg") else path + ".svg"
        if svg_path == path:
            svg_path = path[:-4] + ".svg" if path.lower().endswith(".png") else path + ".svg"
        self.export_svg(svg_path)
        raise RuntimeError(
            _("PNG export needs pycairo. Saved SVG instead:\n%s") % svg_path
        )


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
        vbox.pack_start(bar, False, False, 0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.canvas = CircleTreeCanvas(self)
        scrolled.add(self.canvas)
        vbox.pack_start(scrolled, True, True, 0)
        vbox.show_all()
        return vbox

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
            parts = raw_name.split(", ", 1)
            last_name = parts[0].strip()
            given_part = parts[1].strip()
            given_words = given_part.split()
            first_name = given_words[0] if given_words else ""
        else:
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

    def _build_descendants(self, person, visited=None):
        if visited is None:
            visited = set()
        handle = person.handle
        if handle in visited:
            return None
        visited.add(handle)

        families = []
        # Process ALL families of the person from Gramps (break removed)
        for fhandle in person.get_family_handle_list():
            family = self.dbstate.db.get_family_from_handle(fhandle)
            if not family:
                continue
            spouse_name = None
            if self.show_spouses:
                if person.get_gender() == Person.MALE:
                    sh = family.get_mother_handle()
                else:
                    sh = family.get_father_handle()
                if sh:
                    sp = self.dbstate.db.get_person_from_handle(sh)
                    if sp:
                        spouse_name = self._person_label(sp)

            children_nodes = []
            for child_ref in family.get_child_ref_list():
                child = self.dbstate.db.get_person_from_handle(
                    child_ref.get_reference_handle()
                )
                if child:
                    cn = self._build_descendants(child, visited)
                    if cn:
                        children_nodes.append(cn)

            if spouse_name or children_nodes:
                families.append((spouse_name, children_nodes))

        return TNode(handle, self._person_label(person), families)

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