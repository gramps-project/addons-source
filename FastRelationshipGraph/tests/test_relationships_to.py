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

"""Tests for relationships_to() -- the bulk method with no gramps-core
equivalent at all. Exercises both of its two strategies
(`_relationships_to_small` below `bulk_threshold`, `_relationships_to_bulk`
at or above it) and checks they agree with each other and with
relationship() on the same pairs, plus paging.

Run with::

    python3 -m unittest FastRelationshipGraph.tests.test_relationships_to -v
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


class RelationshipsToTest(unittest.TestCase):
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

    def test_relationships_to_matches_relationship(self):
        h1 = "9BXKQC1PVLPYFMD6IX"
        h2 = "ORFKQC4KLWEGTGR19L"
        result = self.graph.relationships_to(h1, handles=[h2])
        self.assertEqual(result["total"], 1)
        rel_str, _, _ = self.graph.relationship(h1, h2)
        self.assertEqual(result["items"], [{"handle": h2, "relationship_string": rel_str}])

    def test_relationships_to_small_and_bulk_strategies_agree(self):
        """Force the bulk (full-tree-index) strategy via
        bulk_threshold=0 and check it produces the exact same result as
        the default per-target strategy for the same targets."""
        h1 = "9BXKQC1PVLPYFMD6IX"
        targets = ["ORFKQC4KLWEGTGR19L", "cc8205d872f532ab14e", "2ZZJQC5SE4U66ZPIVW"]
        small = self.graph.relationships_to(h1, handles=targets, bulk_threshold=1000)
        bulk = self.graph.relationships_to(h1, handles=targets, bulk_threshold=0)
        self.assertEqual(small["items"], bulk["items"])

    def test_relationships_to_skips_unknown_handles(self):
        h1 = "9BXKQC1PVLPYFMD6IX"
        result = self.graph.relationships_to(h1, handles=["not-a-real-handle"])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)

    def test_relationships_to_excludes_self(self):
        h1 = "9BXKQC1PVLPYFMD6IX"
        result = self.graph.relationships_to(h1, handles=[h1])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["total"], 0)

    def test_relationships_to_paging(self):
        h1 = "9BXKQC1PVLPYFMD6IX"
        unpaged = self.graph.relationships_to(h1, pagesize=1000000)
        total = unpaged["total"]
        self.assertGreater(total, 3)

        page1 = self.graph.relationships_to(h1, page=1, pagesize=2)
        page2 = self.graph.relationships_to(h1, page=2, pagesize=2)
        self.assertEqual(page1["total"], total)
        self.assertEqual(page2["total"], total)
        self.assertEqual(len(page1["items"]), 2)
        self.assertEqual(len(page2["items"]), 2)
        self.assertTrue(
            {i["handle"] for i in page1["items"]}.isdisjoint(
                {i["handle"] for i in page2["items"]}
            )
        )
        self.assertEqual(page1["items"] + page2["items"], unpaged["items"][:4])


if __name__ == "__main__":
    unittest.main()
