"""État du viewport indépendant de l'interface graphique."""

from math import isfinite
from datetime import date

from descendants_timeline.initial_framing import initial_transform_for_layout
from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.layout.represented_date_bounds import represented_date_bounds
from descendants_timeline.navigation_controller import (
    capped_horizontal_zoom,
    capped_vertical_zoom,
    horizontal_zoom_limits,
    resize_viewport_preserving_center,
)
from descendants_timeline.timeline.timeline_model import TimelineModel
from descendants_timeline.viewport_transform import ViewportTransform


class ViewportController:
    def __init__(
        self, model: TimelineModel | None, layout: TimelineLayout | None,
    ) -> None:
        if (model is None) != (layout is None):
            raise ValueError("model and layout must be supplied together")
        self.model = model
        self.layout = layout
        self.transform: ViewportTransform | None = None
        self._viewport_width: float | None = None
        self._initial_framing_completed = False
        self._initial_framing_diagnostics = None
        self._horizontal_frame: tuple[float, float] | None = None

    @property
    def initial_framing_completed(self) -> bool:
        return self._initial_framing_completed

    def clear_timeline(self) -> None:
        """Libère la timeline et son cadrage, en conservant la largeur du viewport."""
        self.model = None
        self.layout = None
        self.transform = None
        self._initial_framing_completed = False
        self._initial_framing_diagnostics = None
        self._horizontal_frame = None

    def _remember_horizontal_frame(self, transform, viewport_width):
        # Display margins belong to navigation, never to genealogical dates.
        self._horizontal_frame = (
            (transform.origin_x, transform.origin_x + viewport_width / transform.effective_scale_x)
            if transform is not None else None
        )
        if self._horizontal_frame is not None and self.model is not None and self.layout is not None:
            bounds = represented_date_bounds(self.model, self.layout)
            if bounds is not None:
                start, end = self._horizontal_frame
                # The initial framing deliberately caps very long timelines.
                # Navigation must still reach every represented coordinate.
                self._horizontal_frame = (
                    min(start, float(bounds[0].toordinal())),
                    max(end, float(bounds[1].toordinal())),
                )

    def horizontal_scroll_state(self) -> tuple[float, float, float, float] | None:
        """Return value, lower, upper, page size in logical coordinates."""
        transform = self.transform
        if transform is None or self._horizontal_frame is None or not self._viewport_width:
            return None
        page = self._viewport_width / transform.effective_scale_x
        start, end = self._horizontal_frame
        value = transform.origin_x
        if page >= end - start:
            return value, value, value + page, page
        # Resize/anchored zoom may temporarily expose an outer margin. Reflect
        # that position without shifting the anchor or widening the pan limits.
        return value, min(start, value), max(end, value + page), page

    def set_horizontal_position(self, value: float) -> None:
        state = self.horizontal_scroll_state()
        if state is None or not isfinite(value):
            return
        origin, _, _, page = state
        start, end = self._horizontal_frame
        if page >= end - start:
            return
        self.transform.origin_x = max(min(start, origin), min(max(end - page, origin), value))

    def pan_horizontal(self, viewport_fraction: float) -> None:
        if self.transform is not None and self._viewport_width:
            self.set_horizontal_position(
                self.transform.origin_x + viewport_fraction * self._viewport_width / self.transform.effective_scale_x
            )

    def fit_to_window(self) -> None:
        if self.model is None or self.layout is None or not self._viewport_width:
            return
        self.transform = initial_transform_for_layout(
            self.model, self.layout, self._viewport_width,
        )
        self._remember_horizontal_frame(self.transform, self._viewport_width)

    def fit_to_placement(self, placement, width: float, height: float, measure) -> bool:
        """Cadre une occurrence courante sans changer le modèle ni le cadre global.

        measure(candidate) retourne l'emprise écran complète, avant clipping.
        La marge est de 24 px par bord, limitée à 10 % de chaque dimension.
        """
        current = self.transform
        if (current is None or self.layout is None or placement is None
                or not any(item is placement for item in self.layout.person_placements)
                or not all(isfinite(value) and value > 0 for value in (width, height))):
            return False
        start, end = placement.bar_x_start, placement.bar_x_end
        if start is None or end is None or not all(isfinite(value) for value in (start, end, placement.y)):
            return False
        anchor = (start + end) / 2
        try:
            year = date.fromordinal(int(anchor)).year
        except (ValueError, OverflowError):
            return False
        context_year = max(1, min(9979, year - 10))
        context_days = (date(context_year + 20, 1, 1) - date(context_year, 1, 1)).days
        reference = current.base_scale_x
        lower, upper = 0.2, 4.0
        if reference is None:
            initial = initial_transform_for_layout(self.model, self.layout, width)
            if initial is None:
                return False
            reference = initial.effective_scale_x
            minimum, maximum = horizontal_zoom_limits(width)
            lower, upper = max(lower, minimum / reference), min(upper, maximum / reference)
        if not isfinite(reference) or reference <= 0 or lower > upper:
            return False
        available_width = width - 2 * min(24.0, width * 0.1)
        available_height = height - 2 * min(24.0, height * 0.1)
        upper = max(lower, min(upper, available_width / (context_days * reference)))

        def projected(relative_zoom):
            zoom_x = relative_zoom if current.base_scale_x is not None else reference * relative_zoom
            candidate = ViewportTransform(anchor, placement.y, zoom_x, min(relative_zoom, 1.0),
                                          base_scale_x=current.base_scale_x)
            if not isfinite(candidate.effective_scale_x) or candidate.effective_scale_x <= 0:
                return candidate, None
            bounds = measure(candidate)
            if (bounds is None or not all(isfinite(value) for value in bounds)
                    or bounds[1] <= bounds[0] or bounds[3] <= bounds[2]):
                return candidate, None
            return candidate, bounds

        def fits(bounds):
            return (bounds is not None and bounds[1] - bounds[0] <= available_width
                    and bounds[3] - bounds[2] <= available_height)

        candidate, bounds = projected(lower)
        if bounds is None:
            return False
        if fits(bounds):
            largest, largest_bounds = projected(upper)
            if fits(largest_bounds):
                candidate, bounds = largest, largest_bounds
            else:
                # Recherche bornée, toujours depuis le même ancrage logique.
                for _ in range(36):
                    middle = (lower + upper) / 2
                    trial, trial_bounds = projected(middle)
                    if fits(trial_bounds):
                        lower = middle
                        candidate, bounds = trial, trial_bounds
                    else:
                        upper = middle
        candidate.origin_x += ((bounds[0] + bounds[1]) / 2 - width / 2) / candidate.effective_scale_x
        candidate.origin_y += ((bounds[2] + bounds[3]) / 2 - height / 2) / candidate.zoom_y
        if not all(isfinite(value) for value in (candidate.origin_x, candidate.origin_y)):
            return False
        self.transform = candidate
        self._viewport_width = width
        return True

    def scroll_vertical(self, delta_screen_y: float) -> None:
        transform = self.transform
        if transform is None:
            return
        transform.origin_y += delta_screen_y / transform.zoom_y

    def zoom_at_cursor(
        self, screen_x: float, screen_y: float, steps: int,
        horizontal_only: bool = False,
    ) -> None:
        transform = self.transform
        if transform.base_scale_x is not None:
            if not (
                transform.zoom_x >= 0.2 and 0.2 <= transform.zoom_y <= min(transform.zoom_x, 1.0)
            ):
                return
            current_scale = transform.effective_scale_x
            if current_scale == 0.0 or not isfinite(current_scale):
                return
            try:
                if not isfinite(steps) or steps == 0:
                    return
                requested_zoom = transform.zoom_x * (1.10 ** steps)
            except OverflowError:
                return
            entering_branch_b = (
                transform.zoom_x >= 1.0 and steps < 0 and requested_zoom < 1.0
            )
            inside_branch_b = transform.zoom_x < 1.0
            if entering_branch_b or inside_branch_b:
                requested_zoom = max(0.2, requested_zoom)
            if (
                (not inside_branch_b and requested_zoom >= 1.0)
                or entering_branch_b
                or inside_branch_b
            ):
                requested_scale = transform.base_scale_x * requested_zoom
                if not (
                    isfinite(requested_zoom) and requested_zoom > 0.0
                    and isfinite(requested_scale) and requested_scale > 0.0
                ):
                    return
                candidate = ViewportTransform(
                    origin_x=transform.origin_x, origin_y=transform.origin_y,
                    zoom_x=transform.zoom_x, zoom_y=transform.zoom_y,
                    base_scale_x=transform.base_scale_x,
                )
                requested_zoom_y = min(requested_zoom, 1.0)
                candidate.zoom_at(screen_x, screen_y, requested_zoom, requested_zoom_y)
                if isfinite(candidate.origin_x) and isfinite(candidate.origin_y):
                    self.transform = candidate
                return
        new_zoom_x = capped_horizontal_zoom(
            self.transform.effective_scale_x, steps, self._viewport_width,
        )
        if self.transform.base_scale_x is not None:
            new_zoom_x /= self.transform.base_scale_x
        origin_y = self.transform.origin_y
        new_zoom_y = (
            self.transform.zoom_y if horizontal_only
            else capped_vertical_zoom(self.transform.zoom_y, steps)
        )
        self.transform.zoom_at(screen_x, screen_y, new_zoom_x, new_zoom_y)
        if horizontal_only:
            self.transform.origin_y = origin_y

    def set_model_and_layout(
        self, model: TimelineModel, layout: TimelineLayout, *, diagnostics=None,
    ) -> None:
        if model is None or layout is None:
            raise ValueError("model and layout must both be supplied")
        transform = None
        initial_framing_completed = False
        if self._viewport_width is not None and self._viewport_width != 0.0:
            transform = initial_transform_for_layout(
                model, layout, self._viewport_width,
                **({"diagnostics": diagnostics} if diagnostics is not None else {}),
            )
            initial_framing_completed = True
        self.model = model
        self.layout = layout
        self.transform = transform
        self._initial_framing_completed = initial_framing_completed
        self._initial_framing_diagnostics = diagnostics if not initial_framing_completed else None
        self._remember_horizontal_frame(transform, self._viewport_width)

    def allocate_width(self, viewport_width: float) -> None:
        if viewport_width == 0.0:
            return
        if self.model is None or self.layout is None:
            self._viewport_width = viewport_width
            return
        if not self._initial_framing_completed:
            self.transform = initial_transform_for_layout(
                self.model, self.layout, viewport_width,
                **({"diagnostics": self._initial_framing_diagnostics}
                   if self._initial_framing_diagnostics is not None else {}),
            )
            self._initial_framing_completed = True
            self._initial_framing_diagnostics = None
            self._remember_horizontal_frame(self.transform, viewport_width)
        elif self.transform is not None:
            self.transform = resize_viewport_preserving_center(
                self.transform, self._viewport_width, viewport_width,
            )
        self._viewport_width = viewport_width
