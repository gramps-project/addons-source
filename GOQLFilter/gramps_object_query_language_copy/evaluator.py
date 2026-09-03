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

"""Evaluate `query.py`'s AST directly against real Gramps objects.

`query.py` compiles a `Query`/`where` expression to SQL, which is only safe
to run against an *unproxied* database -- it has no notion of privacy or any
other proxy-applied rule, and reimplementing one in SQL is exactly the
mistake this module exists to avoid (see `query.py`'s module docstring).
This module instead walks the same AST and evaluates it directly against a
real object, fetched through whatever `db` the caller passes in. When `db`
is a proxy, every object this module ever sees -- the row object itself and
anything reached via a `RelatedObject` hop, at any depth -- has already been
through that proxy's own `include_*`/`sanitize_*` rules. Correctness follows
from that alone: there is no separate privacy guard here the way
`Comparison.compile()` needs a `CASE WHEN` guard for NULL-safe `Eq`/`Ne` --
a masked field already reads back as whatever the proxy's `sanitize_*` left
it as (typically `None`), and plain Python `==`/`!=`/`is None` against that
already-correct value is automatically the right, non-leaking answer.

Not fast: no SQL push-down, no keyset narrowing before objects are fetched.
Intended for the proxied path, where the query's result set is expected to
be small relative to the table, or where correctness matters more than
p99 latency -- see `object_query.py`'s dispatch.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional, Tuple

from gramps.gen.errors import HandleError
from gramps.gen.lib import json_utils

from .query import (
    And,
    BacklinkClassFilter,
    Backlinks,
    Collection,
    CollectionCount,
    ColumnIndex,
    ColumnRef,
    Comparison,
    Contains,
    Exists,
    FlatColumnRef,
    In,
    JsonPath,
    Not,
    ObjectTypeSpec,
    Or,
    RelatedObject,
)

# Real getter method name for each `ObjectTypeSpec.table`, used to fetch a
# `RelatedObject` hop's target through `db` (whatever proxy or plain
# database that is) -- never a direct/unproxied lookup.
GETTER_BY_TABLE: dict[str, str] = {
    "person": "get_person_from_handle",
    "family": "get_family_from_handle",
    "event": "get_event_from_handle",
    "place": "get_place_from_handle",
    "repository": "get_repository_from_handle",
    "source": "get_source_from_handle",
    "citation": "get_citation_from_handle",
    "media": "get_media_from_handle",
    "note": "get_note_from_handle",
    "tag": "get_tag_from_handle",
}


def _given_name(obj: Any) -> str:
    primary_name = obj.get_primary_name()
    return primary_name.get_first_name() if primary_name else ""


def _surname(obj: Any) -> str:
    primary_name = obj.get_primary_name()
    if not primary_name:
        return ""
    surname_list = primary_name.get_surname_list()
    if not surname_list or not surname_list[0]:
        return ""
    return surname_list[0].surname


def _enclosed_by(obj: Any) -> str:
    for placeref in obj.get_placeref_list():
        return placeref.ref
    return ""


# `given_name`/`surname`/`enclosed_by` are real SQL columns (populated by the
# DB layer at write time), but not real attributes on the in-memory object --
# mirrors gramps core's `gen/db/generic.py` `DbGeneric._get_person_data`/
# `_get_place_data` exactly, the functions that populate those same columns.
_DERIVED_COLUMNS: dict[str, dict[str, Any]] = {
    "person": {"given_name": _given_name, "surname": _surname},
    "place": {"enclosed_by": _enclosed_by},
}


def get_flat_column(obj: Any, column: str, spec: ObjectTypeSpec) -> Any:
    """A flat column's value straight off a real object.

    `getattr` for anything `get_secondary_fields()` already exposes as a
    real attribute (`gramps_id`, `gender`, `private`, `handle`,
    `father_handle`, `place`, ...) -- which is everything except the small,
    fixed set of derived columns above.
    """
    derived = _DERIVED_COLUMNS.get(spec.table, {})
    if column in derived:
        return derived[column](obj)
    return getattr(obj, column)


def _walk_json_path(data: Any, segments: Any, root_obj: Any) -> Any:
    """Walk `JsonPath.segments` against `data` (an `object_to_dict()` dict).

    A `ColumnIndex` segment resolves against `root_obj` -- the row the path
    started from -- not whatever `data` has been narrowed to by that point,
    mirroring `_render_handle_ref`'s "this row's `<column>`" semantics
    exactly (only ever appears as a `RelatedObject.handle_ref` segment, so
    this only matters one level deep in practice).
    """
    current = data
    for segment in segments:
        if current is None:
            return None
        if isinstance(segment, ColumnIndex):
            index = getattr(root_obj, segment.column)
            if index is None or index < 0:
                return None
            segment = index
        if isinstance(segment, int):
            if not isinstance(current, list) or not -len(current) <= segment < len(current):
                return None
            current = current[segment]
        else:
            if not isinstance(current, dict):
                return None
            current = current.get(segment)
    return current


def get_json_path(obj: Any, path: JsonPath) -> Any:
    """`JsonPath.segments` extracted from `obj`'s real, in-memory data.

    `object_to_dict()` is the same JSON-shaped structure the compiled SQL
    path navigates via `json_extract`/`->` against the stored `json_data`
    column -- using it here keeps the two paths interpreting a `JsonPath`
    identically without hand-duplicating that shape.
    """
    if path.base_column != "json_data":
        raise ValueError(f"unsupported JsonPath base column: {path.base_column!r}")
    data = json_utils.object_to_dict(obj)
    return _walk_json_path(data, path.segments, obj)


def _resolve_related_object(
    db: Any, obj: Any, ref: RelatedObject, spec: ObjectTypeSpec
) -> Any:
    if isinstance(ref.handle_ref, JsonPath):
        handle = get_json_path(obj, ref.handle_ref)
    else:
        handle = get_flat_column(obj, ref.handle_ref, spec)
    if not handle:
        return None
    getter = getattr(db, GETTER_BY_TABLE[ref.target.table])
    try:
        return getter(handle)
    except HandleError:
        return None


def resolve_column_ref(db: Any, obj: Any, ref: ColumnRef, spec: ObjectTypeSpec) -> Any:
    """`query.py`'s `_render_column`, evaluated in Python against a real
    object instead of rendered as SQL.

    `db` is whatever the caller is running under (proxy or plain) --
    every `RelatedObject` hop is fetched through it (`_resolve_related_object`),
    so the same rules that applied to `obj` itself apply to everything
    reached from it, at any depth, with no separate handling needed here.
    """
    if obj is None:
        return None
    if isinstance(ref, RelatedObject):
        related_obj = _resolve_related_object(db, obj, ref, spec)
        return resolve_column_ref(db, related_obj, ref.field, ref.target)
    if isinstance(ref, JsonPath):
        return get_json_path(obj, ref)
    if isinstance(ref, CollectionCount):
        return _collection_count(db, obj, ref)
    if isinstance(ref, FlatColumnRef):
        return get_flat_column(obj, ref.name, spec)
    return get_flat_column(obj, ref, spec)


def _collection_handles(obj: Any, collection: Collection) -> list:
    """The list of related handles for `collection` on `obj` -- a plain
    handle string per element (`notes`), or each element's `ref_field`
    pulled out (`children`'s `ChildRef.ref`) -- mirrors `query.py`'s
    `_collection_source_sqlite`/`_collection_source_postgresql` exactly, just
    walking the real in-memory list instead of rendering SQL to iterate it.
    """
    items = get_json_path(obj, collection.list_path) or []
    if collection.ref_field:
        return [item.get(collection.ref_field) for item in items if item]
    return [item for item in items if item]


def _backlink_handles(
    db: Any, obj: Any, condition: Optional[BacklinkClassFilter]
) -> Iterator[Tuple[str, str]]:
    """`(class_name, handle)` pairs for every object referencing `obj`,
    matching `condition` (a `BacklinkClassFilter`, `Backlinks`' only
    supported condition shape -- see query.py) if given -- the evaluator
    counterpart to `query.py`'s `_backlinks_subquery_body`, walking
    `db.find_backlink_handles` directly instead of joining the physical
    `reference` table in SQL.

    "eq"/"in" map straight onto `find_backlink_handles`'s own
    `include_classes` parameter (already exactly "which classes to
    include"); "ne" has no such shape to pass through (there's no
    "every class except this one" parameter), so it walks the
    unrestricted result and filters in Python instead.

    Privacy comes from `db` itself, same as every other relationship this
    module evaluates (see the module docstring): when `db` is a
    `PrivateProxyDb`, its own `find_backlink_handles` override already
    excludes a referrer that is itself private (`gramps/gen/proxy/
    private.py`) before this function ever sees it -- no separate privacy
    handling needed here.
    """
    if condition is None:
        yield from db.find_backlink_handles(obj.handle)
    elif condition.op in ("eq", "in"):
        include_classes = [condition.value] if condition.op == "eq" else list(condition.value)
        yield from db.find_backlink_handles(obj.handle, include_classes)
    else:
        for class_name, handle in db.find_backlink_handles(obj.handle):
            if class_name != condition.value:
                yield class_name, handle


def _collection_count(db: Any, obj: Any, count: CollectionCount) -> int:
    """How many related rows in `count.collection` match `count.condition`
    (every related row at all, if `condition` is `None`) -- the evaluator
    counterpart to `query.py`'s `CollectionCount` SQL rendering. Unlike
    `Exists`'s short-circuit on the first match, this has to walk every
    related row, matching `COUNT(*)`'s own semantics.
    """
    if isinstance(count.collection, Backlinks):
        return sum(1 for _ in _backlink_handles(db, obj, count.condition))
    getter = getattr(db, GETTER_BY_TABLE[count.collection.target.table])
    matched = 0
    for handle in _collection_handles(obj, count.collection):
        try:
            related = getter(handle)
        except HandleError:
            continue
        if count.condition is None or evaluate_where(
            db, related, count.condition, count.collection.target
        ):
            matched += 1
    return matched


def _like_to_regex(pattern: str) -> re.Pattern:
    """Translate a SQL `LIKE` pattern (`%`/`_` wildcards) to a regex.

    Case-insensitive, matching SQLite's default `LIKE` behavior for ASCII --
    the backend every test fixture and single-tree/dev deployment actually
    runs (see `object_query.py`'s `_resolve_dialect`). Any other character
    is escaped literally via `re.escape` before the wildcard translation.
    """
    out = []
    for char in pattern:
        if char == "%":
            out.append(".*")
        elif char == "_":
            out.append(".")
        else:
            out.append(re.escape(char))
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


_ORDERING_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def _compare(op: str, left: Any, right: Any) -> Optional[bool]:
    """`None` means SQL's `UNKNOWN` -- see `_evaluate_tri`'s docstring for
    why this three-valued result matters, not just a plain `bool`.
    """
    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == "LIKE":
        if left is None or right is None:
            return None
        return _like_to_regex(str(right)).match(str(left)) is not None
    if op == "REGEXP":
        # Mirrors gramps core's `dbapi/sqlite.py` `regexp(expr, value)` UDF
        # exactly (`re.search(expr, value, re.MULTILINE)`) -- an unanchored,
        # case-sensitive search, not `_like_to_regex`'s case-insensitive
        # full-match -- so this evaluator path and a real SQLite backend
        # agree on every row. `right` is the pattern (`Regex.value`), `left`
        # the haystack, same left/right convention as `LIKE` above.
        if left is None or right is None:
            return None
        return re.search(str(right), str(left), re.MULTILINE) is not None
    if op in _ORDERING_OPS:
        # SQL's ordering comparisons against a NULL operand are UNKNOWN, not
        # False, under standard three-valued logic -- Python raises
        # TypeError instead, so this has to be explicit. Collapsing this
        # straight to False here (rather than in `_evaluate_tri`, one layer
        # up) would be indistinguishable from a genuine False to `Not`,
        # which needs to leave UNKNOWN as UNKNOWN rather than flip it to
        # True -- see `_evaluate_tri`.
        if left is None or right is None:
            return None
        return _ORDERING_OPS[op](left, right)
    raise ValueError(f"unsupported operator: {op!r}")


def _evaluate_tri(db: Any, obj: Any, expr: Any, spec: ObjectTypeSpec) -> Optional[bool]:
    """`evaluate_where`'s actual recursion, in SQL's three-valued logic
    (`True`/`False`/`None` for `UNKNOWN`) rather than a plain `bool`.

    A leaf comparison against a missing value (a masked field, or a path/
    relationship that doesn't resolve) is `UNKNOWN`, not `False` -- SQL's
    `NOT UNKNOWN` is still `UNKNOWN`, not `True`, so if this collapsed to a
    definite `False` at each leaf the way a plain `bool` would force it to,
    `Not` wrapping that leaf would incorrectly flip it to `True` where SQL
    would still exclude the row. Recursing in three-valued logic here, and
    collapsing to a real `bool` exactly once -- in `evaluate_where`, at the
    very end -- keeps `Not`/`And`/`Or` behaving the same as their compiled-
    SQL counterparts at any nesting depth, not just one level deep.

    `And`/`Or` follow SQL's own precedence for combining three values:
    a definite `False` always wins an `And` (regardless of any `UNKNOWN`
    sibling), a definite `True` always wins an `Or` the same way -- checked
    first, before falling back to "`UNKNOWN` if any operand is, else the
    identity value" -- matching `AND`/`OR`'s truth tables exactly, not just
    "any/all treat `None` as falsy" (which would get the dominance wrong).
    """
    if expr is None:
        return True
    if isinstance(expr, And):
        results = [_evaluate_tri(db, obj, e, spec) for e in expr.exprs]
        if any(r is False for r in results):
            return False
        if any(r is None for r in results):
            return None
        return True
    if isinstance(expr, Or):
        results = [_evaluate_tri(db, obj, e, spec) for e in expr.exprs]
        if any(r is True for r in results):
            return True
        if any(r is None for r in results):
            return None
        return False
    if isinstance(expr, Not):
        result = _evaluate_tri(db, obj, expr.expr, spec)
        return None if result is None else not result
    if isinstance(expr, Exists):
        # Always a definite True/False, never UNKNOWN -- matching SQL's own
        # EXISTS/NOT EXISTS, which never propagates NULL from a subquery
        # row that fails its WHERE, it's simply not counted. Unlike every
        # other branch here, there's no missing-value case to collapse to
        # None for.
        collection = expr.collection
        if isinstance(collection, Backlinks):
            return any(True for _ in _backlink_handles(db, obj, expr.condition))
        getter = getattr(db, GETTER_BY_TABLE[collection.target.table])
        for handle in _collection_handles(obj, collection):
            try:
                related = getter(handle)
            except HandleError:
                continue
            if expr.condition is None or evaluate_where(
                db, related, expr.condition, collection.target
            ):
                return True
        return False
    if isinstance(expr, In):
        value = resolve_column_ref(db, obj, expr.column, spec)
        if value is None:
            return None
        return value in expr.values
    if isinstance(expr, Contains):
        # A plain substring test -- unlike `Like`'s SQL-pattern matching
        # (`_like_to_regex`), `expr.value` (when a literal) has no wildcard
        # characters to reinterpret, so a direct (case-insensitive, matching
        # SQLite's default `LIKE` behavior) Python `in` check is both
        # correct and simpler than routing through the LIKE/regex machinery.
        # `expr.value` can also be a `JsonPath`/`RelatedObject` -- a
        # field-vs-field substring test -- resolved the same way `expr.column`
        # is; a missing needle (as opposed to a missing haystack) is just as
        # much "unknown" as a missing haystack, so it collapses to the same
        # `None` (SQL's `LIKE` against a NULL pattern is `UNKNOWN` too).
        value = resolve_column_ref(db, obj, expr.column, spec)
        if value is None:
            return None
        if isinstance(expr.value, (JsonPath, RelatedObject, FlatColumnRef)):
            substring = resolve_column_ref(db, obj, expr.value, spec)
            if substring is None:
                return None
        else:
            substring = expr.value
        return str(substring).lower() in str(value).lower()
    if isinstance(expr, Comparison):
        left = resolve_column_ref(db, obj, expr.column, spec)
        if isinstance(expr.value, (JsonPath, RelatedObject, FlatColumnRef)):
            right = resolve_column_ref(db, obj, expr.value, spec)
        else:
            right = expr.value
        return _compare(expr.op, left, right)
    raise TypeError(f"unsupported where expression: {expr!r}")


def evaluate_where(db: Any, obj: Any, expr: Any, spec: ObjectTypeSpec) -> bool:
    """`query.py`'s `.compile()` tree, evaluated in Python against a real
    object instead of rendered as SQL. See module docstring for why no
    privacy guard is needed here the way `Comparison.compile()` needs one.

    Delegates the actual recursion to `_evaluate_tri`, which tracks SQL's
    three-valued logic (`True`/`False`/`UNKNOWN`) rather than a plain
    `bool` -- collapsed to a real `bool` here, exactly once, the same way
    a SQL `WHERE` clause only keeps rows that are definitely `True`,
    treating `UNKNOWN` the same as `False`.
    """
    return _evaluate_tri(db, obj, expr, spec) is True
