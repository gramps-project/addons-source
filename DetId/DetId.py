#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016      Paul Culley
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
# $Id$

"""Tools/Utilities/Deterministic ID"""

#-------------------------------------------------------------------------
#
# Python modules
#
#-------------------------------------------------------------------------

#-------------------------------------------------------------------------
#
# Gtk modules
#
#-------------------------------------------------------------------------
from gi.repository import Gtk
from gi.repository import Gdk

#-------------------------------------------------------------------------
#
# Gramps modules
#
#-------------------------------------------------------------------------
from gramps.gui.plug import tool
from gramps.gui.managedwindow import ManagedWindow
from gramps.gen.utils.id import set_det_id
from gramps.gen.errors import WindowActiveError
from gramps.gui.dialog import WarningDialog

#------------------------------------------------------------------------
#
# Internationalisation
#
#------------------------------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

#-------------------------------------------------------------------------
#
# Deterministic ID
#
#-------------------------------------------------------------------------
class DetId(tool.Tool, ManagedWindow):
    def __init__(self, dbstate, user, options_class, name, callback=None):
        set_det_id(True)
        uistate = user.uistate
        if not uistate: return

        tool.Tool.__init__(self, dbstate, options_class, name)

        self.window_name = _('Deterministic ID Tool')
        ManagedWindow.__init__(self, uistate, [], self.__class__)

        window = MyWindow(dbstate, self.uistate, [])
        self.set_window(window, None, self.window_name)
        WarningDialog(self.window_name,
              _("The ID and handles now start at 0x00000000, and increment by 0x100000001"),
                self.window)
#------------------------------------------------------------------------
#
# My own widow class (to provide a source for dbstate)
#
#------------------------------------------------------------------------
class MyWindow(Gtk.Window):
    def __init__(self, dbstate, uistate, track):
        self.dbstate = dbstate
        self.uistate = uistate
        self.track = track
        Gtk.Window.__init__(self)

#------------------------------------------------------------------------
#
# Deterministic ID Options
#
#------------------------------------------------------------------------
class DetIdOptions(tool.ToolOptions):
    """
    Defines options and provides handling interface.
    """
    def __init__(self, name, person_id=None):
        tool.ToolOptions.__init__(self, name, person_id)
