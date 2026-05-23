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
Regression test for Mantis bug 14051.

`DetailedDescendantBookReport.append_event` reads
``self.report_app_ref[self.phandle][0]`` to build the "Ref: ..." text
that prefixes each index-of-dates / index-of-places entry. The lookup
table ``report_app_ref`` is only filled by the up-front reference pass
guarded by ``if self.dubperson:`` (the "omit duplicate ancestors"
option). When that option is unselected but Index of Dates or Index of
Places is enabled, ``append_event`` still runs from
``write_person_info`` / ``__write_family_events`` and raises against
the empty / missing table — historically an ``AttributeError`` (before
the partial fix for bugs 12857/12859 unconditionally initialised the
dict), now a ``KeyError`` on the current handle.

This test exercises ``append_event`` in isolation with the settings
combination from bug 14051 (``dubperson=False`` + indexes enabled) and
asserts it completes without raising and that the indexes receive an
entry referencing the current writing-pass context.
"""

import os
import sys
import types
import unittest
from unittest import mock

# Make the addon importable from its parent directory, matching the
# JSON / TMGimporter / Form test convention. Required when this test
# is loaded by its dotted path (`DescendantBooks.tests.<module>`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub RunReport so importing DetailedDescendantBookReport does not pull
# in gramps.gui (which requires gi.require_version('Gtk', '4.0') and a
# display). The append_event method does not touch the report dialog.
_run_report_stub = types.ModuleType("RunReport")
_run_report_stub.RunReport = lambda *a, **kw: None
sys.modules.setdefault("RunReport", _run_report_stub)

import DetailedDescendantBookReport as ddbr


def _make_event(year, place_handle=""):
    """Build a stub event_ref / event pair usable by append_event."""
    date_obj = mock.MagicMock()
    date_obj.get_year.return_value = year

    event = mock.MagicMock()
    event.get_date_object.return_value = date_obj
    event.get_place_handle.return_value = place_handle
    event.get_type.return_value = "Birth"

    event_ref = mock.MagicMock()
    event_ref.ref = "EVENT-HANDLE"
    return event_ref, event, date_obj


class TestAppendEventWithoutOmitDuplicates(unittest.TestCase):
    """append_event must not crash when the reference pre-pass is skipped.

    Bug 14051: with ``Omit duplicate ancestors`` off and an index option
    on, the pre-pass under ``if self.dubperson:`` never populates
    ``report_app_ref``, but ``append_event`` is still invoked for every
    event because the indexes are enabled.
    """

    def _make_report(self):
        # Build a DetailedDescendantBookReport without calling __init__
        # (the real __init__ takes options/user/database and constructs
        # a Bibliography etc., none of which append_event uses).
        report = ddbr.DetailedDescendantBookReport.__new__(
            ddbr.DetailedDescendantBookReport
        )

        # Minimum attributes append_event reads. Mirrors what
        # write_report would set up before invoking the writing pass.
        report.report_app_ref = {}            # the bug's empty table
        report.index_of_dates = {}
        report.index_of_places = {}
        report.dnumber = {"P1": "1"}
        report.dmates = {}
        report.report_count = 3               # third ascendant tree
        report.generation = 1                 # second generation in it
        report.phandle = "P1"
        report.inc_index_of_dates = True
        report.inc_index_of_places = True

        # _ is the report's translation callable; sgettext-style — just
        # return the string verbatim so we can assert on it.
        report._ = lambda s: s
        # _get_date / _get_type return strings; stub to identity-like.
        report._get_date = lambda d: "1850"
        report._get_type = lambda t: str(t)

        # Stub the database so place lookups return a known title.
        place = mock.MagicMock()
        place.get_title.return_value = "Dublin"
        db = mock.MagicMock()
        db.get_event_from_handle.return_value = None  # set per-test
        db.get_place_from_handle.return_value = place
        db.get_person_from_handle.return_value = mock.MagicMock(
            get_primary_name=lambda: mock.MagicMock(get_name=lambda: "John Doe")
        )
        report.database = db
        return report

    def test_append_event_does_not_crash_without_prepopulated_table(self):
        """append_event with an empty report_app_ref must not raise.

        Failure pre-fix: raises ``KeyError: 'P1'`` (or, on addon versions
        prior to the partial fix for 12857/12859, ``AttributeError`` on
        ``report_app_ref``) — the exact crash signature from bug 14051.
        """
        report = self._make_report()
        event_ref, event, _ = _make_event(year=1850, place_handle="PLACE-HANDLE")
        report.database.get_event_from_handle.return_value = event

        # This is the call the report system makes from
        # write_person_info when (inc_index_of_dates or inc_index_of_places)
        # is enabled. It must not raise.
        report.append_event(event_ref)

        # The indexes should have been populated with an entry tagged
        # with the current writing-pass coordinates (report_count,
        # generation+1, dnumber[phandle]) — i.e. "3 2 1" — not with a
        # tuple sourced from a stale / missing report_app_ref entry.
        self.assertIn(1850, report.index_of_dates,
                      "Year 1850 should be indexed")
        self.assertIn("Dublin", report.index_of_places,
                      "Place 'Dublin' should be indexed")

        # Spot-check the Ref text uses current state.
        date_entries = list(report.index_of_dates[1850].values())
        self.assertTrue(any("Ref: 3 2 1" in entry for entry in date_entries),
                        "Index entry should reference current report context "
                        "(report_count=3, generation+1=2, dnumber[phandle]=1); "
                        "got %r" % date_entries)

    def test_append_event_for_mate_without_dnumber(self):
        """A mate's event where the mate is not in dnumber must not crash.

        ``__write_mate`` sets ``self.phandle = mate_handle`` when the
        mate is being printed in full; the mate may not have a
        ``dnumber`` entry (only descendants do). append_event must
        still produce an entry with a sensible fallback Ref rather
        than KeyError on ``self.dnumber[mate_handle]``.
        """
        report = self._make_report()
        report.phandle = "MATE-NOT-IN-DNUMBER"
        # dmates is empty in __write_mate's Branch A (the not-inc_materef
        # path that sets phandle = mate_handle). Leave it that way.
        event_ref, event, _ = _make_event(year=1860)
        report.database.get_event_from_handle.return_value = event

        report.append_event(event_ref)

        # The index should still receive an entry; the Ref's "per" field
        # falls back gracefully when the mate's dnumber isn't known.
        self.assertIn(1860, report.index_of_dates)


if __name__ == "__main__":
    unittest.main()
