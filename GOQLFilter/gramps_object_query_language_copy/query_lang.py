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

"""An "almost Python" expression language, parsed into `object_query.py`'s
JSON `where` shape -- e.g. `"primary_name.surname_list[0].surname == 'Smith'"`
becomes `[{"column": {"json_path": [...]}, "op": "eq", "value": "Smith"}]`.

Uses `ast.parse(expr, mode="eval")` as pure syntax, never `eval()` or
`compile()` -- the tree is inspected and translated node-by-node into plain
JSON, never executed. Safety comes from whitelisting node *shapes*, not
blacklisting names: any AST node this module doesn't explicitly recognize
(function calls other than the whitelisted `like(...)`/`regex(...)`/
`any(...)`/`len(...)` forms, lambdas, attribute access building toward
dunder names, imports, walrus, f-strings, ...) is rejected by
`_translate_*` simply never handling it and falling through to a
`QueryLangError`.

The one exception to "parsed, never rewritten": `any(cond for x in rel [if
...])` and `len([... for x in rel if ...])` are comprehension *sugar* for
`exists(rel, cond)`/`count(rel, cond)`, desugared by a dedicated AST pass
(`_desugar_comprehensions`, see the "comprehension sugar" section below)
before any `_translate_*` function runs -- every other comprehension shape
(bare `[...]`/`{...}`/`{...: ...}`, more than one `for` clause, tuple-unpack
targets, ...) still falls through to the same `QueryLangError` any other
unrecognized node shape gets.

Deliberately not wired to any HTTP endpoint yet -- see `query.py`'s
`JsonPath`, which followed the same build-it-standalone-first,
wire-it-up-later path this session.

Current scope, matching what `object_query.py`'s wire format actually
supports today:

- Top level is a boolean expression of comparisons combined with `and`/`or`/
  `not`, nested however Python's own precedence and grouping resolves it
  (`not` binds tightest, then `and`, then `or`, and parentheses group as
  usual) -- `not a == b and c > d or e == f` parses the same way real
  Python would. The wire shape stays a flat list of leaf conditions,
  implicitly AND'd, for any expression that doesn't use `or`/`not` at all
  -- byte-identical to before either was supported. An expression that
  does use them gets an `{"or": [...]}`/`{"and": [...]}`/`{"not": node}`
  node in place of a leaf wherever it's needed -- see
  `_translate_top_level`/`_translate_bool_or_leaf`.
- A comparison is `OPERAND OP OPERAND` where `OP` is one of
  `== != < <= > >=`, `is`/`is not`, or Python's `in`/`not in`
  (`path in [v1, v2, ...]`) -- these are all the same `ast.Compare` node
  shape, just different `ops`. `is`/`is not` are pure sugar for `==`/`!=`
  (no notion of object identity here, only value equality) and `not in`
  is pure sugar for wrapping `in`'s own translation in `{"not": ...}` --
  none of the three introduce a new wire shape.
- Either side of `==`/`!=`/`</`/`<=`/`>`/`>=` may be the path and the other
  the value -- `5 < gender` and `gender > 5` compile to the identical wire
  node, via `_FLIP_OP` (`lt`<->`gt`, `lte`<->`gte`, `eq`/`ne` unchanged) --
  the wire shape always renders the path as `"column"`, regardless of which
  side of the source expression it was written on. `count(...)` stays an
  exception on purpose: it's only ever recognized when it's *the* left-hand
  operand, per its own left-hand-side-only v1 scope (see
  `_translate_column_or_count`) -- `2 < count(children)` doesn't flip into
  a supported shape, unlike `2 < gender`.
- `in` has a second shape too: `'substring' in path` (a string literal on
  the left, a path on the right) is a plain substring test (`Contains`),
  disambiguated from `path in [...]` purely by the right-hand node's shape
  (`ast.List` vs. a path) -- the same `ast.Compare`/`ast.In` node either way.
- `like(path, 'pattern%')` and `regex(path, 'pattern')` are whitelisted
  function-call forms, for the two operators (`Like`, `Regex`) that aren't
  Python operators.
- A path is a bare identifier optionally followed by `.attr` / `[index]`
  segments, e.g. `gender` or `primary_name.surname_list[0].surname`.
  Single-segment paths that match the target type's flat column whitelist
  resolve to a plain column reference (a real indexed SQL column); every
  other path becomes a `{"json_path": [...]}` reference.
- On the *value* side of a comparison, `ClassName.CONST` (e.g. `Person.MALE`,
  `Note.FLOWED`, `Date.MOD_ABOUT`, `EventType.BIRTH`) resolves to the real
  value read off the actual Gramps class -- see `_CONSTANTS` -- so
  `gender == Person.MALE` and `gender == 1` compile identically. Only a
  `Name.Attribute` shape one level deep is recognized (not `a.b.CONST`).
  Covers both flat-column fields (`Person.gender`, `Citation.confidence`,
  `Note.format`) and fields that only live nested in `json_data`
  (`birth.date.modifier == Date.MOD_ABOUT`, `type.value == EventType.BIRTH`)
  -- the constant class list is unrelated to where the field it's compared
  against happens to live.
- Also on the value side, `Date('Jan 1, 1968')` -- another whitelisted call
  form -- parses a human date string with Gramps' own
  date parser and resolves to `.sortval`, a plain comparable integer
  (Julian day number), so `event.date.sortval >= Date('Jan 1, 1968')` and
  `birth.date.sortval >= Date('Jan 1, 1968')` both work with ordinary
  `>=`/`<=`/`<`/`>`.
- A path may cross a relationship, not just index into one column's own
  `json_data` -- `birth`/`death` (`Person` -> `Event`), `father`/`mother`
  (`Family` -> `Person`), `place` (`Event` -> `Place`) are resolved by
  `query.py`'s `resolve_column_path()`, which this module's path
  translation defers to entirely (see `_translate_column`) rather than
  duplicating any relationship knowledge here. `birth.date.sortval`,
  `father.surname`, and `birth.place.title` are all valid paths this way.
"""

from __future__ import annotations

import ast
from typing import Any, List, Sequence, Tuple, Union

from gramps.gen.datehandler import parser as _date_parser
from gramps.gen.lib import (
    AttributeType,
    ChildRefType,
    Citation,
    Date,
    EventRoleType,
    EventType,
    FamilyRelType,
    MarkerType,
    NameOriginType,
    NameType,
    Note,
    NoteType,
    Person,
    PlaceType,
    RepositoryType,
    SourceMediaType,
    SrcAttributeType,
    StyledTextTagType,
    UrlType,
)

from .query import (
    CITATION,
    EVENT,
    FAMILY,
    MEDIA,
    NOTE,
    PERSON,
    PLACE,
    REPOSITORY,
    SOURCE,
    TAG,
    And,
    BacklinkClassFilter,
    Backlinks,
    CollectionCount,
    ColumnRef,
    Contains,
    Eq,
    Exists,
    FlatColumnRef,
    Gt,
    Gte,
    In,
    Like,
    Lt,
    Lte,
    Ne,
    Not,
    ObjectTypeSpec,
    Or,
    QueryError,
    Regex,
    SelectRef,
    default_ref_key,
    resolve_collection,
    resolve_column_path,
    resolve_ref_string,
)

