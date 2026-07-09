#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025      Doug Blank
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

"""
Generates a block of plain-annotation Python source (a "stub preamble") that
jedi can use to statically infer the row type of a DSL generator function,
e.g. `for person in people(): person.primary_name.first_name`.

jedi's static engine reads class bodies, it never runs our DataDict2.__dir__
override, so a live DataDict2 instance is not enough for this case (there is
no instance until the script actually runs). Instead we derive the field
names straight from Gramps' own JSON schema (cls.get_schema(), present on
every gramps.gen.lib class) and render lightweight classes carrying only
type annotations -- no bodies, nothing is ever executed.

This module has no GTK dependency, only gramps.gen.lib, so it can be
developed and tested without a running Gramps/GTK environment.
"""

import re

from gramps.gen.lib import (
    Citation,
    Event,
    Family,
    Media,
    Note,
    Person,
    Place,
    Repository,
    Source,
)

# The DSL row types generators/active_* names are bound to in
# GrampyScript.execute_code().
ROOT_CLASSES = [Person, Family, Event, Place, Repository, Source, Citation, Note, Media]

# generator function name -> row type, mirrors the DSL bindings in
# GrampyScript.execute_code() (people/families/notes/...).
GENERATOR_ROW_TYPES = {
    "people": "Person",
    "families": "Family",
    "notes": "Note",
    "events": "Event",
    "repositories": "Repository",
    "citations": "Citation",
    "sources": "Source",
    "media": "Media",
    "places": "Place",
}

# active_* name -> row type, mirrors the active_* bindings in
# GrampyScript.execute_code(). These are declared as plain module-level
# annotations (no value), which is enough for jedi to resolve attribute
# chains statically. That matters here: a *live* template DataDict2
# instance would require jedi to actually call DataDict2's computed
# @property methods (father, birth, ...) to see what they return, which
# executes real code (SimpleAccess lookups) and, for a blank template
# with nothing to find, yields no completions at all past that point.
# The stub sidesteps both problems -- nothing is ever executed, and the
# field list comes from the schema regardless of what data exists.
ACTIVE_VARIABLES = {
    "active_person": "Person",
    "active_family": "Family",
    "active_event": "Event",
    "active_place": "Place",
    "active_repository": "Repository",
    "active_source": "Source",
    "active_citation": "Citation",
    "active_note": "Note",
    "active_media": "Media",
}

# selected()/filtered()/custom_filter() in execute_code() all take a
# table-name string argument that picks the row type at runtime (e.g.
# selected("Family")). jedi 0.19 does not discriminate typing.overload by
# a Literal argument value -- verified empirically it merges every
# overload's return fields regardless of which literal was passed, and
# regardless of overload declaration order. So rather than rely on that,
# these are typed as returning the union of every row type: less precise
# than the argument deserves, but strictly more useful than no annotation
# at all (which is what these had before).
TABLE_FUNCTIONS = {
    "selected": ["table_name: str"],
    "filtered": ["table_name: str"],
    "custom_filter": ["name: str", 'namespace: str = "Person"'],
}

# Other top-level DSL callables bound in execute_code() (GrampyScript.py):
# real functions/bound methods with side effects (printing a row, opening/
# closing a transaction, drawing a chart, deleting a record) rather than
# something whose return value ever gets chained. None of these need row-type
# inference, just enough of a signature for jedi to offer them as completions
# and to know their parameters -- hence "-> None" rather than being folded
# into TABLE_FUNCTIONS.
VOID_FUNCTIONS = {
    "row": ["*args"],
    "columns": ["*column_names"],
    "begin_changes": ['message: str = ""'],
    "end_changes": [],
    "delete": ["obj"],
    "chart": ["type", "data", "count: int = 20", "**kwargs"],
}

# back_references(_recursively) can resolve to any primary object type at
# runtime (datadict2.py looks up the handle's own table), so -- same trick as
# TABLE_FUNCTIONS above -- type them as the union of every row type rather
# than "object": jedi merges every union member's attributes, which is more
# useful than no completions at all past a plain "object".
_ALL_ROOT = set(GENERATOR_ROW_TYPES.values())
_BACK_REFERENCE_TYPE = 'list[Union[%s]]' % ", ".join('"%s"' % name for name in sorted(_ALL_ROOT))

_PERSON = {"Person"}
_PERSON_FAMILY = {"Person", "Family"}

# DataDict2's computed @property names (datadict2.py): type_annotation plus
# which root row types the property is actually valid on, derived from what
# each property's own code requires -- a SimpleAccess call that asserts its
# argument type (e.g. sa.gender, sa.spouse: Person only), or a raw dict field
# that only some schemas have (e.g. `place` needs Event.place, `source` needs
# Citation.source_handle). Layering a property onto a type it doesn't apply
# to would offer a completion that's either silently useless or -- like the
# old `gender`-on-non-Person -- raises at runtime.
COMPUTED_PROPERTIES = {
    "gender": ("str", _PERSON),
    "age": ("Span", _PERSON),
    "birth": ("Event", _PERSON),
    "death": ("Event", _PERSON),
    "place": ("Place", {"Event"}),
    "parents": ('list["Person"]', _PERSON_FAMILY),
    "father": ("Person", _PERSON_FAMILY),
    "mother": ("Person", _PERSON_FAMILY),
    "spouse": ("Person", _PERSON),
    "source": ("Source", {"Citation"}),
    "families": ('list["Family"]', _PERSON),
    "parent_families": ('list["Family"]', _PERSON),
    "children": ('list["Person"]', _PERSON_FAMILY),
    "notes": ('list["Note"]', _ALL_ROOT - {"Note"}),
    "tags": ('list["Tag"]', _ALL_ROOT),
    "citations": ('list["Citation"]', {"Person", "Family", "Event", "Place", "Media"}),
    "media": ('list["MediaRef"]', {"Person", "Family", "Event", "Place", "Source", "Citation"}),
    "events": ('list["Event"]', _PERSON_FAMILY),
    "attributes": ('list["Attribute"]', {"Person", "Family", "Event", "Source", "Citation", "Media"}),
    "addresses": ('list["Address"]', {"Person", "Repository"}),
    "lds_ords": ('list["LdsOrdinance"]', _PERSON_FAMILY),
    "references": ('list["PersonRef"]', _PERSON),
    "back_references": (_BACK_REFERENCE_TYPE, _ALL_ROOT),
    "back_references_recursively": (_BACK_REFERENCE_TYPE, _ALL_ROOT),
    "name": ("Name", _PERSON),
    "surname": ("Surname", _PERSON),
    "names": ('list["Name"]', _PERSON),
}

