"""Moteur de calcul du layout logique de la timeline."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from datetime import date

from descendants_timeline.layout.branch_reference_placement import (
    BranchReferencePlacement,
)
from descendants_timeline.layout.diagnostic_placement import DiagnosticPlacement
from descendants_timeline.layout.divorce_node_placement import (
    DivorceNodePlacement,
)
from descendants_timeline.layout.marriage_node_placement import (
    MarriageNodePlacement,
)
from descendants_timeline.layout.remarriage_segment_placement import (
    RemarriageSegmentPlacement,
)
from descendants_timeline.layout.person_placement import PersonPlacement
from descendants_timeline.layout.position_kind import PositionKind
from descendants_timeline.layout.life_bar_kind import LifeBarKind
from descendants_timeline.temporal_bound_qualification import TemporalShape
from descendants_timeline.layout.timeline_layout import TimelineLayout
from descendants_timeline.timeline.timeline_model import TimelineModel
from descendants_timeline.layout.timeline_scale import TimelineScale
from descendants_timeline.layout.temporal_display_value import (
    determine_display_value,
    determine_renderable_display_value,
    qualify_accepted_display_position,
    TemporalPositionQualification,
    PositionProvenance,
)
from descendants_timeline.inference.bound_provenance import has_independent_bound_justification
from descendants_timeline.inference.reconciled_temporal_domain import ReconciledBoundOrigin
from descendants_timeline.model.temporal_target import (
    TargetSemantic,
    TemporalOwnerType,
    TemporalTarget,
)
from descendants_timeline.model.temporal_target_anomaly import TemporalTargetAnomalyType

from descendants_timeline.traversal.descendance_traversal import (
    FamilyTraversalState,
    TraversalRole,
)

class LayoutEngine:
    """Transforme un TimelineModel en placements logiques."""

    DEFAULT_TOP_MARGIN = 20.0
    DEFAULT_ROW_HEIGHT = 28.0
    # Distance géométrique sur l'axe X, sans signification temporelle.
    VISUAL_OFFSET = 365.0
    # Décalage graphique provisoire en coordonnées logiques, sans sens temporel.
    DIVORCE_DIAGNOSTIC_OFFSET = 30.0

    def build(self, model: TimelineModel, *, diagnostics=None) -> TimelineLayout:
        with (
            diagnostics.phase("layout")
            if diagnostics is not None
            else nullcontext()
        ):
            future_event_ids = frozenset(
                event_id
                for result in model.temporal_results.values()
                for anomaly in result.target_entry.anomalies
                if anomaly.anomaly_type is TemporalTargetAnomalyType.FUTURE_EVENT
                for event_id in anomaly.event_ids
            )
            scale = TimelineScale()
            person_placements = tuple(
                self._build_person_placement(
                    model=model,
                    future_event_ids=future_event_ids,
                    scale=scale,
                    row=row,
                    row_index=row_index,
                    visual_rank=row_index,
                )
                for row_index, row in enumerate(model.traversal.rows)
            )

            person_placements = self._resolve_visual_positions(model, person_placements, scale, future_event_ids)

            descendant_marriage_y_by_row = {}
            for occurrence in model.traversal.family_occurrences:
                if (
                    occurrence.descendant_row_index is None
                    or occurrence.spouse_person_id is None
                    or occurrence.spouse_row_index is None
                ):
                    continue
                row_index = occurrence.descendant_row_index
                family_ids = model.data.persons[occurrence.descendant_person_id].family_ids
                family_rank = family_ids.index(occurrence.family_id)
                previous = descendant_marriage_y_by_row.get(row_index)
                if previous is None or family_rank < previous[0]:
                    descendant_marriage_y_by_row[row_index] = (
                        family_rank,
                        (person_placements[row_index].y
                         + person_placements[occurrence.spouse_row_index].y) / 2.0,
                    )

            marriage_node_placements = []
            for occurrence in model.traversal.family_occurrences:
                if (
                    occurrence.spouse_person_id is None
                    or occurrence.spouse_row_index is None
                ):
                    continue

                marriage_target = TemporalTarget(
                    owner_type=TemporalOwnerType.FAMILY,
                    owner_id=occurrence.family_id,
                    semantic=TargetSemantic.MARRIAGE,
                )
                marriage_result = model.temporal_results.get(marriage_target)
                if marriage_result is None:
                    continue
                display_value = determine_renderable_display_value(
                    marriage_result, future_event_ids=future_event_ids, data=model.data,
                )
                if display_value is None:
                    continue

                descendant_y = person_placements[occurrence.descendant_row_index].y
                spouse_y = person_placements[occurrence.spouse_row_index].y
                y_marriage = (descendant_y + spouse_y) / 2.0
                preceding_bar_y = max(
                    placement.y for placement in person_placements
                    if placement.y < spouse_y
                )
                marriage_node_placements.append(
                    MarriageNodePlacement(
                        family_id=occurrence.family_id,
                        descendant_person_id=occurrence.descendant_person_id,
                        spouse_person_id=occurrence.spouse_person_id,
                        descendant_row_index=occurrence.descendant_row_index,
                        spouse_row_index=occurrence.spouse_row_index,
                        x=scale.date_to_x(
                            display_value
                        ),
                        y=y_marriage,
                        descendant_y=descendant_marriage_y_by_row[
                            occurrence.descendant_row_index
                        ][1],
                        spouse_y=(preceding_bar_y + spouse_y) / 2.0,
                    )
                )

            divorce_node_placements = []
            for occurrence in model.traversal.family_occurrences:
                if (
                    occurrence.descendant_person_id is None
                    or occurrence.descendant_row_index is None
                    or occurrence.spouse_person_id is None
                    or occurrence.spouse_row_index is None
                ):
                    continue

                divorce_target = TemporalTarget(
                    owner_type=TemporalOwnerType.FAMILY,
                    owner_id=occurrence.family_id,
                    semantic=TargetSemantic.DIVORCE,
                )
                divorce_result = model.temporal_results.get(divorce_target)
                if divorce_result is None:
                    continue
                display_value = determine_renderable_display_value(
                    divorce_result, future_event_ids=future_event_ids, data=model.data,
                )
                if display_value is None:
                    continue

                descendant_y = person_placements[occurrence.descendant_row_index].y
                divorce_node_placements.append(
                    DivorceNodePlacement(
                        family_id=occurrence.family_id,
                        descendant_person_id=occurrence.descendant_person_id,
                        spouse_person_id=occurrence.spouse_person_id,
                        descendant_row_index=occurrence.descendant_row_index,
                        spouse_row_index=occurrence.spouse_row_index,
                        x=scale.date_to_x(
                            display_value
                        ),
                        y=descendant_y + self.DEFAULT_ROW_HEIGHT / 2.0,
                    )
                )

            remarriage_segment_placements = []
            married_family_ids_by_person = {}
            for marriage in marriage_node_placements:
                person_id = marriage.descendant_person_id
                family_ids = married_family_ids_by_person.setdefault(person_id, set())
                if marriage.family_id in family_ids:
                    continue
                if family_ids:
                    remarriage_segment_placements.append(
                        RemarriageSegmentPlacement(
                            person_id=person_id,
                            x=marriage.x,
                            y_start=min(marriage.descendant_y, marriage.spouse_y),
                            y_end=max(marriage.descendant_y, marriage.spouse_y),
                        )
                    )
                family_ids.add(marriage.family_id)

            diagnostic_placements = []
            for placement in person_placements:
                diagnostic_x = placement.x_start if placement.x_start is not None else placement.visual_x
                if diagnostic_x is None:
                    continue
                birth_target = TemporalTarget(
                    owner_type=TemporalOwnerType.PERSON,
                    owner_id=placement.person_id,
                    semantic=TargetSemantic.BIRTH,
                )
                birth_result = model.temporal_results.get(birth_target)
                if (
                    birth_result is not None
                    and (
                        birth_result.constraint_resolution.conflict_type is not None
                        or birth_result.reconciled_domain.conflict_type is not None
                        or bool(birth_result.target_entry.anomalies)
                    )
                ):
                    diagnostic_placements.append(
                        DiagnosticPlacement(
                            target=birth_target,
                            x=diagnostic_x,
                            y=placement.y,
                        )
                    )

            for placement in person_placements:
                diagnostic_x = placement.x_end if placement.x_end is not None else placement.visual_x
                if diagnostic_x is None:
                    continue
                death_target = TemporalTarget(
                    owner_type=TemporalOwnerType.PERSON,
                    owner_id=placement.person_id,
                    semantic=TargetSemantic.DEATH,
                )
                death_result = model.temporal_results.get(death_target)
                if (
                    death_result is not None
                    and (
                        death_result.constraint_resolution.conflict_type is not None
                        or death_result.reconciled_domain.conflict_type is not None
                        or bool(death_result.target_entry.anomalies)
                    )
                ):
                    diagnostic_placements.append(
                        DiagnosticPlacement(
                            target=death_target,
                            x=diagnostic_x,
                            y=placement.y,
                        )
                    )

            for marriage_node in marriage_node_placements:
                marriage_target = TemporalTarget(
                    owner_type=TemporalOwnerType.FAMILY,
                    owner_id=marriage_node.family_id,
                    semantic=TargetSemantic.MARRIAGE,
                )
                marriage_result = model.temporal_results.get(marriage_target)
                if (
                    marriage_result is not None
                    and (
                        marriage_result.constraint_resolution.conflict_type is not None
                        or marriage_result.reconciled_domain.conflict_type is not None
                        or bool(marriage_result.target_entry.anomalies)
                    )
                ):
                    diagnostic_placements.append(
                        DiagnosticPlacement(
                            target=marriage_target,
                            x=marriage_node.x,
                            y=marriage_node.y,
                        )
                    )

            for divorce_node in divorce_node_placements:
                divorce_target = TemporalTarget(
                    owner_type=TemporalOwnerType.FAMILY,
                    owner_id=divorce_node.family_id,
                    semantic=TargetSemantic.DIVORCE,
                )
                divorce_result = model.temporal_results.get(divorce_target)
                if (
                    divorce_result is not None
                    and (
                        divorce_result.constraint_resolution.conflict_type is not None
                        or divorce_result.reconciled_domain.conflict_type is not None
                        or bool(divorce_result.target_entry.anomalies)
                    )
                ):
                    diagnostic_placements.append(
                        DiagnosticPlacement(
                            target=divorce_target,
                            x=divorce_node.x,
                            y=divorce_node.y,
                        )
                    )

            marriage_node_occurrences = {
                (node.family_id, node.descendant_row_index, node.spouse_row_index)
                for node in marriage_node_placements
            }
            divorce_node_occurrences = {
                (node.family_id, node.descendant_row_index, node.spouse_row_index)
                for node in divorce_node_placements
            }
            for occurrence in model.traversal.family_occurrences:
                if (
                    occurrence.descendant_person_id is None
                    or occurrence.descendant_row_index is None
                    or occurrence.spouse_person_id is None
                    or occurrence.spouse_row_index is None
                ):
                    continue
                occurrence_key = (
                    occurrence.family_id,
                    occurrence.descendant_row_index,
                    occurrence.spouse_row_index,
                )
                diagnostic_targets = []
                for semantic, node_occurrences, offset in (
                    (TargetSemantic.MARRIAGE, marriage_node_occurrences, 0.0),
                    (
                        TargetSemantic.DIVORCE,
                        divorce_node_occurrences,
                        self.DIVORCE_DIAGNOSTIC_OFFSET,
                    ),
                ):
                    if occurrence_key in node_occurrences:
                        continue
                    target = TemporalTarget(
                        owner_type=TemporalOwnerType.FAMILY,
                        owner_id=occurrence.family_id,
                        semantic=semantic,
                    )
                    result = model.temporal_results.get(target)
                    if result is not None and (
                        result.constraint_resolution.conflict_type is not None
                        or result.reconciled_domain.conflict_type is not None
                        or bool(result.target_entry.anomalies)
                    ):
                        diagnostic_targets.append((target, offset))
                if not diagnostic_targets:
                    continue
                descendant = person_placements[occurrence.descendant_row_index]
                spouse = person_placements[occurrence.spouse_row_index]
                descendant_complete = (
                    descendant.bar_x_start is not None
                    and descendant.bar_x_end is not None
                )
                spouse_complete = (
                    spouse.bar_x_start is not None
                    and spouse.bar_x_end is not None
                )
                if descendant_complete and spouse_complete:
                    shared_start = max(descendant.bar_x_start, spouse.bar_x_start)
                    shared_end = min(descendant.bar_x_end, spouse.bar_x_end)
                    diagnostic_x = (
                        (shared_start + shared_end) / 2
                        if shared_start <= shared_end
                        else (descendant.bar_x_start + descendant.bar_x_end) / 2
                    )
                elif descendant_complete:
                    diagnostic_x = (descendant.bar_x_start + descendant.bar_x_end) / 2
                elif spouse_complete:
                    diagnostic_x = (spouse.bar_x_start + spouse.bar_x_end) / 2
                else:
                    continue
                family_ids = model.data.persons[occurrence.descendant_person_id].family_ids
                diagnostic_y = (
                    (descendant.y + spouse.y) / 2
                    if occurrence.family_id == family_ids[0]
                    else descendant.y
                )
                for target, offset in diagnostic_targets:
                    diagnostic_placements.append(
                        DiagnosticPlacement(
                            target=target,
                            x=diagnostic_x + offset,
                            y=diagnostic_y,
                        )
                    )

            branch_reference_placements = []
            for occurrence in model.traversal.family_occurrences:
                if (
                    occurrence.state is not FamilyTraversalState.ALREADY_DESCRIBED
                    or occurrence.spouse_row_index is None
                ):
                    continue
                spouse_placement = person_placements[occurrence.spouse_row_index]
                x = (
                    spouse_placement.bar_x_end + self.VISUAL_OFFSET
                    if spouse_placement.bar_x_end is not None
                    else None
                )
                visual_rank = spouse_placement.visual_rank
                branch_reference_placements.append(
                    BranchReferencePlacement(
                        family_id=occurrence.family_id,
                        descendant_row_index=occurrence.descendant_row_index,
                        spouse_row_index=occurrence.spouse_row_index,
                        referenced_row_index=occurrence.referenced_row_index,
                        visual_rank=visual_rank,
                        y=spouse_placement.y,
                        x=x,
                    )
                )

            return TimelineLayout(
                person_placements=person_placements,
                marriage_node_placements=tuple(marriage_node_placements),
                remarriage_segment_placements=tuple(remarriage_segment_placements),
                diagnostic_placements=tuple(diagnostic_placements),
                divorce_node_placements=tuple(divorce_node_placements),
                branch_reference_placements=tuple(branch_reference_placements),
            )

    def _usable_bound(self, model, target, bound, future_event_ids):
        if bound is None:
            return None
        result = model.temporal_results[target]
        if any(a.anomaly_type is TemporalTargetAnomalyType.FUTURE_EVENT for a in result.target_entry.anomalies):
            return None
        if future_event_ids and not has_independent_bound_justification(
            bound.bound, future_event_ids, data=model.data, result=result,
        ):
            return None
        return bound

    def _resolve_visual_positions(self, model, placements, scale, future_event_ids):
        # Only own admissible references are sources. Conventional positions
        # never propagate as temporal references, so no recursive search occurs.
        own = {p.person_id: p.visual_x for p in placements if p.visual_x is not None}
        represented = {p.person_id for p in placements}
        families = {o.family_id for o in model.traversal.family_occurrences}
        anchors = []
        for target, qualification in model.graphical_qualifications.items():
            if not (
                (target.owner_type is TemporalOwnerType.PERSON and target.owner_id in represented)
                or (target.owner_type is TemporalOwnerType.FAMILY and target.owner_id in families)
            ):
                continue
            for source_bound in (qualification.minimum, qualification.maximum):
                bound = self._usable_bound(model, target, source_bound, future_event_ids)
                if bound is None:
                    continue
                if ((target.owner_type is TemporalOwnerType.PERSON and target.owner_id in represented)
                    or (target.owner_type is TemporalOwnerType.FAMILY and target.owner_id in families
                        and bound.bound.origin is ReconciledBoundOrigin.GRAMPS)):
                    anchors.append(scale.date_to_x(bound.bound.value))

        def family_reference(family):
            for ref in family.event_refs:
                event = model.data.events[ref.event_id]
                semantic = {'MARRIAGE': TargetSemantic.MARRIAGE,
                            'DIVORCE': TargetSemantic.DIVORCE}.get(event.semantic.value)
                if semantic is None:
                    continue
                target = TemporalTarget(TemporalOwnerType.FAMILY, family.family_id, semantic)
                qualification = model.graphical_qualifications.get(target)
                if qualification:
                    bound = (self._usable_bound(model, target, qualification.minimum, future_event_ids)
                             or self._usable_bound(model, target, qualification.maximum, future_event_ids))
                    if bound:
                        return scale.date_to_x(bound.bound.value)
            return None

        resolved = []
        for placement in placements:
            if placement.visual_x is not None:
                resolved.append(placement)
                continue
            person = model.data.persons[placement.person_id]
            # Start with the explicit Gramps order; occurrence order supplies
            # represented families omitted by incomplete legacy snapshots.
            own_family_ids = list(person.family_ids)
            for occurrence in model.traversal.family_occurrences:
                if (placement.person_id in (occurrence.descendant_person_id, occurrence.spouse_person_id)
                    and occurrence.family_id not in own_family_ids):
                    own_family_ids.append(occurrence.family_id)
            own_families = [model.data.families[f] for f in own_family_ids if f in families]
            x = next((value for family in own_families
                      if (value := family_reference(family)) is not None), None)
            if x is None:
                x = next((own[child.person_id] for family in own_families
                          for child in family.child_refs if child.person_id in own), None)
            if x is None:
                x = next((own[parent] for family in own_families
                          for parent in (family.parent1_id, family.parent2_id)
                          if parent != placement.person_id and parent in own), None)
            if x is None:
                parent_family_ids = list(person.parent_family_ids)
                if placement.family_id is not None and placement.family_id not in parent_family_ids:
                    parent_family_ids.append(placement.family_id)
                x = next((own[parent] for family_id in parent_family_ids if family_id in families
                          for parent in (model.data.families[family_id].parent1_id,
                                         model.data.families[family_id].parent2_id)
                          if parent in own), None)
            if x is None:
                x = min(anchors) if anchors else None
            resolved.append(replace(placement, visual_x=x,
                                    visual_position_kind=PositionKind.VISUAL_FALLBACK))
        return tuple(resolved)

    def _build_person_placement(
        self,
        model: TimelineModel,
        scale: TimelineScale,
        row,
        row_index: int,
        visual_rank: int,
        future_event_ids: frozenset[str],
    ) -> PersonPlacement:
        birth_target = TemporalTarget(
            owner_type=TemporalOwnerType.PERSON,
            owner_id=row.person_id,
            semantic=TargetSemantic.BIRTH,
        )
        death_target = TemporalTarget(
            owner_type=TemporalOwnerType.PERSON,
            owner_id=row.person_id,
            semantic=TargetSemantic.DEATH,
        )

        birth = model.graphical_qualifications.get(birth_target)
        death = model.graphical_qualifications.get(death_target)
        birth_maximum = self._usable_bound(model, birth_target, birth.maximum, future_event_ids) if birth else None
        birth_minimum = self._usable_bound(model, birth_target, birth.minimum, future_event_ids) if birth else None
        death_minimum = self._usable_bound(model, death_target, death.minimum, future_event_ids) if death else None
        death_maximum = self._usable_bound(model, death_target, death.maximum, future_event_ids) if death else None
        # Transport the existing display exclusions as well as the lot 1
        # projection. Preserve source qualifications and reuse them unchanged
        # whenever no bound was removed; Cairo never has to repeat this check.
        if birth is not None and (birth.minimum is not birth_minimum or birth.maximum is not birth_maximum):
            birth = replace(birth, minimum=birth_minimum, maximum=birth_maximum)
        if death is not None and (death.minimum is not death_minimum or death.maximum is not death_maximum):
            death = replace(death, minimum=death_minimum, maximum=death_maximum)
        birth_reference = birth_maximum or birth_minimum
        death_reference = death_minimum or death_maximum
        birth_exact = (birth_minimum is not None and birth_maximum is not None
                       and birth.shape is TemporalShape.EXACT)
        death_exact = (death_minimum is not None and death_maximum is not None
                       and death.shape is TemporalShape.EXACT)
        x_start = scale.date_to_x(birth_reference.bound.value) if birth_reference else None
        x_end = scale.date_to_x(death_reference.bound.value) if death_reference else None
        kind = LifeBarKind.NO_GUARANTEED_INTERVAL
        if birth_maximum is not None and death_minimum is not None:
            if birth_maximum.bound.value < death_minimum.bound.value:
                kind = LifeBarKind.NORMAL
            elif (birth_exact and death_exact
                  and birth_maximum.bound.value == death_minimum.bound.value):
                kind = LifeBarKind.ZERO_LENGTH
        birth_kind = (PositionKind.VISUAL_FALLBACK if birth_reference is None else
                      PositionKind.REPRESENTATIVE if birth_exact
                      else PositionKind.DOMAIN_DISPLAY)
        death_kind = (PositionKind.VISUAL_FALLBACK if death_reference is None else
                      PositionKind.REPRESENTATIVE if death_exact
                      else PositionKind.DOMAIN_DISPLAY)
        birth_position = None
        if birth_maximum is not None and not birth_exact:
            birth_position = TemporalPositionQualification(
                birth_maximum.bound.value,
                PositionProvenance.GRAMPS if birth_maximum.bound.origin is ReconciledBoundOrigin.GRAMPS
                else PositionProvenance.INFERENCE,
                (birth_maximum.bound,),
            )
        return PersonPlacement(
            person_id=row.person_id, row_index=row_index, visual_rank=visual_rank,
            generation=row.generation, role=row.role, family_id=row.family_id,
            spouse_of_person_id=row.spouse_of_person_id,
            x_start=x_start, x_start_kind=birth_kind, x_end=x_end, x_end_kind=death_kind,
            y=self.DEFAULT_TOP_MARGIN + visual_rank * self.DEFAULT_ROW_HEIGHT,
            life_bar_kind=kind, birth_qualification=birth, death_qualification=death,
            birth_position_qualification=birth_position,
            visual_x=x_start if x_start is not None else x_end,
            visual_position_kind=birth_kind if x_start is not None else death_kind,
        )
