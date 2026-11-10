"""Transformation des coordonnées logiques en coordonnées écran."""


class ViewportTransform:
    def __init__(
        self,
        origin_x: float,
        origin_y: float,
        zoom_x: float,
        zoom_y: float,
        base_scale_x: float | None = None,
    ) -> None:
        if zoom_x <= 0:
            raise ValueError("zoom_x must be strictly positive")
        if zoom_y <= 0:
            raise ValueError("zoom_y must be strictly positive")
        if base_scale_x is not None and not base_scale_x > 0:
            raise ValueError("base_scale_x must be strictly positive")
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.zoom_x = zoom_x
        self.zoom_y = zoom_y
        self.base_scale_x = base_scale_x

    @property
    def effective_scale_x(self) -> float:
        if self.base_scale_x is None:
            return self.zoom_x
        return self.base_scale_x * self.zoom_x

    def logical_to_screen(
        self,
        logical_x: float,
        logical_y: float,
    ) -> tuple[float, float]:
        return (
            (logical_x - self.origin_x) * self.effective_scale_x,
            (logical_y - self.origin_y) * self.zoom_y,
        )

    def screen_to_logical(
        self,
        screen_x: float,
        screen_y: float,
    ) -> tuple[float, float]:
        return (
            self.origin_x + screen_x / self.effective_scale_x,
            self.origin_y + screen_y / self.zoom_y,
        )

    def zoom_at(
        self,
        screen_x: float,
        screen_y: float,
        new_zoom_x: float,
        new_zoom_y: float,
    ) -> None:
        if new_zoom_x <= 0:
            raise ValueError("new_zoom_x must be strictly positive")
        if new_zoom_y <= 0:
            raise ValueError("new_zoom_y must be strictly positive")
        new_scale_x = (
            new_zoom_x if self.base_scale_x is None
            else self.base_scale_x * new_zoom_x
        )
        new_origin_x = self.origin_x + screen_x / self.effective_scale_x - screen_x / new_scale_x
        new_origin_y = self.origin_y + screen_y / self.zoom_y - screen_y / new_zoom_y
        self.origin_x = new_origin_x
        self.origin_y = new_origin_y
        self.zoom_x = new_zoom_x
        self.zoom_y = new_zoom_y
