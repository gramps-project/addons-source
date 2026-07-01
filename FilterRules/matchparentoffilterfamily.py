#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2002-2006  Donald N. Allingham
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
# with this program; if not, see <https://www.gnu.org/licenses/>.
#

# -------------------------------------------------------------------------
#
# Standard Python modules
#
# -------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale

_ = glocale.translation.gettext

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules import MatchesFilterBase


# -------------------------------------------------------------------------
#
# Typing modules
#
# -------------------------------------------------------------------------
from gramps.gen.lib import Person
from gramps.gen.db import Database


# -------------------------------------------------------------------------
#
# MatchesFilter
#
# -------------------------------------------------------------------------
class MatchesParentOfFilterFamily(MatchesFilterBase):
    """
    Rule that checks against another filter.
g
    This is a base rule for subclassing by specific objects.
    Subclasses need to define the namespace class attribute.

    """
    labels = [_("Family filter name:")]
    name = _("Parents of <filter> family match")
    category = _("Family filters")

    # we want to have this filter show family filters
    namespace = "Family"
    
    def apply_to_one(self, db: Database, person: Person) -> bool:
        filt = self.find_filter()
        if filt:
            for handle in person.get_family_handle_list():
                family = db.get_family_from_handle(handle)
                if filt.apply_to_one(db, family):
                    return True
        return False

