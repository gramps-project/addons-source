"""Projection des primitives de la timeline, sans dépendance graphique."""

from collections.abc import Callable
from colorsys import hsv_to_rgb
from dataclasses import dataclass, field, replace
from enum import Enum
from math import isfinite, pi
from descendants_timeline.inference.reconciled_temporal_domain import ReconciledBoundOrigin
from descendants_timeline.layout.temporal_display_value import (
    TemporalPositionQualification, should_show_inference_indicator,
)

from descendants_timeline.death_graphical_qualification import (
    DeathGraphicalQualification, qualify_death_graphically,
)
from descendants_timeline.temporal_bound_qualification import (
    TemporalDomainQualification, qualify_temporal_domain,
    VisualPositionQualification, qualify_visual_position,
    should_show_visual_fallback_indicator,
    TemporalShape,
)
from descendants_timeline.model.temporal_target import (
    TargetSemantic, TemporalOwnerType, TemporalTarget,
)
from descendants_timeline.layout.divorce_node_placement import DivorceNodePlacement
from descendants_timeline.layout.marriage_node_placement import MarriageNodePlacement
from descendants_timeline.layout.person_placement import PersonPlacement
from descendants_timeline.layout.position_kind import PositionKind
from descendants_timeline.layout.life_bar_kind import LifeBarKind
from descendants_timeline.layout.timeline_scale import TimelineScale
from descendants_timeline.layout.remarriage_segment_placement import RemarriageSegmentPlacement
from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.timeline.timeline_model import TimelineModel
from descendants_timeline.traversal.descendance_traversal import TraversalRole
from descendants_timeline.viewport_controller import ViewportController
from descendants_timeline.viewport_transform import ViewportTransform
from descendants_timeline.timeline_ticks import project_year_tick_x, visible_year_ticks
from descendants_timeline.timeline_geometry import project_marriage_circle_cairo_dimensions
from descendants_timeline.timeline_geometry import project_marriage_circle_outer_diameter
from descendants_timeline.timeline_geometry import project_divorce_x_cairo_dimensions
from descendants_timeline.timeline_geometry import project_person_life_bar_rectangle
from descendants_timeline.timeline_geometry import LIFE_BAR_HEIGHT
from descendants_timeline.timeline_geometry import (
    LifeDurationGeometry, LifeDurationKind, project_life_duration,
)


LIFE_BAR_LINE_WIDTH = 4.0
MARRIAGE_NODE_RADIUS = 5.0
MARRIAGE_NODE_LINE_WIDTH = 2.0
MARRIAGE_NODE_RGB = (0.0, 0.0, 0.0)
REMARRIAGE_SEGMENT_RGB = (0.0, 0.0, 0.0)
REMARRIAGE_SEGMENT_LINE_WIDTH = 2.0
DIVORCE_NODE_HALF_SIZE = 5.0
DIVORCE_NODE_LINE_WIDTH = 2.0
DIVORCE_NODE_RGB = (0.0, 0.0, 0.0)


def _lighten_palette_color(color: tuple[float, float, float]) -> tuple[float, float, float]:
    """Mix 12% white into a default palette color."""
    red, green, blue = color
    return (0.88 * red + 0.12, 0.88 * green + 0.12, 0.88 * blue + 0.12)


GENERATION_ONE_RGB = _lighten_palette_color((0.20, 0.40, 0.75))
GENERATION_TWO_RGB = _lighten_palette_color((0.15, 0.60, 0.50))
_SPOUSE_GRAY = 0.64 * (128 / 255) + 0.36  # Mix 36% white into #808080.
SPOUSE_RGB = (_SPOUSE_GRAY,) * 3


def color_for_spouse() -> tuple[float, float, float]:
    return SPOUSE_RGB


def color_for_generation(
    generation: int,
    *,
    provider: Callable[[int], tuple[float, float, float]] | None = None,
) -> tuple[float, float, float]:
    if generation <= 0:
        raise ValueError("generation must be strictly positive")
    if provider is not None:
        return provider(generation)
    if generation == 1:
        return GENERATION_ONE_RGB
    if generation == 2:
        return GENERATION_TWO_RGB
    if generation > 2:
        # Repli provisoire : la teinte avance de 0.618033988749895 par génération,
        # saturation et valeur constantes, sans état ni dépendance au parcours.
        hue = ((generation - 3) * 0.618033988749895) % 1.0
        return _lighten_palette_color(hsv_to_rgb(hue, 0.5, 0.8))
    raise NotImplementedError("color is not defined for this generation yet")


def color_for_person_placement(
    placement: PersonPlacement,
    *,
    provider: Callable[[int], tuple[float, float, float]] | None = None,
) -> tuple[float, float, float]:
    if placement.role is TraversalRole.SPOUSE:
        return color_for_spouse()
    if placement.role is TraversalRole.ROOT:
        return color_for_generation(placement.generation, provider=provider)
    if placement.role is TraversalRole.DESCENDANT:
        return color_for_generation(placement.generation, provider=provider)
    raise NotImplementedError("color is not defined for this placement yet")


def birth_indicator_right_edge_x(bar_outer_left_x: float, zoom_y: float) -> float:
    """Return the indicator's right edge from the projected outer bar edge."""
    return bar_outer_left_x - 4.0 * zoom_y


def birth_indicator_center_y(bar_outer_top_y: float, bar_outer_height: float) -> float:
    """Return the indicator's reference center from projected outer bar bounds."""
    return bar_outer_top_y + bar_outer_height / 2.0


def birth_indicator_text_origin(
    indicator_right_edge_x: float,
    indicator_center_y: float,
    x_bearing: float,
    y_bearing: float,
    ink_width: float,
    ink_height: float,
) -> tuple[float, float]:
    """Align the ink rectangle's right edge and vertical center to its anchors."""
    return (
        indicator_right_edge_x - x_bearing - ink_width,
        indicator_center_y - y_bearing - ink_height / 2.0,
    )


