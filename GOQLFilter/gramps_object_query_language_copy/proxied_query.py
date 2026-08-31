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

"""Run a `where` expression against a possibly-proxied `db`.

Compiles a `Query.where` expression into a Gramps `Rule`, wrapped in the
matching core `Filter` class (`GenericFilterFactory`), and calls
`Filter.apply(db)` -- the same mechanism Gramps' own Custom Filters use.
`Filter.apply()` fetches each candidate through `db` before testing it
(`GenericFilter.get_object`), so when `db` is a proxy, everything this
module ever hands to `evaluate_where` has already been through that
proxy's own `include_*`/`sanitize_*` rules, at any relationship depth --
see `evaluator.py`'s module docstring for why that's sufficient on its own,
with no separate privacy handling needed here.

Not fast: `Filter.apply()` enumerates every handle of the type before
narrowing, and every enumerated handle is fetched (deserialized) to test
it. See `object_query.py`'s dispatch for when this path is used instead of
`query.py`'s SQL compiler.

`Filter.apply()` only ever returns handles, not the objects it built and
tested them with -- `_PredicateRule` holds onto each matched object itself
(`matched_objects`, keyed by handle) so `run_query` can hand them back
directly instead of fetching (and re-sanitizing) every match a second
time. Confirmed via profiling that this second fetch was ~70% of this
module's entire overhead relative to a hand-written equivalent loop: under
a proxy, re-fetching a handle means re-running the proxy's own
`sanitize_*`, not a cheap cache hit.

`run_query` also implements `order_by`/`limit`/`after` (keyset pagination)
and `select`, entirely in Python over the already-fetched match list, so a
`Query` means the same thing on this path as it does through `query.py`'s
SQL compiler -- see `ROADMAP.md`'s "Evaluator-path pagination/sort parity"
section for the gap this closes. Two deliberate scope caps, matching that
section's recommended v1:

- `order_by` is restricted to flat columns (`OrderBy.column` is always a
  plain string, checked against `spec.columns`) -- the same cap the SQL
  path's own `order_by` already has (a `JsonPath`/`RelatedObject` column
  can't be sorted by there either), so this path doesn't leapfrog ahead of
  what SQL itself can do.
- Collation is ASCII/codepoint only (plain Python `<`/`>`) -- SQL's
  locale-aware `COLLATE` has no Python-side equivalent here. Documented
  gap, not attempted.

`NULL` placement, for both plain sorting and keyset seeking, matches
SQLite's own verified default (confirmed empirically, not assumed): `NULL`
sorts as the smallest value in both directions, so `DESC` is the exact
reverse of `ASC`, `NULL`s included. Keyset seeking (`after`) mirrors
`query.py`'s `_compile_keyset` SQL, which (after its own NULL-safety fix --
see that function's docstring) applies this identical NULL-is-smallest rule
to the seek predicate too, rather than relying on SQL's raw three-valued
comparison semantics -- a plain `col > ?`/`col < ?` against a real `NULL`
is always `UNKNOWN`, which silently produced wrong seek results in two
different ways before that fix (a cursor taken from a `NULL` row couldn't
seek past it at all; a `desc`-sorted `NULL` row was silently dropped from
every later page regardless of the cursor). `_matches_keyset` below reuses
`_null_safe_cmp` directly for exactly this reason -- one NULL rule, shared
by sorting and seeking on both this path and the SQL path, not two.
"""

from __future__ import annotations

import functools
from typing import Any, Dict, List, Optional, Sequence, Tuple

from gramps.gen.filters import GenericFilterFactory
from gramps.gen.filters.rules import Rule

from .evaluator import GETTER_BY_TABLE, evaluate_where, resolve_column_ref
from .query import (
    ColumnRef,
    ObjectTypeSpec,
    OrderBy,
    QueryError,
    effective_order_by,
    order_by_key,
    resolve_order_by,
    resolve_select_ref_string,
)

