#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
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
from gramps.gen.plug._pluginreg import *
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext

"""
Gramps registration file
"""

#------------------------------------------------------------------------
#
# Check and Repair Database for Missing Surnames (To help fix 10078)
#
#------------------------------------------------------------------------

register(TOOL,
id    = 'missing_surnames',
name  = _("Check and Repair Database for Missing Surnames"),
description =  _("Checks the database for integrity problems, fixing the "
                   "problems that it can"),
version = '1.0',
gramps_target_version = "5.0",
status = STABLE,
fname = 'NoSurnameCheckTool.py',
authors = ["The Gramps project"],
authors_email = ["http://gramps-project.org"],
category = TOOL_DBFIX,
toolclass = 'NoSurnameCheck',
optionclass = 'NoSurnameCheckOptions',
tool_modes = [TOOL_MODE_GUI, TOOL_MODE_CLI]
  )
