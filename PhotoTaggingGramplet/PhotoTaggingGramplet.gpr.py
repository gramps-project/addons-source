#
# Gramps - a GTK+/GNOME based genealogy program
# http://gramps-project.org
# Gramplet registration - plug-in/add-on to extend Gramps
#
# Copyright (C) 2013    Artem Glebov <artem.glebov@gmail.com>
# Copyright (C) 2014    Nick Hall
# Copyright (C) 2021    Paul Culley
# Copyright (C) 2021    Bruce Jackson
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
         id="Photo Tagging",
         name=_("Photo Tagging"),
         description = _("Gramplet for tagging people in photos"),
         authors = ["Artem Glebov", "Nick Hall", "Paul Culley", "Bruce Jackson"],
         version = '1.0.41',
         gramps_target_version="5.1",
         status = STABLE,
         fname="PhotoTaggingGramplet.py",
         height=400,
         gramplet = 'PhotoTaggingGramplet',
         gramplet_title=_("Photo Tagging"),
         navtypes=["Media"],
         help_url="Addon:Photo_Tagging_Gramplet",
         include_in_listing = True,
         )
