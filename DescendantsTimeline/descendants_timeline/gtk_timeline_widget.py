"""Construction de la surface graphique avec un module GTK fourni."""

from _i18n import _


def _get_representation_diagnostics(widget, model, layout):
    provider = vars(widget).get("_timeline_diagnostics_provider")
    return None if provider is None else provider(model, layout)


def build_timeline_navigation_widget(
    gtk_module, gdk_module, layout, controller, *, layout_provider=None, on_person_hits=None,
    selection_provider=None,
):
    hit_options = {} if on_person_hits is None else {"on_person_hits": on_person_hits}
    if selection_provider is not None:
        hit_options["selection_provider"] = selection_provider
    if layout_provider is not None:
        hit_options["layout_provider"] = layout_provider
    scrolled_window = create_timeline_view_widget(
        gtk_module, gdk_module, layout, controller, **hit_options,
    )
    header = gtk_module.DrawingArea()
    header.set_size_request(-1, 36)
    header.connect("draw", make_timeline_header_draw_callback(controller))
    root = gtk_module.Box(orientation=gtk_module.Orientation.VERTICAL)
    fit_button = gtk_module.Button(label=_("Fit to window"))

    def fit(widget):
        from descendants_timeline.gtk_draw_adapter import queue_timeline_draw

        get_state = getattr(gtk_module, "get_current_event_state", None)
        state = get_state() if get_state is not None else None
        if (isinstance(state, tuple) and len(state) == 2 and state[0]
                and state[1] & gdk_module.ModifierType.CONTROL_MASK):
            from descendants_timeline.gtk_draw_adapter import fit_selected_occurrence

            selected = selection_provider() if selection_provider is not None else None
            current_layout = layout_provider() if layout_provider is not None else layout
            fit_selected_occurrence(root._timeline_drawing_area, current_layout, controller,
                                    selected, on_person_hits=on_person_hits)
            return
        controller.fit_to_window()
        queue_timeline_draw(root._timeline_drawing_area)

    fit_button.connect("clicked", fit)
    root.pack_start(fit_button, False, False, 0)
    root.pack_start(header, False, False, 0)
    root.pack_start(scrolled_window, True, True, 0)
    root._timeline_header_area = header
    root._timeline_scrolled_window = scrolled_window
    root._timeline_drawing_area = scrolled_window._timeline_drawing_area
    root._timeline_drawing_area._timeline_header_area = header
    root._timeline_controller = controller
    root._timeline_fit_button = fit_button
    body = root._timeline_drawing_area
    body.set_can_focus(True)
    body.add_events(gdk_module.EventMask.KEY_PRESS_MASK)
    body.connect("key-press-event", make_timeline_key_press_callback(
        controller, left_key=gdk_module.KEY_Left, right_key=gdk_module.KEY_Right,
    ))
    adjustment = gtk_module.Adjustment()
    scrollbar = gtk_module.Scrollbar(orientation=gtk_module.Orientation.HORIZONTAL, adjustment=adjustment)

    def changed(adjustment):
        from descendants_timeline.gtk_draw_adapter import queue_timeline_draw

        controller.set_horizontal_position(adjustment.get_value())
        queue_timeline_draw(body)

    handler = adjustment.connect("value-changed", changed)

    def sync_horizontal():
        state = controller.horizontal_scroll_state()
        fit_button.set_sensitive(state is not None)
        adjustment.handler_block(handler)
        try:
            if state is None:
                adjustment.configure(0.0, 0.0, 1.0, 0.1, 0.9, 1.0)
                scrollbar.set_sensitive(False)
            else:
                value, lower, upper, page = state
                adjustment.configure(value, lower, upper, page * 0.1, page * 0.9, page)
                scrollbar.set_sensitive(upper - lower > page)
        finally:
            adjustment.handler_unblock(handler)

    body._timeline_sync_horizontal = sync_horizontal
    root._timeline_horizontal_adjustment = adjustment
    root._timeline_horizontal_scrollbar = scrollbar
    root.pack_start(scrollbar, False, False, 0)
    sync_horizontal()
    from descendants_timeline.gtk_timeline_diagnostics import enable_gtk_geometry_diagnostic

    enable_gtk_geometry_diagnostic(root)
    return root


