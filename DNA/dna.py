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
DNA Gramplet

This Gramplet shows a DNA segment map.
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

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gen.plug import Gramplet
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

class DNAGramplet(Gramplet):

    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add(self.gui.WIDGET)
        self.gui.WIDGET.show()

    def db_changed(self):
        self.connect(self.dbstate.db, 'person-add', self.update)
        self.connect(self.dbstate.db, 'person-delete', self.update)
        self.connect(self.dbstate.db, 'person-update', self.update)

    def build_gui(self):
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox.set_margin_start(6)
        self.vbox.set_margin_end(6)
        self.vbox.set_margin_top(6)
        self.vbox.set_margin_bottom(6)
        self.vbox.set_spacing(12)
        return self.vbox

    def main(self):
        for widget in self.vbox.get_children():
            self.vbox.remove(widget)

        active_handle = self.get_active('Person')
        if active_handle:
            active = self.dbstate.db.get_person_from_handle(active_handle)

            for assoc in active.get_person_ref_list():
                if assoc.get_relation() == 'DNA':
                    for handle in assoc.get_note_list():
                        note = self.dbstate.db.get_note_from_handle(handle)
                        data = get_segment_data(note)
                        self.create_segmap(data)

    def create_segmap(self, data):
        """
        Create a segment map based on a list of segments.
        """
        segmap = SegmentMap()
        segmap.set_title(_('DNA Segment Map'))
        segmap.set_axis(_('Chr'))
        segmap.set_segments(data)
        #segmap.connect('clicked', self.on_segment_clicked, handle_data)
        segmap.show()
        self.vbox.pack_start(segmap, True, True, 0)

    def on_segment_clicked(self, _dummy, value, handle_data):
        """
        Called when a segment is double-clicked.
        """
        print ('clicked')

def get_segment_data(note):
    segments = []
    for line in note.get().split('\n'):
        field = line.split(',')
        chromo = field[0]
        start = get_base(field[1])
        stop = get_base(field[2])
        side = field[3]
        cms = float(field[4])
        segments.append([chromo, start, stop, side, cms])
    return segments

def get_base(num):
    try:
        return int(num)
    except:
        try:
            return int(float(num) * 1000000)
        except:
            return 0


#-------------------------------------------------------------------------
#
# SegmentMap class
#
#-------------------------------------------------------------------------

