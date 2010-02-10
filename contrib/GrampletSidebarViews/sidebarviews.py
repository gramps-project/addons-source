import gtk

from relview import RelationshipView
from eventview import EventView
from familyview import FamilyView
from fanchartview import FanChartView
from geoview import GeoView
from htmlrenderer import HtmlView
from mediaview import MediaView
from noteview import NoteView
from pedigreeview import PedigreeView
from pedigreeviewext import PedigreeViewExt
from personlistview import PersonListView
from persontreeview import PersonTreeView
from placelistview import PlaceListView
from placetreeview import PlaceTreeView
from repoview import RepositoryView
from sourceview import SourceView

from gui.widgets.grampletpane import GrampletPane

def extend(class_):
    class SidebarView(class_):
        def on_delete(self):
            super(SidebarView, self).on_delete()
            self.gramplet_pane.on_delete()

        def build_widget(self):
            container = super(SidebarView, self).build_widget()
            widget = gtk.HPaned()
            self.gramplet_pane = \
                GrampletPane("%s_%s" % (self.navigation_type(), self.__class__.__name__), 
                             self, self.dbstate, self.uistate, 
                             column_count=1,
                             default_gramplets=["Attributes Gramplet"])
            widget.pack1(container, resize=True, shrink=True)
            widget.pack2(self.gramplet_pane, resize=True, shrink=True)
            self.gramplet_pane.set_size_request(self.gramplet_pane.pane_width, -1)
            container.set_size_request(self.gramplet_pane.pane_other_width, -1)
            widget.set_position(self.gramplet_pane.pane_position)
            widget.connect("notify", self.move_handle)
            return widget

        def move_handle(self, widget, notify_type):
            if notify_type.name == "position-set":
                self.gramplet_pane.pane_other_width = widget.get_child1().allocation.width
                self.gramplet_pane.pane_width = widget.get_child2().allocation.width
                self.gramplet_pane.pane_position = widget.get_position()

        def ui_definition(self):
            uid = super(SidebarView, self).ui_definition()
            uid = uid.replace("</popup>", """            <menuitem action="AddGramplet"/>
                <menuitem action="RestoreGramplet"/>
                <separator/>
              </popup>
                """)
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

    return SidebarView

class RelationshipViewSidebar(extend(RelationshipView)):
    """
    """

class EventViewSidebar(extend(EventView)):
    """
    EventView with Gramplet Sidebar.
    """

class FamilyViewSidebar(extend(FamilyView)):
    """
    FamilyView with Gramplet Sidebar.
    """

class FanChartViewSidebar(extend(FanChartView)):
    """
    FanChartView with Gramplet Sidebar.
    """

class GeoViewSidebar(extend(GeoView)):
    """
    GeoView with Gramplet Sidebar.
    """

class HtmlViewSidebar(extend(HtmlView)):
    """
    HtmlView with Gramplet Sidebar.
    """

class MediaViewSidebar(extend(MediaView)):
    """
    MediaView with Gramplet Sidebar.
    """

class NoteViewSidebar(extend(NoteView)):
    """
    NoteView with Gramplet Sidebar.
    """

class PedigreeViewSidebar(extend(PedigreeView)):
    """
    PedigreeView with Gramplet Sidebar.
    """

class PedigreeViewExtSidebar(extend(PedigreeViewExt)):
    """
    PedigreeViewext with Gramplet Sidebar.
    """

class PersonListViewSidebar(extend(PersonListView)):
    """
    PersonlistView with Gramplet Sidebar.
    """

class PersonTreeViewSidebar(extend(PersonTreeView)):
    """
    PersontreeView with Gramplet Sidebar.
    """

class PlaceListViewSidebar(extend(PlaceListView)):
    """
    PlacelistView with Gramplet Sidebar.
    """

class PlaceTreeViewSidebar(extend(PlaceTreeView)):
    """
    PlacetreeView with Gramplet Sidebar.
    """

class RepositoryViewSidebar(extend(RepositoryView)):
    """
    RepoView with Gramplet Sidebar.
    """

class SourceViewSidebar(extend(SourceView)):
    """
    SourceView with Gramplet Sidebar.
    """

