"""
Tests for stub_generator.py — deriving jedi completion stubs from Gramps'
own get_schema().
"""

import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stub_generator import (
    ACTIVE_VARIABLES,
    GENERATOR_ROW_TYPES,
    VOID_FUNCTIONS,
    build_registry,
    render_stub_source,
)
from completion import get_completions


class TestBuildRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry()

    def test_discovers_root_types(self):
        for name in ["Person", "Family", "Event", "Place", "Source", "Citation", "Note", "Media"]:
            self.assertIn(name, self.registry)

    def test_discovers_nested_types(self):
        # Reached only by walking into Person's primary_name / Name's date.
        for name in ["Name", "Surname", "Date"]:
            self.assertIn(name, self.registry)

    def test_sanitizes_titles_with_spaces(self):
        # Raw schema titles are "Event reference", "Child Reference", etc.
        self.assertIn("EventReference", self.registry)
        self.assertNotIn("Event reference", self.registry)

    def test_person_has_raw_schema_fields(self):
        fields = self.registry["Person"]
        self.assertEqual(fields["gramps_id"], "str")
        self.assertEqual(fields["primary_name"], "Name")

    def test_nested_list_field_is_typed(self):
        fields = self.registry["Person"]
        self.assertEqual(fields["address_list"], 'list["Address"]')

    def test_computed_properties_layered_on_matching_root_types(self):
        # `father` is valid on Person and Family (sa.father accepts both).
        for name in ["Person", "Family"]:
            self.assertEqual(self.registry[name]["father"], "Person")

    def test_computed_properties_not_layered_on_mismatched_types(self):
        # `father` shouldn't leak onto nested structural types (Name is
        # reached only by walking Person.primary_name, not a root row type),
        # nor onto root types the underlying SimpleAccess call rejects.
        self.assertNotIn("father", self.registry["Name"])
        self.assertNotIn("spouse", self.registry["Event"])
        self.assertNotIn("gender", self.registry["Family"])

    def test_reference_layered_only_on_ref_types(self):
        # `reference` reads a `ref` handle that only *Ref wrapper types
        # have -- it shouldn't appear on the root row types themselves.
        self.assertEqual(self.registry["PersonRef"]["reference"], "Person")
        self.assertEqual(self.registry["EventReference"]["reference"], "Event")
        self.assertNotIn("reference", self.registry["Person"])

    def test_computed_property_overrides_raw_field(self):
        # `gender` is both a raw int field and a DataDict2 @property;
        # the property wins at real attribute-lookup time.
        self.assertEqual(self.registry["Person"]["gender"], "str")

    def test_class_key_excluded(self):
        self.assertNotIn("_class", self.registry["Person"])


class TestRenderStubSource(unittest.TestCase):
    def test_output_is_valid_python(self):
        source = render_stub_source(build_registry())
        ast.parse(source)  # raises SyntaxError on failure

    def test_generator_functions_present(self):
        source = render_stub_source(build_registry())
        for func_name, row_type in GENERATOR_ROW_TYPES.items():
            self.assertIn("def %s() -> Iterator[%s]: ..." % (func_name, row_type), source)

    def test_empty_registry_still_valid(self):
        source = render_stub_source({}, generator_row_types={}, table_functions={})
        ast.parse(source)

    def test_table_functions_present(self):
        source = render_stub_source(build_registry())
        self.assertIn("def selected(table_name: str) -> Iterator[Union[", source)
        self.assertIn("def filtered(table_name: str) -> Iterator[Union[", source)
        self.assertIn(
            'def custom_filter(name: str, namespace: str = "Person") -> Iterator[Union[',
            source,
        )

    def test_table_function_union_covers_every_row_type(self):
        source = render_stub_source(build_registry())
        line = next(l for l in source.splitlines() if l.startswith("def selected"))
        for row_type in GENERATOR_ROW_TYPES.values():
            self.assertIn(row_type, line)

    def test_no_table_functions_when_omitted(self):
        source = render_stub_source(build_registry(), table_functions={})
        self.assertNotIn("def selected", source)

    def test_active_variables_present(self):
        source = render_stub_source(build_registry())
        for var_name, row_type in ACTIVE_VARIABLES.items():
            self.assertIn("%s: %s" % (var_name, row_type), source)

    def test_no_active_variables_when_omitted(self):
        source = render_stub_source(build_registry(), active_variables={})
        self.assertNotIn("active_person:", source)

    def test_void_functions_present(self):
        source = render_stub_source(build_registry())
        self.assertIn("def columns(*column_names) -> None: ...", source)
        self.assertIn('def begin_changes(message: str = "") -> None: ...', source)
        self.assertIn("def end_changes() -> None: ...", source)
        self.assertIn("def delete(obj) -> None: ...", source)
        self.assertIn("def row(*args) -> None: ...", source)
        self.assertIn(
            "def chart(type, data, count: int = 20, **kwargs) -> None: ...", source
        )

    def test_no_void_functions_when_omitted(self):
        source = render_stub_source(build_registry(), void_functions={})
        self.assertNotIn("def columns", source)


