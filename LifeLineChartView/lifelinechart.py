#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020 Christian Schulze
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

"""
See https://github.com/CWSchulze/life_line_chart
"""

# -------------------------------------------------------------------------
#
# Python modules
#
# -------------------------------------------------------------------------
import logging
import math
import colorsys
import pickle
from html import escape
import cairo
from gi.repository import Pango
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gi.repository import PangoCairo

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from copy import deepcopy
import sys, os
from collections import defaultdict

from life_line_chart import AncestorChart, DescendantChart
from life_line_chart import BaseIndividual, BaseFamily, InstanceContainer, estimate_birth_date, estimate_death_date, LifeLineChartNotEnoughInformationToDisplay
from gramps.gen.display.name import displayer as name_displayer
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.datehandler import displayer as date_displayer
from gramps.gen.lib import Person, ChildRefType, EventType, FamilyRelType
from gramps.gen.lib import Date
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.thumbnails import (get_thumbnail_path, SIZE_NORMAL,
                                         SIZE_LARGE)
import datetime
_max_days = {
    1:31,
    2:29,
    3:31,
    4:30,
    5:31,
    6:30,
    7:31,
    8:31,
    9:30,
    10:31,
    11:30,
    12:31
}
logger = logging.getLogger("LifeLineChart View")

events_key_name = {
    EventType.BIRTH: 'birth',
    EventType.CHRISTEN: 'christening',
    EventType.DEATH: 'death',
    EventType.BURIAL: 'burial',
    EventType.BAPTISM: 'baptism',
}
def get_date(event):
    """
    get date dict of a gramps event

    Args:
        event (gramps.gen.lib.Event): Event instance

    Returns:
        dict: event data dict
    """
    event_data = None
    try:
        date_obj = event.get_date_object()
        if date_obj.year == 0:
            return None
        quality = date_obj.get_quality()
        modifier = date_obj.get_modifier()
        comment = ''
        if quality == Date.QUAL_CALCULATED:
            comment = 'Calculated'
        elif quality == Date.QUAL_ESTIMATED:
            comment = 'Estimated'
        elif modifier == Date.MOD_BEFORE:
            comment = 'Before'
        elif modifier == Date.MOD_AFTER:
            comment = 'After'
        elif modifier == Date.MOD_ABOUT:
            comment = 'About'
        elif modifier == Date.MOD_RANGE:
            comment = 'Between'

        month_max_, day_max_ = 12, 31
        month_min_, day_min_ = 1, 1
        year_min, year_max = None, None
        month_max, day_max = None, None
        month_min, day_min = None, None

        precision = ''
        if date_obj.dateval[0] != 0:
            day_min = date_obj.dateval[0]
            precision += 'd'
        if date_obj.dateval[1] != 0:
            month_min = date_obj.dateval[1]
            precision += 'm'
        year_min = date_obj.year
        precision += 'y'
        year_max = year_min

        if not month_max: month_max = month_max_
        if not month_min: month_min = month_min_
        if not day_max: day_max = day_max_
        if not day_min: day_min = day_min_

        if modifier == Date.MOD_AFTER:
            year_max = year_min + 15
        elif modifier == Date.MOD_BEFORE:
            year_min = year_max - 15

        day_max = min(_max_days[month_max], day_max)

        date_min = datetime.datetime(year_min, month_min, day_min, 0, 0, 0, 0)
        try:
            date_max = datetime.datetime(year_max, month_max, day_max, 0, 0, 0, 0)
        except ValueError as e:
            if month_max==2:
                date_max = datetime.datetime(year_max, month_max, day_max, 0, 0, 0, 0)
            else:
                raise

        if events_key_name[event.get_type().value] in ['burial', 'death']:
            # if unknown move to the end of the year
            date = date_max
        else:
            # if unknown move to the beginning of the year
            date = date_min

        event_data = {
            'gramps_event': event,
            'date': date,
            'ordinal_value': date.toordinal(),
            'ordinal_value_max': date_max.toordinal(),
            'ordinal_value_min': date_min.toordinal(),
            'comment': comment,
            'precision': precision
        }
    except:
        pass
    return event_data


def get_relevant_events(gramps_person, dbstate, target):
    """
    collects the dates which are releavnt for life line charts.

    Args:
        gramps_person (gramps.gen.lib.Person): gramps person instance
        dbstate (dbstate): dbstate
        target (dict): place to store the events
    """
    for eventref in gramps_person.get_event_ref_list():
        #        for get_event_reference, key_name in events:
        #            eventref = get_event_reference()
        event = dbstate.db.get_event_from_handle(eventref.ref)
        if event and event.get_type().value in events_key_name:
            key_name = events_key_name[event.get_type().value]
            val = get_date(event)
            if val:
                target[key_name] = val

    if 'birth' in target:
        target['birth_or_christening'] = target['birth']
    elif 'birth_or_christening' not in target and 'christening' in target:
        target['birth_or_christening'] = target['christening']
    elif 'birth_or_christening' not in target and 'baptism' in target:
        target['birth_or_christening'] = target['baptism']
    else:
        target['birth_or_christening'] = None

    if 'death' in target:
        target['death_or_burial'] = target['death']
    elif 'death_or_burial' not in target and 'burial' in target:
        target['death_or_burial'] = target['burial']
    else:
        target['death_or_burial'] = None


class GrampsInstanceContainer(InstanceContainer):
    def __init__(self, family_constructor, individual_constructor, instantiate_all, dbstate):
        InstanceContainer.__init__(self, family_constructor, individual_constructor, instantiate_all)
        self.dbstate = dbstate

    def display_death_date(self, individual):
        """
        get the death (or burial) date

        Returns:
            str: death date
        """
        event = individual.events['death_or_burial']
        if event:
            date = event['date']
            if event['precision'] == 'dmy':
                gramps_date = Date(date.year, 0, 0)
            elif event['precision'] == 'my':
                gramps_date = Date(date.year, date.month, 0)
            else:
                gramps_date = Date(date.year, date.month, date.day)
            return date_displayer.display(gramps_date)
        else:
            return None

    def display_birth_date(self, individual):
        """
        get the birth (or christening or baptism) date str

        Returns:
            str: birth date str
        """

        event = individual.events['birth_or_christening']
        if event:
            date = event['date']
            if event['precision'] == 'dmy':
                gramps_date = Date(date.year, 0, 0)
            elif event['precision'] == 'my':
                gramps_date = Date(date.year, date.month, 0)
            else:
                gramps_date = Date(date.year, date.month, date.day)
            return date_displayer.display(gramps_date)
        return None

    def display_marriage_date(self, family):
        """
        get the marriage date str

        Returns:
            str: marriage date str
        """

        event = family.marriage
        date = event['date'].date()
        if event['precision'] == 'dmy':
            gramps_date = Date(date.year, 0, 0)
        elif event['precision'] == 'my':
            gramps_date = Date(date.year, date.month, 0)
        else:
            gramps_date = Date(date.year, date.month, date.day)
        return date_displayer.display(gramps_date)

    def display_marriage_location(self, family):
        """
        get the marriage location str

        Returns:
            str: marriage location str
        """
        if family.location:
            return place_displayer.display(self.dbstate.db, family.location)
        return None




class GrampsIndividual(BaseIndividual):
    """
    Interface class to provide person data to live line chart backend
    """
    def __init__(self, instances, dbstate, individual_id):
        BaseIndividual.__init__(self, instances, individual_id)
        self._dbstate = dbstate
        self._gramps_person = self._dbstate.db.get_person_from_handle(
            individual_id)
        self._initialize()
        if self.events['birth_or_christening'] is None or self.events['death_or_burial'] is None:
            raise LifeLineChartNotEnoughInformationToDisplay()

    def _initialize(self):
        BaseIndividual._initialize(self)
        self.child_of_family_id = self._gramps_person.get_parent_family_handle_list()
        get_relevant_events(self._gramps_person, self._dbstate, self.events)
        estimate_birth_date(self, self._instances)
        estimate_death_date(self)

    def get_name(self):
        """
        Get the name string of this person

        Returns:
            str: name
        """
        return [name_displayer.display_format(self._gramps_person, 101), name_displayer.display_format(self._gramps_person, 100)]

    def _get_marriage_family_ids(self):
        """
        get the uids of the marriage families

        Returns:
            list: list of marriage family uids
        """
        return self._gramps_person.get_family_handle_list()


def estimate_marriage_date(family):
    """
    Estimate the marriage date if it is not available

    Args:
        family (GrampsFamily): family instance
    """
    if not family.marriage:
        children_events = []
        for child in family.children_individual_ids:
            child_events = {}
            gramps_person = family._dbstate.db.get_person_from_handle(child)
            get_relevant_events(gramps_person, family._dbstate, child_events)
            if child_events['birth_or_christening']:
                children_events.append(child_events['birth_or_christening'])

        #unsorted_marriages = [family._instances[('f',m)] for m in family._marriage_family_ids]
        if len(children_events) > 0:
            sorted_pairs = list(zip([(m['ordinal_value'], i) for i, m in enumerate(
                children_events)], children_events))
            sorted_pairs.sort()
            family.marriage = sorted_pairs[0][1]


class GrampsFamily(BaseFamily):
    """
    Interface class to provide family data to live line chart backend
    """
    def __init__(self, instances, dbstate, family_id):
        BaseFamily.__init__(self, instances, family_id)
        self._dbstate = dbstate
        self._gramps_family = self._dbstate.db.get_family_from_handle(
            family_id)
        self._initialize()

    def _initialize(self):
        BaseFamily._initialize(self)
        #self.marriage = {}

        reflist = self._gramps_family.get_event_ref_list()
        if reflist:
            elist = [self._dbstate.db.get_event_from_handle(ref.ref)
                     for ref in reflist]
            events = [evnt for evnt in elist
                      if evnt.type == EventType.MARRIAGE]
            if events:
                #    return displayer.display(date_obj)
                self.marriage = get_date(events[0])
                if self.marriage and events[0].place:
                    p = self._dbstate.db.get_place_from_handle(events[0].place)
                    self.location = p
        estimate_marriage_date(self)
        if self.marriage is None:
            raise LifeLineChartNotEnoughInformationToDisplay()

    def _get_husband_and_wife_id(self):
        """
        get the uids of husband and wife

        Returns:
            tuple: husband uid, wife uid
        """
        father_handle = Family.get_father_handle(self._gramps_family)
        mother_handle = Family.get_mother_handle(self._gramps_family)
        return father_handle, mother_handle

    def _get_children_ids(self):
        """
        get the uids of the children

        Returns:
            list: list of children uids
        """
        return [ref.ref for ref in self._gramps_family.get_child_ref_list()]

    @property
    def husb_name(self):
        """
        get the name of the husband

        Returns:
            str: husband name
        """
        father_handle = Family.get_father_handle(self._gramps_family)
        return self.husb.plain_name

    @property
    def wife_name(self):
        """
        get the name of the wife

        Returns:
            str: wife name
        """
        mother_handle = Family.get_mother_handle(self._gramps_family)
        return self.wife.plain_name




def get_dbdstate_instance_container(dbstate):
    """
    constructor for instance container

    Args:
        dbstate (gramps.gen.db): database of gramps

    Returns:
        life_line_chart.InstanceContainer: instance container
    """

    logger.debug('start creating instances')
    ic = GrampsInstanceContainer(
        lambda self, key: GrampsFamily(self, dbstate, key[1]),
        lambda self, key: GrampsIndividual(self, dbstate, key[1]),
        None,
        dbstate)  # lambda self : instantiate_all(self, database_fam, database_indi))

    ic.date_label_translation = {
        'Calculated': '{symbol}\xa0' + _('calculated').replace(' ', '\xa0') + '\xa0{date}',
        'Estimated': '{symbol}\xa0' + _('estimated').replace(' ', '\xa0') + '\xa0{date}',
        'Estimated (min age at marriage)': '{symbol}\xa0' + _('estimated').replace(' ', '\xa0') + '\xa0{date}',
        'Estimated (max age)': '{symbol}\xa0' + _('estimated').replace(' ', '\xa0') + '\xa0{date}',
        'Estimated (after parents marriage)': '{symbol}\xa0' + _('estimated').replace(' ', '\xa0') + '\xa0{date}',
        'Still alive': '',
        'About': '{symbol}\xa0' + _('about').replace(' ', '\xa0') + '\xa0{date}',
        'Before': '{symbol}\xa0' + _('before').replace(' ', '\xa0') + '\xa0{date}',
        'After': '{symbol}\xa0' + _('after').replace(' ', '\xa0') + '\xa0{date}',
        'YearPrecision': '{symbol}\xa0{date}',
        'Between': '{symbol}\xa0{date}'
    }

    return ic



