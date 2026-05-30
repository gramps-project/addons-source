#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2024  Gramps Development Team
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

"""
Tool registry for the Gramps Chatbot.

Usage::

    from .tools import register_tool

    @register_tool
    def my_tool(query: str) -> str:
        "Search for something."
        ...

Tools registered here are automatically exposed to the LLM.
"""

import inspect
import json
import logging
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Python type → JSON Schema type mapping
# ---------------------------------------------------------------------------
_PY_TO_JSON: Dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
}


def _resolve_annotation(annotation) -> tuple:
    """
    Return (json_type_str, description_or_None) for a parameter annotation.

    Handles plain types (str, int, …) and Annotated[T, "description"].
    """
    if annotation is inspect.Parameter.empty:
        return "string", None

    # Annotated[T, "description"] — requires Python 3.9+
    if hasattr(annotation, "__metadata__"):
        args = typing.get_args(annotation)
        base = args[0] if args else str
        desc = args[1] if len(args) > 1 and isinstance(args[1], str) else None
        return _PY_TO_JSON.get(base, "string"), desc

    return _PY_TO_JSON.get(annotation, "string"), None


# ---------------------------------------------------------------------------
# Tool dataclass
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    """
    Wraps a Python callable with the metadata needed to expose it as an
    LLM tool.
    """

    name: str
    description: str
    func: Callable
    parameters: Dict  # JSON Schema {"type":"object","properties":{...},"required":[...]}
    tags: set = field(default_factory=set)  # e.g. {"always"}, {"people"}, {"families"}

    # ------------------------------------------------------------------
    # Schema serialisation
    # ------------------------------------------------------------------

    def to_openai_schema(self) -> Dict:
        """Return OpenAI-format tool dict."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> Dict:
        """Return Anthropic-format tool dict (uses input_schema key)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_function(cls, func: Callable) -> "Tool":
        """
        Build a Tool by introspecting *func*.

        - Name is taken from ``func.__name__``.
        - Description is the full ``func.__doc__``.
        - Parameters are derived from type annotations (``inspect.signature``
          + ``typing.get_type_hints``).
        - Parameters with default values are optional; the rest are required.
        - ``Annotated[T, "description text"]`` populates per-param descriptions.
        """
        name = func.__name__
        doc = inspect.getdoc(func) or ""
        description = doc.strip()

        try:
            hints = typing.get_type_hints(func, include_extras=True)
        except Exception:
            hints = {}

        sig = inspect.signature(func)
        properties: Dict[str, Dict] = {}
        required: List[str] = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            annotation = hints.get(param_name, inspect.Parameter.empty)
            json_type, param_desc = _resolve_annotation(annotation)

            prop: Dict[str, Any] = {"type": json_type}
            if param_desc:
                prop["description"] = param_desc

            properties[param_name] = prop

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        parameters = {
            "type": "object",
            "properties": properties,
        }
        if required:
            parameters["required"] = required

        return cls(
            name=name,
            description=description,
            func=func,
            parameters=parameters,
        )

    def call(self, **kwargs) -> Any:
        """Invoke the wrapped function."""
        return self.func(**kwargs)


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

tool_registry: List[Tool] = []


def register_tool(func_or_tool=None, *, tags=None):
    """
    Decorator or direct call to add a tool to the global registry.

    Can be used as a plain decorator or with keyword arguments::

        @register_tool
        def search(q: str) -> str:
            ...

        @register_tool(tags={"always"})
        def search_wikipedia(query: str) -> str:
            ...

        result = search("Smith")   # still works as a normal function
    """
    def _register(func, tag_set):
        if isinstance(func, Tool):
            tool_registry.append(func)
            return func
        tool = Tool.from_function(func)
        if tag_set:
            tool.tags = set(tag_set)
        tool_registry.append(tool)
        return func

    if func_or_tool is None:
        # Called as @register_tool(tags=...) — return a decorator
        def decorator(func):
            return _register(func, tags)
        return decorator

    # Called as @register_tool (no parentheses) or register_tool(func)
    return _register(func_or_tool, tags)


def get_tools_schema(backend_type: str = "openai", tags=None) -> List[Dict]:
    """
    Return a list of tool dicts formatted for the given backend.

    *backend_type* is ``"openai"`` (default) or ``"anthropic"``.

    If *tags* is provided (a set of strings), only tools whose tags
    intersect with it are returned, plus tools tagged ``"always"`` and
    untagged tools (for backward compatibility with user-registered tools).
    If *tags* is None, all tools are returned.
    """
    if tags is None:
        tools = tool_registry
    else:
        tools = [
            t for t in tool_registry
            if not t.tags or "always" in t.tags or bool(t.tags & tags)
        ]
    if backend_type == "anthropic":
        return [t.to_anthropic_schema() for t in tools]
    return [t.to_openai_schema() for t in tools]


