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

from dataclasses import dataclass, field
from enum import Enum


class Gender(Enum):
    """Domain enum for gender values, decoupled from Gramps integer constants."""

    MALE = "MALE"
    FEMALE = "FEMALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=False)
class Person:
    handle: str
    gramps_id: str
    given_name: str
    gender: Gender
    has_patronymic: bool
    display_name: str
    father_handle: str | None = None
    alternate_first_names: list[str] = field(default_factory=list)
