#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2015       Tim G L Lyons
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

# $Id:$

"""
GRAMPS registration file
"""

#------------------------------------------------------------------------
#
# Download media files form the internet
#
#------------------------------------------------------------------------

register(TOOL, 
id    = 'downloadmedia',
name  = _("Download media files from the internet"),
description =  _("This tool downloads media files form the internet"),
version = '1.0.1',
gramps_target_version = '4.2',
status = STABLE,
fname = 'DownloadMedia.py',
authors = ["Tim Lyons"],
authors_email = [""],
category = TOOL_UTILS,
toolclass = 'DownloadMedia',
optionclass = 'DownloadMediaOptions',
tool_modes = [TOOL_MODE_GUI, TOOL_MODE_CLI]
  )
