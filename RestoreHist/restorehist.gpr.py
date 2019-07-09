#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2018      Paul Culley
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
# $Id$

#------------------------------------------------------------------------
#
# Restore History
#
#------------------------------------------------------------------------
register(GENERAL,
id    = 'RestoreHist',
name  = _("Restart where you were last working"),
description =  _("This addon causes Gramps to restart on the same view and"
                 " object where Gramps was previously closed.  It adds no "
                 "new menus or Gramplets, but allows the last six objects "
                 "visited to be found via the 'Go' menu."),
version = '0.0.9',
gramps_target_version = '5.1',
fname = "restorehist.py",
authors = ["Paul Culley"],
authors_email = ["paulr2787@gmail.com"],
category = TOOL_UTILS,
load_on_reg = True,
status = STABLE
  )
