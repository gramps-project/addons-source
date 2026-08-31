#
# gramps-object-query-language - Object query language and SQL compiler for Gramps data
#
# Copyright (C) 2026      Douglas Blank
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

"""A small, closed query AST and SQL compiler for fast object queries.

This is not a general query language, not GraphQL, and not a raw-SQL
passthrough. Only `where` and `order_by` have tree structure; `select`,
`limit`, and `after` stay flat. Every column name is checked against a
fixed per-type whitelist (`ObjectTypeSpec.columns`, derived from the
secondary columns already flattened server-side for that object's table)
before the compiler ever touches it, and values are always bound as `?`
parameters -- there is no path from client input to a raw SQL string.

This module is pure and does no database access, so it is unit-testable
without a running server. Keyset pagination (`Query.after`) expects the
*resolved* sort-column values for the cursor row, not just a handle --
resolving a client-supplied handle into that tuple (one extra lookup) is
the caller's job; see `after_columns()`.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

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
    Tag,
)
from gramps.gen.lib.tableobj import TableObject


@dataclass(frozen=True)
class ObjectTypeSpec:
    """Table + whitelist for one Gramps object type's flat secondary columns,
    plus the Gramps class itself, whose `get_schema()` describes the *JSON*
    side of the same object (see `walk_schema`).

    `cls` is what makes a `JsonPath` checkable rather than trusted: the
    flat columns are whitelisted by `columns`, and everything reachable
    inside `json_data` is whitelisted by the class's own JSON Schema.
    """

    table: str
    columns: frozenset[str]
    text_columns: frozenset[str]
    cls: type[TableObject]


def _spec_for(
    cls: type[TableObject], extra_columns: frozenset[str] = frozenset()
) -> ObjectTypeSpec:
    """Build an `ObjectTypeSpec` from a Gramps object class's secondary fields.

    Kept in sync with core rather than hardcoded, since this *is* the set of
    columns that exist as real SQL columns on the table. `text_columns` (the
    subset eligible for a locale `COLLATE` clause -- see `compile_query`) is
    derived the same way: every `extra_columns` entry is text today
    (`given_name`/`surname`/`enclosed_by`), and `get_secondary_fields()`
    already tags each field's SQL type.
    """
    fields = list(cls.get_secondary_fields())
    columns = frozenset(field for field, _, _ in fields) | extra_columns
    text_columns = (
        frozenset(field for field, schema_type, _ in fields if schema_type == "string")
        | extra_columns
    )
    return ObjectTypeSpec(
        table=cls.__name__.lower(),
        columns=columns,
        text_columns=text_columns,
        cls=cls,
    )


# One spec per object type, each wired to a `.../query/` endpoint (see
# `resources/object_query.py`).
PERSON = _spec_for(Person, extra_columns=frozenset({"given_name", "surname"}))
FAMILY = _spec_for(Family)
EVENT = _spec_for(Event)
PLACE = _spec_for(Place, extra_columns=frozenset({"enclosed_by"}))
REPOSITORY = _spec_for(Repository)
SOURCE = _spec_for(Source)
CITATION = _spec_for(Citation)
MEDIA = _spec_for(Media)
NOTE = _spec_for(Note)
TAG = _spec_for(Tag)


# --- JSON schema: whitelisting the `json_data` side --------------------------


#: Fields Gramps *serializes* into `json_data` but omits from the matching
#: class's `get_schema()`. Verified against Gramps 6.0.8 by round-tripping a
#: real instance of all 45 schema-carrying classes in `gramps.gen.lib`
#: against its own schema -- these three were the only mismatches, and each
#: is a genuine, queryable stored field, not a serialization artifact.
#:
#: Without this table a path like `birth.date.format` -- real data, present
#: in every serialized `Date` -- would be rejected as unknown. The test
#: `test_schema_gaps_are_still_gaps` re-derives this set from live Gramps
#: and fails if a gap closes upstream (or a new one opens), so this can't
#: quietly rot into a stale hardcoded list.
_SCHEMA_GAPS: dict = {
    "Date": {"format": {"type": ["integer", "null"], "title": "Format"}},
    "Family": {"complete": {"type": "integer", "title": "Complete"}},
    "Media": {"thumb": {"type": ["string", "null"], "title": "Thumbnail"}},
}


def _schema_properties(schema: dict) -> dict:
    """`schema`'s own properties, plus any `_SCHEMA_GAPS` entries for the
    class it describes. Keyed off the schema's `title`, which is how a
    nested schema node names its class (`{"type": "object", "title":
    "Date", ...}`) -- there's no class reference to follow at that depth.
    """
    properties = dict(schema.get("properties", {}))
    properties.update(_SCHEMA_GAPS.get(schema.get("title", ""), {}))
    return properties


def _describe_schema(schema: dict) -> str:
    return schema.get("title") or schema.get("type") or "value"


def walk_schema(spec: ObjectTypeSpec, segments: Sequence[Union[str, int]]) -> dict:
    """Walk `segments` through `spec`'s Gramps JSON Schema, returning the
    schema node for the value the path lands on. Raises `QueryError` -- with
    the field names that *would* have worked -- if the path doesn't exist.

    This is what makes a `JsonPath` a checked reference rather than a
    hopeful one. `json_data`'s contents are not arbitrary: every Gramps
    primary object class publishes a complete, recursive `get_schema()`
    (no `$ref`s, fully inlined), so `primary_name.surname_list[0].surname`
    can be verified statically, exactly like a flat column name is verified
    against `spec.columns`. A path that doesn't exist is a mistake, and
    saying so at compile time beats returning `NULL` for every row.

    A string segment indexes an object's properties; an integer segment
    indexes an array's `items`. Mismatches (a key into a scalar, an index
    into an object) are errors too, not just unknown names.
    """
    schema = spec.cls.get_schema()
    walked: List[str] = []
    for segment in segments:
        if isinstance(segment, int):
            if schema.get("type") != "array":
                raise QueryError(
                    f"{'.'.join(walked) or spec.table!r} is "
                    f"{_describe_schema(schema)}, not a list -- "
                    f"[{segment}] doesn't apply to it"
                )
            schema = schema.get("items", {})
            walked.append(f"[{segment}]")
            continue
        properties = _schema_properties(schema)
        if not properties:
            raise QueryError(
                f"{'.'.join(walked) or spec.table!r} is "
                f"{_describe_schema(schema)}, which has no fields -- "
                f"{segment!r} doesn't apply to it"
            )
        if segment not in properties:
            known = sorted(name for name in properties if not name.startswith("_"))
            raise QueryError(
                f"unknown field {segment!r} on "
                f"{_describe_schema(schema)} -- known fields: "
                f"{', '.join(known)}"
            )
        schema = properties[segment]
        walked.append(segment)
    return schema


def path_value_type(spec: ObjectTypeSpec, segments: Sequence[Union[str, int]]) -> Any:
    """The JSON type a path resolves to (`"string"`, `"integer"`, `"object"`,
    `"array"`, or a list of them for a nullable field), or `None` if the
    schema doesn't say.

    Callers use this to know a value's shape *before* running the query --
    in particular whether it's a composite (`"object"`/`"array"`), which is
    the case a SQLite caller has to JSON-decode on the way back out, since
    `json_extract` hands those back as JSON text while PostgreSQL's `jsonb`
    hands back a parsed value.
    """
    return walk_schema(spec, segments).get("type")


def ref_value_type(spec: ObjectTypeSpec, ref: "ColumnRef") -> Any:
    """The JSON type a whole `ColumnRef` lands on, following a
    `RelatedObject` chain into its target type's schema.

    `None` for a flat column: those are real SQL columns whose type the
    database already knows, so nothing here needs to say it.
    """
    if isinstance(ref, RelatedObject):
        return ref_value_type(ref.target, ref.field)
    if isinstance(ref, JsonPath):
        return path_value_type(spec, ref.segments)
    if isinstance(ref, CollectionCount):
        return "integer"
    if isinstance(ref, WholeJsonData):
        return "object"
    return None


def is_composite_type(value_type: Any) -> bool:
    """Does `value_type` (from `path_value_type`) denote an object/array --
    a value that arrives JSON-encoded from SQLite and parsed from
    PostgreSQL? A nullable field's type is a list, hence the membership
    test rather than an equality check.
    """
    if isinstance(value_type, list):
        return any(item in ("object", "array") for item in value_type)
    return value_type in ("object", "array")


class QueryError(ValueError):
    """Raised when a query references an unknown column or is malformed."""


def _check_column(column: str, whitelist: frozenset[str]) -> None:
    if column not in whitelist:
        raise QueryError(f"unknown or disallowed column: {column!r}")


# Column names that collide with reserved SQL words -- currently just
# `Media.desc` (PostgreSQL reserves DESC; SQLite doesn't). Mirrors
# addons-source's `PostgreSQL`/`SharedPostgreSQL` `_quote_column()` list (see
# PLAN grounding notes); remove once gramps core PR #2178 makes this
# core-provided instead of addon- and caller-side.
_RESERVED_SQL_WORDS = frozenset({"desc", "order", "where", "select"})

# PostgreSQL-only physical-column-name overrides, keyed by logical column
# name (the name `get_secondary_fields()` uses, same as every other
# backend). Existing (and newly created -- see shareddbapi.py's own
# `_quote_column()`) `SharedPostgreSQL` databases physically name these
# columns this way: legacy artifacts of that addon's *former*
# `Connection.execute()`, which used to blindly string-replace
# "desc" -> "desc_" on every query it ran, not just its own -- so a plain,
# unquoted logical name like `description` used to come out the other end
# already corrected to the real physical `desc_ription`, no override
# needed here.
#
# addons-source PR #1001 removed that blind rewrite (rightly -- it
# corrupted any identifier containing "desc" as a substring) in favor of a
# `_quote_column()` used only inside the addon's own generated SQL
# (schema creation, its `ORDER BY`/`UPDATE` paths). It was never wired up
# to also cover SQL built by an external caller like this module, so the
# free auto-correction this compiler used to (silently, fragilely) depend
# on is gone: confirmed live post-#1001, a plain `description`/`desc`
# reference now 500s with `psycopg2.errors.UndefinedColumn` instead of
# reaching the real column. This override table replaces that dependency
# with an explicit one, owned here instead of incidentally supplied by a
# side effect two repos away.
#
# SQLite never had this hack -- its columns are named exactly like every
# other backend's logical name, so nothing is mapped for
# `Dialect.SQLITE`/no dialect.
_POSTGRESQL_PHYSICAL_COLUMN_OVERRIDES: dict[str, str] = {
    "desc": "desc_",
    "description": "desc_ription",
}


def _quote_column(column: str, dialect: Optional["Dialect"] = None) -> str:
    """Render a column identifier for the given dialect.

    PostgreSQL: a column in `_POSTGRESQL_PHYSICAL_COLUMN_OVERRIDES` is
    rendered as its real physical name (see that dict's note); anything
    else that collides with a reserved SQL word is double-quoted.

    SQLite (or no dialect given): always the bare logical name, quoted only
    if it collides with a reserved SQL word -- matching prior output
    exactly for every caller that doesn't pass a dialect.
    """
    if dialect == Dialect.POSTGRESQL and column in _POSTGRESQL_PHYSICAL_COLUMN_OVERRIDES:
        return _POSTGRESQL_PHYSICAL_COLUMN_OVERRIDES[column]
    return f'"{column}"' if column in _RESERVED_SQL_WORDS else column


class Dialect(str, enum.Enum):
    """SQL dialect for backend-specific rendering.

    `JsonPath` is the first thing this compiler emits that needs to know
    which backend it's talking to -- everything else (`?`-parameterized
    comparisons, `AND`/`OR`, keyset seek expressions, `COLLATE`) is
    dialect-neutral SQL that already works unchanged on both backends.
    """

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass(frozen=True)
class ColumnIndex:
    """A `JsonPath` segment whose integer value comes from another column
    on the *current* row, not a compile-time literal -- e.g.
    `event_ref_list[N]` where `N` is this row's `birth_ref_index`. Only
    meaningful inside a `RelatedObject.handle_ref` (see there). `-1` means
    "no such entry" by Gramps' own convention for `birth_ref_index`/
    `death_ref_index`, so rendering code guards this column with `>= 0` --
    required, not defensive: confirmed live that PostgreSQL's `->`
    operator treats a negative array index as "count from the end" rather
    than invalid -- without the guard, a row with no such entry but
    *something else* in the list would silently resolve to that unrelated
    entry.
    """

    column: str


@dataclass(frozen=True)
class JsonPath:
    """A path into a JSON-blob secondary column (default: `json_data`).

    Whitelisted, like a plain column name -- just against a different
    list. `json_data`'s content is *not* arbitrary: every Gramps class
    publishes a complete recursive JSON Schema, so `resolve_column_path`
    checks each path against it (`walk_schema`) before building a
    `JsonPath` at all. A path this class can be constructed with directly,
    bypassing that resolver, is trusted the way any hand-built AST node is.

    Two further guarantees hold regardless of where the path came from:
    every segment is individually type-checked (`str` keys, non-bool `int`
    array indices, or a `ColumnIndex` -- see there), and `str`/`int`
    segments are always bound as query parameters, never interpolated into
    SQL text -- see `_render_json_path`. (A `ColumnIndex` segment is inherently a raw SQL
    column reference, not a bindable value -- see `_render_handle_ref`,
    the only place a `JsonPath` containing one is ever rendered; its
    `column` always comes from the fixed internal `_RELATIONSHIPS`
    registry, never from parsed user input, so this is safe.)

    Usable in `order_by`/keyset pagination as well as `select`/`where`.
    That needed a static type for the value, which the class's own JSON
    Schema now supplies (`path_value_type`): PostgreSQL casts a numeric
    path so it doesn't sort lexicographically, and `COLLATE` is applied
    only when the schema says the value is text -- `text_columns` can't
    answer that for a path, which is why sorting on one was previously out
    of scope. No index backs the extraction, so this is a real scan.
    """

    segments: Tuple[Union[str, int, ColumnIndex], ...]
    base_column: str = "json_data"

    def __post_init__(self) -> None:
        if not self.segments:
            raise QueryError("JsonPath requires at least one segment")
        for segment in self.segments:
            if isinstance(segment, ColumnIndex):
                continue
            if isinstance(segment, bool) or not isinstance(segment, (str, int)):
                raise QueryError(f"invalid JsonPath segment: {segment!r}")


@dataclass(frozen=True)
class WholeJsonData:
    """The entire JSON-blob secondary column, selected whole -- spelled
    `"."` as a path string (`resolve_ref_string(spec, ".")`), the one path
    text that isn't a valid dotted/bracketed `JsonPath` spelling.

    A separate class from `JsonPath` rather than an empty-segments
    `JsonPath(())`, deliberately -- `JsonPath` requires at least one
    segment (`test_jsonpath_requires_at_least_one_segment`) precisely so an
    empty/malformed path stays a caller error there; giving "the whole
    object, on purpose" its own type keeps that guarantee intact instead of
    overloading the same shape to mean two different things depending on
    how it was reached.

    Renders as a bare reference to `base_column` (see `_render_column`) --
    `json_data` is stored as JSON-encoded TEXT already on both backends
    (see `JsonPath`'s docstring), so the whole blob is exactly what
    `SELECT json_data` returns; no extraction function needed the way a
    `JsonPath` needs `json_extract`/`jsonb_extract_path_text`.
    """

    base_column: str = "json_data"


@dataclass(frozen=True)
class RelatedObject:
    """A field reached by following a relationship from the current row to
    another table -- a `Family`'s father (-> `Person`), a `Person`'s birth
    event (-> `Event`), an `Event`'s place (-> `Place`), and so on.
    Resolved via a *correlated scalar subquery*, not a `JOIN`: each
    `RelatedObject`'s subquery is a fully independent SQL scope with its
    own `FROM <target.table>`, correlated back to whatever row it's
    reached from by that table's own (never aliased) name -- confirmed
    live this composes correctly at any depth: sibling subqueries hitting
    the same table (father vs. mother, both `FROM person`) don't collide,
    and chains (nested subqueries, for `birth.place.title`-style paths)
    correlate correctly across levels regardless of nesting -- see
    `_render_related_object`.

    `name`: the relationship's name as used in a path (`"birth"`,
        `"father"`, ...) -- kept for error messages and deriving a default
        response key (`"birth.date.sortval"`); not used by the SQL itself.
    `target`: the `ObjectTypeSpec` of the related table.
    `handle_ref`: how to find the related row's handle on the row this
        `RelatedObject` is reached from -- a plain column name for a
        direct foreign key (`"father_handle"`), or a `JsonPath` with
        exactly one `ColumnIndex` segment for a dynamic, per-row index
        (`event_ref_list[<ref_index_column>].ref`).
    `field`: what to pull from the related row once found -- a plain
        (whitelisted) column name, a `JsonPath` into its `json_data`, or
        another `RelatedObject` to keep chaining.

    Usable in `order_by`/keyset pagination too. A per-row dynamic
    `handle_ref` is no obstacle: the sort and seek predicates re-render the
    whole correlated subquery wherever the value is needed, rather than
    assuming it lives in the base table. Correct, but a subquery per row
    per comparison -- the slowest thing this compiler emits.
    """

    name: str
    target: ObjectTypeSpec
    handle_ref: ColumnRef
    field: ColumnRef


# Registry of relationship roots, keyed by the *current* table -- the only
# thing that varies per relationship is which table it targets and how to
# find the related row's handle; what to extract from that row (`field`) is
# supplied by whatever's left of the path once the relationship name is
# consumed (see `resolve_column_path`). Adding a new relationship (e.g. a
# Citation's source) is one registry entry, not new rendering code.
_RELATIONSHIPS: dict[str, dict[str, Tuple[ObjectTypeSpec, ColumnRef]]] = {
    PERSON.table: {
        "birth": (
            EVENT,
            JsonPath(("event_ref_list", ColumnIndex("birth_ref_index"), "ref")),
        ),
        "death": (
            EVENT,
            JsonPath(("event_ref_list", ColumnIndex("death_ref_index"), "ref")),
        ),
    },
    FAMILY.table: {
        "father": (PERSON, "father_handle"),
        "mother": (PERSON, "mother_handle"),
    },
    EVENT.table: {
        "place": (PLACE, "place"),
    },
    CITATION.table: {
        "source": (SOURCE, "source_handle"),
    },
    PLACE.table: {
        # Self-referencing (Place -> Place), the first entry in this row's
        # own placeref_list -- a real, indexed flat column in Gramps' own
        # DBAPI schema (`enclosed_by VARCHAR(50)`), already exposed via
        # PLACE's extra_columns but never registered as a relationship
        # until now. Distinct from the `enclosing_places` Collection
        # (one-to-many, the full placeref_list with its date ranges) --
        # this is just the one, denormalized "primary enclosing place"
        # handle Gramps' own backend maintains for fast lookups.
        "enclosed_by": (PLACE, "enclosed_by"),
    },
}


@dataclass(frozen=True)
class Collection:
    """A one-to-many relationship -- a list of handles (or handle-bearing ref
    objects) reached from the current row, e.g. a `Family`'s children.

    Unlike `RelatedObject`, never appears as a dotted-path segment (`children.
    surname` would be ambiguous -- which child?) -- only as `Exists`'s target,
    looked up via `resolve_collection`, a separate namespace from
    `_RELATIONSHIPS` on purpose.

    `list_path`: where the list of related items lives in the current row's
        `json_data` (always a single top-level key today, e.g.
        `child_ref_list`, `note_list`).
    `ref_field`: the sub-key that holds each item's handle, for a list of ref
        objects (`"ref"`, for `ChildRef`/`EventRef`/... entries) -- `None`
        for a list that's already plain handle strings (`note_list`,
        `tag_list`).
    """

    name: str
    target: ObjectTypeSpec
    list_path: JsonPath
    ref_field: Optional[str]


@dataclass(frozen=True)
class CollectionCount:
    """How many rows in a `Collection` match an optional `condition` -- the
    value-returning counterpart to `Exists` (a boolean). `count(children) > 2`
    compiles to an ordinary `Gt(CollectionCount(children, None), 2)` -- no new
    `Comparison` subclass needed, unlike `Exists`, which has to be its own
    top-level boolean AST node since a bare `exists(...)` *is* the condition.

    `condition=None` means "count every related row" -- `count(children)`,
    not narrowed by any field of the children themselves.

    Shares `Exists`'s subquery body (`_collection_subquery_body`) verbatim,
    just wrapped as `(SELECT COUNT(*) FROM ...)` instead of
    `EXISTS (SELECT 1 FROM ...)` -- see `_render_collection_count`.
    """

    collection: Collection
    condition: Optional[Any] = None


def _generic_collections(
    *, notes: bool = False, citations: bool = False, media: bool = False, tags: bool = False
) -> dict[str, Collection]:
    """The subset of `note_list`/`citation_list`/`media_list`/`tag_list`
    a given object type actually has -- these four recur across most of the
    ten primary types (every type inheriting `NoteBase`/`CitationBase`/
    `MediaBase`/`TagBase` in Gramps core), but not uniformly: e.g. `Source`
    has no `citation_list` (a source doesn't cite other citations), and
    `Repository` has neither `citation_list` nor `media_list`. Each caller
    below passes only the flags matching what that type's Gramps class
    actually inherits (verified against `gramps/gen/lib/*.py`, not guessed).

    `note_list`/`citation_list`/`tag_list` are flat handle lists
    (`ref_field=None`); `media_list` is a list of `MediaRef` objects
    (`ref_field="ref"`) -- the two `Collection` shapes `children`/`notes`
    already proved out.
    """
    entries: dict[str, Collection] = {}
    if notes:
        entries["notes"] = Collection("notes", NOTE, JsonPath(("note_list",)), None)
    if citations:
        entries["citations"] = Collection(
            "citations", CITATION, JsonPath(("citation_list",)), None
        )
    if media:
        entries["media"] = Collection("media", MEDIA, JsonPath(("media_list",)), "ref")
    if tags:
        entries["tags"] = Collection("tags", TAG, JsonPath(("tag_list",)), None)
    return entries


# Registry of one-to-many collection roots, keyed by the *current* table --
# mirrors `_RELATIONSHIPS`'s shape, but for `EXISTS`-style membership tests
# (see `Exists`) rather than a single correlated scalar subquery.
#
# Every entry here is one of exactly two shapes (`children`/`notes` proved
# both out first): a ref-object list needing `.ref` extraction
# (`ref_field="ref"` -- `child_ref_list`, `event_ref_list`, `person_ref_list`,
# `media_list`, `placeref_list`, `reporef_list`), or a flat handle list that's
# already the handle itself (`ref_field=None` -- `note_list`,
# `citation_list`, `tag_list`, `family_list`, `parent_family_list`). Adding
# each was confirmed against the real Gramps object model
# (`gramps/gen/lib/*.py`'s base classes and field definitions), not assumed
# from naming alone.
_COLLECTIONS: dict[str, dict[str, Collection]] = {
    PERSON.table: {
        **_generic_collections(notes=True, citations=True, media=True, tags=True),
        "families": Collection("families", FAMILY, JsonPath(("family_list",)), None),
        "parent_families": Collection(
            "parent_families", FAMILY, JsonPath(("parent_family_list",)), None
        ),
        "associations": Collection(
            "associations", PERSON, JsonPath(("person_ref_list",)), "ref"
        ),
        "events": Collection("events", EVENT, JsonPath(("event_ref_list",)), "ref"),
    },
    FAMILY.table: {
        "children": Collection("children", PERSON, JsonPath(("child_ref_list",)), "ref"),
        **_generic_collections(notes=True, citations=True, media=True, tags=True),
        "events": Collection("events", EVENT, JsonPath(("event_ref_list",)), "ref"),
    },
    EVENT.table: {
        **_generic_collections(notes=True, citations=True, media=True, tags=True),
    },
    PLACE.table: {
        **_generic_collections(notes=True, citations=True, media=True, tags=True),
        "enclosing_places": Collection(
            "enclosing_places", PLACE, JsonPath(("placeref_list",)), "ref"
        ),
    },
    SOURCE.table: {
        **_generic_collections(notes=True, media=True, tags=True),
        "repositories": Collection(
            "repositories", REPOSITORY, JsonPath(("reporef_list",)), "ref"
        ),
    },
    CITATION.table: {
        **_generic_collections(notes=True, media=True, tags=True),
    },
    REPOSITORY.table: {
        **_generic_collections(notes=True, tags=True),
    },
    MEDIA.table: {
        **_generic_collections(notes=True, citations=True, tags=True),
    },
    NOTE.table: {
        **_generic_collections(tags=True),
    },
}


def _check_no_collection_relationship_name_collisions() -> None:
    for table, collections in _COLLECTIONS.items():
        overlap = set(collections) & set(_RELATIONSHIPS.get(table, {}))
        if overlap:
            raise QueryError(
                f"name collides between a relationship and a collection on "
                f"{table!r}: {sorted(overlap)}"
            )


_check_no_collection_relationship_name_collisions()


def resolve_collection(spec: ObjectTypeSpec, name: str) -> Collection:
    """Look up a `Collection` by name on `spec`'s table -- `exists(...)`'s
    first argument, resolved the same way `resolve_column_path` resolves a
    `_RELATIONSHIPS` name, just from the separate `_COLLECTIONS` namespace.
    """
    collections = _COLLECTIONS.get(spec.table, {})
    if name not in collections:
        raise QueryError(
            f"unknown collection {name!r} on {spec.table!r} "
            f"(known: {', '.join(sorted(collections)) or 'none'})"
        )
    return collections[name]


def resolve_column_path(
    spec: ObjectTypeSpec, segments: Sequence[Union[str, int]]
) -> ColumnRef:
    """Resolve a dotted/indexed path against `spec` into a `ColumnRef`.

    Recursively walks relationship roots (`_RELATIONSHIPS`) as far as the
    path goes -- `birth.date.sortval` consumes `"birth"` as a relationship
    (`Person` -> `Event`), then resolves the remaining `("date", "sortval")`
    against `EVENT`, which isn't a relationship there, so it becomes a
    `JsonPath`. `birth.place.title` keeps going: `"place"` is *also* a
    relationship (`Event` -> `Place`), consumed the same way, leaving just
    `("title",)` to resolve against `PLACE` (a real flat column there).

    `select`/`where`/`where_expr` (`object_query.py`, `query_lang.py`) all
    funnel through this one resolver, so a path means the same thing
    everywhere it's written.

    A relationship name with nothing after it (`segments == ("birth",)`)
    is rejected explicitly -- there's no value to return for "the related
    row itself", only for a field of it.
    """
    if not segments:
        raise QueryError("empty column path")
    head, *rest = segments
    relationships = _RELATIONSHIPS.get(spec.table, {})
    if isinstance(head, str) and head in relationships:
        if not rest:
            raise QueryError(
                f"{head!r} is a relationship on {spec.table!r}, not a value on its "
                f"own -- use {head}.<field>, e.g. {head}.gramps_id"
            )
        target_spec, handle_ref = relationships[head]
        field = resolve_column_path(target_spec, rest)
        return RelatedObject(name=head, target=target_spec, handle_ref=handle_ref, field=field)
    if len(segments) == 1 and isinstance(head, str) and head in spec.columns:
        return head
    # Not a flat column and not a relationship -- so it's a path into
    # `json_data`, checked against the type's own Gramps JSON Schema
    # before it's built (see `walk_schema`). An unknown path is a mistake,
    # and this is the one place every JsonPath-producing surface
    # (`select`, `where`, `where_expr`) funnels through, so checking here
    # covers all of them at once.
    walk_schema(spec, segments)
    return JsonPath(tuple(segments))


_PATH_SEGMENT_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)((?:\[[0-9]+\])*)\Z")
_PATH_INDEX_RE = re.compile(r"\[([0-9]+)\]")


def parse_path_string(text: str) -> Tuple[Union[str, int], ...]:
    """Parse a dotted/bracketed path string into `resolve_column_path`
    segments -- `"primary_name.surname_list[0].surname"` becomes
    `("primary_name", "surname_list", 0, "surname")`.

    The string equivalent of `query_lang.py`'s `_translate_path` (which
    walks a real Python `ast` instead), kept here rather than there because
    `compile_query` itself needs it and `query_lang` imports *this* module,
    not the other way round. The two grammars are deliberately identical,
    so a path means the same thing typed into `select` as typed into
    `where_expr`:

    - segments are separated by `.`, each an identifier
      (`[A-Za-z_][A-Za-z0-9_]*`)
    - a segment may be followed by one or more `[<int>]` subscripts
    - the index must be a non-negative integer literal. Negative indices
      are rejected for parity with `_translate_path` (Python's `ast` makes
      `[-1]` a `UnaryOp`, not the `Constant` it requires) *and* because
      PostgreSQL's `->` reads a negative index as "count from the end"
      while SQLite's JSONPath rejects it outright -- a silently
      dialect-dependent meaning, which is exactly the trap `ColumnIndex`
      already documents guarding against.

    Raises `QueryError` on anything else: this parses raw, untrusted input
    (a client-supplied `select` entry), so a malformed path has to fail
    loudly rather than degrade into a path that quietly matches nothing.
    """
    if not text or not text.strip():
        raise QueryError("empty column path")
    segments: List[Union[str, int]] = []
    for part in text.split("."):
        match = _PATH_SEGMENT_RE.match(part)
        if not match:
            raise QueryError(
                f"invalid path segment {part!r} in {text!r} -- expected a name, "
                f"optionally followed by [<index>]"
            )
        name, subscripts = match.group(1), match.group(2)
        segments.append(name)
        segments.extend(int(index) for index in _PATH_INDEX_RE.findall(subscripts))
    return tuple(segments)


def resolve_ref_string(spec: ObjectTypeSpec, text: str) -> "ColumnRef":
    """Resolve a bare string column reference against `spec`.

    One code path for every spelling: `"gramps_id"`, `"primary_name"`, and
    `"birth.place.title"` all go through `parse_path_string` and then
    `resolve_column_path`, so a string means exactly what the same text
    means in `where_expr` -- a flat column, a schema-checked `JsonPath`, or
    a `RelatedObject` crossing a relationship. There is no special case for
    a single segment: `gendr` is rejected because the Gramps schema has no
    such field, not because of any rule about dots.

    Used for `order_by` and (via `json_column_to_ref`) `where` column
    references too -- `"."` (see `resolve_select_ref_string`) is
    deliberately *not* handled here, so filtering or sorting on the whole
    object stays a `QueryError` (`parse_path_string` rejects `"."` as two
    empty path segments) rather than silently compiling into a comparison
    or `ORDER BY` against a serialized JSON blob.
    """
    return resolve_column_path(spec, parse_path_string(text))


def resolve_select_ref_string(spec: ObjectTypeSpec, text: str) -> "ColumnRef":
    """`resolve_ref_string`, plus `"."` as a `select`-only spelling of "the
    whole `json_data` blob" (`WholeJsonData`) -- not a dotted path at all,
    so it's checked before `parse_path_string` ever sees it (`"."` splits
    into two empty path segments, neither a valid identifier, and would
    otherwise just raise). Used only where a `select` entry string is
    resolved (`compile_query`, `run_query`) -- see `resolve_ref_string`'s
    docstring for why `order_by`/`where` don't get this same case.
    """
    if text == ".":
        return WholeJsonData()
    return resolve_ref_string(spec, text)


def default_ref_key(ref: "ColumnRef") -> str:
    """The canonical response key for a column reference -- the dotted/
    bracketed string that would resolve back to it.

    `primary_name.surname_list[0]` for a plain `JsonPath`, `birth.date.sortval`
    for a `RelatedObject` chain (recursing through `.field`, prefixing each
    hop's `.name`), the name itself for a flat column. Round-trips with
    `resolve_ref_string` for every reference either can express, which is
    what lets a caller spell a `select` entry either way (a path string or
    a resolved ref) and get the same response key for it.

    A `CollectionCount` has no path to derive a name from, so it has no
    default key -- callers must supply one (see `query_lang.parse_select`,
    which requires an explicit alias for `count(...)`).
    """
    if isinstance(ref, str):
        return ref
    if isinstance(ref, FlatColumnRef):
        return ref.name
    if isinstance(ref, RelatedObject):
        return f"{ref.name}.{default_ref_key(ref.field)}"
    if isinstance(ref, WholeJsonData):
        return "."
    if isinstance(ref, JsonPath):
        parts: List[str] = []
        for segment in ref.segments:
            if isinstance(segment, ColumnIndex):
                raise QueryError(
                    "a ColumnIndex path segment has no response-key spelling"
                )
            if isinstance(segment, int):
                parts.append(f"[{segment}]")
            else:
                parts.append(f".{segment}" if parts else str(segment))
        return "".join(parts)
    raise QueryError(f"no default response key for {ref!r} -- supply one explicitly")


@dataclass(frozen=True)
class FlatColumnRef:
    """A flat column referenced as a comparison's *value* -- the right-hand
    side of a field-vs-field comparison whose column happens to be a plain
    (same-table) flat column rather than a `JsonPath`/`RelatedObject`.

    `Comparison.value` (and `Contains.value`) already support a field
    reference on the value side -- but only ever recognize `JsonPath`/
    `RelatedObject` as one (see `Comparison`'s docstring: "a bare string is
    exactly as likely to be a literal value... as a column name, and
    there's no way to tell which was meant"). A flat column resolves to a
    bare `str`, identical in shape to an ordinary string literal -- so
    without this wrapper, "given_name == surname" would silently compile to
    comparing `given_name` against the *literal text* `"surname"`, not the
    two columns against each other. This wraps a flat column specifically
    for that one role, so `is_field_comparison`-style checks can tell it
    apart from a real literal the same way they already can for `JsonPath`/
    `RelatedObject`. Renders identically to a plain column reference --
    `name` is unwrapped and passed straight through wherever a bare `str`
    column already worked (see `_render_column`, `resolve_column_ref`).
    """

    name: str


# A column reference is either a plain (whitelisted) column name, a path
# into one column's JSON content, a field reached via a relationship (see
# `RelatedObject`/`resolve_column_path`), a whole JSON-blob column
# (`WholeJsonData`), or (value-position only, see `FlatColumnRef`) a flat
# column marked as a field rather than a literal -- `field: ColumnRef` on
# `RelatedObject` makes this recursive, so a chain like `birth.place.title`
# is itself a valid `ColumnRef`.
ColumnRef = Union[str, JsonPath, RelatedObject, CollectionCount, FlatColumnRef, WholeJsonData]
SelectRef = ColumnRef


def _require_dialect(dialect: Optional[Dialect], path: JsonPath) -> Dialect:
    if dialect is None:
        raise QueryError(
            f"a dialect is required to compile a JsonPath ({path!r}), but none was given"
        )
    return dialect


def _render_json_path(
    path: JsonPath, dialect: Dialect, value: Any = None
) -> Tuple[str, list]:
    """Render a `JsonPath` into a dialect-specific SQL expression + bound params.

    SQLite: `json_extract(json_data, ?)` with a single bound JSONPath-syntax
    string (`$.primary_name.surname_list[0].surname`). SQLite's `json_extract`
    already returns a properly-typed SQLite value (INTEGER/REAL/TEXT) matching
    the JSON value's own type, so no cast is needed here for correct ordering
    comparisons.

    PostgreSQL: `jsonb_extract_path_text(json_data::jsonb, ?, ?, ...)` with
    one bound parameter per path segment -- `json_data` is stored as `TEXT`
    on both backends (no native `jsonb` column), hence the cast. Confirmed
    live against a real PostgreSQL 16 instance: `jsonb_extract_path_text`
    treats a numeric-looking text segment (e.g. `"0"`) as a JSON array
    index, so integer segments are simply stringified, not cast separately.

    `jsonb_extract_path_text` always returns `TEXT`, though, which is wrong
    for `Lt`/`Gt`/etc. against a numeric or boolean `value` -- PostgreSQL
    compares text lexicographically, not numerically (`'10' < '9'` is true).
    `value` -- the Python value already in hand on the comparison, e.g.
    `Gt(json_path, 5).value` -- picks the cast: `bool` -> `BOOLEAN`, `int`/
    `float` -> `NUMERIC` (via the non-`_text` `jsonb_extract_path` + `CAST`,
    mirroring the pattern in gramps' `SQLiteWithSelect` addon's
    `sql_generator.py`), otherwise `TEXT` as before. This is driven by the
    already-known comparison value rather than a separate static
    type-inference pass.
    """
    if dialect == Dialect.SQLITE:
        jsonpath = "$" + "".join(
            f"[{segment}]" if isinstance(segment, int) else f".{segment}"
            for segment in path.segments
        )
        return f"json_extract({path.base_column}, ?)", [jsonpath]
    if dialect == Dialect.POSTGRESQL:
        placeholders = ", ".join(["?"] * len(path.segments))
        params = [str(segment) for segment in path.segments]
        if isinstance(value, bool):
            extract = f"jsonb_extract_path({path.base_column}::jsonb, {placeholders})"
            return f"CAST({extract} AS BOOLEAN)", params
        if isinstance(value, (int, float)):
            extract = f"jsonb_extract_path({path.base_column}::jsonb, {placeholders})"
            return f"CAST({extract} AS NUMERIC)", params
        return (
            f"jsonb_extract_path_text({path.base_column}::jsonb, {placeholders})",
            params,
        )
    raise QueryError(f"unsupported dialect: {dialect!r}")


def _sqlite_handle_ref_path_sql(
    segments: Sequence[Union[str, int, ColumnIndex]], outer_table: str
) -> str:
    """Build the SQL expression for a JSONPath string used as a `handle_ref`,
    substituting any `ColumnIndex` segment with the live value of that
    column via `||` concatenation, e.g.
    `'$.event_ref_list[' || person.birth_ref_index || '].ref'`. A path with
    no `ColumnIndex` segment collapses to a single literal string, same as
    a normal compile-time-static path.
    """
    fragments: list = []
    literal = "$"
    for segment in segments:
        if isinstance(segment, ColumnIndex):
            literal += "["
            fragments.append(f"'{literal}'")
            fragments.append(f"{outer_table}.{segment.column}")
            literal = "]"
        elif isinstance(segment, int):
            literal += f"[{segment}]"
        else:
            literal += f".{segment}"
    fragments.append(f"'{literal}'")
    return " || ".join(fragments)


def _postgresql_handle_ref_path_sql(
    segments: Sequence[Union[str, int, ColumnIndex]], outer_table: str
) -> str:
    """Build the `->`/`->>` chain for a `handle_ref`, substituting any
    `ColumnIndex` segment with the *unquoted* live value of that column --
    PostgreSQL's `->` operator needs an actual integer (not a quoted
    string) to use its array-index overload rather than its object-key
    overload, confirmed live; a plain `int` literal segment gets the same
    treatment for the same reason.
    """
    expr = f"{outer_table}.json_data::jsonb"
    last_index = len(segments) - 1
    for i, segment in enumerate(segments):
        op = "->>" if i == last_index else "->"
        if isinstance(segment, ColumnIndex):
            expr += f" {op} {outer_table}.{segment.column}"
        elif isinstance(segment, int):
            expr += f" {op} {segment}"
        else:
            expr += f" {op} '{segment}'"
    return expr


def _render_handle_ref(
    handle_ref: ColumnRef, outer_table: str, dialect: Dialect
) -> Tuple[str, Optional[str]]:
    """Render the SQL expression that finds a related row's handle from the
    current row, plus the name of the column to guard with `>= 0` if
    `handle_ref` uses a dynamic `ColumnIndex` segment (`None` for a direct
    foreign key -- a `NULL` handle already fails the equality comparison
    naturally, confirmed live, no guard needed).
    """
    if isinstance(handle_ref, str):
        return f"{outer_table}.{_quote_column(handle_ref, dialect)}", None
    if isinstance(handle_ref, JsonPath):
        index_columns = [
            segment.column
            for segment in handle_ref.segments
            if isinstance(segment, ColumnIndex)
        ]
        if len(index_columns) > 1:
            raise QueryError(
                "a handle reference supports at most one dynamic index segment"
            )
        guard_column = index_columns[0] if index_columns else None
        if dialect == Dialect.SQLITE:
            path_expr = _sqlite_handle_ref_path_sql(handle_ref.segments, outer_table)
            return f"json_extract({outer_table}.json_data, {path_expr})", guard_column
        if dialect == Dialect.POSTGRESQL:
            return (
                _postgresql_handle_ref_path_sql(handle_ref.segments, outer_table),
                guard_column,
            )
        raise QueryError(f"unsupported dialect: {dialect!r}")
    raise QueryError(f"invalid handle reference: {handle_ref!r}")


def _guarded_handle_ref_sql(
    handle_ref: ColumnRef, outer_table: str, dialect: Dialect
) -> str:
    """`_render_handle_ref`'s SQL expression, with the dynamic-index `>= 0`
    guard already applied when needed -- see `_render_related_object`.
    """
    handle_sql, guard_column = _render_handle_ref(handle_ref, outer_table, dialect)
    if guard_column is not None:
        handle_sql = (
            f"CASE WHEN {outer_table}.{guard_column} >= 0 THEN {handle_sql} ELSE NULL END"
        )
    return handle_sql


def _render_related_object(
    related: RelatedObject,
    outer_table: str,
    dialect: Optional[Dialect],
    treeid: Optional[int],
    value: Any = None,
    _depth: int = 0,
) -> Tuple[str, list]:
    """Render a `RelatedObject` as a correlated scalar subquery.

    ```sql
    (SELECT <field extraction> FROM <target.table> AS <target.table>__hop<depth>
     WHERE <target.table>__hop<depth>.handle = <handle_ref, CASE-guarded if dynamic>
       AND <target.table>__hop<depth>.treeid = ?     -- when treeid is given
     LIMIT 1)
    ```

    Not a `JOIN` -- a self-contained SQL scope with its own `FROM`,
    correlated back to `outer_table` by name. Confirmed live this composes
    correctly at any depth: sibling subqueries referencing the same table
    (father vs. mother, both targeting `person`) don't collide with each
    other, and a chain (nested `SELECT`s, for a path like `birth.place.title`)
    correlates correctly across levels -- each `RelatedObject`'s subquery is
    an independent scope regardless of how deep it's nested.

    **Every level is aliased unconditionally** (`_depth` increments by one
    per level of `RelatedObject` chaining), not just when a same-table
    collision is detected -- confirmed *necessary*, not just defensive, for
    a self-referencing relationship (`Place.enclosed_by` -> `Place`, the
    first one registered): without an alias, a nested subquery's own
    `FROM place` shadows any ancestor scope that also happens to be
    `place`, so a bare `place.enclosed_by` reference inside the subquery's
    own `WHERE` resolves to the *subquery's own* row, not the correlated
    ancestor's -- silently making `place.handle = place.enclosed_by` true
    only for a (nonexistent) place that encloses itself, so the whole
    relationship matches nothing, for every row, regardless of real data.
    Confirmed empirically before fixing (`enclosed_by.title == 'Cook
    County'` matched zero rows against a real 3-level place hierarchy where
    it should have matched one) -- the same class of bug as `Collection`
    self-reference (`Person.associations`, see Done above), just one level
    more subtle since `RelatedObject` nests arbitrarily deep rather than
    being a single flat subquery, so a *fixed* alias suffix (which was
    sufficient there) isn't enough here -- two nested self-referencing hops
    (`enclosed_by.enclosed_by`) would still collide with each other under a
    fixed suffix; only a depth-varying one guarantees every level distinct.

    `treeid` scoping applies to *this* subquery's own row, not the outer
    query -- a related row in another tree makes this field come back
    `null`, not exclude the outer row from the results entirely. This
    compiler carries no privacy predicate at all: it only ever runs
    against an unproxied database (see `object_query.py`'s dispatch), so
    there is nothing to guard here that the caller isn't already permitted
    to see, at any depth.

    `value` (a `where`-comparison's right-hand value, `None` for `select`)
    only affects rendering when `field` is a `JsonPath` -- forwarded to
    `_render_json_path` for the same numeric/boolean cast selection
    already used for a plain `JsonPath` column. A `field` that's a plain
    column ignores it (no text-vs-numeric ambiguity for a real column); a
    `field` that's another (chained) `RelatedObject` forwards it one more
    level down to wherever the leaf comparison actually happens.
    """
    if dialect is None:
        raise QueryError(
            f"a dialect is required to compile a relationship path ({related.name!r}), "
            "but none was given"
        )
    target_table = related.target.table
    target_alias = f"{target_table}__hop{_depth}"

    handle_sql = _guarded_handle_ref_sql(related.handle_ref, outer_table, dialect)

    if isinstance(related.field, RelatedObject):
        field_sql, field_params = _render_related_object(
            related.field, target_alias, dialect, treeid, value, _depth=_depth + 1
        )
    elif isinstance(related.field, JsonPath):
        field_sql, field_params = _render_json_path(related.field, dialect, value)
    else:
        _check_column(related.field, related.target.columns)
        field_sql, field_params = _quote_column(related.field, dialect), []

    subquery_where = [f"{target_alias}.handle = ({handle_sql})"]
    where_params: list = []
    if treeid is not None:
        subquery_where.append(f"{target_alias}.treeid = ?")
        where_params.append(treeid)

    subquery = (
        f"(SELECT {field_sql} FROM {target_table} AS {target_alias} "
        f"WHERE {' AND '.join(subquery_where)} LIMIT 1)"
    )
    return subquery, field_params + where_params


def _check_bindings(sql: str, params: Sequence[Any], what: str) -> None:
    """Every `?` in `sql` must have exactly one value in `params`.

    A structural invariant, checked rather than assumed. SQL text and bound
    values are assembled as two separate lists that are matched up by
    position at execution time, so any drift between them is a real class
    of bug -- and one that only *sometimes* announces itself: a count
    mismatch is caught by the driver, but a same-length mis-ordering can
    execute happily and return plausible, wrong rows.

    This can't catch a mis-ordering (both lists still have the same
    length); it catches the drift that causes most of them, at the moment
    it happens, naming the fragment rather than surfacing as the driver's
    context-free "Incorrect number of bindings supplied" later on. The
    semantic half of this guard is the SQL-vs-evaluator parity matrix in
    `test_proxied_query.py`, which re-derives every result a second way.

    Safe as written because no literal `?` is ever emitted into SQL text:
    every value reaches the query as a bound parameter, and the only
    inlined literals are internally-generated JSONPath fragments (see
    `_sqlite_handle_ref_path_sql`).
    """
    expected = sql.count("?")
    if expected != len(params):
        raise QueryError(
            f"internal error: {what} has {expected} placeholder(s) but "
            f"{len(params)} bound value(s) -- SQL: {sql!r} params: {params!r}"
        )


def _render_column(
    column: ColumnRef,
    spec: ObjectTypeSpec,
    dialect: Optional[Dialect],
    value: Any = None,
    treeid: Optional[int] = None,
) -> Tuple[str, list]:
    """Render a column reference (plain name, `JsonPath`, or `RelatedObject`).

    Used for both `SELECT` list entries (no right-hand value to bind,
    `value` stays `None`) and `WHERE` comparisons. `value`, when given, is
    the comparison's right-hand Python value -- used only to pick a
    `JsonPath`/`RelatedObject` cast (see `_render_json_path`/
    `_render_related_object`); ignored for plain column names. `treeid` is
    only used by `RelatedObject`, whose correlated subquery needs its own
    tree-scoping independent of the outer query's.
    """
    if isinstance(column, RelatedObject):
        sql, params = _render_related_object(column, spec.table, dialect, treeid, value)
    elif isinstance(column, JsonPath):
        sql, params = _render_json_path(column, _require_dialect(dialect, column), value)
    elif isinstance(column, CollectionCount):
        sql, params = _render_collection_count(column, spec.table, dialect, treeid)
    elif isinstance(column, WholeJsonData):
        # No extraction function needed -- the column already *is* the
        # whole JSON blob, on both dialects (see `WholeJsonData`'s
        # docstring), so this renders identically regardless of `dialect`.
        sql, params = _quote_column(column.base_column, dialect), []
    else:
        if isinstance(column, FlatColumnRef):
            column = column.name
        _check_column(column, spec.columns)
        sql, params = _quote_column(column, dialect), []
    # Checked per fragment, not only on the finished query: a column
    # reference is re-rendered in up to four places for a paged sort
    # (select list, both seek branches, ORDER BY), so catching drift here
    # names the reference that caused it.
    _check_bindings(sql, params, f"column reference {order_by_key(column)}")
    return sql, params


# --- WHERE: comparison leaves -----------------------------------------------


#: Operators for which a field-vs-field comparison gets a numeric-cast hint
#: (see `Comparison.compile`) -- ordering only, not equality.
_ORDERING_OPS = frozenset({"<", "<=", ">", ">="})

#: `=`/`!=` render as `IS [NOT] DISTINCT FROM` instead -- NULL-safe
#: equality, so a missing value is treated as a distinct, comparable value
#: rather than "unknown" (SQL's default three-valued-logic behavior for
#: `=`/`!=`, which silently drops any row where either side is NULL from
#: *both* an `eq` and an `ne` count). This matters most for field-vs-field
#: comparisons -- "born and died in different places" should include
#: "died in an unknown place", not silently exclude it -- but applies
#: uniformly to literal comparisons too, for the same reason. Requires
#: SQLite 3.39+ (2022-06-25); standard, unconditionally supported on
#: PostgreSQL.
_NULL_SAFE_OPS = {"=": "IS NOT DISTINCT FROM", "!=": "IS DISTINCT FROM"}


class Comparison:
    """Base class for single-column comparison leaves (`Eq`, `Lt`, ...).

    `value` is normally a literal, always bound as a `?` parameter. It can
    also be another `JsonPath`/`RelatedObject`/`FlatColumnRef` -- a
    *field-vs-field* comparison, e.g. "families where the mother's death
    date is before the father's" (`Lt(mother_death_sortval,
    father_death_sortval)`). Plain `str` is deliberately never treated as a
    field reference here (only `JsonPath`/`RelatedObject`/`FlatColumnRef`
    are) -- a bare string is exactly as likely to be a literal value
    (`Eq("surname", "Smith")`) as a column name, and there's no way to tell
    which was meant; a same-table flat column being compared as a field
    (not a literal) has to be wrapped in `FlatColumnRef` for exactly this
    reason -- see its docstring. `JsonPath`/`RelatedObject`/`FlatColumnRef`
    carry no such ambiguity; nothing constructs a bare `str` to represent a
    field reference.
    """

    op: str

    def __init__(self, column: ColumnRef, value: Any):
        self.column = column
        self.value = value

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        is_field_comparison = isinstance(self.value, (JsonPath, RelatedObject, FlatColumnRef))
        # A field-vs-field comparison has no literal runtime value to infer
        # a numeric/boolean cast from (unlike field-vs-value) -- pick it
        # structurally instead: an *ordering* comparison between two paths
        # is overwhelmingly a numeric/date comparison in practice (e.g. two
        # `sortval`s), so hint numeric via a dummy int (only its *type* is
        # inspected by `_render_json_path`/`_render_related_object`, never
        # its value). Equality doesn't need this: an exact TEXT match is
        # correct whether the underlying value is numeric or textual, as
        # long as both sides extract the same way -- which they do, so
        # `cast_hint` naturally falls back to `self.value` there (a
        # JsonPath/RelatedObject instance, neither bool nor numeric, so it
        # still renders as TEXT on both sides via the existing type checks).
        cast_hint = 0 if is_field_comparison and self.op in _ORDERING_OPS else self.value
        sql_op = _NULL_SAFE_OPS.get(self.op, self.op)
        column_sql, column_params = _render_column(
            self.column, spec, dialect, value=cast_hint, treeid=treeid
        )
        if is_field_comparison:
            value_sql, value_params = _render_column(
                self.value, spec, dialect, value=cast_hint, treeid=treeid
            )
            comparison_sql = f"{column_sql} {sql_op} {value_sql}"
            comparison_params = column_params + value_params
        else:
            comparison_sql = f"{column_sql} {sql_op} ?"
            comparison_params = column_params + [self.value]
        return comparison_sql, comparison_params

    def __eq__(self, other: object) -> bool:
        return (
            type(self) is type(other)
            and self.column == other.column  # type: ignore[attr-defined]
            and self.value == other.value  # type: ignore[attr-defined]
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.column!r}, {self.value!r})"


class Eq(Comparison):
    op = "="


class Ne(Comparison):
    op = "!="


class Lt(Comparison):
    op = "<"


class Lte(Comparison):
    op = "<="


class Gt(Comparison):
    op = ">"


class Gte(Comparison):
    op = ">="


class Like(Comparison):
    op = "LIKE"


class Regex(Comparison):
    """WHERE column REGEXP <pattern> (SQLite) / column ~ <pattern> (PostgreSQL)
    -- an unanchored, case-sensitive regex search (`re.search` semantics, not
    `re.fullmatch`), not a plain SQL operator, so it needs a dialect to
    compile at all (like `JsonPath`/`RelatedObject`).

    SQLite has no built-in `REGEXP` operator, but gramps core's
    `dbapi/sqlite.py` `Connection.__init__` already registers one as a UDF
    on every connection it opens (`regexp(expr, value)`, calling Python's
    `re.search(expr, value, re.MULTILINE)`), so `column REGEXP ?` works
    there for free -- no schema/connection change needed by this module.
    PostgreSQL's native `~` operator has the same unanchored, case-sensitive
    substring-search semantics, so no extension is needed there either.

    The two engines don't speak the same regex dialect, though: SQLite's UDF
    is literally Python's `re` (so it agrees exactly with `evaluator.py`'s
    in-memory `_compare`), while PostgreSQL uses POSIX ARE -- no
    lookahead/lookbehind, no `(?P<name>...)` named groups. A pattern meant
    to behave identically on both backends should stick to the intersection
    (character classes, `\\d`/`\\w`/`\\s`, quantifiers, alternation, plain
    groups, anchors).

    SQLite's UDF is also not NULL-safe, unlike every native operator this
    module otherwise relies on: `re.search(None, ...)`/`re.search(..., None)`
    both raise `TypeError` in plain Python, which `sqlite3` surfaces as a
    hard `OperationalError: user-defined function raised exception` instead
    of SQL's usual "NULL propagates to NULL" -- confirmed live against
    gramps core's registered `regexp()` UDF. `compile()` guards both
    operands with a `CASE` on SQLite so a missing haystack or (field-vs-field)
    pattern comes back `NULL`/`UNKNOWN`, same as every other operator here,
    rather than crashing the query outright. PostgreSQL's native `~`
    NULL-propagates correctly on its own, so no guard is needed there.
    """

    op = "REGEXP"

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        if dialect == Dialect.SQLITE:
            sql_op = "REGEXP"
        elif dialect == Dialect.POSTGRESQL:
            sql_op = "~"
        else:
            raise QueryError(
                f"a dialect is required to compile a Regex, but got {dialect!r}"
            )
        # Always a TEXT extraction -- same reasoning as Contains, just below:
        # there's no numeric/boolean form of a regex match.
        column_sql, column_params = _render_column(
            self.column, spec, dialect, value="", treeid=treeid
        )
        if isinstance(self.value, (JsonPath, RelatedObject, FlatColumnRef)):
            value_sql, value_params = _render_column(
                self.value, spec, dialect, value="", treeid=treeid
            )
        else:
            value_sql, value_params = "?", [self.value]
        if dialect == Dialect.SQLITE:
            sql = (
                f"(CASE WHEN {column_sql} IS NULL OR {value_sql} IS NULL "
                f"THEN NULL ELSE {column_sql} {sql_op} {value_sql} END)"
            )
            return sql, (column_params + value_params) * 2
        return f"{column_sql} {sql_op} {value_sql}", column_params + value_params


class Contains(Comparison):
    """WHERE column LIKE '%<value>%' ESCAPE '\\' -- a plain substring test
    (`'Jan' in given_name`), as opposed to `Like`'s user-authored SQL pattern
    with real `%`/`_` wildcards. `value` is normally the literal substring
    being searched for -- any `%`, `_`, or `\\` it contains is escaped here
    so it matches literally instead of being reinterpreted as a wildcard.

    `value` can also be a `JsonPath`/`RelatedObject`/`FlatColumnRef` -- a
    *field-vs-field* substring test (`other_field in field`). The substring
    is then only known at query *execution* time, not compile time, so the
    escaping that Python's `.replace(...)` does up front for a literal has
    to happen in SQL instead, via nested `REPLACE(...)` in the same order
    (backslash first, so it doesn't double-escape the `%`/`_` replacements
    that follow it) -- both dialects support `REPLACE`/`||` identically, so
    there's no per-dialect branch needed here, unlike most of this module's
    other field-crossing rendering.
    """

    op = "LIKE"

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        if isinstance(self.value, (JsonPath, RelatedObject, FlatColumnRef)):
            # Any string content works as the cast hint here -- Contains
            # always wants a TEXT extraction (LIKE has no numeric/boolean
            # form), never the numeric/boolean cast `_render_json_path`
            # would otherwise pick for an ordering comparison.
            column_sql, column_params = _render_column(
                self.column, spec, dialect, value="", treeid=treeid
            )
            value_sql, value_params = _render_column(
                self.value, spec, dialect, value="", treeid=treeid
            )
            escaped = (
                f"REPLACE(REPLACE(REPLACE({value_sql}, '\\', '\\\\'), "
                f"'%', '\\%'), '_', '\\_')"
            )
            return (
                f"{column_sql} LIKE '%' || {escaped} || '%' ESCAPE '\\'",
                column_params + value_params,
            )
        escaped = (
            self.value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        column_sql, column_params = _render_column(
            self.column, spec, dialect, value=pattern, treeid=treeid
        )
        return f"{column_sql} LIKE ? ESCAPE '\\'", column_params + [pattern]


class In:
    """WHERE column IN (values...)."""

    def __init__(self, column: ColumnRef, values: Sequence[Any]):
        if not values:
            raise QueryError("In() requires at least one value")
        self.column = column
        self.values = list(values)

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        column_sql, column_params = _render_column(
            self.column, spec, dialect, value=self.values[0], treeid=treeid
        )
        placeholders = ", ".join(["?"] * len(self.values))
        return f"{column_sql} IN ({placeholders})", column_params + list(self.values)

    def __eq__(self, other: object) -> bool:
        return (
            type(self) is type(other)
            and self.column == other.column  # type: ignore[attr-defined]
            and self.values == other.values  # type: ignore[attr-defined]
        )

    def __repr__(self) -> str:
        return f"In({self.column!r}, {self.values!r})"


# --- WHERE: boolean combinators ---------------------------------------------


class And:
    def __init__(self, *exprs: Any):
        if not exprs:
            raise QueryError("And() requires at least one expression")
        self.exprs = exprs

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        parts = []
        params: list = []
        for expr in self.exprs:
            sql, p = expr.compile(spec, dialect, treeid)
            parts.append(f"({sql})")
            params.extend(p)
        return " AND ".join(parts), params

    def __repr__(self) -> str:
        return f"And{self.exprs!r}"


class Or:
    def __init__(self, *exprs: Any):
        if not exprs:
            raise QueryError("Or() requires at least one expression")
        self.exprs = exprs

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        parts = []
        params: list = []
        for expr in self.exprs:
            sql, p = expr.compile(spec, dialect, treeid)
            parts.append(f"({sql})")
            params.extend(p)
        return " OR ".join(parts), params

    def __repr__(self) -> str:
        return f"Or{self.exprs!r}"


class Not:
    def __init__(self, expr: Any):
        self.expr = expr

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        sql, params = self.expr.compile(spec, dialect, treeid)
        return f"NOT ({sql})", params

    def __repr__(self) -> str:
        return f"Not({self.expr!r})"


# --- EXISTS (one-to-many membership) -----------------------------------------


def _collection_source_sqlite(collection: Collection, outer_table: str) -> Tuple[str, str, list]:
    """`(from_fragment, handle_expr, params)` for iterating `collection` on
    SQLite, via `json_each` as a table-valued function.

    `json_each`'s own `value` column already holds a plain string for a
    flat-handle-list element (`note_list`) -- no extraction needed -- and the
    serialized JSON text of the element for a ref-object one (`child_ref_list`),
    which `json_extract` then reads `ref_field` out of directly, the same way
    it would against a real `json_data` column.
    """
    (key,) = collection.list_path.segments
    source = f"json_each({outer_table}.json_data, ?) AS je"
    if collection.ref_field:
        handle_expr = f"json_extract(je.value, '$.{collection.ref_field}')"
    else:
        handle_expr = "je.value"
    return source, handle_expr, [f"$.{key}"]


def _collection_source_postgresql(collection: Collection, outer_table: str) -> Tuple[str, str, list]:
    """`(from_fragment, handle_expr, params)` for iterating `collection` on
    PostgreSQL.

    A ref-object list uses `jsonb_array_elements` (keeps each element as
    `jsonb`, so `->> ref_field` can pull the handle back out); a flat-handle
    list uses `jsonb_array_elements_text` instead -- `->>` has no meaning
    against a bare jsonb scalar, but `_text` already unwraps each element to
    plain SQL text directly.
    """
    (key,) = collection.list_path.segments
    if collection.ref_field:
        source = f"jsonb_array_elements({outer_table}.json_data::jsonb -> '{key}') AS je(value)"
        handle_expr = f"je.value ->> '{collection.ref_field}'"
    else:
        source = f"jsonb_array_elements_text({outer_table}.json_data::jsonb -> '{key}') AS je(value)"
        handle_expr = "je.value"
    return source, handle_expr, []


def _collection_subquery_body(
    collection: Collection,
    outer_table: str,
    condition: Optional[Any],
    dialect: Dialect,
    treeid: Optional[int],
) -> Tuple[str, list]:
    """`<target_table> AS <alias>, <source> WHERE <handle correlation>
    [ AND (<condition>)][ AND <alias>.treeid = ?]` -- the subquery body
    shared by `Exists` (`EXISTS (SELECT 1 FROM <body>)`) and
    `CollectionCount` (`(SELECT COUNT(*) FROM <body>)`) alike; only the
    wrapper differs.

    The target row is *always* aliased, even when `target_table !=
    outer_table` (the common case) -- a self-referencing collection (e.g.
    `Person`'s own `associations`, `Person` -> `PersonRef` -> `Person`)
    would otherwise reintroduce the very same bare table name already bound
    to the outer, correlated row, inside this same `FROM` clause, shadowing
    it: `source`'s `json_each(<outer_table>.json_data, ...)`/
    `jsonb_array_elements(<outer_table>.json_data, ...)` would then resolve
    against the newly-introduced *local* binding instead of the outer row,
    silently breaking correlation -- confirmed empirically: `Person
    "exists(associations, ...)"` matched zero rows for every person, even
    ones with a real matching association, before this alias was added.
    Aliasing unconditionally (not just when the names happen to collide)
    keeps this one code path correct regardless of which collection targets
    its own table, rather than needing a separate self-reference check.
    """
    target = collection.target
    target_table = target.table
    target_alias = f"{target_table}__target"

    if dialect == Dialect.SQLITE:
        source, handle_expr, source_params = _collection_source_sqlite(collection, outer_table)
    elif dialect == Dialect.POSTGRESQL:
        source, handle_expr, source_params = _collection_source_postgresql(
            collection, outer_table
        )
    else:
        raise QueryError(f"unsupported dialect: {dialect!r}")

    where_parts = [f"{target_alias}.handle = {handle_expr}"]
    params = list(source_params)
    if condition is not None:
        cond_sql, cond_params = condition.compile(target, dialect, treeid)
        where_parts.append(f"({cond_sql})")
        params.extend(cond_params)
    if treeid is not None:
        where_parts.append(f"{target_alias}.treeid = ?")
        params.append(treeid)

    body = f"{target_table} AS {target_alias}, {source} WHERE {' AND '.join(where_parts)}"
    return body, params


def _render_collection_count(
    count: "CollectionCount",
    outer_table: str,
    dialect: Optional[Dialect],
    treeid: Optional[int],
) -> Tuple[str, list]:
    """`(SELECT COUNT(*) FROM <body>)` -- `CollectionCount`'s rendering,
    dispatched from `_render_column` the same way `RelatedObject`/`JsonPath`
    dispatch to their own renderers.
    """
    if dialect is None:
        raise QueryError(
            f"a dialect is required to compile count({count.collection.name!r}, ...), "
            "but none was given"
        )
    body, params = _collection_subquery_body(
        count.collection, outer_table, count.condition, dialect, treeid
    )
    return f"(SELECT COUNT(*) FROM {body})", params


class Exists:
    """`EXISTS (SELECT 1 FROM <target> JOIN <list> ... WHERE ...)` -- a
    one-to-many membership test over a `Collection` (see there), optionally
    narrowed by a `condition` compiled against the collection's target type.

    Not a correlated *scalar* subquery like `RelatedObject` -- `handle_ref`
    there names a single related row; here there can be any number, so the
    subquery iterates the JSON array (`json_each`/`jsonb_array_elements`)
    joined against the target table by handle, and asks only whether at
    least one such row -- matching `condition`, if given -- exists.

    `condition=None` means "at least one related row at all," regardless of
    its fields (`exists(children)`).

    SQL's `EXISTS`/`NOT EXISTS` are never `UNKNOWN` the way an ordinary
    comparison against a missing value is -- a row that doesn't satisfy the
    inner `WHERE` just isn't returned by the subquery, it doesn't propagate a
    `NULL` outward. `evaluator.py` mirrors this: `Exists` always resolves to
    a definite `True`/`False`, never `None`, so `not exists(...)` needs no
    three-valued-logic special case at all.
    """

    def __init__(self, collection: Collection, condition: Optional[Any] = None):
        self.collection = collection
        self.condition = condition

    def compile(
        self,
        spec: ObjectTypeSpec,
        dialect: Optional[Dialect] = None,
        treeid: Optional[int] = None,
    ) -> Tuple[str, list]:
        if dialect is None:
            raise QueryError(
                f"a dialect is required to compile exists({self.collection.name!r}, ...), "
                "but none was given"
            )
        body, params = _collection_subquery_body(
            self.collection, spec.table, self.condition, dialect, treeid
        )
        return f"EXISTS (SELECT 1 FROM {body})", params

    def __repr__(self) -> str:
        return f"Exists({self.collection.name!r}, {self.condition!r})"


# --- ORDER BY ----------------------------------------------------------------


@dataclass(frozen=True)
class OrderBy:
    """One sort column and its direction.

    `column` is any `ColumnRef`: a flat column name, a path string
    (`"birth.date.sortval"`, resolved by `compile_query`/`run_query` the
    same way a `select` entry is), or an already-resolved
    `JsonPath`/`RelatedObject`/`CollectionCount`. Sorting on a non-flat
    column costs what selecting one costs -- a JSON extraction or a
    correlated subquery per row, with no index behind it -- so it is
    materially slower than sorting on a real SQL column, not merely
    different.
    """

    column: Any = "handle"
    direction: str = "asc"

    def __post_init__(self) -> None:
        if self.direction not in ("asc", "desc"):
            raise QueryError(f"invalid sort direction: {self.direction!r}")


def order_by_key(column: "ColumnRef") -> str:
    """A readable name for a sort column, for error messages and for
    `after_columns`' own reporting -- `default_ref_key` where one exists,
    `repr` otherwise (a `CollectionCount` has no path spelling).
    """
    try:
        return default_ref_key(column)
    except QueryError:
        return repr(column)


def resolve_order_by(
    spec: ObjectTypeSpec, order_by: Sequence[OrderBy]
) -> Tuple[OrderBy, ...]:
    """`order_by` with every string column resolved to a `ColumnRef`, the
    same way `compile_query` resolves a `select` entry -- so
    `OrderBy("birth.date.sortval")` means what it says, and a typo is
    caught here rather than sorting every row by NULL.

    Applied by both `compile_query` and `run_query`, so the two paths sort
    on the same resolved references.
    """
    return tuple(
        OrderBy(
            resolve_ref_string(spec, ob.column) if isinstance(ob.column, str) else ob.column,
            ob.direction,
        )
        for ob in order_by
    )


def effective_order_by(order_by: Sequence[OrderBy]) -> Tuple[OrderBy, ...]:
    """`order_by` with a trailing `handle` tiebreaker appended if not present.

    Guarantees a stable, fully-determined order for both `ORDER BY` emission
    and keyset pagination, even when the caller specifies no sort at all.
    Public (not underscore-prefixed) since `proxied_query.py`'s Python-side
    sort/seek needs the exact same effective order the SQL path compiles,
    not just the column names `after_columns()` exposes.
    """
    if any(ob.column == "handle" for ob in order_by):
        return tuple(order_by)
    return tuple(order_by) + (OrderBy("handle", "asc"),)


def after_columns(order_by: Sequence[OrderBy]) -> Tuple[Any, ...]:
    """Column references, in order, that a resolved `after` cursor tuple
    must supply.

    Wiring code turns a client-supplied `after=<handle>` into a `Query.after`
    tuple by looking up these columns for that row (one extra lookup) before
    compiling -- this module does no database access itself.

    Entries are `ColumnRef`s, not necessarily plain names: a sort on
    `birth.date.sortval` needs that path's value for the cursor row, which
    can't be read by interpolating a column name into SQL. Pass them
    straight to `compile_query` as a `select` against the cursor row's
    handle -- `compile_after_lookup` does exactly that.
    """
    return tuple(ob.column for ob in effective_order_by(order_by))


def compile_after_lookup(
    spec: ObjectTypeSpec,
    order_by: Sequence[OrderBy],
    handle: str,
    *,
    dialect: Optional[Dialect] = None,
    treeid: Optional[int] = None,
) -> Tuple[str, list]:
    """Compile the one-row lookup that turns a client-supplied
    `after=<handle>` cursor into the value tuple `Query.after` wants.

    Returns `(sql, params)` selecting `after_columns(order_by)` for that
    handle -- the row's own sort values, in sort order. Exists because a
    non-flat sort column can't be read by interpolating its name into a
    `SELECT`: `birth.date.sortval` is a correlated subquery with bound
    params, so resolving the cursor has to go through the same compiler the
    query itself does.
    """
    resolved = resolve_order_by(spec, order_by)
    return compile_query(
        spec,
        Query(select=list(after_columns(resolved)), where=Eq("handle", handle), limit=1),
        dialect=dialect,
        treeid=treeid,
    )


def check_columns(columns: Iterable[str], spec: ObjectTypeSpec) -> None:
    """Raise `QueryError` if any of `columns` is not in `spec.columns`.

    Exposed for wiring code that needs to validate columns before they can
    safely appear in a raw SQL fragment built outside `compile_query` --
    e.g. resolving an `after` cursor's row values, which necessarily happens
    before compilation.
    """
    for column in columns:
        _check_column(column, spec.columns)


# --- Top level ---------------------------------------------------------------


@dataclass(frozen=True)
class Query:
    """A structured query: what to return, which rows, in what order.

    `select` entries are `SelectRef`s -- a plain flat column name, an
    already-resolved `JsonPath`/`RelatedObject`/`CollectionCount`, or a
    dotted/bracketed *path string* (`"birth.place.title"`,
    `"primary_name.surname_list[0].surname"`), resolved by `compile_query`
    through `resolve_select_ref_string` (the same `resolve_column_path` a
    `where_expr` path goes through, for every spelling except one). A
    single-segment string stays a strict flat-column reference -- see
    `resolve_ref_string`. `"."` is that one exception: the whole `json_data`
    blob (`WholeJsonData`), a `select`-only spelling -- `order_by`/`where`
    reject it. Omitting `select` returns every flat column, sorted.

    `default_ref_key` gives each entry its canonical response key, and
    `query_lang.parse_select` parses a list of entry strings (with optional
    `as <key>` aliases) into `(ref, key)` pairs.
    """

    select: Optional[Sequence[SelectRef]] = None
    where: Optional[Any] = None
    order_by: Sequence[OrderBy] = ()
    limit: int = 50
    after: Optional[Sequence[Any]] = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit <= 0:
            raise QueryError(f"limit must be positive: {self.limit!r}")


#: Cast hints for `_render_json_path`, keyed by the JSON type the schema
#: says a path lands on. `_render_json_path` picks PostgreSQL's cast from a
#: comparison's right-hand *value* (`Gt(path, 5)` -> `NUMERIC`), which works
#: because a comparison always has one in hand. An `ORDER BY` has no such
#: value, so the schema supplies a stand-in of the right Python type -- the
#: value itself is never bound, only its type is read. Without this,
#: PostgreSQL sorts `jsonb_extract_path_text`'s TEXT result
#: lexicographically, putting 10 before 9.
_CAST_HINT_BY_TYPE = {"boolean": False, "integer": 0, "number": 0.0}


def _cast_hint(value_type: Any) -> Any:
    """A representative value of `value_type`, for `_render_json_path`'s
    cast selection. `None` (no cast hint) for text and for anything the
    schema doesn't pin down -- including a nullable field, whose type is a
    list: `["integer", "null"]` is not reliably numeric, and guessing wrong
    is worse than sorting it as text.
    """
    if isinstance(value_type, str):
        return _CAST_HINT_BY_TYPE.get(value_type)
    return None


def _is_text_ref(ref: "ColumnRef", spec: ObjectTypeSpec) -> bool:
    """Is `ref` a text value, and so eligible for a locale `COLLATE` clause?

    Applying `COLLATE` to a non-text value is a SQL error on PostgreSQL, so
    this has to be right rather than permissive. A flat column is checked
    against `spec.text_columns` as before; a `JsonPath`/`RelatedObject` is
    checked against the schema type it lands on -- which is exactly what
    used to be unavailable, and why `JsonPath` sort columns were previously
    out of scope for collation.
    """
    value_type = ref_value_type(spec, ref)
    if value_type is not None:
        return value_type == "string"
    if isinstance(ref, FlatColumnRef):
        ref = ref.name
    return isinstance(ref, str) and ref in spec.text_columns


def _column_expr(
    column: "ColumnRef",
    spec: ObjectTypeSpec,
    collation: Optional[str],
    dialect: Optional[Dialect] = None,
    treeid: Optional[int] = None,
) -> Tuple[str, list]:
    """A sort/seek column reference: SQL expression + bound params, with a
    locale `COLLATE` clause when the value is text (`_is_text_ref`).

    Any `ColumnRef` works here, not just a flat column name -- a `JsonPath`
    or `RelatedObject` renders through the same `_render_column` a `SELECT`
    or `WHERE` reference does, so `ORDER BY birth.date.sortval` emits the
    identical expression selecting it would. The one thing sorting needs
    that comparing doesn't is a cast hint, since there's no right-hand
    value to infer one from -- see `_cast_hint`.

    `dialect` is forwarded to `_quote_column` -- an `ORDER BY`/keyset
    reference to a column in `_POSTGRESQL_PHYSICAL_COLUMN_OVERRIDES` (e.g.
    `Media.desc`) needs the same physical-name mapping a `SELECT`/`WHERE`
    reference does.
    """
    sql, params = _render_column(
        column, spec, dialect, value=_cast_hint(ref_value_type(spec, column)), treeid=treeid
    )
    if collation and _is_text_ref(column, spec):
        return f'{sql} COLLATE "{collation}"', params
    return sql, params


def _keyset_tie_sql(
    column_expr: str, column_params: Sequence[Any], value: Any
) -> Tuple[str, list]:
    """NULL-safe "ties with the cursor" fragment for an earlier-in-order
    `order_by` column. A bound `NULL` parameter makes plain `col = ?`
    `UNKNOWN` (never `TRUE`), so a cursor value of `None` needs `col IS NULL`
    instead, to correctly express "this row's earlier columns match the
    cursor row's" when the cursor row itself had a `NULL` there.

    `column_params` are `column_expr`'s own bound values (a sort column may
    be a JSON path or a correlated subquery, not a bare name). They're
    emitted here, once per occurrence of `column_expr` in the fragment
    returned -- the count of those occurrences is this function's business,
    not the caller's. See `_keyset_leg_sql` for why that matters.
    """
    if value is None:
        return f"{column_expr} IS NULL", list(column_params)
    return f"{column_expr} = ?", list(column_params) + [value]


def _keyset_leg_sql(
    column_expr: str, column_params: Sequence[Any], direction: str, value: Any
) -> Optional[Tuple[str, list]]:
    """NULL-safe "ranks strictly after the cursor" fragment for the one
    `order_by` column a seek's OR-term actually advances past, matching
    `ORDER BY`'s own verified default total order (`NULL` is the smallest
    value in both directions -- see `_null_safe_cmp` in `proxied_query.py`,
    which mirrors this same order for the evaluator path).

    A plain `col > ?`/`col < ?` against a real SQL `NULL` is always
    `UNKNOWN`, which gets this wrong in two different ways a naive
    translation misses:

    - `asc`, cursor value `None` -- nothing is "greater than NULL" in plain
      SQL, but under `NULL`-is-smallest ordering *every* non-`NULL` value
      ranks after it. Needs `col IS NOT NULL`, not `col > ?` against a bound
      `NULL` (which would just be `UNKNOWN` for every row).
    - `desc`, *any* cursor value -- `NULL` sorts last in `desc`, so a `NULL`
      row always ranks after a non-`NULL` cursor -- but plain `col < ?` is
      `UNKNOWN`, not `TRUE`, when `col` is `NULL`, silently dropping those
      rows from every later page regardless of what the cursor itself was.
      Needs `(col IS NULL OR col < ?)`.

    Returns `None` when the condition can never hold at all (`desc`, cursor
    value `None` -- nothing ranks after the minimum value already), so the
    caller can drop this leg from the `OR` entirely instead of emitting a
    fragment that's always false.

    `column_params` are `column_expr`'s own bound values, emitted once per
    occurrence of `column_expr` below. The `desc` branch is why this has to
    live here rather than in the caller: it is the one fragment that names
    the column *twice* (`col IS NULL OR col < ?`), so a caller adding those
    params once -- the obvious thing to do, and what this originally did --
    leaves the SQL a placeholder short. That drift is caught by
    `_check_bindings`; the same mistake between two *same-length* fragments
    would not be, which is why the count is derived here from the fragment
    itself instead of assumed anywhere.
    """
    if direction == "asc":
        if value is None:
            return f"{column_expr} IS NOT NULL", list(column_params)
        return f"{column_expr} > ?", list(column_params) + [value]
    if value is None:
        return None
    return (
        f"({column_expr} IS NULL OR {column_expr} < ?)",
        list(column_params) + list(column_params) + [value],
    )


def _compile_keyset(
    effective_order_by: Sequence[OrderBy],
    after: Sequence[Any],
    spec: ObjectTypeSpec,
    collation: Optional[str],
    dialect: Optional[Dialect] = None,
    treeid: Optional[int] = None,
) -> Tuple[str, list]:
    """Seek-method WHERE fragment for keyset pagination.

    Expands to an OR-of-ANDs (`(c1 > v1) OR (c1 = v1 AND c2 > v2) OR ...`)
    rather than a row-constructor comparison, so mixed asc/desc multi-column
    sorts stay correct on both SQLite and PostgreSQL. Comparisons use the
    same `COLLATE` clause as the matching `ORDER BY` column -- otherwise a
    row could satisfy a binary-comparison seek predicate while sorting
    differently under collation, corrupting page boundaries.

    NULL-safe throughout (`_keyset_tie_sql`/`_keyset_leg_sql`) -- verified
    empirically against real SQLite before fixing (not just reasoned about):
    the original plain-comparison version silently returned zero further
    rows when seeking past a cursor whose own sort value was `NULL`, and
    separately, silently dropped `NULL` rows from every later page of a
    `desc`-sorted column regardless of the cursor, since `NULL`'s own
    three-valued comparison semantics (`UNKNOWN`, not `TRUE`/`FALSE`) don't
    match `ORDER BY`'s "`NULL` is smallest" total order on their own.
    """
    if len(after) != len(effective_order_by):
        raise QueryError(
            f"after cursor has {len(after)} values, expected "
            f"{len(effective_order_by)} "
            f"({', '.join(order_by_key(ob.column) for ob in effective_order_by)})"
        )
    or_terms = []
    params: list = []
    for i, ob in enumerate(effective_order_by):
        # A non-flat sort column's expression carries its own bound params
        # (a JSONPath string, a subquery's segments), and it's re-emitted
        # once per OR-term it appears in -- so its params are collected
        # alongside each occurrence, in the same left-to-right order the
        # placeholders are rendered, not once up front.
        leg_expr, leg_expr_params = _column_expr(ob.column, spec, collation, dialect, treeid)
        leg = _keyset_leg_sql(leg_expr, leg_expr_params, ob.direction, after[i])
        if leg is None:
            continue
        and_terms = []
        and_params: list = []
        for j in range(i):
            tie_expr, tie_expr_params = _column_expr(
                effective_order_by[j].column, spec, collation, dialect, treeid
            )
            tie_sql, tie_params = _keyset_tie_sql(tie_expr, tie_expr_params, after[j])
            and_terms.append(tie_sql)
            and_params.extend(tie_params)
        leg_sql, leg_params = leg
        and_terms.append(leg_sql)
        and_params.extend(leg_params)
        or_terms.append("(" + " AND ".join(and_terms) + ")")
        params.extend(and_params)
    if not or_terms:
        # Every leg was structurally impossible (e.g. a lone `desc` column
        # whose cursor value is already `None`, the minimum -- nothing can
        # rank after it). Correctly means "no further rows", not an error.
        return "0 = 1", []
    keyset_sql = " OR ".join(or_terms)
    _check_bindings(keyset_sql, params, "keyset seek predicate")
    return keyset_sql, params


def _where_clauses(
    spec: ObjectTypeSpec,
    where: Optional[Any],
    dialect: Optional[Dialect] = None,
    treeid: Optional[int] = None,
) -> Tuple[list, list]:
    """Shared `WHERE`-clause + tree-scoping predicate building.

    Used by both `compile_query` and `compile_count_query`, so the two can't
    drift on how tree-scoping is enforced. Carries no privacy predicate at
    all -- this compiler only ever runs against an unproxied database, see
    `object_query.py`'s dispatch.

    `treeid`, when given, appends `AND treeid = ?` -- required on shared
    multi-tree backends (`SharedPostgreSQL`), whose tables hold every tree's
    rows together with `treeid` as part of the primary key. Nothing applies
    this filter automatically at the connection level; every one of
    `SharedDBAPI`'s own query methods (`get_person_handles`, etc.) adds it
    by hand, so this compiler must too, or it silently returns rows from
    every tree sharing the instance -- not just the caller's own. `None`
    (the default) omits the clause entirely, for single-tree-per-database
    backends (`SQLite`, the single-user `PostgreSQL` addon) that have no
    `treeid` column at all -- see `resources/object_query.py`'s
    `_resolve_treeid`.
    """
    clauses = []
    params: list = []
    if where is not None:
        sql, p = where.compile(spec, dialect, treeid)
        clauses.append(f"({sql})")
        params.extend(p)
    if treeid is not None:
        clauses.append("treeid = ?")
        params.append(treeid)
    return clauses, params


def compile_query(
    spec: ObjectTypeSpec,
    query: Query,
    *,
    collation: Optional[str] = None,
    dialect: Optional[Dialect] = None,
    treeid: Optional[int] = None,
) -> Tuple[str, list]:
    """Compile a `Query` into a parameterized `SELECT ... FROM <spec.table>` statement.

    Returns `(sql, params)` where `sql` uses `?` placeholders and `params` is
    the positional parameter list, matching `db.dbapi.execute(sql, params)`.

    Carries no privacy predicate: only ever call this against an unproxied
    database (see `object_query.py`'s dispatch) -- a proxied query runs
    through Gramps' own `Filter`/`Rule` machinery instead
    (`proxied_query.py`), never this compiler. `AND treeid = ?` is appended
    unconditionally whenever `treeid` is given -- see `_where_clauses`.

    `collation`, if given, names a locale collation already ensured to exist
    on the connection (see `resources/object_query.py`'s `_resolve_collation`)
    and is applied to every text-typed `ORDER BY` column (and the matching
    keyset comparisons) via `COLLATE "<collation>"`.

    A `select` entry given as a dotted/bracketed path string is resolved
    here (via `resolve_ref_string`) before rendering, so the same text
    means the same thing in `select` as it does in a `where_expr` -- a
    `QueryError` from an unknown column or a malformed path surfaces from
    this call, not from the database.

    `dialect` selects which backend-specific SQL to render for any `select`
    or `where` entry that's a `JsonPath` or a `RelatedObject` (see
    `_render_json_path`/`_render_related_object`), and also which physical
    name a plain column gets if it's in `_POSTGRESQL_PHYSICAL_COLUMN_OVERRIDES`
    (e.g. `Media.desc`) -- that applies to `order_by`/keyset pagination too,
    not just `select`/`where`, since PostgreSQL's physical table has the
    same renamed column either way. Omitting `dialect` is safe for a query
    that touches none of the above (plain columns not in that override
    table, no `JsonPath`/`RelatedObject`); it is not safe in general.
    """
    columns = [
        resolve_select_ref_string(spec, entry) if isinstance(entry, str) else entry
        for entry in (query.select if query.select else sorted(spec.columns))
    ]

    ordering = effective_order_by(resolve_order_by(spec, query.order_by))

    select_parts = []
    params: list = []
    for column in columns:
        sql_frag, p = _render_column(column, spec, dialect, treeid=treeid)
        select_parts.append(sql_frag)
        params.extend(p)

    where_clauses, where_params = _where_clauses(spec, query.where, dialect, treeid)
    params.extend(where_params)

    if query.after is not None:
        sql, p = _compile_keyset(ordering, query.after, spec, collation, dialect, treeid)
        where_clauses.append(f"({sql})")
        params.extend(p)

    # Built before assembly, not inline: a non-flat sort column contributes
    # bound params of its own, and they belong after the WHERE/keyset params
    # and before `LIMIT`'s -- the order the placeholders appear in the SQL.
    order_parts = []
    order_params: list = []
    for ob in ordering:
        order_sql, p = _column_expr(ob.column, spec, collation, dialect, treeid)
        order_parts.append(f"{order_sql} {ob.direction.upper()}")
        order_params.extend(p)

    sql = f"SELECT {', '.join(select_parts)} FROM {spec.table}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY " + ", ".join(order_parts)
    params.extend(order_params)
    if query.limit is not None:
        sql += " LIMIT ?"
        params.append(query.limit)

    _check_bindings(sql, params, "compiled query")
    return sql, params


def compile_count_query(
    spec: ObjectTypeSpec,
    query: Query,
    *,
    dialect: Optional[Dialect] = None,
    treeid: Optional[int] = None,
) -> Tuple[str, list]:
    """Compile a `Query` into a parameterized `SELECT COUNT(*) FROM <spec.table>`.

    Uses the same `where` and tree-scoping logic as `compile_query` -- see
    there for details -- but ignores `select`/`order_by`/`limit`/`after`,
    since a count has no columns, sort order, or page to return. In
    particular this is a count of *all* matching rows, not of just the
    current keyset page.
    """
    where_clauses, params = _where_clauses(spec, query.where, dialect, treeid)
    sql = f"SELECT COUNT(*) FROM {spec.table}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    _check_bindings(sql, params, "compiled count query")
    return sql, params
