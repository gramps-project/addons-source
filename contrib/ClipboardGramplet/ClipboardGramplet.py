#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010  Doug Blank <doug.blank@gmail.com>
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

# $Id: QueryGramplet.py 195 2010-02-13 22:50:57Z dsblank $

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
from gen.plug import Gramplet
from DdTargets import DdTargets
import gtk
from ScratchPad import * #ScratchPadListView, ScratchPadListModel
import cPickle as pickle

def update_rows(model, path, iter):
    """
    Update the rows of a model.
    """
    model.row_changed(path, iter)

class ClipboardListView(ScratchPadListView):
    """
    Subclass ScratchPadListView to override remove_invalid_objects.
    """
    def remove_invalid_objects(self, dummy=None):
        """
        Does not delete rows, but merely updates to show availability.
        """
        model = self._widget.get_model()
        if model:
            for o in model:
                o[1] = o[1].__class__(self.dbstate, o[1]._pickle)
            model.foreach(update_rows)

class ClipboardGramplet(Gramplet):
    """
    A clipboard-like gramplet.
    """
    def init(self):
        self.object_list = ClipboardListView(self.dbstate, gtk.TreeView())
        self.otree = ScratchPadListModel()
        self.object_list.set_model(self.otree)
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.object_list._widget)
        self.object_list._widget.show()

    def on_load(self):
        i = 0
        while i < len(self.gui.data):
            data = self.gui.data[i]
            i += 1
            title = self.gui.data[i]
            i += 1
            value = self.gui.data[i]
            i += 1
            data = data.replace("\\n", chr(10))
            tuple_data = pickle.loads(data)
            drag_type = tuple_data[0]
            model = self.object_list._widget.get_model()
            class Selection(object):
                def __init__(self, data):
                    self.data = data
            class Context(object):
                targets = [drag_type]
                action = 1
            if drag_type == "TEXT":
                o_list = self.object_list.object_drag_data_received(
                    self.object_list._widget, # widget
                    Context(),       # drag type and action
                    0, 0,            # x, y
                    Selection(tuple_data[1]), # text
                    None,            # info (not used)
                    -1)              # time
            else:
                o_list = self.object_list.object_drag_data_received(
                    self.object_list._widget, # widget
                    Context(),       # drag type and action
                    0, 0,            # x, y
                    Selection(data), # pickled data
                    None,            # info (not used)
                    -1, title=title, value=value)              # time
            #model.append([drag_type, data, lambda: drag_type])

    def on_save(self):
        self.gui.data = [] # clear out old data: data, title, value
        model = self.object_list._widget.get_model()
        if model:
            for o in model:
                # [0]: obj_type
                # [1]: ScratchPad object, [1]._obj: pickle.dumps(data)
                # [2]: tooltip callback
                if isinstance(o[1], ScratchPadText):
                    # type, timestamp, text, preview
                    data = pickle.dumps(("TEXT", o[1]._obj))
                else:
                    # pickled: type, timestamp, handle, value
                    data = o[1].pack()
                self.gui.data.append(data.replace(chr(10), "\\n"))
                self.gui.data.append(o[1]._title)
                self.gui.data.append(o[1]._value)

