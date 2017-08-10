#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017 Paul Culley
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
#from gramps.gen.plug._pluginreg import *
#from gramps.gen.const import GRAMPS_LOCALE as glocale
#_ = glocale.translation.gettext

"""
GRAMPS registration file
"""

register(TOOL,
    id = 'import_merge',
    name = _("Import and Merge tool"),
    description = _("Compares a Gramps XML database with the current one, and allows merging of the differences."),
    version = '0.0.0',
    gramps_target_version = "5.0",
    status = STABLE,
    fname = 'importmerge.py',
    authors = ["Paul Culley"],
    authors_email = ["paulr2787@gmail.com"],
    category = TOOL_DBPROC,
    toolclass = 'ImportMerge',
    optionclass = 'ImportMergeOptions',
    tool_modes = [TOOL_MODE_GUI],
)
