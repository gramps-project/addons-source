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
from gramps.gui.managedwindow import ManagedWindow
import gramps.gui.dialog
import gramps.gui.display

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


class FormActions(ManagedWindow):
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

        self.close_after_run = False    # if True, close this window after running action command(s)

        ManagedWindow.__init__(self, uistate, track, citation)

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
        top = self.__create_gui()
        self.set_window(top, None, self.get_title())
        self._local_init()

        self._populate_model()
        self.tree.expand_all()

        self.show()

    def _local_init(self):
        self.setup_configs('interface.form-actions', 750, 550)

    def __create_gui(self):
        """
        Create and display the GUI components of the action selector.
        """
        root = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        root.set_transient_for(self.uistate.window)
        # Initial position for first run
        root.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

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

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)

        help_btn = Gtk.Button(label=_('_Help'), use_underline=True)
        help_btn.connect('clicked', self.display_help)
        button_box.add(help_btn)
        button_box.set_child_secondary(help_btn, True)

        close_btn = Gtk.Button(label=_('_Close'), use_underline=True)
        close_btn.connect('clicked', self.close)
        button_box.add(close_btn)

        run_btn = Gtk.Button(label=_('_Run'), use_underline=True)
        run_btn.connect('clicked', self.run_actions)
        button_box.add(run_btn)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.set_margin_left(2)
        vbox.set_margin_right(2)
        vbox.set_margin_top(2)
        vbox.set_margin_bottom(2)

        vbox.pack_start(slist, expand=True, fill=True, padding=0)
        vbox.pack_end(button_box, expand=False, fill=True, padding=0)

        root.add(vbox)

        return root

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

    def run_actions(self, widget):
        # run the selected actions
        self.uistate.progress.show()
        self.uistate.pulse_progressbar(0)
        # get the list of actions to be run
        # this helps give meaningful progress information (because we know how many actions in total will be run)
        actions = []
        for action_type_row in self.model:
            for action_row in action_type_row.iterchildren():
                if action_row.model.get_value(action_row.iter, self.RUN_ACTION_COL):
                    actions.append((action_row.model.get_value(action_row.iter, self.ACTION_COMMAND_COL),
                                    action_row.model.get_value(action_row.iter, self.EDIT_DETAIL_COL)))
        self.count_actions = len(actions)
        # run the actions, sequentially
        self.do_next_action(actions, self.dbstate, self.uistate, self.track)

    def do_next_action(self, actions, dbstate, uistate, track):
        # update the progressbar based on the number of actions completed so far
        actions_completed = self.count_actions - len(actions)
        self.uistate.pulse_progressbar(actions_completed / self.count_actions * 100)
        if actions:
            # actions remaining
            # take the top action
            (action, edit_detail) = actions[0]
            # and run it passing, a callback to ourselves, but with actions=actions[1:]
            # effectively indirect recursion via the callback
            action(dbstate, uistate, track, edit_detail,
                   # kwargs is added for convenince of the action command authors.
                   # it is not used, but should not be removed.
                   lambda self=self, actions=actions[1:], dbstate=dbstate, uistate=uistate, track=track, **kwargs:
                        self.do_next_action(actions=actions, dbstate=dbstate, uistate=uistate, track=track))
        else:
            # no more actions. Stop showing progress
            uistate.progress.hide()
            # and, optionally, close our window now that the actions have all run
            if self.close_after_run:
                self.close()
            else:
                gramps.gui.dialog.OkDialog(_("All actions run successfully."), parent=self.window)

    def close(self, *obj):
        ManagedWindow.close(self)

    def display_help(self, obj):
        """
        Display the relevant portion of Gramps manual
        """
        gramps.gui.display.display_help(webpage='Form_Addons')

    def get_title(self):
        if self.source and self.citation:
            title = _('Form: {source_title}: {event_reference}').format(
                source_title=self.source.get_title(), event_reference=self.citation.get_page())
        else:
            title = None
        return title
