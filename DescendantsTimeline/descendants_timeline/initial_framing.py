from contextlib import nullcontext
from datetime import date

from descendants_timeline.layout.represented_date_bounds import represented_date_bounds
from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.navigation_controller import initial_viewport_transform
from descendants_timeline.timeline.timeline_model import TimelineModel
from descendants_timeline.timeline_ticks import select_initial_year_frame, year_frame_to_ordinals
from descendants_timeline.viewport_transform import ViewportTransform


def represented_dates_to_year_frame(
    start_date: date,
    end_date: date,
) -> tuple[int, int]:
    if start_date > end_date:
        raise ValueError(
            "start_date must not follow end_date"
        )
    return (
        start_date.year,
        end_date.year + 1,
    )


def initial_transform_for_layout(
    model: TimelineModel,
    layout: TimelineLayout,
    viewport_width: float,
    *, diagnostics=None,
) -> ViewportTransform | None:
    with (
        diagnostics.phase("framing")
        if diagnostics is not None
        else nullcontext()
    ):
        bounds = represented_date_bounds(model, layout)
        if bounds is None:
            return None
        start_year, end_year = represented_dates_to_year_frame(*bounds)
        frame_start, frame_end = select_initial_year_frame(
            start_year, end_year, viewport_width,
        )
        x_start, x_end = year_frame_to_ordinals(frame_start, frame_end)
        transform = initial_viewport_transform(x_start, x_end, viewport_width)
        transform.base_scale_x = transform.zoom_x
        transform.zoom_x = 1.0
        return transform
