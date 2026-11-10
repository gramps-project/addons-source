from descendants_timeline.gramps_data_adapter import GrampsDataAdapter
from descendants_timeline.gramps_data_loader import GrampsDataLoader
from descendants_timeline.inference.temporal_inference_engine import TemporalInferenceEngine
from descendants_timeline.layout.layout_engine import LayoutEngine
from descendants_timeline.timeline.timeline_model_builder import TimelineModelBuilder
from descendants_timeline.timeline.timeline_model_composer import TimelineModelComposer
from descendants_timeline.traversal.descendance_traversal import DescendanceTraversal


def configure_descendants_timeline_view(
    view,
    data_loader,
    model_builder,
    layout_engine,
):
    view.configure_timeline(
        data_loader,
        model_builder,
        layout_engine,
    )
    return None


def make_descendants_timeline_integration_class(
    navigation_view_class,
    data_loader,
    model_builder,
    layout_engine,
):
    class DescendantsTimelineIntegrationView(navigation_view_class):
        def post(self):
            super().post()
            configure_descendants_timeline_view(
                self,
                data_loader,
                model_builder,
                layout_engine,
            )
            return None

    return DescendantsTimelineIntegrationView


def make_descendants_timeline_constructor_adapter(
    navigation_view_base,
    title,
    bookmark_type,
    nav_group=0,
):
    class DescendantsTimelineConstructorAdapter(navigation_view_base):
        def __init__(self, pdata, dbstate, uistate):
            super().__init__(
                title,
                pdata,
                dbstate,
                uistate,
                bookmark_type,
                nav_group,
            )

    return DescendantsTimelineConstructorAdapter


def load_and_compose_timeline_model(database, root_handle, name_formatter, *, diagnostics=None):
    """Collecte puis compose un modèle avec un diagnostic explicitement fourni."""
    arguments = {} if diagnostics is None else {"diagnostics": diagnostics}
    data = GrampsDataLoader(
        GrampsDataAdapter(database), name_formatter, **arguments,
    )(root_handle)
    return TimelineModelComposer(
        DescendanceTraversal(), TemporalInferenceEngine(), TimelineModelBuilder(),
        **arguments,
    )(data)


def load_compose_and_layout_timeline(database, root_handle, name_formatter, *, diagnostics=None):
    """Collecte, compose et calcule le layout avec un diagnostic facultatif commun."""
    arguments = {} if diagnostics is None else {"diagnostics": diagnostics}
    model = load_and_compose_timeline_model(database, root_handle, name_formatter, **arguments)
    layout = LayoutEngine().build(model, **arguments)
    return model, layout


def install_timeline_in_viewport(controller, model, layout, *, diagnostics=None):
    """Installe les objets existants et transmet le diagnostic du cadrage initial."""
    arguments = {} if diagnostics is None else {"diagnostics": diagnostics}
    return controller.set_model_and_layout(model, layout, **arguments)