# Core `Filter` namespace for each `ObjectTypeSpec.table` that has one.
# `Tag` is deliberately absent: `GenericFilterFactory("Tag")` returns `None`
# (Gramps core has no Filter class for it), and it has no privacy concept to
# delegate to a proxy for anyway (`TAG.has_privacy` is `False`) -- see the
# fallback in `run_query`.
_FILTER_NAMESPACE_BY_TABLE: dict[str, str] = {
    "person": "Person",
    "family": "Family",
    "event": "Event",
    "place": "Place",
    "repository": "Repository",
    "source": "Source",
    "citation": "Citation",
    "media": "Media",
    "note": "Note",
}


class _PredicateRule(Rule):
    """A `Rule` wrapping an already-compiled `where` expression.

    Not a new rule "language" -- `apply_to_one` just hands `obj` to the same
    `Query.where` AST evaluator every query endpoint already builds
    (`evaluator.evaluate_where`), so a query's `where`/`where_expr` means
    exactly the same thing on both the SQL and proxied paths.

    Also doubles as the match-object cache `run_query` reads afterward
    (`matched_objects`) -- `apply_to_one` is hand the real, already-fetched-
    and-sanitized object anyway, so keeping a reference here is free, and
    saves `run_query` from fetching (and re-sanitizing, under a proxy) every
    match a second time just to get the object back.
    """

    def __init__(self, where: Any, spec: ObjectTypeSpec) -> None:
        super().__init__([])
        self._where = where
        self._spec = spec
        self.matched_objects: Dict[str, Any] = {}

    def apply_to_one(self, db: Any, obj: Any) -> bool:
        # `obj is None` means this handle was excluded by whatever proxy
        # `db` is (or genuinely doesn't resolve) -- never a match,
        # regardless of `where` (an empty/`None` where means "match
        # everything", which must still exclude a row that isn't there).
        # Relying on every proxy's handle enumeration to have already
        # filtered this out before `Filter.apply()` ever calls this would be
        # exactly the kind of unverified cross-proxy assumption this
        # redesign exists to avoid -- see `evaluator.py`'s module docstring.
        if obj is None:
            return False
        matched = evaluate_where(db, obj, self._where, self._spec)
        if matched:
            self.matched_objects[obj.handle] = obj
        return matched


def _null_safe_cmp(a: Any, b: Any, direction: str) -> int:
    """Column-level three-way compare matching SQLite's verified `ORDER BY`
    default: `NULL` sorts as the smallest value regardless of direction, so
    `DESC` is the exact reverse of `ASC`, `NULL`s included.
    """
    if a is None and b is None:
        cmp = 0
    elif a is None:
        cmp = -1
    elif b is None:
        cmp = 1
    elif a < b:
        cmp = -1
    elif a > b:
        cmp = 1
    else:
        cmp = 0
    return -cmp if direction == "desc" else cmp


def _sort_key_row(
    db: Any, obj: Any, ordering: Sequence[OrderBy], spec: ObjectTypeSpec
) -> Tuple[Any, ...]:
    return tuple(resolve_column_ref(db, obj, ob.column, spec) for ob in ordering)


def _sort_matches(
    db: Any, matches: List[Any], ordering: Sequence[OrderBy], spec: ObjectTypeSpec
) -> List[Tuple[Tuple[Any, ...], Any]]:
    """`matches` paired with its resolved sort-key row, sorted per `ordering`."""
    keyed = [(_sort_key_row(db, obj, ordering, spec), obj) for obj in matches]

    def compare(row_a: Tuple[Any, ...], row_b: Tuple[Any, ...]) -> int:
        key_a, _ = row_a
        key_b, _ = row_b
        for value_a, value_b, ob in zip(key_a, key_b, ordering):
            result = _null_safe_cmp(value_a, value_b, ob.direction)
            if result != 0:
                return result
        return 0

    keyed.sort(key=functools.cmp_to_key(compare))
    return keyed