def should_draw_birth_indicator(zoom_y: float) -> bool:
    """Allow indicator drawing at or above half vertical zoom."""
    return zoom_y >= 0.5


@dataclass(frozen=True)
class PersonLabel:
    placement: PersonPlacement
    display_name: str


class LifeBarIndicatorKind(str, Enum):
    INFERENCE = "INFERENCE"
    VISUAL_FALLBACK = "VISUAL_FALLBACK"


@dataclass(frozen=True)
class LifeBarIndicatorDrawCommand:
    """Graphical indicator; BIRTH attachment anchors it left of its parent bar."""

    kind: LifeBarIndicatorKind


@dataclass(frozen=True, slots=True)
class SymbolIndicatorDrawCommand:
    kind: LifeBarIndicatorKind
    endpoint: TargetSemantic
    symbol_bounds: tuple[float, float, float, float]
    zoom_y: float


@dataclass(frozen=True)
class LifeBarDrawCommand:
    start: tuple[float, float]
    end: tuple[float, float]
    color: tuple[float, float, float]
    # Bornes écran (left, right, top, bottom), bords extérieurs compris.
    # L'égalité conserve le contrat historique start/end/color.
    outer_bounds: tuple[float, float, float, float] | None = field(default=None, compare=False)
    inner_bounds: tuple[float, float, float, float] | None = field(default=None, compare=False)
    border_width: float = field(default=0.0, compare=False)
    border_color: tuple[float, float, float] = field(default=(0.0, 0.0, 0.0), compare=False)
    label: PersonLabel | None = field(default=None, compare=False)
    birth_qualification: TemporalDomainQualification | None = field(default=None, compare=False)
    death_qualification: TemporalDomainQualification | None = field(default=None, compare=False)
    birth_visual_qualification: VisualPositionQualification | None = field(default=None, compare=False)
    death_visual_qualification: VisualPositionQualification | None = field(default=None, compare=False)
    birth_before_geometry: "BeforeTriangleGeometry | None" = field(default=None, compare=False)
    death_before_geometry: "BeforeTriangleGeometry | None" = field(default=None, compare=False)
    birth_after_geometry: "AfterTriangleGeometry | None" = field(default=None, compare=False)
    death_after_geometry: "AfterTriangleGeometry | None" = field(default=None, compare=False)
    birth_span_geometry: "SpanRectangleGeometry | None" = field(default=None, compare=False)
    death_span_geometry: "SpanRectangleGeometry | None" = field(default=None, compare=False)
    birth_position_qualification: TemporalPositionQualification | None = field(default=None, compare=False)
    birth_indicator: LifeBarIndicatorDrawCommand | None = field(default=None, compare=False)
    duration_geometry: LifeDurationGeometry | None = field(default=None, compare=False)
    temporal_symbols: tuple["TemporalSymbolDrawCommand", ...] | None = field(default=None, compare=False)
    symbol_indicators: tuple[SymbolIndicatorDrawCommand, ...] = field(default=(), compare=False)


@dataclass(frozen=True, slots=True)
class BeforeTriangleGeometry:
    endpoint: TargetSemantic
    vertices: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]

    @property
    def shape(self) -> TemporalShape:
        return TemporalShape.BEFORE


def build_before_triangle_geometry(
    qualification: TemporalDomainQualification | DeathGraphicalQualification,
    endpoint: TargetSemantic,
    transform: ViewportTransform,
    bar: LifeBarDrawCommand,
) -> BeforeTriangleGeometry:
    """Project the usable BEFORE documentary anchor, or the reconciled maximum."""
    if qualification.shape is not TemporalShape.BEFORE:
        raise ValueError("a BEFORE qualification is required")
    if endpoint not in (TargetSemantic.BIRTH, TargetSemantic.DEATH):
        raise ValueError("endpoint must be BIRTH or DEATH")
    if bar.outer_bounds is None:
        raise ValueError("outer bar bounds are required")
    maximum = qualification.maximum
    anchor = maximum.bound.value
    if (
        maximum.bound.origin is ReconciledBoundOrigin.GRAMPS
        and maximum.documentary_value is not None
        and maximum.documentary_value.is_usable_as_evidence
        and maximum.documentary_boundary is not None
    ):
        anchor = maximum.documentary_boundary
    logical_x = TimelineScale().date_to_x(anchor)
    x_bound, _ = transform.logical_to_screen(logical_x, 0.0)
    _, _, top, bottom = bar.outer_bounds
    height = bottom - top
    y_center = (top + bottom) / 2.0
    return BeforeTriangleGeometry(
        endpoint=endpoint,
        vertices=((x_bound - height, y_center), (x_bound, top), (x_bound, bottom)),
    )


@dataclass(frozen=True, slots=True)
class AfterTriangleGeometry:
    endpoint: TargetSemantic
    vertices: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]

    @property
    def shape(self) -> TemporalShape:
        return TemporalShape.AFTER


def build_after_triangle_geometry(
    qualification: TemporalDomainQualification | DeathGraphicalQualification,
    endpoint: TargetSemantic,
    transform: ViewportTransform,
    bar: LifeBarDrawCommand,
) -> AfterTriangleGeometry:
    """Project the usable AFTER documentary anchor, or the reconciled minimum."""
    if qualification.shape is not TemporalShape.AFTER:
        raise ValueError("an AFTER qualification is required")
    if endpoint not in (TargetSemantic.BIRTH, TargetSemantic.DEATH):
        raise ValueError("endpoint must be BIRTH or DEATH")
    if bar.outer_bounds is None:
        raise ValueError("outer bar bounds are required")
    minimum = qualification.minimum
    anchor = minimum.bound.value
    if (
        minimum.bound.origin is ReconciledBoundOrigin.GRAMPS
        and minimum.documentary_value is not None
        and minimum.documentary_value.is_usable_as_evidence
        and minimum.documentary_boundary is not None
    ):
        anchor = minimum.documentary_boundary
    logical_x = TimelineScale().date_to_x(anchor)
    x_bound, _ = transform.logical_to_screen(logical_x, 0.0)
    _, _, top, bottom = bar.outer_bounds
    height = bottom - top
    y_center = (top + bottom) / 2.0
    return AfterTriangleGeometry(
        endpoint=endpoint,
        vertices=((x_bound, top), (x_bound + height, y_center), (x_bound, bottom)),
    )


