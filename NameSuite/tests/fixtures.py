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

from __future__ import annotations

from unittest.mock import MagicMock


def create_mock_name(first_name: str, surname: str = "") -> MagicMock:
    """Helper to create a mock Gramps Name object."""
    mock_name = MagicMock()
    mock_name.get_first_name.return_value = first_name
    mock_name.get_surname_list.return_value = []
    return mock_name


def create_mock_person(
    gramps_id: str,
    given_name: str,
    surname: str,
    handle: str,
    aka_names: list[tuple[str, str]] | None = None,
) -> MagicMock:
    """
    Helper to create a mock Gramps Person object with deep mocking.

    Args:
        gramps_id: Gramps ID (e.g., "I001")
        given_name: Given name (e.g., "Анна")
        surname: Surname (e.g., "Облонская")
        handle: Person handle (e.g., "handle1")
        aka_names: List of (first_name, surname) tuples for AKA names

    Returns:
        MagicMock: Mocked Person object with proper name structure
    """
    mock_person = MagicMock()
    mock_person.handle = handle
    mock_person.gramps_id = gramps_id
    mock_person.given_name = given_name
    mock_person.display_name = f"{surname}, {given_name}"

    # Mock primary name
    mock_primary_name = create_mock_name(given_name, surname)
    mock_person.get_primary_name.return_value = mock_primary_name

    # Mock alternate names
    mock_alt_names = []
    if aka_names:
        for aka_first, aka_surname in aka_names:
            mock_aka_name = create_mock_name(aka_first, aka_surname)
            mock_alt_names.append(mock_aka_name)
    mock_person.get_alternate_names.return_value = mock_alt_names

    # Track added alternate names for verification
    added_alt_names = []

    def add_alternate_name(name):
        added_alt_names.append(name)

    mock_person.add_alternate_name.side_effect = add_alternate_name
    mock_person._added_alt_names = added_alt_names

    return mock_person


def setup_sample_family() -> dict[str, MagicMock]:
    """
    Set up the sample family from the test scenarios.

    Returns:
        dict: Mapping of gramps_id to mock_person objects
    """
    # Father: I001, Облонский, Аркадий
    i001 = create_mock_person(
        gramps_id="I001",
        given_name="Аркадий",
        surname="Облонский",
        handle="handle_i001",
    )

    # Daughter: I000, Облонская, Анна (with AKA: Кюри, Мария)
    i000 = create_mock_person(
        gramps_id="I000",
        given_name="Анна",
        surname="Облонская",
        handle="handle_i000",
        aka_names=[("Мария", "Кюри")],
    )

    # Daughter: I002, Облонская, Долли, Аркадена
    i002 = create_mock_person(
        gramps_id="I002",
        given_name="Долли",
        surname="Облонская",
        handle="handle_i002",
    )

    # Son: I004, Oblonsky, Stiva, Mikhailovich
    i004 = create_mock_person(
        gramps_id="I004",
        given_name="Stiva",
        surname="Oblonsky",
        handle="handle_i004",
    )

    # Unrelated: I003, Skłodowska, Curie, Maria
    i003 = create_mock_person(
        gramps_id="I003",
        given_name="Maria",
        surname="Skłodowska",
        handle="handle_i003",
    )

    return {
        "I001": i001,
        "I000": i000,
        "I002": i002,
        "I004": i004,
        "I003": i003,
    }
