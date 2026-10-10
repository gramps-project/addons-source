#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2026  GWizard Merge Field Tests
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Tests for the field rows built by the GWizard merge dialog.

These cover the surname rows, where a GEDCOM surname prefix (``SPFX``)
and additional surnames must not be mistaken for a match.
"""

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations
import unittest
from unittest.mock import Mock

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.lib import Name, Person, Surname
from gwizard import surname_prefix_text, surname_text
from gwizardmergedialog import (
    citation_sources_summary,
    field_values_differ,
    person_events_by_type,
)


def _person(first: str, surnames: list[tuple[str, str]]) -> Person:
    """
    Build a person with one primary name from (surname, prefix) pairs.

    :param first: The given name.
    :param surnames: Sequence of ``(surname, prefix)`` tuples.
    :returns: The constructed person.
    :rtype: Person
    """
    name = Name()
    name.first_name = first
    for surname, prefix in surnames:
        surn = Surname()
        surn.set_surname(surname)
        surn.set_prefix(prefix)
        name.add_surname(surn)
    person = Person()
    person.set_primary_name(name)
    return person


class GWizardMergeFieldRowsTest(unittest.TestCase):
    """Field row values for names that differ only by prefix or extra surname."""

    def test_surname_prefix_difference_is_flagged(self) -> None:
        """
        A SPFX-only difference must mark the Surname Prefix row as different.
        """
        source = _person("Anna", [("Hansdotter", "")])
        target = _person("Anna", [("Hansdotter", "Vrow")])
        self.assertFalse(
            field_values_differ(
                surname_text(source.get_primary_name()),
                surname_text(target.get_primary_name()),
            )
        )
        self.assertTrue(
            field_values_differ(
                surname_prefix_text(source.get_primary_name()),
                surname_prefix_text(target.get_primary_name()),
            )
        )
        self.assertEqual(surname_prefix_text(source.get_primary_name()), "")
        self.assertEqual(surname_prefix_text(target.get_primary_name()), "Vrow")

    def test_additional_surname_is_flagged(self) -> None:
        """
        An extra surname on the target must mark the Surname row as different.
        """
        source = _person("Anna", [("Hansdotter", "")])
        target = _person("Anna", [("Hansdotter", "Vrow"), ("Smith", "")])
        self.assertTrue(
            field_values_differ(
                surname_text(source.get_primary_name()),
                surname_text(target.get_primary_name()),
            )
        )
        self.assertEqual(surname_text(source.get_primary_name()), "Hansdotter")
        self.assertEqual(surname_text(target.get_primary_name()), "Hansdotter Smith")

    def test_shared_prefix_is_not_flagged(self) -> None:
        """
        Equal prefixes and surnames must not be reported as a difference.
        """
        source = _person("Anna", [("Hansdotter", "Vrow")])
        target = _person("Anna", [("Hansdotter", "Vrow")])
        self.assertFalse(
            field_values_differ(
                surname_prefix_text(source.get_primary_name()),
                surname_prefix_text(target.get_primary_name()),
            )
        )

    def test_empty_source_prefix_still_differs_from_target(self) -> None:
        """
        An empty source value compares as different from a populated target.
        """
        self.assertTrue(field_values_differ("", "Vrow"))
        self.assertFalse(field_values_differ(None, ""))
        self.assertFalse(field_values_differ("Vrow", "Vrow"))


class GWizardCitationSummaryTest(unittest.TestCase):
    """Citation summaries shown with values in the merge dialog."""

    def test_summary_includes_source_title_and_citation_page(self) -> None:
        citation = Mock()
        citation.get_reference_handle.return_value = "source-handle"
        citation.get_page.return_value = "42"
        citation.get_note_list.return_value = []
        source = Mock()
        source.get_title.return_value = "1840 Census"
        source.get_author.return_value = ""
        source.gramps_id = "S0001"
        db = Mock()
        db.get_citation_from_handle.return_value = citation
        db.get_source_from_handle.return_value = source
        obj = Mock()
        obj.get_citation_list.return_value = ["citation-handle"]

        self.assertEqual(citation_sources_summary(db, obj), "1840 Census (page 42)")

    def test_summary_is_empty_without_citations(self) -> None:
        obj = Mock()
        obj.get_citation_list.return_value = []

        self.assertEqual(citation_sources_summary(Mock(), obj), "")

    def test_summary_includes_distinct_author(self) -> None:
        citation = Mock()
        citation.get_reference_handle.return_value = "source-handle"
        citation.get_page.return_value = "42"
        citation.get_note_list.return_value = []
        source = Mock()
        source.get_title.return_value = "1850 Census"
        source.get_author.return_value = "Bureau of the Census"
        source.get_reporef_list.return_value = []
        source.gramps_id = "S0001"
        db = Mock()
        db.get_citation_from_handle.return_value = citation
        db.get_source_from_handle.return_value = source
        obj = Mock()
        obj.get_citation_list.return_value = ["citation-handle"]

        self.assertEqual(
            citation_sources_summary(db, obj),
            "Bureau of the Census, 1850 Census (page 42)",
        )

    def test_summary_omits_duplicate_author(self) -> None:
        citation = Mock()
        citation.get_reference_handle.return_value = "source-handle"
        citation.get_page.return_value = "42"
        citation.get_note_list.return_value = []
        source = Mock()
        source.get_title.return_value = "Ancestry.com Family Tree"
        source.get_author.return_value = "Ancestry.com"
        source.get_reporef_list.return_value = []
        source.gramps_id = "S0001"
        db = Mock()
        db.get_citation_from_handle.return_value = citation
        db.get_source_from_handle.return_value = source
        obj = Mock()
        obj.get_citation_list.return_value = ["citation-handle"]

        self.assertEqual(
            citation_sources_summary(db, obj),
            "Ancestry.com Family Tree (page 42)",
        )

    def test_summary_includes_repository_provenance(self) -> None:
        citation = Mock()
        citation.get_reference_handle.return_value = "source-handle"
        citation.get_page.return_value = "42"
        citation.get_note_list.return_value = []
        repo_ref = Mock(ref="repo-handle")
        source = Mock()
        source.get_title.return_value = "1840 Census"
        source.get_author.return_value = ""
        source.get_reporef_list.return_value = [repo_ref]
        source.gramps_id = "S0001"
        repo = Mock()
        repo.get_name.return_value = "National Archives and Records Administration"
        db = Mock()
        db.get_citation_from_handle.return_value = citation
        db.get_source_from_handle.return_value = source
        db.get_repository_from_handle.return_value = repo
        obj = Mock()
        obj.get_citation_list.return_value = ["citation-handle"]

        self.assertEqual(
            citation_sources_summary(db, obj),
            "1840 Census (page 42) via National Archives and Records Administration",
        )

    def test_summary_combines_author_title_page_and_repository(self) -> None:
        citation = Mock()
        citation.get_reference_handle.return_value = "source-handle"
        citation.get_page.return_value = "ED 51-508, p. 3B"
        citation.get_note_list.return_value = []
        repo_ref = Mock(ref="repo-handle")
        source = Mock()
        source.get_title.return_value = "Population Schedule"
        source.get_author.return_value = "Bureau of the Census"
        source.get_reporef_list.return_value = [repo_ref]
        source.gramps_id = "S0001"
        repo = Mock()
        repo.get_name.return_value = "NARA"
        db = Mock()
        db.get_citation_from_handle.return_value = citation
        db.get_source_from_handle.return_value = source
        db.get_repository_from_handle.return_value = repo
        obj = Mock()
        obj.get_citation_list.return_value = ["citation-handle"]

        self.assertEqual(
            citation_sources_summary(db, obj),
            "Bureau of the Census, Population Schedule (page ED 51-508, p. 3B) via NARA",
        )


class GWizardEventGroupingTest(unittest.TestCase):
    """Events listed in the merge dialog match the compare window's set."""

    def test_includes_vital_and_other_events_but_excludes_internal_markers(
        self,
    ) -> None:
        event_types = {
            "birth": "Birth",
            "death": "Death",
            "occupation": "Occupation",
            "exclude": "_PPEXCLUDE",
            "fslink": "_FSLINK",
        }
        events = {}
        refs = []
        for handle, event_type in event_types.items():
            event = Mock()
            event.handle = handle
            event.get_type.return_value = event_type
            events[handle] = event
            refs.append(Mock(ref=handle))

        db = Mock()
        db.get_event_from_handle.side_effect = events.__getitem__
        person = Mock()
        person.get_event_ref_list.return_value = refs

        self.assertEqual(
            person_events_by_type(db, person),
            {"Birth": ["birth"], "Death": ["death"], "Occupation": ["occupation"]},
        )


if __name__ == "__main__":
    unittest.main()
