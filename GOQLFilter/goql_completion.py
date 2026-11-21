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

"""GOQL completion source for ``goql_completion_popup``'s
``CompletionController``.

The suggestions come from gramps-object-query-language itself
(``gramps_object_query_language.completion.complete``, 0.5.13 and later),
which knows the language's whole grammar and vocabulary: what fits at the
start of a condition, after a field, after a comparison, inside each
function's arguments, after a dotted path, and which values a field takes
(``type.value ==`` -> ``EventType.``). This module only adapts its result to
what the popup expects. An older GOQL without that module turns completion
off (Tab does nothing) rather than breaking the gramplet; filtering itself
still works.

Kept free of GTK imports -- ``goql.py``/``goql_completion_popup.py`` turn a
``Gtk.TextBuffer`` cursor position into ``(source, line, column)``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

_LOG = logging.getLogger(".GOQLFilter.completion")

try:
    from gramps_object_query_language.completion import complete
except ImportError:  # gramps-object-query-language older than 0.5.13
    complete = None
    _LOG.warning(
        "GOQL Filter: Tab completion needs gramps-object-query-language "
        "0.5.13 or later; upgrade it to turn completion on."
    )


def _cursor_offset(source: str, line: int, column: int) -> int:
    """The character offset of ``(line, column)`` in ``source``.

    ``line`` is 1-indexed, ``column`` a 0-indexed character offset within
    that line -- ``CompletionController``'s convention
    (``Gtk.TextIter.get_line() + 1`` / ``get_line_offset()``).
    """
    lines = source.split("\n")
    index = max(0, min(line - 1, len(lines) - 1))
    return sum(len(text) + 1 for text in lines[:index]) + min(column, len(lines[index]))


def get_completion_items(
    source: str, line: int, column: int, namespace: str
) -> List[Dict[str, Any]]:
    """Candidate completions at ``(line, column)`` in ``source``, for the
    given GOQL ``namespace`` ("Person", "Family", ...).

    Each item is ``{"name", "complete", "cursor_offset", "kind",
    "detail"}``: ``name`` is the whole word shown in the list, ``complete``
    the part still to insert at the cursor (the word typed so far is
    always a prefix of ``name``), ``kind``/``detail`` say what it is (see
    GOQL's ``complete_from_vocabularies``). A name that continues ends
    with what follows it -- ``date.``, ``address_list[``, ``any(``, ``and ``.
    """
    if complete is None:
        return []
    cursor = _cursor_offset(source, line, column)
    try:
        results = complete(namespace, source, cursor)
    except ValueError:  # QueryLangError: not a GOQL namespace
        return []
    items = []
    for result in results:
        typed = source[result["start"] : cursor]
        if not result["name"].startswith(typed):
            continue
        items.append(
            {
                "name": result["name"],
                "complete": result["name"][len(typed) :],
                "cursor_offset": 0,
                "kind": result["kind"],
                "detail": result["detail"],
            }
        )
    return items