# Namespace -> ObjectTypeSpec. Both the lowercase form and the actual Gramps
# class-name casing (Person, Family, ...) are accepted; no single-letter
# aliases -- those aren't what was asked for, and Gramps' own gramps_id
# prefixes (P = Place, I = Person, ...) don't line up with the object names
# anyway, so a letter scheme here would just invite confusion.
_NAMES = {
    "person": PERSON,
    "family": FAMILY,
    "event": EVENT,
    "place": PLACE,
    "repository": REPOSITORY,
    "source": SOURCE,
    "citation": CITATION,
    "media": MEDIA,
    "note": NOTE,
    "tag": TAG,
}
_NAMESPACES: dict[str, ObjectTypeSpec] = {
    **_NAMES,
    **{name.capitalize(): spec for name, spec in _NAMES.items()},
}

# `ClassName.CONST` value constants, e.g. `gender == Person.MALE`,
# `type.value == EventType.BIRTH`, `birth.date.modifier == Date.MOD_ABOUT`.
# Values are read off the real Gramps classes, never hardcoded, so they
# can't drift out of sync with core if a constant's underlying value ever
# changes -- see `_int_constants`. Covers both constants that attach to a
# *flat* column (`Person.gender`, `Citation.confidence`, `Note.format`) and
# ones that only live nested in `json_data` (`Event.type` is stored as
# `{"_class": "EventType", "value": 12, "string": ""}`, so the constant is
# compared against `type.value`, not `type` itself) -- `_translate_constant`
# doesn't care which; that distinction is entirely in how the *path* side of
# the comparison resolves (`resolve_column_path`).
#
# Deliberately still not covering arbitrary user-defined custom type values
# (a `PlaceType` of "Ranch", say) -- those have no fixed constant to name in
# the first place, only ever a per-tree string paired with `.CUSTOM`.
_CONSTANT_CLASSES: dict[str, type] = {
    "Person": Person,
    "Citation": Citation,
    "Note": Note,
    "Date": Date,
    "AttributeType": AttributeType,
    "ChildRefType": ChildRefType,
    "EventRoleType": EventRoleType,
    "EventType": EventType,
    "FamilyRelType": FamilyRelType,
    "MarkerType": MarkerType,
    "NameOriginType": NameOriginType,
    "NameType": NameType,
    "NoteType": NoteType,
    "PlaceType": PlaceType,
    "RepositoryType": RepositoryType,
    "SourceMediaType": SourceMediaType,
    "SrcAttributeType": SrcAttributeType,
    "StyledTextTagType": StyledTextTagType,
    "UrlType": UrlType,
}


def _int_constants(cls: type) -> dict[str, int]:
    """Every ALL_CAPS `int` class attribute on `cls`, e.g. `{"MALE": 1,
    "FEMALE": 0, ...}` for `Person`.

    Auto-derived rather than hand-listed so a new constant added to a
    Gramps class (or the value of an existing one changing) shows up here
    automatically instead of silently drifting out of sync. `bool` is
    excluded despite being an `int` subclass -- no Gramps class defines a
    meaningful all-caps boolean constant, and including it would risk
    picking up something like a stray `True`/`False` class attribute as if
    it were a real value.
    """
    return {
        name: value
        for name in dir(cls)
        if name.isupper() and not name.startswith("_")
        for value in [getattr(cls, name)]
        if isinstance(value, int) and not isinstance(value, bool)
    }


_CONSTANTS: dict[str, dict[str, Any]] = {
    class_name: _int_constants(cls) for class_name, cls in _CONSTANT_CLASSES.items()
}


class QueryLangError(ValueError):
    """Raised when an expression doesn't parse or uses unsupported syntax."""


def resolve_namespace(namespace: str) -> ObjectTypeSpec:
    """Look up the `ObjectTypeSpec` for a namespace string (`"person"` or `"Person"`, ...)."""
    try:
        return _NAMESPACES[namespace]
    except KeyError:
        raise QueryLangError(f"unknown namespace: {namespace!r}") from None


def _translate_constant(class_name: str, const_name: str) -> Any:
    try:
        constants = _CONSTANTS[class_name]
    except KeyError:
        raise QueryLangError(
            f"unknown constant namespace: {class_name!r} "
            f"(known: {', '.join(sorted(_CONSTANTS))})"
        ) from None
    try:
        return constants[const_name]
    except KeyError:
        raise QueryLangError(
            f"unknown constant: {class_name}.{const_name} "
            f"(known: {', '.join(class_name + '.' + n for n in constants)})"
        ) from None


_FLIP_OP: dict[str, str] = {
    # For "value OP field" (the literal written on the left, e.g.
    # "Date(...) < mother.birth.sortval") -- the wire shape always puts the
    # column first, so the operator has to flip to keep the same meaning:
    # "A < B" becomes "B > A" once B (the field) is what's rendered as
    # "column". eq/ne are symmetric and flip to themselves.
    "eq": "eq",
    "ne": "ne",
    "lt": "gt",
    "lte": "gte",
    "gt": "lt",
    "gte": "lte",
}


_COMPARE_OPS: dict[type, str] = {
    ast.Eq: "eq",
    ast.NotEq: "ne",
    ast.Lt: "lt",
    ast.LtE: "lte",
    ast.Gt: "gt",
    ast.GtE: "gte",
    ast.In: "in",
    # `is`/`is not` are pure sugar for `==`/`!=` here -- this language has no
    # notion of object identity distinct from value equality, so `gender is
    # None` and `gender == None` compile to the exact same wire node. Reusing
    # "eq"/"ne" verbatim (rather than a dedicated "is"/"is not" wire op) means
    # every existing "eq"/"ne" code path -- field-vs-field, count(...), the
    # SQL/evaluator dialects -- already handles them with no new branches.
    ast.Is: "eq",
    ast.IsNot: "ne",
}


def _translate_path(node: ast.AST) -> List[Union[str, int]]:
    """Walk a `Name`/`Attribute`/`Subscript` chain into an ordered segment list.

    `a.b[0].c` is nested as `Attribute(Attribute(Subscript(Attribute(Name)))...)`
    with the outermost node being the *last* segment -- recurse to the base
    `Name` first, then build the list root-to-leaf.
    """
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return _translate_path(node.value) + [node.attr]
    if isinstance(node, ast.Subscript):
        index_node = node.slice
        if not isinstance(index_node, ast.Constant) or not isinstance(
            index_node.value, int
        ) or isinstance(index_node.value, bool):
            raise QueryLangError(
                f"subscript index must be a plain integer literal: {ast.dump(node)}"
            )
        return _translate_path(node.value) + [index_node.value]
    raise QueryLangError(f"invalid path expression: {ast.dump(node)}")


def _translate_column(node: ast.AST, spec: ObjectTypeSpec) -> Union[str, dict]:
    """Translate a path into a wire column reference: a plain string if it's
    a single segment matching a real flat column, `{"json_path": [...]}`
    otherwise.

    No relationship-specific knowledge lives here -- a multi-segment path
    like `birth.date.sortval` or `father.surname` becomes
    `{"json_path": ["birth", "date", "sortval"]}` the same way any other
    multi-segment path does; `object_query.py`'s `_parse_column_ref` is
    what actually recognizes `"birth"`/`"father"`/etc. as relationship
    roots (via `query.py`'s `resolve_column_path`) once it receives that
    wire form. A bare relationship name with nothing after it
    (`"birth"` alone) isn't a real flat column, so it falls through to
    `{"json_path": ["birth"]}` here too -- `resolve_column_path` rejects
    that with a clear error downstream, just one layer later than a
    dedicated check here would.
    """
    segments = _translate_path(node)
    if len(segments) == 1 and isinstance(segments[0], str) and segments[0] in spec.columns:
        return segments[0]
    return {"json_path": segments}