def call_tool(name: str, args: Dict) -> str:
    """
    Find the tool named *name*, call it with *args*, and return the result
    as a JSON string.

    Raises ``KeyError`` if no such tool is registered.
    """
    for tool in tool_registry:
        if tool.name == name:
            result = tool.func(**args)
            return json.dumps(result, ensure_ascii=False, default=str)
    raise KeyError(f"No tool named {name!r}")


# ---------------------------------------------------------------------------
# Built-in Gramps tools
# ---------------------------------------------------------------------------


def _format_person_details(db, person) -> dict:
    """
    Return a structured dict describing *person* suitable for JSON serialisation.
    """
    from gramps.gen.display.name import displayer as name_displayer
    from gramps.gen.datehandler import displayer as date_displayer

    result = {
        "name": name_displayer.display(person),
        "gramps_id": person.get_gramps_id(),
        "gender": ("Male", "Female", "Unknown")[min(person.get_gender(), 2)],
    }

    birth_ref = person.get_birth_ref()
    if birth_ref:
        birth_event = db.get_event_from_handle(birth_ref.ref)
        birth = {"date": date_displayer.display(birth_event.get_date_object())}
        place_handle = birth_event.get_place_handle()
        if place_handle:
            birth["place"] = db.get_place_from_handle(place_handle).get_name().get_value()
        result["birth"] = birth

    death_ref = person.get_death_ref()
    if death_ref:
        death_event = db.get_event_from_handle(death_ref.ref)
        death = {"date": date_displayer.display(death_event.get_date_object())}
        place_handle = death_event.get_place_handle()
        if place_handle:
            death["place"] = db.get_place_from_handle(place_handle).get_name().get_value()
        result["death"] = death

    parents = []
    for fhandle in person.get_parent_family_handle_list()[:2]:
        family = db.get_family_from_handle(fhandle)
        father_handle = family.get_father_handle()
        mother_handle = family.get_mother_handle()
        if father_handle:
            father = db.get_person_from_handle(father_handle)
            parents.append({"role": "father", "name": name_displayer.display(father),
                            "gramps_id": father.get_gramps_id()})
        if mother_handle:
            mother = db.get_person_from_handle(mother_handle)
            parents.append({"role": "mother", "name": name_displayer.display(mother),
                            "gramps_id": mother.get_gramps_id()})
    if parents:
        result["parents"] = parents

    families = []
    for fhandle in person.get_family_handle_list()[:3]:
        family = db.get_family_from_handle(fhandle)
        father_h = family.get_father_handle()
        mother_h = family.get_mother_handle()
        spouse_h = mother_h if father_h == person.get_handle() else father_h
        family_entry = {}
        if spouse_h:
            spouse = db.get_person_from_handle(spouse_h)
            family_entry["spouse"] = {"name": name_displayer.display(spouse),
                                      "gramps_id": spouse.get_gramps_id()}
        children = []
        for child_ref in family.get_child_ref_list()[:8]:
            child = db.get_person_from_handle(child_ref.ref)
            children.append({"name": name_displayer.display(child),
                             "gramps_id": child.get_gramps_id()})
        if children:
            family_entry["children"] = children
        if family_entry:
            families.append(family_entry)
    if families:
        result["families"] = families

    return result


# Maps sidebar filter class name → primary text field used for keyword search
_SIDEBAR_FILTER_FIELD = {
    "PersonSidebarFilter": "filter_name",
    "FamilySidebarFilter": "filter_father",
    "EventSidebarFilter": "filter_desc",
    "PlaceSidebarFilter": "filter_name",
    "SourceSidebarFilter": "filter_title",
    "CitationSidebarFilter": "filter_src_title",
    "MediaSidebarFilter": "filter_title",
    "RepoSidebarFilter": "filter_title",
    "NoteSidebarFilter": "filter_text",
}


