"""
Tests for register_gramps_tools — each Gramps-specific tool tested in isolation.

Gramps is not required: module-level stubs are installed into sys.modules before
any Gramps imports are attempted.
"""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Gramps module stubs (installed before importing tools)
# ---------------------------------------------------------------------------

def _install_gramps_stubs():
    for mod_name in [
        "gramps",
        "gramps.gen",
        "gramps.gen.display",
        "gramps.gen.display.name",
        "gramps.gen.datehandler",
        "gramps.gui",
        "gramps.gui.editors",
    ]:
        sys.modules.setdefault(mod_name, ModuleType(mod_name))

    name_mod = sys.modules["gramps.gen.display.name"]
    name_mod.displayer = MagicMock()
    name_mod.displayer.display = lambda p: getattr(p, "_display_name", "Unknown")

    date_mod = sys.modules["gramps.gen.datehandler"]
    date_mod.displayer = MagicMock()
    date_mod.displayer.display = lambda d: "1 Jan 1900"

    editors_mod = sys.modules["gramps.gui.editors"]
    editors_mod.EditPerson = MagicMock()


_install_gramps_stubs()

import tools as _tools_module  # noqa: E402  (must come after stubs)
from tools import call_tool, register_gramps_tools  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate each test from global registry state."""
    original = list(_tools_module.tool_registry)
    _tools_module.tool_registry.clear()
    yield
    _tools_module.tool_registry.clear()
    _tools_module.tool_registry.extend(original)


def _make_person(gramps_id="I0001", handle="h001", name="Smith, John", gender=1):
    p = MagicMock()
    p.get_gramps_id.return_value = gramps_id
    p.get_handle.return_value = handle
    p.get_gender.return_value = gender
    p.get_birth_ref.return_value = None
    p.get_death_ref.return_value = None
    p.get_parent_family_handle_list.return_value = []
    p.get_family_handle_list.return_value = []
    p._display_name = name
    return p


def _make_model(handles=None):
    """Mock model with node_map._index2hndl populated."""
    handles = handles if handles is not None else [("", "h001"), ("", "h002")]
    model = MagicMock()
    model.node_map = MagicMock()
    model.node_map._index2hndl = handles
    model.get_n_columns.return_value = 3
    model.get_value.return_value = "Test Value"
    model.get_iter_from_handle.return_value = MagicMock()
    return model


def _make_sidebar(sidebar_filter):
    """Mock sidebar notebook with one tab exposing *sidebar_filter*."""
    sidebar = MagicMock()
    sidebar.is_visible.return_value = True
    sidebar.get_n_pages.return_value = 1
    tab = MagicMock()
    tab.pui = MagicMock()
    tab.pui.filter = sidebar_filter
    sidebar.get_nth_page.return_value = tab
    return sidebar


def _make_page(model=None, sidebar_filter=None):
    page = MagicMock()
    page.model = model if model is not None else _make_model()
    page.sidebar = _make_sidebar(sidebar_filter) if sidebar_filter is not None else None
    return page


def _make_uistate(active_handle="h001", page=None):
    uistate = MagicMock()
    uistate.get_active.return_value = active_handle

    _page = page if page is not None else _make_page()
    vm = MagicMock()
    vm.get_category.return_value = 0
    vm.goto_page.return_value = _page
    vm.active_page = _page
    uistate.viewmanager = vm
    return uistate


def _make_dbstate(open=True, person=None):
    dbstate = MagicMock()
    dbstate.is_open.return_value = open
    dbstate.db.get_person_from_gramps_id.return_value = person
    dbstate.db.get_person_from_handle.return_value = person
    return dbstate


def _jcall(tool_name, args=None):
    """call_tool and JSON-decode the result."""
    return json.loads(call_tool(tool_name, args or {}))


# ---------------------------------------------------------------------------
# get_person_details
# ---------------------------------------------------------------------------

class TestGetPersonDetails:
    def test_success_returns_person_data(self):
        person = _make_person(gramps_id="I0001", gender=0)  # tuple index 0 → "Male"
        register_gramps_tools(_make_dbstate(person=person), _make_uistate())
        result = _jcall("get_person_details", {"gramps_id": "I0001"})
        assert result["gramps_id"] == "I0001"
        assert result["gender"] == "Male"

    def test_female_gender(self):
        person = _make_person(gender=1)  # tuple index 1 → "Female"
        register_gramps_tools(_make_dbstate(person=person), _make_uistate())
        result = _jcall("get_person_details", {"gramps_id": "I0001"})
        assert result["gender"] == "Female"

    def test_unknown_gender(self):
        person = _make_person(gender=99)  # clamped to 2 → "Unknown"
        register_gramps_tools(_make_dbstate(person=person), _make_uistate())
        result = _jcall("get_person_details", {"gramps_id": "I0001"})
        assert result["gender"] == "Unknown"

    def test_person_not_found_returns_error(self):
        register_gramps_tools(_make_dbstate(person=None), _make_uistate())
        result = _jcall("get_person_details", {"gramps_id": "I9999"})
        assert "error" in result

    def test_db_closed_returns_error(self):
        register_gramps_tools(_make_dbstate(open=False), _make_uistate())
        result = _jcall("get_person_details", {"gramps_id": "I0001"})
        assert "error" in result


# ---------------------------------------------------------------------------
# get_active_person
# ---------------------------------------------------------------------------

class TestGetActivePerson:
    def test_success_returns_person_data(self):
        person = _make_person()
        register_gramps_tools(_make_dbstate(person=person), _make_uistate(active_handle="h001"))
        result = _jcall("get_active_person")
        assert "gramps_id" in result

    def test_no_active_handle_returns_error(self):
        register_gramps_tools(_make_dbstate(person=_make_person()), _make_uistate(active_handle=None))
        result = _jcall("get_active_person")
        assert "error" in result

    def test_db_closed_returns_error(self):
        register_gramps_tools(_make_dbstate(open=False), _make_uistate())
        result = _jcall("get_active_person")
        assert "error" in result


# ---------------------------------------------------------------------------
# set_active_person
# ---------------------------------------------------------------------------

class TestSetActivePerson:
    def test_success_calls_set_active(self):
        person = _make_person()
        uistate = _make_uistate()
        register_gramps_tools(_make_dbstate(person=person), uistate)
        result = _jcall("set_active_person", {"gramps_id": "I0001"})
        assert result.get("gramps_id") == "I0001"
        uistate.set_active.assert_called_once()

    def test_person_not_found_returns_error(self):
        register_gramps_tools(_make_dbstate(person=None), _make_uistate())
        result = _jcall("set_active_person", {"gramps_id": "I9999"})
        assert "error" in result

    def test_db_closed_returns_error(self):
        register_gramps_tools(_make_dbstate(open=False), _make_uistate())
        result = _jcall("set_active_person", {"gramps_id": "I0001"})
        assert "error" in result


# ---------------------------------------------------------------------------
# edit_active_person
# ---------------------------------------------------------------------------

class TestEditActivePerson:
    def test_success_opens_dialog(self):
        person = _make_person()
        register_gramps_tools(_make_dbstate(person=person), _make_uistate(active_handle="h001"))
        result = _jcall("edit_active_person")
        assert "status" in result

    def test_no_active_person_returns_error(self):
        register_gramps_tools(_make_dbstate(person=_make_person()), _make_uistate(active_handle=None))
        result = _jcall("edit_active_person")
        assert "error" in result

    def test_db_closed_returns_error(self):
        register_gramps_tools(_make_dbstate(open=False), _make_uistate())
        result = _jcall("edit_active_person")
        assert "error" in result

    def test_edit_dialog_exception_returns_error(self):
        person = _make_person()
        sys.modules["gramps.gui.editors"].EditPerson.side_effect = RuntimeError("dialog failed")
        register_gramps_tools(_make_dbstate(person=person), _make_uistate(active_handle="h001"))
        result = _jcall("edit_active_person")
        assert "error" in result
        sys.modules["gramps.gui.editors"].EditPerson.side_effect = None


# ---------------------------------------------------------------------------
# switch_to_view
# ---------------------------------------------------------------------------

class TestSwitchToView:
    def test_success_returns_status(self):
        register_gramps_tools(_make_dbstate(), _make_uistate())
        result = _jcall("switch_to_view", {"category_name": "People"})
        assert "status" in result

    def test_unknown_category_returns_error(self):
        uistate = _make_uistate()
        uistate.viewmanager.get_category.return_value = None
        uistate.viewmanager.get_views.return_value = []
        register_gramps_tools(_make_dbstate(), uistate)
        result = _jcall("switch_to_view", {"category_name": "Bogus"})
        assert "error" in result


# ---------------------------------------------------------------------------
# get_view_results
# ---------------------------------------------------------------------------

class TestGetViewResults:
    def test_success_returns_items(self):
        model = _make_model([("", "h001"), ("", "h002")])
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results")
        assert result["total"] == 2
        assert len(result["items"]) == 2

    def test_empty_model(self):
        model = _make_model([])
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results")
        assert result["total"] == 0
        assert result["items"] == []

    def test_no_active_page_returns_error(self):
        uistate = _make_uistate()
        uistate.viewmanager.active_page = None
        register_gramps_tools(_make_dbstate(), uistate)
        result = _jcall("get_view_results")
        assert "error" in result

    def test_model_without_node_map_returns_error(self):
        # spec=[] gives an object with no attributes
        model = MagicMock(spec=[])
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results")
        assert "error" in result
        assert "model_type" in result  # debug info included

    def test_pagination_page_zero(self):
        handles = [("", f"h{i:03}") for i in range(10)]
        model = _make_model(handles)
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results", {"page_number": 0, "page_size": 3})
        assert result["total"] == 10
        assert result["total_pages"] == 4
        assert len(result["items"]) == 3

    def test_pagination_last_page(self):
        handles = [("", f"h{i:03}") for i in range(10)]
        model = _make_model(handles)
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results", {"page_number": 3, "page_size": 3})
        assert len(result["items"]) == 1  # only 1 item on last page

    def test_page_out_of_range_returns_error(self):
        model = _make_model([("", "h001")])
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results", {"page_number": 99, "page_size": 10})
        assert "error" in result

    def test_page_size_clamped_to_100(self):
        handles = [("", f"h{i:03}") for i in range(200)]
        model = _make_model(handles)
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results", {"page_number": 0, "page_size": 999})
        assert len(result["items"]) == 100

    def test_markup_stripped_from_values(self):
        model = _make_model([("", "h001")])
        model.get_value.return_value = "<b>Bold Name</b>"
        register_gramps_tools(_make_dbstate(), _make_uistate(page=_make_page(model=model)))
        result = _jcall("get_view_results")
        assert result["items"][0]["values"] == ["Bold Name"]


# ---------------------------------------------------------------------------
# filter_people
# ---------------------------------------------------------------------------

class TestFilterPeople:
    def _setup(self, filter_mock=None):
        sf = filter_mock or MagicMock()
        model = _make_model([("", "h001")])
        page = _make_page(model=model, sidebar_filter=sf)
        uistate = _make_uistate(page=page)
        register_gramps_tools(_make_dbstate(), uistate)
        return sf

    def test_sets_name_filter(self):
        sf = self._setup()
        _jcall("filter_people", {"name": "Smith"})
        sf.filter_name.set_text.assert_called_with("Smith")

    def test_calls_clicked(self):
        sf = self._setup()
        _jcall("filter_people", {"name": "Smith"})
        sf.clicked.assert_called()

    def test_result_has_filter_key(self):
        self._setup()
        result = _jcall("filter_people", {"name": "Smith"})
        assert "filter" in result
        assert result["filter"]["name"] == "Smith"

    def test_empty_params_not_included_in_filter(self):
        self._setup()
        result = _jcall("filter_people", {})
        assert result["filter"] == {}

    def test_no_sidebar_returns_error_string(self):
        model = _make_model([("", "h001")])
        page = _make_page(model=model, sidebar_filter=None)
        uistate = _make_uistate(page=page)
        register_gramps_tools(_make_dbstate(), uistate)
        result = _jcall("filter_people", {"name": "Smith"})
        # returns a plain string (no sidebar found)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# filter_* smoke tests (views that use _open_sidebar_filter)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name,kwargs,checked_field", [
    ("filter_families",    {"father": "John"},      "filter_father"),
    ("filter_events",      {"description": "Birth"}, "filter_desc"),
    ("filter_places",      {"name": "London"},       "filter_name"),
    ("filter_sources",     {"title": "Census"},      "filter_title"),
    ("filter_citations",   {"source_title": "Tax"},  "filter_src_title"),
    ("filter_media",       {"title": "Photo"},       "filter_title"),
    ("filter_repositories",{"name": "Library"},      "filter_title"),
    ("filter_notes",       {"text": "important"},    "filter_text"),
])
def test_filter_smoke(tool_name, kwargs, checked_field):
    """Each filter tool sets the correct field, clicks, and returns a result dict."""
    sf = MagicMock()
    model = _make_model([("", "h001")])
    page = _make_page(model=model, sidebar_filter=sf)
    uistate = _make_uistate(page=page)
    _tools_module.tool_registry.clear()
    register_gramps_tools(_make_dbstate(), uistate)

    result = _jcall(tool_name, kwargs)

    # The filter field should have been set
    field = getattr(sf, checked_field)
    field.set_text.assert_called()
    sf.clicked.assert_called()

    # Result is either a success dict (with "filter") or an error dict
    assert isinstance(result, dict)
    assert "filter" in result or "error" in result


@pytest.mark.parametrize("tool_name", [
    "filter_families", "filter_events", "filter_places",
    "filter_sources", "filter_citations", "filter_media",
    "filter_repositories", "filter_notes",
])
def test_filter_no_sidebar_returns_error(tool_name):
    """When the sidebar is unavailable, filters return a non-crashing error."""
    model = _make_model([("", "h001")])
    page = _make_page(model=model, sidebar_filter=None)
    uistate = _make_uistate(page=page)
    _tools_module.tool_registry.clear()
    register_gramps_tools(_make_dbstate(), uistate)

    result = _jcall(tool_name, {})
    # Should not raise; returns either a string error or dict with error key
    assert isinstance(result, (str, dict))


# ---------------------------------------------------------------------------
# evaluate_expression
# ---------------------------------------------------------------------------

def _make_grampy_instance(output="hello\n"):
    """Return a mock GrampyScript instance whose evaluate_expression returns *output*."""
    instance = MagicMock()
    instance.evaluate_expression.return_value = output
    return instance


def _make_uistate_with_sidebar(instance=None, gramplet_present=True):
    """
    Uistate whose active page has a sidebar mock — required for
    _get_grampy_instance() to succeed.  Optionally wires up a tab whose
    pui has execute_code (so the tab-switch branch runs).
    """
    sidebar = MagicMock()
    sidebar.is_visible.return_value = True
    sidebar.has_gramplet.return_value = gramplet_present
    tab = MagicMock()
    tab.pui = MagicMock(spec=["execute_code"])
    sidebar.get_n_pages.return_value = 1
    sidebar.get_nth_page.return_value = tab

    page = MagicMock()
    page.model = _make_model()
    page.sidebar = sidebar

    uistate = MagicMock()
    uistate.get_active.return_value = "h001"
    vm = MagicMock()
    vm.active_page = page
    vm.pages = [page]
    uistate.viewmanager = vm
    return uistate


def _setup_grampy_module(instance):
    """Install *instance* as the GrampyScript singleton and register tools."""
    grampy_mod = MagicMock()
    grampy_mod._instance = instance
    sys.modules["GrampyScript"] = grampy_mod
    register_gramps_tools(_make_dbstate(), _make_uistate_with_sidebar(instance))
    return grampy_mod


class TestEvaluateExpression:
    def teardown_method(self):
        sys.modules.pop("GrampyScript", None)

    def test_returns_output_from_instance(self):
        instance = _make_grampy_instance("42\n")
        _setup_grampy_module(instance)
        result = call_tool("evaluate_expression", {"code": "print(6 * 7)"})
        assert "42" in result

    def test_calls_instance_evaluate_expression(self):
        instance = _make_grampy_instance()
        _setup_grampy_module(instance)
        call_tool("evaluate_expression", {"code": "print(1)"})
        instance.evaluate_expression.assert_called_once_with("print(1)")

    def test_syntax_error_returns_message_not_exception(self):
        instance = _make_grampy_instance()
        _setup_grampy_module(instance)
        result = call_tool("evaluate_expression", {"code": "def (broken:"})
        assert "Syntax error" in result or "syntax" in result.lower()
        instance.evaluate_expression.assert_not_called()

    def test_grampy_not_installed_returns_error(self):
        sys.modules.pop("GrampyScript", None)
        # Sidebar present but add_gramplet never sets sys.modules["GrampyScript"]
        register_gramps_tools(_make_dbstate(), _make_uistate_with_sidebar())
        result = call_tool("evaluate_expression", {"code": "print(1)"})
        assert "not installed" in result.lower() or "error" in result.lower()

    def test_instance_none_returns_error(self):
        grampy_mod = MagicMock()
        grampy_mod._instance = None
        sys.modules["GrampyScript"] = grampy_mod
        register_gramps_tools(_make_dbstate(), _make_uistate_with_sidebar())
        result = call_tool("evaluate_expression", {"code": "print(1)"})
        assert "initialised" in result or "error" in result.lower()

    def test_multiline_code_passed_through(self):
        instance = _make_grampy_instance("ok\n")
        _setup_grampy_module(instance)
        code = "for p in people():\n    print(p.gramps_id)"
        call_tool("evaluate_expression", {"code": code})
        instance.evaluate_expression.assert_called_once_with(code)

    def test_output_returned_as_json_string(self):
        instance = _make_grampy_instance("result\n")
        _setup_grampy_module(instance)
        raw = call_tool("evaluate_expression", {"code": "print('result')"})
        decoded = json.loads(raw)
        assert "result" in decoded


# ---------------------------------------------------------------------------
# execute_script — regression after _get_grampy_instance refactor
# ---------------------------------------------------------------------------

class TestExecuteScriptAfterRefactor:
    """Smoke tests ensuring execute_script still works after the helper refactor."""

    def teardown_method(self):
        sys.modules.pop("GrampyScript", None)

    def test_no_sidebar_returns_error(self):
        uistate = _make_uistate()
        uistate.viewmanager.active_page = None
        uistate.viewmanager.pages = []
        register_gramps_tools(_make_dbstate(), uistate)
        result = call_tool("execute_script", {"code": "print(1)"})
        assert "sidebar" in result.lower() or "error" in result.lower()

    def test_grampy_not_installed_returns_error(self):
        sys.modules.pop("GrampyScript", None)
        register_gramps_tools(_make_dbstate(), _make_uistate_with_sidebar(gramplet_present=False))
        result = call_tool("execute_script", {"code": "print(1)"})
        assert "not installed" in result.lower() or "error" in result.lower()

    def test_syntax_error_caught_before_staging(self):
        instance = MagicMock()
        _setup_grampy_module(instance)
        result = call_tool("execute_script", {"code": "def (broken:"})
        assert "Syntax error" in result
        instance.ebuf.set_text.assert_not_called()
