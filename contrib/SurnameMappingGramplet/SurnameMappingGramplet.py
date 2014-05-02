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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id:  $

#-------------------------------------------------------------------------
#
# GTK/Gnome modules
#
#-------------------------------------------------------------------------
import gtk

#-------------------------------------------------------------------------
#
# gramps modules
#
#-------------------------------------------------------------------------
from gen.plug import Gramplet

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).gettext

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
        vbox = gtk.VBox()
        self.top = vbox

        button_panel = gtk.Toolbar()

        self.button_add = button_panel.insert_stock(gtk.STOCK_ADD, _("Add Mapping"), None, self.add_mapping_clicked, None, -1)
        self.button_edit = button_panel.insert_stock(gtk.STOCK_EDIT, _("Edit Mapping"), None, self.edit_mapping_clicked, None, -1)
        self.button_del = button_panel.insert_stock(gtk.STOCK_REMOVE, _("Remove Mapping"), None, self.remove_mapping_clicked, None, -1)

        vbox.pack_start(button_panel, expand=False, fill=True, padding=5)

        self.treestore = gtk.TreeStore(str, str)

        self.treeview = gtk.TreeView(self.treestore)
        self.treeview.connect("row-activated", self.row_double_clicked)
        self.column1 = gtk.TreeViewColumn(_('Surname'))
        self.column2 = gtk.TreeViewColumn(_('Group Name'))
        self.treeview.append_column(self.column1)
        self.treeview.append_column(self.column2)

        self.cell1 = gtk.CellRendererText()
        self.cell2 = gtk.CellRendererText()
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
        labelSurname = gtk.Label(_("Surname"))
        entrySurname = gtk.Entry()
        if surname:
            entrySurname.set_text(surname)
        labelGroup = gtk.Label(_("Group"))
        entryGroup = gtk.Entry()
        if group:
            entryGroup.set_text(group)
        dialog = gtk.Dialog(title,
                   None,
                   gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                   (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                    gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        table = gtk.Table(2, 2)
        table.attach(labelSurname, 0, 1, 0, 1, xoptions=gtk.SHRINK, yoptions=gtk.EXPAND, xpadding=5, ypadding=5)
        table.attach(labelGroup, 0, 1, 1, 2, xoptions=gtk.SHRINK, yoptions=gtk.EXPAND, xpadding=5, ypadding=5)
        table.attach(entrySurname, 1, 2, 0, 1, xoptions=gtk.FILL, yoptions=gtk.EXPAND, xpadding=5, ypadding=5)
        table.attach(entryGroup, 1, 2, 1, 2, xoptions=gtk.FILL, yoptions=gtk.EXPAND, xpadding=5, ypadding=5)

        dialog.vbox.pack_start(table, fill=True, expand=True)
        dialog.show_all()

        response = dialog.run()
        if response == gtk.RESPONSE_ACCEPT:
            result = (entrySurname.get_text(), entryGroup.get_text())
        else:
            result = None
        dialog.destroy()
        return result

    def add_mapping_clicked(self, event):
        response = self.show_dialog(_("Create Mapping"), None, None)
        if response:
            (surname, group) = response
            self.dbstate.db.set_name_group_mapping(unicode(surname), unicode(group))
        self.main()

    def remove_mapping_clicked(self, event):
        (model, pathlist) = self.treeview.get_selection().get_selected_rows()
        for path in pathlist:
            tree_iter = model.get_iter(path)
            value = model.get_value(tree_iter, 0)
            self.dbstate.db.set_name_group_mapping(unicode(value), None)
        self.main()

    def edit_row(self, model, path):
        tree_iter = model.get_iter(path)
        surname = model.get_value(tree_iter, 0)
        group = model.get_value(tree_iter, 1)
        response = self.show_dialog(_("Edit Mapping"), surname, group)
        if response:
            (new_surname, new_group) = response
            if new_surname == surname:
                self.dbstate.db.set_name_group_mapping(unicode(surname), unicode(new_group))
            else:
                self.dbstate.db.set_name_group_mapping(unicode(surname), None)
                self.dbstate.db.set_name_group_mapping(unicode(new_surname), unicode(new_group)) 

    def edit_mapping_clicked(self, event):
        (model, pathlist) = self.treeview.get_selection().get_selected_rows()
        for path in pathlist:
            self.edit_row(model, path)
        self.main()

    def row_double_clicked(self, treeview, path, view_column):
        self.edit_row(treeview.get_model(), path)