@dataclass(frozen=True, slots=True)
class SpanRectangleGeometry:
    endpoint: TargetSemantic
    # Screen bounds in the existing (left, right, top, bottom) convention.
    bounds: tuple[float, float, float, float]

    @property
    def shape(self) -> TemporalShape:
        return TemporalShape.SPAN


@dataclass(frozen=True, slots=True)
class TemporalSymbolDrawCommand:
    shape: TemporalShape | str
    endpoint: TargetSemantic | None
    bounds: tuple[float, float, float, float]
    color: tuple[float, float, float]
    detailed: bool
    structural_bounds: tuple[float, float, float, float]
    geometry: BeforeTriangleGeometry | AfterTriangleGeometry | SpanRectangleGeometry | None = None
    stroke_width: float = 0.0


def build_temporal_symbol(qualification, endpoint, transform, bar):
    """Project an already admissible qualification, without reading evidence."""
    if qualification is None or qualification.shape is None:
        return None
    shape = qualification.shape
    _, _, top, bottom = bar.outer_bounds
    color = tuple(0.5 * c + 0.5 for c in bar.color) if qualification.use_lightened_color else bar.color
    reference = qualification.minimum or qualification.maximum
    x, _ = transform.logical_to_screen(TimelineScale().date_to_x(reference.bound.value), 0.0)
    width = max(1.0, 2.0 * transform.zoom_y)
    structural = (x - 0.5, x + 0.5, top, bottom)
    geometry = None
    stroke_width = 0.0
    if shape is TemporalShape.BEFORE:
        geometry = build_before_triangle_geometry(qualification, endpoint, transform, bar)
        x = geometry.vertices[1][0]
        structural = (x - 0.5, x + 0.5, top, bottom)
    elif shape is TemporalShape.AFTER:
        geometry = build_after_triangle_geometry(qualification, endpoint, transform, bar)
        x = geometry.vertices[0][0]
        structural = (x - 0.5, x + 0.5, top, bottom)
    elif shape is TemporalShape.SPAN:
        geometry = build_span_rectangle_geometry(qualification, endpoint, transform, bar)
    if isinstance(geometry, (BeforeTriangleGeometry, AfterTriangleGeometry)):
        xs = [vertex[0] for vertex in geometry.vertices]
        bounds = (min(xs), max(xs), top, bottom)
    elif isinstance(geometry, SpanRectangleGeometry):
        bounds = geometry.bounds
        center = (bounds[0] + bounds[1]) / 2
        structural_width = max(1.0, bounds[1] - bounds[0])
        structural = (center - structural_width / 2, center + structural_width / 2, top, bottom)
        stroke_width = 2.0 * transform.zoom_y
    else:
        bounds = (x - width / 2, x + width / 2, top, bottom)
    return TemporalSymbolDrawCommand(shape, endpoint, bounds, color, transform.zoom_y >= 0.5,
                                      structural, geometry, stroke_width)


def build_person_symbols(command, placement, birth, death, transform):
    symbols, indicators = [], []
    for endpoint, qualification in ((TargetSemantic.BIRTH, birth), (TargetSemantic.DEATH, death)):
        symbol = build_temporal_symbol(qualification, endpoint, transform, command)
        if symbol is None:
            continue
        symbols.append(symbol)
        if qualification.show_inference_indicator:
            indicators.append(SymbolIndicatorDrawCommand(
                LifeBarIndicatorKind.INFERENCE, endpoint, symbol.bounds, transform.zoom_y))
    if not symbols and placement.visual_x is not None and placement.visual_position_kind is PositionKind.VISUAL_FALLBACK:
        x, _ = transform.logical_to_screen(placement.visual_x, placement.y)
        _, _, top, bottom = command.outer_bounds
        width = max(1.0, 2.0 * transform.zoom_y)
        bounds = (x - width / 2, x + width / 2, top, bottom)
        symbols.append(TemporalSymbolDrawCommand(
            "PRESENCE", None, bounds, tuple(0.5 * c + 0.5 for c in command.color),
            transform.zoom_y >= 0.5, bounds))
        indicators.extend(SymbolIndicatorDrawCommand(
            LifeBarIndicatorKind.VISUAL_FALLBACK, endpoint, bounds, transform.zoom_y)
            for endpoint in (TargetSemantic.BIRTH, TargetSemantic.DEATH))
    aliases = {}
    for symbol in symbols:
        if symbol.geometry is not None:
            aliases[f"{symbol.endpoint.value.lower()}_{symbol.shape.value.lower()}_geometry"] = symbol.geometry
    birth_indicator = next((LifeBarIndicatorDrawCommand(i.kind) for i in indicators
                            if i.endpoint is TargetSemantic.BIRTH), None)
    return replace(command, temporal_symbols=tuple(symbols), symbol_indicators=tuple(indicators),
                   birth_qualification=birth, death_qualification=death,
                   birth_indicator=birth_indicator,
                   birth_position_qualification=placement.birth_position_qualification,
                   birth_visual_qualification=qualify_visual_position(placement.x_start_kind),
                   death_visual_qualification=(qualify_visual_position(placement.x_end_kind)
                       if death is None and placement.x_end_kind is PositionKind.VISUAL_FALLBACK else None),
                   **aliases)


