"""Dessin autonome de l'en-tête temporel, sans dépendance à GTK."""

from descendants_timeline.timeline_ticks import (
    project_year_tick_x, visible_year_ticks,
)
from descendants_timeline.viewport_transform import ViewportTransform


def draw_timeline_header(
    context, transform: ViewportTransform, header_width: float,
) -> None:
    """Dessine les graduations annuelles principales dont le X est visible."""
    for year in visible_year_ticks(transform, header_width):
        draw_year_tick(context, year, transform, header_width)


def draw_year_tick(
    context, year: int, transform: ViewportTransform, header_width: float,
) -> None:
    """Dessine une année et sa graduation dans un en-tête de 36 px."""
    x = project_year_tick_x(year, transform)
    text = str(year)
    context.save()
    try:
        context.new_path()
        context.rectangle(0.0, 0.0, header_width, 36.0)
        context.clip()
        context.select_font_face("sans-serif")
        context.set_font_size(16.0)
        x_bearing, _, width, _, _, _ = context.text_extents(text)
        context.set_source_rgb(0.0, 0.0, 0.0)
        context.move_to(x - width / 2.0 - x_bearing, 18.0)
        context.show_text(text)
        context.set_line_width(1.0)
        context.new_path()
        context.move_to(x, 26.0)
        context.line_to(x, 32.0)
        context.stroke()
    finally:
        context.restore()
