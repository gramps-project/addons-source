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
Command completion for the GrampyScript editor, built on jedi.

Kept free of GTK imports so it can be developed and tested without a
running Gramps/GTK environment; GrampyScript.py is responsible for
turning a Gtk.TextBuffer cursor position into (line, column) and for
building the namespace of live/template DSL objects.
"""

import jedi

from stub_generator import build_stub_source

_stub_source = None


def _get_stub_preamble():
    """
    Lazily build and cache the stub-class source (stub_generator.py):
    static type annotations, derived from Gramps' own get_schema(), that
    let jedi infer the row type of DSL generators like `people()` for a
    user's own loop variable -- something no live namespace object can
    provide, since there is no instance until the script actually runs.
    """
    global _stub_source
    if _stub_source is None:
        _stub_source = build_stub_source()
    return _stub_source


def _complete(source, line, column, namespace):
    """Shared jedi call underlying both get_completions() and
    get_completion_items(); returns raw jedi Completion objects."""
    preamble = _get_stub_preamble()
    full_source = preamble + source
    interpreter = jedi.Interpreter(full_source, [namespace])
    try:
        return interpreter.complete(line + preamble.count("\n"), column)
    except Exception:
        return []


def get_completions(source, line, column, namespace):
    """
    Return candidate completion names for `source` at the given cursor
    position. `line`/`column` refer to `source` itself (1-indexed /
    0-indexed, jedi's convention, matching Gtk.TextIter's
    get_line()+1 / get_line_offset()); the stub preamble prepended below
    is accounted for internally.

    `namespace` is a plain dict of name -> live or template object,
    e.g. {"active_person": DataDict2(...), "database": self.db}.
    Attribute completion on dynamic objects (like DataDict2) relies on
    those objects implementing __dir__ correctly, since jedi falls back
    to runtime introspection (dir()/getattr()) for anything it can't
    statically analyze.
    """
    return [completion.name for completion in _complete(source, line, column, namespace)]


def get_completion_items(source, line, column, namespace):
    """
    Same as get_completions(), but for UI use: returns a list of
    {"name": full completion name, "complete": text to insert at the
    cursor} dicts. `name` is for display; `complete` is only the
    remaining characters jedi says are missing (e.g. typing "impo" and
    accepting "import" gives complete == "rt"), so callers can insert it
    directly without recomputing/re-typing the already-typed prefix.
    """
    return [
        {"name": completion.name, "complete": completion.complete}
        for completion in _complete(source, line, column, namespace)
    ]
