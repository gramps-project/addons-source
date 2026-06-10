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

from abc import ABC, abstractmethod
from name_processor.models.audit import RuleContext, ProposedChange


class BaseRule(ABC):
    """Abstract Base Class for all linter consistency rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def severity(self) -> str:
        pass

    @property
    @abstractmethod
    def supported_locales(self) -> set[str]:
        pass

    @property
    @abstractmethod
    def active_era(self) -> tuple[int | None, int | None]:
        pass

    @abstractmethod
    def evaluate(self, ctx: RuleContext, use_pre_reform: bool) -> ProposedChange | None:
        """
        Evaluates context. Returns None if rule passes, or a ProposedChange
        if consistency issues are detected.
        """
        pass
