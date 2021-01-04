#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2021  Paul Culley
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
#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gui.plug import tool
from gramps.gui.utils import ProgressMeter
from gramps.gen.db import DbTxn
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


#-------------------------------------------------------------------------
#
# Removes spaces and replace ',' with '.' in place coordinates
#
#-------------------------------------------------------------------------
class FixCoords(tool.BatchTool):

    def __init__(self, dbstate, user, options_class, name, callback=None):
        uistate = user.uistate

        tool.BatchTool.__init__(self, dbstate, user, options_class, name)
        if self.fail:
            return

        if dbstate.db.readonly:
            return

        self.progress = ProgressMeter(_("Fix Coordinates"), _('Starting'),
                                      parent=uistate.window)
        uistate.set_busy_cursor(True)
        dbstate.db.disable_signals()
        steps = dbstate.db.get_number_of_places()
        self.progress.set_pass(_('Looking for possible coords with ","'
                                 ' characters'), steps)
        with DbTxn(_("Fix coords"), dbstate.db, batch=False) as trans:
            for place_handle in dbstate.db.get_place_handles():
                self.progress.step()
                place = dbstate.db.get_place_from_handle(place_handle)
                place_name = place.get_name()
                pname = place_name.get_value()
                found = False
                if pname != pname.strip():
                    found = True
                    place_name.set_value(pname.strip())
                plat = place.get_latitude()
                if plat != plat.strip().replace(',', '.'):
                    found = True
                    place.set_latitude(plat.strip().replace(',', '.'))
                plon = place.get_longitude()
                if plon != plon.strip().replace(',', '.'):
                    found = True
                    place.set_longitude(plon.strip().replace(',', '.'))
                if found:
                    dbstate.db.commit_place(place, trans)

        uistate.set_busy_cursor(False)
        # close the progress bar
        self.progress.close()
        dbstate.db.enable_signals()
        dbstate.db.request_rebuild()


# ------------------------------------------------------------------------
#
#
#
# ------------------------------------------------------------------------
class FixCoordsOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """

    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
