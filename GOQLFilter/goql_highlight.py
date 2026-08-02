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

"""Token-span classification for GOQL where-expression syntax highlighting.

Kept free of GTK imports -- same "testable without a display" convention as
``goql_completion.py`` -- ``goql.py`` is responsible for turning a span into
a ``Gtk.TextTag`` range.

Uses Python's own ``tokenize`` module rather than a hand-written lexer: a
where-expression's tokens (names, string/number literals, comparison
operators) are a strict subset of Python's own, so there's no new grammar
to maintain here -- just a classification on top of what ``tokenize``
already produces. This is lexical only (keyword/string/number/operator/
known-constant-class recognition from token text alone), not a real parse
-- it never rejects anything ``query_lang.py`` wouldn't also accept or
reject on its own; ``compile_expr``'s own error message is still the
source of truth for whether an expression is valid.
"""

from __future__ import annotations

import io
import tokenize
from typing import Iterator, Tuple

from gramps_object_query_language.query_lang import _CONSTANT_CLASSES

from goql_vocabulary import COMPARISON_OPERATORS, KEYWORDS

# (start_line, start_col, end_line, end_col, category) -- 0-indexed lines,
# matching Gtk.TextIter's own convention (tokenize's rows are 1-indexed).
Span = Tuple[int, int, int, int, str]


def classify_tokens(source: str) -> Iterator[Span]:
    """Yield a ``Span`` for each highlightable token in ``source``.

    Incomplete/invalid source -- the normal state of this buffer while
    still being typed, not an error case -- is handled by
    ``_tokenize_best_effort``: whatever ``tokenize`` managed to produce
    before hitting the unparseable part is still yielded.
    """
    for tok in _tokenize_best_effort(source):
        category = _classify(tok)
        if category is None:
            continue
        start_line, start_col = tok.start
        end_line, end_col = tok.end
        yield (start_line - 1, start_col, end_line - 1, end_col, category)


def _classify(tok) -> str | None:
    if tok.type == tokenize.STRING:
        return "string"
    if tok.type == tokenize.NUMBER:
        return "number"
    if tok.type == tokenize.NAME:
        if tok.string in KEYWORDS:
            return "keyword"
        if tok.string in _CONSTANT_CLASSES:
            return "constant-class"
        return None
    if tok.type == tokenize.OP and tok.string in COMPARISON_OPERATORS:
        return "operator"
    return None


def _tokenize_best_effort(source: str):
    """``tokenize.generate_tokens`` raises on unterminated strings,
    unbalanced brackets, or an expression that just stops mid-line -- all
    routine while typing, not something to surface as a highlighting
    failure. Whatever was already yielded before the exception is kept
    (the loop below appends token-by-token, so a raise partway through
    only truncates the tail, not the whole result).
    """
    tokens = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            tokens.append(tok)
    except Exception:
        pass
    return tokens
