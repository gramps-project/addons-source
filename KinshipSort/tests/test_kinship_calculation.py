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

"""Regression tests for biological kinship; no Gramps or GTK required."""

# ------------------------------------------------------------------------
# Standard Python modules
# ------------------------------------------------------------------------
from collections import defaultdict, deque
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kinship_calculation import calculate_kinship_from_relations


def maps(edges):
    parents, children = defaultdict(set), defaultdict(set)
    for parent, child in edges:
        parents[child].add(parent)
        children[parent].add(child)
    return parents, children


def reference(home, parents, children):
    """Slow oracle: independent BFS from each common ancestor candidate."""
    def distances(start, graph):
        found = {start: 0}
        pending = deque([start])
        while pending:
            current = pending.popleft()
            for target in graph.get(current, ()):
                if target not in found:
                    found[target] = found[current] + 1
                    pending.append(target)
        return found

    candidates = defaultdict(list)
    for ancestor, up in distances(home, parents).items():
        for person, down in distances(ancestor, children).items():
            candidates[person].append((up + down, down - up))
    best = {person: min(paths) for person, paths in candidates.items()}
    return ({p: v[0] for p, v in best.items()},
            {p: -v[1] for p, v in best.items()})


class KinshipCalculationTests(unittest.TestCase):
    def calculate(self, edges, home="home"):
        return calculate_kinship_from_relations(home, *maps(edges))

    def test_home_only(self):
        self.assertEqual(self.calculate([]), ({"home": 0}, {"home": 0}))

    def test_anonymous_parents_need_no_orderable_handles(self):
        father, mother = object(), object()
        edges = [(father, "home"), (mother, "home"),
                 (father, "sibling"), (mother, "sibling"),
                 ("sibling", "niece")]
        result = self.calculate(edges)
        self.assertEqual(result, reference("home", *maps(edges)))
        self.assertEqual(result[0]["sibling"], 2)
        self.assertEqual(result[0]["niece"], 3)

    def test_direct_ancestors_and_descendants(self):
        degrees, generations = self.calculate([
            ("grandparent", "parent"), ("parent", "home"),
            ("home", "child"), ("child", "grandchild")])
        self.assertEqual(degrees, {"home": 0, "parent": 1, "grandparent": 2,
                                   "child": 1, "grandchild": 2})
        self.assertEqual(generations, {"home": 0, "parent": 1, "grandparent": 2,
                                       "child": -1, "grandchild": -2})

    def test_collateral_relatives(self):
        degrees, generations = self.calculate([
            ("grandparent", "parent"), ("parent", "home"),
            ("parent", "sibling"), ("sibling", "niece"),
            ("grandparent", "aunt"), ("aunt", "cousin")])
        self.assertEqual({p: degrees[p] for p in ("sibling", "niece", "aunt", "cousin")},
                         {"sibling": 2, "niece": 3, "aunt": 3, "cousin": 4})
        self.assertEqual({p: generations[p] for p in ("sibling", "niece", "aunt", "cousin")},
                         {"sibling": 0, "niece": -1, "aunt": 1, "cousin": 0})

    def test_half_sibling(self):
        degrees, _ = self.calculate([("parent", "home"), ("parent", "half")])
        self.assertEqual(degrees["half"], 2)

    def test_shared_child_does_not_make_spouse_a_relative(self):
        degrees, _ = self.calculate([
            ("home", "child"), ("spouse", "child"),
            ("inlaw", "spouse"), ("spouse", "stepchild")])
        self.assertEqual(degrees, {"home": 0, "child": 1})

    def test_related_spouse_uses_common_ancestor(self):
        degrees, _ = self.calculate([
            ("gp", "p1"), ("gp", "p2"), ("p1", "home"),
            ("p2", "spouse"), ("home", "child"), ("spouse", "child")])
        self.assertEqual(degrees["spouse"], 4)
        self.assertEqual(degrees["child"], 1)

    def test_shortest_of_multiple_common_ancestor_paths(self):
        degrees, _ = self.calculate([
            ("gp", "p1"), ("gp", "p2"), ("p1", "home"),
            ("p2", "relative"), ("other", "home"), ("other", "relative")])
        self.assertEqual(degrees["relative"], 2)

    def test_equal_degree_prefers_highest_generation(self):
        degrees, generations = self.calculate([
            ("gp", "parent"), ("parent", "home"), ("gp", "relative"),
            ("home", "child"), ("child", "grandchild"),
            ("grandchild", "relative")])
        self.assertEqual((degrees["relative"], generations["relative"]), (3, 1))

    def test_preferred_generation_propagates_to_descendants(self):
        edges = [("gp", "parent"), ("parent", "home"), ("gp", "relative"),
                 ("home", "child"), ("child", "gc"), ("gc", "relative"),
                 ("relative", "next")]
        degrees, generations = self.calculate(edges)
        self.assertEqual((degrees["next"], generations["next"]), (4, 0))

    def test_disconnected_component_excluded(self):
        self.assertEqual(self.calculate([("stranger", "other")]),
                         ({"home": 0}, {"home": 0}))

    def test_malformed_cycles_terminate(self):
        edges = [("home", "a"), ("a", "b"), ("b", "home"), ("a", "a")]
        self.assertEqual(self.calculate(edges), reference("home", *maps(edges)))

    def test_large_generation_depth_is_iterative(self):
        edges = [(str(i), str(i + 1)) for i in range(5000)]
        degrees, generations = self.calculate(edges, home="2500")
        self.assertEqual((degrees["0"], generations["0"]), (2500, 2500))
        self.assertEqual((degrees["5000"], generations["5000"]), (2500, -2500))

    def test_input_maps_are_unchanged(self):
        parents, children = maps([("parent", "home"), ("home", "child")])
        before = (dict(parents), dict(children))
        calculate_kinship_from_relations("home", parents, children)
        self.assertEqual((dict(parents), dict(children)), before)

    def test_random_pedigrees_against_independent_reference(self):
        for seed in range(250):
            rng = random.Random(seed)
            people = [f"p{i}" for i in range(22)]
            edges = [(people[i], people[j]) for i in range(22)
                     for j in range(i + 1, 22) if rng.random() < 0.09]
            parents, children = maps(edges)
            for home in rng.sample(people, 4):
                with self.subTest(seed=seed, home=home):
                    self.assertEqual(calculate_kinship_from_relations(home, parents, children),
                                     reference(home, parents, children))

    def test_random_cyclic_data_against_reference(self):
        for seed in range(50):
            rng = random.Random(seed)
            edges = [(str(i), str(j)) for i in range(12) for j in range(12)
                     if rng.random() < 0.08]
            with self.subTest(seed=seed):
                self.assertEqual(self.calculate(edges, home="0"),
                                 reference("0", *maps(edges)))


if __name__ == "__main__":
    unittest.main()
