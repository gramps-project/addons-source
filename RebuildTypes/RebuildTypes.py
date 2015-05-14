#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013        Nick Hall
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id: RebuildTypes.py 2228 2013-10-17 16:46:53Z romjerome $

"""Tools/Database Processing/Rebuild Types"""


#-------------------------------------------------------------------------
#
# GRAMPS modules
#
#-------------------------------------------------------------------------
from gui.plug import tool
from QuestionDialog import OkDialog

from TransUtils import get_addon_translator
_ = get_addon_translator(__file__).gettext

#-------------------------------------------------------------------------
#
# RebuildTypes
#
#-------------------------------------------------------------------------
class RebuildTypes(tool.Tool):
    """
    Rebuild Gramps Types
    """

    def __init__(self, dbstate, uistate, options_class, name, callback=None):
        
        tool.Tool.__init__(self, dbstate, options_class, name)

        if self.db.readonly:
            return

        person_event_types = []
        family_event_types = []
        for handle in self.db.get_event_handles():
            event = self.db.get_event_from_handle(handle)
            if event.get_type().is_custom():
                links = [x[0] for x in self.db.find_backlink_handles(handle)]
                type_str = str(event.get_type())
                if 'Person' in links and type_str not in person_event_types:
                    person_event_types.append(type_str)
                if 'Family' in links and type_str not in family_event_types:
                    family_event_types.append(type_str)

        self.db.individual_event_names.update(person_event_types)
        self.db.family_event_names.update(family_event_types)
        
        total = len(person_event_types) + len(family_event_types)

        OkDialog(_("Gramps Types rebuilt"),
                 _('Found %d custom event types') % total,
                 parent=uistate.window)

#------------------------------------------------------------------------
#
# RebuildTypesOptions
#
#------------------------------------------------------------------------
class RebuildTypesOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
