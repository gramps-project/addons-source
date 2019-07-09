#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2013      Nick Hall
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

#------------------------------------------------------------------------
#
# Register Gramplet
#
#------------------------------------------------------------------------
register(GRAMPLET,
         id="Person Overview",
         name=_("Person Overview"),
         description = _("Gramplet showing an overview of events for a person"),
         version = '1.0.10',
         gramps_target_version="5.1",
         status = STABLE,
         fname="Overview.py",
         height=200,
         gramplet = 'PersonOverview',
         gramplet_title=_("Overview"),
         navtypes=["Person"],
         )

register(GRAMPLET,
         id="Family Overview",
         name=_("Family Overview"),
         description = _("Gramplet showing an overview of events for a family"),
         version = '1.0.10',
         gramps_target_version="5.1",
         status = STABLE,
         fname="Overview.py",
         height=200,
         gramplet = 'FamilyOverview',
         gramplet_title=_("Overview"),
         navtypes=["Family"],
         )
