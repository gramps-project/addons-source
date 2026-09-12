# encoding:utf-8
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Context View
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
"""
Context View - a chart of a person's immediate family context.

The couple sits in the centre.  Each partner's parents are drawn above
them, in the manner of a vertical ancestor chart; the couple's children
are drawn below; and each partner's siblings are drawn in a column to
that partner's own side, level with the couple, eldest at the top and
siblings of unknown birth date at the foot of the column.

Clicking any box re-centres the chart on that person, so the chart can
be walked outwards in any direction.
"""

# -------------------------------------------------------------------------
#
# Python modules
#
# -------------------------------------------------------------------------
import math
import os
import pickle
from collections import defaultdict, deque

# -------------------------------------------------------------------------
#
# GTK/Gnome modules
#
# -------------------------------------------------------------------------
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango
from gi.repository import PangoCairo
import cairo

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from html import escape

from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import get_date
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.errors import WindowActiveError
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.db import (
    find_children,
    find_parents,
    find_witnessed_people,
    get_birth_or_fallback,
    get_marriage_or_fallback,
)
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.libformatting import FormattingHelper
from gramps.gen.utils.thumbnails import get_thumbnail_path
from gramps.gui.ddtargets import DdTargets
from gramps.gui.dialog import RunDatabaseRepair
from gramps.gui.display import display_help
from gramps.gui.editors import EditFamily, EditPerson
from gramps.gui.utils import (
    color_graph_box,
    get_contrast_color,
    hex_to_rgb_float,
    is_right_click,
)
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gui.views.navigationview import NavigationView

_ = glocale.get_addon_translator(__file__).sgettext

# A wiki page title, which display_help() expands against the Gramps wiki.
HELP_URL = "Addon:Context_View"

# -------------------------------------------------------------------------
#
# Layout constants (pixels)
#
# -------------------------------------------------------------------------
BOX_W = 176  # width of every person box
PAIR_GAP = 16  # between a father and a mother box
MID_GAP = 28  # least gap between the two sets of parents
BASE_GAP = 120  # least gap between the partners themselves
GEN_GAP = 66  # vertical gap between generations
SIB_GAP = 46  # between a sibling column and the block it flanks
SIB_VGAP = 10  # between siblings within a column
CHILD_GAP = 18  # between children in a row
CHILD_ROW_GAP = 30  # between wrapped rows of children
MAX_CHILD_ROW = 6  # children per row before wrapping
MARGIN = 28  # margin around the whole chart
BAR_DROP = 24  # how far a joining bar sits above the boxes it feeds


def _line_height(maxlines):
    """Box height needed for the given number of text lines."""
    return {1: 34, 3: 70, 5: 106}.get(maxlines, 70)