class TestActiveVariableCompletion(unittest.TestCase):
    """
    active_person/active_family/etc. are declared as bare static
    annotations (no value) rather than bound to a live template
    DataDict2 instance. A live template would need jedi to actually call
    DataDict2's computed @property methods (father, birth, ...) to see
    what they return -- real SimpleAccess execution that, for a blank
    template with nothing to find, only yields empty completions anyway.
    """

    def _complete(self, source):
        lines = source.splitlines()
        return get_completions(source, len(lines), len(lines[-1]), {})

    def test_completes_active_person_directly(self):
        names = self._complete("active_person.")
        self.assertIn("primary_name", names)
        self.assertIn("gramps_id", names)

    def test_completes_through_computed_property_chain(self):
        # father is a DataDict2 @property, not a raw schema field --
        # this only works because it's typed in the stub, not executed.
        names = self._complete("active_person.father.primary_name.first_")
        self.assertEqual(names, ["first_name"])

    def test_distinguishes_active_family_from_active_person(self):
        names = self._complete("active_family.")
        self.assertIn("father_handle", names)
        self.assertNotIn("primary_name", names)


class TestTableFunctionCompletion(unittest.TestCase):
    """
    selected()/filtered()/custom_filter() pick their row type from a
    runtime string argument, which jedi cannot discriminate via
    typing.overload + Literal (verified empirically -- it merges every
    overload regardless of the literal passed). These are typed as
    returning the union of every row type instead, so completion still
    offers real fields rather than nothing.
    """

    def _complete(self, source):
        lines = source.splitlines()
        return get_completions(source, len(lines), len(lines[-1]), {})

    def test_selected_offers_real_fields(self):
        names = self._complete('for person in selected("Person"):\n    person.')
        self.assertIn("primary_name", names)

    def test_filtered_offers_real_fields(self):
        names = self._complete('for fam in filtered("Family"):\n    fam.')
        self.assertIn("father_handle", names)

    def test_custom_filter_offers_real_fields_with_default_namespace(self):
        names = self._complete('for person in custom_filter("example filter"):\n    person.')
        self.assertIn("primary_name", names)

    def test_custom_filter_offers_real_fields_with_explicit_namespace(self):
        names = self._complete('for fam in custom_filter("f", "Family"):\n    fam.')
        self.assertIn("father_handle", names)


class TestVoidFunctionCompletion(unittest.TestCase):
    """
    columns()/begin_changes()/end_changes()/delete()/row()/chart() are void
    DSL functions (VOID_FUNCTIONS) -- they don't need row-type inference,
    just a signature so jedi offers them as completions at all. Before
    these were added to the stub, jedi had no way to know these names exist
    since they're bound as local closures inside execute_code(), never
    passed through the completion namespace.
    """

    def _complete(self, source):
        lines = source.splitlines()
        return get_completions(source, len(lines), len(lines[-1]), {})

    def test_completes_void_function_names(self):
        for name in VOID_FUNCTIONS:
            with self.subTest(name=name):
                names = self._complete(name[:-1])
                self.assertIn(name + "()", names)


if __name__ == "__main__":
    unittest.main()
