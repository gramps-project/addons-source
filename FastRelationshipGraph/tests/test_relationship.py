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

"""Tests for FastRelationshipGraph.relationship()/all_relationships(),
against Gramps' own bundled example.gramps.

Several expectations here (handles, exact wording, depth boundary,
translated strings) are the same ones gramps-sql-extensions' own
tests/test_relationship.py validates on this same example.gramps file,
against the same upstream ground truth (gramps-web-api's
tests/test_endpoints/test_relations.py) -- reused here as ground truth
for this independent implementation, not copied from either project's
test suite itself. Since this package delegates directly to core's own
`get_one_relationship`/`get_all_relationships`/`collapse_relations()`
(see fast_relationship_graph.py's module docstring), these results are
expected to match core's literal behavior exactly, not just approximate
it the way gramps-sql-extensions' own SQL reimplementation sometimes
must.

Run with::

    python3 -m unittest FastRelationshipGraph.tests.test_relationship -v
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

from .testutil import find_example_gramps, locale_for


class RelationshipTest(unittest.TestCase):
    """Exercises relationship()/all_relationships() against
    example.gramps -- the same handles/expectations gramps-sql-
    extensions' own test suite validates for the same pairs."""

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

    def _make_graph(self, lang):
        return FastRelationshipGraph(self.db, locale=locale_for(lang))

    def test_relationship_expected_result(self):
        rel_str, dist_a, dist_b = self.graph.relationship(
            "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L"
        )
        self.assertEqual(rel_str, "second great stepgrandaunt")
        self.assertEqual((dist_a, dist_b), (5, 1))

    def test_relationship_same_person(self):
        self.assertEqual(
            self.graph.relationship("9BXKQC1PVLPYFMD6IX", "9BXKQC1PVLPYFMD6IX"),
            ("", -1, -1),
        )

    def test_relationship_unknown_handle(self):
        self.assertEqual(
            self.graph.relationship("9BXKQC1PVLPYFMD6IX", "not-a-real-handle"),
            ("", -1, -1),
        )

    def test_relationship_depth_boundary(self):
        """gramps-core's own depth cutoff excludes a generation once it
        reaches exactly `depth`, not after it -- this pair's common
        ancestor sits at generation 5, so depth=5 must NOT find it,
        depth=6 must."""
        rel_str, _, _ = self.graph.relationship(
            "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L", depth=5
        )
        self.assertEqual(rel_str, "")
        rel_str, _, _ = self.graph.relationship(
            "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L", depth=6
        )
        self.assertEqual(rel_str, "second great stepgrandaunt")

    def test_relationship_locale(self):
        graph_de = self._make_graph("de_DE.UTF-8")
        rel_str, _, _ = graph_de.relationship("9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L")
        self.assertEqual(rel_str, "Stief-/Adoptivalttante")

    def test_relationship_partner(self):
        rel_str, dist_a, dist_b = self.graph.relationship(
            "cc8205d87831c772e87", "cc8205d872f532ab14e"
        )
        self.assertEqual(rel_str, "husband")
        self.assertEqual((dist_a, dist_b), (-1, -1))

    def test_relationship_partner_locale(self):
        graph_it = self._make_graph("it_IT.UTF-8")
        rel_str, _, _ = graph_it.relationship("cc8205d87831c772e87", "cc8205d872f532ab14e")
        self.assertEqual(rel_str, "marito")

    def test_all_relationships_expected_result(self):
        result = self.graph.all_relationships("9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L")
        self.assertIn("common_ancestors", result[0])
        self.assertEqual(result[0]["relationship_string"], "second great stepgrandaunt")
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["common_ancestors"]), 2)

    def test_all_relationships_no_overreporting(self):
        """A common ancestor sitting *behind* a nearer one on both
        people's own routes to it must not be reported as if it were a
        separate, more distant relationship -- gramps-core's own search
        never visits it in the first place, so this pair has exactly
        one true relationship, not a dozen "Nth cousin" phantoms."""
        result = self.graph.all_relationships("2ZZJQC5SE4U66ZPIVW", "WBWJQCBR1TOBGJI68G")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["relationship_string"], "second cousin")
        self.assertEqual(
            set(result[0]["common_ancestors"]),
            {"9GUJQCBJMTV7R6EJU", "ENTJQCZXQV1IRKJXUL"},
        )

    def test_relationship_locale_full_vs_half(self):
        """A shared ancestor *couple* must read as a full relation, not
        a half one -- several locale calculators derive "full" vs.
        "half" wording from whether the relationship path's last hop
        reaches a whole family or just one lone parent."""
        graph_de = self._make_graph("de_DE.UTF-8")
        rel_str, _, _ = graph_de.relationship("2ZZJQC5SE4U66ZPIVW", "WBWJQCBR1TOBGJI68G")
        self.assertEqual(rel_str, "Cousin zweiten Grades")

    def test_all_relationships_same_person(self):
        self.assertEqual(
            self.graph.all_relationships("9BXKQC1PVLPYFMD6IX", "9BXKQC1PVLPYFMD6IX"), [{}]
        )

    def test_all_relationships_depth_boundary(self):
        result = self.graph.all_relationships(
            "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L", depth=5
        )
        self.assertEqual(result, [{}])
        result = self.graph.all_relationships(
            "9BXKQC1PVLPYFMD6IX", "ORFKQC4KLWEGTGR19L", depth=6
        )
        self.assertEqual(result[0]["relationship_string"], "second great stepgrandaunt")


if __name__ == "__main__":
    unittest.main()
