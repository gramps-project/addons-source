#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2009 Douglas S. Blank <doug.blank@gmail.com>
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

register(TOOL, 
         id    = 'SetAttribute',
         name  = _("Set Attribute"),
         description =  _("Set an attribute to a given value."),
         version = '0.0.15',
         gramps_target_version = '4.1',
         status = STABLE, # not yet tested with python 3
         fname = 'SetAttributeTool.py',
         authors = ["Douglas S. Blank"],
         authors_email = ["doug.blank@gmail.com"],
         category = TOOL_DBPROC,
         toolclass = 'SetAttributeWindow',
         optionclass = 'SetAttributeOptions',
         tool_modes = [TOOL_MODE_GUI],
         )