def build_span_rectangle_geometry(
    qualification: TemporalDomainQualification | DeathGraphicalQualification,
    endpoint: TargetSemantic,
    transform: ViewportTransform,
    bar: LifeBarDrawCommand,
) -> SpanRectangleGeometry:
    """Project both reconciled bounds, retaining the bar's vertical bounds."""
    if qualification.shape is not TemporalShape.SPAN:
        raise ValueError("a SPAN qualification is required")
    if endpoint not in (TargetSemantic.BIRTH, TargetSemantic.DEATH):
        raise ValueError("endpoint must be BIRTH or DEATH")
    if bar.outer_bounds is None:
        raise ValueError("outer bar bounds are required")
    scale = TimelineScale()
    logical_minimum = scale.date_to_x(qualification.minimum.bound.value)
    logical_maximum = scale.date_to_x(qualification.maximum.bound.value)
    left, _ = transform.logical_to_screen(logical_minimum, 0.0)
    right, _ = transform.logical_to_screen(logical_maximum, 0.0)
    _, _, top, bottom = bar.outer_bounds
    return SpanRectangleGeometry(endpoint=endpoint, bounds=(left, right, top, bottom))


@dataclass(frozen=True)
class RemarriageSegmentDrawCommand:
    start: tuple[float, float]
    end: tuple[float, float]
    color: tuple[float, float, float] = REMARRIAGE_SEGMENT_RGB
    stroke_width: float = REMARRIAGE_SEGMENT_LINE_WIDTH


@dataclass(frozen=True)
class MarriageNodeDrawCommand:
    center: tuple[float, float]
    radius: float
    color: tuple[float, float, float] = MARRIAGE_NODE_RGB
    stroke_width: float = MARRIAGE_NODE_LINE_WIDTH


@dataclass(frozen=True)
class DivorceNodeDrawCommand:
    center: tuple[float, float]
    half_size: float
    color: tuple[float, float, float] = DIVORCE_NODE_RGB
    stroke_width: float = DIVORCE_NODE_LINE_WIDTH


def draw_birth_indicator(
    context: object,
    command: LifeBarIndicatorDrawCommand,
    outer_bounds: tuple[float, float, float, float],
    zoom_y: float,
) -> None:
    if not should_draw_birth_indicator(zoom_y):
        return
    if command.kind is LifeBarIndicatorKind.INFERENCE:
        return
    elif command.kind is LifeBarIndicatorKind.VISUAL_FALLBACK:
        text = "?"
    else:
        raise NotImplementedError("this indicator kind is not supported")
    context.save()
    try:
        context.select_font_face("sans-serif")
        context.set_font_size(16.0 * zoom_y)
        x_bearing, y_bearing, width, height, _, _ = context.text_extents(text)
        left, _, top, bottom = outer_bounds
        right = birth_indicator_right_edge_x(left, zoom_y)
        center = birth_indicator_center_y(top, bottom - top)
        origin = birth_indicator_text_origin(right, center, x_bearing, y_bearing, width, height)
        context.set_source_rgb(0.0, 0.0, 0.0)
        context.move_to(*origin)
        context.show_text(text)
    finally:
        context.restore()


def draw_remarriage_segment(
    context: object,
    command: RemarriageSegmentDrawCommand,
) -> None:
    context.save()
    try:
        context.set_line_width(command.stroke_width)
        context.set_source_rgb(*command.color)
        context.new_path()
        context.move_to(*command.start)
        context.line_to(*command.end)
        context.stroke()
    finally:
        context.restore()


def draw_divorce_node(
    context, command: DivorceNodeDrawCommand, *, line_cap_butt=None,
) -> None:
    x, y = command.center
    half_size = command.half_size

    context.save()
    try:
        context.set_line_width(command.stroke_width)
        if line_cap_butt is not None:
            context.set_line_cap(line_cap_butt)
        context.set_source_rgb(*command.color)
        context.new_path()
        context.move_to(x - half_size, y - half_size)
        context.line_to(x + half_size, y + half_size)
        context.move_to(x + half_size, y - half_size)
        context.line_to(x - half_size, y + half_size)
        context.stroke()
    finally:
        context.restore()


def draw_marriage_node(context, command: MarriageNodeDrawCommand) -> None:
    context.save()
    try:
        context.set_line_width(command.stroke_width)
        context.set_source_rgb(*command.color)
        context.new_path()
        context.arc(
            command.center[0], command.center[1], command.radius, 0.0, 2.0 * pi,
        )
        context.stroke()
    finally:
        context.restore()


def _draw_triangle(
    context, command: LifeBarDrawCommand,
    geometry: BeforeTriangleGeometry | AfterTriangleGeometry,
) -> None:
    context.save()
    try:
        a, b, c = geometry.vertices
        context.new_path()
        context.move_to(*a)
        context.line_to(*b)
        context.line_to(*c)
        context.close_path()
        color = command.color if isinstance(command, TemporalSymbolDrawCommand) else tuple(0.5 * c + 0.5 for c in command.color)
        context.set_source_rgb(*color)
        context.fill()
    finally:
        context.restore()


def draw_temporal_symbol(context, symbol: TemporalSymbolDrawCommand) -> None:
    if symbol.detailed and isinstance(symbol.geometry, (BeforeTriangleGeometry, AfterTriangleGeometry)):
        _draw_triangle(context, symbol, symbol.geometry)
        return
    if symbol.detailed and symbol.shape is TemporalShape.SPAN:
        _draw_span_rectangle(context, symbol, symbol.geometry)
        return
    context.save()
    try:
        context.set_source_rgb(*symbol.color)
        context.new_path()
        left, right, top, bottom = symbol.bounds if symbol.detailed else symbol.structural_bounds
        context.rectangle(left, top, right - left, bottom - top)
        context.fill()
    finally:
        context.restore()


