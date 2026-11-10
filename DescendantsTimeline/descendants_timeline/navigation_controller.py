def zoom_factor_after_steps(current_zoom, steps):
    return current_zoom * (1.10 ** steps)


from descendants_timeline.viewport_transform import ViewportTransform


def initial_viewport_transform(
    x_start: float,
    x_end: float,
    viewport_width: float,
) -> ViewportTransform:
    return ViewportTransform(
        origin_x=x_start,
        origin_y=0.0,
        zoom_x=initial_horizontal_zoom(x_start, x_end, viewport_width),
        zoom_y=1.0,
    )


def resize_viewport_preserving_center(
    transform: ViewportTransform,
    old_width: float,
    new_width: float,
) -> ViewportTransform:
    if old_width <= 0:
        raise ValueError(
            "old_width must be positive"
        )
    if new_width <= 0:
        raise ValueError(
            "new_width must be positive"
        )
    return ViewportTransform(
        origin_x=transform.origin_x + (old_width - new_width) / (2.0 * transform.effective_scale_x),
        origin_y=transform.origin_y,
        zoom_x=transform.zoom_x,
        zoom_y=transform.zoom_y,
        base_scale_x=transform.base_scale_x,
    )


def capped_vertical_zoom(current_zoom, steps):
    requested_zoom = zoom_factor_after_steps(current_zoom, steps)
    return max(0.20, min(1.0, requested_zoom))


def initial_horizontal_zoom(
    x_start: float,
    x_end: float,
    viewport_width: float,
) -> float:
    if viewport_width <= 0:
        raise ValueError(
            "viewport_width must be positive"
        )
    if x_start >= x_end:
        raise ValueError(
            "x_start must precede x_end"
        )
    return viewport_width / (x_end - x_start)


def horizontal_zoom_limits(viewport_width):
    if viewport_width <= 0:
        raise ValueError("viewport_width must be positive")
    minimum_zoom = viewport_width / (500 * 365.2425)
    maximum_zoom = viewport_width / (10 * 365.2425)
    return minimum_zoom, maximum_zoom


def capped_horizontal_zoom(current_zoom, steps, viewport_width):
    minimum_zoom, maximum_zoom = horizontal_zoom_limits(
        viewport_width=viewport_width,
    )
    if steps < 0 and current_zoom < minimum_zoom:
        return current_zoom
    if steps > 0 and current_zoom > maximum_zoom:
        return current_zoom
    requested_zoom = zoom_factor_after_steps(current_zoom, steps)
    if steps > 0 and current_zoom < minimum_zoom and requested_zoom < minimum_zoom:
        return requested_zoom
    if steps < 0 and current_zoom > maximum_zoom and requested_zoom > maximum_zoom:
        return requested_zoom
    return max(minimum_zoom, min(maximum_zoom, requested_zoom))
