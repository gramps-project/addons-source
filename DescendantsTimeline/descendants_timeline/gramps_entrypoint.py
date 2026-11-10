"""Point d'entrée callable Gramps ; dépendances assemblées par instance de vue."""

from gi.repository import Gdk, Gtk
from gramps.gen.display.name import displayer as name_displayer
from gramps.gui.views.bookmarks import PersonBookmarks
from gramps.gui.views.navigationview import NavigationView

from descendants_timeline.gramps_data_adapter import GrampsDataAdapter
from descendants_timeline.gramps_data_loader import GrampsDataLoader
from descendants_timeline.gramps_navigation_view import make_descendants_timeline_view_class
from descendants_timeline.gramps_view_composition import (
    make_descendants_timeline_constructor_adapter,
    make_descendants_timeline_integration_class,
)
from descendants_timeline.inference.temporal_inference_engine import TemporalInferenceEngine
from descendants_timeline.layout.layout_engine import LayoutEngine
from descendants_timeline.timeline.timeline_model_builder import TimelineModelBuilder
from descendants_timeline.timeline.timeline_model_composer import TimelineModelComposer
from descendants_timeline.traversal.descendance_traversal import DescendanceTraversal
from descendants_timeline.viewport_controller import ViewportController


def create_descendants_timeline_view(pdata, dbstate, uistate):
    """Construit une vue dont chaque collecte utilise la base courante."""
    controller = ViewportController(None, None)

    def loader(root_handle, *, diagnostics=None):
        if not dbstate.is_open():
            raise RuntimeError("No genealogy database is open")
        database = dbstate.db
        return GrampsDataLoader(
            GrampsDataAdapter(database), name_displayer.display,
            **({"diagnostics": diagnostics} if diagnostics is not None else {}),
        )(root_handle)

    composer = TimelineModelComposer(
        DescendanceTraversal(), TemporalInferenceEngine(), TimelineModelBuilder(),
    )
    layout_engine = LayoutEngine()

    def root_handle_is_valid(handle):
        return dbstate.is_open() and dbstate.db.has_person_handle(handle)

    def prepare_cooperatively(view, database, root):
        reader = GrampsDataLoader(GrampsDataAdapter(database), name_displayer.display)
        data = yield from reader._iter_load(root)
        yield "Parcours de la descendance"
        model = yield from composer._iter_compose(data)
        yield "Placement sur la chronologie"
        return model, view.build_timeline_layout(model, layout_engine)

    def make_driver(view, widget):
        from gi.repository import Atk, GLib
        from descendants_timeline.cooperative_timeline_load import CooperativeTimelineLoad

        from descendants_timeline.timeline_menu_actions import TimelineMenuActions

        driver = CooperativeTimelineLoad(
            view, widget, Gtk, GLib, prepare_cooperatively, menu_actions=TimelineMenuActions(view),
        )
        accessible = driver.activity.get_accessible()
        accessible.set_name("Chargement de la chronologie")
        accessible.add_relationship(Atk.RelationType.LABELLED_BY, driver.label.get_accessible())
        return driver

    navigation_view = make_descendants_timeline_view_class(
        NavigationView, Gtk, Gdk, None, controller,
        root_handle_is_valid=root_handle_is_valid, cooperative_driver=make_driver,
    )
    constructor_adapter = make_descendants_timeline_constructor_adapter(
        navigation_view, "Descendants Timeline", PersonBookmarks,
    )
    entry_view = make_descendants_timeline_integration_class(
        constructor_adapter, loader, composer, layout_engine,
    )
    return entry_view(pdata, dbstate, uistate)
