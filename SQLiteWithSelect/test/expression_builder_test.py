#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Doug Blank
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Tests for expression-to-SQL conversion using QueryBuilder.

ExpressionBuilder was merged into QueryBuilder + SQLGenerator. This test
verifies expression conversion via the generate_expression() API.
"""
import unittest

from gramps.gen.lib import Person, EventRoleType, FamilyRelType
from query_builder import QueryBuilder


class ExpressionBuilderCompat:
    """
    Thin wrapper around QueryBuilder that replicates the old ExpressionBuilder API:
      convert_where_clause(where_str) -> SQL string
      convert(expr_str)               -> SQL string
      get_order_by(order_by_list)     -> " ORDER BY ..." string
    """

    def __init__(self, table, dialect, env=None):
        self._builder = QueryBuilder(
            table, dialect=dialect, env=env or {}, enable_type_validation=False
        )
        self._builder.generator.base_table = table

    def convert_where_clause(self, where_str):
        expr = self._builder.parser.parse_expression(where_str)
        return self._builder.generator.generate_expression(expr)

    def convert(self, expr_str):
        expr = self._builder.parser.parse_expression(expr_str)
        return self._builder.generator.generate_expression(expr)

    def get_order_by(self, order_by_list, has_joins=False):
        orders = self._builder._parse_order_by(order_by_list)
        if not orders:
            return ""
        parts = []
        for o in orders:
            sql = self._builder.generator.generate_expression(o.expression)
            suffix = " DESC" if o.direction == "DESC" else ""
            parts.append(f"{sql}{suffix}")
        return " ORDER BY " + ", ".join(parts)


class ExpressionBuilderTestMixin:
    """
    Common test runner for ExpressionBuilderCompat.
    Subclasses set self.dialect and self.expression_builder in setUp.
    """

    def setUp(self):
        self.env = {
            "Person": Person,
            "EventRoleType": EventRoleType,
            "FamilyRelType": FamilyRelType,
        }
        self.expression_builder = ExpressionBuilderCompat(
            "person", dialect=self.dialect, env=self.env
        )

    def _run_test_case(self, test_name, input_dict, expected):
        if test_name == "join_with_variable_index_array_access_and_condition":
            from gramps.gen.lib import EventType

            env = {**self.env, "EventType": EventType}
            eb = ExpressionBuilderCompat("person", dialect=self.dialect, env=env)
        else:
            eb = self.expression_builder

        if "where" in input_dict:
            sql = eb.convert_where_clause(input_dict["where"])
        elif "convert" in input_dict:
            sql = eb.convert(input_dict["convert"])
        elif "order_by" in input_dict:
            sql = eb.get_order_by(input_dict["order_by"], has_joins=False)
        else:
            raise ValueError(f"Unknown input type in test case {test_name}")

        self.assertEqual(sql, expected)


class ExpressionBuilderSQLiteTest(ExpressionBuilderTestMixin, unittest.TestCase):
    """Tests for SQLite dialect."""

    expected_values = {
        "order_by_1": (
            {
                "order_by": [
                    "-person.primary_name.surname_list[0].surname",
                    "person.gender",
                ]
            },
            " ORDER BY json_extract(person.json_data, '$.primary_name.surname_list[0].surname') DESC, json_extract(person.json_data, '$.gender')",
        ),
        "order_by_2": (
            {
                "order_by": [
                    "person.primary_name.surname_list[0].surname",
                    "-person.gender",
                ]
            },
            " ORDER BY json_extract(person.json_data, '$.primary_name.surname_list[0].surname'), json_extract(person.json_data, '$.gender') DESC",
        ),
        "HavePhotos": (
            {"where": "len(person.media_list) > 0"},
            "(json_array_length(json_extract(person.json_data, '$.media_list')) > 0)",
        ),
        "disconnected": (
            {
                "where": "len(person.family_list) == 0 and len(person.parent_family_list) == 0"
            },
            "(((json_array_length(json_extract(person.json_data, '$.family_list')) = 0)) AND ((json_array_length(json_extract(person.json_data, '$.parent_family_list')) = 0)))",
        ),
        "hasunknowngender": (
            {"where": "person.gender == Person.UNKNOWN"},
            "(json_extract(person.json_data, '$.gender') = 2)",
        ),
        "isfemale": (
            {"where": "person.gender == Person.FEMALE"},
            "(json_extract(person.json_data, '$.gender') = 0)",
        ),
        "ismale": (
            {"where": "person.gender == Person.MALE"},
            "(json_extract(person.json_data, '$.gender') = 1)",
        ),
        "hasidof_matching": (
            {"where": "person.gramps_id == 'I0044'"},
            "(json_extract(person.json_data, '$.gramps_id') = 'I0044')",
        ),
        "hasidof_startswith": (
            {"where": "person.gramps_id.startswith('I00')"},
            "LIKE('I00%', json_extract(person.json_data, '$.gramps_id'))",
        ),
        "multiplemarriages": (
            {"where": "len(person.family_list) > 1"},
            "(json_array_length(json_extract(person.json_data, '$.family_list')) > 1)",
        ),
        "nevermarried": (
            {"where": "len(person.family_list) == 0"},
            "(json_array_length(json_extract(person.json_data, '$.family_list')) = 0)",
        ),
        "peopleprivate": (
            {"where": "person.private"},
            "CAST(json_extract(person.json_data, '$.private') AS INTEGER)",
        ),
        "peoplepublic": (
            {"where": "not person.private"},
            "(CAST(json_extract(person.json_data, '$.private') AS INTEGER) IS NULL OR CAST(CAST(json_extract(person.json_data, '$.private') AS INTEGER) AS INTEGER) = 0)",
        ),
        "string_endswith": (
            {"where": "person.gramps_id.endswith('44')"},
            "LIKE('%44', json_extract(person.json_data, '$.gramps_id'))",
        ),
        "string_in_pattern": (
            {"where": "'I00' in person.gramps_id"},
            "json_extract(person.json_data, '$.gramps_id') LIKE '%I00%'",
        ),
        "join_person_family_basic": (
            {"where": "person.handle == family.father_handle"},
            "(json_extract(person.json_data, '$.handle') = json_extract(family.json_data, '$.father_handle'))",
        ),
        "join_person_family_with_condition": (
            {
                "where": "person.handle == family.father_handle and family.type.value == FamilyRelType.MARRIED"
            },
            "(((json_extract(person.json_data, '$.handle') = json_extract(family.json_data, '$.father_handle'))) AND ((json_extract(family.json_data, '$.type.value') = 0)))",
        ),
        "convert_expression_basic": (
            {"convert": "person.primary_name.surname_list[0].surname"},
            "json_extract(person.json_data, '$.primary_name.surname_list[0].surname')",
        ),
        "convert_expression_gender": (
            {"convert": "person.gender"},
            "json_extract(person.json_data, '$.gender')",
        ),
        "convert_expression_handle": (
            {"convert": "person.handle"},
            "json_extract(person.json_data, '$.handle')",
        ),
        "simple_and_expression": (
            {"where": "person.gender == Person.MALE and len(person.family_list) > 0"},
            "(((json_extract(person.json_data, '$.gender') = 1)) AND ((json_array_length(json_extract(person.json_data, '$.family_list')) > 0)))",
        ),
        "simple_or_expression": (
            {"where": "person.gender == Person.MALE or len(person.family_list) == 0"},
            "(((json_extract(person.json_data, '$.gender') = 1)) OR ((json_array_length(json_extract(person.json_data, '$.family_list')) = 0)))",
        ),
        "join_with_variable_index_array_access": (
            {
                "where": "person.event_ref_list[person.birth_ref_index].ref == event.handle"
            },
            "(json_extract((SELECT json_each.value FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$') WHERE CAST(json_each.key AS INTEGER) = CAST(CAST(json_extract(person.json_data, '$.birth_ref_index') AS REAL) AS INTEGER) LIMIT 1), '$.ref') = json_extract(event.json_data, '$.handle'))",
        ),
        "join_with_variable_index_array_access_and_condition": (
            {
                "where": "person.event_ref_list[person.birth_ref_index].ref == event.handle and event.type.value == EventType.BIRTH"
            },
            "(((json_extract((SELECT json_each.value FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$') WHERE CAST(json_each.key AS INTEGER) = CAST(CAST(json_extract(person.json_data, '$.birth_ref_index') AS REAL) AS INTEGER) LIMIT 1), '$.ref') = json_extract(event.json_data, '$.handle'))) AND ((json_extract(event.json_data, '$.type.value') = 12)))",
        ),
        "any_list_comprehension_in_where_basic": (
            {"where": "any([eref for eref in person.event_ref_list])"},
            "EXISTS (SELECT 1 FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$'))",
        ),
        "variable_index_array_access_in_what": (
            {"convert": "person.event_ref_list[person.birth_ref_index]"},
            "(SELECT json_each.value FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$') WHERE CAST(json_each.key AS INTEGER) = CAST(CAST(json_extract(person.json_data, '$.birth_ref_index') AS REAL) AS INTEGER) LIMIT 1)",
        ),
        "variable_index_array_access_with_attributes": (
            {"convert": "person.event_ref_list[person.birth_ref_index].role.value"},
            "json_extract((SELECT json_each.value FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$') WHERE CAST(json_each.key AS INTEGER) = CAST(CAST(json_extract(person.json_data, '$.birth_ref_index') AS REAL) AS INTEGER) LIMIT 1), '$.role.value')",
        ),
        "variable_index_array_access_in_where": (
            {"where": "person.event_ref_list[person.birth_ref_index]"},
            "(SELECT json_each.value FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$') WHERE CAST(json_each.key AS INTEGER) = CAST(CAST(json_extract(person.json_data, '$.birth_ref_index') AS REAL) AS INTEGER) LIMIT 1)",
        ),
        "variable_index_array_access_with_attributes_in_where": (
            {"where": "person.event_ref_list[person.birth_ref_index].role.value == 5"},
            "(json_extract((SELECT json_each.value FROM json_each(json_extract(person.json_data, '$.event_ref_list'), '$') WHERE CAST(json_each.key AS INTEGER) = CAST(CAST(json_extract(person.json_data, '$.birth_ref_index') AS REAL) AS INTEGER) LIMIT 1), '$.role.value') = 5)",
        ),
    }

    def setUp(self):
        self.dialect = "sqlite"
        super().setUp()


class ExpressionBuilderPostgreSQLTest(ExpressionBuilderTestMixin, unittest.TestCase):
    """Tests for PostgreSQL dialect."""

    expected_values = {
        "order_by_1": (
            {
                "order_by": [
                    "-person.primary_name.surname_list[0].surname",
                    "person.gender",
                ]
            },
            " ORDER BY JSON_EXTRACT_PATH(person.json_data, 'primary_name.surname_list[0].surname') DESC, JSON_EXTRACT_PATH(person.json_data, 'gender')",
        ),
        "order_by_2": (
            {
                "order_by": [
                    "person.primary_name.surname_list[0].surname",
                    "-person.gender",
                ]
            },
            " ORDER BY JSON_EXTRACT_PATH(person.json_data, 'primary_name.surname_list[0].surname'), JSON_EXTRACT_PATH(person.json_data, 'gender') DESC",
        ),
        "HavePhotos": (
            {"where": "len(person.media_list) > 0"},
            "(JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'media_list')) > 0)",
        ),
        "disconnected": (
            {
                "where": "len(person.family_list) == 0 and len(person.parent_family_list) == 0"
            },
            "(((JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'family_list')) = 0)) AND ((JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'parent_family_list')) = 0)))",
        ),
        "hasunknowngender": (
            {"where": "person.gender == Person.UNKNOWN"},
            "(JSON_EXTRACT_PATH(person.json_data, 'gender') = 2)",
        ),
        "isfemale": (
            {"where": "person.gender == Person.FEMALE"},
            "(JSON_EXTRACT_PATH(person.json_data, 'gender') = 0)",
        ),
        "ismale": (
            {"where": "person.gender == Person.MALE"},
            "(JSON_EXTRACT_PATH(person.json_data, 'gender') = 1)",
        ),
        "hasidof_matching": (
            {"where": "person.gramps_id == 'I0044'"},
            "(JSON_EXTRACT_PATH(person.json_data, 'gramps_id') = 'I0044')",
        ),
        "hasidof_startswith": (
            {"where": "person.gramps_id.startswith('I00')"},
            "LIKE('I00%', JSON_EXTRACT_PATH(person.json_data, 'gramps_id'))",
        ),
        "multiplemarriages": (
            {"where": "len(person.family_list) > 1"},
            "(JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'family_list')) > 1)",
        ),
        "nevermarried": (
            {"where": "len(person.family_list) == 0"},
            "(JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'family_list')) = 0)",
        ),
        "peopleprivate": (
            {"where": "person.private"},
            "CAST(JSON_EXTRACT_PATH(person.json_data, 'private') AS BOOLEAN)",
        ),
        "peoplepublic": (
            {"where": "not person.private"},
            "(CAST(JSON_EXTRACT_PATH(person.json_data, 'private') AS BOOLEAN) IS NULL OR CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'private') AS BOOLEAN) AS BOOLEAN) = false)",
        ),
        "string_endswith": (
            {"where": "person.gramps_id.endswith('44')"},
            "LIKE('%44', JSON_EXTRACT_PATH(person.json_data, 'gramps_id'))",
        ),
        "string_in_pattern": (
            {"where": "'I00' in person.gramps_id"},
            "JSON_EXTRACT_PATH(person.json_data, 'gramps_id') ILIKE '%I00%'",
        ),
        "join_person_family_basic": (
            {"where": "person.handle == family.father_handle"},
            "(JSON_EXTRACT_PATH(person.json_data, 'handle') = JSON_EXTRACT_PATH(family.json_data, 'father_handle'))",
        ),
        "join_person_family_with_condition": (
            {
                "where": "person.handle == family.father_handle and family.type.value == FamilyRelType.MARRIED"
            },
            "(((JSON_EXTRACT_PATH(person.json_data, 'handle') = JSON_EXTRACT_PATH(family.json_data, 'father_handle'))) AND ((JSON_EXTRACT_PATH(family.json_data, 'type.value') = 0)))",
        ),
        "convert_expression_basic": (
            {"convert": "person.primary_name.surname_list[0].surname"},
            "JSON_EXTRACT_PATH(person.json_data, 'primary_name.surname_list[0].surname')",
        ),
        "convert_expression_gender": (
            {"convert": "person.gender"},
            "JSON_EXTRACT_PATH(person.json_data, 'gender')",
        ),
        "convert_expression_handle": (
            {"convert": "person.handle"},
            "JSON_EXTRACT_PATH(person.json_data, 'handle')",
        ),
        "simple_and_expression": (
            {"where": "person.gender == Person.MALE and len(person.family_list) > 0"},
            "(((JSON_EXTRACT_PATH(person.json_data, 'gender') = 1)) AND ((JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'family_list')) > 0)))",
        ),
        "simple_or_expression": (
            {"where": "person.gender == Person.MALE or len(person.family_list) == 0"},
            "(((JSON_EXTRACT_PATH(person.json_data, 'gender') = 1)) OR ((JSON_ARRAY_LENGTH(JSON_EXTRACT_PATH(person.json_data, 'family_list')) = 0)))",
        ),
        "join_with_variable_index_array_access": (
            {
                "where": "person.event_ref_list[person.birth_ref_index].ref == event.handle"
            },
            "(JSON_EXTRACT_PATH((SELECT json_each.value FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) WITH ORDINALITY AS json_each(value, ordinality) WHERE json_each.ordinality - 1 = CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'birth_ref_index') AS NUMERIC) AS INTEGER) LIMIT 1), 'ref') = JSON_EXTRACT_PATH(event.json_data, 'handle'))",
        ),
        "join_with_variable_index_array_access_and_condition": (
            {
                "where": "person.event_ref_list[person.birth_ref_index].ref == event.handle and event.type.value == EventType.BIRTH"
            },
            "(((JSON_EXTRACT_PATH((SELECT json_each.value FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) WITH ORDINALITY AS json_each(value, ordinality) WHERE json_each.ordinality - 1 = CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'birth_ref_index') AS NUMERIC) AS INTEGER) LIMIT 1), 'ref') = JSON_EXTRACT_PATH(event.json_data, 'handle'))) AND ((JSON_EXTRACT_PATH(event.json_data, 'type.value') = 12)))",
        ),
        "any_list_comprehension_in_where_basic": (
            {"where": "any([eref for eref in person.event_ref_list])"},
            "EXISTS (SELECT 1 FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) AS json_each(value))",
        ),
        "variable_index_array_access_in_what": (
            {"convert": "person.event_ref_list[person.birth_ref_index]"},
            "(SELECT json_each.value FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) WITH ORDINALITY AS json_each(value, ordinality) WHERE json_each.ordinality - 1 = CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'birth_ref_index') AS NUMERIC) AS INTEGER) LIMIT 1)",
        ),
        "variable_index_array_access_with_attributes": (
            {"convert": "person.event_ref_list[person.birth_ref_index].role.value"},
            "JSON_EXTRACT_PATH((SELECT json_each.value FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) WITH ORDINALITY AS json_each(value, ordinality) WHERE json_each.ordinality - 1 = CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'birth_ref_index') AS NUMERIC) AS INTEGER) LIMIT 1), 'role.value')",
        ),
        "variable_index_array_access_in_where": (
            {"where": "person.event_ref_list[person.birth_ref_index]"},
            "(SELECT json_each.value FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) WITH ORDINALITY AS json_each(value, ordinality) WHERE json_each.ordinality - 1 = CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'birth_ref_index') AS NUMERIC) AS INTEGER) LIMIT 1)",
        ),
        "variable_index_array_access_with_attributes_in_where": (
            {"where": "person.event_ref_list[person.birth_ref_index].role.value == 5"},
            "(JSON_EXTRACT_PATH((SELECT json_each.value FROM LATERAL json_array_elements(JSON_EXTRACT_PATH(person.json_data, 'event_ref_list')) WITH ORDINALITY AS json_each(value, ordinality) WHERE json_each.ordinality - 1 = CAST(CAST(JSON_EXTRACT_PATH(person.json_data, 'birth_ref_index') AS NUMERIC) AS INTEGER) LIMIT 1), 'role.value') = 5)",
        ),
    }

    def setUp(self):
        self.dialect = "postgres"
        super().setUp()


def _generate_test_methods(test_class):
    for test_name, (input_dict, expected) in test_class.expected_values.items():

        def make_test(name, inp_dict, exp):
            def test_method(self):
                self._run_test_case(name, inp_dict, exp)

            return test_method

        test_method = make_test(test_name, input_dict, expected)
        test_method.__name__ = f"test_{test_name}"
        setattr(test_class, f"test_{test_name}", test_method)


_generate_test_methods(ExpressionBuilderSQLiteTest)
_generate_test_methods(ExpressionBuilderPostgreSQLTest)


if __name__ == "__main__":
    unittest.main()
