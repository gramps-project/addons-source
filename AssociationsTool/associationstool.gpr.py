#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Benny Malengier
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

MODULE_VERSION="4.2"

#------------------------------------------------------------------------
#
# Association State
#
#------------------------------------------------------------------------

register(TOOL,
id    = 'associationstool',
name  = "Check Associations data",
description =  _("Will check the data on Association for people."),
version = '1.0',
gramps_target_version = MODULE_VERSION,
include_in_listing = False,
status = STABLE,
fname = 'associationstool.py',
authors = ["Jerome Rapinat"],
authors_email = ["romjerome@yahoo.fr"],
category = TOOL_UTILS,
toolclass = 'AssociationsTool',
optionclass = 'AssociationsToolOptions',
tool_modes = [TOOL_MODE_GUI, TOOL_MODE_CLI]
  )


