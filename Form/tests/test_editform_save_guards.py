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

"""Unit tests for ``editform`` save-time guards — Mantis 11054.

Mantis 0011054: if a Source / Person / Family referenced by an open
Form editor is deleted in another window, ``OK`` writes a citation
with a None-target reference and Check & Repair later flags the
dangling handle.

Per nick_h's note 5/7 the accepted fix is narrow:

* On save, if the source has gone, create a replacement source.
* On save, if a referenced person/family has gone, drop the row.

These tests use ``__new__``-bypass to construct ``EditForm``,
``MultiSection``, ``PersonSection`` and ``FamilySection`` instances
without driving the live Gtk dialog tree, then assert that the guards
do the right thing on a deleted-out-from-under-us reference.

Run with::

    python3 -m unittest Form.tests.test_editform_save_guards -v
"""

# ------------------------
# Python modules
# ------------------------
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ------------------------
# Gramps modules
# ------------------------
try:
    import gi

    gi.require_version("Gtk", "3.0")
    import gramps  # noqa: F401
except ImportError as exc:
    raise unittest.SkipTest("Form editform tests require 'gi' and 'gramps': %s" % exc)

if "GRAMPS_RESOURCES" not in os.environ:
    os.environ["GRAMPS_RESOURCES"] = os.path.dirname(os.path.dirname(gramps.__file__))

# ------------------------
# Gramps specific
# ------------------------
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ADDON_DIR not in sys.path:
    sys.path.insert(0, ADDON_DIR)

try:
    import editform
    from editform import EditForm, MultiSection, PersonSection, FamilySection
except ImportError as exc:
    raise unittest.SkipTest(
        "editform import failed (likely missing gramps.gui deps): %s" % exc
    )


# ------------------------------------------------------------------------
#
# EditFormSourceGuardTest
#
# ------------------------------------------------------------------------
class EditFormSourceGuardTest(unittest.TestCase):
    """``EditForm.save`` must not write a citation whose source handle
    no longer resolves — it should create a replacement source first.
    """

    def _make_edit_form(self) -> EditForm:
        """``__new__``-bypass: build an ``EditForm`` with only the
        attributes ``save`` touches. We mock out the wider save flow
        (``headings.save``, ``details.save``, ``close``, ``callback``)
        so the test focuses on whether the source guard fires.
        """
        ef = EditForm.__new__(EditForm)
        ef.db = MagicMock()
        ef.citation = MagicMock()
        ef.event = MagicMock()
        ef.event.get_handle.return_value = "EVENT_HANDLE"
        ef.citation.get_reference_handle.return_value = "DEAD_SOURCE_HANDLE"
        ef.citation.get_handle.return_value = "CITATION_HANDLE"
        ef.headings = MagicMock()
        ef.details = MagicMock()
        ef.get_menu_title = MagicMock(return_value="Edit Form")
        ef.close = MagicMock()
        ef.callback = MagicMock()
        return ef

    def test_dead_source_handle_gets_replacement_source_added(self) -> None:
        """When ``get_source_from_handle`` returns ``None`` for the
        citation's source, ``add_source`` is called and the citation's
        reference handle is repointed at the new source.
        """
        ef = self._make_edit_form()
        ef.db.get_source_from_handle.return_value = None

        with patch.object(editform, "DbTxn") as mock_txn:
            mock_txn.return_value.__enter__.return_value = MagicMock()
            ef.save(button=None)

        ef.db.add_source.assert_called_once()
        ef.citation.set_reference_handle.assert_called_once()

    def test_live_source_handle_leaves_citation_alone(self) -> None:
        """Sanity check: when the source still exists, the guard is a
        no-op — no ``add_source`` call, no ``set_reference_handle`` call.
        """
        ef = self._make_edit_form()
        ef.db.get_source_from_handle.return_value = MagicMock()

        with patch.object(editform, "DbTxn") as mock_txn:
            mock_txn.return_value.__enter__.return_value = MagicMock()
            ef.save(button=None)

        ef.db.add_source.assert_not_called()
        ef.citation.set_reference_handle.assert_not_called()


