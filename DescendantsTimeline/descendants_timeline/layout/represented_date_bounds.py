from datetime import date

from descendants_timeline.inference.reconciled_temporal_domain import ReconciledBoundOrigin
from descendants_timeline.temporal_bound_qualification import TemporalShape

from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.layout.position_kind import PositionKind
from descendants_timeline.model.temporal_target import TargetSemantic, TemporalOwnerType, TemporalTarget
from descendants_timeline.timeline.timeline_model import TimelineModel


def represented_date_bounds(
    model: TimelineModel,
    layout: TimelineLayout,
) -> tuple[date, date] | None:
    """Extent of represented temporal coordinates, not D5.1 admissibility.

    Qualified person bounds are those already filtered by the layout. Family
    nodes and conventional presences contribute their actual coordinates.
    Screen shapes, diagnostic offsets and selection areas add no dates.
    """
    dates = []
    for placement in layout.person_placements:
        if placement.person_id not in model.data.persons:
            raise ValueError(
                "person placement references unknown person"
            )
        if placement.visual_x is not None:
            dates.append(date.fromordinal(int(placement.visual_x)))
        for x, kind, semantic, qualification in (
            (placement.x_start, placement.x_start_kind, TargetSemantic.BIRTH, placement.birth_qualification),
            (placement.x_end, placement.x_end_kind, TargetSemantic.DEATH, placement.death_qualification),
        ):
            if x is None or kind is PositionKind.VISUAL_FALLBACK:
                continue
            target = TemporalTarget(
                owner_type=TemporalOwnerType.PERSON,
                owner_id=placement.person_id,
                semantic=semantic,
            )
            if qualification is None:
                qualification = model.graphical_qualifications.get(target)
            if qualification is not None:
                dates.extend(bound.bound.value for bound in
                             (qualification.minimum, qualification.maximum) if bound is not None)
                documentary_bound = (
                    qualification.minimum if qualification.shape is TemporalShape.AFTER
                    else qualification.maximum if qualification.shape is TemporalShape.BEFORE
                    else None
                )
                if (
                    documentary_bound is not None
                    and documentary_bound.bound.origin is ReconciledBoundOrigin.GRAMPS
                    and documentary_bound.documentary_value is not None
                    and documentary_bound.documentary_value.is_usable_as_evidence
                    and documentary_bound.documentary_boundary is not None
                ):
                    dates.append(documentary_bound.documentary_boundary)

    for placement in layout.marriage_node_placements:
        if placement.family_id not in model.data.families:
            raise ValueError(
                "marriage placement references unknown family"
            )
        dates.append(date.fromordinal(int(placement.x)))

    for placement in layout.divorce_node_placements:
        if placement.family_id not in model.data.families:
            raise ValueError(
                "divorce placement references unknown family"
            )
        dates.append(date.fromordinal(int(placement.x)))

    if not dates:
        return None
    return min(dates), max(dates)
