#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013  Artem Glebov <artem.glebov@gmail.com>
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

# $Id:  $

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk

#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------
from gramps.gen.plug import Gramplet

from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# SurnameMappingGramplet
#
#-------------------------------------------------------------------------

class SurnameMappingGramplet(Gramplet):

    def init(self):
        self.gui.WIDGET = self.build_gui()
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.gui.WIDGET)
        self.top.show_all()

    def build_gui(self):
        """
        Build the GUI interface.
        """
        vbox = Gtk.VBox()
        self.top = vbox

        button_panel = Gtk.Toolbar()

        self.button_add = button_panel.insert_stock(Gtk.STOCK_ADD, _("Add Mapping"), None, self.add_mapping_clicked, None, -1)
        self.button_edit = button_panel.insert_stock(Gtk.STOCK_EDIT, _("Edit Mapping"), None, self.edit_mapping_clicked, None, -1)
        self.button_del = button_panel.insert_stock(Gtk.STOCK_REMOVE, _("Remove Mapping"), None, self.remove_mapping_clicked, None, -1)

        vbox.pack_start(button_panel, expand=False, fill=True, padding=5)

        self.treestore = Gtk.TreeStore(str, str)

        self.treeview = Gtk.TreeView(self.treestore)
        self.treeview.connect("row-activated", self.row_double_clicked)
        self.column1 = Gtk.TreeViewColumn(_('Surname'))
        self.column2 = Gtk.TreeViewColumn(_('Group Name'))
        self.treeview.append_column(self.column1)
        self.treeview.append_column(self.column2)

        self.cell1 = Gtk.CellRendererText()
        self.cell2 = Gtk.CellRendererText()
        self.column1.pack_start(self.cell1, True)
        self.column1.add_attribute(self.cell1, 'text', 0)
        self.column2.pack_start(self.cell2, True)
        self.column2.add_attribute(self.cell2, 'text', 1)

        self.treeview.set_search_column(0)
        self.column1.set_sort_column_id(0)
        self.column2.set_sort_column_id(1)

        vbox.pack_start(self.treeview, expand=True, fill=True)

        return vbox

    def db_changed(self):
        pass

    def main(self):
        self.treestore.clear()
        keys = self.dbstate.db.get_name_group_keys()
        for key in keys:
            group_name = self.dbstate.db.get_name_group_mapping(key)
            self.treestore.append(None, (key, group_name))

    def show_dialog(self, title, surname, group):
        labelSurname = Gtk.Label(_("Surname"))
        entrySurname = Gtk.Entry()
        if surname:
            entrySurname.set_text(surname)
        labelGroup = Gtk.Label(_("Group"))
        entryGroup = Gtk.Entry()
        if group:
            entryGroup.set_text(group)
        dialog = Gtk.Dialog(title,
                   None,
                   Gtk.DIALOG_MODAL | Gtk.DIALOG_DESTROY_WITH_PARENT,
                   (Gtk.STOCK_CANCEL, Gtk.RESPONSE_REJECT,
                    Gtk.STOCK_OK, Gtk.RESPONSE_ACCEPT))

        table = Gtk.Table(2, 2)
        table.attach(labelSurname, 0, 1, 0, 1, xoptions=Gtk.SHRINK, yoptions=Gtk.EXPAND, xpadding=5, ypadding=5)
        table.attach(labelGroup, 0, 1, 1, 2, xoptions=Gtk.SHRINK, yoptions=Gtk.EXPAND, xpadding=5, ypadding=5)
        table.attach(entrySurname, 1, 2, 0, 1, xoptions=Gtk.FILL, yoptions=Gtk.EXPAND, xpadding=5, ypadding=5)
        table.attach(entryGroup, 1, 2, 1, 2, xoptions=Gtk.FILL, yoptions=Gtk.EXPAND, xpadding=5, ypadding=5)

        dialog.vbox.pack_start(table, fill=True, expand=True)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.RESPONSE_ACCEPT:
            result = (entrySurname.get_text(), entryGroup.get_text())
        else:
            result = None
        dialog.destroy()
        return result

    def add_mapping_clicked(self, event):
        response = self.show_dialog(_("Create Mapping"), None, None)
        if response:
            (surname, group) = response
            self.dbstate.db.set_name_group_mapping(str(surname), str(group))
        self.main()

    def remove_mapping_clicked(self, event):
        (model, pathlist) = self.treeview.get_selection().get_selected_rows()
        for path in pathlist:
            tree_iter = model.get_iter(path)
            value = model.get_value(tree_iter, 0)
            self.dbstate.db.set_name_group_mapping(str(value), None)
        self.main()

    def edit_row(self, model, path):
        tree_iter = model.get_iter(path)
        surname = model.get_value(tree_iter, 0)
        group = model.get_value(tree_iter, 1)
        response = self.show_dialog(_("Edit Mapping"), surname, group)
        if response:
            (new_surname, new_group) = response
            if new_surname == surname:
                self.dbstate.db.set_name_group_mapping(str(surname), str(new_group))
            else:
                self.dbstate.db.set_name_group_mapping(str(surname), None)
                self.dbstate.db.set_name_group_mapping(str(new_surname), str(new_group))

    def edit_mapping_clicked(self, event):
        (model, pathlist) = self.treeview.get_selection().get_selected_rows()
        for path in pathlist:
            self.edit_row(model, path)
        self.main()

    def row_double_clicked(self, treeview, path, view_column):
        self.edit_row(treeview.get_model(), path)
