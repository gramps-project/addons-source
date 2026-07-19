#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  Douglas S. Blank <doug.blank@gmail.com>
# Copyright (C) 2026       Douglas S. Blank <doug.blank@gmail.com>
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
"""
Provides a GTK word cloud widget.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import math
import random
from functools import lru_cache

# -------------------------------------------------------------------------
#
# GTK/Cairo/Pango modules
#
# -------------------------------------------------------------------------
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo

# -------------------------------------------------------------------------
#
# Constants
#
# -------------------------------------------------------------------------
_SPIRAL_STEP = 2.5
_MAX_THETA = 50 * math.pi
_MAX_SHRINK_STEPS = 3

_QUALITY_LEVELS = [
    (10, 72, 4),
    (8, 64, 3),
    (7, 56, 2),
    (6, 48, 1),
]


# -------------------------------------------------------------------------
#
# Helper functions
#
# -------------------------------------------------------------------------
def _search_params(quality):
    q = max(0.0, min(1.0, quality))
    theta_step = 2.0 * (0.025**q)
    n_fallbacks = round(q * 2)
    return theta_step, n_fallbacks


def _count_to_fontsize(count, min_c, max_c, min_font, max_font):
    if min_c == max_c:
        return (min_font + max_font) / 2
    count = max(count, 1)
    min_c = max(min_c, 1)
    max_c = max(max_c, 1)
    t = (math.log(count) - math.log(min_c)) / (math.log(max_c) - math.log(min_c))
    t = max(0.0, min(1.0, t))
    return min_font + t * (max_font - min_font)


def _count_to_color(count, min_c, max_c, color_low, color_high):
    if min_c == max_c:
        t = 0.5
    else:
        min_c = max(min_c, 1)
        max_c = max(max_c, 1)
        t = (math.log(max(count, 1)) - math.log(min_c)) / (
            math.log(max_c) - math.log(min_c)
        )
        t = max(0.0, min(1.0, t))
    r = color_low[0] + t * (color_high[0] - color_low[0])
    g = color_low[1] + t * (color_high[1] - color_low[1])
    b = color_low[2] + t * (color_high[2] - color_low[2])
    return (r, g, b)


def _aabbs_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def _spiral_positions(cx, cy, theta_step, max_theta, theta_offset=0.0):
    theta = theta_offset
    while theta - theta_offset < max_theta:
        r = _SPIRAL_STEP * theta
        yield (cx + r * math.cos(theta), cy + r * math.sin(theta))
        theta += theta_step


def _make_font_desc(font_size, style=Pango.Style.NORMAL):
    desc = Pango.FontDescription()
    desc.set_family("Sans")
    desc.set_weight(Pango.Weight.BOLD)
    desc.set_style(style)
    desc.set_absolute_size(font_size * Pango.SCALE)
    return desc


@lru_cache(maxsize=None)
def _measure_word(word, font_size):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surf)
    layout = PangoCairo.create_layout(ctx)
    layout.set_font_description(_make_font_desc(font_size))
    layout.set_text(word, -1)
    tw, th = layout.get_pixel_size()
    return tw, th


def _try_place(word, font_size, cx, cy, vertical, placed, canvas_w, canvas_h, padding):
    tw, th = _measure_word(word, font_size)
    if vertical:
        aw = th + padding * 2
        ah = tw + padding * 2
    else:
        aw = tw + padding * 2
        ah = th + padding * 2

    ax = cx - aw / 2
    ay = cy - ah / 2

    if ax < 0 or ay < 0 or ax + aw > canvas_w or ay + ah > canvas_h:
        return None

    for p in placed:
        if _aabbs_overlap(ax, ay, aw, ah, p["ax"], p["ay"], p["aw"], p["ah"]):
            return None

    return {
        "word": word,
        "font_size": font_size,
        "ax": ax,
        "ay": ay,
        "aw": aw,
        "ah": ah,
        "vertical": vertical,
        "tw": tw,
        "th": th,
        "padding": padding,
    }


def _place_word(word, font_size, canvas_w, canvas_h, placed, padding, quality=1.0):
    theta_step, n_fallbacks = _search_params(quality)

    cx0, cy0 = canvas_w / 2, canvas_h / 2
    jx = random.uniform(-canvas_w / 6, canvas_w / 6)
    jy = random.uniform(-canvas_h / 6, canvas_h / 6)
    cx, cy = cx0 + jx, cy0 + jy

    orientations = [False, True] if random.random() < 0.5 else [True, False]

    for shrink in range(_MAX_SHRINK_STEPS + 1):
        fs = font_size * (0.9**shrink)
        for px, py in _spiral_positions(cx, cy, theta_step, _MAX_THETA):
            for vertical in orientations:
                result = _try_place(
                    word, fs, px, py, vertical, placed, canvas_w, canvas_h, padding
                )
                if result is not None:
                    return result
        fallback_offsets = [math.pi / 3, 2 * math.pi / 3]
        for theta_offset in fallback_offsets[:n_fallbacks]:
            for px, py in _spiral_positions(
                cx0, cy0, theta_step, _MAX_THETA, theta_offset
            ):
                for vertical in orientations:
                    result = _try_place(
                        word,
                        fs,
                        px,
                        py,
                        vertical,
                        placed,
                        canvas_w,
                        canvas_h,
                        padding,
                    )
                    if result is not None:
                        return result

    return None


# -------------------------------------------------------------------------
#
# WordCloudWidget class
#
# -------------------------------------------------------------------------
class WordCloudWidget(Gtk.DrawingArea):
    """
    A GTK DrawingArea that renders a word cloud.

    words       : list of (word: str, count: int)
    on_click    : callable(word: str) or None
    color_low   : RGB tuple (0-1) for the lowest count
    color_high  : RGB tuple (0-1) for the highest count
    color_hover : RGB tuple (0-1) drawn when the mouse is over a word
    quality     : 0-1; 1 = tightest packing (slow), 0 = greedy (fast)
    """

    def __init__(
        self,
        words,
        on_click=None,
        color_low=(0.6, 0.8, 1.0),
        color_high=(0.0, 0.2, 0.6),
        color_hover=(0.8, 0.0, 0.0),
        quality=0.0,
    ):
        super().__init__()
        self._words = words
        self._on_click = on_click
        self._color_low = color_low
        self._color_high = color_high
        self._color_hover = color_hover
        self._quality = max(0.0, min(1.0, quality))
        self._layout = []
        self._layout_size = (0, 0)
        self._hovered = None
        self._resize_timer = None
        self._computing = False
        self._compute_id = None

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("draw", self._on_draw)
        self.connect("size-allocate", self._on_size_allocate)
        self.connect("button-press-event", self._on_click_event)
        self.connect("motion-notify-event", self._on_motion)

    def set_words(self, words):
        self._words = words
        self._invalidate()

    def set_quality(self, quality):
        self._quality = max(0.0, min(1.0, quality))
        self._invalidate()

    def set_colors(self, color_low, color_high, color_hover):
        self._color_low = color_low
        self._color_high = color_high
        self._color_hover = color_hover
        self.queue_draw()

    def configure(
        self, quality=None, color_low=None, color_high=None, color_hover=None
    ):
        """Update settings without triggering a redraw; call set_words() after."""
        if quality is not None:
            self._quality = max(0.0, min(1.0, quality))
        if color_low is not None:
            self._color_low = color_low
        if color_high is not None:
            self._color_high = color_high
        if color_hover is not None:
            self._color_hover = color_hover

    def _invalidate(self):
        self._layout_size = (0, 0)
        self._computing = True
        if self._compute_id is not None:
            GLib.source_remove(self._compute_id)
            self._compute_id = None
        self.queue_draw()

    def _compute_layout(self, canvas_w, canvas_h):
        self._layout = []
        if not self._words:
            return

        counts = [max(c, 1) for _, c in self._words]
        min_c, max_c = min(counts), max(counts)

        best_placed = []
        for min_font, max_font, padding in _QUALITY_LEVELS:
            word_info = []
            for (word, count), c in zip(self._words, counts):
                fs = _count_to_fontsize(c, min_c, max_c, min_font, max_font)
                color = _count_to_color(
                    c, min_c, max_c, self._color_low, self._color_high
                )
                word_info.append((word, c, fs, color))
            word_info.sort(key=lambda x: x[2], reverse=True)

            placed = []
            for word, count, fs, color in word_info:
                result = _place_word(
                    word, fs, canvas_w, canvas_h, placed, padding, self._quality
                )
                if result is not None:
                    result["color"] = color
                    placed.append(result)

            if len(placed) > len(best_placed):
                best_placed = placed

            if len(placed) == len(self._words):
                break

        self._layout = best_placed
        self._layout_size = (canvas_w, canvas_h)

    def _on_size_allocate(self, widget, allocation):
        new_size = (allocation.width, allocation.height)
        if new_size != self._layout_size:
            if self._resize_timer is not None:
                GLib.source_remove(self._resize_timer)
            self._resize_timer = GLib.timeout_add(300, self._on_resize_done)

    def _on_resize_done(self):
        self._resize_timer = None
        self._invalidate()
        return False

    def _draw_computing_message(self, cr, w, h):
        cr.set_source_rgb(0.97, 0.97, 0.97)
        cr.paint()
        cr.set_source_rgb(0.5, 0.5, 0.5)
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(_make_font_desc(18, style=Pango.Style.ITALIC))
        layout.set_text("Drawing…", -1)
        tw, th = layout.get_pixel_size()
        cr.move_to(w / 2 - tw / 2, h / 2 - th / 2)
        PangoCairo.show_layout(cr, layout)

    def _do_compute_layout(self, w, h):
        self._compute_id = None
        self._compute_layout(w, h)
        self._computing = False
        self.queue_draw()
        return False

    def _on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        w, h = alloc.width, alloc.height

        if self._resize_timer is not None:
            cr.set_source_rgb(0.97, 0.97, 0.97)
            cr.paint()
            return

        if self._computing:
            self._draw_computing_message(cr, w, h)
            if self._compute_id is None:
                self._compute_id = GLib.idle_add(self._do_compute_layout, w, h)
            return

        if self._layout_size != (w, h):
            self._compute_layout(w, h)

        cr.set_source_rgb(0.97, 0.97, 0.97)
        cr.paint()

        for pw in self._layout:
            hovered = pw["word"] == self._hovered
            cr.save()
            cr.set_source_rgb(*(self._color_hover if hovered else pw["color"]))

            layout = PangoCairo.create_layout(cr)
            layout.set_font_description(_make_font_desc(pw["font_size"]))
            layout.set_text(pw["word"], -1)

            p = pw["padding"]
            if pw["vertical"]:
                cr.translate(pw["ax"] + p + pw["th"], pw["ay"] + p)
                cr.rotate(math.pi / 2)
                cr.move_to(0, 0)
            else:
                cr.move_to(pw["ax"] + p, pw["ay"] + p)

            PangoCairo.show_layout(cr, layout)
            cr.restore()

    def _on_click_event(self, widget, event):
        if self._on_click is None:
            return
        x, y = event.x, event.y
        for pw in reversed(self._layout):
            if (
                pw["ax"] <= x <= pw["ax"] + pw["aw"]
                and pw["ay"] <= y <= pw["ay"] + pw["ah"]
            ):
                self._on_click(pw["word"])
                return

    def _on_motion(self, widget, event):
        x, y = event.x, event.y
        hit = None
        for pw in reversed(self._layout):
            if (
                pw["ax"] <= x <= pw["ax"] + pw["aw"]
                and pw["ay"] <= y <= pw["ay"] + pw["ah"]
            ):
                hit = pw["word"]
                break
        if hit != self._hovered:
            self._hovered = hit
            self.queue_draw()
