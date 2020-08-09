#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2011 Nick Hall
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
# Register Gramplet
#
#------------------------------------------------------------------------
register(GRAMPLET,
         id="MediaBrowser",
         name=_("Media Browser"),
         description = _("Gramplet showing details of a person"),
         version = '1.0.30',
         gramps_target_version="5.1",
         status = STABLE, # not yet tested with python 3
         fname="MediaBrowser.py",
         height=200,
         gramplet = 'MediaBrowser',
         gramplet_title=_("Browser"),
         navtypes=["Person"],
         )
