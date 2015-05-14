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

# $Id: $

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
import cPickle as pickle

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext
from gramps.gen.plug import Gramplet
from gramps.gui.ddtargets import DdTargets
from gramps.gui.clipboard import (MultiTreeView, ClipboardListModel, 
                           ClipboardListView, ClipText)

#-------------------------------------------------------------------------
#
# Local Functions
#
#-------------------------------------------------------------------------
def escape(data):
    """
    Remove newlines from text.
    """
    data = data.replace(chr(10), "\\n")
    return data

def unescape(data):
    """
    Replace newlines with \n text.
    """
    return data.replace("\\n", chr(10))

#-------------------------------------------------------------------------
#
# ClipboardListView2 class
#
#-------------------------------------------------------------------------
class ClipboardListView2(ClipboardListView):
    """
    Subclass ClipboardListView to override refresh_objects.
    """
    def refresh_objects(self, dummy=None):
        def update_rows(model, path, iter, user_data):
            """
            Update the rows of a model.
            """
            model.row_changed(path, iter)
        # force refresh of each row:
        model = self._widget.get_model()
        if model:
            model.foreach(update_rows, None)

#-------------------------------------------------------------------------
#
# ClipboardGramplet class
#
#-------------------------------------------------------------------------
class ClipboardGramplet(Gramplet):
    """
    A clipboard-like gramplet.
    """
    def init(self):
        self.object_list = ClipboardListView2(self.dbstate, 
                 MultiTreeView(self.dbstate, self.uistate, 
                 lambda: _("Clipboard Gramplet: %s") % self.gui.get_title()))
        self.otree = ClipboardListModel()
        self.object_list.set_model(self.otree)
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.object_list._widget)
        self.object_list._widget.show()

    def on_load(self):
        if len(self.gui.data) % 5 != 0:
            print "Invalid Clipboard Gramplet data on load; skipping..."
            return
        i = 0
        while i < len(self.gui.data):
            data = unescape(self.gui.data[i])
            i += 1
            title = unescape(self.gui.data[i])
            i += 1
            value = unescape(self.gui.data[i])
            i += 1
            dbid = unescape(self.gui.data[i])
            i += 1
            dbname = unescape(self.gui.data[i])
            i += 1
            try:
                tuple_data = pickle.loads(data)
            except:
                tuple_data = ("TEXT", data)
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
                    -1, title=title, value=value, dbid=dbid, 
                    dbname=dbname) # time, data

    def on_save(self):
        self.gui.data = [] # clear out old data: data, title, value
        model = self.object_list._widget.get_model()
        if model:
            for o in model:
                # [0]: obj_type
                # [1]: Clipboard object, [1]._obj: pickle.dumps(data)
                # [2]: tooltip callback
                # [5]: dbid
                # [6]: dbname
                if isinstance(o[1], ClipText):
                    # type, timestamp, text, preview
                    data = pickle.dumps(("TEXT", o[1]._obj))
                else:
                    # pickled: type, timestamp, handle, value
                    data = o[1]._pickle
                self.gui.data.append(escape(data))
                self.gui.data.append(escape(o[1]._title))
                self.gui.data.append(escape(o[1]._value))
                self.gui.data.append(escape(o[1]._dbid))
                self.gui.data.append(escape(o[1]._dbname))
