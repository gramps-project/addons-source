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
Pure-Python helpers shared by GrampyScript.py, update_script_descriptions.py,
and the test suite. Kept free of GTK/Gramps imports so they can be used
from a plain script or test without needing a GUI environment.
"""

import ast
import os

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")


def get_columns(source, func_name):
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, "id") and node.func.id == func_name:
                    return [ast.unparse(arg) for arg in node.args]
    except Exception:
        pass
    return []


def extract_header_comment(source):
    """
    Extract the leading '#'-comment block of a script as plain text,
    for use as a fallback preview when a file has no catalogued
    description in SCRIPT_DESCRIPTIONS.
    """
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            lines.append(stripped.lstrip("#").strip())
        elif stripped == "" and not lines:
            continue
        else:
            break
    return "\n".join(lines).strip()