# ------------------------------------------------------------------------
#
# MultiSectionPersonGuardTest
#
# ------------------------------------------------------------------------
class MultiSectionPersonGuardTest(unittest.TestCase):
    """``MultiSection.save`` must skip rows whose person handle no
    longer resolves and skip removed-people whose handle is dead.
    """

    def _make_multi_section(
        self, rows: list[str], initial: list[str], live: set[str]
    ) -> MultiSection:
        """Build a ``MultiSection`` via ``__new__``-bypass with a fake
        model, a fake db where ``get_person_from_handle`` returns a
        ``MagicMock`` for handles in ``live`` and ``None`` otherwise.
        """
        ms = MultiSection.__new__(MultiSection)
        ms.db = MagicMock()
        # The model is iterated as ``for order, row in enumerate(model)``
        # with ``row[0]`` the handle and ``row[1:]`` extra columns. Use
        # lists-of-lists; one column past the handle is enough.
        ms.model = [[handle, ""] for handle in rows]
        ms.initial_people = initial
        ms.columns = ["col0"]
        ms.role = MagicMock()
        ms.citation = MagicMock()
        ms.event = MagicMock()
        ms.event.handle = "EVENT_HANDLE"

        def _lookup(handle: str) -> MagicMock | None:
            if handle in live:
                person = MagicMock()
                person.get_event_ref_list.return_value = []
                return person
            return None

        ms.db.get_person_from_handle.side_effect = _lookup
        return ms

    def test_row_with_dead_person_is_skipped(self) -> None:
        """A row whose person handle resolves to ``None`` is not
        committed; rows with live handles still commit.
        """
        ms = self._make_multi_section(
            rows=["LIVE_A", "DEAD_B", "LIVE_C"],
            initial=["LIVE_A", "DEAD_B", "LIVE_C"],
            live={"LIVE_A", "LIVE_C"},
        )

        with patch.object(
            editform, "get_event_ref", return_value=MagicMock()
        ), patch.object(editform, "set_attribute"):
            ms.save(trans=MagicMock())

        # Two live rows commit; the dead row does not.
        self.assertEqual(ms.db.commit_person.call_count, 2)

    def test_removed_person_already_gone_is_skipped(self) -> None:
        """A handle in ``initial_people`` but not in the model that
        also no longer resolves is not committed (the row exists only
        to detach a no-longer-referenced person, and detaching from a
        gone person is a no-op).
        """
        ms = self._make_multi_section(
            rows=[],
            initial=["DEAD_REMOVED"],
            live=set(),
        )

        with patch.object(
            editform, "get_event_ref", return_value=MagicMock()
        ), patch.object(editform, "set_attribute"):
            ms.save(trans=MagicMock())

        ms.db.commit_person.assert_not_called()