class SegmentMap(Gtk.DrawingArea):
    """
    A segment map of DNA data.
    """

    __gsignals__ = {'clicked': (GObject.SignalFlags.RUN_FIRST, None, (int,))}

    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect('motion-notify-event', self.on_pointer_motion)
        self.connect('button-press-event', self.on_button_press)

        self.title = ''
        self.axis = ''
        self.grid_lines = True
        self.__rects = None
        self.__active = -1

        self.chromosomes = (
            ('1', 248956422),
            ('2', 242193529),
            ('3', 198295559),
            ('4', 190214555),
            ('5', 181538259),
            ('6', 170805979),
            ('7', 159345973),
            ('8', 145138636),
            ('9', 138394717),
            ('10', 133797422),
            ('11', 135086622),
            ('12', 133275309),
            ('13', 114364328),
            ('14', 107043718),
            ('15', 101991189),
            ('16', 90338345),
            ('17', 83257441),
            ('18', 80373285),
            ('19', 58617616),
            ('20', 64444167),
            ('21', 46709983),
            ('22', 50818468),
            ('X', 156040895))

        self.labels = [chromo[0] for chromo in self.chromosomes]

    def set_title(self, title):
        """
        Set the main chart title.
        @param title: The main chart title.
        @type title: str
        """
        self.title = title

    def set_axis(self, axis):
        """
        Set the axis title.
        @param title: The axis title.
        @type title: str
        """
        self.axis = axis

    def set_grid_lines(self, grid_lines):
        """
        Specify if grid lines should be displayed.
        @param grid_lines: True if grid lines should be displayed.
        @type grid_lines: bool
        """
        self.grid_lines = grid_lines

    def set_segments(self, segments):
        """
        Set the segment data.
        @param data: A list of segments.
        @type data: list
        """
        self.segments = segments

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

        # Title
        layout = self.create_pango_layout(self.title)
        width, height = layout.get_pixel_size()
        cr.move_to((allocation.width - width) / 2, 0)
        PangoCairo.show_layout(cr, layout)

        offset = height + 5

        chr_height = 10
        spacing = 2

        # Chromosome labels
        label_width = 0
        for i, label in enumerate(self.labels):
            layout = self.create_pango_layout(label)
            width, height = layout.get_pixel_size()
            if width > label_width:
                label_width = width
            cr.move_to(0, i * 2 * (chr_height + spacing) + offset)
            PangoCairo.show_layout(cr, layout)

        layout = self.create_pango_layout(self.axis)
        width, height = layout.get_pixel_size()
        if width > label_width:
            label_width = width
        label_width += 5
        cr.move_to((label_width - width) / 2, 0)
        PangoCairo.show_layout(cr, layout)

        chart_width = allocation.width - label_width

        # Border
        cr.move_to(0, offset)
        cr.line_to(allocation.width, offset)
        cr.stroke()

        bottom = len(self.chromosomes) * 2 * (chr_height + spacing) + offset
        cr.move_to(0, bottom)
        cr.line_to(allocation.width, bottom)
        cr.stroke()

        cr.move_to(label_width, 0)
        cr.line_to(label_width, bottom)
        cr.stroke()

        cr.move_to(allocation.width, 0)
        cr.line_to(allocation.width, bottom)
        cr.stroke()

        # Ticks and grid lines
        tick_step, maximum = 50000000, 250000000
        count = 0
        while count <= maximum:
            # draw tick
            tick_pos = label_width + chart_width * count / maximum
            cr.move_to(tick_pos, bottom)
            cr.line_to(tick_pos, bottom + 5)
            cr.stroke()
            # draw grid line
            if self.grid_lines:
                cr.set_dash([1, 2])
                cr.move_to(tick_pos, bottom)
                cr.line_to(tick_pos, (2 * spacing) + offset)
                cr.stroke()
                cr.set_dash([])
            #layout = self.create_pango_layout('%d' % count)
            #width, height = layout.get_pixel_size()
            #cr.move_to(tick_pos - (width / 2), bottom + 5)
            #PangoCairo.show_layout(cr, layout)
            count += tick_step

        offset += spacing

        # Chromosomes
        cr.set_line_width(1)
        for i, chromo in enumerate(self.chromosomes):
            cr.rectangle(label_width,
                         i * 2 * (chr_height + spacing) + offset,
                         chart_width * chromo[1] / maximum,
                         chr_height)
            cr.rectangle(label_width,
                         i * 2 * (chr_height + spacing) + offset + chr_height,
                         chart_width * chromo[1] / maximum,
                         chr_height)

            cr.set_source_rgba(0.95, 0.95, 0.95, 1)
            cr.fill_preserve()
            cr.set_source_rgba(*fg_color)
            cr.stroke()

        # Segments
        cr.set_line_width(1)
        self.__rects = []
        for chromo, start, stop, side, cms in self.segments:
            i = self.labels.index(chromo)
            chr_offset = i * 2 * (chr_height + spacing) + offset
            if side == 'M':
                chr_offset += chr_height
            cr.rectangle(label_width + chart_width * start / maximum,
                         chr_offset,
                         chart_width * (stop-start) / maximum,
                         chr_height)
            self.__rects.append((label_width + chart_width * start / maximum,
                         chr_offset,
                         chart_width * (stop-start) / maximum,
                         chr_height))

            cr.set_source_rgba(0.5, 0.5, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgba(*fg_color)
            cr.stroke()

        self.set_size_request(-1, bottom + height + 5)

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
                self.set_tooltip_text('%s cMs' % self.segments[active][4])

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
