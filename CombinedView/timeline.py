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
Timeline widget

This widget displays a segment of a timeline.
"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import math

#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import PangoCairo

NODE_SIZE = 10


#-------------------------------------------------------------------------
#
# SegmentMap class
#
#-------------------------------------------------------------------------

class Timeline(Gtk.DrawingArea):
    """
    A segment of a timeline.
    """

    __gsignals__ = {'clicked': (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, position='middle'):
        Gtk.DrawingArea.__init__(self)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect('motion-notify-event', self.on_pointer_motion)
        self.connect('button-press-event', self.on_button_press)

        self.position = position
        self.__active = False

    def do_draw(self, cr):
        """
        A custom draw method for this widget.
        @param cr: A cairo context.
        @type cr: cairo.Context
        """
        allocation = self.get_allocation()
        context = self.get_style_context()
        fg_color = context.get_color(context.get_state())
        cr.set_source_rgba(*fg_color)
        cr.set_line_width(5)

        if self.position != 'start':
            cr.move_to(allocation.width / 2, 0)
            cr.line_to(allocation.width / 2, allocation.height / 2)
            cr.stroke()

        if self.position != 'end':
            cr.move_to(allocation.width / 2, allocation.height / 2)
            cr.line_to(allocation.width / 2, allocation.height)
            cr.stroke()

        cr.translate(allocation.width / 2, allocation.height / 2)
        cr.arc(0, 0, NODE_SIZE, 0, 2 * math.pi)
        cr.stroke_preserve()
        if self.__active:
            cr.set_source_rgba(0.7, 0.7, 1, 1)
        else:
            cr.set_source_rgba(0.5, 0.5, 1, 1)
        cr.fill()

        self.set_size_request(100, 50)

    def on_pointer_motion(self, _dummy, event):
        """
        Called when the pointer is moved.
        @param _dummy: This widget.  Unused.
        @type _dummy: Gtk.Widget
        @param event: An event.
        @type event: Gdk.Event
        """
        allocation = self.get_allocation()
        x = allocation.width / 2
        y = allocation.height / 2
        if (event.x > (x - NODE_SIZE) and event.x < (x + NODE_SIZE) and
            event.y > (y - NODE_SIZE) and event.y < (y + NODE_SIZE)):
            active = True
        else:
            active = False

        if self.__active != active:
            self.__active = active
            self.queue_draw()

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
                self.__active):
            self.emit('clicked')