def register_gramps_tools(dbstate, uistate):
    """
    Create and register the built-in Gramps database tools.

    Safe to call multiple times — guards against double-registration.
    Call this from ``ChatbotPanel.__init__`` after *dbstate* is available.
    """
    existing_names = {t.name for t in tool_registry}

    def get_person_details(gramps_id: str) -> dict:
        """
        Get detailed information about a specific person by their Gramps ID.

        Returns name, birth, death, parents, spouses, and children.
        gramps_id: The Gramps ID of the person (e.g. I0001).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        return _format_person_details(db, person)

    def get_active_person() -> dict:
        """
        Get information about the currently active (selected) person in Gramps.

        Returns full details of the person currently being viewed.
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        handle = uistate.get_active("Person")
        if not handle:
            return {"error": "No person is currently selected."}
        person = dbstate.db.get_person_from_handle(handle)
        return _format_person_details(dbstate.db, person)

    def get_home_person() -> dict:
        """
        Get information about the home person (default person) of the Gramps database.

        The home person is the default person set in Gramps preferences,
        distinct from whoever is currently selected.
        Returns full details including name, birth, death, parents, spouses, and children.
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        person = dbstate.db.get_default_person()
        if person is None:
            return {"error": "No home person is set in this database."}
        return _format_person_details(dbstate.db, person)

    def switch_to_view(category_name: str) -> dict:
        """
        Switch the main Gramps window to a named view category.

        Valid category names include: People, Families, Events, Places,
        Sources, Repositories, Media, Notes, Citations, Dashboard, Geography,
        Relationships, Pedigree, Fan Chart.
        category_name: The name of the view category to switch to.
        """
        vm = uistate.viewmanager
        cat_num = vm.get_category(category_name)
        if cat_num is None:
            available = [
                cat_views[0][0].category[1]
                for cat_views in vm.get_views()
                if cat_views
            ]
            return {"error": f"Unknown category '{category_name}'.",
                    "available": available}
        vm.goto_page(cat_num, None)
        return {"status": f"Switched to {category_name} view."}

    def search_in_view(category_name: str, search_text: str) -> dict:
        """
        Switch to a view category, apply a sidebar filter, and press Find.

        Works on list views: People, Families, Events, Places, Sources,
        Repositories, Media, Notes, Citations.
        category_name: The view category to search in (e.g. People, Events).
        search_text: The text to filter by (name, title, description, etc.).
        """
        vm = uistate.viewmanager
        cat_num = vm.get_category(category_name)
        if cat_num is None:
            available = [
                cat_views[0][0].category[1]
                for cat_views in vm.get_views()
                if cat_views
            ]
            return {"error": f"Unknown category '{category_name}'.",
                    "available": available}
        page = vm.goto_page(cat_num, None)
        filter_class = getattr(page, "filter_class", None)
        if filter_class is None:
            return {"error": f"{category_name} does not support sidebar filtering."}

        field_name = _SIDEBAR_FILTER_FIELD.get(filter_class.__name__)
        if field_name is None:
            return {"error": f"No known filter field for {filter_class.__name__}."}

        sidebar = getattr(page, "sidebar", None)
        if sidebar is not None and not sidebar.is_visible():
            sidebar.show()
            if hasattr(page, "search_bar"):
                page.search_bar.hide()

        live_filter = None
        if sidebar is not None:
            for i in range(sidebar.get_n_pages()):
                tab = sidebar.get_nth_page(i)
                if tab and tab.pui and hasattr(tab.pui, "filter"):
                    live_filter = tab.pui.filter
                    break

        if live_filter is not None:
            getattr(live_filter, field_name).set_text(search_text)
            live_filter.clicked(None)
        else:
            def _apply():
                page.generic_filter = _sf.get_filter()
                page.build_tree()
            _sf = filter_class(dbstate, uistate, _apply)
            getattr(_sf, field_name).set_text(search_text)
            _sf.clicked(None)

        return {"filter": {"category": category_name, "text": search_text},
                "results": get_view_results()}

    def set_active_person(gramps_id: str) -> dict:
        """
        Set the active (selected) person in Gramps by their Gramps ID.

        Navigates the UI to the person so all views update to show them.
        gramps_id: The Gramps ID of the person to select (e.g. I0001).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        uistate.set_active(person.get_handle(), "Person")
        from gramps.gen.display.name import displayer as name_displayer
        return {"status": "Active person set.",
                "name": name_displayer.display(person),
                "gramps_id": gramps_id}

    def edit_active_person() -> dict:
        """
        Open the Gramps edit dialog for the currently active (selected) person.

        Use this when the user asks to edit, update, or modify the current person.
        Returns a confirmation message or an error.
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        handle = uistate.get_active("Person")
        if not handle:
            return {"error": "No person is currently selected."}
        person = dbstate.db.get_person_from_handle(handle)
        try:
            from gramps.gui.editors import EditPerson

            EditPerson(dbstate, uistate, [], person)
            return {"status": f"Opened edit dialog for {person.get_gramps_id()}."}
        except Exception as exc:
            return {"error": f"Could not open edit dialog: {exc}"}

    _GENDER_INDEX = {"male": 1, "female": 2, "other": 3, "unknown": 4}

    def filter_people(
        name: str = "",
        gender: str = "",
        birth_year: str = "",
        death_year: str = "",
        birth_place: str = "",
        death_place: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the People view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        Dates accept Gramps date expressions such as "1760", "before 1800",
        or "between 1750 and 1800".

        name: Substring of the person's name.
        gender: One of: male, female, other, unknown.
        birth_year: Birth date expression (e.g. "1760", "before 1800").
        death_year: Death date expression.
        birth_place: Substring of the birth place name.
        death_place: Substring of the death place name.
        note: Substring to search for in notes.
        """
        vm = uistate.viewmanager
        cat_num = vm.get_category("People")
        if cat_num is None:
            return "Could not find the People view."
        page = vm.goto_page(cat_num, None)

        sidebar = getattr(page, "sidebar", None)
        if sidebar is not None and not sidebar.is_visible():
            sidebar.show()
            if hasattr(page, "search_bar"):
                page.search_bar.hide()

        live_filter = None
        if sidebar is not None:
            for i in range(sidebar.get_n_pages()):
                tab = sidebar.get_nth_page(i)
                if tab and tab.pui and hasattr(tab.pui, "filter"):
                    live_filter = tab.pui.filter
                    break

        if live_filter is None:
            return "Could not find the People sidebar filter."

        live_filter.clear(None)

        if name:
            live_filter.filter_name.set_text(name)
        if gender:
            live_filter.filter_gender.set_active(
                _GENDER_INDEX.get(gender.lower(), 0)
            )
        if birth_year:
            live_filter.filter_birth.set_text(birth_year)
        if death_year:
            live_filter.filter_death.set_text(death_year)
        if birth_place:
            live_filter.filter_birth_place.set_text(birth_place)
        if death_place:
            live_filter.filter_death_place.set_text(death_place)
        if note:
            live_filter.filter_note.set_text(note)

        live_filter.clicked(None)

        applied = {k: v for k, v in [("name", name), ("gender", gender),
                                      ("birth_year", birth_year), ("death_year", death_year),
                                      ("birth_place", birth_place), ("death_place", death_place),
                                      ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    # ------------------------------------------------------------------
    # Shared helper: navigate to a category, show sidebar, return filter
    # ------------------------------------------------------------------

    def _open_sidebar_filter(category_name):
        """Return (live_filter, error_str). error_str is None on success."""
        vm = uistate.viewmanager
        cat_num = vm.get_category(category_name)
        if cat_num is None:
            return None, f"Could not find the {category_name} view."
        page = vm.goto_page(cat_num, None)
        sidebar = getattr(page, "sidebar", None)
        if sidebar is not None and not sidebar.is_visible():
            sidebar.show()
            if hasattr(page, "search_bar"):
                page.search_bar.hide()
        if sidebar is None:
            return None, f"{category_name} has no sidebar."
        for i in range(sidebar.get_n_pages()):
            tab = sidebar.get_nth_page(i)
            if tab and tab.pui and hasattr(tab.pui, "filter"):
                return tab.pui.filter, None
        return None, f"Could not find sidebar filter for {category_name}."

    # ------------------------------------------------------------------
    # Per-view filter tools
    # ------------------------------------------------------------------

    def filter_families(
        father: str = "",
        mother: str = "",
        child: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Families view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        father: Substring of the father's name.
        mother: Substring of the mother's name.
        child: Substring of a child's name.
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Families")
        if err:
            return err
        f.clear(None)
        if father: f.filter_father.set_text(father)
        if mother: f.filter_mother.set_text(mother)
        if child:  f.filter_child.set_text(child)
        if note:   f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("father", father), ("mother", mother),
                                      ("child", child), ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_events(
        description: str = "",
        participants: str = "",
        date: str = "",
        place: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Events view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        description: Substring of the event description.
        participants: Substring of participant names.
        date: Date expression (e.g. "1760", "before 1800").
        place: Substring of the place name.
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Events")
        if err:
            return err
        f.clear(None)
        if description:  f.filter_desc.set_text(description)
        if participants: f.filter_mainparts.set_text(participants)
        if date:         f.filter_date.set_text(date)
        if place:        f.filter_place.set_text(place)
        if note:         f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("description", description), ("participants", participants),
                                      ("date", date), ("place", place), ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_places(
        name: str = "",
        code: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Places view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        name: Substring of the place name.
        code: Place code substring.
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Places")
        if err:
            return err
        f.clear(None)
        if name: f.filter_name.set_text(name)
        if code: f.filter_code.set_text(code)
        if note: f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("name", name), ("code", code), ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_sources(
        title: str = "",
        author: str = "",
        abbreviation: str = "",
        publication: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Sources view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        title: Substring of the source title.
        author: Substring of the author name.
        abbreviation: Substring of the abbreviation.
        publication: Substring of the publication info.
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Sources")
        if err:
            return err
        f.clear(None)
        if title:        f.filter_title.set_text(title)
        if author:       f.filter_author.set_text(author)
        if abbreviation: f.filter_abbr.set_text(abbreviation)
        if publication:  f.filter_pub.set_text(publication)
        if note:         f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("title", title), ("author", author),
                                      ("abbreviation", abbreviation), ("publication", publication),
                                      ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_citations(
        source_title: str = "",
        source_author: str = "",
        page: str = "",
        date: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Citations view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        source_title: Substring of the source title.
        source_author: Substring of the source author.
        page: Volume/page substring.
        date: Date expression (e.g. "1760", "before 1800").
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Citations")
        if err:
            return err
        f.clear(None)
        if source_title:  f.filter_src_title.set_text(source_title)
        if source_author: f.filter_src_author.set_text(source_author)
        if page:          f.filter_page.set_text(page)
        if date:          f.filter_date.set_text(date)
        if note:          f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("source_title", source_title), ("source_author", source_author),
                                      ("page", page), ("date", date), ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_media(
        title: str = "",
        mime_type: str = "",
        path: str = "",
        date: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Media view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        title: Substring of the media title.
        mime_type: MIME type substring (e.g. "image/jpeg").
        path: Substring of the file path.
        date: Date expression.
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Media")
        if err:
            return err
        f.clear(None)
        if title:     f.filter_title.set_text(title)
        if mime_type: f.filter_type.set_text(mime_type)
        if path:      f.filter_path.set_text(path)
        if date:      f.filter_date.set_text(date)
        if note:      f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("title", title), ("mime_type", mime_type),
                                      ("path", path), ("date", date), ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_repositories(
        name: str = "",
        address: str = "",
        url: str = "",
        note: str = "",
    ) -> str:
        """
        Switch to the Repositories view and filter using the sidebar filter.

        Each parameter is optional; supply only the ones you need.
        name: Substring of the repository name.
        address: Substring of the address.
        url: Substring of the URL.
        note: Substring to search for in notes.
        """
        f, err = _open_sidebar_filter("Repositories")
        if err:
            return err
        f.clear(None)
        if name:    f.filter_title.set_text(name)
        if address: f.filter_address.set_text(address)
        if url:     f.filter_url.set_text(url)
        if note:    f.filter_note.set_text(note)
        f.clicked(None)
        applied = {k: v for k, v in [("name", name), ("address", address),
                                      ("url", url), ("note", note)] if v}
        return {"filter": applied, "results": get_view_results()}

    def filter_notes(
        text: str = "",
    ) -> str:
        """
        Switch to the Notes view and filter using the sidebar filter.

        text: Substring to search for within note text.
        """
        f, err = _open_sidebar_filter("Notes")
        if err:
            return err
        f.clear(None)
        if text: f.filter_text.set_text(text)
        f.clicked(None)
        applied = {"text": text} if text else {}
        return {"filter": applied, "results": get_view_results()}

    def get_view_results(page_number: int = 0, page_size: int = 100) -> dict:
        """
        Get items currently shown in the active Gramps view after filtering.

        All data comes from the in-memory list model — no database lookups.
        page_number: Zero-based page number (default 0).
        page_size: Number of items per page (1–100, default 100).
        """
        import re as _re
        _strip_markup = lambda s: _re.sub(r"<[^>]+>", "", s)

        page_size = max(1, min(100, page_size))

        vm = uistate.viewmanager
        active = vm.active_page
        if active is None:
            return {"error": "No active view."}

        model = getattr(active, "model", None)
        if model is None or not hasattr(model, "node_map"):
            model_type = type(model).__name__ if model is not None else "None"
            model_attrs = [a for a in dir(model) if not a.startswith("__")] if model is not None else []
            return {"error": "Current view does not expose a filterable list model.",
                    "model_type": model_type,
                    "model_attrs": model_attrs}

        node_map = model.node_map
        index2hndl = node_map._index2hndl
        total = len(index2hndl)

        if total == 0:
            return {"total": 0, "page": page_number, "total_pages": 0, "items": []}

        start = page_number * page_size
        total_pages = (total + page_size - 1) // page_size
        if start >= total:
            return {"error": f"Page {page_number} is out of range.",
                    "total": total, "total_pages": total_pages}

        end = min(start + page_size, total)
        n_cols = model.get_n_columns()

        items = []
        for pos in range(start, end):
            _, handle = index2hndl[pos]
            try:
                iter_ = model.get_iter_from_handle(handle)
            except Exception:
                items.append({"error": True})
                continue
            values = []
            seen: set = set()
            for col in range(min(n_cols, 8)):
                try:
                    val = model.get_value(iter_, col)
                    if isinstance(val, str):
                        val = _strip_markup(val).strip()
                        if val and val not in seen:
                            seen.add(val)
                            values.append(val)
                except Exception:
                    pass
            items.append({"values": values})

        return {"total": total, "page": page_number, "total_pages": total_pages, "items": items}

    def is_person_alive(gramps_id: str) -> dict:
        """
        Check whether a person is probably alive, using Gramps' built-in heuristic.

        Uses birth, death, and family dates to estimate whether the person is
        still living. Returns a best-guess boolean and a plain-English explanation
        of the reasoning.
        gramps_id: The Gramps ID of the person (e.g. I0001).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        from gramps.gen.utils.alive import probably_alive
        alive, birth, death, explanation, _relative = probably_alive(
            person, db, return_range=True
        )
        from gramps.gen.datehandler import displayer as date_displayer
        result = {"gramps_id": gramps_id, "probably_alive": alive, "explanation": explanation}
        if birth and birth.is_valid():
            result["estimated_birth"] = date_displayer.display(birth)
        if death and death.is_valid():
            result["estimated_death"] = date_displayer.display(death)
        return result

    def find_relationship(gramps_id_a: str, gramps_id_b: str) -> dict:
        """
        Find the relationship between two people in the database.

        Returns a human-readable relationship string such as
        'second cousin twice removed' or 'great-grandmother'.
        gramps_id_a: Gramps ID of the first person (e.g. I0001).
        gramps_id_b: Gramps ID of the second person (e.g. I0042).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person_a = db.get_person_from_gramps_id(gramps_id_a)
        if person_a is None:
            return {"error": f"No person found with ID '{gramps_id_a}'."}
        person_b = db.get_person_from_gramps_id(gramps_id_b)
        if person_b is None:
            return {"error": f"No person found with ID '{gramps_id_b}'."}
        from gramps.gen.relationship import get_relationship_calculator
        from gramps.gen.display.name import displayer as name_displayer
        calc = get_relationship_calculator()
        rel_str, dist_a, dist_b = calc.get_one_relationship(
            db, person_a, person_b, extra_info=True
        )
        return {
            "person_a": {"gramps_id": gramps_id_a, "name": name_displayer.display(person_a)},
            "person_b": {"gramps_id": gramps_id_b, "name": name_displayer.display(person_b)},
            "relationship": rel_str if rel_str else "no relationship found",
            "distance_from_a": dist_a,
            "distance_from_b": dist_b,
        }

    def get_database_statistics() -> dict:
        """
        Return a summary of how many records are in the currently open database.

        Counts people, families, events, places, sources, citations, media
        objects, notes, repositories, and tags.
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        return {
            "people":       db.get_number_of_people(),
            "families":     db.get_number_of_families(),
            "events":       db.get_number_of_events(),
            "places":       db.get_number_of_places(),
            "sources":      db.get_number_of_sources(),
            "citations":    db.get_number_of_citations(),
            "media":        db.get_number_of_media(),
            "notes":        db.get_number_of_notes(),
            "repositories": db.get_number_of_repositories(),
            "tags":         db.get_number_of_tags(),
        }

    def get_person_events(gramps_id: str) -> dict:
        """
        Get all recorded events for a person, not just birth and death.

        Returns each event's type, date, place, and description.
        Useful for seeing a full life timeline including baptism, marriage,
        census, immigration, military service, occupation, and more.
        gramps_id: The Gramps ID of the person (e.g. I0001).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        from gramps.gen.display.name import displayer as name_displayer
        from gramps.gen.datehandler import displayer as date_displayer
        events = []
        for event_ref in person.get_event_ref_list():
            event = db.get_event_from_handle(event_ref.ref)
            if event is None:
                continue
            entry = {
                "type": str(event.get_type()),
                "role": str(event_ref.get_role()),
                "date": date_displayer.display(event.get_date_object()),
                "description": event.get_description(),
            }
            place_handle = event.get_place_handle()
            if place_handle:
                place = db.get_place_from_handle(place_handle)
                if place:
                    entry["place"] = place.get_name().get_value()
            events.append(entry)
        from gramps.gen.display.name import displayer as name_displayer
        return {
            "gramps_id": gramps_id,
            "name": name_displayer.display(person),
            "events": events,
        }

    def get_children(gramps_id: str) -> dict:
        """
        Get all children of a person.

        Returns a list of children with their names and Gramps IDs,
        grouped by family (spouse).
        gramps_id: The Gramps ID of the person (e.g. I0001).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        from gramps.gen.display.name import displayer as name_displayer
        families = []
        for family_handle in person.get_family_handle_list():
            family = db.get_family_from_handle(family_handle)
            if not family:
                continue
            father_h = family.get_father_handle()
            mother_h = family.get_mother_handle()
            spouse_h = mother_h if father_h == person.get_handle() else father_h
            family_entry = {"family_id": family.get_gramps_id(), "children": []}
            if spouse_h:
                spouse = db.get_person_from_handle(spouse_h)
                if spouse:
                    family_entry["spouse"] = {
                        "name": name_displayer.display(spouse),
                        "gramps_id": spouse.get_gramps_id(),
                    }
            for child_ref in family.get_child_ref_list():
                child = db.get_person_from_handle(child_ref.ref)
                if child:
                    family_entry["children"].append({
                        "name": name_displayer.display(child),
                        "gramps_id": child.get_gramps_id(),
                    })
            families.append(family_entry)
        return {
            "gramps_id": gramps_id,
            "name": name_displayer.display(person),
            "families": families,
        }

    def get_siblings(gramps_id: str) -> dict:
        """
        Get all siblings of a person.

        Returns a list of siblings with their names and Gramps IDs.
        Half-siblings (from different parents) are included and labelled.
        gramps_id: The Gramps ID of the person (e.g. I0001).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        from gramps.gen.display.name import displayer as name_displayer
        seen = set()
        seen.add(person.get_handle())
        siblings = []
        for family_handle in person.get_parent_family_handle_list():
            family = db.get_family_from_handle(family_handle)
            if not family:
                continue
            for child_ref in family.get_child_ref_list():
                handle = child_ref.ref
                if handle in seen:
                    continue
                seen.add(handle)
                sibling = db.get_person_from_handle(handle)
                if sibling:
                    siblings.append({
                        "name": name_displayer.display(sibling),
                        "gramps_id": sibling.get_gramps_id(),
                    })
        return {
            "gramps_id": gramps_id,
            "name": name_displayer.display(person),
            "siblings": siblings,
        }

    def get_ancestors(gramps_id: str, max_generations: int = 4) -> dict:
        """
        Get ancestors of a person up to a given number of generations.

        Returns a flat list of ancestors with their names, Gramps IDs, and
        generation number (1 = parents, 2 = grandparents, etc.).
        gramps_id: The Gramps ID of the person (e.g. I0001).
        max_generations: How many generations back to search (default 4, max 10).
        """
        if not dbstate.is_open():
            return {"error": "No database is currently open."}
        db = dbstate.db
        person = db.get_person_from_gramps_id(gramps_id)
        if person is None:
            return {"error": f"No person found with ID '{gramps_id}'."}
        from gramps.gen.display.name import displayer as name_displayer
        max_generations = max(1, min(10, max_generations))
        ancestors = []
        seen = set()
        queue = [(person.get_handle(), 0)]
        while queue:
            handle, gen = queue.pop(0)
            if gen == 0:
                for family_handle in db.get_person_from_handle(handle).get_parent_family_handle_list():
                    family = db.get_family_from_handle(family_handle)
                    if not family:
                        continue
                    for parent_h in [family.get_father_handle(), family.get_mother_handle()]:
                        if parent_h and parent_h not in seen:
                            seen.add(parent_h)
                            queue.append((parent_h, 1))
                continue
            ancestor = db.get_person_from_handle(handle)
            if not ancestor:
                continue
            ancestors.append({
                "name": name_displayer.display(ancestor),
                "gramps_id": ancestor.get_gramps_id(),
                "generation": gen,
            })
            if gen < max_generations:
                for family_handle in ancestor.get_parent_family_handle_list():
                    family = db.get_family_from_handle(family_handle)
                    if not family:
                        continue
                    for parent_h in [family.get_father_handle(), family.get_mother_handle()]:
                        if parent_h and parent_h not in seen:
                            seen.add(parent_h)
                            queue.append((parent_h, gen + 1))
        return {
            "gramps_id": gramps_id,
            "name": name_displayer.display(person),
            "max_generations": max_generations,
            "ancestors": ancestors,
        }

    _tool_tags = {
        "get_active_person":      {"always"},
        "get_home_person":        {"always"},
        "get_view_results":       {"always"},
        "switch_to_view":         {"always"},
        "get_database_statistics": {"always"},
        "get_person_details":     {"people"},
        "set_active_person":      {"people"},
        "edit_active_person":     {"people"},
        "filter_people":          {"people"},
        "is_person_alive":        {"people"},
        "find_relationship":      {"people"},
        "get_person_events":      {"people"},
        "get_children":           {"people", "families"},
        "get_siblings":           {"people"},
        "get_ancestors":          {"people"},
        "filter_families":        {"families"},
        "filter_events":          {"events"},
        "filter_places":          {"places"},
        "filter_sources":         {"sources"},
        "filter_citations":       {"sources"},
        "filter_media":           {"media"},
        "filter_repositories":    {"repositories"},
        "filter_notes":           {"notes"},
        "search_in_view":         {"people", "families", "events", "places",
                                   "sources", "media", "repositories", "notes"},
    }

    for func in [get_person_details, get_active_person, get_home_person, set_active_person,
                 get_view_results,
                 switch_to_view, search_in_view,
                 filter_people, filter_families, filter_events, filter_places,
                 filter_sources, filter_citations, filter_media,
                 filter_repositories, filter_notes,
                 edit_active_person,
                 is_person_alive, find_relationship, get_database_statistics,
                 get_person_events, get_children, get_siblings, get_ancestors]:
        if func.__name__ not in existing_names:
            tool = Tool.from_function(func)
            tool.tags = _tool_tags.get(func.__name__, set())
            tool_registry.append(tool)
            _LOG.debug("Registered Gramps tool: %s", func.__name__)


# ---------------------------------------------------------------------------
# Gramps wiki search tool (registered at import time, no db needed)
# ---------------------------------------------------------------------------


@register_tool(tags={"always"})
def search_wikipedia(query: str) -> str:
    """
    Search Wikipedia for articles matching a query and return summaries.

    Useful for looking up historical context, places, surnames, events,
    and general genealogical background information.
    query: The search terms (e.g. 'Ellis Island immigration history').
    """
    import html as _html
    import urllib.parse
    import urllib.request

    # Step 1: find matching page titles
    search_params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 3,
        "utf8": 1,
        "format": "json",
    })
    search_url = "https://en.wikipedia.org/w/api.php?" + search_params
    req = urllib.request.Request(
        search_url, headers={"User-Agent": "GrampsAssist/1.0 (genealogy research tool)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Wikipedia search failed: {exc}"

    import json as _json
    try:
        search_data = _json.loads(data)
    except Exception:
        return "Wikipedia search returned unparseable data."

    hits = search_data.get("query", {}).get("search", [])
    if not hits:
        return f"No Wikipedia articles found for '{query}'."

    titles = [h["title"] for h in hits]

    # Step 2: fetch intro extracts for those titles
    extract_params = urllib.parse.urlencode({
        "action": "query",
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "exsentences": 3,
        "titles": "|".join(titles),
        "utf8": 1,
        "format": "json",
    })
    extract_url = "https://en.wikipedia.org/w/api.php?" + extract_params
    req2 = urllib.request.Request(
        extract_url, headers={"User-Agent": "GrampsAssist/1.0 (genealogy research tool)"}
    )
    try:
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            ext_data = _json.loads(resp2.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return f"Wikipedia extract fetch failed: {exc}"

    pages = ext_data.get("query", {}).get("pages", {})
    # Build title → extract map
    extract_map = {
        page["title"]: page.get("extract", "").strip()
        for page in pages.values()
    }

    lines = []
    for title in titles:
        url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
        extract = extract_map.get(title, "")
        if len(extract) > 300:
            extract = extract[:297] + "..."
        entry = f"{title}\n  {url}"
        if extract:
            entry += f"\n  {extract}"
        lines.append(entry)

    return f"Wikipedia results for '{query}':\n\n" + "\n\n".join(lines)


# @register_tool
# def search_gramps_wiki(query: str, max_results: int = 5) -> str:
#     """
#     Search the Gramps Project wiki for pages matching a query.

#     Returns the titles, URLs, and brief excerpts of the top matching pages.
#     Useful for answering questions about how to use Gramps, its features,
#     and genealogy workflows documented on the wiki.
#     """
#     import html as _html
#     import re
#     import urllib.parse
#     import urllib.request

#     params = urllib.parse.urlencode(
#         {"title": "Special:Search", "search": query, "fulltext": "Search"}
#     )
#     url = "https://www.gramps-project.org/wiki/index.php?" + params
#     req = urllib.request.Request(url, headers={"User-Agent": "GrampsChatbot/1.0"})
#     try:
#         with urllib.request.urlopen(req, timeout=15) as resp:
#             body = resp.read().decode("utf-8", errors="replace")
#     except Exception as exc:
#         return f"Wiki search failed: {exc}"

#     # Each search hit is wrapped in an <li class="mw-search-result ..."> block
#     items = re.findall(
#         r'class="mw-search-result[^"]*".*?</li>',
#         body,
#         re.DOTALL,
#     )

#     _tag_re = re.compile(r"<[^>]+>")
#     _ws_re = re.compile(r"\s+")

#     lines = []
#     for item in items[: int(max_results)]:
#         m = re.search(
#             r'class="mw-search-result-heading".*?href="([^"]+)"[^>]*>([^<]+)',
#             item,
#             re.DOTALL,
#         )
#         if not m:
#             continue
#         href = m.group(1)
#         title = _html.unescape(m.group(2)).strip()
#         page_url = (
#             "https://www.gramps-project.org" + href
#             if href.startswith("/")
#             else href
#         )
#         s = re.search(r'class="searchresult"[^>]*>(.*?)</div>', item, re.DOTALL)
#         snippet = ""
#         if s:
#             snippet = _ws_re.sub(
#                 " ", _tag_re.sub("", _html.unescape(s.group(1)))
#             ).strip()
#             if len(snippet) > 200:
#                 snippet = snippet[:197] + "..."
#         lines.append(
#             f"{title}\n  {page_url}" + (f"\n  {snippet}" if snippet else "")
#         )

#     if not lines:
#         return f"No Gramps wiki pages found for '{query}'."
#     return f"Gramps wiki results for '{query}':\n\n" + "\n\n".join(lines)