def draw_symbol_indicator(context, indicator: SymbolIndicatorDrawCommand) -> None:
    if (indicator.endpoint is TargetSemantic.DEATH
            and indicator.kind is LifeBarIndicatorKind.VISUAL_FALLBACK):
        return
    if indicator.kind is LifeBarIndicatorKind.INFERENCE:
        return
    if not should_draw_birth_indicator(indicator.zoom_y):
        return
    if indicator.endpoint is TargetSemantic.BIRTH:
        draw_birth_indicator(context, LifeBarIndicatorDrawCommand(indicator.kind),
                             indicator.symbol_bounds, indicator.zoom_y)
        return
    left, right, top, bottom = indicator.symbol_bounds
    text = "?"
    context.save()
    try:
        context.select_font_face("sans-serif")
        context.set_font_size(16.0 * indicator.zoom_y)
        xb, yb, width, height, _, _ = context.text_extents(text)
        context.set_source_rgb(0.0, 0.0, 0.0)
        context.move_to(right + 4.0 * indicator.zoom_y - xb, (top + bottom - height) / 2.0 - yb)
        context.show_text(text)
    finally:
        context.restore()


def _draw_span_rectangle(
    context, command: LifeBarDrawCommand, geometry: SpanRectangleGeometry,
) -> None:
    context.save()
    try:
        left, right, top, bottom = geometry.bounds
        context.new_path()
        context.rectangle(left, top, right - left, bottom - top)
        color = command.color if isinstance(command, TemporalSymbolDrawCommand) else tuple(0.5 * c + 0.5 for c in command.color)
        context.set_source_rgb(*color)
        context.fill()
    finally:
        context.restore()


def _draw_duration_rectangles(context, command):
    geometry = command.duration_geometry
    if geometry is not None and geometry.kind is not LifeDurationKind.BAR:
        color = command.color if geometry.kind is LifeDurationKind.ZERO else (0.0, 0.0, 0.0)
        rectangles = ((geometry.bounds, color),)
    else:
        rectangles = (
            (command.outer_bounds, command.border_color),
            (command.inner_bounds, command.color),
        )
        if command.border_width < 1.0:
            rectangles = ((command.outer_bounds, command.color),)
        elif command.inner_bounds[1] == command.inner_bounds[0]:
            rectangles = ((command.outer_bounds, command.border_color),)
    for bounds, color in rectangles:
        left, right, top, bottom = bounds
        context.set_source_rgb(*color)
        context.new_path()
        context.rectangle(left, top, right - left, bottom - top)
        context.fill()


def draw_life_bar(context, command: LifeBarDrawCommand) -> None:
    if (command.outer_bounds is None) != (command.inner_bounds is None):
        raise ValueError("outer_bounds and inner_bounds must both be provided or both be None")
    context.save()
    try:
        if command.outer_bounds is not None and command.inner_bounds is not None:
            geometry = command.duration_geometry
            if command.temporal_symbols is not None:
                # Draw only the guaranteed duration; symbols have their own
                # geometry and do not depend on a central rectangle's width.
                if geometry is not None:
                    _draw_duration_rectangles(context, command)
                for symbol in command.temporal_symbols:
                    draw_temporal_symbol(context, symbol)
                if command.label is not None:
                    draw_person_label(context, command)
                for indicator in command.symbol_indicators:
                    draw_symbol_indicator(context, indicator)
                return
            if geometry is None and command.outer_bounds[0] == command.outer_bounds[1]:
                if command.birth_indicator is not None:
                    zoom_y = (command.outer_bounds[3] - command.outer_bounds[2]) / LIFE_BAR_HEIGHT
                    draw_birth_indicator(context, command.birth_indicator, command.outer_bounds, zoom_y)
                return
            _draw_duration_rectangles(context, command)
            if command.outer_bounds[3] - command.outer_bounds[2] >= LIFE_BAR_HEIGHT * 0.5:
                if command.birth_before_geometry is not None:
                    _draw_triangle(context, command, command.birth_before_geometry)
                if command.death_before_geometry is not None:
                    _draw_triangle(context, command, command.death_before_geometry)
                if command.birth_after_geometry is not None:
                    _draw_triangle(context, command, command.birth_after_geometry)
                if command.death_after_geometry is not None:
                    _draw_triangle(context, command, command.death_after_geometry)
                if command.birth_span_geometry is not None:
                    _draw_span_rectangle(context, command, command.birth_span_geometry)
                if command.death_span_geometry is not None:
                    _draw_span_rectangle(context, command, command.death_span_geometry)
            if command.label is not None and (geometry is None or geometry.kind is not LifeDurationKind.ZERO):
                draw_person_label(context, command)
            if command.birth_indicator is not None and command.outer_bounds[1] > command.outer_bounds[0]:
                zoom_y = (command.outer_bounds[3] - command.outer_bounds[2]) / LIFE_BAR_HEIGHT
                draw_birth_indicator(context, command.birth_indicator, command.outer_bounds, zoom_y)
            return
        context.set_line_width(LIFE_BAR_LINE_WIDTH)
        context.set_source_rgb(*command.color)
        context.move_to(*command.start)
        context.line_to(*command.end)
        context.stroke()
    finally:
        context.restore()


