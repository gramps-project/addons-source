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
Regression test for bug 13955: RepositoriesReport omits URLs when the
"include repositories urls" option is selected.

Historically `RepositoriesReportAlt.__write_repository` had the URL-
writing block commented out (codefarmer, tracker note 7: commented
since 2010, throws `NameError: name 'internet' is not defined` if you
uncomment it naively at line 200). With include-URLs ON, the report
silently produced an empty Internet paragraph -- the URLs the user
asked for never reached the doc.

Construct the class via `__new__` (bypass `__init__` so we don't need
options/database/user wiring or a real doc backend) and call the
name-mangled `__write_repository` method with a stubbed repository,
database, and doc. Assert the URL text reaches `doc.write_text` when
`inc_intern` is on, and is suppressed when it's off.

Pure unit test: no display, no Gtk, no real Gramps DB.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Pin Gtk to 3.0 before importing -- RepositoriesReportAlt pulls in
# gramps.gen.plug.docgen which transitively touches GTK-3-only enums.
# Skip cleanly if GTK 3 is not available.
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
except (ImportError, ValueError) as err:
    raise unittest.SkipTest("GTK 3.0 / PyGObject not available: %s" % err)

# Make sure addon modules are importable from the parent directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_repository(urls):
    """Return a mock Repository with the given list of URL strings."""
    repo = MagicMock(name="Repository")
    repo.get_name.return_value = "Test Library"
    repo.get_type.return_value = "Library"
    repo.get_referenced_handles.return_value = []
    repo.get_text_data_child_list.return_value = []
    repo.get_handle_referents.return_value = []
    repo.handle = "REPO_HANDLE"

    url_objects = []
    for path in urls:
        u = MagicMock(name="Url")
        u.get_path.return_value = path
        url_objects.append(u)
    repo.get_url_list.return_value = url_objects
    return repo


def _make_report(repo, inc_intern, incl_empty=False):
    """Construct a RepositoryReportAlt without running __init__.

    The class' real __init__ wants an Options object, a database, and
    a User -- none of which we need to exercise the per-repository
    write path. Build a bare instance and pin only the attributes
    `__write_repository` reads.
    """
    from RepositoriesReport import RepositoriesReportAlt as mod  # pylint: disable=import-outside-toplevel

    report = mod.RepositoryReportAlt.__new__(mod.RepositoryReportAlt)
    report.doc = MagicMock(name="doc")
    report._ = lambda s: s  # identity i18n for assertion clarity
    report.database = MagicMock(name="database")
    report.database.get_repository_from_handle.return_value = repo
    report.inc_intern = inc_intern
    report.inc_addres = False
    report.inclu_note = False
    report.incl_empty = incl_empty
    return report


class TestRepositoryUrlOutput(unittest.TestCase):
    """Regression for bug 13955."""

    def _written_text(self, report):
        return [call.args[0] for call in report.doc.write_text.call_args_list]

    def test_urls_written_when_inc_intern_on(self):
        """When include-URLs is selected the repository URLs reach
        the doc.

        Pre-fix this fails: the URL block was commented out so the
        Internet paragraph never carried any URL text.
        """
        repo = _make_repository(["https://example.org/", "https://example.net/"])
        report = _make_report(repo, inc_intern=True)
        report._RepositoryReportAlt__write_repository("REPO_HANDLE")

        written = self._written_text(report)
        self.assertIn(
            "Internet: ",
            written,
            "Internet label must appear when inc_intern is on",
        )
        self.assertIn(
            "https://example.org/\nhttps://example.net/",
            written,
            "Both repository URLs must reach the doc",
        )

    def test_no_url_paragraph_when_inc_intern_off(self):
        """With include-URLs off the Internet paragraph is suppressed
        entirely (no empty paragraph, no Internet label).

        Pre-fix behaviour also suppressed the URLs in this case --
        same outcome -- but the regression guard locks the gate so a
        later "always write the section" refactor wouldn't slip
        through.
        """
        repo = _make_repository(["https://example.org/"])
        report = _make_report(repo, inc_intern=False)
        report._RepositoryReportAlt__write_repository("REPO_HANDLE")

        written = self._written_text(report)
        self.assertNotIn("Internet: ", written)
        for text in written:
            self.assertNotIn(
                "https://example.org/",
                text,
                "URL must not appear when inc_intern is off",
            )

    def test_no_url_paragraph_when_no_urls_and_incl_empty_off(self):
        """A repository with no URLs and incl_empty off must not get
        an empty Internet paragraph.

        This pins the contract: the URL section follows the same
        "empty fields suppressed unless incl_empty" rule the rest of
        the report uses (see inc_addres / incl_empty pattern).
        """
        repo = _make_repository([])
        report = _make_report(repo, inc_intern=True, incl_empty=False)
        report._RepositoryReportAlt__write_repository("REPO_HANDLE")

        written = self._written_text(report)
        self.assertNotIn("Internet: ", written)


if __name__ == "__main__":
    unittest.main()
