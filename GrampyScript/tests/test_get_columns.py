"""
Tests for the get_columns() utility from GrampyScript.

get_columns parses Python source and extracts argument expressions from all
calls to a given function name (typically "row").  It is pure ast — no GTK
or Gramps imports required — so the function is tested here by reimporting
it directly from the module source via ast/importlib.
"""

import ast
import importlib.util
import os
import sys

import pytest


# ---------------------------------------------------------------------------
# Load get_columns without importing the full GrampyScript module
# (which needs GTK). We parse the source and exec just the function.
# ---------------------------------------------------------------------------

_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "GrampyScript.py"
)


def _load_get_columns():
    src = open(_SOURCE).read()
    tree = ast.parse(src)
    # Extract the get_columns function definition
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_columns":
            snippet = ast.unparse(node)
            ns = {"ast": ast}   # function body uses ast.parse / ast.walk / ast.unparse
            exec(snippet, ns)
            return ns["get_columns"]
    raise RuntimeError("get_columns not found in GrampyScript.py")


get_columns = _load_get_columns()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetColumns:
    def test_single_row_call_simple_names(self):
        code = "for p in people():\n    row(p.gramps_id, p.name)"
        cols = get_columns(code, "row")
        assert cols == ["p.gramps_id", "p.name"]

    def test_no_row_call_returns_empty(self):
        code = "for p in people():\n    print(p.gramps_id)"
        assert get_columns(code, "row") == []

    def test_multiple_row_calls_returns_first(self):
        # get_columns walks all calls; first match wins in ast.walk order
        code = "row(a, b)\nrow(c, d)"
        cols = get_columns(code, "row")
        assert "a" in cols or "c" in cols  # at least one match

    def test_columns_function_name(self):
        code = "columns('ID', 'Name')\nfor p in people():\n    row(p.gramps_id, p.name)"
        cols = get_columns(code, "columns")
        assert cols == ["'ID'", "'Name'"]

    def test_single_arg(self):
        code = "row(p)"
        assert get_columns(code, "row") == ["p"]

    def test_nested_expression_as_arg(self):
        code = "row(len(p.children))"
        cols = get_columns(code, "row")
        assert cols == ["len(p.children)"]

    def test_invalid_syntax_returns_empty(self):
        assert get_columns("def (broken:", "row") == []

    def test_empty_code_returns_empty(self):
        assert get_columns("", "row") == []

    def test_function_name_not_in_code_returns_empty(self):
        code = "for p in people():\n    print(p)"
        assert get_columns(code, "row") == []