def _translate_count_call(node: ast.Call, spec: ObjectTypeSpec) -> dict:
    """Translate `count(relationship[, condition])` into
    `{"count_of": {"relationship": ..., "where": [...]}}` -- the *value*-
    producing counterpart to `exists(...)`'s leaf-producing
    `_translate_exists_call`. Appears as a comparison's column
    (`count(children) > 2`), never as a leaf on its own -- a bare
    `count(children)` with no comparison isn't a boolean, so it's rejected
    the same way a bare path (`gender`, with no `== ...`) already is.

    `relationship`/`condition` resolve exactly like `exists(...)`'s do --
    same `resolve_collection` lookup, same recursive `_translate_top_level`
    against the collection's target type for the optional condition (or,
    for `Backlinks`, `_translate_backlinks_condition` -- see
    `_translate_exists_call`'s own docstring).
    """
    if not 1 <= len(node.args) <= 2 or node.keywords:
        raise QueryLangError(
            "count(relationship[, condition]) takes 1 or 2 positional arguments"
        )
    name_node = node.args[0]
    if not isinstance(name_node, ast.Name):
        raise QueryLangError(
            f"count(...)'s first argument must be a bare relationship name: "
            f"{ast.dump(name_node)}"
        )
    try:
        collection = resolve_collection(spec, name_node.id)
    except QueryError as error:
        raise QueryLangError(str(error)) from error
    payload: dict = {"relationship": name_node.id}
    if len(node.args) == 2:
        if isinstance(collection, Backlinks):
            payload["where"] = [_translate_backlinks_condition(node.args[1])]
        else:
            payload["where"] = _translate_top_level(node.args[1], collection.target)
    return {"count_of": payload}


def _is_count_call(node: ast.AST) -> bool:
    """Is `node` a `count(...)` call, without translating it? Used to
    classify a comparison's operand as column-like *before* deciding how to
    translate it -- see `_translate_compare`'s left/right classification.
    """
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "count"


def _translate_column_or_count(node: ast.AST, spec: ObjectTypeSpec) -> Union[str, dict]:
    """A comparison's column-like side: an ordinary path (`_translate_column`),
    or a `count(...)` call -- the one place a "column" can be a *computed*
    value rather than a path, verbatim. `count(...)` is deliberately not
    recognized anywhere `_translate_column` itself is called directly (a
    plain field on the other side of a comparison, `'in'`'s list/substring
    branches) -- v1 scope only ever treats `count(...)` as *the* column,
    never as something compared against another field, matching `len()`'s
    own planned restriction (see ROADMAP.md).
    """
    if _is_count_call(node):
        return _translate_count_call(node, spec)
    return _translate_column(node, spec)


def _translate_date_call(node: ast.Call) -> int:
    """Translate `Date('Jan 1, 1968')` into its `.sortval` (a comparable
    Julian day number), via Gramps' own date parser -- not a custom one.
    """
    if len(node.args) != 1 or node.keywords:
        raise QueryLangError("Date(...) takes exactly 1 positional string argument")
    text = _translate_value(node.args[0])
    if not isinstance(text, str):
        raise QueryLangError("Date(...)'s argument must be a string literal")
    parsed = _date_parser.parse(text)
    if not parsed.is_valid():
        raise QueryLangError(f"could not parse {text!r} as a date")
    return parsed.sortval


