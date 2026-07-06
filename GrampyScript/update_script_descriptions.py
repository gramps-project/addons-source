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
Dev tool: keep script_descriptions.py's SCRIPT_DESCRIPTIONS dict in sync
with the files actually present in scripts/.

Run it after adding a new example script, deleting one, or renaming one:

    python3 update_script_descriptions.py

What it does automatically (safe, structural, nothing to lose):
  - Adds a stub entry -- title taken from the new file's leading '#'
    comment, description a "TODO" placeholder -- for any scripts/*.gram.py
    file with no entry yet.
  - Drops entries for files that no longer exist in scripts/.

What it only *warns* about (needs a human judgment call):
  - A file whose leading comment title no longer matches the title
    already catalogued in SCRIPT_DESCRIPTIONS. Titles are not
    auto-overwritten, since the catalogued one may have been deliberately
    written differently (and richer) than the terse in-file comment.

Existing entries' source text (title + description, translator comments,
line wrapping, quoting) is preserved byte-for-byte by slicing it straight
out of the current file with ast -- this script never touches wording it
didn't generate itself.
"""

import ast
import glob
import os
import sys

from script_utils import SCRIPTS_DIR, extract_header_comment

DESCRIPTIONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "script_descriptions.py"
)

STUB_DESCRIPTION = "TODO: describe what this script does."


def _slice_source(lines, node):
    start_line, start_col = node.lineno - 1, node.col_offset
    end_line, end_col = node.end_lineno - 1, node.end_col_offset
    if start_line == end_line:
        return lines[start_line][start_col:end_col]
    parts = [lines[start_line][start_col:]]
    parts.extend(lines[start_line + 1 : end_line])
    parts.append(lines[end_line][:end_col])
    return "".join(parts)


def _load_existing(path):
    """
    Returns (header, entries) where header is the file text up through
    "SCRIPT_DESCRIPTIONS = {" and entries maps filename -> (title,
    raw_value_source) using the tuple's exact original source text.
    """
    source = open(path, encoding="utf-8").read()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    dict_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SCRIPT_DESCRIPTIONS"
            for t in node.targets
        ):
            dict_node = node.value
            break
    if dict_node is None:
        raise RuntimeError("SCRIPT_DESCRIPTIONS not found in %s" % path)

    header = "".join(lines[: dict_node.lineno - 1]) + "SCRIPT_DESCRIPTIONS = {\n"

    entries = {}
    for key_node, value_node in zip(dict_node.keys, dict_node.values):
        filename = ast.literal_eval(key_node)
        title = value_node.elts[0].args[0].value
        raw_value = _slice_source(lines, value_node)
        entries[filename] = (title, raw_value)
    return header, entries


def _stub_entry(title):
    return '(\n        _(%r),\n        _(%r),\n    )' % (title, STUB_DESCRIPTION)


def main():
    header, existing = _load_existing(DESCRIPTIONS_PATH)

    current_files = sorted(
        os.path.basename(p)
        for p in glob.glob(os.path.join(SCRIPTS_DIR, "*.gram.py"))
    )

    added, removed, retitled_warnings = [], [], []

    body_lines = []
    for filename in current_files:
        file_title = extract_header_comment(
            open(os.path.join(SCRIPTS_DIR, filename)).read()
        )
        if filename in existing:
            title, raw_value = existing[filename]
            if file_title and file_title != title:
                retitled_warnings.append((filename, title, file_title))
        else:
            title, raw_value = file_title or filename, _stub_entry(
                file_title or filename
            )
            added.append(filename)
        body_lines.append('    "%s": %s,\n' % (filename, raw_value))

    for filename in existing:
        if filename not in current_files:
            removed.append(filename)

    new_source = header + "".join(body_lines) + "}\n"

    with open(DESCRIPTIONS_PATH, "w", encoding="utf-8") as fp:
        fp.write(new_source)

    if added:
        print("Added stub entries (fill in real descriptions):")
        for filename in added:
            print("  + %s" % filename)
    if removed:
        print("Removed stale entries (file no longer in scripts/):")
        for filename in removed:
            print("  - %s" % filename)
    if retitled_warnings:
        print("Title mismatches (file comment changed, catalogued title did not):")
        for filename, old_title, new_title in retitled_warnings:
            print("  ! %s" % filename)
            print("      catalogued: %r" % old_title)
            print("      in file:    %r" % new_title)
        print(
            "  -> update the title in script_descriptions.py by hand if the "
            "file's title is now the correct one."
        )
    if not (added or removed or retitled_warnings):
        print("script_descriptions.py is already in sync with scripts/.")

    return 1 if retitled_warnings else 0


if __name__ == "__main__":
    sys.exit(main())