from gramps.gen.db import DbTxn
from gramps.gen.errors import WindowActiveError
from gramps.gen.lib import ChildRef, Family, Name, Person, Surname
from gramps.gen.lib.date import Today
from gramps.gen.utils.alive import probably_alive
from gramps.gen.utils.libformatting import FormattingHelper
from gramps.gen.utils.db import (find_children, find_parents, get_timeperiod,
                                 find_witnessed_people, get_age, preset_name)
from gramps.gen.constfunc import is_quartz
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.const import (
    PAD_PX,
    PAD_TEXT,
    BACKGROUND_SCHEME1,
    BACKGROUND_SCHEME2,
    BACKGROUND_GENDER,
    BACKGROUND_WHITE,
    BACKGROUND_GRAD_GEN,
    BACKGROUND_GRAD_AGE,
    BACKGROUND_SINGLE_COLOR,
    BACKGROUND_GRAD_PERIOD,
    GENCOLOR,
    MAX_AGE,
    GRADIENTSCALE,
    NORMAL,
    EXPANDED)
from gramps.gui.widgets.reorderfam import Reorder
from gramps.gui.utils import color_graph_box, hex_to_rgb, is_right_click
from gramps.gui.ddtargets import DdTargets
from gramps.gui.editors import EditPerson, EditFamily
from gramps.gui.utilscairo import warpPath
from gramps.gen.utils.symbols import Symbols

_ = glocale.translation.gettext

# following are used in name_displayer format def
# (must not conflict with standard defs)
TWO_LINE_FORMAT_1 = 100
TWO_LINE_FORMAT_2 = 101


class LifeLineChartAxis(Gtk.DrawingArea):
    def __init__(self, dbstate, uistate, life_line_chart_widget):
        Gtk.DrawingArea.__init__(self)
        self.dbstate = dbstate
        self.uistate = uistate
        self.life_line_chart_widget = life_line_chart_widget
        self.connect("draw", self.on_draw)
        self.set_size_request(100,100)

    def do_size_request(self, requisition):
        """
        Overridden method to handle size request events.
        """
        requisition.width = 100
        requisition.height = 100

    def do_get_preferred_width(self):
        """ GTK3 uses width for height sizing model. This method will
            override the virtual method
        """
        req = Gtk.Requisition()
        self.do_size_request(req)
        return req.width, req.width

    def do_get_preferred_height(self):
        """ GTK3 uses width for height sizing model. This method will
            override the virtual method
        """
        req = Gtk.Requisition()
        self.do_size_request(req)
        return req.height, req.height

    def on_draw(self, widget, ctx, scale=1.):
        """
        callback to draw the lifelinechart
        """
        run_profiler = False
        if run_profiler:
            import cProfile
            cProfile.runctx('widget.draw(ctx)', globals(), locals())
        else:
            widget.draw(ctx)

    def draw(self, ctx=None, scale=1.):
        translated_position = self.life_line_chart_widget._position_move(
            self.life_line_chart_widget.upper_left_view_position,
            self.life_line_chart_widget.center_delta_xy)
        translated_position = self.life_line_chart_widget.view_position_get_limited(translated_position)
        translated_position = (self.life_line_chart_widget.life_line_chart_instance.get_full_width()*self.life_line_chart_widget.zoom_level
                - 0.9*self.get_allocated_width()), translated_position[1]
        ctx.translate(
            -translated_position[0],
            -translated_position[1])
        ctx.scale(self.life_line_chart_widget.zoom_level, self.life_line_chart_widget.zoom_level)

        visible_range = (self.get_allocated_width(), self.get_allocated_height())
        arbitrary_clip_offset = max(visible_range)*0.5 # remove text items if their start position is 50%*view_width outside
        view_x_min = (translated_position[0] - arbitrary_clip_offset) / self.life_line_chart_widget.zoom_level
        view_x_max = (translated_position[0] + arbitrary_clip_offset + visible_range[0]) / self.life_line_chart_widget.zoom_level
        view_y_min = (translated_position[1] - arbitrary_clip_offset) / self.life_line_chart_widget.zoom_level
        view_y_max = (translated_position[1] + arbitrary_clip_offset + visible_range[1]) / self.life_line_chart_widget.zoom_level
        items = []
        if 'grid' in self.life_line_chart_widget.life_line_chart_instance.additional_graphical_items:
            items += self.life_line_chart_widget.life_line_chart_instance.additional_graphical_items['grid']
        if 'axis' in self.life_line_chart_widget.life_line_chart_instance.additional_graphical_items:
            items += self.life_line_chart_widget.life_line_chart_instance.additional_graphical_items['axis']
        self.life_line_chart_widget.draw_items(
            ctx,
            items,
            (view_x_min, view_y_min, view_x_max, view_y_max),
            (12,30))
        pass
#-------------------------------------------------------------------------
#
# LifeLineChartBaseWidget
#
#-------------------------------------------------------------------------


