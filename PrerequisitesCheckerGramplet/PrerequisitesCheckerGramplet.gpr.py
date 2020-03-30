#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2016-2018 Sam Manzi
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
# Diagnostic check that prerequisites have been met for the current install.
#
#------------------------------------------------------------------------

register(GRAMPLET,
         id="Prerequisites Checker Gramplet",
         name=_("Prerequisites Checker"),
         description = _("Prerequisites Checker Gramplet"),
         version = '0.8.27',
         gramps_target_version='5.1',
         status = STABLE,
         fname="PrerequisitesCheckerGramplet.py",
         height = 300,
         gramplet = 'PrerequisitesCheckerGramplet',
         gramplet_title=_("Prerequisites Checker"),
         help_url="PrerequisitesCheckerGramplet"
         )