def _translate_value(node: ast.AST) -> Any:
    """Translate a literal: string / int / float / bool / None, `-<number>`,
    a `ClassName.CONST` value constant (e.g. `Person.MALE`, see `_CONSTANTS`),
    or `Date('...')` (see `_translate_date_call`).
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _translate_value(node.operand)
        if not isinstance(inner, (int, float)) or isinstance(inner, bool):
            raise QueryLangError(f"unary '-' only supported on numeric literals: {ast.dump(node)}")
        return -inner
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return _translate_constant(node.value.id, node.attr)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Date"
    ):
        return _translate_date_call(node)
    raise QueryLangError(f"invalid literal: {ast.dump(node)}")


def _translate_list(node: ast.AST) -> List[Any]:
    if not isinstance(node, ast.List):
        raise QueryLangError(f"expected a list literal, e.g. [1, 2, 3]: {ast.dump(node)}")
    return [_translate_value(elt) for elt in node.elts]


def _is_path_node(node: ast.AST) -> bool:
    """Is `node` a path reference (`Name`/`Attribute`/`Subscript` chain),
    rather than a literal/`Date(...)`/`ClassName.CONST`?

    The one ambiguous shape is a single-level `Attribute(Name, attr)` --
    `Person.MALE` (a constant) and `father.surname` (a path) look
    identical syntactically. Disambiguated the same way `_translate_value`
    already does: whether the base `Name` is a known constant class
    (`_CONSTANT_CLASSES`). Anything deeper (`a.b.c`, `a[0].b`) is
    unambiguously a path -- that shape is never valid for a constant
    (`_translate_value` only recognizes exactly one `Attribute` level).
    """
    if isinstance(node, (ast.Name, ast.Subscript)):
        return True
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id in _CONSTANT_CLASSES:
            return False
        return True
    return False


def _translate_compare(node: ast.Compare, spec: ObjectTypeSpec) -> dict:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        # `a < b < c` -- Python allows chained comparisons, desugaring to
        # pairwise "and": `a < b and b < c` (real Python evaluates each
        # operand at most once; this translator only ever reads a path's
        # *value* at query time, never re-evaluates a Python expression, so
        # that subtlety doesn't apply here -- splitting into independent
        # legs is exactly equivalent). Each leg is an ordinary two-term
        # `ast.Compare`, translated by recursing into this same function --
        # chaining introduces no new comparison semantics of its own, so
        # every leg transparently supports whatever a plain comparison
        # already does (operand ordering, is/is not/in, field-vs-field,
        # even mixed operators like `1 < gender != 3`).
        operands = [node.left, *node.comparators]
        legs = [
            ast.Compare(left=left, ops=[op], comparators=[right])
            for left, op, right in zip(operands, node.ops, operands[1:])
        ]
        return {"and": [_translate_compare(leg, spec) for leg in legs]}
    op_type = type(node.ops[0])
    # "not in" reuses "in"'s own translation below verbatim, then wraps the
    # result in "not" at the very end -- `not (x in y)` already compiles and
    # evaluates correctly (see Done above: the Not/missing-value three-valued
    # logic fix), so there's no new semantics to add here, just sugar for a
    # shape users could already write with explicit parens.
    negate = op_type is ast.NotIn
    lookup_type = ast.In if negate else op_type
    if lookup_type not in _COMPARE_OPS:
        raise QueryLangError(
            f"unsupported comparison operator {op_type.__name__!r} "
            "(supported: == != < <= > >= is 'is not' in 'not in')"
        )
    op = _COMPARE_OPS[lookup_type]
    rhs = node.comparators[0]
    if op == "in":
        if isinstance(rhs, ast.List):
            # "field in [v1, v2, ...]" -- list membership.
            column = _translate_column_or_count(node.left, spec)
            value = _translate_list(rhs)
            if not value:
                raise QueryLangError("'in' requires a non-empty list")
            leaf = {"column": column, "op": "in", "value": value}
        elif _is_path_node(rhs):
            # "'substring' in field" / "other_field in field" -- a plain
            # substring test, mirroring what `in` already means for two real
            # Python strings. The field being searched is on the *right*
            # here (unlike every other operator), since that's what makes
            # `'Jan' in given_name` read the same as it would in real Python.
            column = _translate_column(rhs, spec)
            if _is_path_node(node.left):
                # "other_field in field" -- field-vs-field: the needle is
                # itself a path, only known at query execution time, not a
                # literal to bind now.
                value_column = _translate_column(node.left, spec)
                leaf = {"column": column, "op": "contains", "value_column": value_column}
            else:
                substring = _translate_value(node.left)
                if not isinstance(substring, str):
                    raise QueryLangError(
                        "'... in path' (substring test) requires a string literal "
                        "or a field path on the left, e.g. \"'Jan' in given_name\" "
                        f"or \"nickname in given_name\": {ast.dump(node)}"
                    )
                leaf = {"column": column, "op": "contains", "value": substring}
        else:
            raise QueryLangError(
                "'in' requires either a list literal ('field in [1, 2]') or a "
                f"field path on the right ('... in field', a substring test): {ast.dump(node)}"
            )
    else:
        left = node.left
        if _is_path_node(left) or _is_count_call(left):
            # "field OP value" / "field OP field" -- the shape this function
            # always assumed until operand-ordering was generalized. `left`
            # is the column (or `count(...)`); `rhs` is either another field
            # (`value_column`) or an ordinary value.
            column = _translate_column_or_count(left, spec)
            if _is_path_node(rhs):
                if isinstance(column, dict) and "count_of" in column:
                    # count(...) is left-hand-side-only, against a literal (v1
                    # scope, see ROADMAP.md) -- field-vs-field against a count
                    # isn't supported, so reject explicitly rather than
                    # silently building a value_column nothing downstream
                    # can render.
                    raise QueryLangError(
                        f"count(...) only supports comparison against a literal value, "
                        f"not a field: {ast.dump(node)}"
                    )
                # Field-vs-field: "families where mother.death.date.sortval <
                # father.death.date.sortval" -- the right-hand side is itself
                # a path, not a value to bind.
                value_column = _translate_column(rhs, spec)
                leaf = {"column": column, "op": op, "value_column": value_column}
            else:
                value = _translate_value(rhs)
                leaf = {"column": column, "op": op, "value": value}
        elif _is_path_node(rhs):
            # "value OP field", e.g. "Date('Jan 1, 1968') < mother.birth.sortval"
            # -- the literal happened to be written on the left. Flip the
            # operator so the column still renders on the wire's left, the
            # one shape query.py/evaluator.py know how to read -- count(...)
            # is deliberately not accepted here (see
            # `_translate_column_or_count`'s docstring): only a plain path
            # qualifies as "the column" on this side, matching count(...)'s
            # existing left-hand-side-only v1 scope untouched.
            value = _translate_value(left)
            column = _translate_column(rhs, spec)
            leaf = {"column": column, "op": _FLIP_OP[op], "value": value}
        else:
            raise QueryLangError(
                "a comparison must have a field path on at least one side "
                f"(count(...) is only supported on the left): {ast.dump(node)}"
            )
    return {"not": leaf} if negate else leaf


def _translate_like_call(node: ast.Call, spec: ObjectTypeSpec) -> dict:
    if len(node.args) != 2 or node.keywords:
        raise QueryLangError("like(path, 'pattern') takes exactly 2 positional arguments")
    column = _translate_column(node.args[0], spec)
    pattern = _translate_value(node.args[1])
    if not isinstance(pattern, str):
        raise QueryLangError("like(...)'s second argument must be a string literal")
    return {"column": column, "op": "like", "value": pattern}


def _translate_regex_call(node: ast.Call, spec: ObjectTypeSpec) -> dict:
    if len(node.args) != 2 or node.keywords:
        raise QueryLangError("regex(path, 'pattern') takes exactly 2 positional arguments")
    column = _translate_column(node.args[0], spec)
    pattern = _translate_value(node.args[1])
    if not isinstance(pattern, str):
        raise QueryLangError("regex(...)'s second argument must be a string literal")
    return {"column": column, "op": "regex", "value": pattern}


def _translate_backlinks_condition(node: ast.AST) -> dict:
    """`exists(backlinks, ...)`/`count(backlinks, ...)`'s only supported
    condition shape: a single comparison against `_class`, the referrer's
    own class name (`_class == "Person"`) -- not routed through
    `_translate_compare`'s general and/or/field-path machinery at all,
    since there's no `ObjectTypeSpec` to validate a richer path against (a
    backlink's referrer can be any of the ten object types; see `query.py`'s
    `Backlinks`/`BacklinkClassFilter` docstrings). Chaining (`a < b < c`),
    field-vs-field, and substring/`in`-as-membership-on-a-path are all out
    of scope here on purpose -- only `_class`, `==`/`!=`/`is`/`is not`/`in`
    (folded straight to `"eq"`/`"ne"`/`"in"`, matching `_COMPARE_OPS` --
    `not in` isn't supported, there's no `{"not": ...}` wrapper for this
    leaf shape to unwrap, see `_backlink_condition_from_json`), and a
    string (or string-list, for `in`) literal.
    """
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        raise QueryLangError(
            f"exists(backlinks, ...)'s condition must be a single comparison "
            f"against _class, e.g. _class == \"Person\": {ast.dump(node)}"
        )
    op = _COMPARE_OPS.get(type(node.ops[0]))
    if op not in ("eq", "ne", "in"):
        raise QueryLangError(
            f"_class only supports ==, !=, is, 'is not', in -- not "
            f"{type(node.ops[0]).__name__!r}: {ast.dump(node)}"
        )

    def _is_class_name(candidate: ast.AST) -> bool:
        return isinstance(candidate, ast.Name) and candidate.id == "_class"

    left, rhs = node.left, node.comparators[0]
    if op == "in":
        if not _is_class_name(left):
            raise QueryLangError(
                f"'in' needs _class on the left, e.g. "
                f"_class in [\"Person\", \"Family\"]: {ast.dump(node)}"
            )
        values = _translate_list(rhs)
        if not values or not all(isinstance(v, str) for v in values):
            raise QueryLangError(
                f"_class in [...] needs a non-empty list of string literals: {ast.dump(node)}"
            )
        return {"column": "_class", "op": "in", "value": values}
    if _is_class_name(left):
        value_node = rhs
    elif _is_class_name(rhs):
        value_node = left
        op = _FLIP_OP[op]  # eq/ne flip to themselves -- kept for consistency with every other comparison
    else:
        raise QueryLangError(
            f"exists(backlinks, ...)'s condition must compare _class, the "
            f"referring object's own type: {ast.dump(node)}"
        )
    value = _translate_value(value_node)
    if not isinstance(value, str):
        raise QueryLangError(
            f"_class must be compared against a string literal: {ast.dump(node)}"
        )
    return {"column": "_class", "op": op, "value": value}


def _translate_exists_call(node: ast.Call, spec: ObjectTypeSpec) -> dict:
    """Translate `exists(relationship[, condition])` into
    `{"exists": {"relationship": ..., "where": [...]}}` -- `where` omitted
    entirely when no condition is given (`exists(children)`, "at least one
    related row at all").

    `relationship`'s target type comes from `query.py`'s `_COLLECTIONS`
    registry (via `resolve_collection`), the same way a `_RELATIONSHIPS`
    name's target drives `resolve_column_path` -- `condition`, if given, is
    itself a full `where_expr` boolean expression, just parsed against that
    target type instead of `spec`, via the same `_translate_top_level` this
    module already uses for the top-level expression. `Backlinks` (see
    `resolve_collection`'s own docstring) has no such target type, so its
    `condition` goes through `_translate_backlinks_condition` instead,
    wrapped in a single-element list to match `_translate_top_level`'s own
    `List[dict]` shape.
    """
    if not 1 <= len(node.args) <= 2 or node.keywords:
        raise QueryLangError(
            "exists(relationship[, condition]) takes 1 or 2 positional arguments"
        )
    name_node = node.args[0]
    if not isinstance(name_node, ast.Name):
        raise QueryLangError(
            f"exists(...)'s first argument must be a bare relationship name: "
            f"{ast.dump(name_node)}"
        )
    try:
        collection = resolve_collection(spec, name_node.id)
    except QueryError as error:
        raise QueryLangError(str(error)) from error
    payload: dict = {"relationship": name_node.id}
    if len(node.args) == 2:
        if isinstance(collection, Backlinks):
            payload["where"] = [_translate_backlinks_condition(node.args[1])]
        else:
            payload["where"] = _translate_top_level(node.args[1], collection.target)
    return {"exists": payload}


def _translate_comparison_like_node(node: ast.AST, spec: ObjectTypeSpec) -> dict:
    """A single leaf: a `Compare`, or a whitelisted
    `like(...)`/`regex(...)`/`exists(...)` call."""
    if isinstance(node, ast.Compare):
        return _translate_compare(node, spec)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "like":
            return _translate_like_call(node, spec)
        if node.func.id == "regex":
            return _translate_regex_call(node, spec)
        if node.func.id == "exists":
            return _translate_exists_call(node, spec)
    raise QueryLangError(
        f"expected a comparison (a == b, a in [...], like(a, 'pat'), "
        f"regex(a, 'pat'), exists(rel, cond)), got: {ast.dump(node)}"
    )


def _translate_bool_or_leaf(node: ast.AST, spec: ObjectTypeSpec) -> dict:
    """Translate one node of a (possibly nested) boolean expression: a leaf
    comparison/`like(...)` call, or an `and`/`or`/`not` of further such nodes.

    `ast.parse` has already resolved Python's own `and`/`or`/`not`
    precedence and grouping into correctly nested `BoolOp`/`UnaryOp` nodes
    (`not` binds tighter than `and`, which binds tighter than `or`, so
    `not a and b or c` arrives as `BoolOp(Or, [BoolOp(And, [UnaryOp(Not, a),
    b]), c])`) -- this only walks whatever shape it's handed, it doesn't
    re-implement precedence itself. Any other `ast.UnaryOp` (`+a`, `~a`) has
    no case here and falls through to `_translate_comparison_like_node`,
    which rejects it with a clear error, the same as any other unrecognized
    node shape.
    """
    if isinstance(node, ast.BoolOp):
        key = "and" if isinstance(node.op, ast.And) else "or"
        return {key: [_translate_bool_or_leaf(value, spec) for value in node.values]}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return {"not": _translate_bool_or_leaf(node.operand, spec)}
    return _translate_comparison_like_node(node, spec)


def _translate_top_level(node: ast.AST, spec: ObjectTypeSpec) -> List[dict]:
    """The whole expression, translated to `parse_expr`'s public shape: a
    list of nodes, implicitly AND'd together.

    A top-level `{"and": [...]}` -- i.e. any expression that doesn't use
    `or`/`not` at all, including a single bare comparison -- is unwrapped
    back into a flat list here, so the wire shape for those expressions is
    exactly what it was before `or`/`not` support existed. An expression
    that does use them produces a list containing an `{"or": [...]}"`/
    `{"not": node}` node (alongside plain leaves too, e.g. `"(a or b) and
    c"` -> `[{"or": [a, b]}, c]`), rather than changing the top-level shape
    from a list to something else.
    """
    translated = _translate_bool_or_leaf(node, spec)
    if isinstance(translated, dict) and tuple(translated) == ("and",):
        return translated["and"]
    return [translated]


# --- comprehension sugar for exists(...)/count(...) -------------------------
#
# `any(cond for x in rel)`/`len([... for x in rel if cond])` are pure syntax
# sugar for `exists(rel, cond)`/`count(rel, cond)` -- rewritten away entirely
# by `_ComprehensionDesugarer` before `_translate_top_level` ever runs, so
# every `_translate_*` function above keeps treating `exists(...)`/`count(...)`
# as the only call shapes that carry a nested condition. Nothing downstream of
# this section knows comprehension syntax was ever involved.
#
# The one piece of real work is dropping the loop variable: `where_expr`'s
# `exists`/`count` condition is parsed directly against the collection's
# target type, with no loop-variable prefix of its own (`exists(children,
# given_name == 'Steve')`, not `exists(children, c.given_name == 'Steve')`),
# so `c.given_name` has to become plain `given_name` -- `_BoundNameStripper`
# does exactly that, once per comprehension level.


class _BoundNameStripper(ast.NodeTransformer):
    """Rewrites a comprehension body so every `<bound_name>.attr` /
    `<bound_name>[i]` chain drops its `<bound_name>` root -- `c.given_name`
    becomes plain `given_name`, `c.events` becomes plain `events` (so a
    *nested* comprehension's already-desugared `exists(c.events, ...)`/
    `count(c.events, ...)` call, produced one level down, loses its `c.`
    prefix too -- this is a blind syntactic substitution, indifferent to
    what's inside, so it composes correctly across nesting levels without
    a symbol table).

    A bare reference to `bound_name` with nothing after it (`c == x`, `c in
    [...]`) has no equivalent -- `where_expr` conditions are always a field
    path, never "the whole related object" -- so that's rejected with a
    clear error rather than silently dropped.

    Reusing the same loop-variable name at two nesting levels (`any(any(c.a
    == 1 for c in c.rel) for c in top)`) works correctly without this class
    needing to track more than one name at a time: the *inner*
    `_BoundNameStripper` runs first (`_ComprehensionDesugarer` desugars
    bottom-up) and either strips or errors on every reference to its own
    `c` within its own `elt`/`ifs`, so nothing referring to "the inner `c`"
    can survive unconsumed into the outer pass -- any `c` the outer stripper
    later encounters (e.g. in the inner-produced call's own collection-name
    argument) unambiguously belongs to the outer scope, exactly matching
    real Python's own scoping rule that a comprehension's first `for`
    clause's `iter` is evaluated in the *enclosing* scope.
    """

    def __init__(self, bound_name: str):
        self.bound_name = bound_name

    def _is_own_root(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id == self.bound_name

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if self._is_own_root(node.value):
            return ast.copy_location(ast.Name(id=node.attr, ctx=ast.Load()), node)
        node.value = self.visit(node.value)
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        if self._is_own_root(node.value):
            raise QueryLangError(
                f"can't index the loop variable directly: {ast.dump(node)}"
            )
        node.value = self.visit(node.value)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id == self.bound_name:
            raise QueryLangError(
                f"'{self.bound_name}' can only be used as '{self.bound_name}.field', "
                f"never compared directly (there's no whole-object comparison in "
                f"where_expr, only field paths): {ast.dump(node)}"
            )
        return node

    def _reject_nested_comprehension(self, node: ast.AST) -> ast.AST:
        # By the time a condition reaches this stripper, any comprehension
        # nested inside it should already have been rewritten into an
        # `exists(...)`/`count(...)` call by `_ComprehensionDesugarer`
        # running bottom-up -- a raw comprehension surviving to this point
        # means it wasn't wrapped in a recognized `any(...)`/`len(...)`
        # form, the same "not a whitelisted shape" rejection every other
        # unrecognized node gets.
        raise QueryLangError(
            f"comprehension must be wrapped in any(...) or len([...]): {ast.dump(node)}"
        )

    visit_GeneratorExp = _reject_nested_comprehension
    visit_ListComp = _reject_nested_comprehension
    visit_SetComp = _reject_nested_comprehension
    visit_DictComp = _reject_nested_comprehension


def _comprehension_generator(comp: Union[ast.GeneratorExp, ast.ListComp], call: ast.Call) -> ast.comprehension:
    """Validate and return the single `for x in rel` clause of a
    comprehension being desugared -- `call` is only used for error messages
    (the original `any(...)`/`len(...)` call, more useful to a caller than
    the comprehension fragment alone).

    Restricted on purpose to exactly what `exists(...)`/`count(...)` already
    support written by hand: one loop variable, bound to a plain name (not a
    tuple-unpack), iterating either a bare collection name (`children`) or
    exactly one attribute off an *enclosing* comprehension's own loop
    variable (`c.events`, matching how `exists(children, exists(events,
    ...))` nests today) -- never a longer chain, so this sugar can't
    silently become more expressive than the call syntax it stands in for.
    """
    if len(comp.generators) != 1:
        raise QueryLangError(
            f"comprehension must have exactly one 'for' clause: {ast.dump(call)}"
        )
    generator = comp.generators[0]
    if generator.is_async:
        raise QueryLangError(f"async comprehensions aren't supported: {ast.dump(call)}")
    if not isinstance(generator.target, ast.Name):
        raise QueryLangError(
            f"comprehension's loop variable must be a plain name: {ast.dump(call)}"
        )
    iter_node = generator.iter
    is_bare_name = isinstance(iter_node, ast.Name)
    is_one_attr_off_a_name = isinstance(iter_node, ast.Attribute) and isinstance(
        iter_node.value, ast.Name
    )
    if not (is_bare_name or is_one_attr_off_a_name):
        raise QueryLangError(
            "comprehension's 'in ...' must be a bare collection name, or exactly "
            f"one attribute off an enclosing loop variable: {ast.dump(call)}"
        )
    return generator


def _and_together(parts: List[ast.expr]) -> ast.expr:
    return parts[0] if len(parts) == 1 else ast.BoolOp(op=ast.And(), values=parts)


def _any_condition(comp: ast.GeneratorExp, bound_name: str) -> Union[ast.expr, None]:
    """`any(...)`'s condition: `elt` *is* the boolean predicate (unlike
    `len([...])`'s `elt`, which only ever projects), ANDed with any `if`
    clauses on the generator itself -- `any(x.a == 1 for x in rel if x.b ==
    2)` means the same as `any(x.a == 1 and x.b == 2 for x in rel)`. A bare
    `elt` that's just the loop variable itself (`any(x for x in rel if
    x.b == 2)`) carries no predicate of its own -- the condition is then
    whatever the `if` clauses provide alone (or `None`, "no condition at
    all", if there aren't any either -- `any(x for x in rel)` is just
    `exists(rel)`).
    """
    stripper = _BoundNameStripper(bound_name)
    parts = []
    if not (isinstance(comp.elt, ast.Name) and comp.elt.id == bound_name):
        parts.append(stripper.visit(comp.elt))
    parts.extend(stripper.visit(if_node) for if_node in comp.generators[0].ifs)
    return _and_together(parts) if parts else None


def _len_condition(comp: ast.ListComp, bound_name: str) -> Union[ast.expr, None]:
    """`len([...])`'s condition: unlike `any(...)`, `elt` here only ever
    *projects* what gets collected (traditionally into the list being
    measured), so it carries no predicate -- `len([x for x in rel if
    x.a == 1])` counts by its `if` clause alone. `elt` itself is required to
    be trivial (the loop variable, or a plain literal like `1`) so nothing
    meaningful is silently thrown away by ignoring it; anything else is
    rejected rather than guessed at.
    """
    elt = comp.elt
    if not (
        (isinstance(elt, ast.Name) and elt.id == bound_name)
        or isinstance(elt, ast.Constant)
    ):
        raise QueryLangError(
            "len([...])'s projection must be the loop variable or a plain "
            f"literal (e.g. 'len([1 for x in rel if ...])'): {ast.dump(elt)}"
        )
    stripper = _BoundNameStripper(bound_name)
    ifs = [stripper.visit(if_node) for if_node in comp.generators[0].ifs]
    return _and_together(ifs) if ifs else None


def _make_call(name: str, iter_node: ast.expr, condition: Union[ast.expr, None]) -> ast.Call:
    args = [iter_node] if condition is None else [iter_node, condition]
    return ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=args, keywords=[])


class _ComprehensionDesugarer(ast.NodeTransformer):
    """Rewrites `any(cond for x in rel [if ...])` into `exists(rel, cond)`,
    and `len([... for x in rel if ...])` into `count(rel, ...)`, run once
    over the whole tree before `_translate_top_level` -- see this section's
    module-level comment above.

    Runs bottom-up (`generic_visit` before inspecting the current node), so
    a comprehension nested inside another gets desugared first -- by the
    time the outer level's own condition is stripped of its loop variable
    (`_BoundNameStripper`), any inner `exists(...)`/`count(...)` call
    already sitting in it gets its own loop-variable prefix (`c.events` ->
    `events`) stripped along with everything else, with no special-casing
    needed for "this child happens to be a call I generated a moment ago."
    """

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if not isinstance(node.func, ast.Name) or node.keywords:
            return node
        name = node.func.id
        if name == "any":
            if len(node.args) != 1 or not isinstance(node.args[0], ast.GeneratorExp):
                raise QueryLangError(
                    "any(...) is only supported wrapping a generator comprehension, "
                    f"e.g. any(x.field == 1 for x in rel): {ast.dump(node)}"
                )
            comp = node.args[0]
            generator = _comprehension_generator(comp, node)
            condition = _any_condition(comp, generator.target.id)
            return ast.copy_location(_make_call("exists", generator.iter, condition), node)
        if name == "len":
            if len(node.args) != 1 or not isinstance(node.args[0], ast.ListComp):
                raise QueryLangError(
                    "len(...) is only supported wrapping a list comprehension, "
                    f"e.g. len([1 for x in rel if x.field == 1]): {ast.dump(node)}"
                )
            comp = node.args[0]
            generator = _comprehension_generator(comp, node)
            condition = _len_condition(comp, generator.target.id)
            return ast.copy_location(_make_call("count", generator.iter, condition), node)
        return node


def _desugar_comprehensions(node: ast.AST) -> ast.AST:
    rewritten = _ComprehensionDesugarer().visit(node)
    return ast.fix_missing_locations(rewritten)


def parse_expr_for_spec(spec: ObjectTypeSpec, expr: str) -> List[dict]:
    """Parse an "almost Python" expression against an already-known `ObjectTypeSpec`.

    For callers that already know their target type and don't need (or
    want) a namespace string -- e.g. `resources/object_query.py`'s
    `where_expr` field, where each endpoint's own `self.spec` already fixes
    the type; asking the client to also name it via a namespace string would
    be redundant. `parse_expr()` below is the namespace-string-based
    equivalent, for standalone/library use where there's no such context.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as error:
        raise QueryLangError(f"invalid syntax: {error}") from error
    body = _desugar_comprehensions(tree.body)
    return _translate_top_level(body, spec)


def parse_expr(namespace: str, expr: str) -> List[dict]:
    """Parse an "almost Python" expression into a `where` condition list.

    >>> parse_expr("person", "gender == 1")
    [{'column': 'gender', 'op': 'eq', 'value': 1}]

    >>> parse_expr("person", "primary_name.surname_list[0].surname == 'Smith'")
    [{'column': {'json_path': ['primary_name', 'surname_list', 0, 'surname']}, 'op': 'eq', 'value': 'Smith'}]

    The result is ready to drop directly into a `POST .../query/` request
    body's `"where"` field. Raises `QueryLangError` on anything outside the
    supported grammar -- never executes the input (`ast.parse` only, no
    `eval`/`compile`/`exec`).
    """
    spec = resolve_namespace(namespace)
    return parse_expr_for_spec(spec, expr)


# --- expr -> query.py AST ----------------------------------------------------
#
# `parse_expr`/`parse_expr_for_spec` stop at the JSON wire shape, since that's
# all `object_query.py`'s `where_expr` request field ever needs. A caller that
# wants to actually *run* a where-expression string (this module's tests, the
# docs, or any standalone/library use with a real `db` connection) needs that
# JSON turned into `query.py`'s `Eq`/`And`/`RelatedObject`-based AST instead --
# `compile_expr`/`compile_expr_for_spec` are that bridge, built entirely out of
# `query.py`'s own exported pieces (no new AST shape of its own).

_OP_CLASSES: dict[str, type] = {
    "eq": Eq,
    "ne": Ne,
    "lt": Lt,
    "lte": Lte,
    "gt": Gt,
    "gte": Gte,
}

# Every leaf `op` a condition dict can carry -- `_OP_CLASSES`'s keys plus
# "in"/"like"/"regex"/"contains" (special-cased in `_condition_from_json`, not
# plain `Comparison` subclasses). Public so `object_query.py`'s own
# `where`-body schema validates against this directly instead of a second,
# hand-copied whitelist that can (and did) drift -- new ops added here are
# then automatically valid for a raw `where` JSON body too, no
# gramps-web-api change needed (though gramps-web-api's own `value_column`
# restriction for "in"/"like"/"regex" is a separate, hand-maintained check --
# see its `_validate_leaf_condition`).
VALID_LEAF_OPS = frozenset(_OP_CLASSES) | {"in", "like", "regex", "contains"}


def json_column_to_ref(column: Union[str, dict], spec: ObjectTypeSpec) -> ColumnRef:
    """A wire-format column reference (plain string, `{"json_path": [...]}`,
    or `{"count_of": {...}}`), resolved to a `ColumnRef` -- via
    `resolve_column_path`, so a path crossing a relationship
    (`{"json_path": ["birth", "date", "sortval"]}`) becomes a `RelatedObject`
    the same way it would coming from `object_query.py`, not a literal
    `JsonPath(("birth", "date", "sortval"))` that would (harmlessly, but
    incorrectly) look for a `birth` key inside `json_data` instead.
    `{"count_of": {"relationship": ..., "where": [...]}}` resolves to a
    `CollectionCount` the same way `_node_from_json`'s `"exists"` case
    resolves to an `Exists` -- same `resolve_collection` lookup, same
    recursive `where_list_to_ast` for the optional condition (or, when
    `relationship` resolves to `Backlinks`, `_backlink_condition_from_json`
    instead -- see `_node_from_json`'s own docstring for why).

    A plain string goes through `resolve_ref_string`, so a *dotted* one
    (`"birth.date.sortval"`) means the same thing here as the identical
    text does inside a `where_expr`, rather than being rejected as an
    unknown flat column. A single-segment string stays a flat column
    reference, whitelist-checked -- see `resolve_ref_string`.
    """
    if isinstance(column, str):
        return resolve_ref_string(spec, column)
    if "count_of" in column:
        payload = column["count_of"]
        collection = resolve_collection(spec, payload["relationship"])
        if "where" not in payload:
            condition = None
        elif isinstance(collection, Backlinks):
            condition = _backlink_condition_from_json(payload["where"])
        else:
            condition = where_list_to_ast(payload["where"], collection.target)
        return CollectionCount(collection, condition)
    return resolve_column_path(spec, column["json_path"])


def _condition_from_json(condition: dict, spec: ObjectTypeSpec) -> Any:
    """One `parse_expr`-shaped condition dict, translated to a `query.py`
    comparison object (`Eq`, `Lt`, `In`, `Like`, `Regex`, `Contains`, ...)."""
    column = json_column_to_ref(condition["column"], spec)
    op = condition["op"]
    if op == "in":
        return In(column, condition["value"])
    if op == "like":
        return Like(column, condition["value"])
    if op == "regex":
        # Literal pattern only, same as "like" just above -- a pattern only
        # known at row-execution time (via "value_column") can't be
        # validated as a compilable regex ahead of time, so it's not
        # supported here (gramps-web-api's `_validate_leaf_condition`
        # enforces the same restriction on a raw `where` JSON body).
        return Regex(column, condition["value"])
    if "value_column" in condition:
        # Field-vs-field, e.g. "mother.death.date.sortval < father.death.date.sortval",
        # or (for "contains") "other_field in field".
        value = json_column_to_ref(condition["value_column"], spec)
        if isinstance(value, str):
            # A flat (same-table) column resolves to a bare str here --
            # identical in shape to an ordinary literal, which
            # Comparison/Contains would otherwise (silently, wrongly) treat
            # this as. Wrap it so it's unambiguously "a field", the same
            # way a JsonPath/RelatedObject already unambiguously is -- see
            # FlatColumnRef's docstring.
            value = FlatColumnRef(value)
    else:
        value = condition["value"]
    if op == "contains":
        return Contains(column, value)
    return _OP_CLASSES[op](column, value)


def _backlink_condition_from_json(where: List[dict]) -> BacklinkClassFilter:
    """The `Backlinks`-specific counterpart to `where_list_to_ast` -- a
    backlinks condition is always exactly the one leaf
    `_translate_backlinks_condition` (or a raw `where` JSON body written by
    hand in that same shape) produces: `{"column": "_class", "op":
    "eq"/"ne"/"in", "value": ...}`. No `and`/`or`/`not`/nested `exists` --
    see `BacklinkClassFilter`'s own docstring in query.py for why a
    backlink's condition can't reach any richer than its own class name.
    Raises `QueryError` (not `QueryLangError` -- matching `where_list_to_ast`'s
    own convention: there's no parsing here, only already-translated/
    already-parsed JSON).
    """
    if len(where) != 1:
        raise QueryError(
            f"a backlinks condition must be exactly one comparison against "
            f"_class, got {len(where)}"
        )
    leaf = where[0]
    op = leaf.get("op")
    if leaf.get("column") != "_class" or op not in ("eq", "ne", "in"):
        raise QueryError(
            f"a backlinks condition must be a single _class ==/!=/in "
            f"comparison, got {leaf!r}"
        )
    return BacklinkClassFilter(op=op, value=leaf["value"])


def where_list_to_ast(conditions: List[dict], spec: ObjectTypeSpec) -> Any:
    """A `parse_expr`-shaped list of top-level conditions (implicitly AND'd),
    translated to a single `query.py` boolean expression -- shared by
    `compile_expr_for_spec` and `_node_from_json`'s `"exists"` case, whose
    `where` payload is exactly this same shape, just against the collection's
    target type instead of the outer spec.

    Public (no leading underscore) specifically so gramps-web-api's
    `object_query.py` can call it directly for its own `where`/`where_expr`
    request bodies, rather than maintaining a second, hand-written copy of
    this same JSON -> AST translation that can (and did) drift out of sync
    every time this module gains a feature -- e.g. missing 'and'/'exists'/
    'count_of' support, and silently mishandling same-table field-vs-field
    comparisons that need `FlatColumnRef` wrapping (see `_condition_from_json`).
    Raises `QueryError` (not `QueryLangError` -- there's no parsing here,
    only already-parsed JSON) on a malformed condition; callers building
    `where` from raw, untrusted client JSON (as opposed to this module's own
    `parse_expr_for_spec` output, always well-formed by construction) are
    responsible for their own leaf-shape validation first -- see
    `object_query.py`'s `_validate_leaf_condition` for what that needs to
    cover that this function intentionally doesn't re-check.
    """
    asts = [_node_from_json(condition, spec) for condition in conditions]
    return asts[0] if len(asts) == 1 else And(*asts)


def _node_from_json(node: dict, spec: ObjectTypeSpec) -> Any:
    """One `parse_expr`-shaped node -- a leaf condition, or an `{"and"/"or":
    [...]}`/`{"not": node}`/`{"exists": {...}}` combinator -- translated to a
    `query.py` boolean expression (`Eq`/`Lt`/`In`/... for a leaf, `And`/`Or`/
    `Not`/`Exists` for a combinator), recursing into each child the same way.
    `"exists"`'s `relationship` resolving to `Backlinks` (rather than an
    ordinary `Collection`) routes its optional `where` through
    `_backlink_condition_from_json` instead of `where_list_to_ast` -- a
    `Backlinks` condition is never a general boolean tree (see
    `BacklinkClassFilter`'s docstring in query.py), so it needs no
    `collection.target` to resolve against (it has none).
    """
    if "and" in node:
        return And(*(_node_from_json(child, spec) for child in node["and"]))
    if "or" in node:
        return Or(*(_node_from_json(child, spec) for child in node["or"]))
    if "not" in node:
        return Not(_node_from_json(node["not"], spec))
    if "exists" in node:
        payload = node["exists"]
        collection = resolve_collection(spec, payload["relationship"])
        if "where" not in payload:
            condition = None
        elif isinstance(collection, Backlinks):
            condition = _backlink_condition_from_json(payload["where"])
        else:
            condition = where_list_to_ast(payload["where"], collection.target)
        return Exists(collection, condition)
    return _condition_from_json(node, spec)


def compile_expr_for_spec(spec: ObjectTypeSpec, expr: str) -> Any:
    """Parse and translate a where-expression string into a `query.py` `where`
    AST (a single comparison, or an `And`/`Or` tree of them), ready for
    `compile_query`/`compile_count_query`. For callers that already have
    `spec` -- see `parse_expr_for_spec`.
    """
    conditions = parse_expr_for_spec(spec, expr)
    return where_list_to_ast(conditions, spec)


def compile_expr(namespace: str, expr: str) -> Tuple[ObjectTypeSpec, Any]:
    """Parse and translate a where-expression string into `(spec, where)`,
    ready to pass straight to `compile_query(spec, Query(where=where), ...)`.

    >>> spec, where = compile_expr("person", "gender == 1")
    >>> where
    Eq('gender', 1)

    Field-vs-field paths on both sides of a comparison work the same way
    `object_query.py` resolves them -- e.g. `"mother.death.date.sortval <
    father.death.date.sortval"` becomes `Lt(RelatedObject(...), RelatedObject(...))`.
    """
    spec = resolve_namespace(namespace)
    return spec, compile_expr_for_spec(spec, expr)


# --- select entries ----------------------------------------------------------


#: Separator between a `select` entry's expression and its response-key
#: alias (`"birth.place.title as birthplace"`). Not valid inside a Python
#: expression, so it's split off before `ast.parse` ever sees the text --
#: the same reason SQL needs a keyword here rather than an operator.
_SELECT_ALIAS_SEPARATOR = " as "


def parse_select_entry(spec: ObjectTypeSpec, entry: str) -> Tuple[SelectRef, str]:
    """Parse one `select` entry string into `(column_ref, response_key)`.

    The entry is a column expression in the same "almost Python" grammar
    `where_expr` uses for a comparison's column side -- a flat column
    (`gramps_id`), a JSON path (`primary_name.surname_list[0].surname`), a
    path crossing relationships (`birth.place.title`), or a
    `count(relationship[, condition])` call -- optionally followed by
    `as <key>` to name it in the response.

    Without an alias the key is `default_ref_key`'s canonical spelling of
    the reference, which for every path is the path text itself. A
    `count(...)` entry has no path to derive a name from, so it falls back
    to its own source text (`"count(events)"`); an explicit alias is the
    way to get a tidier key than that.

    Deliberately not a general expression parser -- `select` takes column
    references, not arithmetic or comparisons, matching what `SelectRef`
    can actually represent. Anything else fails here rather than compiling
    into something surprising.
    """
    text = entry.strip()
    if not text:
        raise QueryLangError("empty select entry")
    alias = None
    if _SELECT_ALIAS_SEPARATOR in text:
        text, _, alias = text.partition(_SELECT_ALIAS_SEPARATOR)
        text, alias = text.strip(), alias.strip()
        if not text or not alias:
            raise QueryLangError(
                f"malformed select alias in {entry!r} -- expected "
                f"'<column> as <key>'"
            )
        if _SELECT_ALIAS_SEPARATOR in alias or not alias.isidentifier():
            raise QueryLangError(
                f"invalid select alias {alias!r} in {entry!r} -- a response key "
                f"must be a plain name"
            )

    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError as error:
        raise QueryLangError(f"could not parse select entry {entry!r}: {error}") from error

    try:
        ref = json_column_to_ref(_translate_column_or_count(node, spec), spec)
    except (QueryLangError, QueryError) as error:
        raise QueryLangError(f"invalid select entry {entry!r}: {error}") from error

    if alias is not None:
        return ref, alias
    try:
        return ref, default_ref_key(ref)
    except QueryError:
        # No path to name it after (a `count(...)` entry) -- fall back to
        # the entry's own text, whitespace-normalized. Not pretty as a
        # response key, but it's what the caller wrote, it can't collide
        # with a differently-written entry, and two counts over the same
        # collection with different conditions stay distinct (which a
        # derived name like `events_count` would not). An explicit
        # `as <key>` is still the way to get a tidy name.
        return ref, " ".join(text.split())


def parse_select(
    spec: ObjectTypeSpec, entries: Sequence[str]
) -> List[Tuple[SelectRef, str]]:
    """Parse a `select` list of entry strings into `(column_ref, key)` pairs,
    ready for `Query(select=[ref, ...])` plus the response keys to zip each
    result row against.

    >>> from gramps_object_query_language.query import PERSON
    >>> parse_select(PERSON, ["handle", "birth.place.title as birthplace"])
    [('handle', 'handle'), (RelatedObject(...), 'birthplace')]

    Duplicate response keys are rejected: two entries writing to the same
    key would silently drop one of them from every result row, and which
    one won would depend on nothing the caller can see.
    """
    parsed = [parse_select_entry(spec, entry) for entry in entries]
    seen: set = set()
    for _, key in parsed:
        if key in seen:
            raise QueryLangError(f"duplicate select key: {key!r}")
        seen.add(key)
    return parsed
