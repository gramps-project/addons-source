"""Recherche des personnes dans les zones projetées, par priorité visuelle."""

from descendants_timeline.layout.person_placement import PersonPlacement
from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.timeline_geometry import project_person_life_bar_selection_rectangle
from descendants_timeline.timeline_renderer import build_colored_person_life_bar_command, measure_person_label
from descendants_timeline.viewport_transform import ViewportTransform


def _contains(bounds, x, y):
    if bounds is None:
        return False
    left, right, top, bottom = bounds
    return left < right and top < bottom and left <= x <= right and top <= y <= bottom


def hit_test_person_bars(
    layout: TimelineLayout,
    transform: ViewportTransform,
    screen_x: float,
    screen_y: float,
    *, context=None, model=None, viewport_bounds=None,
) -> tuple[PersonPlacement, ...]:
    """Retourne tous les candidats du meilleur niveau, sans départager leur ordre."""
    if viewport_bounds is not None and not _contains(viewport_bounds, screen_x, screen_y):
        return ()
    bar_hits, name_hits, extension_hits = [], [], []
    for placement in layout.person_placements:
        command = build_colored_person_life_bar_command(placement, transform, model=model)
        if command is None:
            continue
        geometry = command.duration_geometry
        if geometry is not None and _contains(geometry.bounds, screen_x, screen_y):
            bar_hits.append(placement)
        if context is not None:
            context.save()
            try:
                measured = measure_person_label(context, command)
            finally:
                context.restore()
            if measured is not None and _contains(measured[1], screen_x, screen_y):
                name_hits.append(placement)
        bounds = project_person_life_bar_selection_rectangle(placement, transform)
        if _contains(bounds, screen_x, screen_y):
            extension_hits.append(placement)
    return tuple(bar_hits or name_hits or extension_hits)
