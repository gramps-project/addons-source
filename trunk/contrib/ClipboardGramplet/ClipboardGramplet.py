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
import gtk
import time
import cPickle as pickle

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
from gen.plug import Gramplet
from DdTargets import DdTargets
from ScratchPad import * 
import Errors

#-------------------------------------------------------------------------
#
# Local Functions
#
#-------------------------------------------------------------------------
def update_rows(model, path, iter):
    """
    Update the rows of a model.
    """
    model.row_changed(path, iter)

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
# MultiTreeView class
#
#-------------------------------------------------------------------------
class MultiTreeView(gtk.TreeView):
    '''
    TreeView that captures mouse events to make drag and drop work properly
    '''
    def __init__(self, dbstate, uistate):
        self.dbstate = dbstate
        self.uistate = uistate
        super(MultiTreeView, self).__init__()
        self.connect('button_press_event', self.on_button_press)
        self.connect('button_release_event', self.on_button_release)
        self.connect('key_press_event', self.key_press_event)
        self.defer_select = False

    def key_press_event(self, widget, event):
        if event.type == gtk.gdk.KEY_PRESS:
            if event.keyval == gtk.keysyms.Delete:
                model, paths = self.get_selection().get_selected_rows()
                # reverse, to delete from the end
                paths.sort(key=lambda x:-x[0])
                for path in paths:
                    try:
                        node = model.get_iter(path)
                    except:
                        node = None
                    if node:
                        model.remove(node)
                return True

    def on_button_press(self, widget, event):
        # Here we intercept mouse clicks on selected items so that we can
        # drag multiple items without the click selecting only one
        target = self.get_path_at_pos(int(event.x), int(event.y))
        if event.button == 3: # right mouse
            selection = widget.get_selection()
            store, paths = selection.get_selected_rows()
            tpath = paths[0] if len(paths) > 0 else None
            node = store.get_iter(tpath) if tpath else None
            o = None
            if node:
                o = store.get_value(node, 1)
            popup = gtk.Menu()
            # ---------------------------
            if o:
                objclass, handle = o._objclass, o._handle
            else:
                objclass, handle = None, None
            if objclass in ['Person', 'Event', 'Media', 'Source',
                            'Repository', 'Family', 'Note', 'Place']:
                menu_item = gtk.MenuItem(_("See %s details") % objclass)
                menu_item.connect("activate", 
                   lambda widget: self.edit_obj(objclass, handle))
                popup.append(menu_item)
                menu_item.show()
                # ---------------------------
                menu_item = gtk.MenuItem(_("Make Active %s") % objclass)
                menu_item.connect("activate", 
                      lambda widget: self.uistate.set_active(handle, objclass))
                popup.append(menu_item)
                menu_item.show()
                # ---------------------------
                gids = set()
                for path in paths:
                    node = store.get_iter(path)
                    if node:
                        o = store.get_value(node, 1)
                        if o._objclass == objclass:
                            my_handle = o._handle
                            obj = self.dbstate.db.get_table_metadata(objclass)["handle_func"](my_handle)
                            if obj:
                                gids.add(obj.gramps_id)
                menu_item = gtk.MenuItem(_("Create Filter from selected %s...") % objclass)
                menu_item.connect("activate", 
                      lambda widget: self.make_filter(objclass, gids))
                popup.append(menu_item)
                menu_item.show()
            # Show the popup menu:
            popup.popup(None, None, None, 3, event.time)
            return True        
        elif event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
            model, paths = self.get_selection().get_selected_rows()
            for path in paths:
                node = model.get_iter(path)
                if node is not None:
                    o = model.get_value(node,1)
                    objclass = o._objclass
                    handle = o._handle
                    self.edit_obj(objclass, handle)
            return True
        # otherwise:
        if (target 
            and event.type == gtk.gdk.BUTTON_PRESS
            and not (event.state & (gtk.gdk.CONTROL_MASK|gtk.gdk.SHIFT_MASK))
            and self.get_selection().path_is_selected(target[0])):
            # disable selection
            self.get_selection().set_select_function(lambda *ignore: False)
            self.defer_select = target[0]
			
    def on_button_release(self, widget, event):
        # re-enable selection
        self.get_selection().set_select_function(lambda *ignore: True)
        
        target = self.get_path_at_pos(int(event.x), int(event.y))	
        if (self.defer_select and target 
            and self.defer_select == target[0]
            and not (event.x==0 and event.y==0)): # certain drag and drop
            self.set_cursor(target[0], target[1], False)
            
        self.defer_select=False

    def edit_obj(self, objclass, handle):
        from gui.editors import (EditPerson, EditEvent, EditFamily, EditSource,
                                 EditPlace, EditRepository, EditNote, EditMedia)
        if objclass == 'Person':
            person = self.dbstate.db.get_person_from_handle(handle)
            if person:
                try:
                    EditPerson(self.dbstate, 
                               self.uistate, [], person)
                except Errors.WindowActiveError:
                    pass
        elif objclass == 'Event':
            event = self.dbstate.db.get_event_from_handle(handle)
            if event:
                try:
                    EditEvent(self.dbstate, 
                              self.uistate, [], event)
                except Errors.WindowActiveError:
                    pass
        elif objclass == 'Family':
            ref = self.dbstate.db.get_family_from_handle(handle)
            if ref:
                try:
                    EditFamily(self.dbstate, 
                               self.uistate, [], ref)
                except Errors.WindowActiveError:
                    pass
        elif objclass == 'Source':
            ref = self.dbstate.db.get_source_from_handle(handle)
            if ref:
                try:
                    EditSource(self.dbstate, 
                               self.uistate, [], ref)
                except Errors.WindowActiveError:
                    pass
        elif objclass == 'Place':
            ref = self.dbstate.db.get_place_from_handle(handle)
            if ref:
                try:
                    EditPlace(self.dbstate, 
                               self.uistate, [], ref)
                except Errors.WindowActiveError:
                    pass
        elif objclass == 'Repository':
            ref = self.dbstate.db.get_repository_from_handle(handle)
            if ref:
                try:
                    EditRepository(self.dbstate, 
                               self.uistate, [], ref)
                except Errors.WindowActiveError:
                    pass
        elif objclass == 'Note':
            ref = self.dbstate.db.get_note_from_handle(handle)
            if ref:
                try:
                    EditNote(self.dbstate, 
                             self.uistate, [], ref)
                except Errors.WindowActiveError:
                    pass
        elif objclass in ['Media', 'MediaObject']:
            ref = self.dbstate.db.get_object_from_handle(handle)
            if ref:
                try:
                    EditMedia(self.dbstate, 
                              self.uistate, [], ref)
                except Errors.WindowActiveError:
                    pass

    def make_filter(self, objclass, gramps_ids):
        import Filters 
        from gui.filtereditor import EditFilter
        import const

        FilterClass = Filters.GenericFilterFactory(objclass)
        rule = getattr(getattr(Filters.Rules, objclass),'RegExpIdOf')
        filter = FilterClass()
        filter.set_name(_("Filter %s from Clipboard") % objclass)
        struct_time = time.localtime()
        filter.set_comment( _("Created on %4d/%02d/%02d") % 
            (struct_time.tm_year, struct_time.tm_mon, struct_time.tm_mday))
        re = "|".join(["^%s$" % gid for gid in gramps_ids])
        filter.add_rule(rule([re]))

        filterdb = Filters.FilterList(const.CUSTOM_FILTERS)
        filterdb.load()
        EditFilter(objclass, self.dbstate, self.uistate, [],
                   filter, filterdb,
                   lambda : self.edit_filter_save(filterdb, objclass))

    def edit_filter_save(self, filterdb, objclass):
        """
        If a filter changed, save them all. Reloads, and also calls callback.
        """
        from Filters import reload_custom_filters
        filterdb.save()
        reload_custom_filters()
        self.uistate.emit('filters-changed', (objclass,))

#-------------------------------------------------------------------------
#
# ClipboardListView class
#
#-------------------------------------------------------------------------
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
                o[3] = o[1]._type
                o[4] = o[1]._value
            model.foreach(update_rows)

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
        self.object_list = ClipboardListView(self.dbstate, 
                                             MultiTreeView(self.dbstate, self.uistate))
        self.otree = ScratchPadListModel()
        self.object_list.set_model(self.otree)
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.object_list._widget)
        self.object_list._widget.show()

    def on_load(self):
        i = 0
        while i < len(self.gui.data):
            data = unescape(self.gui.data[i])
            i += 1
            title = unescape(self.gui.data[i])
            i += 1
            value = unescape(self.gui.data[i])
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
                    -1, title=title, value=value)              # time

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
                self.gui.data.append(escape(data))
                self.gui.data.append(escape(o[1]._title))
                self.gui.data.append(escape(o[1]._value))

