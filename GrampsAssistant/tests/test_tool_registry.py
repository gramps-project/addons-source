"""
Tests for the tool registry: Tool, register_tool, get_tools_schema, call_tool.

No Gramps dependency — pure stdlib / registry logic only.
"""

import inspect
import json
from typing import Annotated

import pytest

import tools as _tools_module
from tools import (
    Tool,
    _resolve_annotation,
    call_tool,
    get_tools_schema,
    register_tool,
    tool_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate each test: save, clear, restore the global registry."""
    original = list(_tools_module.tool_registry)
    _tools_module.tool_registry.clear()
    yield
    _tools_module.tool_registry.clear()
    _tools_module.tool_registry.extend(original)


# ---------------------------------------------------------------------------
# _resolve_annotation
# ---------------------------------------------------------------------------

class TestResolveAnnotation:
    def test_str(self):
        assert _resolve_annotation(str) == ("string", None)

    def test_int(self):
        assert _resolve_annotation(int) == ("integer", None)

    def test_float(self):
        assert _resolve_annotation(float) == ("number", None)

    def test_bool(self):
        assert _resolve_annotation(bool) == ("boolean", None)

    def test_list(self):
        assert _resolve_annotation(list) == ("array", None)

    def test_empty_annotation_defaults_to_string(self):
        assert _resolve_annotation(inspect.Parameter.empty) == ("string", None)

    def test_unknown_type_defaults_to_string(self):
        assert _resolve_annotation(dict) == ("string", None)

    def test_annotated_str_with_description(self):
        ann = Annotated[str, "a query string"]
        json_type, desc = _resolve_annotation(ann)
        assert json_type == "string"
        assert desc == "a query string"

    def test_annotated_int_with_description(self):
        ann = Annotated[int, "a count"]
        json_type, desc = _resolve_annotation(ann)
        assert json_type == "integer"
        assert desc == "a count"

    def test_annotated_without_description_returns_none(self):
        ann = Annotated[str, 42]  # non-string metadata
        _, desc = _resolve_annotation(ann)
        assert desc is None


# ---------------------------------------------------------------------------
# Tool.from_function
# ---------------------------------------------------------------------------

class TestToolFromFunction:
    def test_name_taken_from_function(self):
        def my_func(): pass
        assert Tool.from_function(my_func).name == "my_func"

    def test_full_docstring_used_as_description(self):
        def my_func():
            """First paragraph.

            Second paragraph with more detail.
            """
        t = Tool.from_function(my_func)
        assert "First paragraph." in t.description
        assert "Second paragraph with more detail." in t.description

    def test_empty_docstring(self):
        def my_func(): pass
        assert Tool.from_function(my_func).description == ""

    def test_required_params_have_no_default(self):
        def my_func(a: str, b: int): pass
        t = Tool.from_function(my_func)
        assert t.parameters["required"] == ["a", "b"]

    def test_optional_params_omitted_from_required(self):
        def my_func(a: str = ""): pass
        t = Tool.from_function(my_func)
        assert "required" not in t.parameters

    def test_mixed_required_and_optional(self):
        def my_func(a: str, b: int = 0): pass
        t = Tool.from_function(my_func)
        assert t.parameters["required"] == ["a"]
        assert "b" in t.parameters["properties"]

    def test_param_json_types(self):
        def my_func(a: str, b: int, c: float, d: bool, e: list): pass
        props = Tool.from_function(my_func).parameters["properties"]
        assert props["a"]["type"] == "string"
        assert props["b"]["type"] == "integer"
        assert props["c"]["type"] == "number"
        assert props["d"]["type"] == "boolean"
        assert props["e"]["type"] == "array"

    def test_annotated_param_gets_description(self):
        def my_func(q: Annotated[str, "the search query"]): pass
        props = Tool.from_function(my_func).parameters["properties"]
        assert props["q"]["description"] == "the search query"

    def test_self_param_skipped(self):
        class Foo:
            def method(self, x: str): pass
        props = Tool.from_function(Foo.method).parameters["properties"]
        assert "self" not in props
        assert "x" in props

    def test_no_annotations_default_to_string(self):
        def my_func(x): pass
        props = Tool.from_function(my_func).parameters["properties"]
        assert props["x"]["type"] == "string"


# ---------------------------------------------------------------------------
# Tool schema serialisation
# ---------------------------------------------------------------------------

class TestToolSchema:
    def _simple_tool(self):
        def greet(name: str) -> str:
            "Say hello to someone."
        return Tool.from_function(greet)

    def test_openai_schema_top_level_keys(self):
        schema = self._simple_tool().to_openai_schema()
        assert schema["type"] == "function"
        assert "function" in schema

    def test_openai_schema_function_keys(self):
        fn = self._simple_tool().to_openai_schema()["function"]
        assert fn["name"] == "greet"
        assert "description" in fn
        assert "parameters" in fn

    def test_openai_schema_has_no_input_schema(self):
        schema = self._simple_tool().to_openai_schema()
        assert "input_schema" not in schema
        assert "input_schema" not in schema.get("function", {})

    def test_anthropic_schema_top_level_keys(self):
        schema = self._simple_tool().to_anthropic_schema()
        assert schema["name"] == "greet"
        assert "description" in schema
        assert "input_schema" in schema

    def test_anthropic_schema_has_no_parameters_key(self):
        schema = self._simple_tool().to_anthropic_schema()
        assert "parameters" not in schema

    def test_description_appears_in_both_schemas(self):
        t = self._simple_tool()
        assert t.to_openai_schema()["function"]["description"] == t.description
        assert t.to_anthropic_schema()["description"] == t.description


# ---------------------------------------------------------------------------
# register_tool
# ---------------------------------------------------------------------------

class TestRegisterTool:
    def test_decorator_adds_to_registry(self):
        @register_tool
        def my_tool(x: str) -> str:
            "A tool."
        assert any(t.name == "my_tool" for t in _tools_module.tool_registry)

    def test_original_function_still_callable(self):
        @register_tool
        def double(x: int) -> int:
            "Double x."
            return x * 2
        assert double(4) == 8

    def test_tool_instance_registered_directly(self):
        t = Tool(
            name="direct",
            description="Direct.",
            func=lambda: None,
            parameters={"type": "object", "properties": {}},
        )
        register_tool(t)
        assert any(tool.name == "direct" for tool in _tools_module.tool_registry)

    def test_multiple_registrations_accumulate(self):
        @register_tool
        def tool_a() -> str:
            "A."
        @register_tool
        def tool_b() -> str:
            "B."
        names = {t.name for t in _tools_module.tool_registry}
        assert "tool_a" in names
        assert "tool_b" in names


# ---------------------------------------------------------------------------
# get_tools_schema
# ---------------------------------------------------------------------------

class TestGetToolsSchema:
    def _register_one(self, name="schema_tool"):
        func = lambda q: q
        func.__name__ = name
        func.__doc__ = "A schema tool."
        func.__annotations__ = {"q": str}
        register_tool(func)

    def test_openai_format(self):
        self._register_one("openai_tool")
        schemas = get_tools_schema("openai")
        assert all(s.get("type") == "function" for s in schemas)

    def test_anthropic_format(self):
        self._register_one("anthropic_tool")
        schemas = get_tools_schema("anthropic")
        assert all("input_schema" in s for s in schemas)

    def test_default_is_openai(self):
        self._register_one("default_tool")
        schemas = get_tools_schema()
        assert all(s.get("type") == "function" for s in schemas)

    def test_empty_registry_returns_empty_list(self):
        assert get_tools_schema() == []


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------

class TestCallTool:
    def test_returns_json_string(self):
        @register_tool
        def add(a: int, b: int) -> int:
            "Add two numbers."
            return a + b
        result = call_tool("add", {"a": 2, "b": 3})
        assert isinstance(result, str)
        assert json.loads(result) == 5

    def test_dict_result_serialised(self):
        @register_tool
        def get_dict() -> dict:
            "Return a dict."
            return {"key": "value"}
        assert json.loads(call_tool("get_dict", {})) == {"key": "value"}

    def test_unknown_tool_raises_key_error(self):
        with pytest.raises(KeyError):
            call_tool("no_such_tool_xyz", {})

    def test_tool_receives_kwargs(self):
        received = {}

        @register_tool
        def capture(x: str, y: int) -> str:
            "Capture args."
            received["x"] = x
            received["y"] = y
            return "ok"

        call_tool("capture", {"x": "hello", "y": 42})
        assert received == {"x": "hello", "y": 42}

    def test_non_serialisable_uses_str_fallback(self):
        import datetime

        @register_tool
        def get_date() -> dict:
            "Return a date."
            return {"d": datetime.date(2024, 1, 1)}

        result = json.loads(call_tool("get_date", {}))
        assert isinstance(result["d"], str)