def measure_person_label(context, command: LifeBarDrawCommand):
    """Prepare the exact baseline and ink bounds used by drawing and picking."""
    if command.label is None or command.inner_bounds is None:
        return None
    geometry = command.duration_geometry
    if command.temporal_symbols is None and (
        (geometry is not None and geometry.kind is LifeDurationKind.ZERO)
        or (geometry is None and command.outer_bounds[0] == command.outer_bounds[1])
    ):
        return None
    left, right, top, bottom = command.inner_bounds
    if bottom <= top:
        return
    zoom_y = (command.outer_bounds[3] - command.outer_bounds[2]) / LIFE_BAR_HEIGHT
    if zoom_y < 0.5:
        return
    margin = 4.0 * zoom_y
    # Cairo defaults to normal slant and normal weight.
    context.select_font_face("sans-serif")
    context.set_font_size(16.0 * zoom_y)
    x_bearing, y_bearing, width, height, _, _ = context.text_extents(command.label.display_name)
    if height > bottom - top:
        return
    x = left + margin - x_bearing
    y = (top + bottom - height) / 2.0 - y_bearing
    return (x, y), (x + x_bearing, x + x_bearing + width,
                    y + y_bearing, y + y_bearing + height)


def draw_person_label(context, command: LifeBarDrawCommand) -> None:
    measured = measure_person_label(context, command)
    if measured is None:
        return
    (x, y), _ = measured
    context.set_source_rgb(0.0, 0.0, 0.0)
    context.move_to(x, y)
    context.show_text(command.label.display_name)


def measure_person_graphics(context, placement, transform, *, model):
    """Emprise complète du même dessin individuel, sans clipping ni liens familiaux."""
    import cairo

    command = build_colored_person_life_bar_command(placement, transform, model=model)
    if command is None:
        return None
    target = context.get_target()
    scale_x, scale_y = target.get_device_scale()
    if not all(isfinite(value) and value > 0 for value in (scale_x, scale_y)):
        return None
    surface = cairo.RecordingSurface(cairo.CONTENT_COLOR_ALPHA, None)
    surface.set_device_scale(scale_x, scale_y)
    recorder = cairo.Context(surface)
    options = target.get_font_options()
    options.merge(context.get_font_options())
    recorder.set_font_options(options)
    draw_life_bar(recorder, command)
    x, y, width, height = surface.ink_extents()
    if width <= 0 or height <= 0:
        return None
    return x / scale_x, (x + width) / scale_x, y / scale_y, (y + height) / scale_y


def draw_temporal_guides(context, transform: ViewportTransform, width: float, height: float) -> None:
    """Repères calendaires en coordonnées écran, sous le contenu de la vue."""
    if width <= 0.0 or height <= 0.0:
        return
    years = visible_year_ticks(transform, width, guides=True)
    if not years:
        return
    context.save()
    try:
        context.new_path()
        context.rectangle(0.0, 0.0, width, height)
        context.clip()
        context.set_source_rgb(168 / 255, 168 / 255, 168 / 255)
        context.set_line_width(1.0)
        context.set_line_cap(0)  # Cairo LINE_CAP_BUTT, sans importer Cairo.
        context.set_dash((2.0, 4.0), 0.0)
        context.new_path()
        for year in years:
            x = project_year_tick_x(year, transform)
            context.move_to(x, 0.0)
            context.line_to(x, height)
        context.stroke()
    finally:
        context.restore()


def render_viewport(
    context: object,
    layout: TimelineLayout,
    controller: ViewportController,
    *, line_cap_butt=None, selected_person_placement: PersonPlacement | None = None,
) -> None:
    transform = controller.transform
    if transform is None:
        return
    selection_options = (
        {} if selected_person_placement is None
        else {"selected_person_placement": selected_person_placement}
    )
    model = getattr(controller, "model", None)
    if model is not None:
        selection_options["model"] = model
    if line_cap_butt is None:
        render_timeline(context, layout, transform, **selection_options)
    else:
        render_timeline(context, layout, transform, line_cap_butt=line_cap_butt, **selection_options)


def render_timeline(
    context,
    layout: TimelineLayout,
    transform: ViewportTransform,
    *, line_cap_butt=None, selected_person_placement: PersonPlacement | None = None,
    model: TimelineModel | None = None,
) -> None:
    model_options = {} if model is None else {"model": model}
    if selected_person_placement is None:
        render_person_life_bars(context, layout, transform, **model_options)
    else:
        render_person_life_bars(
            context, layout, transform, selected_person_placement=selected_person_placement,
            **model_options,
        )
    if line_cap_butt is None:
        render_divorce_nodes(context, layout, transform)
    else:
        render_divorce_nodes(context, layout, transform, line_cap_butt=line_cap_butt)
    render_remarriage_segments(context, layout, transform)
    render_marriage_nodes(context, layout, transform)
    render_branch_references(context, layout, transform)


def render_branch_references(
    context,
    layout: TimelineLayout,
    transform: ViewportTransform,
) -> None:
    text = "Descendance déjà décrite plus haut"
    for placement in layout.branch_reference_placements:
        if placement.x is None:
            continue
        x, y = transform.logical_to_screen(placement.x, placement.y)
        context.save()
        try:
            context.select_font_face("sans-serif")
            context.set_font_size(16.0 * transform.zoom_y)
            x_bearing, y_bearing, width, height, _, _ = context.text_extents(text)
            context.set_source_rgb(0.0, 0.0, 0.0)
            context.move_to(x - x_bearing, y - height / 2.0 - y_bearing)
            context.show_text(text)
        finally:
            context.restore()


def render_person_life_bars(
    context,
    layout: TimelineLayout,
    transform: ViewportTransform,
    *,
    provider: Callable[[int], tuple[float, float, float]] | None = None,
    selected_person_placement: PersonPlacement | None = None,
    model: TimelineModel | None = None,
) -> None:
    model_options = {} if model is None else {"model": model}
    if selected_person_placement is not None:
        for placement in layout.person_placements:
            command = build_colored_person_life_bar_command(
                placement, transform, provider=provider, **model_options,
            )
            if command is None:
                continue
            draw_life_bar(context, command)
            if placement is selected_person_placement:
                draw_life_bar_selection_contour(context, command, 3.0 * transform.zoom_y)
        return
    commands = build_person_life_bar_commands(layout, transform, provider=provider, **model_options)
    draw_life_bar_commands(context, commands)


