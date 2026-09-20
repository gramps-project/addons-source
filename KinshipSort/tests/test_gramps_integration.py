#
# KinshipSort - biological kinship sorting for Gramps
# Copyright (C) 2026 Jacek Kuznia <jacek.kuznia@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""Tests using real Gramps objects, SQLite and GTK models in a test profile."""

# ------------------------------------------------------------------------
# Standard Python modules
# ------------------------------------------------------------------------
from pathlib import Path
import tempfile
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ------------------------------------------------------------------------
# GTK/Gnome and Gramps modules
# ------------------------------------------------------------------------
try:
    import gi
    from gi.repository import Gtk
    from gramps.gen.db import DbTxn
    from gramps.gen.db.dummydb import DummyDb
    from gramps.gen.lib import ChildRef, ChildRefType, Family, Person, Surname
    from gramps.plugins.db.dbapi.sqlite import SQLite
except ImportError as error:
    raise unittest.SkipTest("Requires the Gramps 6.0 and GTK Python environment") from error

# ------------------------------------------------------------------------
# Addon modules
# ------------------------------------------------------------------------
from kinshipsort import (
    KINSHIP_COL, TAG_COLOR_COL, KinshipBaseView,
    KinshipPersonListModel, KinshipPersonTreeModel, calculate_kinship_info,
)


class GrampsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="kinshipsort-test-")
        self.db = SQLite()
        self.db.load(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.db.close)
        self.uistate = SimpleNamespace(window=None)
        self.models = []
        self.addCleanup(self.destroy_models)

    def destroy_models(self):
        for model in self.models:
            model.destroy()

    def person(self, handle, surname="Test", first=None):
        person = Person()
        person.set_handle(handle)
        name = person.get_primary_name()
        name.set_first_name(first or handle)
        family_name = Surname()
        family_name.set_surname(surname)
        name.add_surname(family_name)
        person.set_primary_name(name)
        with DbTxn("Add synthetic person", self.db) as transaction:
            self.db.add_person(person, transaction)
        return person

    def family(self, father, mother, child, father_relation=ChildRefType.BIRTH,
               mother_relation=ChildRefType.BIRTH):
        family = Family()
        family.set_father_handle(father)
        family.set_mother_handle(mother)
        ref = ChildRef()
        ref.ref = child
        ref.set_father_relation(father_relation)
        ref.set_mother_relation(mother_relation)
        family.add_child_ref(ref)
        with DbTxn("Add synthetic family", self.db) as transaction:
            self.db.add_family(family, transaction)
            for handle in (father, mother):
                if handle:
                    parent = self.db.get_person_from_handle(handle)
                    parent.add_family_handle(family.handle)
                    self.db.commit_person(parent, transaction)
            person = self.db.get_person_from_handle(child)
            person.add_parent_family_handle(family.handle)
            self.db.commit_person(person, transaction)
        return family

    def sibling(self, family, child, father_relation=ChildRefType.BIRTH,
                mother_relation=ChildRefType.BIRTH):
        ref = ChildRef()
        ref.ref = child
        ref.set_father_relation(father_relation)
        ref.set_mother_relation(mother_relation)
        family.add_child_ref(ref)
        with DbTxn("Add synthetic sibling", self.db) as transaction:
            self.db.commit_family(family, transaction)
            person = self.db.get_person_from_handle(child)
            person.add_parent_family_handle(family.handle)
            self.db.commit_person(person, transaction)

    def fixture(self):
        for handle, surname in [("home", "Baker"), ("parent", "Baker"),
                                ("sibling", "Baker"), ("child", "Baker"),
                                ("spouse", "Adams"), ("stranger", "Zulu")]:
            self.person(handle, surname)
        self.family("parent", None, "home")
        self.family("parent", None, "sibling")
        self.family("home", "spouse", "child")
        self.db.set_default_person_handle("home")

    def model(self, model_class, **kwargs):
        model = model_class(self.db, self.uistate, **kwargs)
        self.models.append(model)
        return model

    @staticmethod
    def handles(model):
        if isinstance(model, KinshipPersonListModel):
            return [model.get_handle_from_iter(model.get_iter(Gtk.TreePath((index,))))
                    for index in range(len(model.node_map))]
        if not model.tree:
            return []
        found = []
        def visit(parent=None):
            iterator = model.iter_children(parent)
            while iterator is not None:
                handle = model.get_handle_from_iter(iterator)
                if handle:
                    found.append(handle)
                if model.iter_has_child(iterator):
                    visit(iterator)
                iterator = model.iter_next(iterator)
        visit()
        return found

    def test_closed_database_and_none(self):
        self.assertEqual(calculate_kinship_info(None), ({}, {}, None))
        self.assertEqual(calculate_kinship_info(DummyDb()), ({}, {}, None))
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            model = cls(DummyDb(), self.uistate)
            self.models.append(model)
            self.assertEqual(model.kinship_degrees, {})
            self.assertEqual(self.handles(model), [])

    def test_no_home_and_stale_home(self):
        self.person("person")
        self.assertEqual(calculate_kinship_info(self.db), ({}, {}, None))
        self.db.set_default_person_handle("missing")
        self.assertEqual(calculate_kinship_info(self.db), ({}, {}, None))

    def test_birth_relation_is_checked_separately_for_each_parent(self):
        for handle in ("home", "biological", "adoptive", "foster", "child"):
            self.person(handle)
        self.family("biological", "adoptive", "home", mother_relation=ChildRefType.ADOPTED)
        self.family("home", "foster", "child", father_relation=ChildRefType.FOSTER)
        self.db.set_default_person_handle("home")
        degrees, generations, home = calculate_kinship_info(self.db)
        self.assertEqual(degrees, {"home": 0, "biological": 1})
        self.assertEqual(generations, {"home": 0, "biological": 1})
        self.assertEqual(home, "home")

    def test_calculation_does_not_change_genealogical_records(self):
        self.fixture()
        def records():
            return ([self.db.get_person_from_handle(h).serialize()
                     for h in sorted(self.db.get_person_handles())],
                    [self.db.get_family_from_handle(h).serialize()
                     for h in sorted(self.db.get_family_handles())])
        before = records()
        degrees, _, _ = calculate_kinship_info(self.db)
        self.assertEqual(degrees, {"home": 0, "parent": 1, "child": 1, "sibling": 2})
        self.assertEqual(records(), before)

    def test_degrees_match_core_for_recorded_common_ancestors(self):
        from gramps.gen.relationship import RelationshipCalculator

        self.fixture()
        for handle in ("grandparent", "aunt", "cousin", "adoptive", "foster"):
            self.person(handle)
        self.family("grandparent", None, "parent")
        self.family("grandparent", None, "aunt")
        self.family("aunt", None, "cousin")
        self.family("adoptive", None, "home", father_relation=ChildRefType.ADOPTED)
        self.family("home", None, "foster", father_relation=ChildRefType.FOSTER)
        # A second parent family makes the spouse a blood relative as well.
        self.family("parent", None, "spouse")
        degrees, generations, _ = calculate_kinship_info(self.db)
        calculator = RelationshipCalculator()
        calculator.set_depth(20)
        home = self.db.get_person_from_handle("home")
        for handle in self.db.get_person_handles():
            with self.subTest(person=handle):
                relations, messages = calculator.get_relationship_distance_new(
                    self.db, home, self.db.get_person_from_handle(handle),
                    all_families=True, all_dist=True, only_birth=True)
                self.assertEqual(messages, [])
                valid = [(relation[0], len(relation[2]) - len(relation[4]))
                         for relation in relations if relation[0] >= 0]
                if valid:
                    degree, generation = min(valid, key=lambda pair: (pair[0], -pair[1]))
                    self.assertEqual((degrees[handle], generations[handle]),
                                     (degree, generation))
                else:
                    self.assertNotIn(handle, degrees)

    def test_flat_order_and_live_reverse(self):
        self.fixture()
        model = self.model(KinshipPersonListModel, scol=KINSHIP_COL)
        expected = ["home", "parent", "child", "sibling", "spouse", "stranger"]
        self.assertEqual(self.handles(model), expected)
        model.reverse_order()
        self.assertEqual(self.handles(model), list(reversed(expected)))
        descending = self.model(KinshipPersonListModel, scol=KINSHIP_COL,
                                order=Gtk.SortType.DESCENDING)
        self.assertEqual(self.handles(descending), list(reversed(expected)))

    def test_siblings_and_descendants_without_recorded_parents(self):
        for handle in ("home", "brother", "sister", "niece", "grandniece",
                       "child", "spouse", "other_family"):
            self.person(handle)
        family = self.family(None, None, "home")
        self.sibling(family, "brother")
        self.sibling(family, "sister")
        self.family("brother", None, "niece")
        self.family("niece", None, "grandniece")
        self.family("home", "spouse", "child")
        self.family(None, None, "other_family")
        self.db.set_default_person_handle("home")
        def records():
            return ([self.db.get_person_from_handle(h).serialize()
                     for h in sorted(self.db.get_person_handles())],
                    [self.db.get_family_from_handle(h).serialize()
                     for h in sorted(self.db.get_family_handles())])
        before = records()
        degrees, generations, _ = calculate_kinship_info(self.db)
        expected = {"home": 0, "brother": 2, "sister": 2, "niece": 3,
                    "grandniece": 4, "child": 1}
        self.assertEqual(degrees, expected)
        self.assertEqual(generations, {"home": 0, "brother": 0, "sister": 0,
                                      "niece": -1, "grandniece": -2, "child": -1})
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            model = self.model(cls, scol=KINSHIP_COL)
            self.assertEqual(model.kinship_degrees, expected)
        self.assertEqual(records(), before)
        self.db.set_default_person_handle("child")
        degrees, generations, _ = calculate_kinship_info(self.db)
        self.assertEqual((degrees["brother"], generations["brother"]), (3, 1))
        self.assertEqual((degrees["niece"], generations["niece"]), (4, 0))
        self.assertEqual(degrees["grandniece"], 5)

    def test_missing_parent_requires_birth_relation_to_the_same_parent(self):
        for missing in ("father", "mother", "both"):
            with self.subTest(missing=missing):
                names = {role: f"{missing}-{role}" for role in
                         ("home", "sibling", "opposite", "adopted", "foster", "known")}
                for handle in names.values():
                    self.person(handle)
                father = names["known"] if missing == "mother" else None
                mother = names["known"] if missing == "father" else None
                birth = (ChildRefType.BIRTH, ChildRefType.ADOPTED)
                if missing == "mother":
                    birth = tuple(reversed(birth))
                family = self.family(father, mother, names["home"], *birth)
                self.sibling(family, names["sibling"], *birth)
                self.sibling(family, names["opposite"], *reversed(birth))
                self.sibling(family, names["adopted"],
                             ChildRefType.ADOPTED, ChildRefType.ADOPTED)
                self.sibling(family, names["foster"],
                             ChildRefType.FOSTER, ChildRefType.FOSTER)
                self.db.set_default_person_handle(names["home"])
                degrees, _, _ = calculate_kinship_info(self.db)
                self.assertEqual(degrees, {names["home"]: 0, names["sibling"]: 2})

    def test_adding_parent_preserves_sibling_degrees(self):
        for handle in ("home", "sibling", "niece", "parent"):
            self.person(handle)
        family = self.family(None, None, "home")
        self.sibling(family, "sibling")
        self.family("sibling", None, "niece")
        self.db.set_default_person_handle("home")
        before, _, _ = calculate_kinship_info(self.db)
        self.assertEqual(before, {"home": 0, "sibling": 2, "niece": 3})
        family.set_father_handle("parent")
        with DbTxn("Record previously unknown parent", self.db) as transaction:
            self.db.commit_family(family, transaction)
            parent = self.db.get_person_from_handle("parent")
            parent.add_family_handle(family.handle)
            self.db.commit_person(parent, transaction)
        after, _, _ = calculate_kinship_info(self.db)
        self.assertEqual(after, dict(before, parent=1))

    def test_separate_unknown_parent_families_do_not_infer_transitive_kinship(self):
        for handle in ("home", "half_sibling", "other_half_sibling", "niece"):
            self.person(handle)
        first = self.family(None, None, "home", mother_relation=ChildRefType.ADOPTED)
        self.sibling(first, "half_sibling", mother_relation=ChildRefType.ADOPTED)
        second = self.family(None, None, "half_sibling", father_relation=ChildRefType.ADOPTED)
        self.sibling(second, "other_half_sibling", father_relation=ChildRefType.ADOPTED)
        self.family("half_sibling", None, "niece")
        self.db.set_default_person_handle("home")
        degrees, _, _ = calculate_kinship_info(self.db)
        self.assertEqual(degrees, {"home": 0, "half_sibling": 2, "niece": 3})

    def test_group_order_and_reverse(self):
        self.fixture()
        model = self.model(KinshipPersonTreeModel, scol=KINSHIP_COL)
        expected = ["home", "child", "parent", "sibling", "spouse", "stranger"]
        self.assertEqual(self.handles(model), expected)
        model.reverse_order()
        self.assertEqual(self.handles(model), list(reversed(expected)))

    def test_other_column_retains_normal_name_sort(self):
        self.fixture()
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            with self.subTest(model=cls.__name__):
                model = self.model(cls, scol=0)
                self.assertEqual(self.handles(model),
                                 ["spouse", "child", "home", "parent", "sibling", "stranger"])

    def test_hidden_kinship_skips_calculation(self):
        self.fixture()
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            for columns in (
                [(True, 0)],
                [(False, KINSHIP_COL), (True, 0)],
            ):
                with self.subTest(model=cls.__name__, columns=columns):
                    with patch("kinshipsort.calculate_kinship_info") as calculate, patch.object(
                        KinshipPersonTreeModel, "_calculate_group_degrees"
                    ) as groups:
                        model = self.model(cls, scol=0, sort_map=columns)
                        calculate.assert_not_called()
                        groups.assert_not_called()
                    self.assertEqual(model.kinship_degrees, {})
                    self.assertEqual(model.generation_levels, {})
                    self.assertEqual(model.home_handle, "home")
                    self.assertEqual(self.handles(model),
                                     ["spouse", "child", "home", "parent", "sibling", "stranger"])

    def test_visible_kinship_is_calculated_when_sorting_by_name(self):
        self.fixture()
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            with self.subTest(model=cls.__name__):
                with patch("kinshipsort.calculate_kinship_info",
                           wraps=calculate_kinship_info) as calculate, patch.object(
                    KinshipPersonTreeModel, "_calculate_group_degrees"
                ) as groups:
                    model = self.model(cls, scol=0,
                                       sort_map=[(True, 0), (True, KINSHIP_COL)])
                    calculate.assert_called_once_with(self.db)
                    groups.assert_not_called()
                self.assertEqual(model.kinship_degrees["sibling"], 2)
                self.assertEqual(model.column_kinship_degree(
                    self.db.get_person_from_handle("sibling")), "2")
                self.assertEqual(self.handles(model)[0], "spouse")

    def test_showing_kinship_uses_current_home_and_relationships(self):
        self.fixture()
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            self.model(cls, scol=0, sort_map=[(True, 0), (False, KINSHIP_COL)])
        self.family("stranger", None, "home")
        self.db.set_default_person_handle("child")
        # Changing column visibility rebuilds the model in Gramps ListView.
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            with self.subTest(model=cls.__name__):
                model = self.model(cls, scol=0,
                                   sort_map=[(True, 0), (True, KINSHIP_COL)])
                self.assertEqual(model.home_handle, "child")
                self.assertEqual(model.kinship_degrees["child"], 0)
                self.assertEqual(model.kinship_degrees["spouse"], 1)
                self.assertEqual(model.kinship_degrees["stranger"], 2)

    def test_column_map_with_kinship_moved_to_first(self):
        self.fixture()
        sort_map = [(True, KINSHIP_COL), (True, 0)]
        for cls in (KinshipPersonListModel, KinshipPersonTreeModel):
            with self.subTest(model=cls.__name__):
                model = self.model(cls, scol=0, sort_map=sort_map)
                self.assertEqual(self.handles(model)[0], "home")
                self.assertEqual(model.color_column(), TAG_COLOR_COL)

    def test_new_model_reflects_new_home_and_family_edit(self):
        self.fixture()
        self.db.set_default_person_handle("child")
        model = self.model(KinshipPersonListModel, scol=KINSHIP_COL)
        self.assertEqual(model.kinship_degrees["spouse"], 1)
        self.assertEqual(model.kinship_degrees["parent"], 2)
        self.family("stranger", None, "home")
        updated = self.model(KinshipPersonTreeModel, scol=KINSHIP_COL)
        self.assertEqual(updated.kinship_degrees["stranger"], 2)

    def test_view_column_contract_matches_gramps(self):
        self.assertEqual(len(KinshipBaseView.COLUMNS), KINSHIP_COL + 1)
        self.assertEqual(sorted(KinshipBaseView._DEFAULT_RANK), list(range(KINSHIP_COL + 1)))

    def registrations(self, gettext):
        from gramps.gen.plug import make_environment
        source = Path(__file__).resolve().parents[1]
        registrations = []
        environment = make_environment()
        environment["register"] = lambda kind, **values: registrations.append((kind, values))
        environment["_"] = gettext
        filename = source / "KinshipSort.gpr.py"
        exec(compile(filename.read_text(encoding="utf-8"), str(filename), "exec"), environment)
        return registrations

    def test_registration(self):
        from gramps.gen.plug._pluginreg import VIEW
        registrations = self.registrations(lambda message: message)
        self.assertEqual(len(registrations), 2)
        self.assertTrue(all(kind == VIEW for kind, _ in registrations))
        self.assertEqual([values["name"] for _, values in registrations],
                         ["People by kinship degree", "People by kinship, grouped"])
        for _, values in registrations:
            self.assertEqual(values["gramps_target_version"], "6.0")

    def test_polish_translation(self):
        from gramps.gen.const import GRAMPS_LOCALE
        source = Path(__file__).resolve().parents[1]
        if not (source / "locale/pl/LC_MESSAGES/addon.mo").is_file():
            self.skipTest("Compile the Polish catalog before translation validation")
        translator = GRAMPS_LOCALE.get_addon_translator(
            str(source / "kinshipsort.py"), languages=["pl"])
        registrations = self.registrations(translator.gettext)
        self.assertEqual([values["name"] for _, values in registrations],
                         ["Osoby według stopnia pokrewieństwa", "Osoby według pokrewieństwa, grupowane"])
        self.assertEqual(translator.gettext("Kinship degree"), "Stopień pokrewieństwa")


if __name__ == "__main__":
    unittest.main()
