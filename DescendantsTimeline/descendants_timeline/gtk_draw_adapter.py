"""Adaptateur de dessin utilisable sans dépendance à GTK."""

from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.timeline_renderer import draw_temporal_guides, render_viewport
from descendants_timeline.viewport_controller import ViewportController


VERTICAL_SCROLL_PIXELS_PER_STEP = 40.0


def queue_timeline_draw(widget):
    """Invalide le corps et son en-tête associé, s'il existe."""
    sync = vars(widget).get("_timeline_sync_horizontal")
    if sync is not None:
        sync()
    widget.queue_draw()
    header = vars(widget).get("_timeline_header_area")
    if header is not None:
        header.queue_draw()


def scroll_modifiers_from_state(
    state: int,
    *,
    ctrl_mask: int,
    shift_mask: int,
) -> tuple[bool, bool]:
    return (
        bool(state & ctrl_mask),
        bool(state & shift_mask),
    )


def scroll_direction_to_steps(
    direction: object,
    *,
    up_direction: object,
    down_direction: object,
) -> int | None:
    if direction == down_direction:
        return -1
    if direction == up_direction:
        return 1
    return None


def scroll_steps_to_vertical_pixels(steps: int) -> float:
    return -steps * VERTICAL_SCROLL_PIXELS_PER_STEP


def smooth_scroll_delta_to_vertical_pixels(delta_y: float) -> float:
    return float(delta_y) * VERTICAL_SCROLL_PIXELS_PER_STEP


def draw_timeline(
    widget: object,
    context: object,
    layout: TimelineLayout,
    controller: ViewportController,
    *, line_cap_butt=None, selected_person_placement=None,
) -> bool:
    if callable(getattr(type(context), "get_font_options", None)):
        widget._timeline_font_options = context.get_font_options()
    if controller.transform is not None and callable(getattr(type(widget), "get_allocation", None)):
        allocation = widget.get_allocation()
        draw_temporal_guides(context, controller.transform, float(allocation.width), float(allocation.height))
    selection_options = (
        {} if selected_person_placement is None
        else {"selected_person_placement": selected_person_placement}
    )
    if line_cap_butt is None:
        render_viewport(context, layout, controller, **selection_options)
    else:
        render_viewport(context, layout, controller, line_cap_butt=line_cap_butt, **selection_options)
    return False


def fit_selected_occurrence(widget, layout, controller, selected, *, on_person_hits=None) -> bool:
    """Mesure et cadre l'objet sélectionné avec les dimensions réelles du corps."""
    if selected is None:
        return False
    if (layout is None or controller.layout is not layout
            or not any(item is selected for item in layout.person_placements)):
        if on_person_hits is not None:
            on_person_hits(())
        return False
    if controller.transform is None:
        return False
    window = widget.get_window()
    if window is None:
        return False
    context = window.cairo_create()
    font_options = vars(widget).get("_timeline_font_options")
    if font_options is not None:
        context.set_font_options(font_options)
    allocation = widget.get_allocation()
    from descendants_timeline.timeline_renderer import measure_person_graphics

    def measure(transform):
        return measure_person_graphics(context, selected, transform, model=controller.model)

    changed = controller.fit_to_placement(selected, float(allocation.width), float(allocation.height), measure)
    if changed:
        queue_timeline_draw(widget)
    return changed


def allocate_timeline_width(
    widget: object,
    allocation: object,
    controller: ViewportController,
) -> None:
    controller.allocate_width(float(allocation.width))
    if vars(widget).get("_timeline_header_area") is not None:
        queue_timeline_draw(widget)


def scroll_timeline_vertical(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    delta_screen_y: float,
) -> bool:
    controller.scroll_vertical(delta_screen_y)
    return True


def scroll_timeline_smooth_vertical(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    delta_y: float,
) -> bool:
    return scroll_timeline_vertical(
        widget,
        event,
        controller,
        delta_screen_y=smooth_scroll_delta_to_vertical_pixels(delta_y),
    )


def scroll_timeline_smooth_zoom(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    delta_y: float,
    horizontal_only: bool,
) -> bool:
    controller.zoom_at_cursor(
        float(event.x),
        float(event.y),
        -float(delta_y),
        horizontal_only=horizontal_only,
    )
    return True


def scroll_timeline_smooth(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    delta_y: float,
    ctrl: bool,
    shift: bool,
) -> bool:
    if not ctrl:
        return scroll_timeline_smooth_vertical(
            widget,
            event,
            controller,
            delta_y=delta_y,
        )
    return scroll_timeline_smooth_zoom(
        widget,
        event,
        controller,
        delta_y=delta_y,
        horizontal_only=False,
    )


def scroll_timeline_smooth_event(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    ctrl, shift = scroll_modifiers_from_state(
        event.state,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )
    return scroll_timeline_smooth(
        widget,
        event,
        controller,
        delta_y=event.delta_y,
        ctrl=ctrl,
        shift=shift,
    )


def scroll_timeline_direction_event(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    up_direction: int,
    down_direction: int,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    steps = scroll_direction_to_steps(
        event.direction,
        up_direction=up_direction,
        down_direction=down_direction,
    )
    if steps is None:
        return False

    ctrl, shift = scroll_modifiers_from_state(
        event.state,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )
    return scroll_timeline(
        widget,
        event,
        controller,
        steps=steps,
        ctrl=ctrl,
        shift=shift,
    )


def scroll_timeline(
    widget: object,
    event: object,
    controller: ViewportController,
    *,
    steps: int,
    horizontal_only: bool = False,
    ctrl: bool | None = None,
    shift: bool | None = None,
) -> bool:
    if ctrl is False and shift in (False, True):
        return scroll_timeline_vertical(
            widget,
            event,
            controller,
            delta_screen_y=scroll_steps_to_vertical_pixels(steps),
        )
    if ctrl is True:
        controller.zoom_at_cursor(
            float(event.x),
            float(event.y),
            steps,
            horizontal_only=False,
        )
        return True
    controller.zoom_at_cursor(
        float(event.x),
        float(event.y),
        steps,
        horizontal_only=horizontal_only,
    )
    return True
