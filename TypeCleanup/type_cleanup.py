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
""" A tool to assist in clearing out extraneous custom 'types'.  Can delete
a custom type, or rename it to another value.

Changes to the primary db objects can be undone.
"""
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
from gramps.gen.db import DbTxn
from gramps.gen.errors import WindowActiveError
from gramps.gen.lib.grampstype import GrampsType
from gramps.gen.utils.db import navigation_label
from gramps.gui.dialog import QuestionDialog2
from gramps.gui.display import display_url
from gramps.gui.editors import EditNote
from gramps.gui.plug import tool
from gramps.gui.managedwindow import ManagedWindow
from gramps.gui.utils import ProgressMeter
from gramps.gui.utils import edit_object
from gramps.gui.widgets import MonitoredDataType

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
WIKI_PAGE = ('https://gramps-project.org/wiki/index.php/Types_Cleanup_Tool')


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
        # Create a dict of dicts of lists.  The first level dict has primary
        # objects as keys.  The second level dict has type names for keys,
        # and lists of references as values.
        # the list is of (object_type, handle) tuples for each reference.
        self.types_dict = {obj : {} for (_attr, _name, obj, _srcobj) in
                           self.t_table}

        window = Gtk.Window()
        window.set_size_request(740, 500)
        window.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_window(window, None, self.window_name)

        # main area
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        window.add(vbox)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, expand=True)
        vbox.add(hbox)
        # left types tree
        scrolled_window = Gtk.ScrolledWindow(min_content_width=250)
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC)
        hbox.pack_start(scrolled_window, False, True, 2)
        # right references tree
        scrolled_window_r = Gtk.ScrolledWindow(hexpand=True)
        scrolled_window_r.set_policy(Gtk.PolicyType.AUTOMATIC,
                                     Gtk.PolicyType.AUTOMATIC)
        hbox.pack_start(scrolled_window_r, True, True, 2)
        # Buttons etc.
        bbox = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(bbox, False, False, 5)
        # Help
        help_btn = Gtk.Button(label=_('Help'))
        help_btn.connect('clicked', self.on_help_clicked)
        bbox.add(help_btn)
        # Delete
        self.del_btn = Gtk.Button(label=_('Remove'))
        self.del_btn.set_tooltip_text(
            _('Remove the selected type from the db.\n'
              'This does not change any referenced objects.'))
        self.del_btn.connect('clicked', self.delete)
        self.del_btn.set_sensitive(False)
        bbox.add(self.del_btn)
        # Combo
        self.cbox = Gtk.Box()
        self.cbox.set_tooltip_text(
            _('Select a new name for the current type, prior to renaming the '
              'type in the referenced objects.'))
        self.combo = Gtk.ComboBox.new_with_entry()
        self.combo.get_child().set_width_chars(40)
        self.cbox.add(self.combo)
        bbox.add(self.cbox)
        self.type_name = None
        # Rename
        self.ren_btn = Gtk.Button(label=_('Rename'))
        self.ren_btn.connect('clicked', self.rename)
        self.ren_btn.set_tooltip_text(
            _('Rename the selected type in all referenced objects.'))
        bbox.add(self.ren_btn)
        # close
        close_btn = Gtk.Button(label=_('Close'))
        close_btn.set_tooltip_text(_('Close the Type Cleanup Tool'))
        close_btn.connect('clicked', self.close)
        bbox.add(close_btn)
        # left types treeview
        view = Gtk.TreeView()
        view.expand_all()
        column = Gtk.TreeViewColumn(_('Types'))
        view.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text', 0)
        column.set_sort_column_id(0)
        column.set_sort_indicator(True)
        # model: a tree of types and their custom values
        # Type name, t_table index for type, db cust type list index for type
        self.model = Gtk.TreeStore(str, int, int)
        self.model_load()
        view.set_model(self.model)
        view.show()
        selection = view.get_selection()
        selection.connect('changed', self.selection_changed)
        scrolled_window.add(view)

        # right references treeview
        view = Gtk.TreeView(hexpand=True)
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
        column.set_expand(True)
        column.set_resizable(True)
        column.set_sort_column_id(1)
        column.set_sort_indicator(True)
        # model: a list of type references
        # translated object_type, object display name, handle, object class
        self.model_r = Gtk.ListStore(str, str, str, str)
        view.set_model(self.model_r)
        view.show()
        view.connect('row_activated', self.button_press)
        scrolled_window_r.add(view)

        self.show()

    def build_menu_names(self, _obj):
        """Override :class:`.ManagedWindow` method."""
        return (_('Type Cleanup Tool'), None)

    def on_help_clicked(self, dummy):
        """ Button: Display the relevant portion of GRAMPS manual"""
        display_url(WIKI_PAGE)

    def model_load(self):
        """ populate the tree with types """
        r_indx = 0
        self.model.clear()
        for (attr, name, _obj, _srcobj) in self.t_table:
            # 99 is indicator that row is a title row
            row = (name, 0, 99)
            iter_ = self.model.append(None, row)
            # get custom types from db
            types = getattr(self.db, attr, None)
            if types is None:
                continue
            for indx, cust_type in enumerate(types):
                # update right model
                row = (cust_type, indx, r_indx)
                self.model.append(iter_, row)
                # create refs list for the custom type
                self.types_dict[_obj][cust_type] = []
            r_indx += 1
        progress = ProgressMeter(self.window_name, can_cancel=False,
                                 parent=self.window)
        # find total of db objects
        total = 0
        for obj_type in self.primary_objects_pl:
            total += self.db.method('get_number_of_%s', obj_type)()

        # scan db objects and record all custom GrampsTypes found as references
        progress.set_pass(_("Reading database..."), total)
        for obj_type in self.primary_objects:
            for hndl in self.db.method('get_%s_handles', obj_type)():
                obj = self.db.method('get_%s_from_handle', obj_type)(hndl)
                self.do_recurse(obj, obj_type, hndl)
                progress.step()
        progress.close()

    def do_recurse(self, obj, obj_class, hndl):
        """ recurse through the object, looking for GrampsType """
        if isinstance(obj, list):
            for item in obj:    # item from a list
                self.do_recurse(item, obj_class, hndl)
        elif hasattr(obj, '__dict__'):
            for item in obj.__dict__.values():  # item from object dict
                self.do_recurse(item, obj_class, hndl)
        if isinstance(obj, GrampsType):  # if Gramps type
            if(obj.__class__ in self.types_dict and  # one of monitored types
               obj.string in self.types_dict[obj.__class__]):  # custom type
                # save a reference to the original primary object
                self.types_dict[obj.__class__][obj.string].append(
                    (obj_class, hndl))

    def button_press(self, _view, path, _column):
        """
        Called when a right tree row is activated.  Edit the object.
        """
        iter_ = self.model_r.get_iter(path)
        (objclass, handle) = (self.model_r.get_value(iter_, 3),
                              self.model_r.get_value(iter_, 2))

        if objclass == 'Note':  # the method below did not include notes!!!
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
        self.type_name = None
        model, iter_ = selection.get_selected()
        if not iter_:
            return
        # save row information
        self.iter_ = iter_
        value = model.get_value(iter_, 0)
        self.name = value
        self.r_indx = model.get_value(iter_, 2)
        # set button sensitivity if valid row
        self.del_btn.set_sensitive(self.r_indx != 99)
        self.combo.set_sensitive(False)
        # clear right pane
        self.model_r.clear()
        # clear the rename combo
        self.combo.get_child().set_text('')
        self.ren_btn.set_sensitive(False)
        if self.r_indx == 99:  # if not a custom type row, done
            return
        # get list of refs
        refs = self.types_dict[self.t_table[self.r_indx][2]][value]
        for (obj_type, hndl) in refs:
            # some ref tables (Attributes) have elements from several primary
            # objects.  We only want the ones for the current type.
            if(self.t_table[self.r_indx][3] and
               obj_type != self.t_table[self.r_indx][3]):
                continue
            # get a display name for ref
            name = navigation_label(self.db, obj_type, hndl)[0]
            # fill in row of model, only first two columns are visible
            self.model_r.append((_(obj_type), name, hndl, obj_type))
        if not refs:  # if there are no refs, we are done
            return
        # allow rename, combo selector is enabled
        self.combo.set_sensitive(True)

        # make an GrampsType object to allow selection
        self.obj = self.t_table[self.r_indx][2](value)
        # Create combo selector new every time
        self.cbox.remove(self.combo)
        self.combo = Gtk.ComboBox.new_with_entry()
        self.combo.get_child().set_width_chars(40)
        self.combo.show()
        self.cbox.add(self.combo)
        self.type_name = MonitoredDataType(self.combo, self.set_obj,
                                           self.get_obj, self.db.readonly,
                                           self.get_cust_types())

    def get_cust_types(self):
        """ creates the custom types list for the MonitoredDataType """
        return list(getattr(self.db, self.t_table[self.r_indx][0], None))

    def set_obj(self, val):
        """ update our temporary object from combo """
        self.obj.set(val)
        # if we have changed the combo value, enable the rename button
        if '' != str(self.obj) != self.name:
            self.ren_btn.set_sensitive(True)

    def get_obj(self):
        """ Allow MonitoredDataType to see our temporary GrampsType object """
        return self.obj

    def rename(self, _button):
        """ Rename (or reselect) the selected type """
        # get list of references
        refs = self.types_dict[
            self.t_table[self.r_indx][2]][self.name]
        with DbTxn(_("Changing type from %(old_type)s to %(new_type)s.") %
                   {"old_type" : self.name,
                    "new_type" : str(self.obj)},
                   self.db, batch=False) as trans:
            for (obj_type, hndl) in refs:
                # some ref tables (Attributes) have elements from several
                # primary objects.  We only want the ones for the current type.
                # ignore refs that are not really part of this list
                if(self.t_table[self.r_indx][3] and
                   obj_type != self.t_table[self.r_indx][3]):
                    continue
                # get object to modify
                mod_obj = self.db.method("get_%s_from_handle", obj_type)(hndl)
                # find and modify the type
                self.mod_recurse(mod_obj, self.obj)
                # save result
                self.db.method("commit_%s", obj_type)(mod_obj, trans)
        # remove the old custom type from db
        types = getattr(self.db, self.t_table[self.r_indx][0], None)
        types.remove(self.name)
        # reload the gui
        self.model_load()

    def mod_recurse(self, mod_obj, type_obj):
        """ Recursivly search for a Grampstype and modify it when found """
        if isinstance(mod_obj, list):
            for item in mod_obj:
                self.mod_recurse(item, type_obj)
        elif hasattr(mod_obj, '__dict__'):
            for item in mod_obj.__dict__.values():
                self.mod_recurse(item, type_obj)
        if isinstance(mod_obj, self.t_table[self.r_indx][2]):  # if right type
            if(mod_obj.string == self.name):                 # and right value
                mod_obj.set(type_obj)

    def delete(self, _button):
        """ process the delete button """
        if self.r_indx == 99:  # not a custom type row
            return
        (attr, _name, _obj, _srcobj) = self.t_table[self.r_indx]
        refs = self.types_dict[self.t_table[self.r_indx][2]][self.name]
        # warn if there are refs...
        if refs:
            warn_dialog = QuestionDialog2(
                self.window_name,
                _("Removing this custom type will eliminate it from the type "
                  "selection drop down lists\nand further runs of this tool.\n"
                  "\nHowever, it will not remove it from the referenced items "
                  "in the database.\nIf you want to change it in referenced "
                  "items, use 'Rename'."),
                _('_Remove'), _('_Stop'),
                parent=self.window)
            if not warn_dialog.run():
                return False
        # actually remove from the db
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
