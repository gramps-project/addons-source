#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016-2018 Sam Manzi
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
""" A tool to assist in clearing out extraneous custom 'types'
"""
#----------------------------------------------------------------------------
#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------
#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gui.plug import tool
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter
from gramps.gen.utils.db import navigation_label
from gramps.gui.utils import edit_object
from gramps.gui.dialog import QuestionDialog2
from gramps.gen.lib.grampstype import GrampsType
from gramps.gui.editors import EditNote
from gramps.gen.errors import WindowActiveError

from gramps.gen.lib.attrtype import AttributeType
from gramps.gen.lib.eventroletype import EventRoleType
from gramps.gen.lib.eventtype import EventType
from gramps.gen.lib.familyreltype import FamilyRelType
from gramps.gen.lib.childreftype import ChildRefType
from gramps.gen.lib.nameorigintype import NameOriginType
from gramps.gen.lib.nametype import NameType
from gramps.gen.lib.notetype import NoteType
from gramps.gen.lib.placetype import PlaceType
from gramps.gen.lib.repotype import RepositoryType
from gramps.gen.lib.srcattrtype import SrcAttributeType
from gramps.gen.lib.srcmediatype import SourceMediaType
from gramps.gen.lib.urltype import UrlType


#-------------------------------------------------------------------------
#
# constants
#
#-------------------------------------------------------------------------
#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


