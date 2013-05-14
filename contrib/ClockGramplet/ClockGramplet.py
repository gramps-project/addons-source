# Clock Example by Ralph Glass
# http://ralph-glass.homepage.t-online.de/clock/readme.html

from gi.repository import PangoCairo
from gi.repository import GObject
from gi.repository import Gtk
import math
import time

TEXT = 'cairo'
BORDER_WIDTH = 10

class ClockWidget(Gtk.DrawingArea):

    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self.connect("draw", self.on_draw)
        self.timer = GObject.timeout_add(1000, self.tick)
                                           
    def on_draw(self, widget, cr):
        
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(self.get_style().font_desc)
        layout.set_markup(TEXT, -1)

        fontw, fonth = layout.get_pixel_size()
        xmin = fontw + BORDER_WIDTH
        ymin = fonth + BORDER_WIDTH
        self.set_size_request(xmin, ymin)

        # time 

        hours = time.localtime().tm_hour
        minutes = time.localtime().tm_min
        secs = time.localtime().tm_sec
        second_arc = (2*math.pi / 60) * secs
        minute_arc = (2*math.pi / 60) * minutes
        if hours > 12:
            hours = hours - 12       
        hour_arc = (2*math.pi / 12) * hours + minute_arc / 12
       
        # clock background

        alloc = self.get_allocation()
        x = alloc.x
        y = alloc.y
        w = alloc.width
        h = alloc.height
        cr.set_source_rgba(1, 0.2, 0.2, 0.6)
        cr.arc(w/2, h/2, min(w,h)/2 - 8 , 0, 2 * 3.14) 
        cr.fill()
        cr.stroke()

        # center arc

        cr.set_source_rgb(0, 0, 0)
        cr.arc ( w/2, h/2, (min(w,h)/2 -20) / 5, 0, 2 * math.pi)
        cr.fill()
        cr.line_to(w/2,h/2)
        cr.stroke()

        # pointer hour

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
 
        # pointer second

        cr.set_source_rgba(0.5, 0.5, 0.5, 0.5) 
        cr.set_line_width ((min(w,h)/2 -20)/6 * 0.4)
        cr.move_to(w/2,h/2)
        cr.line_to(w/2 + (min(w,h)/2 -20) * math.cos(second_arc - math.pi/2), 
            h/2 + (min(w,h)/2 -20) * math.sin(second_arc - math.pi/2))
        cr.stroke()
 
        # pango layout 
        
        cr.move_to((w - fontw - 4), (h - fonth ))
        PangoCairo.show_layout(cr, layout)

    def tick(self):
        self.queue_draw()
        return True

# Clock Integrated with Gramplets
# (c) 2009, Doug Blank

from gramps.gen.plug import Gramplet

class ClockGramplet(Gramplet):
    def init(self):
        self.gui.clock = ClockWidget()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.clock)
        self.gui.clock.show()

