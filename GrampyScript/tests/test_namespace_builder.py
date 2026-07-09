"""
Tests for namespace_builder.py — the runtime completion namespace.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gramps.gen.lib import Date

from namespace_builder import build_namespace


class TestBuildNamespace(unittest.TestCase):
    def test_without_database(self):
        namespace = build_namespace()
        self.assertIn("today", namespace)
        self.assertIn("counter", namespace)
        self.assertNotIn("database", namespace)

    def test_today_is_a_real_date(self):
        namespace = build_namespace()
        self.assertIsInstance(namespace["today"], Date)

    def test_counter_returns_defaultdict(self):
        namespace = build_namespace()
        counter = namespace["counter"]()
        self.assertEqual(counter["anything"], 0)

    def test_database_included_when_given(self):
        sentinel = object()
        namespace = build_namespace(sentinel)
        self.assertIs(namespace["database"], sentinel)

    def test_active_names_are_not_included(self):
        # active_person etc. are handled as static stub annotations
        # (stub_generator.ACTIVE_VARIABLES), not live namespace objects.
        namespace = build_namespace()
        self.assertNotIn("active_person", namespace)
        self.assertNotIn("active_family", namespace)


if __name__ == "__main__":
    unittest.main()