#-------------------------------------------------------------------------
#
# Type Cleanup
#
#-------------------------------------------------------------------------
class TypeCleanup(tool.Tool, ManagedWindow):
    t_table = [
        ("event_attributes", _("Event Attributes"), AttributeType, 'Event'),
        ("family_attributes", _("Family Attributes"), AttributeType, 'Family'),
        ("media_attributes", _("Media Attributes"), AttributeType, 'Media'),
        ("individual_attributes", _("Person Attributes"),
         AttributeType, 'Person'),
        ("event_role_names", _("Event Roles"), EventRoleType, None),
        ("event_names", _("Event Types"), EventType, None),
        ("family_rel_types", _("Family Relation Types"), FamilyRelType, None),
        ("child_ref_types", _("Child reference Types"), ChildRefType, None),
        ("origin_types", _("Name Origin Types"), NameOriginType, None),
        ("name_types", _("Name Types"), NameType, None),
        ("note_types", _("Note Types"), NoteType, None),
        ("place_types", _("Place Types"), PlaceType, None),
        ("repository_types", _("Repository Types"), RepositoryType, None),
        ("source_attributes", _("Source Attributes"), SrcAttributeType, None),
        ("source_media_types", _("Source Media Types"), SourceMediaType, None),
        ("url_types", _("URL Types"), UrlType, None), ]

    primary_objects = ['Person', 'Family', 'Event', 'Place', 'Source',
                       'Citation', 'Repository', 'Media', 'Note']
    primary_objects_pl = ['People', 'Families', 'Events', 'Places', 'Sources',
                          'Citations', 'Repositories', 'Media', 'Notes']

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate

        tool.Tool.__init__(self, dbstate, options_class, name)

        self.window_name = _('Types Cleanup Tool')
        ManagedWindow.__init__(self, uistate, [], self.__class__)

        self.db = dbstate.db
        self.dbstate = dbstate
        self.types_dict = {obj : {} for (_attr, _name, obj, _srcobj) in
                           self.t_table}

        window = Gtk.Window()
        window.set_size_request(600, 500)
        window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_window(window, None, self.window_name)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        window.add(vbox)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, expand=True)
        vbox.add(hbox)
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        hbox.pack_start(scrolled_window, True, True, 5)
        scrolled_window_r = Gtk.ScrolledWindow()
        scrolled_window_r.set_policy(Gtk.PolicyType.AUTOMATIC,
                                     Gtk.PolicyType.AUTOMATIC)
        hbox.pack_start(scrolled_window_r, True, True, 5)
        bbox = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(bbox, False, False, 5)
        self.del_btn = Gtk.Button(label=_('Remove'))
        self.del_btn.set_tooltip_text(_('Remove the selected type'))
        self.del_btn.connect('clicked', self.delete)
        self.del_btn.set_sensitive(False)
        bbox.add(self.del_btn)
        close_btn = Gtk.Button(label=_('Close'))
        close_btn.set_tooltip_text(_('Close the Type Cleanup Tool'))
        close_btn.connect('clicked', self.close)
        bbox.add(close_btn)
        view = Gtk.TreeView()
        column = Gtk.TreeViewColumn(_('Types'))
        view.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 0)
        column.set_sort_column_id(0)
        column.set_sort_indicator(True)
        self.model = Gtk.TreeStore(str, int, int)
        self.model_load()
        view.set_model(self.model)
        view.show()
        selection = view.get_selection()
        selection.connect('changed', self.selection_changed)
        scrolled_window.add(view)
        #window.show_all()

        view = Gtk.TreeView()
        column = Gtk.TreeViewColumn(_("Type"))
        view.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 0)
        column.set_sort_column_id(0)
        column.set_sort_indicator(True)
        column = Gtk.TreeViewColumn(_("References"))
        view.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 1)
        column.set_sort_column_id(1)
        column.set_sort_indicator(True)
        self.model_r = Gtk.ListStore(str, str, str, str)
        view.set_model(self.model_r)
        view.show()
        view.connect('row_activated', self.button_press)
        scrolled_window_r.add(view)

        self.show()

    def build_menu_names(self, obj):
        """Override :class:`.ManagedWindow` method."""
        return (_('Type Cleanup Tool'), None)

    def model_load(self):
        """ populate the tree with types """
        r_indx = 0
        for (attr, name, _obj, _srcobj) in self.t_table:
            row = (name, 0, 99)
            iter_ = self.model.append(None, row)
            types = getattr(self.db, attr, None)
            if types is None:
                continue
            for indx, cust_type in enumerate(types):
                row = (cust_type, indx, r_indx)
                self.model.append(iter_, row)
                self.types_dict[_obj][cust_type] = []
            r_indx += 1
        progress = ProgressMeter(self.window_name, can_cancel=False,
                                 parent=self.window)
        total = 0
        for obj_type in self.primary_objects_pl:
            total += self.db.method('get_number_of_%s', obj_type)()

        progress.set_pass(_("Reading database..."), total)
        for obj_type in self.primary_objects:
            for hndl in self.db.method('get_%s_handles', obj_type)():
                obj = self.db.method('get_%s_from_handle', obj_type)(hndl)
                self.do_recurse(obj, obj_type, hndl)
                progress.step()
        progress.close()

    def do_recurse(self, obj, obj_class, hndl):
        if isinstance(obj, list):
            for item in obj:
                self.do_recurse(item, obj_class, hndl)
        elif hasattr(obj, '__dict__'):
            for item in obj.__dict__.values():
                self.do_recurse(item, obj_class, hndl)
        if isinstance(obj, GrampsType):
            if(obj.__class__ in self.types_dict and
               obj.string in self.types_dict[obj.__class__]):
                self.types_dict[obj.__class__][obj.string].append(
                    (obj_class, hndl))

    def button_press(self, _view, path, _column):
        """
        Called when a right tree row is activated.
        """
        iter_ = self.model_r.get_iter(path)
        (objclass, handle) = (self.model_r.get_value(iter_, 3),
                              self.model_r.get_value(iter_, 2))

        if objclass == 'Note':
            try:
                note = self.db.get_note_from_handle(handle)
                EditNote(self.dbstate, self.uistate, [], note)
            except WindowActiveError:
                pass
        else:
            edit_object(self.dbstate, self.uistate, objclass, handle)

    def selection_changed(self, selection):
        """
        Called when selection changed within the treeview
        """
        model, iter_ = selection.get_selected()
        if not iter_:
            return
        self.iter_ = iter_
        value = model.get_value(iter_, 0)
        self.name = value
        self.r_indx = model.get_value(iter_, 2)
        self.del_btn.set_sensitive(self.r_indx != 99)
        self.model_r.clear()
        if self.r_indx == 99:
            return
        refs = self.types_dict[self.t_table[self.r_indx][2]][value]
        for (obj_type, hndl) in refs:
            if(self.t_table[self.r_indx][3] and
               obj_type != self.t_table[self.r_indx][3]):
                return
            name = navigation_label(self.db, obj_type, hndl)[0]
            self.model_r.append((_(obj_type), name, hndl, obj_type))

    def delete(self, _button):
        """ process the delete button """
        if self.r_indx == 99:
            return
        (attr, _name, _obj, _srcobj) = self.t_table[self.r_indx]
        refs = self.types_dict[self.t_table[self.r_indx][2]][self.name]
        if refs:
            warn_dialog = QuestionDialog2(
                self.window_name,
                _("Removing this custom type will eliminate it from the type "
                  "selection drop down lists.  However, it will not remove "
                  "it from the referenced items in the database."),
                _('_Remove'), _('_Stop'),
                parent=self.window)
            if not warn_dialog.run():
                return False

        types = getattr(self.db, attr, None)
        types.remove(self.name)
        self.model.remove(self.iter_)


#------------------------------------------------------------------------
#
# Type Cleanup Options
#
#------------------------------------------------------------------------
class TypeCleanupOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