# ------------------------------------------------------------------------
#
# PersonSectionGuardTest
#
# ------------------------------------------------------------------------
class PersonSectionGuardTest(unittest.TestCase):
    """``PersonSection.save`` must early-return when the attached
    person has been deleted, and skip the detach step when the
    previously-attached person is gone.
    """

    def _make_person_section(
        self, handle: str | None, initial_handle: str | None
    ) -> PersonSection:
        """``__new__``-bypass for ``PersonSection``."""
        ps = PersonSection.__new__(PersonSection)
        ps.handle = handle
        ps.initial_handle = initial_handle
        ps.dbstate = MagicMock()
        ps.db = MagicMock()
        ps.event = MagicMock()
        ps.event.handle = "EVENT_HANDLE"
        ps.role = MagicMock()
        ps.citation = MagicMock()
        ps.headings = []
        ps.widgets = {}
        return ps

    def test_dead_attached_person_short_circuits(self) -> None:
        """``get_person_from_handle(self.handle)`` returning ``None``
        causes an immediate return — no commits.
        """
        ps = self._make_person_section(handle="DEAD_HANDLE", initial_handle=None)
        ps.dbstate.db.get_person_from_handle.return_value = None

        ps.save(trans=MagicMock())

        ps.dbstate.db.commit_person.assert_not_called()
        ps.db.commit_person.assert_not_called()

    def test_dead_initial_person_skips_detach(self) -> None:
        """When ``initial_handle`` no longer resolves but the current
        ``handle`` does, the section commits the current person and
        skips the detach step rather than crashing on a ``None``.
        """
        ps = self._make_person_section(
            handle="LIVE_HANDLE", initial_handle="DEAD_INITIAL"
        )

        live_person = MagicMock()
        live_person.get_event_ref_list.return_value = []

        def _lookup(handle: str) -> MagicMock | None:
            if handle == "LIVE_HANDLE":
                return live_person
            return None

        ps.dbstate.db.get_person_from_handle.side_effect = _lookup
        ps.db.get_person_from_handle.side_effect = _lookup

        with patch.object(
            editform, "get_event_ref", return_value=MagicMock()
        ), patch.object(editform, "write_attributes"):
            ps.save(trans=MagicMock())

        # Current person committed (via dbstate.db); detach skipped
        # because the initial person was already deleted.
        ps.dbstate.db.commit_person.assert_called_once_with(
            live_person, unittest.mock.ANY
        )
        ps.db.commit_person.assert_not_called()


# ------------------------------------------------------------------------
#
# FamilySectionGuardTest
#
# ------------------------------------------------------------------------
class FamilySectionGuardTest(unittest.TestCase):
    """``FamilySection.save`` mirrors ``PersonSection.save`` but on the
    family table.
    """

    def _make_family_section(
        self, handle: str | None, initial_handle: str | None
    ) -> FamilySection:
        """``__new__``-bypass for ``FamilySection``."""
        fs = FamilySection.__new__(FamilySection)
        fs.handle = handle
        fs.initial_handle = initial_handle
        fs.dbstate = MagicMock()
        fs.db = MagicMock()
        fs.event = MagicMock()
        fs.event.handle = "EVENT_HANDLE"
        fs.role = MagicMock()
        fs.citation = MagicMock()
        fs.headings = []
        fs.widgets = {}
        fs.widgets2 = {}
        return fs

    def test_dead_attached_family_short_circuits(self) -> None:
        """``get_family_from_handle(self.handle)`` returning ``None``
        causes an immediate return — no commits.
        """
        fs = self._make_family_section(handle="DEAD_HANDLE", initial_handle=None)
        fs.dbstate.db.get_family_from_handle.return_value = None

        fs.save(trans=MagicMock())

        fs.dbstate.db.commit_family.assert_not_called()
        fs.db.commit_family.assert_not_called()

    def test_dead_initial_family_skips_detach(self) -> None:
        """When ``initial_handle`` no longer resolves but the current
        ``handle`` does, the section commits the current family and
        skips the detach step.
        """
        fs = self._make_family_section(
            handle="LIVE_HANDLE", initial_handle="DEAD_INITIAL"
        )

        live_family = MagicMock()
        live_family.get_event_ref_list.return_value = []

        def _lookup(handle: str) -> MagicMock | None:
            if handle == "LIVE_HANDLE":
                return live_family
            return None

        fs.dbstate.db.get_family_from_handle.side_effect = _lookup
        fs.db.get_family_from_handle.side_effect = _lookup

        with patch.object(
            editform, "get_event_ref", return_value=MagicMock()
        ), patch.object(editform, "write_attributes"):
            fs.save(trans=MagicMock())

        fs.dbstate.db.commit_family.assert_called_once_with(
            live_family, unittest.mock.ANY
        )
        fs.db.commit_family.assert_not_called()


if __name__ == "__main__":
    unittest.main()
