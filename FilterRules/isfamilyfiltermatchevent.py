#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Matthias Kemmer
# Copyright (C) 2025  Steve Youngs
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
"""Filter rule that matches events of families matching a <family filter>."""

# -------------------------------------------------------------------------
#
# Standard python modules
#
# -------------------------------------------------------------------------
from __future__ import annotations

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gui.editors.filtereditor import MyFilters
from gramps.gen.filters.rules._matchesfilterbase import MatchesFilterBase
from gramps.gen.const import GRAMPS_LOCALE as glocale

# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from typing import Set
from gramps.gen.types import EventHandle
from gramps.gen.lib import Event
from gramps.gen.db import Database

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# Family filter selector
#
# -------------------------------------------------------------------------
class FamFilt(MyFilters):
    """Add custom family filter selector."""

    def __init__(self, db):
        import inspect

        stack = inspect.stack()  # our stack frame
        caller_locals = stack[1][0].f_locals  # locals from caller
        # the caller has an attribute 'filterdb' which has what we need
        MyFilters.__init__(self, caller_locals["filterdb"].get_filters("Family"))


# -------------------------------------------------------------------------
#
# Events matching family filter
#
# -------------------------------------------------------------------------
class IsFamilyFilterMatchEvent(MatchesFilterBase):
    """Rule that checks for an event matching a <family filter>."""

    labels = [(_("Family Filter name:"), FamFilt)]
    name = _("Events of families matching a <family filter>")
    description = _("Events of families matching a <family filter>")
    category = _("General filters")
    namespace = "Family"

    def prepare(self, db: Database, user):
        """Prepare a reference list for the filter."""
        self.selected_handles: Set[EventHandle] = set()
        MatchesFilterBase.prepare(self, db, user)
        self.MFF = self.find_filter()
        if self.MFF:
            for family in db.iter_families():
                if self.MFF.apply_to_one(db, family):
                    self.events.update([e.ref for e in family.get_event_ref_list()])

    def apply_to_one(self, db: Database, event: Event) -> bool:
        """
        Return True if the event matches the filter rule.

        :returns: True or False
        """
        return event.handle in self.selected_handles
