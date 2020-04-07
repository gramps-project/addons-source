#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2017 Jerome Rapinat
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

"""
GRAMPS registration file
"""

MODULE_VERSION="5.1"

#------------------------------------------------------------------------
#
# Map relations with home person
#
#------------------------------------------------------------------------

register(TOOL,
id    = 'relationtab',
name  = _("Display relations and distances with the home person"),
description =  _("Will display relational informations with the home person"),
version = '1.0.14',
gramps_target_version = MODULE_VERSION,
include_in_listing = False,
status = STABLE,
fname = 'relation_tab.py',
authors = ["Jerome Rapinat"],
authors_email = ["romjerome@yahoo.fr"],
category = TOOL_ANAL,
toolclass = 'RelationTab',
optionclass = 'RelationTabOptions',
tool_modes = [TOOL_MODE_GUI, TOOL_MODE_CLI]
  )

