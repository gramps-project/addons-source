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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

# $Id$

#------------------------------------------------------------------------
#
# Register Gramplet
#
#------------------------------------------------------------------------

register(GRAMPLET, 
         id="Extended Person Attributes", 
         name=_("Extended Person Attributes"), 
         description = _("Gramplet showing the attributes of a person"),
         version = '1.0.13',
         gramps_target_version="4.1",
         status = STABLE, # not yet tested with python 3
         fname="ExtendedAttributes.py",
         height=200,
         gramplet = 'ExtendedPersonAttributes',
         gramplet_title=_("Attributes"),
         navtypes=["Person"],
         )

register(GRAMPLET, 
         id="Extended Family Attributes", 
         name=_("Extended Family Attributes"), 
         description = _("Gramplet showing the attributes of a family"),
         version = '1.0.13',
         gramps_target_version="4.1",
         status = STABLE, # not yet tested with python 3
         fname="ExtendedAttributes.py",
         height=200,
         gramplet = 'ExtendedFamilyAttributes',
         gramplet_title=_("Attributes"),
         navtypes=["Family"],
         )