def draw_life_bar_selection_contour(context, command: LifeBarDrawCommand, thickness: float) -> None:
    """Ajoute un contour intérieur sans agrandir le rectangle de la barre."""
    geometry = command.duration_geometry
    if geometry is not None:
        if not geometry.detailed or geometry.kind is LifeDurationKind.SHORT:
            return
        if geometry.kind is LifeDurationKind.ZERO:
            left, right, top, bottom = geometry.bounds
            side_width = (right - left) / 2.0
            context.save()
            try:
                context.set_source_rgb(0.0, 0.0, 0.0)
                context.new_path()
                context.rectangle(left - side_width, top, side_width, bottom - top)
                context.rectangle(right, top, side_width, bottom - top)
                context.fill()
            finally:
                context.restore()
            return
    left, right, top, bottom = command.outer_bounds
    if right == left:
        return
    inset_x = min(thickness, (right - left) / 2.0)
    inset_y = min(thickness, (bottom - top) / 2.0)
    context.save()
    try:
        context.set_source_rgb(0.0, 0.0, 0.0)
        context.new_path()
        context.rectangle(left, top, right - left, inset_y)
        context.rectangle(left, bottom - inset_y, right - left, inset_y)
        context.rectangle(left, top + inset_y, inset_x, bottom - top - 2 * inset_y)
        context.rectangle(right - inset_x, top + inset_y, inset_x, bottom - top - 2 * inset_y)
        context.fill()
    finally:
        context.restore()


def render_marriage_nodes(
    context,
    layout: TimelineLayout,
    transform: ViewportTransform,
) -> None:
    commands = build_marriage_node_commands(layout, transform)
    draw_marriage_node_commands(context, commands)


def render_divorce_nodes(
    context,
    layout: TimelineLayout,
    transform: ViewportTransform,
    *, line_cap_butt=None,
) -> None:
    commands = build_divorce_node_commands(layout, transform)
    if line_cap_butt is None:
        draw_divorce_node_commands(context, commands)
    else:
        draw_divorce_node_commands(context, commands, line_cap_butt=line_cap_butt)


def render_remarriage_segments(
    context: object,
    layout: TimelineLayout,
    transform: ViewportTransform,
) -> None:
    commands = build_remarriage_segment_commands(layout, transform)
    draw_remarriage_segment_commands(context, commands)


def draw_remarriage_segment_commands(
    context: object,
    commands: tuple[RemarriageSegmentDrawCommand, ...],
) -> None:
    for command in commands:
        draw_remarriage_segment(context, command)


def draw_divorce_node_commands(
    context,
    commands: tuple[DivorceNodeDrawCommand, ...],
    *, line_cap_butt=None,
) -> None:
    for command in commands:
        if line_cap_butt is None:
            draw_divorce_node(context, command)
        else:
            draw_divorce_node(context, command, line_cap_butt=line_cap_butt)


def draw_marriage_node_commands(
    context,
    commands: tuple[MarriageNodeDrawCommand, ...],
) -> None:
    for command in commands:
        draw_marriage_node(context, command)


def draw_life_bar_commands(
    context,
    commands: tuple[LifeBarDrawCommand, ...],
) -> None:
    for command in commands:
        draw_life_bar(context, command)


def build_person_life_bar_commands(
    layout: TimelineLayout,
    transform: ViewportTransform,
    *,
    provider: Callable[[int], tuple[float, float, float]] | None = None,
    model: TimelineModel | None = None,
) -> tuple[LifeBarDrawCommand, ...]:
    commands = []
    model_options = {} if model is None else {"model": model}
    for placement in layout.person_placements:
        command = build_colored_person_life_bar_command(
            placement, transform, provider=provider,
            **model_options,
        )
        if command is not None:
            commands.append(command)
    return tuple(commands)


def build_colored_person_life_bar_command(
    placement: PersonPlacement,
    transform: ViewportTransform,
    *,
    provider: Callable[[int], tuple[float, float, float]] | None = None,
    model: TimelineModel | None = None,
) -> LifeBarDrawCommand | None:
    color = color_for_person_placement(placement, provider=provider)
    command = build_person_life_bar_command(placement, transform, color)
    qualified = getattr(model, "graphical_qualifications", {}) if model is not None else {}
    birth_target = TemporalTarget(TemporalOwnerType.PERSON, placement.person_id, TargetSemantic.BIRTH)
    death_target = TemporalTarget(TemporalOwnerType.PERSON, placement.person_id, TargetSemantic.DEATH)
    birth = placement.birth_qualification or qualified.get(birth_target)
    death = placement.death_qualification or qualified.get(death_target)
    if command is not None and (birth is not None or death is not None
                                or placement.life_bar_kind is LifeBarKind.NO_GUARANTEED_INTERVAL):
        if model is not None:
            command = replace(command, label=PersonLabel(placement, model.data.persons[placement.person_id].display_name))
        return build_person_symbols(command, placement, birth, death, transform)
    if command is not None:
        command = replace(command, birth_position_qualification=placement.birth_position_qualification)
    if command is not None and model is not None:
        command = replace(command, label=PersonLabel(
            placement, model.data.persons[placement.person_id].display_name,
        ))
    if (
        command is not None
        and placement.x_start_kind in (
            PositionKind.VISUAL_FALLBACK, PositionKind.REPRESENTATIVE, PositionKind.DOMAIN_DISPLAY,
        )
    ):
        command = replace(
            command, birth_visual_qualification=qualify_visual_position(placement.x_start_kind),
        )
        if (
            command.birth_indicator is None
            and command.birth_visual_qualification is not None
            and should_show_visual_fallback_indicator(command.birth_visual_qualification)
        ):
            command = replace(command, birth_indicator=LifeBarIndicatorDrawCommand(
                kind=LifeBarIndicatorKind.VISUAL_FALLBACK,
            ))
    if (
        command is not None
        and command.death_qualification is None
        and placement.x_end_kind is PositionKind.VISUAL_FALLBACK
    ):
        command = replace(
            command, death_visual_qualification=qualify_visual_position(placement.x_end_kind),
        )
    return command


