#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2020       Matthias Kemmer
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
"""Filter rule that matches people who are matched by an event filter."""

# -------------------------------------------------------------------------
#
# Gramps modules
#
# -------------------------------------------------------------------------
from gramps.gen.filters.rules.person._matcheseventfilter import MatchesEventFilter
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


# -------------------------------------------------------------------------
#
# IsRelatedWithFilterMatch
#
# -------------------------------------------------------------------------
class PersonsHavingEventFilterMatch(MatchesEventFilter):
    """Filter rule that checks against an event filter."""

    labels = [_('Event filter name:')]
    name = _('People matching <event filter>')
    category = _("Event filters")
    description = _("Matches people who are matched by an event filter")
