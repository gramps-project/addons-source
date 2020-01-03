#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2019-2020 Steve Youngs
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
# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
import logging
import importlib.util
import inspect
import os
import sys

# ------------------------------------------------------------------------
#
# GTK modules
#
# ------------------------------------------------------------------------
from gi.repository import Gtk, GObject

# ------------------------------------------------------------------------
#
# Gramps modules
#
# ------------------------------------------------------------------------
from gramps.gen.config import config
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.datehandler import get_date
from gramps.gen.db import DbTxn
from gramps.gui.display import display_help
from gramps.gui.managedwindow import ManagedWindow

# ------------------------------------------------------------------------
#
# Gramplet modules
#
# ------------------------------------------------------------------------
import actionutils
from editform import find_form_event
from form import (get_form_id, get_form_type)

# ------------------------------------------------------------------------
#
# Logging
#
# ------------------------------------------------------------------------
LOG = logging.getLogger('.form')

# ------------------------------------------------------------------------
#
# Internationalisation
#
# ------------------------------------------------------------------------
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# ------------------------------------------------------------------------
#
# FormActions class
#
# ------------------------------------------------------------------------


class FormActions(object):
    """
    Form Action selector.
    """
    RUN_ACTION_COL = 0
    RUN_INCONSISTENT_COL = 1
    ACTION_COL = 2
    DETAIL_COL = 3
    CAN_EDIT_DETAIL_COL = 4  # actionutils.CANNOT_EDIT_DETAIL, actionutils.CAN_EDIT_DETAIL or actionutils.MUST_EDIT_DETAIL
    ACTION_COMMAND_COL = 5
    EDIT_DETAIL_COL = 6

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
        full_path = os.path.join(os.path.dirname(
            __file__), '{form_id}.py'.format(form_id=self.form_id))
        if os.path.exists(full_path):
            # temporarily modify sys.path so that any import statements in the module get processed correctly
            sys.path.insert(0, os.path.dirname(__file__))
            try:
                spec = importlib.util.spec_from_file_location(
                    'form.actions.{form_id}'.format(form_id=self.form_id), full_path)
                self.actions_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.actions_module)
            except (ValueError, ImportError, SyntaxError) as err:
                self.actions_module = None
                LOG.warning(_("Form plugin error (from '{path}'): {error}").format(
                    path=full_path, error=err))
            finally:
                # must make sure we restore sys.path
                sys.path.pop(0)

        self.event = find_form_event(self.db, self.citation)

        self.top = self._create_dialog(self.get_dialog_title())

        self._config = config.get_manager('form')
        width = self._config.get('interface.form-actions-width')
        height = self._config.get('interface.form-actions-height')
        self.top.resize(width, height)
        horiz_position = self._config.get(
            'interface.form-actions-horiz-position')
        vert_position = self._config.get(
            'interface.form-actions-vert-position')
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

        self.model = Gtk.TreeStore(
            bool, bool, str, str, int, GObject.TYPE_PYOBJECT, bool)
        self.tree = Gtk.TreeView(model=self.model)
        renderer_text = Gtk.CellRendererText()
        column1 = Gtk.TreeViewColumn(_("Action"))
        renderer_action_toggle = Gtk.CellRendererToggle()
        renderer_action_toggle.connect('toggled', self.on_action_toggled)
        column1.pack_start(renderer_action_toggle, False)
        column1.add_attribute(renderer_action_toggle,
                              'active', self.RUN_ACTION_COL)
        column1.add_attribute(renderer_action_toggle,
                              'inconsistent', self.RUN_INCONSISTENT_COL)
        column1.pack_start(renderer_text, True)
        column1.add_attribute(renderer_text, 'text', self.ACTION_COL)

        render_edit_detail_toggle = Gtk.CellRendererToggle()
        render_edit_detail_toggle.connect(
            "toggled", self.on_edit_detail_toggled)
        column2 = Gtk.TreeViewColumn(
            _("Edit"), render_edit_detail_toggle, active=self.EDIT_DETAIL_COL)
        column2.set_cell_data_func(
            render_edit_detail_toggle, FormActions.detail_data_func)

        column3 = Gtk.TreeViewColumn(
            _("Detail"), renderer_text, text=self.DETAIL_COL)

        self.tree.append_column(column1)
        self.tree.append_column(column2)
        self.tree.append_column(column3)

        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        slist = Gtk.ScrolledWindow()
        slist.add(self.tree)
        slist.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(slist, True, True, 5)

        top.add_button(_('_Help'), Gtk.ResponseType.HELP)
        top.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        top.add_button(_('_OK'), Gtk.ResponseType.OK)
        top.set_default_response(Gtk.ResponseType.OK)

        top.show_all()

        return top

    def on_action_toggled(self, widget, path):
        row_iter = self.model.get_iter(path)
        parent = self.model.iter_parent(row_iter)
        if not parent:
            # user clicked an action category row. toggle all children
            new_state = not self.model[row_iter][self.RUN_ACTION_COL]
            child = self.model.iter_children(row_iter)
            while child:
                self.model[child][self.RUN_ACTION_COL] = new_state
                child = self.model.iter_next(child)
            # all children are now consistent
            self.model[row_iter][self.RUN_INCONSISTENT_COL] = False
        # toggle RUN_ACTION_COL for the row that was clicked
        self.model[row_iter][self.RUN_ACTION_COL] = not self.model[row_iter][self.RUN_ACTION_COL]
        if parent:
            # update the status of the parent
            (consistent, value) = FormActions.all_children_consistent(
                self.model, parent, FormActions.RUN_ACTION_COL)
            self.model[parent][self.RUN_INCONSISTENT_COL] = not consistent
            self.model[parent][self.RUN_ACTION_COL] = consistent and value

    @staticmethod
    def detail_data_func(col, cell, model, iter, user_data):
        can_edit_detail = model.get_value(
            iter, FormActions.CAN_EDIT_DETAIL_COL)
        cell.set_property("visible", can_edit_detail !=
                          actionutils.CANNOT_EDIT_DETAIL)
        cell.set_property("activatable", can_edit_detail != actionutils.MUST_EDIT_DETAIL)

    def on_edit_detail_toggled(self, widget, path):
        edit_detail = not self.model[path][self.EDIT_DETAIL_COL]
        self.model[path][self.EDIT_DETAIL_COL] = edit_detail
        if edit_detail:
            # as a convenience, if the user turns EDIT_DETAIL_COL on, automatically turn on RUN_ACTION_COL
            self.model[path][self.RUN_ACTION_COL] = True

    @staticmethod
    def all_children_consistent(model, parent, col):
        consistent = True
        value = False
        child = model.iter_children(parent)
        if child:   # handle case of no children
            # start with value of first child
            value = model.get_value(child, col)
            # advance to second child (if there is one)
            child = model.iter_next(child)
            # loop over all remaining children until we find an inconsistent value or reach the end
            while consistent and child:
                consistent = model.get_value(child, col) == value
                child = model.iter_next(child)
        return (consistent, value)

    def _populate_model(self):
        if self.actions_module:
            # get the all actions that the actions module can provide for the form
            # because the module is dynamically loaded, use getattr to retrieve the actual function to call
            all_actions = getattr(self.actions_module, 'get_actions')(
                self.dbstate, self.citation, self.event)
            for (title, actions) in all_actions:
                if actions:
                    # add the action category
                    parent = self.model.append(
                        None, (False, False, title, None, actionutils.CANNOT_EDIT_DETAIL, None, False))
                    for action_detail in actions:
                        # add available actions within this category
                        self.model.append(
                            parent, (False, False) + action_detail + (action_detail[2] == actionutils.MUST_EDIT_DETAIL,))

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

        if response == Gtk.ResponseType.OK:
            # run the selected actions
            self.uistate.set_busy_cursor(True)
            self.uistate.progress.show()
            self.uistate.pulse_progressbar(0)
            # get the list of actions to be run
            # this helps give meaningful progress information (because we know how many actions in total will be run)
            actions = []
            for action_type_row in self.model:
                for action_row in action_type_row.iterchildren():
                    if action_row.model.get_value(action_row.iter, self.RUN_ACTION_COL):
                        actions.append(action_row.model.get_value(
                            action_row.iter, self.ACTION_COMMAND_COL))
            # run the actions
            for index, action in enumerate(actions):
                (action)(self.dbstate, self.uistate, self.track)
                self.uistate.pulse_progressbar(
                    (index + 1) / len(actions) * 100)
            self.uistate.progress.hide()
            self.uistate.set_busy_cursor(False)

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
        dialog_title = _('Form: {source_title}: {event_reference}').format(
            source_title=self.source.get_title(), event_reference=self.citation.get_page())

        return dialog_title
