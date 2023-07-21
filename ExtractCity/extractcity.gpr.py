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
Gramps registration file
"""

#------------------------------------------------------------------------
#
# Extract Place Data from a Place Title
#
#------------------------------------------------------------------------

register(TOOL,
id    = 'excity',
name  = _("Extract Place Data from a Place Title"),
description =  _("Attempts to extract city and state/province "
                 "from a place title"),
version = '1.0.13',
gramps_target_version = "5.2",
status = STABLE,
fname = 'extractcity.py',
authors = ["Donald N. Allingham"],
authors_email = ["don@gramps-project.org"],
category = TOOL_DBPROC,
toolclass = 'ExtractCity',
optionclass = 'ExtractCityOptions',
tool_modes = [TOOL_MODE_GUI]
  )
