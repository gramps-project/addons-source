#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010       Douglas S. Blank <doug.blank@gmail.com>
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
#
# $Id$
#
#

import gtk
import gobject

views = [("relview", "RelationshipView", ["TODO Gramplet"]),
         ("eventview", "EventView", ["TODO Gramplet"]),
         ("familyview", "FamilyView", ["TODO Gramplet"]),
         ("fanchartview", "FanChartView", ["TODO Gramplet"]),
         ("geoview", "GeoView", ["TODO Gramplet"]),
         ("htmlrenderer", "HtmlView", ["TODO Gramplet"]),
         ("mediaview", "MediaView", ["TODO Gramplet"]),
         ("noteview", "NoteView", ["TODO Gramplet"]),
         ("pedigreeview", "PedigreeView", ["TODO Gramplet"]),
         ("personlistview", "PersonListView", ["TODO Gramplet"]),
         ("persontreeview", "PersonTreeView", ["TODO Gramplet"]),
         ("placelistview", "PlaceListView", ["TODO Gramplet"]),
         ("placetreeview", "PlaceTreeView", ["TODO Gramplet"]),
         ("repoview", "RepositoryView", ["TODO Gramplet"]),
         ("sourceview", "SourceView", ["TODO Gramplet"]),
         ]

from gui.widgets.grampletpane import GrampletPane

def extend(class_):
    class SidebarView(class_):
        def on_delete(self):
            super(SidebarView, self).on_delete()
            self.gramplet_pane.on_delete()

        def build_widget(self):
            self.top_level = gtk.Frame()
            self.main_pane = super(SidebarView, self).build_widget()
            self.gramplet_pane = \
                GrampletPane(self.ident + "_gramplets",
                             self, self.dbstate, self.uistate, 
                             column_count=1,
                             default_gramplets=self.DEFAULT_GRAMPLETS)
            if self.gramplet_pane.pane_orientation == "horizontal":
                widget = gtk.HPaned()
            elif self.gramplet_pane.pane_orientation == "vertical":
                widget = gtk.VPaned()
            elif self.gramplet_pane.pane_orientation == "none":
                self.top_level.add(self.main_pane)
                self.multipane = None
                return self.top_level
            else:
                raise AttributeError("invalid pane_orientation: '%s'" % 
                                     self.gramplet_pane.pane_orientation)
            widget.pack1(self.main_pane, resize=True, shrink=True)
            widget.pack2(self.gramplet_pane, resize=True, shrink=True)
            widget.set_position(self.gramplet_pane.pane_position)
            widget.connect("notify", self.move_handle)
            self.multipane = widget
            self.top_level.add(widget)
            return self.top_level

        def change_orientation(self, orientation):
            self.gramplet_pane.pane_orientation = orientation
            if self.multipane:
                self.top_level.remove(self.multipane)
            else:
                self.top_level.remove(self.main_pane)
            if isinstance(self.multipane, gtk.Paned):
                self.multipane.remove(self.main_pane)
                self.multipane.remove(self.gramplet_pane)
            # else is just the main_pane
            self.gramplet_pane.pane_position = -1
            if self.gramplet_pane.pane_orientation == "horizontal":
                self.multipane = gtk.HPaned()
            elif self.gramplet_pane.pane_orientation == "vertical":
                self.multipane = gtk.VPaned()
            elif self.gramplet_pane.pane_orientation == "none":
                self.multipane = None
                self.top_level.add(self.main_pane)
                return
            else:
                raise AttributeError("invalid pane_orientation: '%s'" % 
                                     self.gramplet_pane.pane_orientation)
            self.multipane.pack1(self.main_pane, resize=True, shrink=True)
            self.multipane.pack2(self.gramplet_pane, resize=True, shrink=True)
            self.multipane.set_position(self.gramplet_pane.pane_position)
            self.multipane.connect("notify", self.move_handle)
            self.top_level.add(self.multipane)
            self.multipane.show_all()

        def move_handle(self, widget, notify_type):
            if notify_type.name == "position-set":
                self.gramplet_pane.pane_position = widget.get_position()

        def ui_definition(self):
            uid = super(SidebarView, self).ui_definition()
            this_uid = """            
                <menuitem action="AddGramplet"/>
                <menuitem action="RestoreGramplet"/>
                <separator/>
                """
            if "</popup>" in uid:
                uid = uid.replace("</popup>", this_uid + "</popup>")
            elif "</ui>" in uid:
                uid = uid.replace("</ui>", """<popup name="Popup">%s</popup></ui>""" % this_uid)
            else:
                uid = """<ui><popup name="Popup">%s</popup></ui>""" % this_uid
            return uid

        def define_actions(self):
            super(SidebarView, self).define_actions()
            self._add_action("AddGramplet", None, _("Add a gramplet"))
            self._add_action("RestoreGramplet", None, _("Restore a gramplet"))

        def set_inactive(self):
            super(SidebarView, self).set_inactive()
            self.gramplet_pane.set_inactive()

        def set_active(self):
            super(SidebarView, self).set_active()
            self.gramplet_pane.set_active()
            # This is a workaround to get gramplets to redraw correctly:
            gobject.timeout_add(100, self.gramplet_pane.set_state_all)

        def can_configure(self):
            """
            See :class:`~gui.views.pageview.PageView 
            :return: bool
            """
            if super(SidebarView, self).can_configure():
                return True
            elif self.gramplet_pane.can_configure():
                self._config = self.gramplet_pane._config
                return True
            else:
                return False

        def split_panel(self, configdialog):
            orientation = self.gramplet_pane.pane_orientation
            table = gtk.Table(3, 2)
            table.set_border_width(12)
            table.set_col_spacings(6)
            table.set_row_spacings(6)

            from PluginUtils import make_gui_option
            from gen.plug.menu import EnumeratedListOption
            # Add types:
            self.view_list = EnumeratedListOption(_("Split view"), 
                                    self.gramplet_pane.pane_orientation)
            for item in [("horizontal", _("Horizontal views")), 
                         ("vertical", _("Vertical views")), 
                         ("none", _("No split")), 
                         ]:
                self.view_list.add_item(item[0], item[1])
            # Add particular lists:
            type_widget, option = make_gui_option(self.view_list, 
                            self.dbstate, self.uistate, [])
            type_widget.value_changed = self.update_settings
            table.attach(type_widget, 1, 4, 5, 6, yoptions=0)
            return [_("Split View"), table]

        def update_settings(self):
            self.change_orientation(self.view_list.get_value())

        def _get_configure_page_funcs(self):
            """
            Return a list of functions that create gtk elements to use in the 
            notebook pages of the Configure dialog
            
            :return: list of functions
            """
            def get_configure_page_funcs():
                retval = []
                if super(SidebarView, self).can_configure():
                    other = super(SidebarView, self)._get_configure_page_funcs()
                    if callable(other):
                        retval += other()
                    else:
                        retval += other
                func = self.gramplet_pane._get_configure_page_funcs()
                return [self.split_panel] + retval + func()
            return get_configure_page_funcs

    return SidebarView



for library, name, gramplets in views:
    try:
        exec("from %s import %s" % (library, name))
        exec("""class %sSidebar(extend(%s)):
    DEFAULT_GRAMPLETS = %s
""" % (name, name, gramplets))
    except:
        print "ERROR: unable to create '%s'" % name
        import traceback
        traceback.print_exc()
