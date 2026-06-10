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

from dataclasses import dataclass
from enum import Enum
import re


class MatchMode(Enum):
    EXACT = "exact"
    SUBSTRING = "substring"
    REGEX = "regex"


class AltAction(Enum):
    PRESERVE = "Preserve"
    OVERWRITE = "Overwrite"


@dataclass
class RenameConfig:
    """Stores and validates user-defined replacement rules."""

    mode: MatchMode
    source: str
    target: str
    pattern: re.Pattern | None = None
    is_valid: bool = True
    error_msg: str = ""


@dataclass
class ProposedRename:
    """DTO representing a single proposed name change for the UI grid."""

    handle: str
    gramps_id: str
    display_name: str
    original_given_name: str
    proposed_given_name: str
    alt_action: str = AltAction.OVERWRITE.value
    matched_text: str = ""  # Text that was matched and replaced (for highlighting)
