#
# FastRelationshipGraph -- a standalone addon, independent of gramps-core
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation; either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
#

"""Tests for relationship_path() / all_relationship_paths() -- the two
methods with no gramps-core equivalent (core only ever returns wording,
never the chain of people). Ground truth here is relationship()'s own
wording (already validated against core in test_relationship.py) for
each path's endpoint-to-endpoint relationship, plus structural checks on
the chain itself (starts at h1, ends at h2, passes through a real common
ancestor).

Run with::

    python3 -m unittest FastRelationshipGraph.tests.test_paths -v
"""

import unittest

try:
    import gi  # noqa: F401
    import gramps
except ImportError as exc:
    raise unittest.SkipTest("FastRelationshipGraph tests require 'gi' and 'gramps': %s" % exc)

from gramps.gen.db.utils import import_as_dict
from gramps.gen.user import User

from fast_relationship_graph import FastRelationshipGraph

from .testutil import find_example_gramps


class RelationshipPathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        example = find_example_gramps()
        if example is None:
            raise unittest.SkipTest("example.gramps not found")
        cls.db = import_as_dict(example, User())
        cls.graph = FastRelationshipGraph(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_relationship_path_same_person(self):
        handle = "9BXKQC1PVLPYFMD6IX"
        self.assertEqual(
            self.graph.relationship_path(handle, handle),
            [{"handle": handle, "relationship_string": ""}],
        )

    def test_relationship_path_unknown_handle(self):
        self.assertEqual(
            self.graph.relationship_path("9BXKQC1PVLPYFMD6IX", "not-a-real-handle"), []
        )

    def test_relationship_path_spouse(self):
        h1, h2 = "cc8205d87831c772e87", "cc8205d872f532ab14e"
        path = self.graph.relationship_path(h1, h2)
        self.assertEqual([node["handle"] for node in path], [h1, h2])
        self.assertEqual(path[0]["relationship_string"], "")
        self.assertEqual(path[1]["relationship_string"], "husband")

    def test_relationship_path_endpoints_and_ordering(self):
        """The chain must start at h1 (empty relationship_string, since
        it's always relative to h1) and end at h2, whose
        relationship_string must equal what relationship() itself
        reports for this pair."""
        h1, h2 = "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L"
        path = self.graph.relationship_path(h1, h2)
        self.assertEqual(path[0], {"handle": h1, "relationship_string": ""})
        self.assertEqual(path[-1]["handle"], h2)
        rel_str, _, _ = self.graph.relationship(h1, h2)
        self.assertEqual(path[-1]["relationship_string"], rel_str)

    def test_relationship_path_depth_boundary(self):
        h1, h2 = "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L"
        self.assertEqual(self.graph.relationship_path(h1, h2, depth=5), [])
        path = self.graph.relationship_path(h1, h2, depth=6)
        self.assertEqual(path[-1]["handle"], h2)

    def test_all_relationship_paths_first_matches_relationship_path(self):
        """`all_relationship_paths(h1, h2)[0]` always equals
        `relationship_path(h1, h2)` -- documented contract."""
        h1, h2 = "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L"
        self.assertEqual(
            self.graph.all_relationship_paths(h1, h2)[0], self.graph.relationship_path(h1, h2)
        )

    def test_all_relationship_paths_same_person(self):
        handle = "9BXKQC1PVLPYFMD6IX"
        self.assertEqual(
            self.graph.all_relationship_paths(handle, handle),
            [[{"handle": handle, "relationship_string": ""}]],
        )

    def test_all_relationship_paths_max_paths_caps_results(self):
        h1, h2 = "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L"
        full = self.graph.all_relationship_paths(h1, h2)
        capped = self.graph.all_relationship_paths(h1, h2, max_paths=1)
        self.assertEqual(len(capped), min(1, len(full)))
        if full:
            self.assertEqual(capped[0], full[0])

    def test_all_relationship_paths_two_separate_paths_for_ancestor_couple(self):
        """A pair sharing a common ancestor *couple* (both parents of
        the shared family are common ancestors) has two genuinely
        distinct routes up the tree -- one via each parent -- even
        though relationship()/all_relationships() correctly collapse
        them into one wording via core's own collapse_relations().
        all_relationship_paths() must NOT collapse them: it returns two
        distinct routes, each a valid chain from h1 to h2, differing in
        which ancestor they climb through."""
        h1, h2 = "2ZZJQC5SE4U66ZPIVW", "WBWJQCBR1TOBGJI68G"
        paths = self.graph.all_relationship_paths(h1, h2)
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertEqual(path[0], {"handle": h1, "relationship_string": ""})
            self.assertEqual(path[-1]["handle"], h2)
        handle_sets = [tuple(node["handle"] for node in path) for path in paths]
        self.assertNotEqual(handle_sets[0], handle_sets[1])


if __name__ == "__main__":
    unittest.main()
