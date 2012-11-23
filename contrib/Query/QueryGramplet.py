#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007  Donald N. Allingham
# Copyright (C) 2008  Brian Matherly
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

#import os

from gramps.gen.utils.trans import get_addon_translator
_ = get_addon_translator(__file__).gettext
from gramps.gui.plug.quick import run_quick_report_by_name

#from gramps.gen.const import USER_PLUGINS
#import os.path.join(USER_PLUGINS, 'PythonGramplet', 'PythonGramplet')

class QueryGramplet(PythonGramplet):
    def init(self):
        self.prompt = "$"
        self.set_tooltip(_("Enter SQL query"))
        # GUI setup:
        self.gui.textview.set_editable(True)
        self.set_text("Structured Query Language\n%s " % self.prompt)
        self.gui.textview.connect('key-press-event', self.on_key_press)

    def process_command(self, command):
        retval = run_quick_report_by_name(self.gui.dbstate, 
                                          self.gui.uistate, 
                                          'Query Quickview', 
                                          command)
        return retval