# -------------------------------------------------------------------------
#
# PersonBox
#
# -------------------------------------------------------------------------
class PersonBox(Gtk.DrawingArea):
    """
    One person, drawn with cairo in the Gramps graph-box colours.

    Left-click re-centres the chart on this person, double-click opens the
    person editor, right-click offers a short context menu.
    """

    def __init__(
        self, view, person, width, height, focus=False, pathway=False
    ):
        Gtk.DrawingArea.__init__(self)
        self.view = view
        self.person = person
        self.focus = focus
        self.pathway = pathway
        self.highlight = False
        self.in_drag = False
        self.textlayout = None
        self.img_surf = None
        self.set_size_request(width, height)

        dbstate = view.dbstate
        if person:
            self.text = view.format_helper.format_person(
                person, view.maxlines, True
            )
            if pathway:
                # The name alone is emboldened: it is the line that
                # identifies the box, and the dates stay legible beside the
                # other boxes in the same column.
                name, newline, rest = self.text.partition("\n")
                self.text = "<b>%s</b>%s%s" % (name, newline, rest)
            gender = person.get_gender()
            alive = probably_alive(person, dbstate.db)
        else:
            self.text = ""
            gender = None
            alive = False
        self.alive = alive

        bgcolor, bordercolor = color_graph_box(alive, gender)
        if view.show_tags and person:
            for tag_handle in person.get_tag_list():
                tag = dbstate.db.get_tag_from_handle(tag_handle)
                if tag and tag.get_color() not in ("#000000", "#000000000000"):
                    bgcolor = tag.get_color()
        self.bgcolor = hex_to_rgb_float(bgcolor)
        self.bordercolor = hex_to_rgb_float(bordercolor)

        if view.show_images and person:
            path = self._image_path(dbstate, person)
            if path and os.path.exists(path):
                try:
                    with open(path, "rb") as handle:
                        self.img_surf = cairo.ImageSurface.create_from_png(handle)
                except (OSError, cairo.Error):
                    self.img_surf = None

        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.ENTER_NOTIFY_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.connect("draw", self.on_draw)
        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        if person:
            self.connect("button-press-event", self.on_button_press)
            self.connect("button-release-event", self.on_button_release)
            self.set_tooltip_text(
                view.format_helper.format_person(person, 5, False)
            )
            self.connect("drag_data_get", self.on_drag_data_get)
            self.connect("drag_begin", self.on_drag_begin)
            self.connect("drag_end", self.on_drag_end)
            self.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK, [], Gdk.DragAction.COPY
            )
            tglist = Gtk.TargetList.new([])
            tglist.add(
                DdTargets.PERSON_LINK.atom_drag_type,
                DdTargets.PERSON_LINK.target_flags,
                DdTargets.PERSON_LINK.app_id,
            )
            tglist.add_text_targets(0)
            self.drag_source_set_target_list(tglist)

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _image_path(dbstate, person):
        """Thumbnail path of the person's first image, if any."""
        media_list = person.get_media_list()
        if not media_list:
            return None
        photo = media_list[0]
        obj = dbstate.db.get_media_from_handle(photo.get_reference_handle())
        if not obj:
            return None
        mime = obj.get_mime_type()
        if not mime or mime[0:5] != "image":
            return None
        return get_thumbnail_path(
            media_path_full(dbstate.db, obj.get_path()),
            rectangle=photo.get_rectangle(),
        )

    # -- events -----------------------------------------------------------

    def on_drag_begin(self, widget, data):
        self.in_drag = True
        self.drag_source_set_icon_name("gramps-person")

    def on_drag_end(self, widget, data):
        self.in_drag = False

    def on_drag_data_get(self, widget, context, sel_data, info, time):
        tgs = [x.name() for x in context.list_targets()]
        if info == DdTargets.PERSON_LINK.app_id:
            data = (
                DdTargets.PERSON_LINK.drag_type,
                id(self),
                self.person.get_handle(),
                0,
            )
            sel_data.set(sel_data.get_target(), 8, pickle.dumps(data))
        elif ("TEXT" in tgs or "text/plain" in tgs) and info == 0:
            sel_data.set_text(
                self.view.format_helper.format_person(self.person, 11), -1
            )

    def on_enter(self, widget, event):
        self.highlight = True
        self.queue_draw()

    def on_leave(self, widget, event):
        self.highlight = False
        self.queue_draw()

    def on_button_press(self, widget, event):
        # Gdk.Event.triggers_context_menu(), which is what is_right_click()
        # asks, is only ever true of a *press*; testing it on the release
        # silently never fires.
        if is_right_click(event):
            self.view.person_context_menu(event, self.person.get_handle())
            return True
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
            self.view.edit_person(self.person.get_handle())
            return True
        return False

    def on_button_release(self, widget, event):
        if self.in_drag:
            return False
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_RELEASE:
            self.view.change_active(self.person.get_handle())
            return True
        return False

    # -- drawing ----------------------------------------------------------

    def on_draw(self, widget, context):
        """Draw the rounded box, its border, the thumbnail and the text."""
        alloc = self.get_allocation()
        width, height = alloc.width, alloc.height

        def boxpath():
            radius = 6
            context.new_path()
            context.arc(radius, radius, radius, math.pi, 1.5 * math.pi)
            context.arc(width - 4 - radius, radius, radius, 1.5 * math.pi, 0)
            context.arc(
                width - 4 - radius, height - 4 - radius, radius, 0, 0.5 * math.pi
            )
            context.arc(
                radius, height - 4 - radius, radius, 0.5 * math.pi, math.pi
            )
            context.close_path()

        # drop shadow
        context.save()
        context.translate(3, 3)
        boxpath()
        context.set_source_rgba(*(self.bordercolor[:3] + (0.35,)))
        context.fill()
        context.restore()

        context.save()
        boxpath()
        context.clip_preserve()
        context.set_source_rgb(*self.bgcolor[:3])
        context.fill()

        imgw = 0
        if self.img_surf:
            # scale the thumbnail into a square at the right-hand end of the
            # box, keeping its aspect: much of this tree's media is record
            # scans rather than portraits, and they are any shape at all
            side = height - 12
            src_w = self.img_surf.get_width()
            src_h = self.img_surf.get_height()
            scale = min(side / float(src_w), side / float(src_h), 1.0)
            draw_w = src_w * scale
            draw_h = src_h * scale
            context.save()
            context.translate(width - 8 - draw_w, (height - 4 - draw_h) / 2)
            context.scale(scale, scale)
            context.set_source_surface(self.img_surf, 0, 0)
            context.paint()
            context.restore()
            imgw = int(draw_w) + 6

        # a corner slash marks the deceased, as in the pedigree view
        if self.person and not self.alive:
            context.set_source_rgb(0, 0, 0)
            context.set_line_width(2)
            context.move_to(0, 11)
            context.line_to(11, 0)
            context.stroke()
        context.restore()

        # border: heavier for the person the chart is centred on
        context.save()
        boxpath()
        if self.focus:
            context.set_line_width(4)
        elif self.highlight:
            context.set_line_width(3)
        else:
            context.set_line_width(1.5)
        context.set_source_rgb(*self.bordercolor[:3])
        context.stroke()
        context.restore()

        if not self.person:
            return

        if not self.textlayout:
            self.textlayout = PangoCairo.create_layout(context)
            font_desc = self.get_style_context().get_font(Gtk.StateFlags.NORMAL)
            self.textlayout.set_font_description(font_desc)
            self.textlayout.set_markup(self.text, -1)
            self.textlayout.set_width((width - 12 - imgw) * Pango.SCALE)
            self.textlayout.set_ellipsize(Pango.EllipsizeMode.END)

        context.save()
        context.move_to(6, 4)
        context.set_source_rgb(*get_contrast_color(self.bgcolor)[:3])
        PangoCairo.show_layout(context, self.textlayout)
        context.restore()


# -------------------------------------------------------------------------
#
# ChartCanvas
#
# -------------------------------------------------------------------------
class ChartCanvas(Gtk.DrawingArea):
    """
    The backdrop that carries the joining lines and the marriage captions.
    The person boxes are laid over it in a Gtk.Fixed.
    """

    def __init__(self):
        Gtk.DrawingArea.__init__(self)
        self.segments = []
        self.captions = []
        self.message = None
        self.connect("draw", self.on_draw)

    def clear(self):
        self.segments = []
        self.captions = []
        self.message = None

    def on_draw(self, widget, context):
        style = self.get_style_context()
        fg = style.get_color(Gtk.StateFlags.NORMAL)

        if self.message is not None:
            layout = PangoCairo.create_layout(context)
            layout.set_font_description(style.get_font(Gtk.StateFlags.NORMAL))
            layout.set_markup(self.message, -1)
            context.set_source_rgba(fg.red, fg.green, fg.blue, 0.7)
            context.move_to(MARGIN, MARGIN)
            PangoCairo.show_layout(context, layout)
            return

        context.set_source_rgba(fg.red, fg.green, fg.blue, 0.55)
        context.set_line_width(1.5)
        context.set_line_cap(cairo.LINE_CAP_ROUND)
        for (x_1, y_1), (x_2, y_2) in self.segments:
            context.move_to(x_1, y_1)
            context.line_to(x_2, y_2)
        context.stroke()

        if not self.captions:
            return
        layout = PangoCairo.create_layout(context)
        layout.set_font_description(style.get_font(Gtk.StateFlags.NORMAL))
        layout.set_alignment(Pango.Alignment.CENTER)
        context.set_source_rgba(fg.red, fg.green, fg.blue, 0.8)
        for centre_x, bottom_y, markup in self.captions:
            layout.set_markup(markup, -1)
            width, height = layout.get_pixel_size()
            context.move_to(centre_x - width / 2, bottom_y - height)
            PangoCairo.show_layout(context, layout)


