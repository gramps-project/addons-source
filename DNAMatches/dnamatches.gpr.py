#
# Gramps - a GTK+/GNOME based genealogy program
# http://gramps-project.org
# Gramplet registration - plug-in/add-on to extend Gramps
#
# Copyright (C) 2020        Nick Hall
# Copyright (C) 2020-2022   Gary Griffin
# Copyright (C) 2023        Milan Kurovsky
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
register(GRAMPLET,
         id = "DNAMatches",
         name = _("DNA Matches"),
         authors = ["Milan Kurovsky"],
         authors_email = ["gxm210@gmail.com"],
         description = _("Gramplet to display a list of DNA matches"),
         status = STABLE,
         fname="dnamatches.py",
         height=100,
         expand=True,
         gramplet = 'DNAMatches',
         gramplet_title=_("DNA Matches"),
         detached_width = 600,
         detached_height = 450,
         version = '1.1.0',
         gramps_target_version='5.1',
         help_url="Addon:DNAMatches",
         include_in_listing = True
         )
