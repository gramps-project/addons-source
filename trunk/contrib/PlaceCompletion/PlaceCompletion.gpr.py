#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007-2009  B. Malengier
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
         id    = 'PlaceCompletion',
         name  = _("PlaceCompletion"),
         description =  _("Provides a browsable list of selected places, with possibility to complete/parse/set the attribute fields."),
         version = '0.0.2',
         gramps_target_version = '3.3',
         status = STABLE,
         fname = 'PlaceCompletion.py',
         authors = ["B. Malengier"],
         authors_email = ["bm@cage.ugent.be"],
         category = TOOL_UTILS,
         toolclass = 'PlaceCompletion',
         optionclass = 'PlaceCompletionOptions',
         tool_modes = [TOOL_MODE_GUI]
         )