# -------------------------------------------------------------------------
#
# ContextView
#
# -------------------------------------------------------------------------
class ContextView(NavigationView):
    """
    A chart of the active person's immediate family context.
    """

    CONFIGSETTINGS = (
        ("interface.contextview-show-images", False),
        ("interface.contextview-show-tags", False),
        ("interface.contextview-show-siblings", True),
        ("interface.contextview-show-marriage", True),
        ("interface.contextview-max-lines", 3),
    )

    def __init__(self, pdata, dbstate, uistate, nav_group=0):
        NavigationView.__init__(
            self, _("Context"), pdata, dbstate, uistate, PersonBookmarks, nav_group
        )
        self.dbstate = dbstate
        self.uistate = uistate
        self.dbstate.connect("database-changed", self.change_db)
        uistate.connect("nameformat-changed", self.person_rebuild)
        uistate.connect("placeformat-changed", self.person_rebuild)
        uistate.connect("font-changed", self.person_rebuild)

        self.format_helper = FormattingHelper(self.dbstate, self.uistate)

        self.scrolledwindow = None
        self.canvas = None
        self.fixed = None
        self.spouse_bar = None
        self.spouse_label = None
        self.home_hint = None
        self.legend_bar = None
        self.legend = None
        self.family_index = 0
        self._shown_handle = None
        self._home_cache = None
        self._home_cache_for = None
        self._menu = None
        self._last_x = 0
        self._last_y = 0
        self._in_move = False

        self.show_images = self._config.get("interface.contextview-show-images")
        self.show_tags = self._config.get("interface.contextview-show-tags")
        self.show_siblings = self._config.get("interface.contextview-show-siblings")
        self.show_marriage = self._config.get("interface.contextview-show-marriage")
        self.maxlines = self._config.get("interface.contextview-max-lines")

        self.additional_uis.append(self.additional_ui)

    # -- plumbing ---------------------------------------------------------

    def navigation_type(self):
        return "Person"

    def get_stock(self):
        return "gramps-relation"

    def get_viewtype_stock(self):
        return "gramps-relation"

    def can_configure(self):
        return True

    def on_delete(self):
        self._config.save()
        NavigationView.on_delete(self)

    def build_widget(self):
        """
        Build the scrolling chart area: a backdrop carrying the joining
        lines, with the person boxes laid over it in a Gtk.Fixed, and a
        partner selector strip above when the person has more than one
        family.
        """
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.spouse_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.spouse_bar.set_border_width(4)
        prev_button = Gtk.Button.new_from_icon_name(
            "go-previous", Gtk.IconSize.BUTTON
        )
        prev_button.set_tooltip_text(_("Show the previous family"))
        prev_button.connect("clicked", self.cb_family_step, -1)
        next_button = Gtk.Button.new_from_icon_name("go-next", Gtk.IconSize.BUTTON)
        next_button.set_tooltip_text(_("Show the next family"))
        next_button.connect("clicked", self.cb_family_step, 1)
        self.spouse_label = Gtk.Label()
        self.spouse_bar.pack_start(prev_button, False, False, 0)
        self.spouse_bar.pack_start(self.spouse_label, False, False, 0)
        self.spouse_bar.pack_start(next_button, False, False, 0)
        self.home_hint = Gtk.Label()
        self.home_hint.set_margin_start(12)
        self.spouse_bar.pack_start(self.home_hint, False, False, 0)
        container.pack_start(self.spouse_bar, False, False, 0)

        # Shown in the same place when there is no family selector to show:
        # without it the emboldened name means nothing to a new reader.
        self.legend_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.legend_bar.set_border_width(4)
        self.legend = Gtk.Label()
        self.legend.set_halign(Gtk.Align.START)
        self.legend_bar.pack_start(self.legend, False, False, 0)
        container.pack_start(self.legend_bar, False, False, 0)

        self.scrolledwindow = Gtk.ScrolledWindow()
        self.scrolledwindow.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        event_box = Gtk.EventBox()
        event_box.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.BUTTON1_MOTION_MASK
        )
        event_box.connect("button-press-event", self.cb_bg_button_press)
        event_box.connect("button-release-event", self.cb_bg_button_release)
        event_box.connect("motion-notify-event", self.cb_bg_motion_notify)

        overlay = Gtk.Overlay()
        self.canvas = ChartCanvas()
        overlay.add(self.canvas)
        self.fixed = Gtk.Fixed()
        self.fixed.set_halign(Gtk.Align.START)
        self.fixed.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.fixed)
        event_box.add(overlay)
        self.scrolledwindow.add(event_box)
        container.pack_start(self.scrolledwindow, True, True, 0)

        return container

    def _connect_db_signals(self):
        self._add_db_signal("person-add", self.person_rebuild)
        self._add_db_signal("person-update", self.person_rebuild)
        self._add_db_signal("person-delete", self.person_rebuild)
        self._add_db_signal("person-rebuild", self.person_rebuild_bm)
        self._add_db_signal("family-add", self.person_rebuild)
        self._add_db_signal("family-update", self.person_rebuild)
        self._add_db_signal("family-delete", self.person_rebuild)
        self._add_db_signal("family-rebuild", self.person_rebuild)
        self._add_db_signal("event-update", self.person_rebuild)
        self._add_db_signal("home-person-changed", self.person_rebuild)

    def change_db(self, db):
        self._change_db(db)
        self._home_cache = None
        if self.active:
            self.bookmarks.redraw()
        self.build_tree()

    def build_tree(self):
        try:
            self.rebuild(self.get_active())
        except AttributeError as msg:
            RunDatabaseRepair(str(msg), parent=self.uistate.window)

    def change_page(self):
        NavigationView.change_page(self)
        self.uistate.clear_filter_results()
        if self.dirty:
            self.rebuild(self.get_active())

    def goto_handle(self, handle=None):
        self.dirty = True
        if handle != self._shown_handle:
            self.family_index = 0
        self.rebuild(handle)
        self.uistate.modify_statusbar(self.dbstate)

    def person_rebuild_bm(self, dummy=None):
        self.person_rebuild(dummy)
        if self.active:
            self.bookmarks.redraw()

    def person_rebuild(self, dummy=None):
        self.format_helper.clear_cache()
        self.format_helper.reload_symbols()
        self._home_cache = None
        self.dirty = True
        if self.active:
            self.rebuild(self.get_active())

    # -- data helpers -----------------------------------------------------

    def _person(self, handle):
        if not handle:
            return None
        return self.dbstate.db.get_person_from_handle(handle)

    def _birth_key(self, handle):
        """
        Sort key putting the eldest first and anyone whose birth date is
        unknown at the end.  Python's sort is stable, so people with no
        date keep the order they hold in the database.
        """
        person = self._person(handle)
        if person:
            event = get_birth_or_fallback(self.dbstate.db, person)
            if event:
                sortval = event.get_date_object().get_sort_value()
                if sortval:
                    return (0, sortval)
        return (1, 0)

    def _home_distances(self):
        """
        Breadth-first distances from the home person, measured over the graph
        this chart itself navigates: from any person a single click reaches
        their parents, their children, their partners and their siblings.

        The result is cached, and recomputed when the home person changes or
        the database is edited.
        """
        db = self.dbstate.db
        home_handle = db.get_default_handle()
        if not home_handle:
            self._home_cache, self._home_cache_for = {}, None
            return self._home_cache
        if self._home_cache is not None and self._home_cache_for == home_handle:
            return self._home_cache

        neighbours = defaultdict(set)

        def link(one, other):
            neighbours[one].add(other)
            neighbours[other].add(one)

        for family in db.iter_families():
            parents = [
                handle
                for handle in (
                    family.get_father_handle(),
                    family.get_mother_handle(),
                )
                if handle
            ]
            children = [ref.ref for ref in family.get_child_ref_list()]
            if len(parents) == 2:
                link(parents[0], parents[1])
            for parent in parents:
                for child in children:
                    link(parent, child)
            for index, child in enumerate(children):
                for sibling in children[index + 1 :]:
                    link(child, sibling)

        distances = {home_handle: 0}
        queue = deque([home_handle])
        while queue:
            handle = queue.popleft()
            step = distances[handle] + 1
            for other in neighbours[handle]:
                if other not in distances:
                    distances[other] = step
                    queue.append(other)

        self._home_cache, self._home_cache_for = distances, home_handle
        return distances

    def _family_reach(self, person_handle, family):
        """
        The people a chart of this family would put within one click: the
        partner, that partner's parents and siblings, and the children.
        """
        partner = family.get_mother_handle()
        if partner == person_handle:
            partner = family.get_father_handle()
        handles = set()
        if partner:
            handles.add(partner)
            parents, siblings = self._origin(partner)
            handles.update(handle for handle in parents if handle)
            handles.update(siblings)
        handles.update(ref.ref for ref in family.get_child_ref_list())
        handles.discard(person_handle)
        return handles

    def _family_toward_home(self, person_handle, family_handles):
        """
        Where a person has more than one family, the index of the family
        whose chart comes nearest the home person, or None if none of them
        does better than standing still.  Without this a walk home can halt
        on someone whose way back lies through a family not on show.
        """
        distances = self._home_distances()
        if not distances:
            return None
        here = distances.get(person_handle)
        if not here:
            return None
        best_index, best = None, here
        for index, family_handle in enumerate(family_handles):
            family = self.dbstate.db.get_family_from_handle(family_handle)
            if not family:
                continue
            reach = [
                distances[handle]
                for handle in self._family_reach(person_handle, family)
                if handle in distances
            ]
            if reach and min(reach) < best:
                best_index, best = index, min(reach)
        return best_index

    def _pathway_handles(self, focus_handle, shown):
        """
        Of the people on the chart, those lying nearer the home person, so
        that the way back is always the next click.  Where two boxes are
        equally near, both are marked rather than one chosen arbitrarily.

        Nothing at all is marked once the home person is themselves on the
        chart, whether centred or merely drawn on it: the bold is a direction
        to walk in, and at that point there is nowhere left to walk.
        """
        distances = self._home_distances()
        if not distances:
            return set()
        home_handle = self.dbstate.db.get_default_handle()
        if not home_handle or home_handle in shown:
            return set()
        here = distances.get(focus_handle)
        if not here:
            return set()

        # The nearest box on the chart, not merely the nearest neighbour: a
        # partner's parents are drawn here too, and clicking one of those
        # covers two steps of the walk at once.
        reachable = [
            (distances[handle], handle)
            for handle in shown
            if handle in distances and handle != focus_handle
        ]
        if not reachable:
            return set()
        nearest = min(step for step, _handle in reachable)
        if nearest >= here:
            return set()
        return {handle for step, handle in reachable if step == nearest}

    def _parent_family(self, person):
        """The family in which this person is a child, if any."""
        handles = person.get_parent_family_handle_list()
        if not handles:
            return None
        return self.dbstate.db.get_family_from_handle(handles[0])

    def _origin(self, handle):
        """
        Return (parent_handles, sibling_handles) for one partner.
        parent_handles is [father, mother], either of which may be None.
        Siblings are ordered eldest first, unknown birth dates last.
        """
        person = self._person(handle)
        if not person:
            return [None, None], []
        family = self._parent_family(person)
        if not family:
            return [None, None], []
        parents = [family.get_father_handle(), family.get_mother_handle()]
        siblings = []
        if self.show_siblings:
            siblings = [
                ref.ref
                for ref in family.get_child_ref_list()
                if ref.ref != handle
            ]
            siblings.sort(key=self._birth_key)
        return parents, siblings

    @staticmethod
    def _block_width(parents):
        known = len([handle for handle in parents if handle])
        if known == 2:
            return 2 * BOX_W + PAIR_GAP
        if known == 1:
            return BOX_W
        return 0

    def _marriage_caption(self, family):
        if not family or not self.show_marriage:
            return None
        event = get_marriage_or_fallback(self.dbstate.db, family)
        if not event:
            return None
        date = get_date(event)
        place = self.format_helper.get_place_name(event.get_place_handle())
        parts = [escape(part) for part in (date, place) if part]
        if not parts:
            return None
        return "<small>%s</small>" % "\n".join(parts)

    # -- layout -----------------------------------------------------------

    def rebuild(self, person_handle):
        """Lay the chart out afresh around the given person."""
        if self.fixed is None:
            return
        self.dirty = False
        self._shown_handle = person_handle

        for child in self.fixed.get_children():
            self.fixed.remove(child)
        self.canvas.clear()

        person = self._person(person_handle)
        if person is None:
            self.spouse_bar.hide()
            self.legend_bar.hide()
            self.canvas.message = _("No person is active.")
            self.canvas.set_size_request(400, 200)
            self.canvas.queue_draw()
            return

        families = person.get_family_handle_list()
        if self.family_index >= len(families):
            self.family_index = 0
        family = None
        if families:
            family = self.dbstate.db.get_family_from_handle(
                families[self.family_index]
            )

        if len(families) > 1:
            self.spouse_label.set_text(
                _("Family %(current)d of %(total)d")
                % {"current": self.family_index + 1, "total": len(families)}
            )
            toward_home = self._family_toward_home(person_handle, families)
            if toward_home is not None and toward_home != self.family_index:
                self.home_hint.set_markup(
                    "<i>%s</i>"
                    % (_("family %d lies toward the home person") % (toward_home + 1))
                )
            else:
                self.home_hint.set_text("")
            self.spouse_bar.show_all()
            self.legend_bar.hide()
        else:
            self.spouse_bar.hide()
            self._show_legend()

        # Which partner is drawn on which side.  Gramps records the roles,
        # so the father keeps the left-hand place and the mother the right.
        left_handle = right_handle = None
        if family:
            father = family.get_father_handle()
            mother = family.get_mother_handle()
            if father and mother:
                left_handle, right_handle = father, mother
            else:
                left_handle = father or mother or person_handle
        else:
            left_handle = person_handle

        boxes, segments, captions, size = self._layout(
            left_handle, right_handle, family, person_handle
        )

        width, height = size
        self.canvas.segments = segments
        self.canvas.captions = captions
        self.canvas.set_size_request(width, height)
        self.fixed.set_size_request(width, height)

        pathway = self._pathway_handles(
            person_handle, {handle for handle, _x, _y, _h, _f in boxes}
        )
        for handle, pos_x, pos_y, box_h, focus in boxes:
            box = PersonBox(
                self,
                self._person(handle),
                BOX_W,
                box_h,
                focus=focus,
                pathway=handle in pathway,
            )
            self.fixed.put(box, pos_x, pos_y)

        self.fixed.show_all()
        self.canvas.queue_draw()

    def _show_legend(self):
        """
        Explain the bold, but only when it can occur: with no home person set
        nothing is ever emboldened, and a legend for it would mislead.
        """
        if self.dbstate.db.get_default_handle():
            self.legend.set_markup(
                "<small>%s</small>"
                % _("<b>Bold</b> marks the way to the home person")
            )
            self.legend_bar.show_all()
        else:
            self.legend_bar.hide()

    def _layout(self, left_handle, right_handle, family, focus_handle):
        """
        Work the geometry out in a free coordinate space, then shift
        everything into positive coordinates with a margin.

        Returns (boxes, segments, captions, (width, height)) where boxes is
        a list of (handle, x, y, height, is_focus).
        """
        box_h = _line_height(self.maxlines)
        boxes = []
        segments = []
        captions = []

        left_parents, left_sibs = self._origin(left_handle)
        if right_handle:
            right_parents, right_sibs = self._origin(right_handle)
        else:
            right_parents, right_sibs = [None, None], []

        left_block = self._block_width(left_parents)
        right_block = self._block_width(right_parents)

        # The couple must stand far enough apart that the two sets of
        # parents, each centred over its own partner, do not collide.
        gap = BASE_GAP
        if right_handle:
            needed = left_block / 2 + right_block / 2 + MID_GAP - BOX_W
            gap = max(BASE_GAP, needed)

        left_x = 0.0
        left_cx = left_x + BOX_W / 2
        right_x = left_x + BOX_W + gap
        right_cx = right_x + BOX_W / 2

        y_parents = 0.0
        y_couple = y_parents + box_h + GEN_GAP
        cy_couple = y_couple + box_h / 2
        y_children = y_couple + box_h + GEN_GAP

        boxes.append(
            (left_handle, left_x, y_couple, box_h, left_handle == focus_handle)
        )
        if right_handle:
            boxes.append(
                (right_handle, right_x, y_couple, box_h, right_handle == focus_handle)
            )
            # the marriage line between the partners
            segments.append(((left_x + BOX_W, cy_couple), (right_x, cy_couple)))
            caption = self._marriage_caption(family)
            if caption:
                captions.append(
                    ((left_x + BOX_W + right_x) / 2, cy_couple - 6, caption)
                )

        couple_mid = (left_cx + right_cx) / 2 if right_handle else left_cx

        # Children are worked out before the siblings, because a wide row of
        # them reaches out under the sibling columns and so decides how far
        # out those columns have to stand.
        children = []
        if family:
            children = [ref.ref for ref in family.get_child_ref_list()]
            children.sort(key=self._birth_key)
        child_rows = self._child_rows(children, couple_mid, y_children, box_h)
        child_zone = None
        if child_rows:
            all_x = [pos_x for _row_y, row in child_rows for _h, pos_x in row]
            child_zone = (min(all_x), max(all_x) + BOX_W, y_children - BAR_DROP)

        # -- each partner's parents and siblings --------------------------
        for handle, centre_x, parents, siblings, block, side in (
            (left_handle, left_cx, left_parents, left_sibs, left_block, -1),
            (right_handle, right_cx, right_parents, right_sibs, right_block, 1),
        ):
            if handle is None:
                continue
            self._layout_origin(
                boxes,
                segments,
                centre_x,
                parents,
                siblings,
                block,
                side,
                y_parents,
                y_couple,
                cy_couple,
                box_h,
                focus_handle,
                child_zone,
            )

        drop_from = cy_couple if right_handle else y_couple + box_h
        self._place_children(
            boxes, segments, child_rows, couple_mid, drop_from, box_h, focus_handle
        )

        return self._normalise(boxes, segments, captions)

    @staticmethod
    def _child_rows(children, couple_mid, y_children, box_h):
        """
        Position the children in one or more rows centred under the couple,
        wrapping once a row would grow past MAX_CHILD_ROW.  Returns a list of
        (row_y, [(handle, x), ...]).
        """
        if not children:
            return []
        rows = int(math.ceil(len(children) / float(MAX_CHILD_ROW)))
        per_row = int(math.ceil(len(children) / float(rows)))
        result = []
        for index in range(0, len(children), per_row):
            row = children[index : index + per_row]
            row_y = y_children + len(result) * (box_h + CHILD_ROW_GAP)
            row_width = len(row) * BOX_W + (len(row) - 1) * CHILD_GAP
            start_x = couple_mid - row_width / 2
            result.append(
                (
                    row_y,
                    [
                        (handle, start_x + position * (BOX_W + CHILD_GAP))
                        for position, handle in enumerate(row)
                    ],
                )
            )
        return result

    @staticmethod
    def _place_children(
        boxes, segments, child_rows, couple_mid, drop_from, box_h, focus_handle
    ):
        """Add the children's boxes and the bars that join them to the couple."""
        if not child_rows:
            return
        first_bar_y = child_rows[0][0] - BAR_DROP
        outer_x = min(pos_x for _h, pos_x in child_rows[0][1]) - CHILD_GAP
        wrapped = len(child_rows) > 1

        for row_index, (row_y, entries) in enumerate(child_rows):
            bar_y = row_y - BAR_DROP
            centres = []
            for handle, child_x in entries:
                boxes.append((handle, child_x, row_y, box_h, handle == focus_handle))
                child_cx = child_x + BOX_W / 2
                centres.append(child_cx)
                segments.append(((child_cx, bar_y), (child_cx, row_y)))
            left_end = outer_x if wrapped else min(centres)
            segments.append(((left_end, bar_y), (max(centres), bar_y)))
            if row_index:
                # carry the connection down the outside of the rows above
                segments.append(((outer_x, first_bar_y), (outer_x, bar_y)))

        segments.append(((couple_mid, drop_from), (couple_mid, first_bar_y)))

    def _layout_origin(
        self,
        boxes,
        segments,
        centre_x,
        parents,
        siblings,
        block,
        side,
        y_parents,
        y_couple,
        cy_couple,
        box_h,
        focus_handle,
        child_zone,
    ):
        """
        Place one partner's parents above them and that partner's siblings
        in a column to their own side, and join the lot to a single bar so
        that the partner and their siblings visibly share the same parents.
        """
        bar_y = y_parents + box_h + GEN_GAP / 2
        known = [handle for handle in parents if handle]

        if known:
            if len(known) == 2:
                positions = [
                    centre_x - PAIR_GAP / 2 - BOX_W,
                    centre_x + PAIR_GAP / 2,
                ]
            else:
                positions = [centre_x - BOX_W / 2]
            for handle, parent_x in zip(known, positions):
                boxes.append(
                    (handle, parent_x, y_parents, box_h, handle == focus_handle)
                )
                parent_cx = parent_x + BOX_W / 2
                segments.append(((parent_cx, y_parents + box_h), (parent_cx, bar_y)))
            if len(known) == 2:
                segments.append(
                    (
                        (positions[0] + BOX_W / 2, bar_y),
                        (positions[1] + BOX_W / 2, bar_y),
                    )
                )
            # down from the bar into the partner
            segments.append(((centre_x, bar_y), (centre_x, y_couple)))
        elif siblings:
            # no parent is recorded, but the parent family exists: hang the
            # partner and the siblings from a bare bar all the same
            segments.append(((centre_x, bar_y), (centre_x, y_couple)))

        if not siblings:
            return

        total_h = len(siblings) * box_h + (len(siblings) - 1) * SIB_VGAP
        top_y = cy_couple - total_h / 2

        # outer edge of everything already placed on this side
        if block:
            edge = centre_x + side * (block / 2)
        else:
            edge = centre_x + side * (BOX_W / 2)

        # A long column hangs down as far as the children; where it does, it
        # must also stand clear of the row of children, which is wider than
        # the couple whenever there are several of them.
        if child_zone and top_y + total_h > child_zone[2] - SIB_VGAP:
            if side < 0:
                edge = min(edge, child_zone[0])
            else:
                edge = max(edge, child_zone[1])

        spine_x = edge + side * SIB_GAP / 2
        column_x = edge + side * SIB_GAP
        if side < 0:
            column_x -= BOX_W

        centres = []
        for index, handle in enumerate(siblings):
            sib_y = top_y + index * (box_h + SIB_VGAP)
            boxes.append((handle, column_x, sib_y, box_h, handle == focus_handle))
            sib_cy = sib_y + box_h / 2
            centres.append(sib_cy)
            inner_edge = column_x + BOX_W if side < 0 else column_x
            segments.append(((spine_x, sib_cy), (inner_edge, sib_cy)))

        # the spine, and its run back to the parents' bar
        segments.append(
            ((spine_x, min(min(centres), bar_y)), (spine_x, max(max(centres), bar_y)))
        )
        segments.append(((spine_x, bar_y), (centre_x, bar_y)))

    @staticmethod
    def _normalise(boxes, segments, captions):
        """Shift everything into positive coordinates and add a margin."""
        xs = []
        ys = []
        for _handle, pos_x, pos_y, box_h, _focus in boxes:
            xs.extend((pos_x, pos_x + BOX_W))
            ys.extend((pos_y, pos_y + box_h))
        for (x_1, y_1), (x_2, y_2) in segments:
            xs.extend((x_1, x_2))
            ys.extend((y_1, y_2))
        if not xs:
            return [], [], [], (400, 200)

        off_x = MARGIN - min(xs)
        off_y = MARGIN - min(ys)
        width = int(max(xs) - min(xs) + 2 * MARGIN)
        height = int(max(ys) - min(ys) + 2 * MARGIN)

        boxes = [
            (handle, int(pos_x + off_x), int(pos_y + off_y), box_h, focus)
            for handle, pos_x, pos_y, box_h, focus in boxes
        ]
        segments = [
            ((x_1 + off_x, y_1 + off_y), (x_2 + off_x, y_2 + off_y))
            for (x_1, y_1), (x_2, y_2) in segments
        ]
        captions = [
            (centre_x + off_x, bottom_y + off_y, markup)
            for centre_x, bottom_y, markup in captions
        ]
        return boxes, segments, captions, (width, height)

    # -- interaction -------------------------------------------------------

    def cb_family_step(self, button, step):
        person = self._person(self._shown_handle)
        if not person:
            return
        count = len(person.get_family_handle_list())
        if count < 2:
            return
        self.family_index = (self.family_index + step) % count
        self.rebuild(self._shown_handle)

    def edit_person(self, handle):
        person = self._person(handle)
        if not person:
            return
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def edit_family(self, handle):
        family = self.dbstate.db.get_family_from_handle(handle)
        if not family:
            return
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def cb_goto_person(self, menuitem, handle):
        """Menu entries that name a person re-centre the chart on them."""
        self.change_active(handle)

    def cb_home(self, menuitem):
        handle = self.dbstate.db.get_default_handle()
        if handle:
            self.change_active(handle)

    def cb_set_home(self, menuitem, handle):
        if handle:
            self.dbstate.db.set_default_person_handle(handle)

    def cb_copy_person_to_clipboard(self, menuitem, handle):
        """Put a few lines about the person on the clipboard."""
        person = self._person(handle)
        if not person:
            return False
        clipboard = Gtk.Clipboard.get_for_display(
            Gdk.Display.get_default(), Gdk.SELECTION_CLIPBOARD
        )
        clipboard.set_text(self.format_helper.format_person(person, 11), -1)
        return True

    def cb_toggle_setting(self, menuitem, setting):
        self._config.set(setting, menuitem.get_active())

    def on_help_clicked(self, dummy):
        display_help(HELP_URL)

    def _add_person_item(self, menu, handle, emphasise=False):
        """
        One person entry.  A Gtk.Label carries the text rather than the menu
        item itself, because only a label will render the markup that marks
        out the people who lead somewhere further.
        """
        person = self._person(handle)
        if not person:
            return
        text = escape(name_displayer.display(person))
        label = Gtk.Label(label="<b><i>%s</i></b>" % text if emphasise else text)
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        label.show()
        item = Gtk.MenuItem()
        item.add(label)
        item.connect("activate", self.cb_goto_person, handle)
        item.show()
        menu.append(item)

    def _add_person_submenu(self, menu, title, handles, emphasise=None):
        """A submenu of people, insensitive when there are none."""
        item = Gtk.MenuItem(label=title)
        handles = [handle for handle in handles if self._person(handle)]
        if handles:
            item.set_submenu(Gtk.Menu())
            submenu = item.get_submenu()
            submenu.set_reserve_toggle_size(False)
            for handle in handles:
                self._add_person_item(
                    submenu, handle, emphasise(handle) if emphasise else False
                )
        else:
            item.set_sensitive(False)
        item.show()
        menu.append(item)

    def add_nav_portion_to_menu(self, menu, person_handle):
        """The history navigation common to both menus."""
        history = self.get_history()
        entries = (
            (_("Pre_vious"), self.back_clicked, not history.at_front()),
            (_("_Next"), self.fwd_clicked, not history.at_end()),
            (_("_Home"), self.cb_home, bool(self.dbstate.db.get_default_handle())),
        )
        for label, callback, sensitive in entries:
            item = Gtk.MenuItem.new_with_mnemonic(label)
            item.set_sensitive(sensitive)
            item.connect("activate", callback)
            item.show()
            menu.append(item)
        item = Gtk.MenuItem.new_with_mnemonic(_("Set _Home Person"))
        item.connect("activate", self.cb_set_home, person_handle)
        item.set_sensitive(person_handle is not None)
        item.show()
        menu.append(item)

    def add_settings_to_menu(self, menu):
        """The settings changed often enough to be worth a right-click."""
        item = Gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)
        for label, setting in (
            (_("Show siblings"), "interface.contextview-show-siblings"),
            (_("Show images"), "interface.contextview-show-images"),
            (_("Show marriage data"), "interface.contextview-show-marriage"),
        ):
            entry = Gtk.CheckMenuItem(label=label)
            entry.set_active(self._config.get(setting))
            entry.connect("toggled", self.cb_toggle_setting, setting)
            entry.show()
            menu.append(entry)

        item = Gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)
        item = Gtk.MenuItem.new_with_mnemonic(_("About Context View"))
        item.connect("activate", self.on_help_clicked)
        item.show()
        menu.append(item)

    def person_context_menu(self, event, handle):
        """
        The full right-click menu, as the pedigree view offers it: the person
        themselves, editing and copying, then their spouses, siblings,
        children, parents and the people they are recorded as witnessing,
        then history navigation and the display settings.
        """
        person = self._person(handle)
        if not person:
            return
        db = self.dbstate.db
        self._menu = Gtk.Menu()
        self._menu.set_reserve_toggle_size(False)

        self._add_person_item(self._menu, handle)

        item = Gtk.MenuItem.new_with_mnemonic(_("_Edit"))
        item.connect("activate", lambda _w: self.edit_person(handle))
        item.show()
        self._menu.append(item)

        item = Gtk.MenuItem.new_with_mnemonic(_("_Copy"))
        item.connect("activate", self.cb_copy_person_to_clipboard, handle)
        item.show()
        self._menu.append(item)

        # not in the pedigree menu, but this view draws couples, so editing
        # the family the box sits in is worth reaching from here
        families = [
            family_handle
            for family_handle in person.get_family_handle_list()
            if db.get_family_from_handle(family_handle)
        ]
        if families:
            item = Gtk.MenuItem(label=_("Edit Family"))
            if len(families) == 1:
                item.connect("activate", lambda _w: self.edit_family(families[0]))
            else:
                item.set_submenu(Gtk.Menu())
                submenu = item.get_submenu()
                submenu.set_reserve_toggle_size(False)
                for family_handle in families:
                    family = db.get_family_from_handle(family_handle)
                    other = family.get_mother_handle()
                    if other == handle:
                        other = family.get_father_handle()
                    other_person = self._person(other)
                    entry = Gtk.MenuItem(
                        label=name_displayer.display(other_person)
                        if other_person
                        else _("Unknown")
                    )
                    entry.connect(
                        "activate",
                        lambda _w, fam=family_handle: self.edit_family(fam),
                    )
                    entry.show()
                    submenu.append(entry)
            item.show()
            self._menu.append(item)

        item = Gtk.SeparatorMenuItem()
        item.show()
        self._menu.append(item)

        spouses = []
        for family_handle in person.get_family_handle_list():
            family = db.get_family_from_handle(family_handle)
            if not family:
                continue
            other = family.get_mother_handle()
            if other == handle:
                other = family.get_father_handle()
            if other:
                spouses.append(other)
        self._add_person_submenu(self._menu, _("Spouses"), spouses)

        siblings = []
        for family_handle in person.get_parent_family_handle_list():
            family = db.get_family_from_handle(family_handle)
            if not family:
                continue
            siblings.extend(
                ref.ref for ref in family.get_child_ref_list() if ref.ref != handle
            )
        self._add_person_submenu(
            self._menu,
            _("Siblings"),
            siblings,
            lambda other: bool(find_children(db, self._person(other))),
        )
        self._add_person_submenu(
            self._menu,
            _("Children"),
            find_children(db, person),
            lambda other: bool(find_children(db, self._person(other))),
        )
        self._add_person_submenu(
            self._menu,
            _("Parents"),
            find_parents(db, person),
            lambda other: bool(find_parents(db, self._person(other))),
        )
        self._add_person_submenu(
            self._menu, _("Related"), find_witnessed_people(db, person)
        )

        item = Gtk.SeparatorMenuItem()
        item.show()
        self._menu.append(item)
        self.add_nav_portion_to_menu(self._menu, handle)
        self.add_settings_to_menu(self._menu)
        self._menu.popup_at_pointer(event)

    def background_context_menu(self, event):
        """Right-click on empty chart: navigation and settings only."""
        self._menu = Gtk.Menu()
        self._menu.set_reserve_toggle_size(False)
        self.add_nav_portion_to_menu(self._menu, None)
        self.add_settings_to_menu(self._menu)
        self._menu.popup_at_pointer(event)

    # -- background drag to pan -------------------------------------------

    def cb_bg_button_press(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
            widget.get_window().set_cursor(
                Gdk.Cursor.new_for_display(
                    Gdk.Display.get_default(), Gdk.CursorType.FLEUR
                )
            )
            self._last_x = event.x
            self._last_y = event.y
            self._in_move = True
            return True
        if is_right_click(event):
            self.background_context_menu(event)
            return True
        return False

    def cb_bg_button_release(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType.BUTTON_RELEASE:
            widget.get_window().set_cursor(None)
            self._in_move = False
            return True
        return False

    def cb_bg_motion_notify(self, widget, event):
        if not self._in_move:
            return False
        hadj = self.scrolledwindow.get_hadjustment()
        vadj = self.scrolledwindow.get_vadjustment()
        hadj.set_value(
            min(
                max(hadj.get_value() - (event.x - self._last_x), hadj.get_lower()),
                hadj.get_upper() - hadj.get_page_size(),
            )
        )
        vadj.set_value(
            min(
                max(vadj.get_value() - (event.y - self._last_y), vadj.get_lower()),
                vadj.get_upper() - vadj.get_page_size(),
            )
        )
        return True

    # -- configuration -----------------------------------------------------

    def _get_configure_page_funcs(self):
        return [self.config_panel]

    def config_panel(self, configdialog):
        grid = Gtk.Grid()
        grid.set_border_width(12)
        grid.set_column_spacing(6)
        grid.set_row_spacing(6)
        configdialog.add_checkbox(
            grid,
            _("Show images"),
            0,
            "interface.contextview-show-images",
            stop=3,
        )
        configdialog.add_checkbox(
            grid,
            _("Show tag colour"),
            1,
            "interface.contextview-show-tags",
            stop=3,
        )
        configdialog.add_checkbox(
            grid,
            _("Show siblings"),
            2,
            "interface.contextview-show-siblings",
            stop=3,
        )
        configdialog.add_checkbox(
            grid,
            _("Show marriage data"),
            3,
            "interface.contextview-show-marriage",
            stop=3,
        )
        configdialog.add_combo(
            grid,
            _("Details in each box"),
            4,
            "interface.contextview-max-lines",
            (
                (1, _("Name only")),
                (3, _("Name and dates")),
                (5, _("Name, dates and places")),
            ),
            valueactive=True,
        )
        return _("Layout"), grid

    def config_update(self, client, cnxn_id, entry, data):
        self.show_images = self._config.get("interface.contextview-show-images")
        self.show_tags = self._config.get("interface.contextview-show-tags")
        self.show_siblings = self._config.get("interface.contextview-show-siblings")
        self.show_marriage = self._config.get("interface.contextview-show-marriage")
        self.maxlines = self._config.get("interface.contextview-max-lines")
        self.rebuild(self._shown_handle)

    def config_connect(self):
        for setting, _default in self.CONFIGSETTINGS:
            self._config.connect(setting, self.config_update)

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
      <section id="AddEditBook">
        <item>
          <attribute name="action">win.AddBook</attribute>
          <attribute name="label" translatable="yes">_Add Bookmark</attribute>
        </item>
        <item>
          <attribute name="action">win.EditBook</attribute>
          <attribute name="label" translatable="no">%s...</attribute>
        </item>
      </section>
"""
        % _("Organize Bookmarks"),
        """
    <placeholder id='CommonNavigation'>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-previous</property>
        <property name="action-name">win.Back</property>
        <property name="tooltip_text" translatable="yes">"""
        """Go to the previous object in the history</property>
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
        <property name="tooltip_text" translatable="yes">"""
        """Go to the next object in the history</property>
        <property name="label" translatable="yes">_Forward</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    <child groups='RO'>
      <object class="GtkToolButton">
        <property name="icon-name">go-home</property>
        <property name="action-name">win.HomePerson</property>
        <property name="tooltip_text" translatable="yes">"""
        """Go to the home person</property>
        <property name="label" translatable="yes">_Home</property>
        <property name="use-underline">True</property>
      </object>
      <packing>
        <property name="homogeneous">False</property>
      </packing>
    </child>
    </placeholder>
    """,
    ]
