"""Normalisation des événements sans dépendance à GTK."""

from types import SimpleNamespace

from descendants_timeline.gtk_draw_adapter import (
    queue_timeline_draw,
    scroll_timeline_direction_event,
    scroll_timeline_smooth_event,
)


def handle_button_press_event(widget, event, layout, controller, *, on_person_hits) -> bool:
    """Transmet les coordonnées locales au moteur et restitue son tuple intact."""
    from descendants_timeline.timeline_hit_testing import hit_test_person_bars

    transform = controller.transform
    if layout is None or transform is None:
        return False
    if hasattr(widget, "grab_focus"):
        widget.grab_focus()
    hit_options = {}
    # A realized DrawingArea supplies a local Cairo context with the same
    # target scale as its draw context. Only font measurement is performed.
    if callable(getattr(type(widget), "get_window", None)):
        window = widget.get_window()
        if window is not None:
            context = window.cairo_create()
            font_options = vars(widget).get("_timeline_font_options")
            if font_options is not None:
                context.set_font_options(font_options)
            allocation = widget.get_allocation()
            hit_options = dict(
                context=context, model=getattr(controller, "model", None),
                viewport_bounds=(0.0, float(allocation.width), 0.0, float(allocation.height)),
            )
    hits = hit_test_person_bars(layout, transform, event.x, event.y, **hit_options)
    on_person_hits(hits)
    return True


def handle_scroll_event(
    widget,
    event,
    controller,
    *,
    up_direction: int,
    down_direction: int,
    smooth_direction: int,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    if event.state & ctrl_mask and controller.transform is None:
        return False

    if event.direction in (up_direction, down_direction):
        return handle_direction_scroll_event_and_redraw(
            widget,
            event,
            controller,
            up_direction=up_direction,
            down_direction=down_direction,
            ctrl_mask=ctrl_mask,
            shift_mask=shift_mask,
        )
    if event.direction == smooth_direction:
        return handle_smooth_scroll_event_and_redraw(
            widget,
            event,
            controller,
            ctrl_mask=ctrl_mask,
            shift_mask=shift_mask,
        )

    return False


def handle_direction_scroll_event(
    widget,
    event,
    controller,
    *,
    up_direction: int,
    down_direction: int,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    return scroll_timeline_direction_event(
        widget,
        event,
        controller,
        up_direction=up_direction,
        down_direction=down_direction,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )


def handle_direction_scroll_event_and_redraw(
    widget,
    event,
    controller,
    *,
    up_direction: int,
    down_direction: int,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    handled = handle_direction_scroll_event(
        widget,
        event,
        controller,
        up_direction=up_direction,
        down_direction=down_direction,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )
    if handled:
        queue_timeline_draw(widget)

    return handled


def handle_smooth_scroll_event_and_redraw(
    widget,
    event,
    controller,
    *,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    handled = handle_smooth_scroll_event(
        widget,
        event,
        controller,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )
    if handled:
        queue_timeline_draw(widget)

    return handled


def handle_smooth_scroll_event(
    widget,
    event,
    controller,
    *,
    ctrl_mask: int,
    shift_mask: int,
) -> bool:
    success, delta_x, delta_y = event.get_scroll_deltas()
    if not success:
        return False

    normalized_event = SimpleNamespace(
        state=event.state,
        x=event.x,
        y=event.y,
        delta_y=float(delta_y),
    )
    return scroll_timeline_smooth_event(
        widget,
        normalized_event,
        controller,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )
