from descendants_timeline.layout.person_placement import PersonPlacement
from descendants_timeline.viewport_transform import ViewportTransform
from descendants_timeline.layout.life_bar_kind import LifeBarKind
from dataclasses import dataclass
from enum import Enum


LIFE_BAR_HEIGHT = 24.0
MARRIAGE_CIRCLE_OUTER_DIAMETER = 10.0
MARRIAGE_CIRCLE_STROKE_WIDTH = 2.0
DIVORCE_X_PATH_HALF_SIZE = 5.0
DIVORCE_X_STROKE_WIDTH = 2.0


class LifeDurationKind(str, Enum):
    BAR = "BAR"
    ZERO = "ZERO"
    SHORT = "SHORT"


@dataclass(frozen=True, slots=True)
class LifeDurationGeometry:
    kind: LifeDurationKind
    bounds: tuple[float, float, float, float]
    border_width: float
    detailed: bool


def project_life_duration(
    placement: PersonPlacement, transform: ViewportTransform,
    *, projected_bounds: tuple[float, float, float, float] | None = None,
) -> LifeDurationGeometry | None:
    """Project the lot 3 duration without changing its temporal classification."""
    if placement.life_bar_kind not in (LifeBarKind.NORMAL, LifeBarKind.ZERO_LENGTH):
        return None
    bounds = projected_bounds if projected_bounds is not None else project_person_life_bar_rectangle(placement, transform)
    if bounds is None:
        return None
    left, right, top, bottom = bounds
    detailed = transform.zoom_y >= 0.5
    border = 2.0 * transform.zoom_y if detailed else 0.0
    if placement.life_bar_kind is LifeBarKind.ZERO_LENGTH:
        kind = LifeDurationKind.ZERO
    elif placement.bar_x_end > placement.bar_x_start:
        if right - left - 2.0 * border >= 1.0:
            return LifeDurationGeometry(LifeDurationKind.BAR, bounds, border, detailed)
        kind = LifeDurationKind.SHORT
    else:
        return None
    # Supported durations start at the projected left endpoint; no second
    # temporal projection or midpoint convention is needed for the trait.
    center = left
    width = 2.0 * transform.zoom_y if detailed else 1.0
    return LifeDurationGeometry(kind, (center - width / 2.0, center + width / 2.0, top, bottom),
                                0.0, detailed)


def project_divorce_x_cairo_dimensions(
    transform: ViewportTransform,
) -> tuple[float, float]:
    """Retourne (demi-taille du chemin, épaisseur du trait) en coordonnées écran."""
    half_size = DIVORCE_X_PATH_HALF_SIZE * transform.zoom_y
    stroke_width = DIVORCE_X_STROKE_WIDTH * transform.zoom_y
    return half_size, stroke_width


def project_marriage_circle_outer_diameter(transform: ViewportTransform) -> float:
    """Diamètre extérieur écran, contour compris, selon le seul zoom vertical."""
    return MARRIAGE_CIRCLE_OUTER_DIAMETER * transform.zoom_y


def project_marriage_circle_cairo_dimensions(
    transform: ViewportTransform,
) -> tuple[float, float]:
    """Retourne (rayon du chemin, épaisseur du contour) en coordonnées écran."""
    stroke_width = MARRIAGE_CIRCLE_STROKE_WIDTH * transform.zoom_y
    outer_diameter = project_marriage_circle_outer_diameter(transform)
    path_radius = (outer_diameter - stroke_width) / 2.0
    return path_radius, stroke_width


def project_person_life_bar_rectangle(
    placement: PersonPlacement,
    transform: ViewportTransform,
) -> tuple[float, float, float, float] | None:
    """Retourne (left, right, top, bottom), ou None si une extrémité manque."""
    x_start = placement.bar_x_start
    x_end = placement.bar_x_end
    if x_start is None or x_end is None:
        return None
    half_height = LIFE_BAR_HEIGHT / 2.0
    start_x, top = transform.logical_to_screen(x_start, placement.y - half_height)
    end_x, bottom = transform.logical_to_screen(x_end, placement.y + half_height)
    return min(start_x, end_x), max(start_x, end_x), top, bottom


def project_person_life_bar_selection_rectangle(
    placement: PersonPlacement,
    transform: ViewportTransform,
) -> tuple[float, float, float, float] | None:
    """Étend seulement la borne droite pour une sélection d'au moins 200 unités logiques."""
    bounds = project_person_life_bar_rectangle(placement, transform)
    if bounds is None:
        return None
    left, right, top, bottom = bounds
    minimum_right, _ = transform.logical_to_screen(
        placement.bar_x_start + 200.0, placement.y,
    )
    return left, max(right, minimum_right), top, bottom