def make_timeline_header_draw_callback(controller):
    def callback(widget, context):
        from descendants_timeline.timeline_header_renderer import draw_timeline_header

        transform = controller.transform
        if transform is None:
            return False
        width = float(widget.get_allocated_width())
        if width <= 0.0:
            return False
        completed = vars(widget).get("_timeline_header_draw_completed") if hasattr(widget, "__dict__") else None
        current_model = getattr(controller, "model", None) if completed is not None else None
        current_layout = getattr(controller, "layout", None) if completed is not None else None
        diagnostics = (
            _get_representation_diagnostics(widget, current_model, current_layout)
            if current_model is not None and current_layout is not None else None
        )
        clock = diagnostics.first_header_draw_clock if diagnostics is not None else None
        started_at = clock() if clock is not None else None
        draw_timeline_header(context, transform, width)
        duration = max(0.0, clock() - started_at) if clock is not None else None
        if (
            diagnostics is not None
            and controller.model is current_model
            and controller.layout is current_layout
            and controller.transform is transform
        ):
            timing_options = {} if started_at is None else {"started_at": started_at, "duration": duration}
            completed(current_model, current_layout, diagnostics, **timing_options)
        drawn = vars(widget).get("_timeline_cooperative_drawn") if hasattr(widget, "__dict__") else None
        if (drawn is not None and widget.get_mapped() and controller.transform is transform
                and widget.get_allocated_height() > 0):
            drawn("header", controller.model, controller.layout)
        return False

    return callback


def create_timeline_view_widget(
    gtk_module, gdk_module, layout, controller, *, layout_provider=None, on_person_hits=None,
    selection_provider=None,
):
    hit_options = {} if on_person_hits is None else {"on_person_hits": on_person_hits}
    if selection_provider is not None:
        hit_options["selection_provider"] = selection_provider
    if layout_provider is None:
        drawing_area = create_timeline_drawing_area_from_gdk(
            gtk_module, gdk_module, layout, controller, **hit_options,
        )
    else:
        drawing_area = create_timeline_drawing_area_from_gdk(
            gtk_module, gdk_module, layout, controller, layout_provider=layout_provider,
            **hit_options,
        )
    return create_timeline_scrolled_window(gtk_module, drawing_area)


def create_timeline_scrolled_window(gtk_module, drawing_area):
    scrolled_window = gtk_module.ScrolledWindow()
    # Horizontal position is owned by ViewportTransform, not GtkViewport.
    scrolled_window.set_policy(gtk_module.PolicyType.NEVER, gtk_module.PolicyType.AUTOMATIC)
    scrolled_window.add(drawing_area)
    scrolled_window._timeline_drawing_area = drawing_area
    return scrolled_window


def create_timeline_drawing_area_from_gdk(
    gtk_module, gdk_module, layout, controller, *, layout_provider=None, on_person_hits=None,
    selection_provider=None,
):
    constants = get_timeline_gdk_constants(gdk_module)
    if selection_provider is not None:
        constants["selection_provider"] = selection_provider
    if on_person_hits is not None:
        constants["button_press_mask"] = gdk_module.EventMask.BUTTON_PRESS_MASK
        constants["on_person_hits"] = on_person_hits
    if layout_provider is not None:
        return create_configured_timeline_drawing_area(
            gtk_module, layout, controller, **constants, layout_provider=layout_provider,
        )
    return create_configured_timeline_drawing_area(
        gtk_module, layout, controller, **constants,
    )


def get_timeline_gdk_constants(gdk_module):
    return {
        "scroll_mask": gdk_module.EventMask.SCROLL_MASK,
        "smooth_scroll_mask": gdk_module.EventMask.SMOOTH_SCROLL_MASK,
        "up_direction": gdk_module.ScrollDirection.UP,
        "down_direction": gdk_module.ScrollDirection.DOWN,
        "smooth_direction": gdk_module.ScrollDirection.SMOOTH,
        "ctrl_mask": gdk_module.ModifierType.CONTROL_MASK,
        "shift_mask": gdk_module.ModifierType.SHIFT_MASK,
    }


def make_timeline_draw_callback(
    layout, controller, *, layout_provider=None, line_cap_butt=None,
    selection_provider=None,
):
    def callback(widget, context):
        from descendants_timeline.gtk_draw_adapter import draw_timeline

        current_layout = (
            layout_provider()
            if layout_provider is not None
            else layout
        )
        if current_layout is None:
            return False
        selection_options = {}
        if selection_provider is not None:
            selected = selection_provider()
            if selected is not None:
                selection_options["selected_person_placement"] = selected
        completed = vars(widget).get("_timeline_body_draw_completed") if hasattr(widget, "__dict__") else None
        current_model = getattr(controller, "model", None) if completed is not None else None
        transform = controller.transform if completed is not None else None
        diagnostics = (
            _get_representation_diagnostics(widget, current_model, current_layout)
            if current_model is not None and transform is not None else None
        )
        clock = diagnostics.first_body_draw_clock if diagnostics is not None else None
        started_at = clock() if clock is not None else None
        if line_cap_butt is not None:
            result = draw_timeline(
                widget, context, current_layout, controller, line_cap_butt=line_cap_butt,
                **selection_options,
            )
        else:
            result = draw_timeline(widget, context, current_layout, controller, **selection_options)
        duration = max(0.0, clock() - started_at) if clock is not None else None
        if diagnostics is not None and controller.model is current_model and controller.transform is transform:
            timing_options = {} if started_at is None else {"started_at": started_at, "duration": duration}
            completed(current_model, current_layout, diagnostics, **timing_options)
        drawn = vars(widget).get("_timeline_cooperative_drawn") if hasattr(widget, "__dict__") else None
        if (drawn is not None and widget.get_mapped() and transform is not None and controller.transform is transform
                and controller.layout is current_layout
                and widget.get_allocated_width() > 0 and widget.get_allocated_height() > 0):
            drawn("body", current_model, current_layout)
        return result

    return callback


