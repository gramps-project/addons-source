"""Collecte FIFO des références accessibles depuis une racine Gramps."""

from collections import deque
from contextlib import nullcontext
from functools import partial

from descendants_timeline.cooperative_steps import complete
from descendants_timeline.gramps_data_adapter import GrampsDataAdapter
from descendants_timeline.gramps_data_converter import convert_date_is_empty, convert_event, convert_event_date_object, convert_family, convert_person
from descendants_timeline.gramps_date_normalization import normalize_gramps_date
from descendants_timeline.model.genealogy import RawGenealogyData
from descendants_timeline.model.temporal import TemporalValue


class GrampsDataLoader:
    def __init__(self, adapter, name_formatter, *, diagnostics=None):
        self._adapter = adapter
        self._name_formatter = name_formatter
        self._diagnostics = diagnostics

    def __call__(self, root_handle, *, diagnostics=None) -> RawGenealogyData:
        return complete(self._iter_load(root_handle, diagnostics=diagnostics))

    def _iter_load(self, root_handle, *, diagnostics=None):
        diagnostics = self._diagnostics if diagnostics is None else diagnostics
        with (
            diagnostics.phase("collection")
            if diagnostics is not None
            else nullcontext()
        ):
            persons = {}
            families = {}
            events = {}
            date_normalization_diagnostics = []
            pending = deque()
            scheduled = set()

            def schedule(object_type, handle):
                task = (object_type, handle)
                if task not in scheduled:
                    scheduled.add(task)
                    pending.append(task)

            readers = {
                "person": self._adapter.get_person,
                "family": self._adapter.get_family,
                "event": self._adapter.get_event,
            }
            if diagnostics is not None and isinstance(self._adapter, GrampsDataAdapter):
                readers = {
                    kind: partial(reader, diagnostics=diagnostics)
                    for kind, reader in readers.items()
                }
            schedule("person", root_handle)
            yield None
            while pending:
                object_type, handle = pending.popleft()
                source = readers[object_type](handle)
                label = (
                    "Root person"
                    if object_type == "person" and handle == root_handle
                    else object_type.capitalize()
                )
                if source is None:
                    raise LookupError(f"{label} not found: {handle}")
                returned_handle = source.get_handle()
                if returned_handle != handle:
                    raise ValueError(
                        f"{label} handle mismatch: requested {handle}, returned {returned_handle}"
                    )

                if object_type == "person":
                    person = convert_person(source, self._name_formatter)
                    persons[person.person_id] = person
                    for ref in person.event_refs:
                        schedule("event", ref.event_id)
                    for family_id in person.family_ids:
                        schedule("family", family_id)
                    for family_id in person.parent_family_ids:
                        schedule("family", family_id)
                elif object_type == "family":
                    family = convert_family(source)
                    families[family.family_id] = family
                    for parent_id in (family.parent1_id, family.parent2_id):
                        if parent_id is not None:
                            schedule("person", parent_id)
                    for ref in family.child_refs:
                        schedule("person", ref.person_id)
                    for ref in family.event_refs:
                        schedule("event", ref.event_id)
                else:
                    date_object = convert_event_date_object(source)
                    temporal_value = TemporalValue.unknown()
                    if date_object is not None and not convert_date_is_empty(date_object):
                        result = normalize_gramps_date(
                            date_object, event_id=handle,
                        )
                        temporal_value = result.temporal_value
                        if result.diagnostic is not None:
                            date_normalization_diagnostics.append(result.diagnostic)
                    event = convert_event(source, temporal_value)
                    events[event.event_id] = event
                yield None

            data = RawGenealogyData(
                persons=persons,
                families=families,
                events=events,
                root_person_id=root_handle,
                date_normalization_diagnostics=tuple(date_normalization_diagnostics),
            )
            if diagnostics is not None:
                diagnostics.increment("persons_collected", len(data.persons))
                diagnostics.increment("families_collected", len(data.families))
                diagnostics.increment("events_collected", len(data.events))
            return data
