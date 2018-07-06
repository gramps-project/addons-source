#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009-2015 Nick Hall
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
EntryGrid widget.
"""

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk

#------------------------------------------------------------------------
#
# Indicator class
#
#------------------------------------------------------------------------
class Indicator(Gtk.DrawingArea):

    def __init__(self):
        Gtk.DrawingArea.__init__(self)
        self.connect('draw', self._draw)
        self.active = False
        self.set_size_request(5, -1)

    def set_active(self, value):
        self.active = value
        self.queue_draw()

    def _draw(self, widget, cr):

        # clip area to avoid extra work
        #cr.rectangle(event.area.x, event.area.y,
                     #event.area.width, event.area.height)
        #cr.clip()

        alloc = self.get_allocation()
        if self.active:
            cr.set_source_rgba(1, 0, 0, 1)
        else:
            cr.set_source_rgba(1, 0, 0, 0)
        cr.rectangle(0, 3, alloc.width, alloc.height-6)
        cr.fill()


#------------------------------------------------------------------------
#
# EntryGrid class
#
#------------------------------------------------------------------------
class EntryGrid(Gtk.Grid):

    def __init__(self, headings=None, tooltips=None, model=None, callback=None):
        Gtk.Grid.__init__(self)

        self.headings = headings
        self.tooltips = tooltips
        self.model = model
        self.widgets = []
        self.indicators = []
        self.selected = None
        self.callback = callback

    def set_model(self, model):
        self.model = model

        model.connect('row-inserted', self.row_inserted)
        model.connect('row-deleted', self.row_deleted)
        model.connect('rows-reordered', self.rows_reordered)
        self.sig_id = model.connect('row-changed', self.row_changed)

        if len(self.model) > 0:
            self.selected = model.get_iter((0,))

    def set_columns(self, columns, tooltips):
        self.headings = columns
        self.tooltips = tooltips

    def build(self):

        for child in self.get_children():
            self.remove(child)
            child.destroy()

        self.indicators = []
        self.widgets = []

        for column, heading in enumerate(self.headings):
            label = Gtk.Label(heading)
            label.set_alignment(0, 0.5)
            label.show()
            self.attach(label, column + 2, 0, 1, 1)

        for row in range(len(self.model)):
            image = Gtk.Image()
            image.set_from_icon_name('gtk-index', Gtk.IconSize.BUTTON)
            button = Gtk.Button()
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.add(image)
            button.connect('clicked', self.clicked, row)
            button.set_can_focus(False)
            button.show_all()
            self.attach(button, 0, row + 1, 1, 1)
            box = Indicator()
            box.show()
            if self.model.get_path(self.selected)[0] == row:
                box.set_active(True)
            self.attach(box, 1, row + 1, 1, 1)
            self.indicators.append(box)
            entry_row = []
            for column, value in enumerate(self.model[row]):
                if column == 0:
                    continue
                entry = Gtk.Entry()
                entry.set_width_chars(5)
                if value is not None:
                    entry.set_text(value)
                    set_size(entry)
                entry.set_tooltip_text(self.tooltips[column - 1])
                entry.connect('changed', self.changed, row, column)
                entry.connect('focus-in-event', self.got_focus, row)
                entry.show()
                self.attach(entry, column + 1, row + 1, 1, 1)
                entry_row.append(entry)
            self.widgets.append(entry_row)

    def get_selected(self):
        return self.selected

    def clicked(self, button, row):
        iter_ = self.model.get_iter((row,))
        self.callback(self.model, iter_)

    def got_focus(self, entry, event, row):
        for indicator in self.indicators:
            indicator.set_active(False)
        self.selected = self.model.get_iter((row,))
        self.indicators[row].set_active(True)

    def changed(self, entry, row, column):
        set_size(entry)
        self.model.handler_block(self.sig_id)
        self.model[row][column] = entry.get_text()
        self.model.handler_unblock(self.sig_id)

    def row_inserted(self, model, path, iter_):
        self.selected = model.get_iter((len(model) - 1,))
        self.build()

    def row_changed(self, model, path, iter_):
        for column in range(1, len(self.headings) + 1):
            value = model.get_value(iter_, column)
            if value is not None:
                self.widgets[path[0]][column - 1].set_text(value)

    def row_deleted(self, model, path):
        if len(model) > 0:
            self.selected = model.get_iter((0,))
        else:
            self.selected = None
        self.build()

    def rows_reordered(self, model, path, iter_, new_order):
        self.build()

    def clean_up(self):
        self.headings = None
        self.tooltips = None
        self.model = None
        self.widgets = None
        self.indicators = None
        self.selected = None
        self.callback = None

def set_size(entry):
    layout = entry.get_layout()
    width, height = layout.get_pixel_size()
    entry.set_size_request(width + 18, -1)
