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

# $Id: RebuildTypes.gpr.py 2374 2014-05-02 13:29:19Z romjerome $

register(TOOL, 
id    = 'rebuild_types',
name  = _("Rebuild Gramps Types"),
description =  _("Rebuilds Gramps Types"),
version = '1.0.4',
gramps_target_version = '4.1',
include_in_listing = False,
status = UNSTABLE,
fname = 'RebuildTypes.py',
authors = ["Nick Hall"],
authors_email = ["nick__hall@hotmail.com"],
category = TOOL_DBFIX,
toolclass = 'RebuildTypes',
optionclass = 'RebuildTypesOptions',
tool_modes = [TOOL_MODE_GUI, TOOL_MODE_CLI]
  )
