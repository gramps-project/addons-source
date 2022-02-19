#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020  Matthias Kemmer
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
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gui.editors.filtereditor import MyFilters
from gramps.gen.filters.rules._matchesfilterbase import MatchesFilterBase
from gramps.gen.const import GRAMPS_LOCALE as glocale
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
        MyFilters.__init__(self,
                           caller_locals["filterdb"].get_filters('Family'))


# -------------------------------------------------------------------------
#
# Events matching family filter
#
# -------------------------------------------------------------------------
class IsFamilyFilterMatchEvent(MatchesFilterBase):
    """Rule that checks for an event matching a <family filter>."""

    labels = [(_('Family Filter name:'), FamFilt)]
    name = _('Events of families matching a <family filter>')
    description = _('Events of families matching a <family filter>')
    category = _('General filters')
    namespace = 'Family'

    def prepare(self, db, user):
        """Prepare a reference list for the filter."""
        self.events = set()
        MatchesFilterBase.prepare(self, db, user)
        self.MFF = self.find_filter()
        if self.MFF:
            for family_handle in db.iter_family_handles():
                if self.MFF.check(db, family_handle):
                    family = db.get_family_from_handle(family_handle)
                    event_refs = family.get_event_ref_list()
                    for event_ref in event_refs:
                        self.events.add(event_ref.ref)

    def apply(self, db, obj):
        """
        Return True if an event appies to the filter rule.

        :returns: True or False
        """
        if obj.get_handle() in self.events:
            return True
        return False
