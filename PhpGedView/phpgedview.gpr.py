#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2007 Martin Hawlisch
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

register(TOOL,
         id    = 'PhpGedView',
         name  = _("PhpGedView"),
         description =  _("Download a GEDCOM file from a phpGedView server."),
         version = '0.0.13',
         gramps_target_version = "5.2",
         include_in_listing = False,
         status = UNSTABLE,
         fname = 'phpgedviewconnector.py',
         authors = ["Martin Hawlisch"],
         authors_email = ["martin.hawlisch@gmx.de"],
         category = TOOL_UTILS,
         toolclass = 'PHPGedViewConnector',
         optionclass = 'phpGedViewImporter',
         tool_modes = [TOOL_MODE_GUI],
         )

