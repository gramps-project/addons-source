#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
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

# ----------------------------------------------------------------------------

"""
Utility functions for displaying tabular data in terminal.

This module provides helper functions to format and print:
- Rows from a Gtk.ListStore model as separate field-value tables.
- Lists of dataclass instances as aligned, readable tables.

Intended for debugging or inspection purposes in console-based environments.
"""

from dataclasses import fields, is_dataclass
from typing import Any, List
from gi.repository import GdkPixbuf


def print_dataclass_table(
    data_list: list[Any], max_width_override: dict[int, int] = None
):
    """
    Print a table view of a list of dataclass instances with optional column width overrides.

    Args:
        data_list (list): List of dataclass instances.
        max_width_override (dict[int, int], optional):
            Dictionary mapping field indices to max widths.
            Example: {5: 30, 6: 50}
    """
    if not data_list:
        print("No data to display.")
        return

    if not is_dataclass(data_list[0]):
        raise ValueError("Items in the list must be dataclass instances.")

    max_width_override = max_width_override or {}
    field_list = fields(data_list[0])
    field_names = [f.name for f in field_list]
    num_fields = len(field_names)

    def calc_width(i):
        if i in max_width_override:
            return max_width_override[i]
        max_len = max(
            (
                len(str(getattr(item, field_names[i])))
                if getattr(item, field_names[i]) is not None
                else 0
            )
            for item in data_list
        )
        return max(max_len, len(field_names[i])) + 2

    col_widths = [calc_width(i) for i in range(num_fields)]

    def truncate(value, width):
        value_str = str(value) if value is not None else ""
        return value_str if len(value_str) <= width else value_str[: width - 3] + "..."

    # Header
    header = " | ".join(f"{field_names[i]:<{col_widths[i]}}" for i in range(num_fields))
    print(header)
    print("-" * len(header))

    # Rows
    for item in data_list:
        row = " | ".join(
            f"{truncate(getattr(item, field_names[i]), col_widths[i]):<{col_widths[i]}}"
            for i in range(num_fields)
        )
        print(row)


def print_model_as_row_tables(
    model, model_schema, max_value_width=80, fields_to_print=None
):
    """
    Prints each row of a Gtk.ListStore model as a separate table.
    Each row is displayed as a two-column table: field name and value.

    :param model: Gtk.ListStore - the model to print.
    :param model_schema: list of tuples (name, type) defining the schema of the model.
    :param max_value_width: int - maximum width of the value before truncation (default: 80).
    :param fields_to_print: optional list of field names to print; if None, all fields are printed.
    """

    if len(model) == 0:
        print("⚠️  The model is empty — no rows to display.")
        return

    def truncate(value):
        val = str(value)
        if len(val) > max_value_width:
            return val[: max_value_width - 3] + "..."
        return val

    selected_fields = []
    for idx, (name, _) in enumerate(model_schema):
        if fields_to_print is None or name in fields_to_print:
            selected_fields.append((idx, name))

    for row_index, row in enumerate(model):
        print(f"\n🔹 Row {row_index + 1}")
        print("-" * (max_value_width + 35))
        print(f"{'Field':<30} | Value")
        print("-" * (max_value_width + 35))
        for idx, name in selected_fields:
            value = row[idx]
            if isinstance(value, GdkPixbuf.Pixbuf):
                value_str = "<Image>"
            elif value is None:
                value_str = ""
            else:
                value_str = truncate(value)
            print(f"{name:<30} | {value_str}")
        print("-" * (max_value_width + 35))


def print_parsed_archive_references_table(title: str, cases: List[str], parser_func):
    """Prints a formatted table of test results for visual inspection."""
    print(f"\n{title}")
    print("-" * 100)
    print(
        f"{'#':<3} "
        f"{'Input':<55} "
        f"{'archive_code':<12} "
        f"{'collection':<10} "
        f"{'series':<8} "
        f"{'file':<6}"
    )
    print("-" * 100)
    for i, case in enumerate(cases, 1):
        result = parser_func(case) or {}
        print(
            f"{i:<3} {case:<55} "
            f"{str(result.get('archive_code', '')):<12} "
            f"{str(result.get('collection_number', '')):<10} "
            f"{str(result.get('series_number', '')):<8} "
            f"{str(result.get('file_number', '')):<6}"
        )
