#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  Eduard Ralph
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

"""Integration tests: run RepositoriesReport against ``example.gramps``.

These reproduce two crashes that only surface when the report walks a real
database — they are invisible to a mocked-DB unit test, because a mock
returns only what it is told to:

* Citations: ``__write_referenced_sources`` queried
  ``find_backlink_handles(source)`` with no class filter, then fed every
  backlink to ``get_citation_from_handle``. A source's backlinks include
  ``Note`` objects, so the first Note handle raised ``HandleError``.
* Notes: the repository note loop fed every handle from
  ``repository.get_referenced_handles()`` to ``get_note_from_handle``
  without the ``classname == 'Note'`` guard its sibling source loop already
  has, so a tagged repository raised ``HandleError`` on the Tag handle.

The report is driven through its public ``write_report`` against
``example.gramps`` (the canonical fixture); the only stub is the output doc
backend, which is not the code under test. Pre-fix these fail with
``HandleError``; post-fix the report completes.
"""

# ------------------------
# Python modules
# ------------------------
import os
import sys
import unittest
from unittest.mock import MagicMock

# ------------------------
# Gramps modules
# ------------------------
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    import gramps  # noqa: F401
    from gramps.cli.user import User
    from gramps.gen.db import DbTxn
    from gramps.gen.db.utils import import_as_dict
    from gramps.gen.lib import Tag
except (ImportError, ValueError) as exc:
    raise unittest.SkipTest("RepositoriesReport tests require 'gi' + 'gramps': %s" % exc)

# ------------------------
# Gramps specific
# ------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    from RepositoriesReportAlt import RepositoryReportAlt
except ImportError as exc:
    raise unittest.SkipTest("RepositoriesReportAlt import failed: %s" % exc)


def _find_example_gramps():
    """Locate the canonical example.gramps shipped with Gramps."""
    candidates = []
    res = os.environ.get("GRAMPS_RESOURCES")
    if res:
        candidates.append(os.path.join(res, "example", "gramps", "example.gramps"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(gramps.__file__)))
    candidates.append(os.path.join(root, "example", "gramps", "example.gramps"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


# ------------------------------------------------------------------------
#
# _StubFilter
#
# ------------------------------------------------------------------------
class _StubFilter:
    """Empty-named filter so ``__write_all_repositories`` walks every
    repository via ``get_repository_handles`` (no GUI filter plumbing)."""

    def get_name(self):
        return ""


# ------------------------------------------------------------------------
#
# RepositoriesReportExampleGrampsTest
#
# ------------------------------------------------------------------------
class RepositoriesReportExampleGrampsTest(unittest.TestCase):
    """Drive the report end-to-end against example.gramps."""

    @classmethod
    def setUpClass(cls):
        cls.example = _find_example_gramps()
        if cls.example is None:
            raise unittest.SkipTest("example.gramps not found")

    def _load_db(self):
        return import_as_dict(self.example, User())

    def _make_report(self, db):
        """Build a report via ``__new__``-bypass against a real db, with
        only the output doc stubbed (it is not the code under test)."""
        report = RepositoryReportAlt.__new__(RepositoryReportAlt)
        report.database = db
        report.user = User()
        report.doc = MagicMock()
        report._ = lambda text, *args: text
        report.black_list = []
        report.filter = _StubFilter()
        for attr in (
            "inc_intern",
            "inc_addres",
            "inc_author",
            "inc_abbrev",
            "inc_public",
            "inc_datamp",
            "inclu_note",
            "incl_citat",
            "incl_empty",
        ):
            setattr(report, attr, True)
        # Skip the PrivateProxyDb wrap (we already hold a real db) and the
        # media path (it would load image files off disk, unrelated here).
        report.inc_privat = True
        report.incl_media = False
        return report

    def test_report_runs_over_example_gramps(self):
        """Full report walk must complete — exercises the citations
        backlink path that raised HandleError on a Note backlink."""
        db = self._load_db()
        report = self._make_report(db)
        report.write_report()  # pre-fix: HandleError from get_citation_from_handle
        # Prove it actually traversed, not just no-op'd.
        self.assertTrue(report.doc.write_text.called)
        self.assertTrue(report.doc.start_paragraph.called)

    def test_tagged_repository_does_not_crash_note_path(self):
        """A tagged repository must not crash the note loop — its
        get_referenced_handles() returns a ('Tag', handle) tuple that was
        fed unguarded to get_note_from_handle."""
        db = self._load_db()
        repo_handle = next(iter(db.get_repository_handles()), None)
        self.assertIsNotNone(repo_handle, "example.gramps must contain a repository")
        with DbTxn("attach tag", db) as trans:
            tag = Tag()
            tag.set_name("IntegrationTestTag")
            tag_handle = db.add_tag(tag, trans)
            repo = db.get_repository_from_handle(repo_handle)
            repo.add_tag(tag_handle)
            db.commit_repository(repo, trans)
        # Sanity: the repo now references a non-Note object.
        repo = db.get_repository_from_handle(repo_handle)
        classes = {cls for cls, _ in repo.get_referenced_handles()}
        self.assertIn("Tag", classes)

        report = self._make_report(db)
        report.write_report()  # pre-fix: HandleError from get_note_from_handle


if __name__ == "__main__":
    unittest.main()
