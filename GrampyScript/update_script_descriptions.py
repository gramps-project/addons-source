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
Dev tool: rebuild script_descriptions.py's SCRIPT_DESCRIPTIONS dict from the
files in scripts/. Each scripts/*.gram.py file is the source of truth for
its own entry: the title comes from the file's leading '# Title' comment,
and the description comes from its module docstring (the triple-quoted
string right below that comment).

Run it any time you add a new example script, edit an existing script's
title or docstring, or delete a script:

    python3 update_script_descriptions.py

The whole SCRIPT_DESCRIPTIONS body is always fully rebuilt from scripts/ --
there is no hand-maintained text left to preserve. A script missing a
title comment or a docstring is an error, since both are now required.
The static header (license block, module docstring, imports) is kept as
whatever's already at the top of script_descriptions.py.
"""

import ast
import glob
import os
import sys
import textwrap

from script_utils import SCRIPTS_DIR, extract_header_comment

DESCRIPTIONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "script_descriptions.py"
)

ENTRY_INDENT = " " * 8
TEXT_INDENT = " " * 12
DESCRIPTION_WIDTH = 65


def _load_header(path):
    """Return the file text up through the "SCRIPT_DESCRIPTIONS = {" line."""
    source = open(path, encoding="utf-8").read()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SCRIPT_DESCRIPTIONS"
            for t in node.targets
        ):
            return "".join(lines[: node.lineno - 1]) + "SCRIPT_DESCRIPTIONS = {\n"
    raise RuntimeError("SCRIPT_DESCRIPTIONS not found in %s" % path)


def _dquote(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_call(text, width=None):
    lines = textwrap.wrap(text, width=width) if width else [text]
    if len(lines) <= 1:
        return "_(%s)" % _dquote(text)
    body = "".join(
        "%s%s\n" % (TEXT_INDENT, _dquote(line + (" " if i < len(lines) - 1 else "")))
        for i, line in enumerate(lines)
    )
    return "_(\n%s%s)" % (body, ENTRY_INDENT)


def render_entry(filename, title, description):
    return "    %s: (\n%s%s,\n%s%s,\n    ),\n" % (
        _dquote(filename),
        ENTRY_INDENT,
        _render_call(title),
        ENTRY_INDENT,
        _render_call(description, width=DESCRIPTION_WIDTH),
    )


def collect_entries():
    """
    Returns (entries, errors), where entries maps filename -> (title,
    description) read from scripts/*.gram.py, and errors lists filenames
    missing a title comment or a docstring.
    """
    entries = {}
    errors = []
    for path in sorted(glob.glob(os.path.join(SCRIPTS_DIR, "*.gram.py"))):
        filename = os.path.basename(path)
        source = open(path, encoding="utf-8").read()
        title = extract_header_comment(source)
        description = ast.get_docstring(ast.parse(source), clean=True)
        if description:
            description = " ".join(description.split())
        if not title:
            errors.append("%s: missing a leading '# Title' comment" % filename)
        if not description:
            errors.append("%s: missing a description docstring" % filename)
        if title and description:
            entries[filename] = (title, description)
    return entries, errors


def build_source(entries, header):
    body = "".join(
        render_entry(filename, title, description)
        for filename, (title, description) in entries.items()
    )
    return header + body + "}\n"


def main():
    entries, errors = collect_entries()
    if errors:
        print("Cannot regenerate script_descriptions.py:")
        for error in errors:
            print("  ! %s" % error)
        return 1

    header = _load_header(DESCRIPTIONS_PATH)
    new_source = build_source(entries, header)

    with open(DESCRIPTIONS_PATH, "w", encoding="utf-8") as fp:
        fp.write(new_source)

    print("Regenerated script_descriptions.py from %d scripts." % len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