def make_timeline_scroll_callback(
    controller,
    *,
    up_direction: int,
    down_direction: int,
    smooth_direction: int,
    ctrl_mask: int,
    shift_mask: int,
):
    def callback(widget, event):
        from descendants_timeline.gtk_event_bridge import handle_scroll_event

        return handle_scroll_event(
            widget,
            event,
            controller,
            up_direction=up_direction,
            down_direction=down_direction,
            smooth_direction=smooth_direction,
            ctrl_mask=ctrl_mask,
            shift_mask=shift_mask,
        )

    return callback


def make_timeline_size_allocate_callback(controller):
    def callback(widget, allocation):
        from descendants_timeline.gtk_draw_adapter import allocate_timeline_width

        return allocate_timeline_width(widget, allocation, controller)

    return callback


def make_timeline_key_press_callback(controller, *, left_key, right_key):
    def callback(widget, event):
        from descendants_timeline.gtk_draw_adapter import queue_timeline_draw

        if not widget.has_focus() or event.state or event.keyval not in (left_key, right_key):
            return False
        if controller.horizontal_scroll_state() is None:
            return False
        controller.pan_horizontal(-0.1 if event.keyval == left_key else 0.1)
        queue_timeline_draw(widget)
        return True

    return callback


def make_timeline_button_press_callback(layout, controller, *, layout_provider=None, on_person_hits):
    def callback(widget, event):
        from descendants_timeline.gtk_event_bridge import handle_button_press_event

        current_layout = layout_provider() if layout_provider is not None else layout
        return handle_button_press_event(
            widget, event, current_layout, controller, on_person_hits=on_person_hits,
        )

    return callback


def create_timeline_drawing_area(
    gtk_module,
    *,
    scroll_mask: int | None = None,
    smooth_scroll_mask: int | None = None,
    draw_callback=None,
    scroll_callback=None,
    size_allocate_callback=None,
    button_press_mask: int | None = None,
    button_press_callback=None,
):
    drawing_area = gtk_module.DrawingArea()
    if scroll_mask is not None or smooth_scroll_mask is not None or button_press_mask is not None:
        mask = (scroll_mask if scroll_mask is not None else 0) | (
            smooth_scroll_mask if smooth_scroll_mask is not None else 0
        )
        mask |= button_press_mask if button_press_mask is not None else 0
        drawing_area.add_events(mask)
    if draw_callback is not None:
        drawing_area.connect("draw", draw_callback)
    if scroll_callback is not None:
        drawing_area.connect("scroll-event", scroll_callback)
    if size_allocate_callback is not None:
        drawing_area.connect("size-allocate", size_allocate_callback)
    if button_press_callback is not None:
        drawing_area.connect("button-press-event", button_press_callback)
    return drawing_area


def create_configured_timeline_drawing_area(
    gtk_module,
    layout,
    controller,
    *,
    scroll_mask: int,
    smooth_scroll_mask: int,
    up_direction: int,
    down_direction: int,
    smooth_direction: int,
    ctrl_mask: int,
    shift_mask: int,
    layout_provider=None,
    button_press_mask: int | None = None,
    on_person_hits=None,
    selection_provider=None,
):
    import cairo

    selection_options = {} if selection_provider is None else {"selection_provider": selection_provider}
    if layout_provider is None:
        draw_callback = make_timeline_draw_callback(
            layout, controller, line_cap_butt=cairo.LINE_CAP_BUTT,
            **selection_options,
        )
    else:
        draw_callback = make_timeline_draw_callback(
            layout, controller, layout_provider=layout_provider,
            line_cap_butt=cairo.LINE_CAP_BUTT,
            **selection_options,
        )
    scroll_callback = make_timeline_scroll_callback(
        controller,
        up_direction=up_direction,
        down_direction=down_direction,
        smooth_direction=smooth_direction,
        ctrl_mask=ctrl_mask,
        shift_mask=shift_mask,
    )
    size_allocate_callback = make_timeline_size_allocate_callback(controller)
    hit_options = {}
    if on_person_hits is not None:
        hit_options = {
            "button_press_mask": button_press_mask,
            "button_press_callback": make_timeline_button_press_callback(
                layout, controller, layout_provider=layout_provider, on_person_hits=on_person_hits,
            ),
        }
    return create_timeline_drawing_area(
        gtk_module,
        scroll_mask=scroll_mask,
        smooth_scroll_mask=smooth_scroll_mask,
        draw_callback=draw_callback,
        scroll_callback=scroll_callback,
        size_allocate_callback=size_allocate_callback,
        **hit_options,
    )
