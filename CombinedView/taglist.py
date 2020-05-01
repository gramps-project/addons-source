#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Nick Hall
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
Tag list widget

This widget displays a graphical list of tags.
"""

#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import PangoCairo

#-------------------------------------------------------------------------
#
# SegmentMap class
#
#-------------------------------------------------------------------------

class TagList(Gtk.DrawingArea):
    """
    A graphical list of tags.
    """

    __gsignals__ = {'clicked': (GObject.SignalFlags.RUN_FIRST, None, (int,))}

    def __init__(self, tag_list=None):
        Gtk.DrawingArea.__init__(self)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect('motion-notify-event', self.on_pointer_motion)
        self.connect('button-press-event', self.on_button_press)

        self.__active = -1
        self.__rects = []
        if tag_list is None:
            self.tag_list = []
        else:
            self.tag_list = tag_list

    def set_tags(self, tag_list):
        """
        Set the tags to display.
        @param tag_list: A list of (tag name, color) tuples.
        @type tag_list: list
        """
        self.tag_list = tag_list

    def do_draw(self, cr):
        """
        A custom draw method for this widget.
        @param cr: A cairo context.
        @type cr: cairo.Context
        """
        if (len(self.tag_list)) == 0:
            return

        allocation = self.get_allocation()
        context = self.get_style_context()
        fg_color = context.get_color(context.get_state())

        padding = 2
        size = 10

        cr.set_line_width(1)
        self.__rects = []
        for i, tag in enumerate(self.tag_list):

            cr.rectangle(i * (padding + size),
                         padding,
                         size,
                         size)
            self.__rects.append((i * (padding + size),
                         padding,
                         size,
                         size))

            color = Gdk.RGBA()
            color.parse(tag[1])
            cr.set_source_rgba(color.red, color.green, color.blue, 1)
            cr.fill()

        self.set_size_request((size + padding) * (i + 1) + padding, -1)

    def on_pointer_motion(self, _dummy, event):
        """
        Called when the pointer is moved.
        @param _dummy: This widget.  Unused.
        @type _dummy: Gtk.Widget
        @param event: An event.
        @type event: Gdk.Event
        """
        if self.__rects is None:
            return False
        active = -1
        for i, rect in enumerate(self.__rects):
            if (event.x > rect[0] and event.x < rect[0] + rect[2] and
                    event.y > rect[1] and event.y < rect[1] + rect[3]):
                active = i
        if self.__active != active:
            self.__active = active
            if active == -1:
                self.set_tooltip_text('')
            else:
                self.set_tooltip_text(self.tag_list[active][0])

        return False

    def on_button_press(self, _dummy, event):
        """
        Called when a mouse button is clicked.
        @param _dummy: This widget.  Unused.
        @type _dummy: Gtk.Widget
        @param event: An event.
        @type event: Gdk.Event
        """
        if (event.button == 1 and
                event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and
                self.__active != -1):
            self.emit('clicked', self.__active)
