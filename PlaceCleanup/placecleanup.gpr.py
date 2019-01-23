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

"""
Place Cleanup Gramplet.
"""

register(
    GRAMPLET,
    id = "PlaceCleanup",
    name = _("Place Cleanup"),
    description = _("Place Cleanup Gramplet assists in merging places, as"
                    " well as completing places from the GeoNames web"
                    " database"),
    authors = ["Paul R. Culley"],
    authors_email = ["paulr2787@gmail.com"],
    status = STABLE,
    version = '1.0.8',
    gramps_target_version = '5.0',
    fname = "placecleanup.py",
    gramplet = 'PlaceCleanup',
    navtypes=["Place"],
    height = 375,
    detached_width = 510,
    detached_height = 480,
    expand = True,
    gramplet_title = _("Place Cleanup"),
    help_url="Addon:PlaceCleanup",
    include_in_listing = True,
    )
