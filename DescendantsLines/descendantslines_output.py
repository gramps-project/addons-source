#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Gramps Development Team
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
"""
Output-filename derivation for the DescendantsLines report.

This module is deliberately free of any ``gi`` / ``gramps.gui`` imports so the
filename logic can be unit-tested headlessly. The report
(``DescendantsLines.py``) routes through :func:`derive_output_filename`, so the
test exercises the very code the production report runs (no parallel copy).

Bug 5965: the DescendantsLines graphic was always written to the report's own
persisted "Destination" option (``output_fn``). That option keeps its value
across Gramps sessions, so a graphic produced this run carried the *previous*
session's name, ignoring the filename the user chose for the current run in the
standard report dialog's "Document Options". The fix derives the graphic name
from the destination selected for the *current* run, falling back to the
persisted option only when the current run supplies no destination.
"""

import os


def derive_output_filename(current_destination, option_destination, output_fmt):
    """
    Return the graphic output filename for the *current* report run.

    :param current_destination: the output destination selected for this run
        (the report document's output, i.e. ``options_class.get_output()``).
        Reflects the name the user picked in the current invocation; may be
        ``None``/empty when no document destination was given (e.g. CLI without
        an explicit ``-O``).
    :param option_destination: the report's own persisted "Destination" option
        value (``output_fn``). Retained across sessions, so on its own it is a
        *stale* source for the current run's name.
    :param output_fmt: the addon's chosen output format ("PNG", "PDF", ...).
        Forced onto the filename so it is named for *this* run's format.
    :returns: the filename to write the graphic to.

    The destination chosen for the current run takes precedence over the
    persisted option, so the graphic never carries a prior session's name. When
    the current destination is what the standard report document is also written
    to, the graphic is given a distinct ``-chart`` suffix: the document is closed
    (and thus written) *after* the graphic is drawn, so sharing the exact path
    would let the document's close() clobber the graphic.
    """
    base = current_destination or option_destination or ""
    ext = output_fmt.lower()
    root = os.path.splitext(base)[0]
    candidate = "%s.%s" % (root, ext)
    if current_destination and candidate == current_destination:
        candidate = "%s-chart.%s" % (root, ext)
    return candidate
