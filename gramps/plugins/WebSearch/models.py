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
Data structures for handling website links and search context in Gramps WebSearch.

This module defines simple data containers used to represent:
- website entries and metadata
- context for search link generation
- AI-related domain categorization

These classes are primarily used during preprocessing and link building
for web search and archival queries.
"""


from dataclasses import dataclass, field
from typing import Optional
from typing import Set


@dataclass
class WebsiteEntry:
    """Represents a single website entry used for search or display purposes."""

    # pylint: disable=too-many-instance-attributes
    nav_type: str
    country_code: Optional[str]
    source_type: Optional[str]
    title: str
    is_enabled: str
    url_pattern: str
    comment: Optional[str]
    is_custom_file: bool


@dataclass
class LinkContext:
    """Holds context information needed to generate a search URL."""

    core_keys: dict
    attribute_keys: dict
    nav_type: str
    obj: object


@dataclass
class AIDomainData:
    """Categorizes domains for AI-driven filtering of search results."""

    community_country_codes: Set[str]
    regular_country_codes: Set[str]
    regular_domains: Set[str]
    community_urls: Set[str]
    include_global: bool
    skipped_domains: Set[str] = field(default_factory=set)
