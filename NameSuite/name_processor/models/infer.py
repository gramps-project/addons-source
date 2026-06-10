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

from enum import Enum
from dataclasses import dataclass


class PatronymicInferenceStatus(Enum):
    """Status codes for patronymic inference."""

    SUCCESS = "SUCCESS"
    NO_ACTIVE_PERSON = "NO_ACTIVE_PERSON"
    NO_FATHER = "NO_FATHER"
    FATHER_NO_NAME = "FATHER_NO_NAME"
    NON_BINARY = "NON_BINARY"
    ALREADY_HAS_PATRONYMIC = "ALREADY_HAS_PATRONYMIC"
    MORPHOLOGY_FAIL = "MORPHOLOGY_FAIL"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass
class ProposedPatronymic:
    """Result of inferring a patronymic for a single person."""

    status: PatronymicInferenceStatus = PatronymicInferenceStatus.UNKNOWN_ERROR
    patronymic: str | None = None
    father_name: str | None = None
    confidence: float | None = None