def build_person_life_bar_command(
    placement: PersonPlacement,
    transform: ViewportTransform,
    color: tuple[float, float, float],
) -> LifeBarDrawCommand | None:
    endpoints = project_person_life_bar(placement, transform)
    if endpoints is None:
        return None
    outer_bounds = project_person_life_bar_rectangle(placement, transform)
    left, right, top, bottom = outer_bounds
    border_width = 2.0 * transform.zoom_y
    inset_x = min(border_width, (right - left) / 2.0)
    inner_bounds = (
        left + inset_x, right - inset_x,
        top + border_width, bottom - border_width,
    )
    return LifeBarDrawCommand(
        start=endpoints[0], end=endpoints[1], color=color,
        outer_bounds=outer_bounds, inner_bounds=inner_bounds,
        border_width=border_width,
        duration_geometry=project_life_duration(placement, transform, projected_bounds=outer_bounds),
    )


def build_marriage_node_commands(
    layout: TimelineLayout,
    transform: ViewportTransform,
) -> tuple[MarriageNodeDrawCommand, ...]:
    commands = []
    for placement in layout.marriage_node_placements:
        if placement.descendant_y is None or placement.spouse_y is None:
            commands.append(build_marriage_node_command(placement, transform))
            continue
        commands.append(build_marriage_node_command(
            replace(placement, y=placement.descendant_y), transform,
        ))
        if placement.spouse_y != placement.descendant_y:
            commands.append(build_marriage_node_command(
                replace(placement, y=placement.spouse_y), transform,
            ))
    return tuple(commands)


def build_marriage_node_command(
    placement: MarriageNodePlacement,
    transform: ViewportTransform,
) -> MarriageNodeDrawCommand:
    path_radius, stroke_width = project_marriage_circle_cairo_dimensions(transform)
    return MarriageNodeDrawCommand(
        center=project_marriage_node(placement, transform),
        radius=path_radius,
        stroke_width=stroke_width,
    )


def build_divorce_node_commands(
    layout: TimelineLayout,
    transform: ViewportTransform,
) -> tuple[DivorceNodeDrawCommand, ...]:
    return tuple(
        build_divorce_node_command(placement, transform)
        for placement in layout.divorce_node_placements
    )


def build_divorce_node_command(
    placement: DivorceNodePlacement,
    transform: ViewportTransform,
) -> DivorceNodeDrawCommand:
    half_size, stroke_width = project_divorce_x_cairo_dimensions(transform)
    return DivorceNodeDrawCommand(
        center=project_divorce_node(placement, transform),
        half_size=half_size,
        stroke_width=stroke_width,
    )


def build_remarriage_segment_commands(
    layout: TimelineLayout,
    transform: ViewportTransform,
) -> tuple[RemarriageSegmentDrawCommand, ...]:
    commands = []
    for placement in layout.remarriage_segment_placements:
        command = build_remarriage_segment_command(placement, transform)
        if command is not None:
            commands.append(command)
    return tuple(commands)


def build_remarriage_segment_command(
    placement: RemarriageSegmentPlacement,
    transform: ViewportTransform,
) -> RemarriageSegmentDrawCommand | None:
    start, end = project_remarriage_segment(placement, transform)
    outer_radius = project_marriage_circle_outer_diameter(transform) / 2.0
    endpoints = trim_remarriage_segment_to_circle_edges(start, end, outer_radius)
    if endpoints is None:
        return None
    return RemarriageSegmentDrawCommand(
        start=endpoints[0], end=endpoints[1],
        stroke_width=REMARRIAGE_SEGMENT_LINE_WIDTH * transform.zoom_y,
    )


def trim_remarriage_segment_to_circle_edges(
    start: tuple[float, float],
    end: tuple[float, float],
    outer_radius: float = MARRIAGE_NODE_RADIUS,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Raccourcit en coordonnées écran le segment, s'il reste visible."""
    distance = abs(end[1] - start[1])
    if distance <= 2 * outer_radius:
        return None
    direction = 1.0 if end[1] > start[1] else -1.0
    return (
        (start[0], start[1] + direction * outer_radius),
        (end[0], end[1] - direction * outer_radius),
    )


def project_remarriage_segment(
    placement: RemarriageSegmentPlacement,
    transform: ViewportTransform,
) -> tuple[tuple[float, float], tuple[float, float]]:
    return (
        transform.logical_to_screen(placement.x, placement.y_start),
        transform.logical_to_screen(placement.x, placement.y_end),
    )


def project_divorce_node(
    placement: DivorceNodePlacement,
    transform: ViewportTransform,
) -> tuple[float, float]:
    return transform.logical_to_screen(placement.x, placement.y)


def project_marriage_node(
    placement: MarriageNodePlacement,
    transform: ViewportTransform,
) -> tuple[float, float]:
    return transform.logical_to_screen(placement.x, placement.y)


def project_person_life_bar(
    placement: PersonPlacement,
    transform: ViewportTransform,
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Projette une barre complète, ou retourne None si une extrémité manque."""
    x_start = placement.bar_x_start
    x_end = placement.bar_x_end
    if x_start is None or x_end is None:
        return None
    return (
        transform.logical_to_screen(x_start, placement.y),
        transform.logical_to_screen(x_end, placement.y),
    )
