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

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).ugettext
from gen.plug import Gramplet

from Filters.SideBar import (PersonSidebarFilter, FamilySidebarFilter,
                             EventSidebarFilter, SourceSidebarFilter, PlaceSidebarFilter,
                             MediaSidebarFilter, RepoSidebarFilter, NoteSidebarFilter)

class FilterGramplet(Gramplet):
    """
    A Filter gramplet for controlling object views.
    """
    def init(self):
        nav_type = None
        if hasattr(self.gui.pane, "splitview"):
            if self.gui.pane.splitview:
                nav_type = self.gui.pane.splitview.navigation_type()
            else:
                raise AttributeError("This gramplet only works on split object views")
        else:
            raise AttributeError("This gramplet only works on split object views")
        if nav_type == "Person":
            sidebar_class = PersonSidebarFilter
        elif nav_type == "Family":
            sidebar_class = FamilySidebarFilter
        elif nav_type == "Event":
            sidebar_class = EventSidebarFilter
        elif nav_type == "Source":
            sidebar_class = SourceSidebarFilter
        elif nav_type == "Place":
            sidebar_class = PlaceSidebarFilter
        elif nav_type == "Media":
            sidebar_class = MediaSidebarFilter
        elif nav_type == "Repo":
            sidebar_class = RepoSidebarFilter
        elif nav_type == "Note":
            sidebar_class = NoteSidebarFilter
        else:
            raise AttributeError("This gramplet only works on split object views")

        self.filter_sidebar = sidebar_class(self.dbstate, self.uistate, 
                                            self.filter_clicked)
        self.gui.get_container_widget().remove(self.gui.textview)
        self.gui.get_container_widget().add_with_viewport(self.filter_sidebar.table)
        self.filter_sidebar.table.show_all()

    def filter_clicked(self):
        self.gui.pane.splitview.generic_filter = self.filter_sidebar.get_filter()
        self.gui.pane.splitview.build_tree(force_sidebar=True)