class LifeLineChartBaseWidget(Gtk.DrawingArea):
    """ a base widget for lifelinecharts"""
    CENTER = 60                # pixel radius of center, changes per lifelinechart

    def __init__(self, dbstate, uistate, callback_popup=None):
        Gtk.DrawingArea.__init__(self)
        self.dbstate = dbstate
        self.uistate = uistate
        self.childrenroot = []
        self.angle = {}
        self.filter = None
        self.translating = False
        self.dupcolor = None
        self.surface = None
        self.goto = None
        self._tooltip_individual_cache = None
        self.on_popup = callback_popup
        self.last_x, self.last_y = None, None
        self.fontsize = 8
        # add parts of a two line name format to the displayer.  We add them
        # as standard names, but set them inactive so they don't show up in
        # name editor or selector.
        name_displayer.set_name_format(
            [(TWO_LINE_FORMAT_1, 'lifelinechart_name_line1', '%l', False),
             (TWO_LINE_FORMAT_2, 'lifelinechart_name_line2', '%f %s', False)])
        self.connect("button_release_event", self.on_mouse_up)
        self.connect("motion_notify_event", self.on_mouse_move)
        self.connect("leave_notify_event", self.on_mouse_leave)
        self.connect("button-press-event", self.on_mouse_down)
        self.connect("scroll_event", self.scroll_mouse)
        #we want to grab key events also
        self.set_can_focus(True)
        self.connect("key-press-event", self.on_key_press)
        self.connect("key-release-event", self.on_key_release)

        self.connect("draw", self.on_draw)
        self.add_events(Gdk.EventMask.SMOOTH_SCROLL_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.LEAVE_NOTIFY_MASK |
                        Gdk.EventMask.KEY_PRESS_MASK |
                        Gdk.EventMask.KEY_RELEASE_MASK)

        # Enable drag
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, [],
                             Gdk.DragAction.COPY)
        tglist = Gtk.TargetList.new([])
        tglist.add(DdTargets.PERSON_LINK.atom_drag_type,
                   DdTargets.PERSON_LINK.target_flags,
                   DdTargets.PERSON_LINK.app_id)
        #allow drag to a text document, info on drag_get will be 0L !
        tglist.add_text_targets(0)
        self.drag_source_set_target_list(tglist)
        self.connect("drag_data_get", self.on_drag_data_get)
        self.connect("drag_begin", self.on_drag_begin)
        self.connect("drag_end", self.on_drag_end)
        # Enable drop
        self.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP,
                           [DdTargets.PERSON_LINK.target()],
                           Gdk.DragAction.COPY)
        self.connect('drag_data_received', self.on_drag_data_received)
        self.uistate.connect('font-changed', self.reload_symbols)

        self._mouse_click = False
        self.rotate_value = 90  # degrees, initially, 1st gen male on right half
        self.center_delta_xy = [0, 0]  # translation of the center of the
        # lifeline wrt canonical center
        self.upper_left_view_position = [0, 0]  # coord of the center of the lifeline
        self.mouse_x = 0
        self.mouse_y = 0
        #(re)compute everything
        self.reset()
        self.set_size_request(120, 120)
        self.maxperiod = 0
        self.minperiod = 0
        self.cstart_hsv = None
        self.cend_hsv = None
        self.colors = None
        self.maincolor = None
        self.gradval = None
        self.gradcol = None
        self.in_drag = False
        self._mouse_click_cell_address = None
        self.symbols = Symbols()
        self.reload_symbols()
        self.axis_widget = None

    def set_axis_widget(self, widget):
        self.axis_widget = widget

    def reload_symbols(self):
        dth_idx = self.uistate.death_symbol
        if self.uistate.symbols:
            self.bth = self.symbols.get_symbol_for_string(
                self.symbols.SYMBOL_BIRTH)
            self.dth = self.symbols.get_death_symbol_for_char(dth_idx)
        else:
            self.bth = self.symbols.get_symbol_fallback(
                self.symbols.SYMBOL_BIRTH)
            self.dth = self.symbols.get_death_symbol_fallback(dth_idx)

    def reset(self):
        """
        Reset the lifeline chart. This should trigger computation of all data
        structures needed
        """

        # fill the data structure
        #self._fill_data_structures()

        # prepare the colors for the boxes

    def _fill_data_structures(self):
        """
        fill in the data structures that will be needed to draw the chart
        """
        raise NotImplementedError

    def do_size_request(self, requisition):
        """
        Overridden method to handle size request events.
        """
        requisition.width = 800
        requisition.height = 600

    def do_get_preferred_width(self):
        """ GTK3 uses width for height sizing model. This method will
            override the virtual method
        """
        req = Gtk.Requisition()
        self.do_size_request(req)
        return req.width, req.width

    def do_get_preferred_height(self):
        """ GTK3 uses width for height sizing model. This method will
            override the virtual method
        """
        req = Gtk.Requisition()
        self.do_size_request(req)
        return req.height, req.height


    def zoom_in(self, _button=None, fix_point = None):
        """
        Increase zoom scale.
        """
        scale_coef = self.zoom_level * 1.25
        self.set_zoom(scale_coef, fix_point)

    def zoom_out(self, _button=None, fix_point = None):
        """
        Decrease zoom scale.
        """
        scale_coef = self.zoom_level / 1.25
        if scale_coef < 0.01:
            scale_coef = 0.01
        self.set_zoom(scale_coef, fix_point)

    def set_original_zoom(self, _button):
        """
        Set original zoom scale = 1.
        """
        self.set_zoom(1)

    def set_zoom(self, value, fix_point = None):
        zoom_level_backup = self.zoom_level
        self.zoom_level = max(0.01, min(1000, value))
        visible_range = (self.get_allocated_width(), self.get_allocated_height())
        if fix_point is None:
            fix_point = visible_range[0] * 0.5, visible_range[1] * 0.5
        self.upper_left_view_position = (
            (self.zoom_level / zoom_level_backup) * (
            fix_point[0] + self.upper_left_view_position[0]) - fix_point[0],
            (self.zoom_level / zoom_level_backup) * (
            fix_point[1] + self.upper_left_view_position[1]) - fix_point[1]
        )
        self.view_position_limit_to_bounds()
        self.queue_draw_wrapper()

    def fit_to_page(self, _button=None):
        width = self.life_line_chart_instance.get_full_width()
        height = self.life_line_chart_instance.get_full_height()
        width_a = self.get_allocated_width()
        height_a = self.get_allocated_height()
        scale_w = width_a / width
        scale_h = height_a / height
        new_zoom_level = min(scale_w, scale_h)
        self.upper_left_view_position = (width*new_zoom_level - width_a) / 2.0, (height*new_zoom_level - height_a) / 2.0
        self.set_zoom(new_zoom_level)

    def _position_move(self, position, delta):
        """
        Move position by delta.

        Args:
            position (tuple): x, y tuple
            delta (tuple): x, y tuple

        Returns:
            tuple: new position as x, y tuple
        """
        return position[0] + delta[0], position[1] + delta[1]

    def view_position_limit_to_bounds(self):
        """
        limit the view to the outer bounds
        """
        self.upper_left_view_position = self.view_position_get_limited(self.upper_left_view_position)

    def view_position_get_limited(self, position):
        """
        Calculate the limited view position.

        Args:
            position (tuple): original position

        Returns:
            tuple: limited position
        """
        width = self.life_line_chart_instance.get_full_width()
        height = self.life_line_chart_instance.get_full_height()
        width_a = self.get_allocated_width()
        height_a = self.get_allocated_height()
        allowed_x_min = min(0, (width*self.zoom_level - width_a) / 2.0)
        allowed_y_min = min(0, (height*self.zoom_level - height_a) / 2.0)
        allowed_x_max = max(width*self.zoom_level - width_a, allowed_x_min)
        allowed_y_max = max(height*self.zoom_level - height_a, allowed_y_min)
        return (
           max(allowed_x_min, min(allowed_x_max, position[0])),
           max(allowed_y_min, min(allowed_y_max, position[1])),
        )

    def get_view_position_center(self):
        visible_range = (self.get_allocated_width(), self.get_allocated_height())
        return tuple([cp + vr/2 for cp, vr in zip(self.upper_left_view_position, visible_range)])

    def set_view_position_center(self, new_center):
        visible_range = (self.get_allocated_width(), self.get_allocated_height())
        return tuple([cp + vr/2 for cp, vr in zip(self.upper_left_view_position, visible_range)])

    def on_draw(self, widget, ctx, scale=1.):
        """
        callback to draw the lifelinechart
        """
        dummy_scale = scale
        dummy_widget = widget
        # if self.surface:
        #     ctx.set_source_surface(self.surface, 0, 0)

        run_profiler = False
        if run_profiler:
            import cProfile
            cProfile.runctx('widget.draw(ctx)', globals(), locals())
        else:
            widget.draw(ctx)
        #print('blub')

        #self.da.paint()
        #ctx.set_source_surface(self.da, 0, 0)
        #widget.draw(ctx)
        #ctx.paint()

    def prt_draw(self, widget, ctx, scale=1.0):
        """
        method to allow direct drawing to cairo context for printing
        """
        dummy_widget = widget
        self.draw(ctx=ctx, scale=scale)

    def on_key_press(self, widget, eventkey):
        """grab key press
        """
        dummy_widget = widget
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if eventkey.state & accel_mask == Gdk.ModifierType.CONTROL_MASK:
            if Gdk.keyval_name(eventkey.keyval) == 'plus':
                self.zoom_in()
                return True
            if Gdk.keyval_name(eventkey.keyval) == 'minus':
                self.zoom_out()
                return True
        if Gdk.keyval_name(eventkey.keyval) in ['Control_L', 'Control_R']:
            try:
                cursor = Gdk.Cursor.new_from_name(widget.get_display(), 'grab')
            except:
                cursor = Gdk.Cursor(Gdk.CursorType.HAND1)
            self.get_window().set_cursor(cursor)

        #if self.mouse_x and self.mouse_y:
            # cell_address = self.cell_address_under_cursor(self.mouse_x,
            # #                                               self.mouse_y)
            # if cell_address is None:
            #     return False
            # person, family = (self.person_at(cell_address),
            #                   self.family_at(cell_address))
            # if person and (Gdk.keyval_name(eventkey.keyval) == 'e'):
            #     # we edit the person
            #     self.edit_person_cb(None, person.handle)
            #     return True
            # elif family and (Gdk.keyval_name(eventkey.keyval) == 'f'):
            #     # we edit the family
            #     self.edit_fam_cb(None, family.handle)
            #     return True

        return False

    def on_key_release(self, widget, eventkey):
        """grab key release
        """
        if Gdk.keyval_name(eventkey.keyval) in ['Control_L', 'Control_R']:
            cursor = Gdk.Cursor(Gdk.CursorType.ARROW)
            self.get_window().set_cursor(cursor)

    def on_mouse_down(self, widget, event):
        """
        What to do if we release a mouse button
        """
        dummy_widget = widget
        self.translating = False  # keep track of up/down/left/right movement

        if event.button == 1:
            #we grab the focus to enable to see key_press events
            self.grab_focus()



        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.CONTROL_MASK:
            # left mouse on center dot, we translate on left click
            if event.button == 1:  # left mouse
                # save the mouse location for movements
                try:
                    cursor = Gdk.Cursor.new_from_name(widget.get_display(), 'grabbing')
                except:
                    cursor = Gdk.Cursor(Gdk.CursorType.HAND1)
                self.get_window().set_cursor(cursor)
                self.translating = True
                self.last_x, self.last_y = event.x, event.y
                return True
        # else:
        #     # line was clicked!
        #     individual = self.life_line_chart_instance.get_individual_from_position(
        #         event.x/self.zoom_level, event.y/self.zoom_level)
        #     if individual:
        #         individual_id = individual.individual_id

        #         #return True

        #     # #left click on person, prepare for expand/collapse or drag
        #         if event.button == 1:
        #             self._mouse_click = True
        #             self._mouse_click_individual_id = individual_id
        #             return False

        #right click on person, context menu
        # Do things based on state, event.get_state(), or button, event.button
        if is_right_click(event):
            gr_individual, gr_family = self.life_line_chart_instance.get_individual_from_position(
                (event.x + self.upper_left_view_position[0])/self.zoom_level,
                (event.y + self.upper_left_view_position[1])/self.zoom_level)
            if gr_individual and self.on_popup:
                self.on_popup(widget, event, gr_individual, gr_family)
                return True

        return True

    def scroll_mouse(self, widget, event):
        """
        Zoom by mouse wheel.
        """
        # Handles zoom in / zoom out on Ctrl+mouse wheel
        accel_mask = Gtk.accelerator_get_default_mod_mask()
        if event.state & accel_mask == Gdk.ModifierType.CONTROL_MASK:
            if event.direction == Gdk.ScrollDirection.SMOOTH:
                hasdeltas, dx, dy = event.get_scroll_deltas()
                self.set_zoom(self.zoom_level / (1 + max(-0.9, min(10, 0.25 * dy))), fix_point=(event.x, event.y))
            elif event.direction == Gdk.ScrollDirection.UP:
                self.zoom_in(fix_point=(event.x, event.y))
            elif event.direction == Gdk.ScrollDirection.DOWN:
                self.zoom_out(fix_point=(event.x, event.y))
        else:
            if event.direction == Gdk.ScrollDirection.SMOOTH:
                hasdeltas, dx, dy = event.get_scroll_deltas()
                if hasdeltas:
                    self.upper_left_view_position = (
                        self.upper_left_view_position[0] + 50 * dx,
                        self.upper_left_view_position[1] + 50 * dy)
                    self.view_position_limit_to_bounds()
                    self.queue_draw_wrapper()
            elif event.state & accel_mask == Gdk.ModifierType.SHIFT_MASK:
                if event.direction == Gdk.ScrollDirection.UP:
                    self.upper_left_view_position = (self.upper_left_view_position[0] - 50, self.upper_left_view_position[1])
                elif event.direction == Gdk.ScrollDirection.DOWN:
                    self.upper_left_view_position = (self.upper_left_view_position[0] + 50, self.upper_left_view_position[1])
                self.view_position_limit_to_bounds()
                self.queue_draw_wrapper()
            else:
                print(str(event.get_scroll_deltas()))
                if event.direction == Gdk.ScrollDirection.UP:
                    self.upper_left_view_position = (self.upper_left_view_position[0], self.upper_left_view_position[1] - 50)
                elif event.direction == Gdk.ScrollDirection.DOWN:
                    self.upper_left_view_position = (self.upper_left_view_position[0], self.upper_left_view_position[1] + 50)
                self.view_position_limit_to_bounds()
                self.queue_draw_wrapper()

        # stop the signal of scroll emission
        # to prevent window scrolling
        return True

    def on_mouse_leave(self, widget, event):
        self._tooltip_individual_cache = None
        self.info_label.set_text('')
        self.pos_label.set_text('')
        self.queue_draw_wrapper()

    def on_mouse_move(self, widget, event):
        """
        What to do if we move the mouse
        """
        dummy_widget = widget
        self._mouse_click = False
        if self.last_x is None or self.last_y is None:
            # while mouse is moving, we must update the tooltip based on person
            gr_individual, gr_family = self.life_line_chart_instance.get_individual_from_position(
                (event.x + self.upper_left_view_position[0])/self.zoom_level,
                (event.y + self.upper_left_view_position[1])/self.zoom_level)
            ov = self.life_line_chart_instance._inverse_y_position((event.y + self.upper_left_view_position[1])/self.zoom_level)
            try:
                date = datetime.date.fromordinal(int(ov))
            except:
                date = datetime.date.fromordinal(1)
            self.mouse_x, self.mouse_y = event.x, event.y
            tooltip = ""
            if gr_individual:
                if (self._tooltip_individual_cache is None or \
                    self._tooltip_individual_cache != gr_individual, gr_family):
                    if self._tooltip_individual_cache != (gr_individual, gr_family):
                        self._tooltip_individual_cache = gr_individual, gr_family
                        self.queue_draw_wrapper()
                    tooltip = gr_individual.individual.short_info_text
                    tooltip += '\nGramps id: ' + gr_individual.individual._gramps_person.get_gramps_id()
                    self.info_label.set_text(tooltip.replace('\n','   //   '))
                self.info_label.set_sensitive(True)
            else:
                if self._tooltip_individual_cache is not None:
                    self._tooltip_individual_cache = None
                    self.queue_draw_wrapper()
                self.info_label.set_sensitive(False)
                #self.info_label.set_text(tooltip.replace('\n','   //   '))
            self.pos_label.set_text('cursor position at ' + str(date))
            #self.set_tooltip_text(tooltip)
            return False

        #translate or rotate should happen
        if self.translating:
            self.center_delta_xy = (self.last_x - event.x,
                                    self.last_y - event.y)
        # else:
        #     # get the angles of the two points from the center:
        #     start_angle = math.atan2(event.y - self.upper_left_view_position[1],
        #                              event.x - self.upper_left_view_position[0])
        #     end_angle = math.atan2(self.last_y - self.upper_left_view_position[1],
        #                            self.last_x - self.upper_left_view_position[0])
        #     # now look at change in angle:
        #     diff_angle = (end_angle - start_angle) % (math.pi * 2.0)
        #     self.rotate_value -= math.degrees(diff_angle)
        #     self.last_x, self.last_y = event.x, event.y
        #self.draw()
        self.queue_draw_wrapper()
        return True

    def do_mouse_click(self):
        """
        action to take on left mouse click
        """
        pass

    def on_mouse_up(self, widget, event):
        """
        What to do if we move the mouse
        """
        dummy_widget = widget
        dummy_event = event
        if self._mouse_click:
            self.do_mouse_click()
            return True
        if self.last_x is None or self.last_y is None:
            # No translate or rotate
            return True
        if self.translating:
            try:
                cursor = Gdk.Cursor.new_from_name(widget.get_display(), 'grab')
            except:
                cursor = Gdk.Cursor(Gdk.CursorType.HAND1)
            self.get_window().set_cursor(cursor)
            self.translating = False
            self.upper_left_view_position = \
                self.upper_left_view_position[0] + self.center_delta_xy[0], \
                self.upper_left_view_position[1] + self.center_delta_xy[1]
            self.view_position_limit_to_bounds()
            self.center_delta_xy = 0, 0
        else:
            self.center_delta_xy = 0, 0

        self.last_x, self.last_y = None, None
        #self.draw()
        self.queue_draw_wrapper()
        return True

    def on_drag_begin(self, widget, data):
        """Set up some inital conditions for drag. Set up icon."""
        dummy_widget = widget
        dummy_data = data
        self.in_drag = True
        self.drag_source_set_icon_name('gramps-person')

    def on_drag_end(self, widget, data):
        """Set up some inital conditions for drag. Set up icon."""
        dummy_widget = widget
        dummy_data = data
        self.in_drag = False

    def on_drag_data_get(self, widget, context, sel_data, info, time):
        """
        Returned parameters after drag.
        Specified for 'person-link', for others return text info about person.
        """
        if not self._mouse_click_individual_id:
            return
        dummy_widget = widget
        dummy_time = time
        tgs = [x.name() for x in context.list_targets()]
        person = self.life_line_chart_instance._instances[(
            'i', self._mouse_click_individual_id)]._gramps_person
        if person:
            if info == DdTargets.PERSON_LINK.app_id:
                data = (DdTargets.PERSON_LINK.drag_type,
                        id(self), person.get_handle(), 0)
                sel_data.set(sel_data.get_target(), 8, pickle.dumps(data))
            elif ('TEXT' in tgs or 'text/plain' in tgs) and info == 0:
                sel_data.set_text(self.format_helper.format_person(person,
                                                                   11), -1)

    def on_drag_data_received(self, widget, context, pos_x, pos_y,
                              sel_data, info, time):
        """
        Handle the standard gtk interface for drag_data_received.

        If the selection data is defined, extract the value from sel_data.data
        """
        dummy_context = context
        dummy_widget = widget
        dummy_info = info
        dummy_time = time
        # radius, dummy_rads = self.cursor_to_polar(pos_x, pos_y)

        # if radius < self.CENTER:
        #     if sel_data and sel_data.get_data():
        #         (dummy_drag_type, dummy_idval, handle,
        #          dummy_val) = pickle.loads(sel_data.get_data())
        #         self.goto(self, handle)

    def edit_person_cb(self, obj, person_handle):
        """
        Edit a person
        """
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
            return True
        return False

    def edit_fam_cb(self, obj, family_handle):
        """
        Edit a family
        """
        fam = self.dbstate.db.get_family_from_handle(family_handle)
        if fam:
            try:
                EditFamily(self.dbstate, self.uistate, [], fam)
            except WindowActiveError:
                pass
            return True
        return False

    def queue_draw_wrapper(self):
        self.queue_draw()
        if self.axis_widget:
            self.axis_widget.queue_draw()