# `reference` (datadict2.py) isn't valid on any root row type -- it reads
# `self.ref`, a handle that exists only on the nested *Ref wrapper types
# (mirrors datadict2.REFERENCE_TABLES). Sanitized schema class name -> the
# row type its `ref` handle points into.
REFERENCE_TARGET_TYPES = {
    "ChildReference": "Person",
    "EventReference": "Event",
    "MediaRef": "Media",
    "PersonRef": "Person",
    "PlaceRef": "Place",
    "RepositoryRef": "Repository",
}

_SCALAR_TYPES = {"string": "str", "integer": "int", "boolean": "bool", "number": "float"}


def _sanitize(title):
    """Turn a Gramps schema title like "Event reference" into a valid
    Python identifier like "EventReference"."""
    return "".join(word.capitalize() for word in re.findall(r"[A-Za-z0-9]+", title))


def _pytype(schema, registry):
    type_ = schema.get("type")
    if isinstance(type_, list):
        return "object"
    if type_ == "object" and "properties" in schema:
        _walk(schema, registry)
        return _sanitize(schema["title"])
    if type_ == "array":
        items = schema.get("items")
        if isinstance(items, dict) and items.get("type") == "object" and "properties" in items:
            _walk(items, registry)
            return 'list["%s"]' % _sanitize(items["title"])
        return "list"
    return _SCALAR_TYPES.get(type_, "object")


def _walk(schema, registry):
    title = schema.get("title")
    if not title:
        return
    name = _sanitize(title)
    if name in registry:
        return
    registry[name] = {}  # reserve first, to break reference cycles
    fields = {}
    for field_name, sub in schema.get("properties", {}).items():
        if field_name == "_class":
            continue
        fields[field_name] = _pytype(sub, registry)
    registry[name] = fields


def build_registry(root_classes=ROOT_CLASSES):
    """
    Return {sanitized_class_name: {field_name: type_annotation}} for every
    type reachable from `root_classes` via Gramps' own get_schema(). Each
    entry in COMPUTED_PROPERTIES is layered only onto the root row types it
    lists as valid (matching real attribute lookup order: properties shadow
    raw dict keys) -- nested structural types (Name, Attribute, ...) get
    schema fields only. `reference` is layered separately, onto the nested
    *Ref types listed in REFERENCE_TARGET_TYPES, since that's what it's
    actually valid on.
    """
    registry = {}
    for cls in root_classes:
        _walk(cls.get_schema(), registry)
    for class_name, fields in registry.items():
        if class_name in _ALL_ROOT:
            for prop_name, (type_, valid_for) in COMPUTED_PROPERTIES.items():
                if class_name in valid_for:
                    fields[prop_name] = type_
        target = REFERENCE_TARGET_TYPES.get(class_name)
        if target is not None:
            fields["reference"] = target
    return registry


def render_stub_source(
    registry,
    generator_row_types=GENERATOR_ROW_TYPES,
    table_functions=TABLE_FUNCTIONS,
    active_variables=ACTIVE_VARIABLES,
    void_functions=VOID_FUNCTIONS,
):
    """
    Render `registry` plus DSL generator function signatures and active_*
    variable annotations as a block of Python source usable as a jedi
    completion preamble. No class or function body has real logic, only
    annotations -- this text is only ever fed to jedi for static
    analysis, never executed.
    """
    lines = [
        "from __future__ import annotations",
        "from typing import Iterator, Union",
        "from gramps.gen.lib.date import Span",
        "",
    ]
    for name in sorted(registry):
        lines.append("class %s:" % name)
        fields = registry[name]
        if not fields:
            lines.append("    pass")
        else:
            for field_name, type_ in fields.items():
                lines.append("    %s: %s" % (field_name, type_))
        lines.append("")
    for func_name, row_type in generator_row_types.items():
        lines.append("def %s() -> Iterator[%s]: ..." % (func_name, row_type))
    if table_functions:
        row_union = "Union[%s]" % ", ".join(sorted(set(generator_row_types.values())))
        for func_name, params in table_functions.items():
            lines.append(
                "def %s(%s) -> Iterator[%s]: ..." % (func_name, ", ".join(params), row_union)
            )
    for func_name, params in void_functions.items():
        lines.append("def %s(%s) -> None: ..." % (func_name, ", ".join(params)))
    lines.append("")
    for var_name, row_type in active_variables.items():
        lines.append("%s: %s" % (var_name, row_type))
    lines.append("")
    return "\n".join(lines)


def build_stub_source():
    """Convenience: build the registry and render it in one call."""
    return render_stub_source(build_registry())