def _matches_keyset(
    key_row: Sequence[Any], after: Sequence[Any], ordering: Sequence[OrderBy]
) -> bool:
    """Python equivalent of `query._compile_keyset`'s NULL-safe seek
    predicate, after its own NULL-safety fix -- "ranks strictly after the
    cursor" reuses `_null_safe_cmp`'s own total order (`NULL` is the
    smallest value in both directions, the same rule plain sorting uses),
    rather than SQL's raw three-valued comparison semantics. A tie always
    uses `"asc"` regardless of that column's own direction, since equality
    itself isn't direction-dependent (`_null_safe_cmp` returns `0` for a tie
    under either direction -- only strict ordering flips).
    """
    for i, ob in enumerate(ordering):
        if any(_null_safe_cmp(key_row[j], after[j], "asc") != 0 for j in range(i)):
            continue
        if _null_safe_cmp(key_row[i], after[i], ob.direction) > 0:
            return True
    return False


def run_query(
    db: Any,
    spec: ObjectTypeSpec,
    where: Any,
    *,
    order_by: Sequence[OrderBy] = (),
    limit: Optional[int] = None,
    after: Optional[Sequence[Any]] = None,
    select: Optional[Sequence[ColumnRef]] = None,
) -> List[Any]:
    """Every real object of `spec`'s type matching `where`, fetched through `db`.

    `db` may be a proxy or a plain database -- either way, the returned
    objects (and match decisions) reflect whatever `db` itself would return
    for each handle, never an unproxied lookup.

    `order_by`/`limit`/`after` mean exactly what they mean on `Query`/
    `compile_query` -- see this module's own docstring for the two scope
    caps (flat-column `order_by` only, ASCII-only collation) and the NULL
    placement policies used. A trailing `handle` tiebreaker is always
    applied (via `effective_order_by`), even when `order_by` is empty, so
    the result is always in a fully deterministic order, matching the SQL
    path's own always-present `ORDER BY`.

    `select`, when given, projects the final page into a list of value
    tuples (one per entry in `select`, resolved via `resolve_column_ref`)
    instead of returning full objects -- the evaluator-path equivalent of
    the SQL path's `SELECT` list. Omitting `select` (the default) keeps
    returning full objects, unchanged from before this parameter existed.
    """
    getter = getattr(db, GETTER_BY_TABLE[spec.table])
    namespace = _FILTER_NAMESPACE_BY_TABLE.get(spec.table)
    if namespace is None:
        handles = getattr(db, f"get_{spec.table}_handles")()
        matches = [
            obj
            for handle in handles
            if (obj := getter(handle)) is not None and evaluate_where(db, obj, where, spec)
        ]
    else:
        filter_class = GenericFilterFactory(namespace)
        gfilter = filter_class()
        rule = _PredicateRule(where, spec)
        gfilter.add_rule(rule)
        matched_handles = gfilter.apply(db)
        matches = [
            rule.matched_objects[handle]
            for handle in matched_handles
            if handle in rule.matched_objects
        ]

    # Resolved, not whitelist-checked: `order_by` takes the same
    # `ColumnRef`s `select` does, and `_sort_key_row` already resolves
    # whatever it's given via `resolve_column_ref`. The Python sort needs
    # no CAST hint the way the SQL path does -- `<`/`>` on the extracted
    # values already compare by their own types.
    ordering = effective_order_by(resolve_order_by(spec, order_by))
    keyed = _sort_matches(db, matches, ordering, spec)

    if after is not None:
        if len(after) != len(ordering):
            raise QueryError(
                f"after cursor has {len(after)} values, expected "
                f"{len(ordering)} "
                f"({', '.join(order_by_key(ob.column) for ob in ordering)})"
            )
        keyed = [(key, obj) for key, obj in keyed if _matches_keyset(key, after, ordering)]

    matches = [obj for _, obj in keyed]
    if limit is not None:
        matches = matches[:limit]

    if select is not None:
        # Resolve exactly as the SQL path's `compile_query` does, rather
        # than whitelist-checking strings here: a path entry
        # ("birth.place.title") has to mean the same thing on both paths.
        # `resolve_ref_string` still rejects everything `check_columns`
        # rejected -- a flat column against `spec.columns`, a JSON path
        # against the type's own Gramps schema -- just with a better error.
        columns = [
            resolve_select_ref_string(spec, column) if isinstance(column, str) else column
            for column in select
        ]
        return [
            tuple(resolve_column_ref(db, obj, column, spec) for column in columns)
            for obj in matches
        ]
    return matches
