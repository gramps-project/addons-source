# Copyright (C) 2026 Philippe
# Distributed under the GNU General Public License, version 2.
# See the LICENSE file distributed with this addon.

"""Regression checks for the Gramps 6.0 review."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ADDON = Path(__file__).resolve().parents[1]
if str(ADDON) not in sys.path:
    sys.path.insert(0, str(ADDON))

from descendants_timeline.gramps_data_loader import GrampsDataLoader
from descendants_timeline.gramps_date_normalization import (
    DateNormalizationDiagnosticCode, DateNormalizationRejected, normalize_gramps_date,
)
from descendants_timeline.model.child_ref import ChildRelation
from descendants_timeline.model.temporal import TemporalValue
from descendants_timeline.traversal.descendance_traversal import (
    DescendanceMode, DescendanceTraversal, TraversalOptions,
)


class RegistrationTest(unittest.TestCase):
    def test_listing_registers_only_view_and_runtime_keeps_initializer(self):
        code = compile((ADDON / "descendants_timeline.gpr.py").read_bytes(),
                       "descendants_timeline.gpr.py", "exec")
        for build_script, expected in (
            (True, ["descendants_timeline"]),
            (False, ["descendants_timeline", "descendants_timeline_selector_init"]),
        ):
            with self.subTest(build_script=build_script):
                plugins = []
                env = dict(VIEW="VIEW", GENERAL="GENERAL", STABLE="STABLE", END="END", _=str)
                scope = {"register": lambda kind, **entry: plugins.append(entry)}
                if build_script:
                    scope["build_script"] = True
                exec(code, env, scope)
                self.assertEqual([plugin["id"] for plugin in plugins], expected)
                if not build_script:
                    self.assertTrue(plugins[1]["load_on_reg"])
                    self.assertFalse(plugins[1]["include_in_listing"])


class LoadingTest(unittest.TestCase):
    def setUp(self):
        try:
            from gramps.gen import lib
        except ModuleNotFoundError as error:
            if error.name != "gramps":
                raise
            self.skipTest("Gramps runtime required")
        self.lib = lib

    def person(self, handle):
        person = self.lib.Person()
        person.set_handle(handle)
        return person

    def load(self, persons, families=(), events=()):
        groups = [{item.get_handle(): item for item in items}
                  for items in (persons, families, events)]
        adapter = SimpleNamespace(get_person=groups[0].get, get_family=groups[1].get,
                                  get_event=groups[2].get)
        loader = GrampsDataLoader(adapter, lambda person: person.get_handle())
        before = [item.serialize() for group in groups for item in group.values()]
        steps = loader._iter_load(persons[0].get_handle())
        self.assertIsNone(next(steps))
        with self.assertRaises(StopIteration) as done:
            while True:
                next(steps)
        result = done.exception.value
        self.assertEqual(loader(persons[0].get_handle()), result)
        self.assertEqual([item.serialize() for group in groups for item in group.values()], before)
        return result

    def test_partial_range_rejected_locally_while_following_event_is_loaded(self):
        root = self.person("root")
        events = []
        for handle in ("partial", "exact"):
            event = self.lib.Event()
            event.set_handle(handle)
            event.set_type(self.lib.EventType.BIRTH if handle == "partial" else self.lib.EventType.DEATH)
            ref = self.lib.EventRef()
            ref.set_reference_handle(handle)
            root.add_event_ref(ref)
            events.append(event)
        partial, exact = (event.get_date_object() for event in events)
        raw = (0, 0, 1820, False, 0, 5, 1821, False)
        partial.set(modifier=self.lib.Date.MOD_RANGE, value=raw)
        exact.set_yr_mon_day(1880, 6, 15)
        with self.assertRaises(DateNormalizationRejected) as strict:
            normalize_gramps_date(partial, event_id="partial")
        self.assertEqual(strict.exception.diagnostic.code,
                         DateNormalizationDiagnosticCode.VALIDATION_UNDETERMINED)
        data = self.load([root], events=events)
        self.assertEqual(data.events["partial"].date, TemporalValue.unknown())
        self.assertEqual(data.events["partial"].date_document.dateval, raw)
        self.assertEqual(data.date_normalization_diagnostics, (strict.exception.diagnostic,))
        self.assertTrue(data.events["exact"].date.is_usable_as_evidence)

    def test_custom_father_relation_preserves_label_and_family_without_expanding_dfs(self):
        father, mother, custom, birth = (self.person(h) for h in ("father", "mother", "custom", "birth"))
        family = self.lib.Family()
        family.set_handle("family")
        family.set_father_handle("father")
        family.set_mother_handle("mother")
        for parent in (father, mother):
            parent.add_family_handle("family")
        for child in (custom, birth):
            child.add_parent_family_handle("family")
            ref = self.lib.ChildRef()
            ref.set_reference_handle(child.get_handle())
            if child is custom:
                ref.set_father_relation("Custom relationship to father")
                ref.set_mother_relation(self.lib.ChildRefType.BIRTH)
            else:
                ref.set_father_relation(self.lib.ChildRefType.BIRTH)
                ref.set_mother_relation("Custom relationship to mother")
            family.add_child_ref(ref)
        data = self.load([father, mother, custom, birth], families=[family])
        refs = data.families["family"].child_refs
        self.assertEqual([ref.person_id for ref in refs], ["custom", "birth"])
        self.assertIs(refs[0].relation_to_parent1, ChildRelation.CUSTOM)
        self.assertEqual(refs[0].custom_relation_to_parent1, "Custom relationship to father")
        self.assertIs(refs[0].relation_to_parent2, ChildRelation.BIRTH)
        self.assertIsNone(refs[0].custom_relation_to_parent2)
        self.assertIs(refs[1].relation_to_parent2, ChildRelation.CUSTOM)
        self.assertEqual(refs[1].custom_relation_to_parent2, "Custom relationship to mother")
        self.assertIsNone(refs[1].custom_relation_to_parent1)
        traversal = DescendanceTraversal()
        for mode in DescendanceMode:
            result = traversal.traverse(data, "father", TraversalOptions(mode))
            self.assertEqual([row.person_id for row in result.rows], ["father", "mother", "birth"])
        result = traversal.traverse(data, "mother")
        self.assertEqual([row.person_id for row in result.rows], ["mother", "father", "custom"])
