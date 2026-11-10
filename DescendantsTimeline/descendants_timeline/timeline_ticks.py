import math

from datetime import date

from descendants_timeline.layout.timeline_scale import TimelineScale
from descendants_timeline.viewport_transform import ViewportTransform

YEAR_TICK_STEPS = (1, 2, 5, 10, 20, 25, 50, 100, 200, 500)
MIN_TICK_SPACING_PX = 80
INITIAL_FRAME_WIDTHS = (
    10, 20, 25, 50, 75, 100,
    150, 200, 225, 250, 300, 400, 500,
)


def project_year_tick_x(year: int, transform: ViewportTransform) -> float:
    """Projette le 1er janvier avec la même transformation que les barres."""
    logical_x = TimelineScale().date_to_x(date(year, 1, 1))
    screen_x, _ = transform.logical_to_screen(logical_x, 0.0)
    return screen_x


def _guide_tick_stride(visible_intervals: float) -> int:
    """Préfère les multiples simples, puis environ sept repères visibles."""
    ideal = max(1.0, visible_intervals / 7.0)
    decade = 10 ** math.floor(math.log10(ideal))
    simple = {1, decade, 2 * decade, 5 * decade, 10 * decade}
    candidates = simple | {math.floor(ideal), math.ceil(ideal)}
    # Une marge sous dix tient compte du repère éventuellement présent au bord.
    return min(candidates, key=lambda stride: (
        not 5.0 <= visible_intervals / stride <= 9.0,
        stride not in simple,
        abs(visible_intervals / stride - 7.0),
        stride,
    ))


def visible_year_ticks(
    transform: ViewportTransform, viewport_width: float, *, guides: bool = False,
) -> tuple[int, ...]:
    """Années principales visibles, avec les limites et le pas historiques."""
    if viewport_width <= 0.0:
        return ()
    left, _ = transform.screen_to_logical(0.0, 0.0)
    right, _ = transform.screen_to_logical(viewport_width, 0.0)
    scale = TimelineScale()
    minimum = scale.date_to_x(date.min)
    maximum = scale.date_to_x(date.max)
    if right < minimum or left > maximum:
        return ()
    start_year = scale.x_to_date(max(left, minimum)).year
    end_year = scale.x_to_date(min(right, maximum)).year
    # Approximation pour la densité uniquement ; chaque X reste projeté exactement.
    visible_years = (right - left) / 365.2425
    step = select_year_tick_step(visible_years, viewport_width)
    if guides:
        step *= _guide_tick_stride(visible_years / step)
    return tuple(year for year in year_ticks_between(start_year, end_year, step)
                 if 0.0 <= project_year_tick_x(year, transform) <= viewport_width)


def year_frame_to_ordinals(
    start_year: int,
    end_year: int,
) -> tuple[float, float]:
    if start_year >= end_year:
        raise ValueError(
            "start_year must precede end_year"
        )
    return (
        float(date(start_year, 1, 1).toordinal()),
        float(date(end_year, 1, 1).toordinal()),
    )


def select_year_tick_step(visible_years, viewport_width):
    if visible_years <= 0:
        raise ValueError("visible_years must be positive")
    if viewport_width <= 0:
        raise ValueError("viewport_width must be positive")
    for step in YEAR_TICK_STEPS:
        spacing = viewport_width * step / visible_years
        if spacing >= MIN_TICK_SPACING_PX:
            return step
    return YEAR_TICK_STEPS[-1]


def year_ticks_between(start_year, end_year, step):
    if step <= 0:
        raise ValueError("step must be positive")
    if start_year > end_year:
        raise ValueError("start_year must not exceed end_year")
    first_year = -(-start_year // step) * step
    return tuple(range(first_year, end_year + 1, step))


def select_initial_frame_width(required_years):
    if required_years <= 0:
        raise ValueError("required_years must be positive")

    for width in INITIAL_FRAME_WIDTHS:
        if width >= required_years:
            return width

    return INITIAL_FRAME_WIDTHS[-1]


def position_fixed_width_year_frame(
    start_year,
    end_year,
    frame_width,
    step,
):
    if start_year >= end_year:
        raise ValueError("start_year must precede end_year")
    if frame_width <= 0:
        raise ValueError("frame_width must be positive")
    if step <= 0:
        raise ValueError("step must be positive")
    if frame_width % step != 0:
        raise ValueError("frame_width must be a multiple of step")

    duration = end_year - start_year
    margin = duration * 0.05
    lower_bound = start_year - margin
    upper_bound = end_year + margin

    first_index = math.ceil(
        (upper_bound - frame_width) / step
    )
    last_index = math.floor(lower_bound / step)

    if first_index > last_index:
        raise ValueError(
            "no aligned frame fits the requested width"
        )

    ideal_start = (
        lower_bound + upper_bound - frame_width
    ) / 2

    best_index = min(
        range(first_index, last_index + 1),
        key=lambda index: (
            abs(index * step - ideal_start),
            index,
        ),
    )

    frame_start = best_index * step

    return (
        int(frame_start),
        int(frame_start + frame_width),
    )


def first_fitting_frame_width(
    start_year,
    end_year,
    minimum_width,
    step,
):
    if minimum_width <= 0:
        raise ValueError(
            "minimum_width must be positive"
        )
    if step <= 0:
        raise ValueError(
            "step must be positive"
        )

    for width in INITIAL_FRAME_WIDTHS:
        if width < minimum_width:
            continue

        if width % step != 0:
            continue

        try:
            position_fixed_width_year_frame(
                start_year=start_year,
                end_year=end_year,
                frame_width=width,
                step=step,
            )
        except ValueError:
            continue

        return width

    raise ValueError(
        "no fitting frame width available"
    )


def aesthetic_initial_frame_width(compact_width):
    if compact_width == 75:
        return 100
    return compact_width


def select_initial_year_frame(start_year, end_year, viewport_width):
    if start_year >= end_year:
        raise ValueError(
            "start_year must precede end_year"
        )

    if viewport_width <= 0:
        raise ValueError(
            "viewport_width must be positive"
        )

    duration = end_year - start_year

    if duration * 1.10 > 500:
        frame_start = math.floor(start_year / 50) * 50
        return frame_start, frame_start + 500

    minimum_width = select_initial_frame_width(
        duration * 1.10
    )

    try:
        compact_width = first_fitting_frame_width(
            start_year,
            end_year,
            minimum_width,
            25,
        )
    except ValueError as exc:
        if str(exc) != "no fitting frame width available":
            raise

        frame_start = math.floor(start_year / 50) * 50
        return frame_start, frame_start + 500

    frame_width = aesthetic_initial_frame_width(
        compact_width
    )

    for step in (50, 25):
        if frame_width % step != 0:
            continue

        try:
            return position_fixed_width_year_frame(
                start_year,
                end_year,
                frame_width,
                step,
            )
        except ValueError:
            continue

    raise ValueError(
        "no aligned initial year frame fits the selected width"
    )
