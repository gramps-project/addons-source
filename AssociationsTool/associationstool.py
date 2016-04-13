#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2006  Donald N. Allingham
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

""" Associations Statistics.

    Inherited from gedcom model
"""
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gi.repository import Gtk
from gramps.gui.listmodel import ListModel
from gramps.gui.managedwindow import ManagedWindow

from gramps.gui.plug import tool
from gen.display.name import displayer as name_displayer

#-------------------------------------------------------------------------
#
#
#
#-------------------------------------------------------------------------
class AssociationsTool(tool.Tool, ManagedWindow):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate
        self.label = _("Associations state tool")
        tool.Tool.__init__(self, dbstate, options_class, name)
        if uistate:
            ManagedWindow.__init__(self,uistate,[],
                                                 self.__class__)

        stats_list = []

        plist = dbstate.db.get_person_handles(sort_handles=True)

        for handle in plist:
            person = dbstate.db.get_person_from_handle(handle)
            name1 = name_displayer.display(person)
            refs = person.get_person_ref_list()
            if refs:
                for ref in person.serialize()[-1]:
                    (a, b, c, two, value) = ref
                    person2 = dbstate.db.get_person_from_handle(two)
                    name2 = name_displayer.display(person2)
                    stats_list.append((name1, value, name2))

        if uistate:
            titles = [
                (_('Name'), 0, 200),
                (_('Type of link'), 1, 200),
                (_('Of'), 2, 200),
                ]

            treeview = Gtk.TreeView()
            model = ListModel(treeview, titles)
            for entry in stats_list:
                model.add(entry, entry[0])

            window = Gtk.Window()
            window.set_default_size(800, 600)
            s = Gtk.ScrolledWindow()
            s.add(treeview)
            window.add(s)
            window.show_all()
            self.set_window(window, None, self.label)
            self.show()

        else:
            print('\t%s'*3 % ('Name','Type of link','Of'))
            print()
            for entry in stats_list:
                print('\t%s'*3 % entry)

    def build_menu_names(self, obj):
        return (self.label,None)

#------------------------------------------------------------------------
#
#
#
#------------------------------------------------------------------------
class AssociationsToolOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