#-------------------------------------------------------------------------
#
# LifeLineChartWidget
#
#-------------------------------------------------------------------------


class LifeLineChartWidget(LifeLineChartBaseWidget):
    """
    Interactive Life Line Chart Widget.
    """

    def __init__(self, dbstate, uistate, callback_popup=None, chart_class=None):
        """
        Life Line Chart Widget. Handles visualization of data in self.data.
        See main() of LifeLineChartGramplet for example of model format.
        """
        self.chart_class = chart_class
        self.rootpersonh = None
        self.rebuild_next_time = True
        self.formatting = None
        self.positioning = None
        self.chart_configuration = None
        self.filter = None
        self.chart_items = []
        self.image_cache = {}
        self.zoom_level = 1.0
        self.zoom_level_backup = 1.0
        self.life_line_chart_instance = None
        self.angle = {}
        self.childrenroot = []
        self.rootangle_rad = []
        self.menu = None
        self.data = {}
        self.dbstate = dbstate
        self.set_values(None, None)
        LifeLineChartBaseWidget.__init__(
            self, dbstate, uistate, callback_popup)
        #self.ic = get_dbdstate_instance_container(self.dbstate)

    def set_values(self, root_person_handle, filtr):
        """
        Reset the values to be used:

        """

        reset = False
        new_root_individual = False
        if self.rootpersonh != root_person_handle:  # or self.filter != filtr:
            reset = True
            new_root_individual = True
        reset = reset or self.rebuild_next_time
        new_filter = self.filter != filtr
        self.filter = filtr
        root_person = None
        if root_person_handle is not None and root_person_handle != '':
            try:
                root_person = self.dbstate.db.get_person_from_handle(root_person_handle)
            except:
                pass
        if root_person is None:
            # self.life_line_chart_instance = AncestorChart(
            #                 instance_container=get_dbdstate_instance_container(self.dbstate))
            self.life_line_chart_instance = self.chart_class(
                            instance_container=get_dbdstate_instance_container(self.dbstate))
            # self.life_line_chart_instance.select_individuals(
            #     None)
            # cof_family_id = None
            # self.life_line_chart_instance.place_selected_individuals(None, None, None, None)
            # self.life_line_chart_instance._formatting = deepcopy(
            #     self.formatting)
            self.rebuild_next_time = False

            self.life_line_chart_instance.define_svg_items()
        else:
            def plot(reset):
                # x = GrampsIndividual(self.ic, self.dbstate, self.rootpersonh)
                if self.life_line_chart_instance is None:
                    # self.life_line_chart_instance = AncestorChart(
                    #     instance_container=get_dbdstate_instance_container(self.dbstate))
                    self.life_line_chart_instance = self.chart_class(
                        instance_container=get_dbdstate_instance_container(self.dbstate))

                self.text_color = self.uistate.window.get_style_context().get_color(Gtk.StateFlags.NORMAL)
                if self.text_color.red > 0.5:
                    # dark theme
                    self.life_line_chart_instance._colors = self.life_line_chart_instance.COLOR_CONFIGURATIONS['dark']
                else:
                    self.life_line_chart_instance._colors = self.life_line_chart_instance.COLOR_CONFIGURATIONS['light']

                def filter_lambda(individual):
                    return False

                def color_lambda(gr_individual):
                    if self.filter:
                        person = gr_individual.individual._gramps_person
                        if not self.filter.match(person.handle, self.dbstate.db):
                            return (220, 220, 220)
                    return None

                def images_lambda(individual):
                    images = {}
                    for i, reference in enumerate(individual._gramps_person.media_list):
                        handle = reference.get_reference_handle()
                        media = self.dbstate.db.get_media_from_handle(handle)
                        path = media_path_full(self.dbstate.db, media.get_path())
                        if media.mime in ['image/jpeg', 'image/png'] and os.path.isfile(path):
                            year = media.date.get_year()
                            if year != 0:
                                date_ov = datetime.date(*[i if i != 0 else 1 for i in media.date.get_ymd()]).toordinal()
                                date_ov = max(date_ov, individual.events['birth_or_christening']['date'].date().toordinal() + 1)
                            else:
                                continue
                            image_path = get_thumbnail_path(path, media.mime, size=SIZE_NORMAL)
                            thumbnail = GdkPixbuf.Pixbuf.new_from_file(image_path)
                            images[date_ov] = {
                                'filename': image_path,
                                'size': (thumbnail.get_width(), thumbnail.get_height())
                                }
                    if not images:
                        for i, reference in enumerate(individual._gramps_person.media_list):
                            handle = reference.get_reference_handle()
                            media = self.dbstate.db.get_media_from_handle(handle)
                            path = media_path_full(self.dbstate.db, media.get_path())
                            if media.mime in ['image/jpeg', 'image/png'] and os.path.isfile(path):
                                year = media.date.get_year()
                                date_ov = individual.events['birth_or_christening']['date'].date().toordinal() + int((i+1)*365*5) + 1
                                image_path = get_thumbnail_path(path, media.mime, size=SIZE_NORMAL)
                                thumbnail = GdkPixbuf.Pixbuf.new_from_file(image_path)
                                images[date_ov] = {
                                    'filename': image_path,
                                    'size': (thumbnail.get_width(), thumbnail.get_height())
                                    }
                    return images

                unavailable_items = []
                for handle in self.chart_configuration['discovery_blacklist']:
                    try:
                        individual = self.life_line_chart_instance._instances[(
                            'i', handle)]
                    except:
                        unavailable_items.append(handle)
                for handle in unavailable_items:
                    self.chart_configuration['discovery_blacklist'].remove(handle)

                unavailable_items = []
                if 'family_children' in self.chart_configuration:
                    for handle in self.chart_configuration['family_children']:
                        try:
                            family = self.life_line_chart_instance._instances[(
                                'f', handle)]
                        except:
                            unavailable_items.append(handle)
                    for handle in unavailable_items:
                        self.chart_configuration['family_children'].remove(handle)

                self.chart_configuration['root_individuals'][0]['individual_id'] = root_person_handle
                self.life_line_chart_instance.set_formatting(self.formatting)
                self.life_line_chart_instance.set_positioning(self.positioning)
                self.life_line_chart_instance.set_chart_configuration(self.chart_configuration)

                reset = self.life_line_chart_instance.update_chart(filter_lambda=filter_lambda,
                                                                   color_lambda=color_lambda,
                                                                   images_lambda=images_lambda,
                                                                   rebuild_all=reset,
                                                                   update_view=new_filter)
                return reset

            run_profiler = False
            if run_profiler:
                import cProfile
                cProfile.runctx('plot(reset)', globals(), locals(), sort=1)
            else:
                reset = plot(reset)
            self.rebuild_next_time = False
            self.view_restore_btn.set_sensitive(
                'ancestor_placement' in self.chart_configuration and bool(self.chart_configuration['ancestor_placement']) or
                'family_children' in self.chart_configuration and bool(self.chart_configuration['family_children']) or
                'discovery_blacklist' in self.chart_configuration and bool(self.chart_configuration['discovery_blacklist'])
                )
        self.rootpersonh = root_person_handle
        additional_items = []
        for key, value in self.life_line_chart_instance.additional_graphical_items.items():
            if key == 'axis':
                continue
            additional_items += value
        sorted_individuals = [(gr.birth_date_ov, index, gr) for index, gr in enumerate(
            self.life_line_chart_instance.gr_individuals)]
        sorted_individuals.sort()
        # sorted_individual_items = []
        # for _, index, graphical_individual_representation in sorted_individuals:
        #     sorted_individual_items += graphical_individual_representation.items

        sorted_individual_dict = defaultdict(list)
        for _, _, gr_individual in sorted_individuals:
            for key, item in gr_individual.items:
                sorted_individual_dict[key].append(item)
        sorted_individual_flat_item_list = []
        for key in sorted(sorted_individual_dict.keys()):
            sorted_individual_flat_item_list += sorted_individual_dict[key]

        self.chart_items = additional_items + sorted_individual_flat_item_list
        self.image_cache = {}
        try:
            if new_root_individual:
                self.fit_to_page()
        except:
            pass

    def clear_instance_cache(self, _button=None):
        if self.life_line_chart_instance:
            self.rebuild_next_time = True
            self.life_line_chart_instance.clear_graphical_representations()
            self.life_line_chart_instance._instances.clear()

    def rebuild_instance_cache(self, _button=None):
        self.clear_instance_cache()
        if self.life_line_chart_instance:
            rp = self.rootpersonh
            self.rootpersonh = None
            self.set_values(rp, self.filter)

    def revert_placement(self, _button=None):
        if self.life_line_chart_instance:
            if 'ancestor_placement' in self.chart_configuration:
                self.chart_configuration['ancestor_placement'] = {}
            if 'family_children' in self.chart_configuration:
                self.chart_configuration['family_children'] = []
            if 'discovery_blacklist' in self.chart_configuration:
                self.chart_configuration['discovery_blacklist'] = []
            self.set_values(self.rootpersonh, self.filter)

    def draw(self, ctx=None, scale=1.):
        """
        The main method to do the drawing.
        If ctx is given, we assume we draw draw raw on the cairo context ctx
        To draw in GTK3 and use the allocation, set ctx=None.
        Note: when drawing for display, to counter a Gtk issue with scrolling
        or resizing the drawing window, we draw on a surface, then copy to the
        drawing context when the Gtk 'draw' signal arrives.
        """
        # first do size request of what we will need
        if not ctx:  # Display
            graph = self.life_line_chart_instance
            size_w_a = max(100, min(400000, int(graph.get_full_width()*self.zoom_level)))
            size_h_a = max(100, min(400000, int(graph.get_full_height()*self.zoom_level)))
            #size_w_a = max(size_w_a, self.get_allocated_width())
            #size_h_a = max(size_h_a, self.get_allocated_height())
            size_w_a = self.get_allocated_width()
            size_h_a = self.get_allocated_height()
            self.set_size_request(size_w_a, size_h_a)
            size_w = self.get_allocated_width()
            size_h = self.get_allocated_height()
            self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                              size_w_a, size_h_a)
            ctx = cairo.Context(self.surface)
            ctx.scale(self.zoom_level, self.zoom_level)

            visible_range = self.scrolledwindow.get_clip(
            ).width, self.scrolledwindow.get_clip().height
            sb_h_adj = self.scrolledwindow.get_hscrollbar().get_adjustment()
            sb_v_adj = self.scrolledwindow.get_vscrollbar().get_adjustment()
            #visible_range = 0,0
            sb_h_adj.set_value((self.zoom_level / self.zoom_level_backup) * (
                visible_range[0] * 0.5 + sb_h_adj.get_value()) - visible_range[0] * 0.5)
            sb_v_adj.set_value((self.zoom_level / self.zoom_level_backup) * (
                visible_range[1] * 0.5 + sb_v_adj.get_value()) - visible_range[1] * 0.5)
            self.zoom_level_backup = self.zoom_level
        else:  # printing
            # ??

            self.view_position_limit_to_bounds()
            translated_position = self._position_move(self.upper_left_view_position, self.center_delta_xy)
            translated_position = self.view_position_get_limited(translated_position)
            ctx.translate(-translated_position[0], -translated_position[1])
            ctx.scale(self.zoom_level, self.zoom_level)
            ctx.set_antialias(cairo.Antialias.BEST)
            #ctx.scale(scale, scale)
            #self.zoom_level_backup = self.zoom_level
        visible_range = (self.get_allocated_width(), self.get_allocated_height())
        arbitrary_clip_offset = max(visible_range)*0.5 # remove text items if their start position is 50%*view_width outside
        view_x_min = (self.upper_left_view_position[0] - arbitrary_clip_offset) / self.zoom_level
        view_x_max = (self.upper_left_view_position[0] + arbitrary_clip_offset + visible_range[0]) / self.zoom_level
        view_y_min = (self.upper_left_view_position[1] - arbitrary_clip_offset) / self.zoom_level
        view_y_max = (self.upper_left_view_position[1] + arbitrary_clip_offset + visible_range[1]) / self.zoom_level
        self.draw_items(ctx, self.chart_items, (view_x_min, view_y_min, view_x_max, view_y_max))

    def draw_items(self, ctx, chart_items, view_clip_box, limit_font_size = None):
        view_x_min, view_y_min, view_x_max, view_y_max = view_clip_box
        for item_index, item in enumerate(chart_items):
            def text_function(ctx, text, x, y, rotation=0, fontName="Arial", fontSize=10, verticalPadding=0, vertical_offset=0, horizontal_offset=0, bold=False, align='center', position='middle', color=(0,0,0)):
                """
                Used to draw normal text
                """
                rotation = rotation * math.pi / 180

                if bold:
                    ctx.select_font_face(
                        fontName, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                else:
                    ctx.select_font_face(
                        fontName, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                f_o = cairo.FontOptions()

                ctx.set_source_rgba(float(color[0]/255),
                                    float(color[1]/255),
                                    float(color[2]/255),
                                    1) # transparency
                #f_o.set_antialias(cairo.ANTIALIAS_GOOD)
                f_o.set_hint_metrics(cairo.HINT_METRICS_OFF)
                ctx.set_font_options(f_o)
                ctx.set_font_size(fontSize)

                # this method still quantizes the fheight!
                # fascent, fdescent, fheight, fxadvance, fyadvance = ctx.font_extents()
                fheight = 1.15*fontSize

                ctx.save()
                ctx.translate(x, y)
                ctx.rotate(rotation)
                ctx.translate(horizontal_offset, vertical_offset)

                lines = text.split("\n")

                for i, line in enumerate(lines):
                    # ctx.set_font_size(fontSize)
                    xoff, yoff, textWidth, textHeight = ctx.text_extents(line)[
                        :4]
                    # xoff *= self.zoom_level
                    # yoff *= self.zoom_level
                    # textWidth *= self.zoom_level
                    # textHeight *= self.zoom_level

                    if align == 'middle':
                        offx = -textWidth / 2.0
                    elif align == 'end':
                        offx = -textWidth
                    else:
                        offx = 0

                    if position == 'middle':
                        offy = (fheight / 2.0) + \
                            (fheight + verticalPadding) * i
                    else:
                        offy = (fheight + verticalPadding) * i

                    ctx.move_to(offx, offy)
                    ctx.show_text(line)
                ctx.restore()

            if item['type'] == 'text':
                args = item['config']
                #ctx.set_font_size(float(args['font_size'][:-2]))
                # ctx.select_font_face("Arial",
                #                     cairo.FONT_SLANT_NORMAL,
                #                     cairo.FONT_WEIGHT_NORMAL)
                font_size = item['font_size']
                if type(font_size) == str:
                    if font_size.endswith('px') or font_size.endswith('pt'):
                        font_size = float(font_size[:-2])
                if limit_font_size:
                    font_size = min(font_size, limit_font_size[1]/self.zoom_level)
                    font_size = max(font_size, limit_font_size[0]/self.zoom_level)
                rotation = 0
                if 'transform' in args and args['transform'].startswith('rotate('):
                    rotation = float(args['transform'][7:-1].split(',')[0])

                estimated_end_pos = (
                    args['insert'][0] + math.cos(rotation/180*math.pi)*font_size*self.zoom_level*len(args['text']),
                    args['insert'][1] + math.sin(rotation/180*math.pi)*font_size*self.zoom_level*len(args['text'])
                )
                font_too_small = item['font_size'] * self.zoom_level < 1
                view_x_size = view_x_max - view_x_min
                view_y_size = view_y_max - view_y_min

                q_x_start = (args['insert'][0] - view_x_min)/view_x_size
                q_x_end = (estimated_end_pos[0] - view_x_min)/view_x_size
                q_y_start = (args['insert'][1] - view_y_min)/view_y_size
                q_y_end = (estimated_end_pos[1] - view_y_min)/view_y_size
                text_should_be_visible_x = q_x_start < 0 and q_x_end >= 0 or \
                    q_x_end < 0 and q_x_start >= 0 or \
                    q_x_start > 1 and q_x_end <= 1 or \
                    q_x_end > 1 and q_x_start <= 1 or \
                    q_x_start >= 0 and q_x_start <= 1 and q_x_end >= 0 and q_x_start <= 1
                text_should_be_visible_y = q_y_start < 0 and q_y_end >= 0 or \
                    q_y_end < 0 and q_y_start >= 0 or \
                    q_y_start > 1 and q_y_end <= 1 or \
                    q_y_end > 1 and q_y_start <= 1 or \
                    q_y_start >= 0 and q_y_start <= 1 and q_y_end >= 0 and q_y_start <= 1
                if font_too_small or not text_should_be_visible_x or not text_should_be_visible_y:
                    continue # dont draw this item!
                vertical_offset = 0
                if 'dy' in args:
                    if args['dy'][0].endswith('px') or args['dy'][0].endswith('pt'):
                        vertical_offset = float(args['dy'][0][:-2])
                    else:
                        vertical_offset = float(args['dy'][0])
                horizontal_offset = 0
                if 'dx' in args:
                    if args['dx'][0].endswith('px') or args['dx'][0].endswith('pt'):
                        horizontal_offset = float(args['dx'][0][:-2])
                    else:
                        horizontal_offset = float(args['dx'][0])
                anchor = args.get('text_anchor')
                if not anchor:
                    anchor = 'start'
                color = item.get('fill', (0,0,0))
                text_function(
                    ctx,
                    args['text'],
                    args['insert'][0],
                    args['insert'][1],
                    rotation,
                    fontSize=font_size,
                    fontName=item['font_name'],
                    vertical_offset=vertical_offset,
                    horizontal_offset=horizontal_offset,
                    align=anchor,
                    position='top',
                    color=color)
                # ctx.save()
                # ctx.
                # if 'text_anchor' in args and args['text_anchor'] == 'middle':
                #     x_bearing, y_bearing, width, height = ctx.text_extents(args['text'])[:4]
                #     ctx.move_to(args['insert'][0] - width/2, args['insert'][1])
                #     ctx.show_text(args['text'])
                # else:
                #     ctx.move_to(*args['insert'])
                #     ctx.show_text(args['text'])
                # cr.restore()
                #
                # #args = deepcopy(item['config'])
                # #args['insert'] = (args['insert'][0], args['insert'][1])
                # svg_text = svg_document.text(
                #     **args)
                # x = svg_document.add(svg_text)
            elif item['type'] == 'path':
                arguments = deepcopy(item['config']['arguments'])
                arguments = [individual_id for individual_id in arguments]
                colors = [c/255. for c in item['color']]
                def paint_path(stroke_with_multiplier, colors):
                    if self.formatting['fade_individual_color'] and 'color_pos' in item:
                        cp = item['color_pos']

                        #ctx.set_source_rgb(colors[0], colors[1], colors[2])
                        #lg3 = cairo.LinearGradient(0, item['color_pos'][0],  0, item['color_pos'][1])
                        lg3 = cairo.LinearGradient(
                            arguments[0].real, item['color_pos'][0],
                            arguments[0].real, item['color_pos'][1])
                        #fill = svg_document.linearGradient(("0", str(item['color_pos'][0])+""), ("0", str(item['color_pos'][1])+""), gradientUnits='userSpaceOnUse')
                        lg3.add_color_stop_rgba(
                            0, colors[0], colors[1], colors[2], 1)
                        lg3.add_color_stop_rgb(1, *self.life_line_chart_instance._colors['fade_to_death'])

                        ctx.set_source(lg3)
                        if item['config']['type'] == 'Line':
                            ctx.move_to(arguments[0].real, arguments[0].imag)
                            ctx.set_line_width(item['stroke_width']*stroke_with_multiplier)
                            ctx.line_to(arguments[1].real, arguments[1].imag)
                            ctx.stroke()
                        elif item['config']['type'] == 'CubicBezier':
                            ctx.move_to(arguments[0].real, arguments[0].imag)
                            ctx.set_line_width(item['stroke_width']*stroke_with_multiplier)
                            ctx.curve_to(
                                arguments[1].real, arguments[1].imag,
                                arguments[2].real, arguments[2].imag,
                                arguments[3].real, arguments[3].imag)
                            ctx.stroke()
                    else:
                        if item['config']['type'] == 'Line':
                            ctx.move_to(arguments[0].real, arguments[0].imag)
                            ctx.set_source_rgb(
                                colors[0], colors[1], colors[2])
                            ctx.set_line_width(item['stroke_width']*stroke_with_multiplier)
                            ctx.line_to(arguments[1].real, arguments[1].imag)
                            if 'stroke_dasharray' in item:
                                ctx.set_dash([float(v) for v in item['stroke_dasharray'].split(',')])
                            ctx.stroke()
                            if 'stroke_dasharray' in item:
                                ctx.set_dash([])
                        elif item['config']['type'] == 'CubicBezier':

                            ctx.move_to(arguments[0].real, arguments[0].imag)
                            ctx.set_source_rgb(
                                colors[0], colors[1], colors[2])
                            ctx.set_line_width(item['stroke_width']*stroke_with_multiplier)
                            ctx.curve_to(arguments[1].real, arguments[1].imag, arguments[2].real,
                                            arguments[2].imag, arguments[3].real, arguments[3].imag)
                            ctx.stroke()
                if self._tooltip_individual_cache is not None and 'gir' in item and item['gir'] == self._tooltip_individual_cache[0]:
                    paint_path(1.4, (1,0,0))
                    paint_path(1.2, (self.text_color.red, self.text_color.green, self.text_color.blue))
                paint_path(1, colors)
            elif item['type'] == 'textPath':
                from math import cos, sin, atan2, pi

                # def distance(x1, y1, x2, y2):
                #     """Get the distance between two points."""
                #     return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

                # def point_angle(cx, cy, px, py):
                #     """Return angle between x axis and point knowing given center."""
                #     return atan2(py - cy, px - cx)

                # def point_following_path(path, width):
                #     """Get the point at ``width`` distance on ``path``."""
                #     total_length = 0
                #     for item in path:
                #         if item[0] == cairo.PATH_MOVE_TO:
                #             old_point = item[1]
                #         elif item[0] == cairo.PATH_LINE_TO:
                #             new_point = item[1]
                #             length = distance(
                #                 old_point[0], old_point[1], new_point[0], new_point[1])
                #             total_length += length
                #             if total_length < width:
                #                 old_point = new_point
                #             else:
                #                 length -= total_length - width
                #                 angle = point_angle(
                #                     old_point[0], old_point[1], new_point[0], new_point[1])
                #                 x = cos(angle) * length + old_point[0]
                #                 y = sin(angle) * length + old_point[1]
                #                 return x, y

                # def zip_letters(xl, yl, dxl, dyl, rl, word):
                #     """Returns a list with the current letter's positions (x, y and rotation).
                #     E.g.: for letter 'L' with positions x = 10, y = 20 and rotation = 30:
                #     >>> [[10, 20, 30], 'L']
                #     Store the last value of each position and pop the first one in order to
                #     avoid setting an x,y or rotation value that have already been used.
                #     """
                #     return (
                #         ([pl.pop(0) if pl else None for pl in (xl, yl, dxl, dyl, rl)], char)
                #         for char in word)

                # x, y, dx, dy, rotate = [], [], [], [], [0]
                # if 'x' in node:
                #     x = [size(surface, i, 'x')
                #         for i in normalize(node['x']).strip().split(' ')]
                # if 'y' in node:
                #     y = [size(surface, i, 'y')
                #         for i in normalize(node['y']).strip().split(' ')]
                # if 'dx' in node:
                #     dx = [size(surface, i, 'x')
                #         for i in normalize(node['dx']).strip().split(' ')]
                # if 'dy' in node:
                #     dy = [size(surface, i, 'y')
                #         for i in normalize(node['dy']).strip().split(' ')]
                # if 'rotate' in node:
                #     rotate = [radians(float(i)) if i else 0
                #             for i in normalize(node['rotate']).strip().split(' ')]
                # last_r = rotate[-1]
                # letters_positions = zip_letters(x, y, dx, dy, rotate, node.text)
                # def draw_t_a_p():
                #
                #     for i, ((x, y, dx, dy, r), letter) in enumerate(letters_positions):
                #         if x:
                #             surface.cursor_d_position[0] = 0
                #         if y:
                #             surface.cursor_d_position[1] = 0
                #         surface.cursor_d_position[0] += dx or 0
                #         surface.cursor_d_position[1] += dy or 0
                #         text_extents = surface.context.text_extents(letter)
                #         extents = text_extents[4]
                #         if text_path:
                #             start = surface.text_path_width + surface.cursor_d_position[0]
                #             start_point = point_following_path(cairo_path, start)
                #             middle = start + extents / 2
                #             middle_point = point_following_path(cairo_path, middle)
                #             end = start + extents
                #             end_point = point_following_path(cairo_path, end)
                #             if i:
                #                 extents += letter_spacing
                #             surface.text_path_width += extents
                #             if not all((start_point, middle_point, end_point)):
                #                 continue
                #             if not 0 <= middle <= length:
                #                 continue
                #             surface.context.save()
                #             surface.context.translate(*start_point)
                #             surface.context.rotate(point_angle(*(start_point + end_point)))
                #             surface.context.translate(0, surface.cursor_d_position[1])
                #             surface.context.move_to(0, 0)
                #             bounding_box = extend_bounding_box(
                #                 bounding_box, ((end_point[0], text_extents[3]),))

                # def pathtext(g, path, txt, offset) :
                #     "draws the characters of txt along the specified path in the Context g, using its" \
                #     " current font and other rendering settings. offset is the initial character placement" \
                #     " offset from the start of the path."
                #     #path = path.flatten() # ensure all straight-line segments
                #     curch = 0 # index into txt
                #     setdist = offset # distance at which to place next char
                #     pathdist = 0
                #     for seg in path.segments :
                #         curpos = None
                #         ovr = 0
                #         for pt in tuple(seg.points) + ((), (seg.points[0],))[seg.closed] :
                #             assert not pt.off
                #             prevpos = curpos
                #             curpos = pt.pt
                #             if prevpos != None :
                #                 delta = curpos - prevpos
                #                 dist = abs(delta) # length of line segment
                #                 if dist != 0 :
                #                     ds = delta / dist * ovr
                #                     cp = g.user_to_device(prevpos + ds)
                #                     pathdist += dist # accumulate length of path
                #                     while True :
                #                         if setdist > pathdist :
                #                             # no more room to place a character
                #                             ovr = setdist - pathdist
                #                             # deduct off placement of first char on next line segment
                #                             break
                #                         #end if
                #                         if curch == len(txt) :
                #                             # no more characters to place
                #                             break
                #                         # place another character along this line segment
                #                         ch = txt[curch] # FIXME: should not split off trailing diacritics
                #                         curch += 1
                #                         text_extents = g.text_extents(ch)
                #                         charbounds = Vector(text_extents.x_advance, text_extents.y_bearing)
                #                         g.save()
                #                         g.transform \
                #                         (
                #                                 Matrix.translate
                #                                 (
                #                                     g.device_to_user(cp) + delta * charbounds / 2 / dist
                #                                 ) # midpoint of character back to character position
                #                             *
                #                                 Matrix.rotate(delta.angle())
                #                                 # rotate about midpoint of character
                #                             *
                #                                 Matrix.translate(- charbounds / 2)
                #                                 # midpoint of character to origin
                #                         )
                #                         g.show_text(ch)
                #                         cp = g.user_to_device(g.current_point)
                #                         g.restore()
                #                         setdist += charbounds.x # update distance travelled along path
                #                     #end while
                #                 #end if
                #             #end if
                #         #end for
                #     #end for
                # #end pathtext
                import svgpathtools
                from cmath import phase

                def draw_text_along_path(ctx, textspans, start_x, start_y, cp1_x, cp1_y, cp2_x, cp2_y, end_x, end_y, show_path_line=True):
                    def warpPath(ctx, function):
                        first = True

                        for type, points in ctx.copy_path_flat():
                            if type == cairo.PATH_MOVE_TO:
                                if first:
                                    ctx.new_path()
                                    first = False
                                x, y = function(*points)
                                ctx.move_to(x, y)

                            elif type == cairo.PATH_LINE_TO:
                                x, y = function(*points)
                                ctx.line_to(x, y)

                            elif type == cairo.PATH_CURVE_TO:
                                x1, y1, x2, y2, x3, y3 = points
                                x1, y1 = function(x1, y1)
                                x2, y2 = function(x2, y2)
                                x3, y3 = function(x3, y3)
                                ctx.curve_to(x1, y1, x2, y2, x3, y3)

                            elif type == cairo.PATH_CLOSE_PATH:
                                ctx.close_path()

                    def follow_path(path_length, path, te, x, y):
                        #p = x/path_length
                        p = path.ilength(
                            min(x, path_length), error=1e-3, min_depth=2)
                        return path.point(p).real - path.normal(p).real*(y-te.y_bearing/2), path.point(p).imag - path.normal(p).imag*(y-te.y_bearing/2)

                    def xxx(path_length, ctx, path, textspans, vertical_offset, horizontal_offset):
                        x_pos = horizontal_offset
                        for text, args in textspans:
                            if 'dx' in args:
                                x_pos += float(args['dx'][0])
                            for character in text:
                                p = path.ilength(
                                    min(x_pos, path_length), error=1e-3, min_depth=2)
                                character_pos = path.point(
                                    p) - path.normal(p) * vertical_offset*0
                                x, y = (character_pos.real,
                                        character_pos.imag)
                                r = phase(path.normal(p))/pi*180 + 90
                                ctx.save()

                                text_function(
                                    ctx,
                                    character,
                                    x,
                                    y,
                                    r,
                                    fontSize=item['font_size'],
                                    fontName=item['font_name'],
                                    vertical_offset=vertical_offset,
                                    horizontal_offset=horizontal_offset,
                                    align='start',
                                    position='left',
                                    bold='style' in args and 'bold' in args['style'])
                                ctx.select_font_face(
                                    item['font_name'], cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                                ctx.set_font_size(font_size)
                                te = ctx.text_extents(character,)
                                ctx.restore()
                                x_pos += te.x_advance

                            te = ctx.text_extents(' ',)
                            x_pos += te.x_advance
                    svg_path = svgpathtools.CubicBezier(
                        start_x + start_y*1j, cp1_x + cp1_y*1j, cp2_x + cp2_y*1j, end_x + end_y*1j)
                    # if show_path_line:
                    #     ctx.move_to(start_x, start_y)
                    #     ctx.curve_to(cp1_x, cp1_y, cp2_x, cp2_y, end_x, end_y)
                    #     ctx.stroke()
                    #path = ctx.copy_path_flat()

                    #ctx.new_path()
                    #ctx.move_to(0, 0)
                    #ctx.text_path(text)
                    path_length = svg_path.length(error=1e-3, min_depth=2)

                    ##pathtext(ctx, path, text, 0)

                    vertical_offset = 0
                    if 'dy' in item['config']:
                        if item['config']['dy'][0].endswith('px') or item['config']['dy'][0].endswith('pt'):
                            vertical_offset = float(
                                item['config']['dy'][0][:-2])
                        else:
                            vertical_offset = float(
                                item['config']['dy'][0])
                    horizontal_offset = 0
                    if 'dx' in args:
                        if args['dx'][0].endswith('px') or args['dx'][0].endswith('pt'):
                            horizontal_offset = float(args['dx'][0][:-2])
                        else:
                            horizontal_offset = float(args['dx'][0])
                    xxx(path_length, ctx, svg_path,
                        item['spans'], vertical_offset, horizontal_offset)
                    #te=ctx.text_extents(text)

                    #warpPath(ctx, lambda x, y: follow_path(path_length, svg_path, te, x, y))
                    ctx.fill()

                args_path = item['path']
                args_text = item['config']

                if args_path['type'] == 'CubicBezier':
                    arguments = deepcopy(args_path['arguments'])
                    ctx.new_path()
                    ctx.set_line_width(0.1)
                    #path = svgpathtools.CubicBezier(*arguments)
                    ctx.set_source_rgb(0, 0, 0)

                    draw_text_along_path(ctx, item['spans'][0][0], arguments[0].real, arguments[0].imag, arguments[1].real,
                                            arguments[1].imag, arguments[2].real, arguments[2].imag, arguments[3].real, arguments[3].imag)
                    # ctx.move_to(arguments[0].real, arguments[0].imag)
                    # ctx.set_source_rgb(*[c/255. for c in graphical_individual_representation.color])
                    # ctx.set_line_width(self.life_line_chart_instance._formatting['line_thickness'])
                    # ctx.curve_to()
                    # ctx.text_path("textxxxxxx")
                    # path = ctx.copy_path()
                    #ctx.curve_to(arguments[1].real, arguments[1].imag, arguments[2].real, arguments[2].imag, arguments[3].real, arguments[3].imag)
                    #warpPath(ctx, curl)
                    #ctx.close_path()
                    #ctx.fill()
                    #ctx.stroke()
                #args_path['arguments']
                pass
                # svg_text = svg_document.text(
                #     **args_text)
                # if args_path['type'] == 'Line':
                #     constructor_function = Line
                # elif args_path['type'] == 'CubicBezier':
                #     constructor_function = CubicBezier
                # svg_path = Path(constructor_function(*args_path['arguments']))
                # y = svg_document.path( svg_path.d(), fill = 'none')
                # svg_document.add(y)
                # #x = svg_document.add(svg_text)
                # x = svg_document.add(svgwrite.text.Text('', dy = [args_text['dy']], font_size = args_text['font_size']))
                # t = svgwrite.text.TextPath(y, text = args_text['text'])
                # for span in item['spans']:
                #     t.add(svg_document.tspan(span[0], **span[1]))
                # x.add(t)

            elif item['type'] == 'image':
                def draw_image(ctx, image, left, top, width, height):
                    """Draw a scaled image on a given context."""
                    image_surface = self.image_cache.get(image)
                    if image_surface is None:
                        if os.path.splitext(image.upper())[1] in ['.JPG', 'JPEG']:
                            image_surface = cairo.ImageSurface.create_from_jpg(image)
                        if os.path.splitext(image.upper())[1] in ['.PNG']:
                            image_surface = cairo.ImageSurface.create_from_png(image)
                        self.image_cache[image] = image_surface
                    # calculate proportional scaling
                    img_height = image_surface.get_height()
                    img_width = image_surface.get_width()
                    width_ratio = float(width) / float(img_width)
                    height_ratio = float(height) / float(img_height)
                    scale_xy = min(height_ratio, width_ratio)
                    if height_ratio > scale_xy:
                        top -= (img_height * scale_xy - height)/2
                    if width_ratio - scale_xy:
                        left -= (img_width * scale_xy - width)/2
                    # scale image and add it
                    ctx.save()
                    ctx.translate(left, top)
                    ctx.scale(scale_xy, scale_xy)
                    ctx.set_source_surface(image_surface)

                    ctx.paint()
                    ctx.restore()
                import os

                if self._tooltip_individual_cache is not None and 'gfr' in item and \
                        item['gfr'] == self._tooltip_individual_cache[1]:
                    factor = 1.5
                    size = item['config']['size'][0]*factor, item['config']['size'][1]*factor
                    pos = item['config']['insert'][0] - item['config']['size'][0]*(factor/2 - 0.5), \
                          item['config']['insert'][1] - item['config']['size'][1]*(factor/2 - 0.5)
                    draw_image(ctx, item['filename'], pos[0], pos[1], size[0], size[1])
                else:
                    draw_image(ctx, item['filename'], item['config']['insert'][0], item['config']['insert'][1], item['config']['size'][0], item['config']['size'][1])
                # marriage_pos and 'spouse' in positions[individual_id]['marriage']:
                #m_pos_x = (positions[positions[individual_id]['marriage']['spouse']]['x_position'] + x_pos)/2
                #svg_document.add(svg_document.use(image_def.get_iri(), **item['config']))
                pass

            elif item['type'] == 'rect':
                pass
                #this_rect = svg_document.rect(**item['config'])

                #insert=(rect[0], rect[1]), size = (rect[2]-rect[0], rect[3]-rect[1]), fill = 'none')
                #svg_document.add(this_rect)

    def do_mouse_click(self):
        # no drag occured, expand or collapse the section
        self._mouse_click = False
        #self.draw()
        self.queue_draw_wrapper()

class LifeLineChartGrampsGUI:
    """ class for functions lifelinechart GUI elements will need in Gramps
    """

    def __init__(self, on_childmenu_changed):
        """
        Common part of GUI that shows Life Line Chart, needs to know what to do if
        one moves via Fan Ch    def set_lifeline(self, lifeline):art to a new person
        on_childmenu_changed: in popup, function called on moving
                              to a new person
        """
        self.lifeline = None
        self.menu = None
        self.filter = None
        self.on_childmenu_changed = on_childmenu_changed
        self.format_helper = FormattingHelper(self.dbstate, self.uistate)
        self.uistate.connect('font-changed', self.reload_symbols)

    def reload_symbols(self):
        self.format_helper.reload_symbols()

    def set_lifeline(self, lifeline):
        """
        Set the lifelinechartwidget to work on
        """
        self.lifeline = lifeline
        self.lifeline.format_helper = self.format_helper
        self.lifeline.goto = self.on_childmenu_changed

    def main(self):
        """
        Fill the data structures with the active data. This initializes all
        data.
        """
        if self.lifeline.get_allocated_width() < 10:
            return
        root_person_handle = self.get_active('Person')
        self.lifeline.set_values(root_person_handle, self.generic_filter)
        self.lifeline.reset()
        #self.lifeline.draw()
        self.lifeline.queue_draw()

    def hide_person(self, obj, person_handle):
        self.chart_configuration['discovery_blacklist'].append(person_handle)
        root_person_handle = self.get_active('Person')
        self.lifeline.set_values(root_person_handle, self.generic_filter)

    def show_hidden_person(self, obj, person_handle):
        try:
            self.chart_configuration['discovery_blacklist'].remove(person_handle)
            root_person_handle = self.get_active('Person')
            self.lifeline.set_values(root_person_handle, self.generic_filter)
        except Exception as e:
            pass

    def show_siblings(self, obj, person_handle):
        if 'family_children' in self.chart_configuration:
            individual = self.lifeline.life_line_chart_instance._instances[(
                'i', person_handle)]
            self.chart_configuration['family_children'].append(individual.child_of_families[0].family_id)
            root_person_handle = self.get_active('Person')
            self.lifeline.set_values(root_person_handle, self.generic_filter)

    def hide_siblings(self, obj, person_handle):
        individual = self.lifeline.life_line_chart_instance._instances[(
            'i', person_handle)]
        try:
            self.chart_configuration['family_children'].remove(individual.child_of_families[0].family_id)
            root_person_handle = self.get_active('Person')
            self.lifeline.set_values(root_person_handle, self.generic_filter)
        except Exception as e:
            pass

    def place_ancestors_above_specific_family(self, obj, gr_individual, gr_family):
        try:
            gr_cof = gr_individual.connected_parent_families[0]
            if gr_cof.g_id in self.chart_configuration['ancestor_placement']:
                self.chart_configuration['ancestor_placement'].pop(gr_cof.g_id)
            self.chart_configuration['ancestor_placement'][gr_cof.g_id] =(
                gr_family.g_id, gr_individual.g_id
            )
            root_person_handle = self.get_active('Person')
            self.lifeline.set_values(root_person_handle, self.generic_filter)
        except Exception as e:
            pass

    def on_popup(self, obj, event, gr_individual, gr_family=None):
        """
        Builds the full menu (including Siblings, Spouses, Children,
        and Parents) with navigation.
        """
        person_handle = gr_individual.individual._gramps_person.handle
        if gr_family:
            family_handle = gr_family.family._gramps_family.handle
        else:
            family_handle = None
        dummy_obj = obj
        #store menu for GTK3 to avoid it being destroyed before showing
        self.menu = Gtk.Menu()
        menu = self.menu
        self.menu.set_reserve_toggle_size(False)

        person = self.dbstate.db.get_person_from_handle(person_handle)
        if not person:
            return 0

        go_item = Gtk.MenuItem(label=name_displayer.display(person))
        go_item.connect("activate", self.on_childmenu_changed, person_handle)
        go_item.show()
        menu.append(go_item)

        sep = Gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)

        if person_handle != self.lifeline.rootpersonh:
            blacklist_item = Gtk.MenuItem(label=_('Hide person'))
            blacklist_item.connect("activate", self.hide_person, person_handle)
            blacklist_item.show()
            menu.append(blacklist_item)

        if len(self.chart_configuration['discovery_blacklist']):
            remove_from_blacklist_item = Gtk.MenuItem(label=_('Show person'))
            remove_from_blacklist_item.show()
            remove_from_blacklist_item.set_submenu(Gtk.Menu())
            rbl_menu = remove_from_blacklist_item.get_submenu()
            rbl_menu.set_reserve_toggle_size(False)
            unavailable_items = []
            for handle in self.chart_configuration['discovery_blacklist']:
                try:
                    p = self.dbstate.db.get_person_from_handle(handle)
                    blacklist_item = Gtk.MenuItem(label=name_displayer.display(p))
                    blacklist_item.connect("activate", self.show_hidden_person, handle)
                    blacklist_item.show()
                    rbl_menu.append(blacklist_item)
                except:
                    unavailable_items.append(handle)
            for handle in unavailable_items:
                self.chart_configuration['discovery_blacklist'].remove(handle)
            menu.append(remove_from_blacklist_item)

        try:
            if self.lifeline.chart_class == AncestorChart:
                cof = gr_individual.individual.child_of_families[0]
                if len(cof.children_individual_ids) > 1:
                    if cof.family_id not in self.chart_configuration['family_children']:
                        if len(cof.children_individual_ids) > len(cof.graphical_representations[0].visible_children):
                            show_siblings_item = Gtk.MenuItem(label=_('Show siblings'))
                            show_siblings_item.connect("activate", self.show_siblings, person_handle)
                            show_siblings_item.show()
                            menu.append(show_siblings_item)
                    else:
                        hide_siblings_item = Gtk.MenuItem(label=_('Hide siblings'))
                        hide_siblings_item.connect("activate", self.hide_siblings, person_handle)
                        hide_siblings_item.show()
                        menu.append(hide_siblings_item)
        except Exception as e:
            pass

        sep = Gtk.SeparatorMenuItem()
        sep.show()
        menu.append(sep)

        try:
            if self.lifeline.chart_class == AncestorChart:
                for gr_cof in gr_individual.connected_parent_families:
                    vms = gr_individual.visible_marriages
                    # if gr_family in vms:
                    #     gr_marriage = gr_family
                    # else:
                    #     gr_marriage = vms[0]
                    vss = gr_cof.visible_children
                    if len(vms) > 1 or len(vss):
                        if (gr_cof.g_id not in self.chart_configuration['ancestor_placement'] \
                                and (gr_family != vms[0] or gr_individual != vss[0]) \
                                or self.chart_configuration['ancestor_placement'][gr_cof.g_id] != \
                                    (gr_family.g_id, gr_individual.g_id)):
                            show_siblings_item = Gtk.MenuItem(label=_('Show ancestors above ')
                                +str(gr_family.husb.plain_name)
                                + " and " +
                                str(gr_family.wife.plain_name)
                            )
                            show_siblings_item.connect("activate", self.place_ancestors_above_specific_family, gr_individual, gr_family)
                            show_siblings_item.show()
                            menu.append(show_siblings_item)
                # if len(cof.children_individual_ids) > 1:
                #     if cof.family_id not in self.chart_configuration['family_children']:
                #         if len(cof.children_individual_ids) > len(cof.graphical_representations[0].visible_children):
                #             show_siblings_item = Gtk.MenuItem(label=_('Show siblings'))
                #             show_siblings_item.connect("activate", self.show_siblings, person_handle)
                #             show_siblings_item.show()
                #             menu.append(show_siblings_item)
                #     else:
                #         hide_siblings_item = Gtk.MenuItem(label=_('Hide siblings'))
                #         hide_siblings_item.connect("activate", self.hide_siblings, person_handle)
                #         hide_siblings_item.show()
                #         menu.append(hide_siblings_item)

                sep = Gtk.SeparatorMenuItem()
                sep.show()
                menu.append(sep)
        except Exception as e:
            pass

        edit_item = Gtk.MenuItem.new_with_mnemonic(_('_Edit'))
        edit_item.connect("activate", self.edit_person_cb, person_handle)
        edit_item.show()
        menu.append(edit_item)
        # action related to the clicked family (when there is one)
        if family_handle:
            family = self.dbstate.db.get_family_from_handle(family_handle)
            edit_fam_item = Gtk.MenuItem()
            edit_fam_item.set_label(label=_("Edit family"))
            edit_fam_item.connect("activate", self.edit_fam_cb, family_handle)
            edit_fam_item.show()
            menu.append(edit_fam_item)
            #see if a reorder button is needed
            if family.get_father_handle() == person_handle:
                parth = family.get_mother_handle()
            else:
                parth = family.get_father_handle()
            lenfams = 0
            if parth:
                partner = self.dbstate.db.get_person_from_handle(parth)
                lenfams = len(partner.get_family_handle_list())
                if lenfams in [0, 1]:
                    lenfams = len(partner.get_parent_family_handle_list())
            reord_fam_item = Gtk.MenuItem()
            reord_fam_item.set_label(label=_("Reorder families"))
            reord_fam_item.connect("activate", self.reord_fam_cb, parth)
            reord_fam_item.set_sensitive(lenfams > 1)
            reord_fam_item.show()
            menu.append(reord_fam_item)

        clipboard_item = Gtk.MenuItem.new_with_mnemonic(_('_Copy'))
        clipboard_item.connect("activate", self.copy_person_to_clipboard_cb,
                               person_handle)
        clipboard_item.show()
        menu.append(clipboard_item)

        # collect all spouses, parents and children
        linked_persons = []

        # Go over spouses and build their menu
        item = Gtk.MenuItem(label=_("Spouses"))
        fam_list = person.get_family_handle_list()
        no_spouses = 1
        for fam_id in fam_list:
            family = self.dbstate.db.get_family_from_handle(fam_id)
            if family.get_father_handle() == person.get_handle():
                sp_id = family.get_mother_handle()
            else:
                sp_id = family.get_father_handle()
            if not sp_id:
                continue
            spouse = self.dbstate.db.get_person_from_handle(sp_id)
            if not spouse:
                continue

            if no_spouses:
                no_spouses = 0
                item.set_submenu(Gtk.Menu())
                sp_menu = item.get_submenu()
                sp_menu.set_reserve_toggle_size(False)

            sp_item = Gtk.MenuItem(label=name_displayer.display(spouse))
            linked_persons.append(sp_id)
            sp_item.connect("activate", self.on_childmenu_changed, sp_id)
            sp_item.show()
            sp_menu.append(sp_item)

        if no_spouses:
            item.set_sensitive(0)

        item.show()
        menu.append(item)

        # Go over siblings and build their menu
        item = Gtk.MenuItem(label=_("Siblings"))
        pfam_list = person.get_parent_family_handle_list()
        siblings = []
        step_siblings = []
        for fhdle in pfam_list:
            fam = self.dbstate.db.get_family_from_handle(fhdle)
            sib_list = fam.get_child_ref_list()
            for sib_ref in sib_list:
                sib_id = sib_ref.ref
                if sib_id == person.get_handle():
                    continue
                siblings.append(sib_id)
        # Collect a list of per-step-family step-siblings
            for parent_h in [fam.get_father_handle(), fam.get_mother_handle()]:
                if not parent_h:
                    continue
                parent = self.dbstate.db.get_person_from_handle(parent_h)
                other_families = [self.dbstate.db.get_family_from_handle(fam_id)
                                  for fam_id in parent.get_family_handle_list()
                                  if fam_id not in pfam_list]
                for step_fam in other_families:
                    fam_stepsiblings = [sib_ref.ref
                                        for sib_ref in
                                        step_fam.get_child_ref_list()
                                        if not sib_ref.ref ==
                                        person.get_handle()]
                    if fam_stepsiblings:
                        step_siblings.append(fam_stepsiblings)

        # Add siblings sub-menu with a bar between each siblings group
        if siblings or step_siblings:
            item.set_submenu(Gtk.Menu())
            sib_menu = item.get_submenu()
            sib_menu.set_reserve_toggle_size(False)
            sibs = [siblings]+step_siblings
            for sib_group in sibs:
                for sib_id in sib_group:
                    sib = self.dbstate.db.get_person_from_handle(sib_id)
                    if not sib:
                        continue
                    if find_children(self.dbstate.db, sib):
                        thelabel = escape(name_displayer.display(sib))
                        label = Gtk.Label(label='<b><i>%s</i></b>' % thelabel)
                    else:
                        thelabel = escape(name_displayer.display(sib))
                        label = Gtk.Label(label=thelabel)
                    sib_item = Gtk.MenuItem()
                    label.set_use_markup(True)
                    label.show()
                    label.set_alignment(0, 0)
                    sib_item.add(label)
                    linked_persons.append(sib_id)
                    sib_item.connect("activate", self.on_childmenu_changed,
                                     sib_id)
                    sib_item.show()
                    sib_menu.append(sib_item)
                if sibs.index(sib_group) < len(sibs)-1:
                    sep = Gtk.SeparatorMenuItem.new()
                    sep.show()
                    sib_menu.append(sep)
        else:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

        # Go over children and build their menu
        item = Gtk.MenuItem(label=_("Children"))
        no_children = 1
        childlist = find_children(self.dbstate.db, person)
        for child_handle in childlist:
            child = self.dbstate.db.get_person_from_handle(child_handle)
            if not child:
                continue

            if no_children:
                no_children = 0
                item.set_submenu(Gtk.Menu())
                child_menu = item.get_submenu()
                child_menu.set_reserve_toggle_size(False)

            if find_children(self.dbstate.db, child):
                thelabel = escape(name_displayer.display(child))
                label = Gtk.Label(label='<b><i>%s</i></b>' % thelabel)
            else:
                label = Gtk.Label(label=escape(name_displayer.display(child)))

            child_item = Gtk.MenuItem()
            label.set_use_markup(True)
            label.show()
            label.set_halign(Gtk.Align.START)
            child_item.add(label)
            linked_persons.append(child_handle)
            child_item.connect("activate", self.on_childmenu_changed,
                               child_handle)
            child_item.show()
            child_menu.append(child_item)

        if no_children:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

        # Go over parents and build their menu
        item = Gtk.MenuItem(label=_("Parents"))
        item.set_submenu(Gtk.Menu())
        par_menu = item.get_submenu()
        par_menu.set_reserve_toggle_size(False)
        no_parents = 1
        par_list = find_parents(self.dbstate.db, person)
        for par_id in par_list:
            if not par_id:
                continue
            par = self.dbstate.db.get_person_from_handle(par_id)
            if not par:
                continue

            if no_parents:
                no_parents = 0

            if find_parents(self.dbstate.db, par):
                thelabel = escape(name_displayer.display(par))
                label = Gtk.Label(label='<b><i>%s</i></b>' % thelabel)
            else:
                label = Gtk.Label(label=escape(name_displayer.display(par)))

            par_item = Gtk.MenuItem()
            label.set_use_markup(True)
            label.show()
            label.set_halign(Gtk.Align.START)
            par_item.add(label)
            linked_persons.append(par_id)
            par_item.connect("activate", self.on_childmenu_changed, par_id)
            par_item.show()
            par_menu.append(par_item)

        if no_parents:
            #show an add button
            add_item = Gtk.MenuItem.new_with_mnemonic(_('_Add'))
            add_item.connect("activate", self.on_add_parents, person_handle)
            add_item.show()
            par_menu.append(add_item)

        item.show()
        menu.append(item)

        # Go over parents and build their menu
        item = Gtk.MenuItem(label=_("Related"))
        no_related = 1
        for p_id in find_witnessed_people(self.dbstate.db, person):
            #if p_id in linked_persons:
            #    continue    # skip already listed family members

            per = self.dbstate.db.get_person_from_handle(p_id)
            if not per:
                continue

            if no_related:
                no_related = 0
                item.set_submenu(Gtk.Menu())
                per_menu = item.get_submenu()
                per_menu.set_reserve_toggle_size(False)

            label = Gtk.Label(label=escape(name_displayer.display(per)))

            per_item = Gtk.MenuItem()
            label.set_use_markup(True)
            label.show()
            label.set_halign(Gtk.Align.START)
            per_item.add(label)
            per_item.connect("activate", self.on_childmenu_changed, p_id)
            per_item.show()
            per_menu.append(per_item)

        if no_related:
            item.set_sensitive(0)
        item.show()
        menu.append(item)

        #we now construct an add menu
        item = Gtk.MenuItem.new_with_mnemonic(_("_Add"))
        item.set_submenu(Gtk.Menu())
        add_menu = item.get_submenu()
        add_menu.set_reserve_toggle_size(False)
        if family_handle:
            # allow to add a child to this family
            add_child_item = Gtk.MenuItem()
            add_child_item.set_label(_("Add child to family"))
            add_child_item.connect("activate", self.add_child_to_fam_cb,
                                   family_handle)
            add_child_item.show()
            add_menu.append(add_child_item)
        elif person_handle:
            #allow to add a partner to this person
            add_partner_item = Gtk.MenuItem()
            add_partner_item.set_label(_("Add partner to person"))
            add_partner_item.connect("activate", self.add_partner_to_pers_cb,
                                     person_handle)
            add_partner_item.show()
            add_menu.append(add_partner_item)

        add_pers_item = Gtk.MenuItem()
        add_pers_item.set_label(_("Add a person"))
        add_pers_item.connect("activate", self.add_person_cb)
        add_pers_item.show()
        add_menu.append(add_pers_item)
        item.show()
        menu.append(item)

        menu.popup(None, None, None, None, event.button, event.time)
        return 1

    def edit_person_cb(self, obj, person_handle):
        """
        Edit a person
        """
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            try:
                EditPerson(self.dbstate, self.uistate, [], person)
            except WindowActiveError:
                pass
            return True
        return False

    def edit_fam_cb(self, obj, family_handle):
        """
        Edit a family
        """
        fam = self.dbstate.db.get_family_from_handle(family_handle)
        if fam:
            try:
                EditFamily(self.dbstate, self.uistate, [], fam)
            except WindowActiveError:
                pass
            return True
        return False

    def reord_fam_cb(self, obj, person_handle):
        """
        reorder a family
        """
        try:
            Reorder(self.dbstate, self.uistate, [], person_handle)
        except WindowActiveError:
            pass
        return True

    def add_person_cb(self, obj):
        """
        Add a person
        """
        person = Person()
        #the editor requires a surname
        person.primary_name.add_surname(Surname())
        person.primary_name.set_primary_surname(0)
        try:
            EditPerson(self.dbstate, self.uistate, [], person)
        except WindowActiveError:
            pass

    def add_child_to_fam_cb(self, obj, family_handle):
        """
        Add a child to a family
        """
        def callback(x): return self.callback_add_child(x, family_handle)
        person = Person()
        name = Name()
        #the editor requires a surname
        name.add_surname(Surname())
        name.set_primary_surname(0)
        family = self.dbstate.db.get_family_from_handle(family_handle)
        father = self.dbstate.db.get_person_from_handle(
            family.get_father_handle())
        if father:
            preset_name(father, name)
        person.set_primary_name(name)
        try:
            EditPerson(self.dbstate, self.uistate, [], person,
                       callback=callback)
        except WindowActiveError:
            pass

    def callback_add_child(self, person, family_handle):
        """
        Add a child
        """
        ref = ChildRef()
        ref.ref = person.get_handle()
        family = self.dbstate.db.get_family_from_handle(family_handle)
        family.add_child_ref(ref)

        with DbTxn(_("Add Child to Family"), self.dbstate.db) as trans:
            #add parentref to child
            person.add_parent_family_handle(family_handle)
            #default relationship is used
            self.dbstate.db.commit_person(person, trans)
            #add child to family
            self.dbstate.db.commit_family(family, trans)

    def add_partner_to_pers_cb(self, obj, person_handle):
        """
        Add a family with the person preset
        """
        family = Family()
        person = self.dbstate.db.get_person_from_handle(person_handle)

        if not person:
            return

        if person.gender == Person.MALE:
            family.set_father_handle(person.handle)
        else:
            family.set_mother_handle(person.handle)

        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            pass

    def on_add_parents(self, obj, person_handle):
        """
        Add a family
        """
        dummy_obj = obj
        family = Family()
        childref = ChildRef()
        childref.set_reference_handle(person_handle)
        family.add_child_ref(childref)
        try:
            EditFamily(self.dbstate, self.uistate, [], family)
        except WindowActiveError:
            return

    def copy_person_to_clipboard_cb(self, obj, person_handle):
        """
        Renders the person data into some lines of text and puts that
        into the clipboard
        """
        person = self.dbstate.db.get_person_from_handle(person_handle)
        if person:
            cbx = Gtk.Clipboard.get_for_display(Gdk.Display.get_default(),
                                                Gdk.SELECTION_CLIPBOARD)
            cbx.set_text(self.format_helper.format_person(person, 11), -1)
            return True
        return False
