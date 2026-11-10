"""Pure D5.1 decision over the represented DFS and qualified absolute bounds."""

from descendants_timeline.model.temporal_target import TemporalOwnerType, TargetSemantic
from descendants_timeline.timeline.timeline_model import TimelineModel
from descendants_timeline.inference.reconciled_temporal_domain import ReconciledBoundOrigin


def has_admissible_temporal_anchor(model: TimelineModel) -> bool:
    """Use lot 1 bounds; family anchors must retain documentary provenance.

    Family qualifications already reflect the selected event, its role and
    documentary modifier exclusions. No new temporal qualification is needed.
    Presentation values and positions are deliberately not inputs here.
    """
    represented_people = {row.person_id for row in model.traversal.rows}
    represented_families = {occurrence.family_id for occurrence in model.traversal.family_occurrences}
    for target, qualification in model.graphical_qualifications.items():
        bounds = (qualification.minimum, qualification.maximum)
        if (
            target.owner_type is TemporalOwnerType.PERSON
            and target.owner_id in represented_people
            and target.semantic in (TargetSemantic.BIRTH, TargetSemantic.DEATH)
            and any(bound is not None for bound in bounds)
        ):
            return True
        if (
            target.owner_type is TemporalOwnerType.FAMILY
            and target.owner_id in represented_families
            and target.semantic in (TargetSemantic.MARRIAGE, TargetSemantic.DIVORCE)
            and any(
                bound is not None and bound.bound.origin is ReconciledBoundOrigin.GRAMPS
                for bound in bounds
            )
        ):
            return True
    return False
