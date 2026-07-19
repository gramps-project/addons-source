#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Dmitry Bryndin
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

"""Row schema data structures for GTK ListStore column definitions.

These NamedTuples define the column order and types for GTK ListStore widgets.
The order must match the actual column definitions in the GTK store.
Note: `handle` column is internal and not displayed in the UI.
"""

from typing import NamedTuple

from name_processor.models.renamer import AltAction


# Given Names store column indices (Tab 1 - Rename Given Names)
# Important: Order must match the actual column definitions in the GTK store
# Note: `handle` column is internal and not displayed in the UI
class GivenRowData(NamedTuple):
    """Row data for the Given Names rename proposals table."""

    checkbox: bool
    gramps_id: str
    display_name: str
    current: str
    proposed: str
    alt_action: AltAction
    handle: str


# Audit store column indices (Tab 2 - Audit Patronymics)
# Important: Order must match the actual column definitions in the GTK store
# Note: `handle` column is internal and not displayed in the UI
class AuditRowData(NamedTuple):
    """Row data for the Audit Patronymics results table."""

    checkbox: bool
    display_name: str
    gramps_id: str
    father_name: str
    current_patronymic: str
    diff_markup: str
    confidence: str
    ref_year: str
    rule_id: str
    handle: str
    suggested_string: str
    explanation: str
