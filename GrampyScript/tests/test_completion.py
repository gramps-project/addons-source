"""
Tests for completion.py — jedi-based command completion.

Uses real Gramps gen-lib objects (no GTK required).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gramps.gen.lib import Person, Name, Surname
from gramps.gen.simple import SimpleAccess

from datadict2 import DataDict2, set_sa
from completion import get_completions, get_completion_items


def _make_person(gramps_id="I0001", first="John", surname="Smith"):
    p = Person()
    p.set_gramps_id(gramps_id)
    n = Name()
    sn = Surname()
    sn.set_surname(surname)
    n.add_surname(sn)
    n.set_first_name(first)
    p.set_primary_name(n)
    return p


class _MockSaBase(unittest.TestCase):
    """Base class that sets up a minimal SimpleAccess mock before each test."""

    def setUp(self):
        db = MagicMock()
        sa = SimpleAccess(db)
        set_sa(sa)

    def _complete(self, source, namespace):
        line = source.count("\n") + 1
        column = len(source) - (source.rfind("\n") + 1)
        return get_completions(source, line, column, namespace)


class TestBareWordCompletion(_MockSaBase):
    def test_completes_python_builtins(self):
        names = self._complete("pri", {})
        self.assertIn("print", names)

    def test_completes_namespace_variable(self):
        names = self._complete("active_per", {"active_person": DataDict2(_make_person())})
        self.assertIn("active_person", names)


class TestAttributeCompletion(_MockSaBase):
    def setUp(self):
        super().setUp()
        self.namespace = {"active_person": DataDict2(_make_person())}

    def test_completes_dynamic_dict_keys(self):
        names = self._complete("active_person.", self.namespace)
        self.assertIn("primary_name", names)
        self.assertIn("gramps_id", names)

    def test_completes_class_properties(self):
        names = self._complete("active_person.", self.namespace)
        self.assertIn("father", names)
        self.assertIn("age", names)

    def test_completes_nested_attribute_chain(self):
        names = self._complete("active_person.primary_name.", self.namespace)
        self.assertIn("first_name", names)
        self.assertIn("surname_list", names)

    def test_prefix_narrows_nested_match(self):
        names = self._complete("active_person.primary_name.first_", self.namespace)
        self.assertEqual(names, ["first_name"])

    def test_no_false_match_for_unrelated_prefix(self):
        names = self._complete("active_person.primary_name.zzz", self.namespace)
        self.assertEqual(names, [])


class TestGeneratorRowTypeInference(_MockSaBase):
    """
    Completion on a user's own loop variable, e.g.
    `for person in people(): person.primary_name.first_name` -- `person` is
    a name the user chose, not something we bind into the namespace, so it
    can only be resolved via the stub_generator preamble's static
    annotation on `people()`, not runtime introspection.
    """

    def test_completes_loop_variable_over_people(self):
        names = self._complete("for person in people():\n    person.", {})
        self.assertIn("primary_name", names)
        self.assertIn("gramps_id", names)

    def test_completes_nested_attribute_on_loop_variable(self):
        names = self._complete(
            "for person in people():\n    person.primary_name.first_", {}
        )
        self.assertEqual(names, ["first_name"])

    def test_distinguishes_row_type_by_generator(self):
        # families() yields Family, not Person -- fields must not bleed
        # across generators.
        names = self._complete("for fam in families():\n    fam.", {})
        self.assertIn("father_handle", names)
        self.assertNotIn("primary_name", names)


class TestCompletionItems(_MockSaBase):
    """get_completion_items() is get_completions() plus the jedi
    `.complete` suffix, used by the editor to insert just the missing
    characters rather than re-typing the whole name."""

    def test_complete_is_only_the_missing_suffix(self):
        namespace = {"active_person": DataDict2(_make_person())}
        items = get_completion_items("active_person.primary_", 1, len("active_person.primary_"), namespace)
        self.assertEqual(
            items, [{"name": "primary_name", "complete": "name", "cursor_offset": 0}]
        )

    def test_complete_is_full_name_when_nothing_typed_yet(self):
        namespace = {"active_person": DataDict2(_make_person())}
        items = get_completion_items("active_person.", 1, len("active_person."), namespace)
        matching = [i for i in items if i["name"] == "primary_name"]
        self.assertEqual(
            matching, [{"name": "primary_name", "complete": "primary_name", "cursor_offset": 0}]
        )

    def test_no_arg_function_gets_parens_appended(self):
        # people() takes no arguments -- cursor lands after "()".
        items = get_completion_items("peop", 1, len("peop"), {})
        matching = [i for i in items if i["name"] == "people()"]
        self.assertEqual(
            matching, [{"name": "people()", "complete": "le()", "cursor_offset": 0}]
        )

    def test_function_with_args_lands_cursor_between_parens(self):
        items = get_completion_items("custom_fil", 1, len("custom_fil"), {})
        matching = [i for i in items if i["name"] == "custom_filter()"]
        self.assertEqual(
            matching, [{"name": "custom_filter()", "complete": "ter()", "cursor_offset": 1}]
        )

    def test_non_function_completion_has_no_parens(self):
        namespace = {"active_person": DataDict2(_make_person())}
        items = get_completion_items("active_person.gramps_", 1, len("active_person.gramps_"), namespace)
        matching = [i for i in items if i["name"] == "gramps_id"]
        self.assertEqual(
            matching, [{"name": "gramps_id", "complete": "id", "cursor_offset": 0}]
        )


class TestRobustness(_MockSaBase):
    def test_empty_source_does_not_raise(self):
        # Completing on an empty buffer legitimately lists every builtin
        # in scope; the point of this test is only that it doesn't raise.
        names = self._complete("", {})
        self.assertIn("print", names)

    def test_incomplete_code_does_not_raise(self):
        # Mid-typing code is often syntactically invalid; must not crash.
        names = self._complete("for person in people(", {})
        self.assertIsInstance(names, list)


if __name__ == "__main__":
    unittest.main()
