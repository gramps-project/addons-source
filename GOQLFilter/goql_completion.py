#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026       Douglas Blank
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

"""GOQL-specific completion source for ``goql_completion_popup``'s
``CompletionController``.

Kept free of GTK imports, mirroring ``GrampyScript/completion.py``'s own
"testable without a display" convention -- ``goql.py`` is responsible for
turning a ``Gtk.TextBuffer`` cursor position into ``(source, line, column)``.

Deliberately not jedi-based, unlike GrampyScript's completion engine: a
where-expression is never executed, has no live namespace of real Python
objects to introspect, and its grammar is a small closed set (see
``gramps_object_query_language.query_lang``'s module docstring) -- general
Python completion would suggest names (arbitrary methods, ``import``, ...)
that are simply invalid here. This only ever offers two things, matching
what was actually asked for:

- At the top level (no ``.`` immediately before the word being typed): the
  current namespace's own vocabulary -- flat column names, relationship
  names (``birth``, ``father``, ...), collection names (``children``,
  ``events``, ...), the where-expression keywords (``and``/``or``/``not``/
  ``in``/``like``/``Date``/``exists``/``count``), the comparison operators
  (``==``/``!=``/``<``/``<=``/``>``/``>=``) -- included even though most are
  a single character and so only ever surface with an empty prefix (Tab on
  its own), not because they're likely to be *typed* out via completion --
  and the constant class names themselves (``Person``, ``EventType``, ...)
  so typing far enough to reach one and then ``.`` is a smooth continuation.
- Right after ``ClassName.``, where ``ClassName`` is one of the constant
  classes ``query_lang.py`` recognizes on the value side of a comparison
  (``Person.MALE``, ``EventType.BIRTH``, ...): that class's own ALL_CAPS
  int constants.

Anything else (e.g. completing a nested JSON field inside
``primary_name.``) returns no completions -- out of scope for now, not a
silent failure to fix.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# `_RELATIONSHIPS`/`_COLLECTIONS` (query.py) and `_CONSTANT_CLASSES`/
# `_CONSTANTS` (query_lang.py) are module-private -- there is no public way
# to *enumerate* every relationship/collection/constant name for a spec
# (only to resolve one given name, via the public `resolve_collection`/
# `resolve_column_path`). Reaching into them here is a deliberate, narrow
# exception for exactly this reason, not an oversight; if
# gramps-object-query-language grows a public enumeration API, switch to it.
from gramps_object_query_language.query import _COLLECTIONS, _RELATIONSHIPS
from gramps_object_query_language.query_lang import (
    QueryLangError,
    _CONSTANT_CLASSES,
    _CONSTANTS,
    resolve_namespace,
)

from goql_vocabulary import COMPARISON_OPERATORS, KEYWORDS

_DOTTED_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z0-9_]*)$")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


def _text_before_cursor(source: str, line: int, column: int) -> str:
    """``source`` truncated to the cursor position.

    ``line`` is 1-indexed, ``column`` is a 0-indexed character offset
    within that line -- the same convention ``CompletionController`` uses
    (``GrampyScript/completion_popup.py``'s ``_cursor_line_column``,
    matching ``Gtk.TextIter.get_line() + 1`` / ``get_line_offset()``).
    """
    lines = source.split("\n")
    index = max(0, min(line - 1, len(lines) - 1)) if lines else 0
    before_lines = lines[:index]
    current_line = lines[index] if lines else ""
    return "\n".join(before_lines + [current_line[:column]])


def _top_level_names(namespace: str) -> Set[str]:
    try:
        spec = resolve_namespace(namespace)
    except QueryLangError:
        return set()
    names: Set[str] = set(spec.columns)
    names.update(_RELATIONSHIPS.get(spec.table, {}).keys())
    names.update(_COLLECTIONS.get(spec.table, {}).keys())
    names.update(KEYWORDS)
    names.update(COMPARISON_OPERATORS)
    names.update(_CONSTANT_CLASSES.keys())
    return names


def _constant_names(class_name: str) -> Set[str]:
    return set(_CONSTANTS.get(class_name, {}).keys())


def get_completion_items(
    source: str, line: int, column: int, namespace: str
) -> List[Dict[str, Any]]:
    """Candidate completions at ``(line, column)`` in ``source``, for the
    given GOQL ``namespace`` ("Person", "Family", ...).

    Same return shape as ``GrampyScript/completion.py``'s
    ``get_completion_items`` -- ``{"name": ..., "complete": ..., "cursor_offset":
    0}`` dicts -- so ``goql_completion_popup.CompletionController`` (adapted
    from ``GrampyScript/completion_popup.py``) can drive either unchanged.
    Always flat: no attempt to parse the surrounding expression's grammar,
    only what immediately precedes the word being completed.
    """
    text_before = _text_before_cursor(source, line, column)
    dotted = _DOTTED_RE.search(text_before)
    if dotted:
        class_name, prefix = dotted.group(1), dotted.group(2)
        names = _constant_names(class_name)
    else:
        word = _WORD_RE.search(text_before)
        prefix = word.group(0) if word else ""
        names = _top_level_names(namespace)

    matches = sorted(name for name in names if name.startswith(prefix))
    return [
        {"name": name, "complete": name[len(prefix) :], "cursor_offset": 0}
        for name in matches
    ]
