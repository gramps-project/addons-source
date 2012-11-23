# Clock Example by Ralph Glass
# http://ralph-glass.homepage.t-online.de/clock/readme.html

#import pygtk
#pygtk.require('2.0')

from gi.repository import GObject
import pango
import math
import time
from gi.repository import Gtk
from gi.repository import Gdk
try:
    import cairo
except ImportError:
    pass

#if gtk.pygtk_version < (2,3,93):
    #raise Exception("PyGtk 2.3.93 or later required")

from gramps.gen.utils.trans import get_addon_translator

_ = get_addon_translator(__file__).gettext
TEXT = 'cairo'
BORDER_WIDTH = 10

def progress_timeout(object):
    if object.window:
        x, y, w, h = object.allocation
        object.window.invalidate_rect((0,0,w,h),False)
    return True # keep ticking!

class ClockWidget(Gtk.Widget):
    __gsignals__ = { 'realize': 'override',
                     'expose-event' : 'override',
                     'size-allocate': 'override',
                     'size-request': 'override',}

    def __init__(self):
        Gtk.Widget.__init__(self)
        self.draw_gc = None
        self.layout = self.create_pango_layout(TEXT)
        self.layout.set_font_description(pango.FontDescription("sans 8"))
        self.timer = GObject.timeout_add (1000, progress_timeout, self)
                                           
    def do_realize(self):
        self.set_flags(self.flags() | Gtk.REALIZED)
        self.window = Gdk.Window(self.get_parent_window(),
                                 width=self.allocation.width,
                                 height=self.allocation.height,
                                 window_type=Gdk.WINDOW_CHILD,
                                 wclass=Gdk.INPUT_OUTPUT,
                                 event_mask=self.get_events() | Gdk.EXPOSURE_MASK)
        if not hasattr(self.window, "cairo_create"):
            self.draw_gc = Gdk.GC(self.window,
                                  line_width=5,
                                  line_style=Gdk.SOLID,
                                  join_style=Gdk.JOIN_ROUND)

	self.window.set_user_data(self)
        self.style.attach(self.window)
        self.style.set_background(self.window, Gtk.STATE_NORMAL)
        self.window.move_resize(*self.allocation)

    def do_size_request(self, requisition):
	width, height = self.layout.get_size()
	requisition.width = (width // pango.SCALE + BORDER_WIDTH*4)* 1.45
	requisition.height = (3 * height // pango.SCALE + BORDER_WIDTH*4) * 1.2

    def do_size_allocate(self, allocation):
        self.allocation = allocation
        if self.flags() & Gtk.REALIZED:
            self.window.move_resize(*allocation)

    def _expose_gdk(self, event):
        x, y, w, h = self.allocation
        self.layout = self.create_pango_layout('no cairo')
        fontw, fonth = self.layout.get_pixel_size()
        self.style.paint_layout(self.window, self.state, False,
                                event.area, self, "label",
                                (w - fontw) / 2, (h - fonth) / 2,
                                self.layout)

    def _expose_cairo(self, event, cr):
        
        # time 

        hours = time.localtime().tm_hour
        minutes = time.localtime().tm_min
        secs = time.localtime().tm_sec
        minute_arc = (2*math.pi / 60) * minutes
        if hours > 12:
            hours = hours - 12       
        hour_arc = (2*math.pi / 12) * hours + minute_arc / 12
       
        # clock background

        x, y, w, h = self.allocation
        cr.set_source_rgba(1, 0.2, 0.2, 0.6)
        cr.arc(w/2, h/2, min(w,h)/2 - 8 , 0, 2 * 3.14) 
        cr.fill()
        cr.stroke()

        # center arc

        cr.set_source_color(self.style.fg[self.state])
        cr.arc ( w/2, h/2, (min(w,h)/2 -20) / 5, 0, 2 * math.pi)
        cr.fill()
        cr.line_to(w/2,h/2)
        cr.stroke()

        # pointer hour

        cr.set_source_color(self.style.fg[self.state])
        cr.set_source_rgba(0.5, 0.5, 0.5, 0.5) 
        cr.set_line_width ((min(w,h)/2 -20)/6 )
        cr.move_to(w/2,h/2)
        cr.line_to(w/2 + (min(w,h)/2 -20) * 0.6 * math.cos(hour_arc - math.pi/2),
            h/2 + (min(w,h)/2 -20) * 0.6 * math.sin(hour_arc - math.pi/2))
        cr.stroke()

        # pointer minute

        cr.set_source_rgba(0.5, 0.5, 0.5, 0.5) 
        cr.set_line_width ((min(w,h)/2 -20)/6 * 0.8)
        cr.move_to(w/2,h/2)
        cr.line_to(w/2 + (min(w,h)/2 -20) * 0.8 * math.cos(minute_arc - math.pi/2), 
            h/2 + (min(w,h)/2 -20) * 0.8 * math.sin(minute_arc - math.pi/2))
        cr.stroke()
 
        # pango layout 
        
        fontw, fonth = self.layout.get_pixel_size()
        cr.move_to((w - fontw - 4), (h - fonth ))
        cr.update_layout(self.layout)
        cr.show_layout(self.layout)
        
    def do_expose_event(self, event):
        self.chain(event)
        try:
            cr = self.window.cairo_create()
        except AttributeError:
            return self._expose_gdk(event)
        return self._expose_cairo(event, cr)

# Clock Integrated with Gramplets
# (c) 2009, Doug Blank

from gen.plug import Gramplet

class ClockGramplet(Gramplet):
    def init(self):
        self.gui.clock = ClockWidget()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.clock)
        self.gui.clock.show()

