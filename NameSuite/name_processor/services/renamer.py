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

import re

from name_processor.models.renamer import MatchMode, RenameConfig


class RenamerService:
    @classmethod
    def create_config(
        cls, match_type: MatchMode, source: str, target: str
    ) -> RenameConfig:
        config = RenameConfig(mode=match_type, source=source, target=target)
        if match_type == MatchMode.REGEX:
            config.pattern = re.compile(source)
        return config

    @classmethod
    def evaluate_person(cls, name: str, cfg: RenameConfig) -> str | None:
        """Returns the transformed given name, or None if no change."""
        if not name:
            return None

        original_name = name
        proposed_name = None

        if cfg.mode == MatchMode.EXACT and original_name == cfg.source:
            proposed_name = cfg.target

        elif cfg.mode == MatchMode.SUBSTRING:
            proposed_name = original_name.replace(cfg.source, cfg.target)

        elif cfg.mode == MatchMode.REGEX and cfg.pattern:
            proposed_name = cfg.pattern.sub(cfg.target, original_name)

        if not proposed_name or proposed_name == original_name:
            return None

        return proposed_name
