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
Translatable titles and descriptions for the bundled example scripts in
scripts/. Kept out of the .gram.py files themselves so the examples stay
free of gettext markup while still being picked up by the addon's normal
xgettext-based translation pipeline (see ../make.py).
"""

from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

SCRIPT_DESCRIPTIONS = {
    "01_list_people.gram.py": (
        _("List All People"),
        _(
            "Iterate over every person in the database and show their "
            "Gramps ID, given name, surname, and gender in the results "
            "table."
        ),
    ),
    "02_filter_by_surname.gram.py": (
        _("Filter By Surname"),
        _(
            "List only the people whose surname matches a given value — "
            "a starting point for narrowing any report down by a "
            "condition."
        ),
    ),
    "03_family_overview.gram.py": (
        _("Family Overview"),
        _(
            "List every family together with the father, the mother, and "
            "how many children they have — a quick way to spot families "
            "that look incomplete."
        ),
    ),
    "04_gender_pie_chart.gram.py": (
        _("Gender Breakdown (Pie Chart)"),
        _(
            "Count how many people are male, female, or of unknown "
            "gender, then draw a pie chart of the totals. Check the "
            "Chart tab after running."
        ),
    ),
    "05_age_histogram.gram.py": (
        _("Age At Death Histogram"),
        _(
            "For everyone with both a birth and a death event recorded, "
            "compute their age in whole years and draw a histogram of "
            "the distribution. Check the Chart tab after running."
        ),
    ),
    "06_mark_unsourced_people_private.gram.py": (
        _("Mark Unsourced People As Private"),
        _(
            "Batch-edit example: find every person who has no citations "
            "attached and flag them as private, wrapped in "
            "begin_changes()/end_changes() so the edits happen inside a "
            "single, undoable transaction."
        ),
    ),
    "07_csv_ready_report.gram.py": (
        _("CSV-Ready People Report"),
        _(
            "Build a simple tabular report — ID, name, gender, birth "
            "year — for every person. Once it runs, use Data > Save as "
            "CSV or Copy to clipboard to export the Table tab's "
            "contents."
        ),
    ),
    "08_active_person_summary.gram.py": (
        _("Active Person Summary"),
        _(
            "Show a compact family summary for the currently active "
            "person: their record, parents, spouse, and children."
        ),
    ),
    "09_selected_people_report.gram.py": (
        _("Report On Selected People"),
        _(
            "List just the people currently selected (highlighted) in "
            "the People view. Select some rows in the People view "
            "before running this script."
        ),
    ),
    "10_find_missing_birth_dates.gram.py": (
        _("Find People Missing A Birth Date"),
        _(
            "Data-quality check: list every person who has no recorded "
            "birth event, so you can prioritize research on those "
            "records."
        ),
    ),
    "11_import_example.gram.py": (
        _("Births Per Decade (Import Example)"),
        _(
            "Counts births by decade, using a decade() function imported "
            "from script_helpers.py in this same folder — a template for "
            "sharing helper code between your own scripts with a plain "
            "'import' statement."
        ),
    ),
    "12_custom_filter_example.gram.py": (
        _("Custom Filter Example"),
        _(
            "Runs one of your own custom filters (from the Filters "
            "gramplet/editor) by name using custom_filter(). Change "
            "'example filter' to the name of a filter you've already "
            "created; if the name doesn't match one, a warning shows up "
            "in the Output tab instead."
        ),
    ),
    "13_delete_unused_repositories.gram.py": (
        _("Delete Unused Repositories (Delete Example)"),
        _(
            "Demonstrates delete(): removes any Repository record that "
            "nothing else in the tree refers to. Most trees have no "
            "unused repositories, so this is unlikely to actually delete "
            "anything — it's meant to show the pattern, wrapped in "
            "begin_changes()/end_changes() as a single undoable "
            "transaction."
        ),
    ),
}
