#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019 Steve Youngs
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
Form action chooser
"""
import importlib.util
import inspect
import os
import gobject

#------------------------------------------------------------------------
#
# GTK modules
#
#------------------------------------------------------------------------
from gi.repository import Gtk, GObject

#------------------------------------------------------------------------
#
# Gramps modules
#
#------------------------------------------------------------------------
from gramps.gui.managedwindow import ManagedWindow
from gramps.gen.config import config
from gramps.gen.datehandler import get_date
from gramps.gen.db import DbTxn

#------------------------------------------------------------------------
#
# Gramplet modules
#
#------------------------------------------------------------------------
from editform import find_form_event
from form import (get_form_id, get_form_type)
from actionbase import ActionBase

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

#------------------------------------------------------------------------
#
# FormActions class
#
#------------------------------------------------------------------------
class FormActions(object):
    """
    Form Action selector.
    """

    def __init__(self, dbstate, uistate, track, citation):
        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        self.db = dbstate.db
        self.citation = citation
        source_handle = self.citation.get_reference_handle()
        self.source = self.db.get_source_from_handle(source_handle)
        self.form_id = get_form_id(self.source)

        self.actions_module = None
        # for security reasons provide the full path to the actions_module .py file
        full_path = os.path.join(os.path.dirname(__file__), '%s.py' % self.form_id)
        if os.path.exists(full_path):
            spec = importlib.util.spec_from_file_location('form.action.', full_path)
            self.actions_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.actions_module)

        self.event = find_form_event(self.db, self.citation)

        self.top = self._create_dialog(self.get_dialog_title())

        self._config = config.get_manager('form')
        width = self._config.get('interface.form-actions-width')
        height = self._config.get('interface.form-actions-height')
        self.top.resize(width, height)
        horiz_position = self._config.get('interface.form-actions-horiz-position')
        vert_position = self._config.get('interface.form-actions-vert-position')
        if horiz_position != -1:
            self.top.move(horiz_position, vert_position)

    def _create_dialog(self, title):
        """
        Create and display the GUI components of the action selector.
        """
        top = Gtk.Dialog(title)
        top.set_modal(True)
        top.set_transient_for(self.uistate.window)
        top.vbox.set_spacing(5)

        box = Gtk.Box()
        top.vbox.pack_start(box, True, True, 5)

        self.model = Gtk.TreeStore(str, str, GObject.TYPE_PYOBJECT)
        self.tree = Gtk.TreeView(model=self.model)
        renderer = Gtk.CellRendererText()
        column1 = Gtk.TreeViewColumn(_("Action"), renderer, text=0)
        column1.set_sort_column_id(1)
        column2 = Gtk.TreeViewColumn(_("Detail"), renderer, text=1)
        self.tree.append_column(column1)
        self.tree.append_column(column2)

        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        slist = Gtk.ScrolledWindow()
        slist.add(self.tree)
        slist.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(slist, True, True, 5)

        top.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        top.add_button(_('_OK'), Gtk.ResponseType.OK)
        top.set_default_response(Gtk.ResponseType.OK)

        top.show_all()

        return top

    def _populate_model(self):
        form_id = get_form_id(self.source)
        if self.actions_module:
            # get all classes defined in actions_module which are a subclass of ActionBase (but exclude ActionBase itself)
            action_classes = inspect.getmembers(self.actions_module, lambda obj: inspect.isclass(obj) and obj is not ActionBase and issubclass(obj, ActionBase))

            for action_class in action_classes:
                action = (action_class[1])()
                action.populate_model(self.dbstate, self.citation, self.event, self.model)

    def run(self):
        """
        Run the dialog and return the result.
        """
        self._populate_model()
        self.tree.expand_all()
        while True:
            response = self.top.run()
            if response == Gtk.ResponseType.HELP:
                display_help(webpage='Form_Addons')
            else:
                break

        (width, height) = self.top.get_size()
        self._config.set('interface.form-actions-width', width)
        self._config.set('interface.form-actions-height', height)
        (root_x, root_y) = self.top.get_position()
        self._config.set('interface.form-actions-horiz-position', root_x)
        self._config.set('interface.form-actions-vert-position', root_y)
        self._config.save()

        # run the selected actions
        (model, pathlist) = self.tree.get_selection().get_selected_rows()
        for path in pathlist :
            tree_iter = model.get_iter(path)

            command = model.get_value(tree_iter, 2)
            if command:
                (command)(self.dbstate, self.uistate, self.track)

        self.top.destroy()

        return None

    def help_clicked(self, obj):
        """
        Display the relevant portion of Gramps manual
        """
        display_help(webpage='Form_Addons')

    def get_dialog_title(self):
        """
        Get the title of the dialog.
        """
        dialog_title = _('Form: %s: %s')  % (self.source.get_title(), self.citation.get_page())

        return dialog_title
